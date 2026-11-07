# Where Tokens will Take You

**Theme 3 of the Vibathon: time to power.** AI runs in data centers, and the power grid now decides where they can be built. This app answers two questions:

1. **Where can a data center go?** Every US county is scored on power, water and land. For each county you see how big a campus fits, how long power takes, what it costs, what it emits, and sites to buy or lease.
2. **What does your company's AI emit?** For most companies the answer is to stay on a cloud AI API, not to build. So the second view turns a company's AI usage into the emissions it reports under California's SB 253.

Built by Hovik, Joy, Dome and MJ. The team is pinned on the globe at home: Armenia, China, Thailand, and Trinidad and Tobago.

## Who it's for

- **Site-selection teams** at AI and data center companies screening where to look first.
- **Towns and investors** weighing what a campus means for the local grid, water and emissions.
- **Companies that buy AI** and need a defensible emissions estimate for their climate report.

## How the scope changed

We started with the three factors (power, water and land) and a build-vs-buy calculator for companies. That calculator showed that building, colocating or renting GPUs pays off only at thousands of times a typical company's AI volume. So the company view became a **reporting tool** instead: it estimates the emissions of AI bought through an API, and how they change with the data center region that serves it. The environmental work became a map layer (Impact) and a carbon card for every county.

## Try it in two minutes

1. **Globe:** pick *United States* and press **Explore**.
2. **Explore:**
   - Switch the map between **Overall · Power · Water · Land · Cost · Impact**. The sidebar lists the best opportunities: counties a large campus can use (100 MW+, a usable 230 kV+ line).
   - Click a state, then a county. The panel shows:
     - room for X MW, and what limits it;
     - months to power and tokens a day;
     - cost and carbon per year;
     - what to check next;
     - sites to **Buy** or **Lease**.
   - **Campus size** and **Adjust** (priorities, cooling, grid or PPA power, grid lines) change everything live. The link in the address bar saves your view.
3. **Your company:**
   - Pick a sample (e.g. *Coding team: 500 developers*) or upload a usage CSV from Claude Console, OpenAI or Google.
   - Choose where your AI runs: the US average, a cloud region, or click any county on the map.
   - Press **Calculate**. You get CO₂e a year, the same usage in other regions, the SB 253 reporting line, a worksheet to download, and a disclosure note drafted by Claude.

## Run locally

On Windows, double-click `run.bat`. Or:

```bash
pip install fastapi "uvicorn[standard]" pandas numpy python-multipart anthropic
```

```bash
python -m uvicorn app.main:app --port 8001
```

Open http://localhost:8001. The processed data is in the repo, so the demo runs without internet.

**Optional Anthropic API key** (`ANTHROPIC_API_KEY`, or put it in a `.env` file next to `run.bat`). With a key:
- **Sites to buy or lease, for any county.** Claude searches listing sites with Anthropic's web search and opens each listing to read its size, price or lease rate, utilities and photo. Only links from a real search result or an opened page are shown, and results are cached for 6 hours.
- **The disclosure note** is written by Claude from the computed numbers.

Without a key:
- **Buy** shows listings read on Nov 7, 2026 for 11 top counties.
- **Lease** shows search links.
- **The note** uses a template.

## What's in the numbers

| Model | In short |
| --- | --- |
| Power | Lines that run at least 5 km inside the county (230 kV 250 MW · 345 kV 500 MW · 500 kV+ 1,000 MW; each extra line adds half the last), adjusted for planned and retiring plants and the grid operator's spare capacity at peak |
| Water | Up to 10% of the county's public water supply ÷ water per MW (cooling design × local heat) |
| Land | Open land estimated from population density; 0.5% of it usable at 1 acre per MW |
| Capacity | The smallest of power, water and land: that's the limit |
| Time to power | By the strongest usable line: 2–3 years on 500 kV, 5–8 years if a new line is needed |
| Cost | Energy (state industrial rate, or a solar or wind PPA) + capacity-market charge + water and sewer + land |
| Carbon and Impact | Grid CO₂ from each operator's 12-month fuel mix; Impact = 50% grid CO₂ + 30% water stress + 20% clean power planned nearby |
| Tokens | Campus MW × 70% load ÷ energy per token (per-model factors from the team model sheet) |
| Your company | Output tokens × Wh per 1,000 + calls × Wh per call → kWh → CO₂e at the grid where the AI runs; Scope 3 · Category 1 |

Scores are percentiles against all 3,144 US counties. The overall score is a weighted mix (default power 45 / water 30 / land 25).

**Read this before quoting a number.** These are screening estimates, not an interconnection study or an emissions filing.
- Line loading isn't public.
- The water data is from 2015.
- Providers don't say which data center serves a request.
- Long-context AI work is undercounted, because input tokens aren't charged.

Every assumption, with the reason and a ⚑ where the team still has to decide, is in [ASSUMPTIONS.md](ASSUMPTIONS.md).

## Docs

| File | What |
| --- | --- |
| [ASSUMPTIONS.md](ASSUMPTIONS.md) | Every assumption and why |
| [sources.md](sources.md) | Every data source, what it feeds, and a link |
| [suggestion.md](suggestion.md) | Pitch framing, risks to say out loud, next steps |

## Rebuild the data

```bash
pip install -r requirements.txt
```

```bash
python scripts/fetch_data.py
```

```bash
python scripts/build_sites.py
```

```bash
python scripts/build_catalog.py
```

`fetch_data.py` downloads the power lines, plants, hourly grid data, water use, population and county shapes into `data/raw/` (not in git). Three files are added by hand:
- the NOAA climate normals (precipitation and cooling degree days);
- the EIA price table page;
- the team model sheet, as `data/raw/sheet/sheet.xlsx`.

See [sources.md](sources.md) for links.

## Layout

| Path | What |
| --- | --- |
| `app/static/index.html` | The whole front end (D3, no build step) |
| `app/main.py` | FastAPI: `/api/config`, `/api/map`, `/api/county/{fips}`, `/api/top`, `/api/sites/{fips}`, `/api/company/*`, `/api/catalog` |
| `app/siting.py` | County model: power, water, land, capacity, cost, carbon, Impact, tokens |
| `app/company.py` | Your company: usage → kWh → CO₂e where the AI runs, region comparison, disclosure note |
| `app/listings.py` | Sites to buy or lease: live web search, saved for-sale listings as fallback |
| `app/usage.py`, `app/catalog.py` | Usage CSV parser (from the AI Energy Bill project); per-model prices and energy |
| `scripts/build_sites.py` | Joins all sources to 3,144 counties → `data/counties.json` and the map layers |
| `scripts/build_catalog.py` | Builds `data/model_catalog.csv` and the size-class energy factors from the team model sheet |
| `data/siting_factors.json` | Every number the models use; change values here, not in code |
| `data/energy_factors.json` | Energy per 1,000 output tokens and per call, by size class |
| `app/static/data/listings.json` | Saved for-sale listings for 11 counties (Nov 7, 2026) |
