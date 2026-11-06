"""Download the raw public datasets into data/raw/. Run once: python scripts/fetch_data.py"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (vibathon-siting-prototype)"}

SOURCES = {
    # EIA-860M: every US generator, operating + planned, with lat/lon and MW
    "eia860m.xlsx": "https://www.eia.gov/electricity/data/eia860m/xls/september_generator2026.xlsx",
    # USGS county water use 2015 (latest county-level national compilation)
    "usgs_water_2015.csv": "https://www.sciencebase.gov/catalog/file/get/5af3311be4b0da30c1b245d8?f=__disk__eb%2F74%2Feb%2Feb74ebb41169c76aaf374990bd5a71cac82604c1",
    # Census Gazetteer: county land area + centroid
    "gazetteer_counties.zip": "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_counties_national.zip",
    # Census county population estimates, July 2024 (one CSV, no key)
    "census_popest_2024.csv": "https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/counties/totals/co-est2024-alldata.csv",
    # County shapes for the map
    "counties-10m.json": "https://cdn.jsdelivr.net/npm/us-atlas@3/counties-10m.json",
}

TX_URL = ("https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/"
          "US_Electric_Power_Transmission_Lines/FeatureServer/0/query")


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def fetch_transmission(min_kv: int = 230) -> None:
    """HIFLD transmission lines >= min_kv as one GeoJSON (simplified ~500 m)."""
    out = RAW / "transmission_230kv.geojson"
    if out.exists():
        print("skip", out.name); return
    feats, offset = [], 0
    while True:
        q = urllib.parse.urlencode({
            "where": f"VOLTAGE>={min_kv}", "outFields": "VOLTAGE,VOLT_CLASS,OWNER,STATUS,SUB_1,SUB_2",
            "f": "geojson", "outSR": 4326, "resultOffset": offset, "resultRecordCount": 2000,
            "maxAllowableOffset": 0.005, "geometryPrecision": 3})
        page = json.loads(get(f"{TX_URL}?{q}"))
        feats += page.get("features", [])
        print(f"  transmission: {len(feats)} features")
        if len(page.get("features", [])) < 2000:
            break
        offset += 2000
        time.sleep(0.3)
    out.write_text(json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8")


def main() -> None:
    for name, url in SOURCES.items():
        p = RAW / name
        if p.exists():
            print("skip", name); continue
        print("get ", name)
        p.write_bytes(get(url))
    fetch_transmission()
    print("done")


if __name__ == "__main__":
    sys.exit(main())
