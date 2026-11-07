# Where Tokens will Take You

Data center siting for Theme 3 of the Vibathon (time to power). Pick a region on a spinning globe (the team is pinned to home: Hovik in Armenia, Joy in China, Dome in Thailand, MJ in Trinidad and Tobago) and the app answers two questions.

**Explore: where can a data center go?** Every US county is scored on power, water and land, from country to state to county.
- **Map layers:** Overall, Power, Water, Land, Cost and Impact (environmental footprint, red to green). The best opportunities (100 MW+, a usable 230 kV+ line) are pinned and listed.
- **Click a county** to see:
  - how big a campus fits and what limits it;
  - months to power and tokens a day;
  - yearly cost and carbon;
  - what to check next;
  - **sites to buy or lease** that fit the campus.

**Your company: what does your AI emit, for SB 253?** Most companies are best served staying on a cloud AI API, so this reports what that use emits. Upload an AI usage CSV (or pick a sample) and choose where your AI runs: the US average, a common cloud region, or any county on the map. The app:
- shows the yearly CO₂e (in kg or tonnes) and how it changes by region;
- tags it as Scope 3 · Category 1 for California SB 253;
- gives a downloadable worksheet;
- has Claude draft the methodology note for your report.

Ideas and next steps: [suggestion.md](suggestion.md). Every assumption: [ASSUMPTIONS.md](ASSUMPTIONS.md).

## Run locally

On Windows, double-click `run.bat`. Or:

```bash
pip install fastapi "uvicorn[standard]" pandas numpy python-multipart anthropic
```

```bash
python -m uvicorn app.main:app --port 8001
```

Open http://localhost:8001. The processed data is in the repo, so the demo needs no internet.

**With an Anthropic API key** (`ANTHROPIC_API_KEY`, or a `.env` file next to `run.bat`), two features go live:
- **Sites to buy or lease, for any county.** Claude searches listing sites with Anthropic's web search, opens each listing to read its size, price or lease rate, utilities and photo, and checks it's still available. Only links from a search result or an opened page are shown, and results are cached for 6 hours.
- **The disclosure note** for your SB 253 report.

Without a key:
- Buy shows listings read from the listing pages on Nov 7, 2026 for 11 top counties (`app/static/data/listings.json`), with that date.
- Lease shows search links.
- The disclosure note uses a template.

Public land-for-lease listings are mostly small parcels, so lease results often say nothing listed is as big as the campus needs.

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

`build_catalog.py` reads the team model sheet, downloaded to `data/raw/sheet/sheet.xlsx`. NOAA climate files and the EIA price page were downloaded once into `data/raw/` (see `data/siting_factors.json` → `sources`).

## Layout

| Path | What |
| --- | --- |
| `scripts/fetch_data.py` | Downloads HIFLD lines ≥230 kV, EIA-860M, EIA-930 hourly grid data, USGS water, Census population and shapes |
| `scripts/build_sites.py` | Joins everything to 3,144 counties → `data/counties.json`, map layers → `app/static/data/` |
| `scripts/build_catalog.py` | Builds the model catalog and size-class energy factors from the team model sheet |
| `app/siting.py` | The county model: power / water / land MW, scores, cost, carbon, tokens |
| `app/company.py` | Your company: usage → kWh → CO₂e where the AI runs, region comparison, SB 253 disclosure note |
| `app/listings.py` | Sites to buy or lease: live web search, with the saved for-sale listings as fallback |
| `app/usage.py`, `app/catalog.py` | Usage CSV parser (from the AI Energy Bill project); per-model prices and energy (`data/model_catalog.csv`) |
| `app/main.py` | FastAPI: `/api/config`, `/api/map`, `/api/county/{fips}`, `/api/top`, `/api/sites/{fips}`, `/api/company/*`, `/api/catalog` |
| `app/static/index.html` | The whole front end (D3, no build step) |
| `data/siting_factors.json` | Every number the model uses; edit it here, not in code |
| `data/energy_factors.json` | Wh per 1,000 output tokens and per call, by size class (team model sheet) |

## Model in one screen

```
Power MW   = lines running ≥ 5 km inside the county (230 kV 250 · 345 kV 500 · 500 kV+ 1,000 MW;
             strongest in full, each extra line at half the last)
             × (1 + 0.25 per GW planned generation, max +50% − 0.15 per GW retiring)
             × grid operator's spare capacity at peak (EIA-930 demand vs EIA-860M capacity: ×0.5–1.1)
Water MW   = 10% of public-supply water ÷ water per MW (cooling design × local heat)
Land MW    = open acres (from density) × 0.5% ÷ 1 acre per MW
Campus MW  = min(Power, Water, Land)   → the smallest is the "limiting factor"
Cost/year  = MWh × state industrial rate (or PPA + delivery)
             + capacity-market price × MW (per MW-day: PJM $333, MISO $116–126, ISO-NE $118, NYISO $329 est.)
             + water and sewer ($6 per 1,000 gal default × 0.75–1.5 by water stress, sewer on 20%)
             + 8% a year × land (1 acre/MW × state farmland $/acre × 1–25 near big lines)
Carbon     = MWh × the grid operator's 12-month CO₂ rate (EIA-930 fuel mix × EIA factors)
Impact     = 50% low grid CO₂ + 30% low water stress + 20% clean power planned nearby
Tokens/day = Campus MW × 70% load × 24 h ÷ Wh per 1,000 output tokens × 1,000
Scores     = percentiles vs. all US counties; overall = weighted mix (default 45/30/25)
```
