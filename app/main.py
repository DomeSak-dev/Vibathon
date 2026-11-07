"""FastAPI app. Run: python -m uvicorn app.main:app --reload --port 8001"""
from __future__ import annotations

from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import catalog, company, listings, siting, usage

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="Where Tokens will Take You · data center siting")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


def _weights(wp: float, ww: float, wl: float) -> dict[str, float]:
    return {"power": max(wp, 0), "water": max(ww, 0), "land": max(wl, 0)}


def _cooling(c: str) -> str:
    if c not in siting.F["water"]["cooling"]:
        raise HTTPException(400, f"cooling must be one of {list(siting.F['water']['cooling'])}")
    return c


def _power(p: str) -> str:
    if p not in siting.F["pricing"]["power_sources"]:
        raise HTTPException(400, f"power must be one of {list(siting.F['pricing']['power_sources'])}")
    return p


DEF = siting.F["weights"]
COOL = siting.F["water"]["default_cooling"]
POWER = siting.F["pricing"]["default_power_source"]


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/config")
def config():
    return {"weights": DEF, "cooling": siting.F["water"]["cooling"], "default_cooling": COOL,
            "pricing": siting.F["pricing"], "default_power": POWER,
            "facility": siting.F["facility"], "acres_per_mw": siting.F["land"]["acres_per_mw"],
            "water_price_default": siting.F["water"]["price_per_kgal_default"],
            "environment": siting.F["environment"],
            "sources": siting.F["sources"], "regions": [{"id": "na", "label": "United States", "ready": True},
                                                        {"id": "eu", "label": "Europe (coming soon)", "ready": False},
                                                        {"id": "apac", "label": "Asia-Pacific (coming soon)", "ready": False}]}


@app.get("/api/map")
def map_layer(cooling: str = COOL, wp: float = DEF["power"], ww: float = DEF["water"], wl: float = DEF["land"],
              power: str = POWER):
    return siting.map_layer(_cooling(cooling), _weights(wp, ww, wl), _power(power))


@app.get("/api/county/{geoid}")
def county(geoid: str, cooling: str = COOL, wp: float = DEF["power"], ww: float = DEF["water"],
           wl: float = DEF["land"], power: str = POWER, env_mw: float | None = None):
    try:
        return siting.detail(geoid, _cooling(cooling), _weights(wp, ww, wl), _power(power), env_mw)
    except KeyError:
        raise HTTPException(404, "Unknown county") from None


@app.get("/api/sites/{geoid}")
def sites(geoid: str, cooling: str = COOL, wp: float = DEF["power"], ww: float = DEF["water"], wl: float = DEF["land"],
          power: str = POWER, min_mw: float = 0, deal: str = "sale"):
    """Three sites for sale or for lease in the county that fit the campus (live web search; see app/listings.py)."""
    try:
        r = siting.detail(geoid, _cooling(cooling), _weights(wp, ww, wl), _power(power))
    except KeyError:
        raise HTTPException(404, "Unknown county") from None
    need = listings.needs_for(r, min_mw, siting.F["land"]["acres_per_mw"], siting.F["facility"]["min_viable_mw"])
    name = r["NAME"] if any(w in r["NAME"] for w in ("County", "Parish", "Borough", "city")) else r["NAME"] + " County"
    return listings.find_sites(geoid, name, r["STATE_NAME"], r["STUSPS"], need, deal)


@app.get("/api/top")
def top(cooling: str = COOL, wp: float = DEF["power"], ww: float = DEF["water"], wl: float = DEF["land"],
        n: int = Query(10, le=50), min_mw: float = 0, state: str | None = None, power: str = POWER,
        by: str = "score"):
    return siting.top(_cooling(cooling), _weights(wp, ww, wl), n, min_mw, state, _power(power), by)


# ---------------- your company: AI emissions for SB 253 ----------------
MAX_UPLOAD = 25 * 1024 * 1024
SAMPLE = siting.DATA / "sample_usage.csv"


@app.get("/api/company/sample.csv")
def company_sample():
    return FileResponse(SAMPLE, filename="sample_usage.csv")


@app.post("/api/company/analyze")
async def company_analyze(
    file: UploadFile | None = File(None), scale: float = Form(1.0), site: str = Form(""),
    preset: str = Form(""), preset_model: str = Form("claude-sonnet-5"),
):
    """The company's AI use -> kWh and location-based CO2e a year, where it runs and in common cloud regions."""
    presets = siting.F["company"]["presets"]
    if file is None and preset in presets:
        summary, label = preset_summary(presets[preset], preset_model), f"{presets[preset]['label']} on {preset_model}"
    else:
        raw = await file.read() if file is not None else SAMPLE.read_bytes()
        if len(raw) > MAX_UPLOAD:
            raise HTTPException(413, "File too large (max 25 MB). Group it by day and model first.")
        try:
            summary = usage.summarize(usage.load_usage(raw))
        except usage.UsageError as e:
            raise HTTPException(400, str(e)) from None
        label = file.filename if file is not None else "Online store sample"
    try:
        out = company.footprint(summary, max(scale, 1e-6), site or None)
    except KeyError:
        raise HTTPException(404, "Unknown county") from None
    out["file"] = label
    return out


def preset_summary(p: dict, model: str) -> dict:
    """A usage summary for one of the sheet's developer scenarios, all on one model."""
    tier = usage.model_class(model)
    tiers = {c: {"input": 0.0, "cached": 0.0, "output": 0.0} for c in usage.CLASSES}
    tiers[tier] = {"input": float(p["input"]), "cached": 0.0, "output": float(p["output"])}
    return {"days": None, "tiers": tiers, "requests_month": float(p["requests"]),
            "models": [{"model": model, "tier": tier, "tokens_month": float(p["input"] + p["output"])}],
            "by_model": [{"model": model, "tier": tier, "input": float(p["input"]), "cached": 0.0,
                          "output": float(p["output"]), "requests": float(p["requests"])}],
            "split_assumed": False, "requests_assumed": False}


@app.get("/api/catalog")
def model_catalog():
    t = catalog.table()
    presets = {k: v["label"] for k, v in siting.F["company"]["presets"].items() if not k.startswith("_")}
    regions = siting.F["company"]["reporting"]["cloud_regions"]
    return {"presets": presets, "regions": regions,
            "models": [{"model": r.model, "provider": r.Provider, "tier": r.tier if isinstance(r.tier, str) else None,
                        "price_in": r.price_in, "price_out": r.price_out}
                       for r in t.itertuples() if isinstance(r.tier, str)]}


@app.post("/api/company/note")
def company_note(analysis: dict = Body(...)):
    """Claude drafts the SB 253 methodology note from the computed numbers (template without a key)."""
    return company.note(analysis)
