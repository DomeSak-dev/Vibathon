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

    # per-county km by class, and max kV
    pieces = gpd.overlay(lines[["kv", "geometry"]], cty[["GEOID", "geometry"]], how="intersection",
                         keep_geom_type=True)
    pieces["km"] = pieces.length / 1000
    pieces["cls"] = np.select([pieces.kv >= 450, pieces.kv >= 300], ["km_500", "km_345"], "km_230")
    km = pieces.pivot_table(index="GEOID", columns="cls", values="km", aggfunc="sum").fillna(0)
    km["max_kv"] = pieces.groupby("GEOID").kv.max()
    km["n_lines"] = pieces.groupby("GEOID").size()
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
        "ba": op.groupby("GEOID")["Balancing Authority Code"].agg(
            lambda s: s.dropna().mode().iat[0] if s.notna().any() else None),
    }).fillna({"gen_mw": 0, "gen_firm_mw": 0, "retire_mw": 0, "planned_mw": 0, "planned_n": 0})

    # planned mix (top technologies) for the detail panel
    mix = (pl[plan_year.le(2029)].groupby(["GEOID", "Technology"]).mw.sum()
           .reset_index().sort_values("mw", ascending=False))
    out["planned_mix"] = mix.groupby("GEOID").apply(
        lambda d: [[t, round(m)] for t, m in zip(d.Technology.head(3), d.mw.head(3))])
    return out.reset_index()


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
    # Connecticut's 2022 planning regions (and 2 new AK areas) have no 2015 USGS row:
    # estimate from the state's per-capita use, and flag it
    df["water_est"] = df.ps_mgd.isna()
    for c in ["ps_mgd", "ps_gw_mgd", "fresh_mgd", "irr_mgd", "thermo_mgd"]:
        st = df.groupby("STUSPS").apply(lambda d: d[c].sum() / d["pop"][d[c].notna()].sum())
        nat = df[c].sum() / df["pop"][df[c].notna()].sum()
        df[c] = df[c].fillna(df.STUSPS.map(st) * df["pop"]).fillna(nat * df["pop"])
    for c in ["km_230", "km_345", "km_500", "max_kv", "n_lines"]:
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
