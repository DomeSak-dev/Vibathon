"""FastAPI app. Run: python -m uvicorn app.main:app --reload --port 8001"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import siting

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="Time to Power · data center siting")
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
            "sources": siting.F["sources"], "regions": [{"id": "na", "label": "North America", "ready": True},
                                                        {"id": "eu", "label": "Europe (coming soon)", "ready": False},
                                                        {"id": "apac", "label": "Asia-Pacific (coming soon)", "ready": False}]}


@app.get("/api/map")
def map_layer(cooling: str = COOL, wp: float = DEF["power"], ww: float = DEF["water"], wl: float = DEF["land"],
              power: str = POWER):
    return siting.map_layer(_cooling(cooling), _weights(wp, ww, wl), _power(power))


@app.get("/api/county/{geoid}")
def county(geoid: str, cooling: str = COOL, wp: float = DEF["power"], ww: float = DEF["water"],
           wl: float = DEF["land"], power: str = POWER):
    try:
        return siting.detail(geoid, _cooling(cooling), _weights(wp, ww, wl), _power(power))
    except KeyError:
        raise HTTPException(404, "Unknown county") from None


@app.get("/api/top")
def top(cooling: str = COOL, wp: float = DEF["power"], ww: float = DEF["water"], wl: float = DEF["land"],
        n: int = Query(10, le=50), min_mw: float = 0, state: str | None = None, power: str = POWER):
    return siting.top(_cooling(cooling), _weights(wp, ww, wl), n, min_mw, state, _power(power))
