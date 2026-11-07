"""Model catalog from the team sheet (data/model_catalog.csv, built by scripts/build_catalog.py):
real API prices and per-model energy (facility Wh per 1,000 output tokens + Wh per call)."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"


def key(name: str) -> str:
    n = str(name).strip().lower()
    n = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", n)
    return re.sub(r"-\d{8}$", "", n)


@lru_cache(maxsize=1)
def table() -> pd.DataFrame:
    return pd.read_csv(DATA / "model_catalog.csv")


@lru_cache(maxsize=512)
def match(name: str) -> dict | None:
    """Exact match after lowercasing and dropping a date suffix (gpt-4o-2024-08-06 -> gpt-4o).
    No fuzzy matching: claude-opus-5-5 must not pick up claude-opus-5's price. None if not in the sheet."""
    k = key(name)
    t = table()
    hit = t[t.key == k]
    if hit.empty:
        hit = t[t.key == re.sub(r"-latest$", "", k)]
    if hit.empty:
        return None
    r = hit.iloc[0].to_dict()
    return {k2: (None if pd.isna(v) else v) for k2, v in r.items()}
