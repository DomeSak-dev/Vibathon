"""Your company: the emissions of a company's AI use, for California SB 253 reporting.

Most companies are best served staying on a cloud AI API, so this reports what that use emits:
  kWh/month  = output tokens x Wh per 1,000 + calls x Wh per call   (team model sheet; PUE included)
  t CO2e/yr  = kWh/month x 12 x the grid CO2 rate where the AI runs (location-based)
Where the AI runs: the US average grid when the provider doesn't say, a common cloud region,
or any county picked on the map (its grid operator's 12-month EIA-930 mix).
It is Scope 3, Category 1 (purchased goods and services) under the GHG Protocol.
All numbers: data/siting_factors.json -> company.
"""
from __future__ import annotations

import json
import os

import anthropic

from . import catalog, siting

C = siting.F["company"]
E = siting.E
TIERS = ("small", "medium", "large")


# ---------------- usage -> energy and API cost ----------------
def model_rates(m: dict) -> dict:
    """Price and energy for one usage row: the team sheet's exact model when it is there,
    else the size class (Claude list price of that class, median energy of the class)."""
    cat = catalog.match(m["model"])
    cls, p = E["classes"][m["tier"]], C["api_price_per_m"][m["tier"]]
    priced = bool(cat and cat.get("price_in") is not None)
    measured = bool(cat and cat.get("wh_base") is not None)
    price_in = cat["price_in"] if priced else p["input"]
    return {
        "model": m["model"], "tier": m["tier"],
        "price_model": cat["model"] if priced else p["model"] + " (same size class)",
        "price_in": price_in, "price_out": cat["price_out"] if priced else p["output"],
        "price_cached": price_in * C["cached_price_share"] if priced else p["cached"],
        "fee_call": (cat.get("fee_call") or 0.0) if priced else 0.0,
        "energy_model": cat["model"] if measured else f"{m['tier']} class median",
        "wh_out": cat["wh_base"] if measured else cls["typical"],
        "wh_call": cat["wh_call"] if measured else cls.get("wh_per_call", 0.0),
    }


def kwh_month(summary: dict) -> float:
    """Facility kWh: output tokens x Wh per 1K + calls x Wh per call (the team sheet's method)."""
    tot = 0.0
    for m in summary["by_model"]:
        r = model_rates(m)
        tot += (m["output"] / 1000 * r["wh_out"] + m["requests"] * r["wh_call"]) / 1000
    return tot


def api_usd_month(summary: dict) -> float:
    tot = 0.0
    for m in summary["by_model"]:
        r = model_rates(m)
        tot += ((m["input"] - m["cached"]) * r["price_in"] + m["cached"] * r["price_cached"]
                + m["output"] * r["price_out"]) / 1e6 + m["requests"] * r["fee_call"]
    return tot


def tokens_month(summary: dict) -> float:
    return sum(m["input"] + m["output"] for m in summary["by_model"])


def model_table(summary: dict, scale: float, kg_kwh: float) -> list[dict]:
    rows = []
    for m in sorted(summary["by_model"], key=lambda m: -(m["input"] + m["output"]))[:10]:
        r = model_rates(m)
        tok = (m["input"] + m["output"]) * scale
        api = ((m["input"] - m["cached"]) * r["price_in"] + m["cached"] * r["price_cached"]
               + m["output"] * r["price_out"]) / 1e6 * scale + m["requests"] * scale * r["fee_call"]
        kwh = (m["output"] / 1000 * r["wh_out"] + m["requests"] * r["wh_call"]) / 1000 * scale
        rows.append({**r, "tokens_month": tok, "api_month": api, "kwh_month": kwh,
                     "kwh_year": kwh * 12, "kg_year": kwh * 12 * kg_kwh})
    return rows


# ---------------- where the AI runs ----------------
def place(geoid: str) -> dict:
    d = siting.table(siting.F["water"]["default_cooling"])
    r = d[d.GEOID == geoid]
    if r.empty:
        raise KeyError(geoid)
    r = r.iloc[0]
    return {"key": geoid, "GEOID": geoid, "label": f"{r.NAME}, {r.STUSPS}", "ba": r.ba,
            "kg_kwh": float(r.grid_co2_kg_kwh), "clean_share": float(r.grid_clean_share),
            "estimated": bool(r.grid_mix_est), "lat": float(r.lat), "lon": float(r.lon)}


def footprint(summary: dict, scale: float, site: str | None) -> dict:
    """Yearly location-based emissions of the company's AI use, where it runs and in the common cloud regions."""
    R = C["reporting"]
    us = {"key": "us", "GEOID": None, "label": "US average", "ba": None, "kg_kwh": R["provider_grid_kg_kwh"],
          "clean_share": None, "estimated": False}
    chosen = place(site) if site else us
    regions = []
    for g in R["cloud_regions"]:
        p = place(g["geoid"])
        regions.append(p | {"label": g["label"], "examples": g["examples"]})
    match = next((x for x in regions if x["GEOID"] == site), None)
    if match:
        chosen = match
    kwh_m = kwh_month(summary) * scale
    kwh_y = kwh_m * 12
    comps = [us] + regions + ([chosen] if site and not match else [])
    comps = [c | {"kg_year": kwh_y * c["kg_kwh"], "chosen": c["key"] == chosen["key"]} for c in comps]
    comps.sort(key=lambda c: c["kg_year"])
    kg_year = kwh_y * chosen["kg_kwh"]
    return {
        "inputs": {"scale": scale, "site": site},
        "site": chosen,
        "kg_year": kg_year,
        "kwh_year": kwh_y,
        "scope": R["scope_by_option"]["api"],
        "comparisons": comps,
        "cleanest": comps[0],
        "usage": {
            "tokens_month": tokens_month(summary) * scale, "api_month": api_usd_month(summary) * scale,
            "kwh_month": kwh_m, "by_model": model_table(summary, scale, chosen["kg_kwh"]),
            "days": summary["days"], "split_assumed": summary["split_assumed"],
        },
        "reporting": {k: v for k, v in R.items() if not k.startswith("_") and k != "cloud_regions"},
    }


# ---------------- Claude: a disclosure note for the SB 253 report ----------------
NOTE_SYSTEM = (
    "You write the methodology note a company files with its greenhouse-gas inventory for one line item: "
    "generative AI services bought through a cloud API, reported under California SB 253 as Scope 3, "
    "Category 1 (purchased goods and services). Use ONLY the facts in the JSON; never invent or recompute "
    "figures, and round what you quote. Write 4 short sentences in plain, formal language: the amount and the "
    "period it covers; the method (activity-based: tokens to kWh with per-model energy factors that include data "
    "center overhead, times a location-based grid emission factor for where the AI runs); the main limitation "
    "(the provider gives no customer-specific data, inference only, training and hardware excluded); and the next "
    "step (ask the provider for supplier-specific data or a region). No markdown, no lists, under 120 words."
)


def note_facts(a: dict) -> dict:
    u = a["usage"]
    return {
        "reporting_line": a["scope"],
        "emissions_kg_co2e_per_year": round(a["kg_year"]),
        "electricity_kwh_per_year": round(a["kwh_year"]),
        "tokens_per_month": round(u["tokens_month"]),
        "where_the_ai_runs": a["site"]["label"],
        "grid_factor_kg_co2_per_kwh": round(a["site"]["kg_kwh"], 3),
        "grid_factor_source": ("US average grid, used because the provider does not disclose its location"
                               if a["site"]["key"] == "us" else
                               f"{a['site']['ba']} grid operator, 12-month generation mix (EIA-930)"),
        "models": [{"model": m["model"], "energy_factor_source": m["energy_model"]} for m in u["by_model"]],
        "cleanest_region": {"label": a["cleanest"]["label"], "kg_co2e_per_year": round(a["cleanest"]["kg_year"])},
    }


def template_note(a: dict) -> str:
    f = note_facts(a)
    kg = f["emissions_kg_co2e_per_year"]
    amount = f"{kg / 1000:,.1f} t" if kg >= 1000 else f"{kg:,} kg"
    return (f"Generative AI services bought through a cloud API account for an estimated {amount} CO2e a year, "
            f"reported as {f['reporting_line']}. We estimated it from activity data: about {f['tokens_per_month']:,} "
            f"tokens a month, converted to {f['electricity_kwh_per_year']:,} kWh a year with per-model energy factors "
            f"that include data center overhead, times a location-based factor of {f['grid_factor_kg_co2_per_kwh']} kg "
            f"CO2 per kWh ({f['grid_factor_source']}). The provider gives no customer-specific data, and the figure "
            f"covers inference only. We will ask the provider for supplier-specific data and the region that serves us.")


def note(a: dict) -> dict:
    facts = note_facts(a)
    try:
        client = anthropic.Anthropic(timeout=40.0, max_retries=1)
        resp = client.beta.messages.create(
            model=os.getenv("CLAUDE_MODEL", "claude-opus-5-5"),
            max_tokens=4000,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=NOTE_SYSTEM,
            messages=[{"role": "user", "content": json.dumps(facts)}],
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError("refused")
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        if not text:
            raise RuntimeError("empty")
        return {"text": text, "source": "claude"}
    except Exception as e:  # noqa: BLE001 - the demo must never break
        return {"text": template_note(a), "source": "template", "error": type(e).__name__}
