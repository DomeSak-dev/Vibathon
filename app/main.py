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


DEF = siting.F["weights"]
COOL = siting.F["water"]["default_cooling"]


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/config")
def config():
    return {"weights": DEF, "cooling": siting.F["water"]["cooling"], "default_cooling": COOL,
            "sources": siting.F["sources"], "regions": [{"id": "na", "label": "North America", "ready": True},
                                                        {"id": "eu", "label": "Europe (coming soon)", "ready": False},
                                                        {"id": "apac", "label": "Asia-Pacific (coming soon)", "ready": False}]}


@app.get("/api/map")
def map_layer(cooling: str = COOL, wp: float = DEF["power"], ww: float = DEF["water"], wl: float = DEF["land"]):
    return siting.map_layer(_cooling(cooling), _weights(wp, ww, wl))


@app.get("/api/county/{geoid}")
def county(geoid: str, cooling: str = COOL, wp: float = DEF["power"], ww: float = DEF["water"],
           wl: float = DEF["land"]):
    try:
        return siting.detail(geoid, _cooling(cooling), _weights(wp, ww, wl))
    except KeyError:
        raise HTTPException(404, "Unknown county") from None


@app.get("/api/top")
def top(cooling: str = COOL, wp: float = DEF["power"], ww: float = DEF["water"], wl: float = DEF["land"],
        n: int = Query(10, le=50), min_mw: float = 0, state: str | None = None):
    return siting.top(_cooling(cooling), _weights(wp, ww, wl), n, min_mw, state)
