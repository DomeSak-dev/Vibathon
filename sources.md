# Data sources

Every outside source the project uses, grouped by what it feeds. The numbers taken from them live in `data/siting_factors.json` and `data/energy_factors.json`. How each one is used, and every assumption built on it, is in [ASSUMPTIONS.md](ASSUMPTIONS.md).

Raw downloads go to `data/raw/` (not in git); rebuild them with `scripts/fetch_data.py`.

## Power and the grid

| Source | What we use | Link |
|---|---|---|
| HIFLD Electric Power Transmission Lines | Every line ≥ 230 kV: voltage, route, status (10,692 lines) | [ArcGIS FeatureServer](https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/US_Electric_Power_Transmission_Lines/FeatureServer/0) |
| EIA-860M, September 2026 | Every generator: operating, planned (to 2029), retiring (to 2030); capacity, fuel, location, grid operator | [EIA-860M](https://www.eia.gov/electricity/data/eia860m/) |
| EIA-930 Hourly Electric Grid Monitor, Jul 2025 – Jun 2026 | Each grid operator's hourly demand (peak, spare capacity) and generation by fuel (carbon, clean share) | [Six-month files](https://www.eia.gov/electricity/gridmonitor/) |
| EIA Electric Power Monthly, Table 5.6.B, Jan–Aug 2026 | Industrial electricity price by state | [Table 5.6.B](https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=epmt_5_6_b) |
| PJM 2027/28 Base Residual Auction | Capacity price, $333.44/MW-day | [PJM Inside Lines](https://insidelines.pjm.com/pjm-auction-procures-134479-mw-of-generation-resources/) |
| MISO 2026/27 Planning Resource Auction | Capacity price, $126 / $116 (South) per MW-day | [mgrid](https://mgrid.org/2026/04/28/miso-2026-27-capacity-auction-clears-at-126-mw-day-down-42/) |
| ISO-NE Forward Capacity Auction 18 | Capacity price, $3.58/kW-month | [ISO Newswire](https://isonewswire.com/?p=6422) |
| NYISO summer 2026 spot capacity | Capacity price estimate, ~$10/kW-month | [Modo Energy](https://modoenergy.com/research/en/nyiso-capacity-prices-record-summer-2026) |
| LevelTen PPA Price Index, Q2 2026 | Solar and wind PPA prices (approximate) | [LevelTen](https://www.leveltenenergy.com/post/levelten-north-american-ppa-price-index-q2-2026) |

## Carbon and power-plant water

| Source | What we use | Link |
|---|---|---|
| EIA FAQ: CO₂ per kWh by fuel | Coal 1.04, gas 0.44, oil 1.08 kg CO₂/kWh, applied to the EIA-930 fuel mix | [EIA FAQ](https://www.eia.gov/tools/faqs/faq.php?id=74&t=11) |
| NREL, Macknick et al. (operational water use by power plants) | Water consumed per kWh: coal, gas, nuclear | [NREL/TP-6A20-50900](https://www.nrel.gov/docs/fy11osti/50900.pdf) |
| EPA eGRID2023 | Cross-check of our grid carbon factors (ERCOT, CAISO) | [eGRID summary data](https://www.epa.gov/egrid/summary-data) |
| EPA Greenhouse Gas Equivalencies | Trees, homes and cars equivalents | [EPA calculator](https://www.epa.gov/energy/greenhouse-gas-equivalencies-calculator-calculations-and-references) |

## Water and climate

| Source | What we use | Link |
|---|---|---|
| USGS Estimated Use of Water in the US, county data 2015 (v2.0) | Public-supply, fresh and irrigation withdrawals by county | [ScienceBase](https://www.sciencebase.gov/catalog/item/5af3311be4b0da30c1b245d8) |
| NOAA nClimDiv county normals, 1991–2020 | Annual precipitation and cooling degree days | [NCEI climdiv](https://www.ncei.noaa.gov/monitoring-content/data/us/climdiv/monthly/current/) |
| City water tariffs (2025) | Verified commercial water rates: Carson City NV, Orange City FL, Webster FL, Lucas TX | [Carson City](https://www.carsoncity.gov/home/showpublisheddocument/91222/638851586106100000) · [Orange City](https://mta-sts.orangecityfl.gov/city/government/utilities-water-rates/water-rates-commercial.pdf) · [Webster](https://websterfl.com/wp-content/uploads/2025/11/Water-and-Sewer-Rates-Worksheet-2025-1.pdf) · [Lucas](https://www.lucastexas.us/226/Water-Waste-Water-Utility-Rates) |

## Land and people

| Source | What we use | Link |
|---|---|---|
| US Census Bureau cartographic boundaries 2023 (1:20M) | County shapes and land area | [cb_2023_us_county_20m](https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_20m.zip) |
| US Census Bureau population estimates, July 2024 | County population (density, open land) | [co-est2024-alldata](https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/counties/totals/co-est2024-alldata.csv) |
| USDA NASS Land Values 2026 Summary | Farm real estate value per acre by state | [USDA NASS](https://esmis.nal.usda.gov/sites/default/release-files/795999/land0726.txt) |
| Data Center Knowledge / Altus Group | Price premium for land near big lines (~2.4×) | [Data Center Knowledge](https://datacenterknowledge.com/data-center-construction/ai-data-center-land-buying-hits-6b-as-power-premiums-rise) |
| Listing sites (LoopNet, Crexi, LandWatch, CityFeet) | Sites to buy (saved Nov 7, 2026 for 11 counties) or lease (live search only) | `app/static/data/listings.json`, `app/listings.py` |

## AI energy, prices and usage

| Source | What we use | Link |
|---|---|---|
| Team model sheet | Per-model API prices (38 models), EcoLogits-based energy per 1,000 output tokens and per call, provider PUE, developer usage scenarios | [Google Sheet](https://docs.google.com/spreadsheets/d/1m6kRk2w5xF75yZ-zI-F9LhEcI-Ypx3Gs) |
| EcoLogits methodology | The energy method behind the sheet's factors | [EcoLogits](https://ecologits.ai/latest/methodology/llm_inference/) |
| iternal.ai token usage guide | Token ranges per request in the developer scenarios | [iternal.ai](https://iternal.ai/token-usage-guide) |
| Claude API list prices (Anthropic, Oct 2026) | Prices for models not in the sheet (Haiku 5.5, Sonnet 5.5, Opus 5.5) | [Anthropic pricing](https://www.anthropic.com/pricing) |
| BurstGPT (via the AI Energy Bill project) | The "online store" sample usage file | `data/sample_usage.csv` |
| Reference figures (not used in calculations) | Google 0.24 Wh per Gemini prompt; OpenAI ~0.34 Wh per ChatGPT query; Jegham et al. 2025 | [Google](https://arxiv.org/abs/2508.15734) · [OpenAI](https://blog.samaltman.com/the-gentle-singularity) · [Jegham et al.](https://arxiv.org/abs/2505.09598) |

## Reporting (California SB 253)

| Source | What we use | Link |
|---|---|---|
| Greenberg Traurig, Oct 2026 | First Scope 1 and 2 deadline, Nov 10, 2026 | [GT Law](https://www.gtlaw.com/ar/insights/2026/10/california-sb-253-carb-sets-nov-10-2026-deadline-for-scope-1-and-scope-2-emissions-reports) |
| Fenwick, Jul 2026 | Scope 3 from 2027; the first five categories include Category 1 | [Fenwick](https://whatstrending.fenwick.com/post/carb-previews-2027-sb-253-reporting-rules-and-confirms-delayed-2026-deadline) |
| Vinson & Elkins via JD Supra, Apr 2026 | CARB's proposed Scope 3 options and methods | [JD Supra](https://www.jdsupra.com/legalnews/carb-previews-proposed-regulations-for-6332261/) |
| Cloud region locations (public reports) | Approximate county of six common cloud regions (Northern Virginia, Ohio, Iowa, Texas, Oregon, Central Washington) | `data/siting_factors.json` → `company.reporting.cloud_regions` |

## Maps and code libraries

| Source | What we use | Link |
|---|---|---|
| us-atlas | US state borders for the map | [us-atlas](https://github.com/topojson/us-atlas) |
| world-atlas (Natural Earth) | The globe | [world-atlas](https://github.com/topojson/world-atlas) |
| D3 and topojson-client | Map and chart drawing | [d3js.org](https://d3js.org) |
