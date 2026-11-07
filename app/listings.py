"""Sites for sale: up to three parcels or buildings in a county that fit the campus.

Live: Claude searches the web with Anthropic's server-side web search and web fetch tools, opens each
listing page to read its size, price, utilities and photo, and returns its picks through a strict tool.
Every URL we return must come from a search result or a page Claude fetched, so a made-up link can never
reach the screen. Needs ANTHROPIC_API_KEY (or another credential the Anthropic SDK finds) and
`pip install anthropic`.

Snapshot: app/static/data/listings.json holds listings read from public listing pages on a stated date,
for the top counties. It answers when live search is off or fails, marked with its date.
Without either, the endpoint answers status "unavailable" and the app shows search links instead.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import threading
import time
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlsplit

MODEL = "claude-opus-5-5"
CACHE_TTL_S = 6 * 3600          # listings move; re-search a county after 6 hours
MAX_TURNS = 6
SNAPSHOT = Path(__file__).parent / "static" / "data" / "listings.json"
_cache: dict[tuple, tuple[float, dict]] = {}
_lock = threading.Lock()

SUBMIT_TOOL = {
    "name": "submit_sites",
    "description": "Return your final picks: up to 3 sites for sale right now, best first. Call this once, at the end.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["sites", "note"],
        "properties": {
            "sites": {
                "type": "array",
                "description": "Up to 3 sites",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["name", "url", "kind", "acres", "sq_ft", "price_usd", "price_text", "location", "zoning",
                                 "facilities", "highlights", "image_url", "fit", "check", "still_listed"],
                    "properties": {
                        "name": {"type": "string", "description": "Listing title, short"},
                        "url": {"type": "string", "description": "The listing page URL, exactly as found"},
                        "kind": {"type": "string", "enum": ["land", "building"]},
                        "acres": {"type": ["number", "null"], "description": "Lot size in acres, null if not stated"},
                        "sq_ft": {"type": ["number", "null"], "description": "Building floor area in square feet, null if none or not stated"},
                        "price_usd": {"type": ["number", "null"], "description": "Asking price in US dollars, null if not stated"},
                        "price_text": {"type": ["string", "null"], "description": "The price as the listing shows it, e.g. 'Call for pricing'"},
                        "location": {"type": "string", "description": "Address or road and city, as the listing gives it"},
                        "zoning": {"type": ["string", "null"], "description": "Zoning as the listing states it, null if not stated"},
                        "facilities": {"type": "array", "items": {"type": "string"},
                                       "description": "Up to 5 short phrases on utilities and infrastructure the listing states: power, water, sewer, gas, rail, road access, buildings"},
                        "highlights": {"type": "array", "items": {"type": "string"},
                                       "description": "Up to 3 short phrases on other details worth knowing, from the listing"},
                        "image_url": {"type": ["string", "null"], "description": "URL of the listing's main photo exactly as it appears in the fetched page, null if none"},
                        "fit": {"type": "string", "description": "One sentence: why it fits the needs, citing the listing"},
                        "check": {"type": "string", "description": "One sentence: the biggest thing still unverified"},
                        "still_listed": {"type": "boolean", "description": "True only if you opened the page and it shows the site as for sale"},
                    },
                },
            },
            "note": {"type": "string", "description": "One sentence on the search, e.g. why fewer than 3 were found"},
        },
    },
}


def search_links(county: str, st: str, acres: int) -> list[dict]:
    """Plain web searches the person can run themselves. Always returned, with or without a key."""
    base = f'"{county}" {st} land for sale {acres}+ acres industrial'
    return [{"label": label, "url": "https://www.google.com/search?q=" + quote_plus(f"{base} site:{site}")}
            for label, site in (("LoopNet", "loopnet.com"), ("Crexi", "crexi.com"), ("LandWatch", "landwatch.com"))]


def needs_for(r: dict, min_mw: float, acres_per_mw: float, min_viable: float) -> dict:
    """What a site has to offer, from the county's analysis and the person's inputs."""
    cap = r.get("supportable_mw") or 0
    mw = min(max(min_mw or 0, min_viable), cap) if cap else max(min_mw or 0, min_viable)
    acres = max(10, round(mw * acres_per_mw))
    return {"mw": round(mw), "acres": acres, "kv": int(r["max_kv"]) if r.get("max_kv") else None,
            "binding": r.get("binding"), "cooling": r.get("cooling_label")}


def _prompt(county: str, state: str, st: str, need: dict) -> str:
    line = (f"within about 5 miles of a {need['kv']} kV transmission line or substation" if need["kv"]
            else "as close as possible to a 230 kV or larger transmission line or substation")
    return f"""Find up to 3 properties for sale right now in {county}, {state} ({st}) where a {need['mw']} MW data center campus could be built.

Needs, in order:
1. Currently listed for sale (not sold, not under contract, not lease-only).
2. At least {need['acres']} acres of land, or an industrial building on at least that much land. If none that large exist, the largest industrial or developable parcels you can find, and say so.
3. Zoned industrial, or agricultural or vacant land that could be rezoned.
4. {line[0].upper() + line[1:]}.
5. Access to municipal water or a large well permit is a plus. This county's tightest limit is {need['binding']}.

Search commercial and land listing sites (for example LoopNet, Crexi, LandWatch, Land.com, CommercialCafe, broker sites) and county economic development site lists. Open each candidate listing page with web fetch to confirm it is still for sale and to read its acreage, building square feet, price, zoning, utilities and main photo. Use only URLs that appeared in your search results or that you fetched; never build or guess a URL. Leave a field null, or a list empty, when the listing doesn't state it. Prefer fewer, real listings over 3 weak ones.

When done, call submit_sites once."""


def _urls(blocks) -> tuple[set[str], set[str], list[str]]:
    """URLs that search results returned, URLs that were fetched, and the fetched pages' text."""
    found, fetched, texts = set(), set(), []
    for b in blocks:
        t = getattr(b, "type", None)
        if t == "web_search_tool_result" and isinstance(getattr(b, "content", None), list):
            found |= {getattr(x, "url", "") for x in b.content}
        elif t == "web_fetch_tool_result":
            c = getattr(b, "content", None)
            u = getattr(c, "url", None)
            if u and getattr(c, "type", "") == "web_fetch_result":
                fetched.add(u)
                data = getattr(getattr(getattr(c, "content", None), "source", None), "data", None)
                if isinstance(data, str):
                    texts.append(data)
    return found - {""}, fetched, texts


def _norm(u: str) -> str:
    p = urlsplit(u.strip())
    return (p.netloc.lower().removeprefix("www.") + p.path.rstrip("/")).lower()


def _base(host: str) -> str:
    return ".".join(host.lower().split(".")[-2:])


def _photo(img, page_url: str, texts: list[str]):
    """Keep a photo URL only if it is https and either appears in a fetched page or is served by the listing site."""
    if not isinstance(img, str) or not img.startswith("https://"):
        return None
    if any(img in t for t in texts) or _base(urlsplit(img).netloc) == _base(urlsplit(page_url).netloc):
        return img
    return None


_snap = None


def snapshot(geoid: str) -> dict | None:
    """The dated listings snapshot for a county, if we have one."""
    global _snap
    if _snap is None:
        try:
            _snap = json.loads(SNAPSHOT.read_text())
        except (OSError, ValueError):
            _snap = {}
    c = (_snap.get("counties") or {}).get(geoid)
    return c and {"sites": c["sites"], "note": c.get("note", ""), "checked": _snap.get("checked")}


def _fallback(geoid: str, reason: str, need: dict, links: list[dict], status: str = "unavailable") -> dict:
    """When live search is off or fails: the dated snapshot if this county has one, else the reason and links."""
    snap = snapshot(geoid)
    if snap:
        return {"status": "snapshot", "reason": reason, "need": need, "links": links} | snap
    return {"status": status, "reason": reason, "need": need, "links": links}


def find_sites(geoid: str, county: str, state: str, st: str, need: dict) -> dict:
    links = search_links(county, st, need["acres"])
    key = (geoid, need["acres"], need["kv"])
    with _lock:
        hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL_S:
        return hit[1] | {"cached": True}

    try:
        import anthropic
    except ImportError:
        return _fallback(geoid, "The anthropic package isn't installed.", need, links)
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_PROFILE")):
        return _fallback(geoid, "No Anthropic API key is set on the server.", need, links)

    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": _prompt(county, state, st, need)}]
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 6},
             {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 6},
             SUBMIT_TOOL]
    found, fetched, texts, picks = set(), set(), [], None
    try:
        for _ in range(MAX_TURNS):
            resp = client.beta.messages.create(
                model=MODEL, max_tokens=16000, tools=tools, messages=messages,
                output_config={"effort": "medium"},
                betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            )
            f1, f2, t = _urls(resp.content)
            found |= f1
            fetched |= f2
            texts += t
            if resp.stop_reason == "refusal":
                return _fallback(geoid, "The search was declined.", need, links, "error")
            call = next((b for b in resp.content if b.type == "tool_use" and b.name == "submit_sites"), None)
            if call:
                picks = call.input if isinstance(call.input, dict) else json.loads(call.input)
                break
            messages.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason == "pause_turn":
                continue
            messages.append({"role": "user", "content": "Call submit_sites now with what you found."})
    except anthropic.APIConnectionError:
        return _fallback(geoid, "Couldn't reach the search service.", need, links, "error")
    except anthropic.RateLimitError:
        return _fallback(geoid, "Search is busy. Try again in a minute.", need, links, "error")
    except anthropic.APIStatusError as e:
        return _fallback(geoid, f"Search failed ({e.status_code}).", need, links, "error")

    if picks is None:
        return _fallback(geoid, "The search ended without results.", need, links, "error")
    seen = {_norm(u) for u in found | fetched}
    opened = {_norm(u) for u in fetched}
    sites = []
    for s in picks.get("sites", [])[:3]:
        n = _norm(s.get("url", ""))
        if not n or n not in seen:            # a URL no search returned is dropped, never shown
            continue
        listed = bool(s.get("still_listed")) and n in opened
        sites.append(s | {"source": urlsplit(s["url"]).netloc.removeprefix("www."),
                          "opened": n in opened, "still_listed": listed, "status": "for sale" if listed else "unclear",
                          "facilities": list(s.get("facilities") or [])[:5], "highlights": list(s.get("highlights") or [])[:3],
                          "image_url": _photo(s.get("image_url"), s["url"], texts)})
    out = {"status": "ok", "sites": sites, "note": picks.get("note", ""), "need": need, "links": links,
           "searched_at": datetime.now(timezone.utc).isoformat(timespec="minutes")}
    with _lock:
        _cache[key] = (time.time(), out)
    return out
