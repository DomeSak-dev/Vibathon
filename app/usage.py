"""Usage CSV parser, copied from the AI Energy Bill project (app/energy.py).

Accepts provider exports (Claude Console, OpenAI, Google) or per-request logs and returns
one standard frame: model, size class, input / output / cached tokens, requests, date.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"
FACTORS = json.loads((DATA / "energy_factors.json").read_text(encoding="utf-8"))
EQ = FACTORS["equivalents"]
CLASSES = list(FACTORS["classes"])          # small, medium, large
LEVELS = ("low", "typical", "high")
DAYS_PER_MONTH = 30.4

# column aliases from Claude Console / OpenAI / Google exports and per-request logs
ALIASES = {
    "model": ["model", "model_name", "model_version", "model id", "model_id"],
    "input_tokens": ["input_tokens", "uncached_input_tokens", "prompt_tokens", "request tokens",
                     "request_tokens", "input", "contexttokens", "context_tokens"],
    "cached_tokens": ["cache_read_input_tokens", "cached_input_tokens", "input_cached_tokens",
                      "cache_read_tokens", "cache_read", "cached_tokens"],
    "cache_write_tokens": ["cache_creation_input_tokens", "cache_write_tokens", "cache_write"],
    "output_tokens": ["output_tokens", "completion_tokens", "response tokens", "response_tokens",
                      "output", "generatedtokens", "generated_tokens"],
    "total_tokens": ["total_tokens", "total tokens", "tokens"],
    "requests": ["requests", "num_requests", "num_model_requests", "request_count", "n_requests"],
    "date": ["date", "day", "usage_date", "usage_date_utc", "timestamp", "time",
             "starting_at", "start_time", "created_at"],
}


class UsageError(ValueError):
    pass


def model_class(name: str) -> str:
    from . import catalog                      # a model in the team sheet uses its measured size class
    m = catalog.match(name)
    if m and m.get("tier") in CLASSES:
        return m["tier"]
    n = str(name).lower()
    for rule in FACTORS["model_rules"]:
        if rule["match"] in n:
            return rule["class"]
    return FACTORS["default_class"]


def load_usage(raw: bytes) -> pd.DataFrame:
    """Read any usage CSV (daily export or per-request log) into a standard frame."""
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as e:  # noqa: BLE001
        raise UsageError(f"Could not read the CSV: {e}") from e
    lower = {c.strip().lower(): c for c in df.columns}
    out = pd.DataFrame(index=df.index)
    for std, names in ALIASES.items():
        for n in names:
            if n in lower:
                out[std] = df[lower[n]]
                break
    found = set(out.columns)
    if "model" not in out:
        out["model"] = "unknown-model"
    for c in ("input_tokens", "cached_tokens", "cache_write_tokens", "output_tokens", "total_tokens", "requests"):
        if c in out:
            out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0)
        elif c != "total_tokens":
            out[c] = 1 if c == "requests" else 0  # per-request log: one row = one request
    out["split_assumed"] = False
    out["requests_assumed"] = "requests" not in found
    if not found & {"input_tokens", "output_tokens"}:
        if "total_tokens" not in found:
            raise UsageError("No token columns found. Expected columns like "
                             "input_tokens / output_tokens or total_tokens.")
        # only a total is given: assume the BurstGPT input/output split (80/20)
        out["input_tokens"] = out["total_tokens"] * 0.8
        out["output_tokens"] = out["total_tokens"] * 0.2
        out["split_assumed"] = True
    # cache writes are processed like normal input
    out["input_tokens"] = out["input_tokens"] + out["cache_write_tokens"]
    out["total_tokens"] = out["input_tokens"] + out["cached_tokens"] + out["output_tokens"]
    if "date" in out:
        out["date"] = pd.to_datetime(out["date"], errors="coerce", utc=True).dt.tz_localize(None).dt.date
    out = out[out["total_tokens"] > 0]
    if out.empty:
        raise UsageError("The file has no rows with tokens.")
    out["model"] = out["model"].astype(str)
    out["class"] = out["model"].map(model_class)
    out["weighted"] = (out["output_tokens"] + FACTORS["input_weight"] * out["input_tokens"]
                       + FACTORS["cached_weight"] * out["cached_tokens"])
    return out


def summarize(df: pd.DataFrame) -> dict:
    """Scale a parsed usage frame to one month and split it by model size class."""
    has_dates = "date" in df and df["date"].notna().any()
    if has_dates:
        d = df["date"].dropna()
        days = max((d.max() - d.min()).days + 1, 1)
    else:
        days = DAYS_PER_MONTH
    k = DAYS_PER_MONTH / days
    by = df.groupby("class")[["input_tokens", "cached_tokens", "output_tokens", "requests"]].sum() * k
    tiers = {c: {"input": float(by.loc[c, "input_tokens"] + by.loc[c, "cached_tokens"]) if c in by.index else 0.0,
                 "cached": float(by.loc[c, "cached_tokens"]) if c in by.index else 0.0,
                 "output": float(by.loc[c, "output_tokens"]) if c in by.index else 0.0}
             for c in CLASSES}
    models = (df.groupby(["model", "class"]).total_tokens.sum() * k).sort_values(ascending=False).head(8)
    bm = df.groupby(["model", "class"])[["input_tokens", "cached_tokens", "output_tokens", "requests"]].sum() * k
    by_model = [{"model": m, "tier": c, "input": float(r.input_tokens + r.cached_tokens), "cached": float(r.cached_tokens),
                 "output": float(r.output_tokens), "requests": float(r.requests)} for (m, c), r in bm.iterrows()]
    return {
        "days": None if not has_dates else int(days),
        "tiers": tiers,
        "requests_month": float(df["requests"].sum() * k),
        "models": [{"model": m, "tier": c, "tokens_month": float(v)} for (m, c), v in models.items()],
        "by_model": by_model,
        "split_assumed": bool(df["split_assumed"].any()),
        "requests_assumed": bool(df["requests_assumed"].any()),
    }
