"""Turn the team's model spreadsheet (data/raw/sheet/sheet.xlsx) into data/model_catalog.csv and
recalibrate the small / medium / large energy factors in data/energy_factors.json.

Sheet: https://docs.google.com/spreadsheets/d/1m6kRk2w5xF75yZ-zI-F9LhEcI-Ypx3Gs (tabs Model rates,
Energy inputs, Usage assumptions). Energy factors there are EcoLogits-based IT energy (H100, 16-bit,
batch 64) per 1,000 OUTPUT tokens plus a fixed amount per call; we multiply by the provider PUE so
every factor here is at the facility.
Run: python scripts/build_catalog.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SHEET = ROOT / "data" / "raw" / "sheet" / "sheet.xlsx"
OUT = ROOT / "data" / "model_catalog.csv"
FACTORS = ROOT / "data" / "energy_factors.json"
# size class from facility Wh per 1,000 output tokens (base case)
SMALL_MAX, MEDIUM_MAX = 0.8, 3.5


def key(name: str) -> str:
    """Normalise a model name: lowercase, no date suffix."""
    n = str(name).strip().lower()
    n = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", n)
    n = re.sub(r"-\d{8}$", "", n)
    return n


def main() -> None:
    rates = pd.read_excel(SHEET, "Model rates", header=4)
    energy = pd.read_excel(SHEET, "Energy inputs", header=4)
    rates = rates.rename(columns={"Exact calculator model / rate variant": "model", "Input $ / 1M": "price_in",
                                  "Output $ / 1M": "price_out", "Fixed $ / call": "fee_call",
                                  "Price verification": "price_check", "As of": "as_of"})
    energy = energy.rename(columns={"Exact model": "model", "Proxy output IT Wh / 1K low": "it_low",
                                    "Proxy output IT Wh / 1K base": "it_base", "Proxy output IT Wh / 1K high": "it_high",
                                    "Fixed IT Wh / call base": "it_call", "PUE base": "pue"})
    df = rates[["Provider", "model", "price_in", "price_out", "fee_call", "price_check", "as_of"]].merge(
        energy[["model", "it_low", "it_base", "it_high", "it_call", "pue"]], on="model", how="left")
    df = df.dropna(subset=["model"])
    df["key"] = df.model.map(key)
    for lv in ("low", "base", "high"):
        df[f"wh_{lv}"] = df[f"it_{lv}"] * df.pue          # facility Wh / 1K output tokens
    df["wh_call"] = df.it_call * df.pue                    # facility Wh per call
    df["tier"] = pd.cut(df.wh_base, [0, SMALL_MAX, MEDIUM_MAX, 1e9], labels=["small", "medium", "large"]).astype(str)
    df.loc[df.wh_base.isna(), "tier"] = ""
    cols = ["Provider", "model", "key", "tier", "price_in", "price_out", "fee_call", "wh_low", "wh_base", "wh_high",
            "wh_call", "pue", "price_check", "as_of"]
    df[cols].round(4).to_csv(OUT, index=False)
    print(f"wrote {OUT.name}: {len(df)} models, {int(df.wh_base.notna().sum())} with energy factors")

    # recalibrate tiers: median of the catalog models in each class
    f = json.loads(FACTORS.read_text(encoding="utf-8"))
    e = df[df.wh_base.notna()]
    for t in ("small", "medium", "large"):
        g = e[e.tier == t]
        c = f["classes"][t]
        c.update({"low": round(float(g.wh_low.median()), 3), "typical": round(float(g.wh_base.median()), 3),
                  "high": round(float(g.wh_high.median()), 3), "wh_per_call": round(float(g.wh_call.median()), 4),
                  "n_models": int(len(g)), "examples": ", ".join(g.sort_values("wh_base").model.head(4))})
        print(t, {k: c[k] for k in ("low", "typical", "high", "wh_per_call", "n_models")})
    f["input_weight"] = 0.0
    f["cached_weight"] = 0.0
    f["_note"] = ("Facility Wh per 1,000 OUTPUT tokens plus a fixed Wh per call, from the team model sheet "
                  "(EcoLogits proxy x provider PUE; median of the models in each class). Input tokens are not "
                  "charged separately, following the sheet: input effects are unresolved. See ASSUMPTIONS.md.")
    f["sources"]["energy"].insert(0, "Team model sheet (EcoLogits-based, H100/16-bit/batch-64 proxy), "
                                     "https://docs.google.com/spreadsheets/d/1m6kRk2w5xF75yZ-zI-F9LhEcI-Ypx3Gs")
    FACTORS.write_text(json.dumps(f, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
