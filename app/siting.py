"""Siting model: county metrics -> power / water / land capacity (MW), scores, cost and tokens.

Supportable MW = min(power MW, water MW, land MW)        -> the binding factor is named
Power MW  = MW by highest line voltage x (1 + planned-generation bonus - retirement penalty)
Water MW  = 10% of public-supply withdrawals / water per MW (cooling design x local heat)
Land MW   = open acres x 0.2% / 1 acre per MW
Tokens/day = MW x utilization x 24 h / (Wh per 1,000 output tokens) x 1,000
Cost/year  = energy (state rate, or PPA + delivery) + capacity-market price (PJM, MISO, ISO-NE, NYISO)
             + water and sewer (default rate x stress)
             + capital charge x land (acres x state farmland $/acre x line-voltage premium)
All assumptions: ASSUMPTIONS.md. All numbers: data/siting_factors.json.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"
F = json.loads((DATA / "siting_factors.json").read_text(encoding="utf-8"))
E = json.loads((DATA / "energy_factors.json").read_text(encoding="utf-8"))
GAL_PER_L = 0.264172


def kv_tier(kv: float) -> str:
    return "500" if kv >= 450 else "345" if kv >= 300 else "230" if kv >= 220 else "0"


def water_mgd_per_mw(cooling: str, utilization: float) -> float:
    l_per_kwh = F["water"]["cooling"][cooling]["l_per_kwh"]
    return 1000 * 24 * utilization * l_per_kwh * GAL_PER_L / 1e6


def pct(s: pd.Series) -> pd.Series:
    return (s.rank(pct=True) * 100).round(1)


@lru_cache(maxsize=8)
def table(cooling: str = F["water"]["default_cooling"]) -> pd.DataFrame:
    d = pd.read_json(DATA / "counties.json", dtype={"GEOID": str})
    num = ["km_230", "km_345", "km_500", "max_kv", "n_lines", "gen_mw", "gen_firm_mw", "retire_mw",
           "planned_mw", "planned_n"]
    d[num] = d[num].fillna(0)
    P, W, L = F["power"], F["water"], F["land"]
    util = F["facility"]["utilization"]

    # power
    d["kv_tier"] = d.max_kv.map(kv_tier)
    bonus = np.minimum(P["planned_gen_bonus_cap"], d.planned_mw / 1000 * P["planned_gen_bonus_per_gw"])
    penalty = d.retire_mw / 1000 * P["retire_penalty_per_gw"]
    d["power_mw"] = (d.kv_tier.map(lambda t: P["mw_by_kv"][t]) * (1 + bonus - penalty).clip(0.5, 1.5)).round()
    d["months_lo"] = d.kv_tier.map(lambda t: P["months_by_kv"][t][0])
    d["months_hi"] = d.kv_tier.map(lambda t: P["months_by_kv"][t][1])
    hv_km = d.km_230 + 1.5 * d.km_345 + 2.5 * d.km_500
    price_pct = 100 - pct(d.elec_ind_c.fillna(d.elec_ind_c.median()))
    d["power_score"] = (0.55 * pct(d.power_mw + hv_km / 100) + 0.20 * pct(d.planned_mw + 0.2 * d.gen_firm_mw)
                        + 0.25 * price_pct).round(1)

    # water
    d["water_allow_mgd"] = d.ps_mgd * W["allowance_share_of_public_supply"]
    for c in ("precip_in", "cdd"):
        d[c] = d[c].fillna(d.groupby("STUSPS")[c].transform("median")).fillna(d[c].median())
    # hotter climates evaporate more cooling water per kWh (1,500 CDD ~ US median data-center market)
    d["heat_mult"] = (W["heat_base"] + (1 - W["heat_base"]) * d.cdd / W["heat_ref_cdd"]).clip(0.6, 1.6).round(2)
    d["water_mw"] = (d.water_allow_mgd / (water_mgd_per_mw(cooling, util) * d.heat_mult)).round()
    d["rain_mgd"] = d.precip_in * d.land_sqmi * 17.38 / 365          # 1 inch on 1 sq mi = 17.38 Mgal
    stress = (0.4 * pct(d.fresh_mgd / d.rain_mgd.clip(lower=0.01)) + 0.4 * (100 - pct(d.precip_in))
              + 0.2 * pct(d.irr_mgd / d.fresh_mgd.clip(lower=0.01)))
    d["water_stress"] = stress.round(1)          # 0 = little competition, 100 = heavy
    d["water_price"] = d.GEOID.map(lambda g: W["price_per_kgal_overrides"].get(g, {}).get("price",
                                                                                  W["price_per_kgal_default"]))
    d["water_score"] = (0.6 * pct(d.water_mw) + 0.4 * (100 - stress)).round(1)

    # land
    d["density"] = d["pop"] / d.land_sqmi.clip(lower=0.1)
    lo, hi = math.log(L["density_full_open"]), math.log(L["density_no_open"])
    open_share = (1 - (np.log(d.density.clip(lower=1)) - lo) / (hi - lo)).clip(0, 1)
    d["open_acres"] = (d.land_sqmi * 640 * open_share).round()
    d["land_mw"] = (d.open_acres * L["open_land_share_available"] / L["acres_per_mw"]).round()
    d["land_score"] = (0.5 * pct(d.land_mw) + 0.5 * (100 - pct(d.density))).round(1)

    # combined
    caps = d[["power_mw", "water_mw", "land_mw"]]
    d["supportable_mw"] = caps.min(axis=1).clip(lower=0).round()
    d["binding"] = caps.idxmin(axis=1).str.replace("_mw", "", regex=False)

    # grid operator: a county with no generator has none on file, so take the nearest county in the
    # same state that has one (any state if none does). Flagged as estimated.
    d["ba_est"] = d.ba.isna()
    d["ba_fill"] = d.ba
    lat, lon = np.radians(d.lat.to_numpy()), np.radians(d.lon.to_numpy())
    known = d.ba.notna().to_numpy()
    for i in np.flatnonzero(~known):
        pool = known & (d.STUSPS.to_numpy() == d.STUSPS.iat[i])
        if not pool.any():
            pool = known
        j = np.flatnonzero(pool)
        dx = (lon[j] - lon[i]) * np.cos((lat[j] + lat[i]) / 2)
        d.iat[i, d.columns.get_loc("ba_fill")] = d.ba.iat[j[np.argmin(dx * dx + (lat[j] - lat[i]) ** 2)]]

    # land price: state farmland value (USDA); Alaska, Hawaii and DC are not reported -> US average, flagged
    C = F["pricing"]
    d["land_usd_acre"] = d.STUSPS.map(C["land_usd_per_acre_by_state"])
    d["land_price_est"] = d.land_usd_acre.isna()
    d["land_usd_acre"] = d.land_usd_acre.fillna(C["land_usd_per_acre_us"])
    return d


@lru_cache(maxsize=16)
def priced(cooling: str = F["water"]["default_cooling"], power: str = F["pricing"]["default_power_source"]) -> pd.DataFrame:
    """Yearly cost of the campus each county can host. Missing inputs stay NaN, never zero."""
    d = table(cooling).copy()
    C, W = F["pricing"], F["water"]
    util = F["facility"]["utilization"]
    mw = d.supportable_mw
    mwh = mw * util * 8760

    # power: energy at the state industrial rate, or a PPA price plus delivery
    src = C["power_sources"][power]
    if src["usd_mwh"] is None:
        d["energy_usd_mwh"] = d.elec_ind_c * 10                      # cents/kWh -> $/MWh
    else:
        d["energy_usd_mwh"] = src["usd_mwh"] + sum(C["ppa_delivery_c_per_kwh"]) / 2 * 10
    d["energy_cost_year"] = mwh * d.energy_usd_mwh
    # capacity: priced where a capacity market sets it (PJM, MISO, ISO-NE, NYISO); NaN = inside the energy price
    south = (d.ba_fill == "MISO") & d.STUSPS.isin(C["capacity_miso_south_states"])
    d["capacity_key"] = d.ba_fill.where(~south, "MISO South")
    d["capacity_usd_mw_day"] = d.capacity_key.map(C["capacity_usd_per_mw_day"]).astype(float)
    d["capacity_cost_year"] = mw * d.capacity_usd_mw_day * 365

    # water and sewer: default rate scaled by water stress; a verified local rate is used as it is
    d["water_gal_year"] = mw * water_mgd_per_mw(cooling, util) * d.heat_mult * 1e6 * 365
    lo, hi = C["water_stress_multiplier"]
    local = d.GEOID.isin(list(W["price_per_kgal_overrides"]))
    d["water_rate_local"] = local
    d["water_mult"] = np.where(local, 1.0, (lo + (hi - lo) * d.water_stress / 100).round(2))
    d["water_rate"] = d.water_price * d.water_mult
    d["water_cost_year"] = d.water_gal_year / 1000 * d.water_rate
    d["sewer_cost_year"] = d.water_gal_year * C["sewer_share_of_water"] / 1000 * d.water_rate

    # land: bought once, carried at a yearly capital charge
    d["land_premium"] = d.kv_tier.map(C["land_premium_by_kv"]).astype(float)
    d["land_acres"] = mw * F["land"]["acres_per_mw"]
    d["land_cost"] = d.land_acres * d.land_usd_acre * d.land_premium
    d["land_cost_year"] = d.land_cost * C["capital_charge"]

    # NaN energy price -> NaN total (missing, not cheap); capacity NaN means "not priced separately"
    d["total_cost_year"] = (d.energy_cost_year + d.capacity_cost_year.fillna(0) + d.water_cost_year
                            + d.sewer_cost_year + d.land_cost_year)
    d["cost_mwh"] = (d.total_cost_year / mwh).where(mwh > 0).round(2)
    d["cost_score"] = (100 - pct(d.cost_mwh)).round(1)           # 100 = cheapest per MWh
    return d


def scored(cooling: str, weights: dict[str, float], power: str = F["pricing"]["default_power_source"]) -> pd.DataFrame:
    d = priced(cooling, power).copy()
    tot = sum(weights.values()) or 1
    d["score"] = sum(d[f"{k}_score"] * v for k, v in weights.items()) / tot
    d["score"] = d.score.round(1)
    return d


MAP_COLS = ["GEOID", "NAME", "STUSPS", "score", "power_score", "water_score", "land_score",
            "supportable_mw", "binding", "max_kv", "cost_mwh", "cost_score"]
DEF_POWER = F["pricing"]["default_power_source"]


def map_layer(cooling: str, weights: dict[str, float], power: str = DEF_POWER) -> list[dict]:
    d = scored(cooling, weights, power)
    return json.loads(d[MAP_COLS].to_json(orient="records"))


def tokens_per_day(mw: float, util: float) -> dict[str, dict[str, float]]:
    wh_day = mw * 1e6 * util * 24
    return {k: {lvl: wh_day / c[lvl] * 1000 for lvl in ("low", "typical", "high")} | {"label": c["label"],
                                                                                        "examples": c["examples"]}
            for k, c in E["classes"].items()}


def detail(geoid: str, cooling: str, weights: dict[str, float], power: str = DEF_POWER) -> dict:
    d = scored(cooling, weights, power)
    row = d[d.GEOID == geoid]
    if row.empty:
        raise KeyError(geoid)
    r = json.loads(row.to_json(orient="records"))[0]
    util = F["facility"]["utilization"]
    C = F["pricing"]
    mw = r["supportable_mw"]
    mwh_year = mw * util * 8760
    per_mw = water_mgd_per_mw(cooling, util) * r["heat_mult"]
    price = F["water"]["price_per_kgal_overrides"].get(geoid)
    src = C["power_sources"][power]
    r |= {
        "rank": int((d.score > r["score"]).sum()) + 1,
        "of": len(d),
        "state_rank": int((d[d.STUSPS == r["STUSPS"]].score > r["score"]).sum()) + 1,
        "cooling": cooling,
        "cooling_label": F["water"]["cooling"][cooling]["label"],
        "utilization": util,
        "energy_mwh_year": mwh_year,
        "power_source": power,
        "power_source_label": src["label"],
        "ppa_usd_mwh": src["usd_mwh"],
        "ppa_delivery_c": sum(C["ppa_delivery_c_per_kwh"]) / 2 if src["usd_mwh"] is not None else None,
        "elec_cost_year": r["energy_cost_year"],
        "capacity_where": C["capacity_where"].get(r["capacity_key"]),
        "capacity_est": r["capacity_key"] in C["capacity_est"],
        "sewer_share": C["sewer_share_of_water"],
        "capital_charge": C["capital_charge"],
        "land_price_where": (f"{r['STATE_NAME']} farmland, USDA 2026" if not r["land_price_est"]
                             else "US average farmland, USDA 2026 (state not reported)"),
        "water_mgd_need": mw * per_mw,
        "water_price_source": price["where"] if price else "National default (no local tariff loaded) ⚑",
        "water_share_of_ps": (mw * per_mw / r["ps_mgd"]) if r["ps_mgd"] else None,
        "tokens": tokens_per_day(mw, util),
        "all_cooling": {c: round(r["water_allow_mgd"] / (water_mgd_per_mw(c, util) * r["heat_mult"]))
                        for c in F["water"]["cooling"]},
    }
    return r


def top(cooling: str, weights: dict[str, float], n: int = 10, min_mw: float = 0,
        state: str | None = None, power: str = DEF_POWER) -> list[dict]:
    d = scored(cooling, weights, power)
    if state:
        d = d[d.STUSPS == state.upper()]
    d = d[d.supportable_mw >= min_mw].sort_values("score", ascending=False).head(n)
    return json.loads(d[MAP_COLS + ["lat", "lon"]].to_json(orient="records"))
