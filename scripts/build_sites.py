"""Join the raw datasets into one county table + a light grid-line layer for the map.

Inputs  (data/raw/, from scripts/fetch_data.py):
  transmission_230kv.geojson  HIFLD lines >= 230 kV
  eia860m.xlsx                EIA-860M Sep 2026: operating / planned / retiring generators
  usgs_water_2015.csv         USGS county water use 2015
  census_popest_2024.csv      Census county population, July 2024
  cb_2023_us_county_20m.zip   Census county shapes
  eia_epm_5_6_b.html          EIA state electricity prices, Jan-Aug 2026
Outputs:
  data/counties.json          one record per county (metrics; scoring happens in app/siting.py)
  app/static/data/grid.json   simplified >= 230 kV lines for the map

Run: python scripts/build_sites.py
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT_STATIC = ROOT / "app" / "static" / "data"
OUT_STATIC.mkdir(parents=True, exist_ok=True)
EQUAL_AREA = 5070  # NAD83 / Conus Albers, metres
MIN_LINE_KM = 5    # a line must run at least this far inside a county to count as reachable

STATE_ABBR = {"Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
              "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC",
              "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL",
              "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
              "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
              "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
              "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
              "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
              "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
              "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA",
              "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY"}


def counties() -> gpd.GeoDataFrame:
    g = gpd.read_file(f"zip://{RAW / 'cb_2023_us_county_20m.zip'}")
    g = g[~g.STATEFP.isin(["60", "66", "69", "72", "78"])]  # 50 states + DC
    g = g[["GEOID", "NAME", "STUSPS", "STATE_NAME", "ALAND", "geometry"]].to_crs(EQUAL_AREA)
    g["land_sqmi"] = g.ALAND / 2_589_988.11
    return g.reset_index(drop=True)


def transmission(cty: gpd.GeoDataFrame) -> pd.DataFrame:
    lines = gpd.read_file(RAW / "transmission_230kv.geojson")
    lines = lines[lines.STATUS.fillna("").str.upper().ne("NOT IN SERVICE")]
    lines["kv"] = pd.to_numeric(lines.VOLTAGE, errors="coerce")
    lines.loc[lines.VOLT_CLASS.eq("DC"), "kv"] = 500  # HVDC: treat as EHV
    lines = lines[lines.kv >= 220].to_crs(EQUAL_AREA)
    lines["lid"] = np.arange(len(lines))

    # map layer: simplify ~1 km, round to 0.01 deg
    m = lines.copy()
    m["geometry"] = m.geometry.simplify(1000)
    m = m.to_crs(4326)
    feats = []
    for kv, geom in zip(m.kv, m.geometry):
        if geom is None or geom.is_empty:
            continue
        gj = json.loads(gpd.GeoSeries([geom]).to_json())["features"][0]["geometry"]
        def rnd(c):
            return [rnd(x) for x in c] if isinstance(c[0], list) else [round(c[0], 2), round(c[1], 2)]
        gj["coordinates"] = rnd(gj["coordinates"])
        cls = 500 if kv >= 450 else 345 if kv >= 300 else 230
        feats.append({"type": "Feature", "properties": {"kv": cls}, "geometry": gj})
    (OUT_STATIC / "grid.json").write_text(json.dumps({"type": "FeatureCollection", "features": feats},
                                                    separators=(",", ":")), encoding="utf-8")

    # per-county km by class, max kV, and lines that run far enough inside the county to tap
    pieces = gpd.overlay(lines[["lid", "kv", "geometry"]], cty[["GEOID", "geometry"]], how="intersection",
                         keep_geom_type=True)
    pieces["km"] = pieces.length / 1000
    pieces["cls"] = np.select([pieces.kv >= 450, pieces.kv >= 300], ["km_500", "km_345"], "km_230")
    km = pieces.pivot_table(index="GEOID", columns="cls", values="km", aggfunc="sum").fillna(0)
    km["max_kv"] = pieces.groupby("GEOID").kv.max()
    per_line = pieces.groupby(["GEOID", "lid", "cls"], as_index=False).km.sum()
    q = per_line[per_line.km >= MIN_LINE_KM]          # a corner clip can't host a substation
    km["n_lines"] = per_line.groupby("GEOID").size()
    for c, n in [("km_500", "n_500"), ("km_345", "n_345"), ("km_230", "n_230")]:
        km[n] = q[q.cls == c].groupby("GEOID").size()
    km[["n_500", "n_345", "n_230"]] = km[["n_500", "n_345", "n_230"]].fillna(0).astype(int)
    return km.reset_index()


def generators(cty: gpd.GeoDataFrame) -> pd.DataFrame:
    xl = RAW / "eia860m.xlsx"
    op = pd.read_excel(xl, "Operating", header=2)
    pl = pd.read_excel(xl, "Planned", header=2)

    def pts(df):
        df = df.dropna(subset=["Latitude", "Longitude"]).copy()
        df["mw"] = pd.to_numeric(df["Nameplate Capacity (MW)"], errors="coerce").fillna(0)
        return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.Longitude, df.Latitude),
                                crs=4326).to_crs(EQUAL_AREA)

    op, pl = pts(op), pts(pl)
    op = gpd.sjoin(op, cty[["GEOID", "geometry"]], predicate="within")
    pl = gpd.sjoin(pl, cty[["GEOID", "geometry"]], predicate="within")
    ret_year = pd.to_numeric(op["Planned Retirement Year"], errors="coerce")
    plan_year = pd.to_numeric(pl["Planned Operation Year"], errors="coerce")
    firm = ["NG", "NUC", "WAT", "BIT", "SUB", "LIG", "RC", "DFO", "GEO", "WDS"]

    out = pd.DataFrame({
        "gen_mw": op.groupby("GEOID").mw.sum(),
        "gen_firm_mw": op[op["Energy Source Code"].isin(firm)].groupby("GEOID").mw.sum(),
        "retire_mw": op[ret_year.le(2030)].groupby("GEOID").mw.sum(),
        "planned_mw": pl[plan_year.le(2029)].groupby("GEOID").mw.sum(),
        "planned_n": pl[plan_year.le(2029)].groupby("GEOID").size(),
        "planned_clean_mw": pl[plan_year.le(2029) & pl.Technology.str.contains(
            "Solar|Wind|Batter|Nuclear|Hydro|Geothermal", case=False, na=False)].groupby("GEOID").mw.sum(),
        "ba": op.groupby("GEOID")["Balancing Authority Code"].agg(
            lambda s: s.dropna().mode().iat[0] if s.notna().any() else None),
    }).fillna({"gen_mw": 0, "gen_firm_mw": 0, "retire_mw": 0, "planned_mw": 0, "planned_n": 0, "planned_clean_mw": 0})

    # planned mix (top technologies) for the detail panel
    mix = (pl[plan_year.le(2029)].groupby(["GEOID", "Technology"]).mw.sum()
           .reset_index().sort_values("mw", ascending=False))
    out["planned_mix"] = mix.groupby("GEOID").apply(
        lambda d: [[t, round(m)] for t, m in zip(d.Technology.head(3), d.mw.head(3))])
    return out.reset_index()


# Share of a plant's summer capacity that can be counted on at the evening peak (rough capacity credits)
CAPACITY_CREDIT = {"SUN": 0.3, "WND": 0.15}


def grid_tightness() -> pd.DataFrame:
    """Peak hourly demand (EIA-930, last 12 months) vs. firm generating capacity (EIA-860M) per
    balancing authority. Margin = capacity / peak - 1. Line loading itself is not public (CEII)."""
    peaks = []
    for f in ("eia930_2025_H2.csv", "eia930_2026_H1.csv"):
        d = pd.read_csv(RAW / f, usecols=["Balancing Authority", "Demand (MW) (Adjusted)"], thousands=",")
        d["mw"] = pd.to_numeric(d["Demand (MW) (Adjusted)"], errors="coerce")
        peaks.append(d.dropna(subset=["mw"]))
    d = pd.concat(peaks)
    # 99.9th percentile of the hours drops bad readings but keeps the true peak (~9 hours a year)
    peak = d.groupby("Balancing Authority").mw.quantile(0.999)
    op = pd.read_excel(RAW / "eia860m.xlsx", "Operating", header=2)
    op["mw"] = pd.to_numeric(op["Net Summer Capacity (MW)"], errors="coerce").fillna(0)
    op["firm"] = op.mw * op["Energy Source Code"].map(CAPACITY_CREDIT).fillna(1.0)
    cap = op.groupby("Balancing Authority Code").firm.sum()
    t = pd.DataFrame({"ba_peak_mw": peak, "ba_firm_mw": cap}).dropna()
    t = t[t.ba_peak_mw > 100]
    t["ba_margin"] = t.ba_firm_mw / t.ba_peak_mw - 1
    return t.rename_axis("ba").reset_index()


# Grid mix from EIA-930 hourly generation by fuel (same 12 months as grid tightness).
FUELS = {
    "coal": ["Coal"], "gas": ["Natural Gas"], "nuclear": ["Nuclear"], "oil": ["All Petroleum Products"],
    "hydro": ["Hydropower Excluding Pumped Storage"],
    "solar": ["Solar without Integrated Battery Storage", "Solar with Integrated Battery Storage"],
    "wind": ["Wind without Integrated Battery Storage", "Wind with Integrated Battery Storage"],
    "geothermal": ["Geothermal"], "other": ["Other Fuel Sources", "Unknown Fuel Sources"],
}
# kg CO2 per kWh generated: EIA FAQ "How much carbon dioxide is produced per kWh" (coal 2.30, gas 0.97,
# petroleum 2.38 lb/kWh); "other" (biomass, waste, unknown) is a rough 0.5
CO2_KG_KWH = {"coal": 1.04, "gas": 0.44, "oil": 1.08, "other": 0.5}
# litres of water consumed per kWh at the power plant: NREL Macknick et al. 2012 medians
# (coal 687, gas combined cycle 198, nuclear 672 gal/MWh with cooling towers); hydro reservoir evaporation excluded
WATER_L_KWH = {"coal": 2.60, "gas": 0.75, "nuclear": 2.54, "oil": 1.5, "other": 1.0, "geothermal": 1.0, "solar": 0.004}
CLEAN = ("nuclear", "hydro", "solar", "wind", "geothermal")


def grid_mix() -> pd.DataFrame:
    parts = []
    for f in ("eia930_2025_H2.csv", "eia930_2026_H1.csv"):
        cols = ["Balancing Authority"] + [f"Net Generation (MW) from {c}" for cs in FUELS.values() for c in cs]
        d = pd.read_csv(RAW / f, usecols=cols, thousands=",")
        out = pd.DataFrame({"ba": d["Balancing Authority"]})
        for fuel, cs in FUELS.items():
            out[fuel] = sum(pd.to_numeric(d[f"Net Generation (MW) from {c}"], errors="coerce").fillna(0).clip(lower=0)
                            for c in cs)
        parts.append(out)
    g = pd.concat(parts).groupby("ba").sum()           # MWh over 12 months (hourly MW)
    tot = g.sum(axis=1)
    g = g[tot > 0]
    share = g.div(g.sum(axis=1), axis=0)
    res = pd.DataFrame({
        "grid_co2_kg_kwh": sum(share[f] * v for f, v in CO2_KG_KWH.items()),
        "grid_clean_share": share[list(CLEAN)].sum(axis=1),
        "grid_water_l_kwh": sum(share[f] * v for f, v in WATER_L_KWH.items()),
        "grid_gen_twh": g.sum(axis=1) / 1e6,
        "grid_mix": share.round(3).apply(lambda r: {k: v for k, v in r.items() if v >= 0.01}, axis=1),
    })
    return res.rename_axis("ba").reset_index()


def water() -> pd.DataFrame:
    w = pd.read_csv(RAW / "usgs_water_2015.csv", skiprows=1, dtype={"FIPS": str})
    w.columns = [c.strip() for c in w.columns]
    w["GEOID"] = w.FIPS.str.zfill(5)
    num = lambda c: pd.to_numeric(w[c], errors="coerce").fillna(0)  # noqa: E731
    return pd.DataFrame({
        "GEOID": w.GEOID,
        "ps_mgd": num("PS-Wtotl"),             # public-supply withdrawals, Mgal/day
        "ps_gw_mgd": num("PS-WGWFr"),          # ... of which fresh groundwater
        "fresh_mgd": num("TO-WFrTo"),          # all fresh withdrawals
        "irr_mgd": num("IR-WFrTo"),            # irrigation
        "thermo_mgd": num("PT-WFrTo") if "PT-WFrTo" in w else 0,
    })


def population() -> pd.DataFrame:
    p = pd.read_csv(RAW / "census_popest_2024.csv", encoding="latin-1", dtype={"STATE": str, "COUNTY": str})
    p = p[p.SUMLEV == 50]
    return pd.DataFrame({"GEOID": p.STATE.str.zfill(2) + p.COUNTY.str.zfill(3), "pop": p.POPESTIMATE2024})


def prices() -> pd.DataFrame:
    t = pd.read_html(RAW / "eia_epm_5_6_b.html")[1]
    t.columns = ["state", "res", "res_prev", "com", "com_prev", "ind", "ind_prev", "tr", "tr_prev", "all", "all_prev"]
    t = t[t.state.isin(STATE_ABBR)]
    return pd.DataFrame({"STUSPS": t.state.map(STATE_ABBR),
                         "elec_com_c": pd.to_numeric(t.com, errors="coerce"),
                         "elec_ind_c": pd.to_numeric(t.ind, errors="coerce")})


NCDC_STATES = ["AL", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "ID", "IL", "IN", "IA", "KS", "KY", "LA",
               "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND",
               "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"]


def climate() -> pd.DataFrame:
    """NOAA nClimDiv county normals (1991-2020, period code 0010): annual precipitation (in) and cooling degree days."""
    fips = {a: f for a, f in zip(*[pd.read_csv(RAW / "usgs_water_2015.csv", skiprows=1, dtype=str)[c]
                                    for c in ("STATE", "STATEFIPS")])}
    out = {}
    for name, file in [("precip_in", "noaa_norm_pcpn_county.txt"), ("cdd", "noaa_norm_cdd_county.txt")]:
        vals = {}
        for line in (RAW / file).read_text().splitlines():
            code, *months = line.split()
            if code[7:11] != "0010":
                continue
            n = int(code[:2])
            st = "AK" if n == 50 else NCDC_STATES[n - 1] if n <= 48 else None
            if st is None:
                continue
            vals[fips[st].zfill(2) + code[2:5]] = sum(float(m) for m in months)
        out[name] = pd.Series(vals)
    return pd.DataFrame(out).rename_axis("GEOID").reset_index()


def main() -> None:
    cty = counties()
    print("counties", len(cty))
    df = pd.DataFrame(cty.drop(columns="geometry"))
    for part, key in [(transmission(cty), "GEOID"), (generators(cty), "GEOID"), (water(), "GEOID"),
                      (population(), "GEOID"), (climate(), "GEOID"), (prices(), "STUSPS")]:
        df = df.merge(part, on=key, how="left")
        print("joined", list(part.columns)[:4], "...")
    # grid operator for counties with no power plant: the nearest county in the same state that has one
    # (any state if none does), flagged as estimated
    xy = cty.geometry.centroid
    df["ba_est"] = df.ba.isna()
    known = df.ba.notna().to_numpy()
    x, y, st = xy.x.to_numpy(), xy.y.to_numpy(), df.STUSPS.to_numpy()
    ba = df.ba.to_numpy(dtype=object).copy()
    for i in np.flatnonzero(~known):
        pool = known & (st == st[i])
        if not pool.any():
            pool = known
        j = np.flatnonzero(pool)
        ba[i] = df.ba.iat[j[np.argmin((x[j] - x[i]) ** 2 + (y[j] - y[i]) ** 2)]]
    df["ba"] = ba
    print("grid operator estimated for", int(df.ba_est.sum()), "counties (nearest county with a plant)")
    gt = grid_tightness()
    df = df.merge(gt, on="ba", how="left")
    df = df.merge(grid_mix(), on="ba", how="left")
    # drop operators whose reported generation is implausible next to their peak (e.g. BANC reports
    # ~100x its real output): more than 3x what running at peak all year would produce
    bad = df.grid_gen_twh > df.ba_peak_mw.fillna(0) * 8760 / 1e6 * 3
    mix_cols = ["grid_co2_kg_kwh", "grid_clean_share", "grid_water_l_kwh"]
    df.loc[bad, mix_cols + ["grid_mix"]] = None
    df["grid_mix_est"] = df.grid_co2_kg_kwh.isna()
    for c in mix_cols:   # counties without a usable operator: their state's median, else the US median
        df[c] = df[c].fillna(df.groupby("STUSPS")[c].transform("median")).fillna(df[c].median())
    print("grid mix for", int((~df.grid_mix_est).sum()), "counties;", int(bad.sum()), "dropped as implausible")
    print("grid tightness for", int(df.ba_margin.notna().sum()), "counties;", len(gt), "operators")
    # Connecticut's 2022 planning regions (and 2 new AK areas) have no 2015 USGS row:
    # estimate from the state's per-capita use, and flag it
    df["water_est"] = df.ps_mgd.isna()
    for c in ["ps_mgd", "ps_gw_mgd", "fresh_mgd", "irr_mgd", "thermo_mgd"]:
        st = df.groupby("STUSPS").apply(lambda d: d[c].sum() / d["pop"][d[c].notna()].sum())
        nat = df[c].sum() / df["pop"][df[c].notna()].sum()
        df[c] = df[c].fillna(df.STUSPS.map(st) * df["pop"]).fillna(nat * df["pop"])
    for c in ["km_230", "km_345", "km_500", "max_kv", "n_lines", "n_500", "n_345", "n_230"]:
        df[c] = df.get(c, 0)
        df[c] = df[c].fillna(0)
    shapes = cty[["GEOID", "geometry"]].copy()
    shapes["geometry"] = shapes.geometry.simplify(1500)
    shapes = shapes.to_crs(4326)
    shapes["geometry"] = shapes.geometry.set_precision(0.01)
    (OUT_STATIC / "counties.geojson").write_text(shapes.to_json(drop_id=True), encoding="utf-8")
    cen = cty.geometry.centroid.to_crs(4326)
    df["lon"], df["lat"] = cen.x.round(3), cen.y.round(3)
    df = df.drop(columns=["ALAND"])
    recs = json.loads(df.to_json(orient="records"))
    (ROOT / "data" / "counties.json").write_text(json.dumps(recs), encoding="utf-8")
    print("wrote", len(recs), "counties;", "missing water:", int(df.ps_mgd.isna().sum()),
          "missing pop:", int(df["pop"].isna().sum()))


if __name__ == "__main__":
    main()
