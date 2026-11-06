# Time to Power

Data center siting for Theme 3 of the Vibathon. Pick a region on a spinning globe, then drill down from country to state to county. The country view colors each state by its best counties; clicking a state shows its counties scored on power (transmission lines), water and land. Click a county to see:
- the largest campus it could likely host, and what limits it;
- months to power;
- yearly cost: energy, capacity, water and sewer, and land (grid rate or a solar or wind PPA);
- how many AI tokens a day the campus could serve.

Ideas and next steps: [suggestion.md](suggestion.md). Every assumption: [ASSUMPTIONS.md](ASSUMPTIONS.md).

## Run locally

On Windows, double-click `run.bat`. Or:

```bash
pip install fastapi "uvicorn[standard]" pandas numpy
```

```bash
python -m uvicorn app.main:app --port 8001
```

Open http://localhost:8001. The processed data is already in the repo, so the demo needs no internet. d3 and the map files are in `app/static/vendor/`.

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

NOAA climate files and the EIA price page were downloaded once into `data/raw/` (see `data/siting_factors.json` → `sources`).

## Layout

| Path | What |
| --- | --- |
| `scripts/fetch_data.py` | Downloads HIFLD lines ≥230 kV, EIA-860M, USGS water, Census population and shapes |
| `scripts/build_sites.py` | Joins everything to 3,144 counties → `data/counties.json`, map layers → `app/static/data/` |
| `app/siting.py` | The model: power / water / land MW, scores, binding factor, costs, tokens |
| `app/main.py` | FastAPI: `/api/config`, `/api/map`, `/api/county/{fips}`, `/api/top` |
| `app/static/index.html` | The whole front end (D3, no build step) |
| `data/siting_factors.json` | Every number the model uses; edit it here, not in code |
| `data/energy_factors.json` | Wh per 1,000 tokens by model tier (from the AI Energy Bill project) |

## Model in one screen

```
Power MW   = MW by highest line voltage in county (230 kV 250 · 345 kV 500 · 500 kV+ 1,000)
             × (1 + 0.25 per GW planned generation, max +50% − 0.15 per GW retiring)
Water MW   = 10% of public-supply water ÷ water per MW (cooling design × local heat)
Land MW    = open acres (from density) × 0.5% ÷ 1 acre per MW
Campus MW  = min(Power, Water, Land)   → the smallest is the "limiting factor"
Tokens/day = Campus MW × 70% load × 24 h ÷ Wh per 1,000 output tokens × 1,000
Scores     = percentiles vs. all US counties; overall = weighted mix (default 45/30/25)
Cost/year  = MWh × state industrial rate (or PPA + delivery)
             + PJM capacity $333/MW-day × MW
             + water and sewer ($6 per 1,000 gal default × 0.75–1.5 by water stress, sewer on 20%)
             + 8% a year × land (1 acre/MW × state farmland $/acre × 1–25 near big lines)
```
