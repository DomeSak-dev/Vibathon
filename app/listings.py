"""Live sites for sale: three parcels or buildings in a county that fit the campus, found by web search.

Claude searches the web with Anthropic's server-side web search and web fetch tools,
opens the listing pages to check they are still for sale, and returns its picks through a strict tool.
We do not scrape listing sites (LoopNet, Crexi and LandWatch bar automated access); every URL we return
must come from a search result or a page Claude fetched, so a made-up link can never reach the screen.

Needs ANTHROPIC_API_KEY (or another credential the Anthropic SDK finds) and `pip install anthropic`.
Without one, the endpoint answers status "unavailable" and the app shows search links instead.
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlsplit

MODEL = "claude-opus-5-5"
CACHE_TTL_S = 6 * 3600          # listings move; re-search a county after 6 hours
MAX_TURNS = 6
_cache: dict[tuple, tuple[float, dict]] = {}
_lock = threading.Lock()

SUBMIT_TOOL = {
    "name": "submit_sites",
    "description": "Return your final picks: up to 3 sites for sale right now. Call this once, at the end.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["sites", "note"],
        "properties": {
            "sites": {
                "type": "array",
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["name", "url", "kind", "acres", "price_usd", "location", "fit", "check", "still_listed"],
                    "properties": {
                        "name": {"type": "string", "description": "Listing title, short"},
                        "url": {"type": "string", "description": "The listing page URL, exactly as found"},
                        "kind": {"type": "string", "enum": ["land", "building"]},
                        "acres": {"type": ["number", "null"], "description": "Lot size in acres, null if not stated"},
                        "price_usd": {"type": ["number", "null"], "description": "Asking price in US dollars, null if not stated"},
                        "location": {"type": "string", "description": "City or road, as the listing gives it"},
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

Search commercial and land listing sites (for example LoopNet, Crexi, LandWatch, Land.com, broker sites) and county economic development site lists. Open each candidate listing page with web fetch to confirm it is still for sale and to read its acreage and price. Use only URLs that appeared in your search results or that you fetched; never build or guess a URL. Leave acres or price null when the listing doesn't state them. Prefer fewer, real listings over 3 weak ones.

When done, call submit_sites once."""


def _urls(blocks) -> tuple[set[str], set[str]]:
    """URLs that search results returned, and URLs that were fetched."""
    found, fetched = set(), set()
    for b in blocks:
        t = getattr(b, "type", None)
        if t == "web_search_tool_result" and isinstance(getattr(b, "content", None), list):
            found |= {getattr(x, "url", "") for x in b.content}
        elif t == "web_fetch_tool_result":
            c = getattr(b, "content", None)
            u = getattr(c, "url", None)
            if u and getattr(c, "type", "") == "web_fetch_result":
                fetched.add(u)
    return found - {""}, fetched


def _norm(u: str) -> str:
    p = urlsplit(u.strip())
    return (p.netloc.lower().removeprefix("www.") + p.path.rstrip("/")).lower()


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
        return {"status": "unavailable", "reason": "The anthropic package isn't installed.", "need": need, "links": links}
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_PROFILE")):
        return {"status": "unavailable", "reason": "No Anthropic API key is set on the server.", "need": need, "links": links}

    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": _prompt(county, state, st, need)}]
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 6},
             {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 6},
             SUBMIT_TOOL]
    found, fetched, picks = set(), set(), None
    try:
        for _ in range(MAX_TURNS):
            resp = client.beta.messages.create(
                model=MODEL, max_tokens=16000, tools=tools, messages=messages,
                output_config={"effort": "medium"},
                betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            )
            f1, f2 = _urls(resp.content)
            found |= f1
            fetched |= f2
            if resp.stop_reason == "refusal":
                return {"status": "error", "reason": "The search was declined.", "need": need, "links": links}
            call = next((b for b in resp.content if b.type == "tool_use" and b.name == "submit_sites"), None)
            if call:
                picks = call.input if isinstance(call.input, dict) else json.loads(call.input)
                break
            messages.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason == "pause_turn":
                continue
            messages.append({"role": "user", "content": "Call submit_sites now with what you found."})
    except anthropic.APIConnectionError:
        return {"status": "error", "reason": "Couldn't reach the search service.", "need": need, "links": links}
    except anthropic.RateLimitError:
        return {"status": "error", "reason": "Search is busy. Try again in a minute.", "need": need, "links": links}
    except anthropic.APIStatusError as e:
        return {"status": "error", "reason": f"Search failed ({e.status_code}).", "need": need, "links": links}

    if picks is None:
        return {"status": "error", "reason": "The search ended without results.", "need": need, "links": links}
    seen = {_norm(u) for u in found | fetched}
    opened = {_norm(u) for u in fetched}
    sites = []
    for s in picks.get("sites", [])[:3]:
        n = _norm(s.get("url", ""))
        if not n or n not in seen:            # a URL no search returned is dropped, never shown
            continue
        sites.append(s | {"source": urlsplit(s["url"]).netloc.removeprefix("www."),
                          "opened": n in opened, "still_listed": bool(s.get("still_listed")) and n in opened})
    out = {"status": "ok", "sites": sites, "note": picks.get("note", ""), "need": need, "links": links,
           "searched_at": datetime.now(timezone.utc).isoformat(timespec="minutes")}
    with _lock:
        _cache[key] = (time.time(), out)
    return out
