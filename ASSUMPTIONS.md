# Time to Power: assumptions

⚑ marks an assumption the team hasn't agreed yet. All numbers are in `data/siting_factors.json`.

## Scope
| # | Assumption | Reason |
|---|---|---|
| S1 | **Unit of analysis is the county** (3,144, all 50 states + DC). | Water, population and generator data are reported by county, so finer cells would be false precision. See suggestion.md §3 for a site-level layer. |
| S2 | **Screening, not engineering.** Results say where to look first, not where to sign. | We can't see how much line capacity is already contracted. |
| S3 ⚑ | **Demo region is the US.** The globe offers North America; Canada and Mexico aren't scored. | US data is open and consistent. |

## Power
| # | Assumption | Reason |
|---|---|---|
| P1 ⚑ | **Only lines that run at least 5 km inside the county count.** Each counts by voltage: 230 kV 250 MW, 345 kV 500 MW, 500 kV+ 1,000 MW (HVDC as 500 kV). The strongest line counts in full, and each further line adds half as much as the one before, so the total tops out near twice the strongest line. A county with no line ≥ 230 kV gets 50 MW. | A line that only clips a corner can't host a substation. More lines mean more capacity and a backup path, but each new connection still has to go through one substation, so returns diminish. A single-circuit 230 kV line carries ~200–400 MW, 345 kV ~400–900 MW, and 500 kV 1,000+ MW. |
| P2 ⚑ | **Planned generation within the county by 2029 adds 25% per GW (max +50%). Retirements by 2030 remove 15% per GW.** | New local supply eases connection, and retirements tighten it. Source: EIA-860M Sep 2026. |
| P2b ⚑ | **The grid operator's spare capacity scales power MW.** Spare = firm capacity ÷ peak demand − 1. Peak demand is the 99.9th-percentile hour from EIA-930 for Jul 2025–Jun 2026. Firm capacity is EIA-860M summer capacity, with solar counted at 30% and wind at 15%. The multiplier is ×0.5 at −20%, ×0.65 at 0%, ×0.9 at 15%, ×1.0 at 30% and ×1.1 at 50%+. Operators with a peak under 2 GW are treated as neutral. The margin is also 20% of the power score. | **How loaded each individual line is isn't public** (FERC classes it as critical energy infrastructure information). Operator-wide spare capacity is the best public proxy: an operator with little spare can't add a large load quickly without new plants. Small operators lean on their neighbours, so their own ratio misleads. |
| P3 ⚑ | **Months to power: 500 kV 24–36, 345 kV 24–42, 230 kV 36–48, no ≥230 kV line 60–96.** | Ranges are rules of thumb: a new substation on an existing line takes 2–4 years, and a new line takes 5–8. The LBNL queue data would replace this (suggestion.md). |
| P4 | **Electricity price = state industrial average, EIA Jan–Aug 2026.** | Large campuses usually buy on industrial or large-power tariffs. |
| P5 | **Lines in HIFLD marked "not in service" are excluded.** | Only existing lines count. |

## Water
| # | Assumption | Reason |
|---|---|---|
| W1 ⚑ | **A single campus may take up to 10% of the county's public-supply withdrawals.** | Utilities rarely commit more than a small share of system capacity to one customer. |
| W2 | **On-site water per kWh: evaporative 1.8 L, hybrid 0.5 L (default), closed-loop / air 0.05 L.** | Evaporative is near the LBNL industry average. Hybrid sits between the hyperscaler range (AWS 0.12 to Google 1.15). Closed-loop uses almost no water. |
| W3 | **Water per kWh scales with heat: × (0.7 + 0.3 × CDD/1,500), clipped to 0.6–1.6.** | Hot climates evaporate more. Source: NOAA 1991–2020 cooling degree day normals. |
| W4 ⚑ | **Water stress index = 40% withdrawals ÷ rainfall volume + 40% aridity + 20% irrigation share** (all percentiles). | It's a proxy built from USGS + NOAA. WRI Aqueduct would be better. |
| W5 ⚑ | **Commercial water price: $6.00 / 1,000 gal default; four counties use a verified local tariff.** | No national commercial-rate dataset exists. |
| W6 | **USGS water use is from 2015.** Connecticut (new planning regions) and 2 Alaska areas are estimated from per-capita use and flagged. | It's the latest national county-level compilation. |

## Land
| # | Assumption | Reason |
|---|---|---|
| L1 ⚑ | **Open land share falls with population density (log scale): fully open below 50 people/sq mi, none above 3,000.** | It's a stand-in for land cover until NLCD/CDL is added. |
| L2 ⚑ | **0.5% of open acres is realistically available as large parcels, and a campus needs 1 acre per MW.** | Hyperscale campuses run roughly 0.5–2 acres per MW including the substation and setbacks. |

## Tokens and costs
| # | Assumption | Reason |
|---|---|---|
| T1 | **Average load is 70% of the campus's maximum draw.** | It's a typical utilization for AI campuses. |
| T2 | **Facility energy = output tokens × Wh per 1,000 output tokens + calls × Wh per call. Input tokens are not charged separately.** For size classes: small 0.19, medium 1.89, large 5.00 Wh per 1K (median of the models in each class, with low/high bounds). Per-call energy is 0.002 / 0.013 / 0.095 Wh. A model listed in the team sheet uses its own figures. | This is the team model sheet's method: EcoLogits-based IT energy (H100, 16-bit, batch 64) × provider PUE (OpenAI 1.2, Google 1.09, Anthropic 1.115) for 34 exact models. Classes come from energy itself: under 0.8 Wh is small, 0.8–3.5 is medium, above that is large. The sheet leaves input effects unresolved, so long-context work (coding agents) is probably underestimated. These are modeled proxies, not measurements. |
| T3 | **Tokens are output tokens; all campus energy goes to inference.** | It keeps the headline simple. Training would lower the count. |

## Pricing
Cost per year = energy + capacity + water and sewer + a yearly charge on the land. Missing inputs stay missing: a county with no electricity rate, or no room for a campus, gets no cost, never $0. All numbers are in `data/siting_factors.json` → `pricing`.

| # | Assumption | Reason |
|---|---|---|
| C1 | **Energy = MWh × the state industrial average rate (EIA, Jan–Aug 2026).** | Large campuses buy on industrial or large-load tariffs. A real tariff quote can differ a lot. |
| C2 ⚑ | **PPA option: solar $60/MWh or wind $70/MWh, plus 2.25¢/kWh for delivery (the midpoint of 1.5–3¢).** | From the LevelTen Q2 2026 index, approximate because the full index is paid. A PPA covers energy only, so delivery is added. |
| C3 ⚑ | **Capacity: campus MW × the capacity-market price per MW-day, added on top of the state rate.** PJM $333.44 (2027/28 auction, RTO-wide, at the cap). MISO $126 North/Central and $116 South (2026/27 auction, annualized; South = MISO counties in AR, LA, MS, TX). ISO-NE $117.70 (FCA 18 for 2027/28, $3.58/kW-month, preliminary). NYISO $329, an estimate (summer 2026 spot of about $10/kW-month for Long Island and rest of state). Grids with no capacity market (ERCOT, SPP, the Southeast and West utilities) are assumed to carry it in the state rate. | Sources: [PJM](https://insidelines.pjm.com/pjm-auction-procures-134479-mw-of-generation-resources/), [MISO via mgrid](https://mgrid.org/2026/04/28/miso-2026-27-capacity-auction-clears-at-126-mw-day-down-42/), [ISO-NE](https://isonewswire.com/?p=6422), [NYISO via Modo Energy](https://modoenergy.com/research/en/nyiso-capacity-prices-record-summer-2026). Part of each price is already in the state rate, so this errs high. The NYISO figure is a summer month used for the whole year, so it errs high too. |
| C4 ⚑ | **882 counties have no grid operator on file (no generator there). They take the nearest county in the same state that has one** (`scripts/build_sites.py`; the grid's carbon and spare capacity follow it). | Shown as "est." in the app. |
| C5 ⚑ | **The $6 default water rate is scaled ×0.75 (no stress) to ×1.5 (highest stress). Verified local rates are used as they are.** | Scarce water tends to cost more. A starting guess. |
| C6 ⚑ | **Sewer is charged on 20% of the water volume, at the water rate.** | Cooling towers discharge part of what they take. |
| C7 | **Land price = state farm real estate value per acre (USDA NASS Land Values 2026; US average $4,500). Alaska, Hawaii and DC aren't reported and use the US average, flagged.** | The only current national series. County values from NASS Quick Stats would be better. Source: [USDA NASS](https://esmis.nal.usda.gov/sites/default/release-files/795999/land0726.txt). |
| C8 ⚑ | **Land near big lines costs more: ×1 with no 230 kV+ line, ×10 at 230 kV, ×20 at 345 kV, ×25 at 500 kV.** | Sites near 230–500 kV lines sold for about 2.4× those near 138 kV or lower (Altus Group, 80 deals), and powered land in Northern Virginia sells for $4–6M an acre. This puts rural land near a big line in the six figures per acre. |
| C9 ⚑ | **Land is bought once and carried at 8% of its price a year.** | A common capital charge. It puts a one-time cost on the same yearly basis as the rest. |
| C10 | **Cost per MWh = yearly total ÷ MWh at 70% load. The Cost map colors counties by its percentile (lighter = cheaper).** | Per-MWh cost compares counties of different sizes. |

## Sites for sale or lease
| # | Assumption | Reason |
|---|---|---|
| F1 ⚑ | **A site needs 1 acre per MW for the campus you set (Campus size, at least 100 MW), capped at what the county can host.** It also needs a 230 kV+ line nearby (the county's highest, within about 5 miles), industrial zoning or land that could be rezoned, and it must be for sale, not lease-only. | It's the same land rule as L2, applied to one parcel. |
| F2 | **Live listings come from a web search by Claude, which opens each listing page to read it.** Each pick links to the page it came from. A link that no search returned is dropped. "Status unclear" means the page wasn't opened or didn't show a status. | It reads the same public pages a person would, one county at a time, instead of bulk scraping. |
| F3 | **Results are cached for 6 hours per county and size.** | Listings change daily. The cache keeps repeat clicks fast and cheap. |
| F4 ⚑ | **Saved listings for 11 counties were read from the listing pages on Nov 7, 2026 and are shown with that date.** The counties are the top 10 at 850 MW with default inputs, plus King County. Price, size, zoning, utilities and details are as each page showed them. The "Check" line on each box is ours. Listings marked off market, pending or ground lease were left out. "Status unclear" means the page didn't show a status. | Live search needs an API key. A dated snapshot shows real listings without one, and says how old they are. |
| F5 | **When a listing gives no lot size, the fit is unknown, not zero.** "Room for about X MW" is the lot's acres at 1 acre per MW (F1). The drawing shows the lot and the campus to scale. | Missing data never shows as zero. |
| F6 | **Photos load from the listing site.** The hosted copy can't load outside images, so it shows the to-scale drawing instead. | The photo belongs to the listing; the link takes you to it. |
| F7 ⚑ | **Lease listings come from the same live search, asked for land or buildings offered for lease (ground leases included).** There is no saved lease snapshot, so without an API key the panel shows lease searches on LoopNet, Crexi and CityFeet. | Public land-for-lease listings are mostly small parcels (a few to a few dozen acres) and often show no rate, because large data-center sites are usually leased as built shells or negotiated privately. The app says when nothing listed is as big as the campus needs. |

## Scoring
| # | Assumption | Reason |
|---|---|---|
| R1 | **Every sub-score is a 0–100 percentile against all US counties.** | Units don't mix, so percentiles make them comparable. |
| R2 | **Power score = 55% capacity + line length, 20% planned + firm generation, 25% cheap power.** **Water = 60% water-limited MW + 40% low stress.** **Land = 50% land MW + 50% low density.** | — |
| R3 ⚑ | **Default weights are power 45 / water 30 / land 25, and users can change them.** | Power is the main constraint in this theme. |

## Your company: AI usage (B)
These numbers are in `data/siting_factors.json` → `company`.

| # | Assumption | Reason |
|---|---|---|
| B1 | **Usage is read with the AI Energy Bill parser and scaled to one month.** Each model is first looked up in the team sheet's catalog (`data/model_catalog.csv`, 38 models) by exact name, ignoring a date suffix; otherwise it is sorted into small, medium or large by keywords. | It reuses a tested parser that accepts Claude, OpenAI and Google exports. |
| B2 | **The API bill uses each model's own list price from the team sheet** (dated 2026-11-06, mostly from a third-party price calculator). Cached input is priced at 10% of the input price ⚑. Models not in the sheet use the Claude list price of the same size class. | It is shown for context only; the footprint doesn't depend on it. |
| B3 | **Ready-made samples come from the team sheet's developer scenarios:** 10, 50 or 500 developers, 30 requests a day each, 20 workdays, 1,250 input + 275 output tokens per request. The team picks the model. | Source: the sheet's Usage assumptions tab (token ranges from iternal.ai). The app reproduces the sheet's own kWh results. |
| B4 | **We assume the company keeps using a cloud AI API.** | For almost every company it is far cheaper than renting GPUs, colocating or building. Our earlier build-vs-buy model found building pays off only at thousands of times a typical company's volume. |
| B5 | **The disclosure note is drafted by Claude (claude-opus-5-5, low effort) from the computed numbers only.** Without an API key, a template note is used. | The AI writes the methodology paragraph; it can't change or invent figures. |

## Impact layer (environment, V)
| # | Assumption | Reason |
|---|---|---|
| V1 | **Grid CO₂ and clean share are each grid operator's average generation mix over Jul 2025–Jun 2026** (EIA-930 hourly generation by fuel). The county takes its operator's mix: the most common operator among its power plants, or the state's most common if it has none. | Same footprint logic as the AI Energy Bill project (location-based), but fresher and local. Checks against EPA eGRID: ERCOT 0.31 vs 0.33, CAISO 0.18 vs 0.20 kg/kWh. |
| V2 | **CO₂ per kWh generated: coal 1.04, gas 0.44, oil 1.08, other (biomass, waste, unknown) 0.5 ⚑; nuclear, hydro, wind, solar and geothermal 0.** | EIA FAQ "How much carbon dioxide is produced per kilowatthour". These are CO₂ from combustion only, not lifecycle. |
| V3 | **Water consumed at power plants (L/kWh): coal 2.60, gas 0.75, nuclear 2.54, oil 1.5 ⚑, other 1.0 ⚑, geothermal 1.0 ⚑, solar 0.004. Hydro reservoir evaporation is excluded ⚑.** | NREL (Macknick et al. 2012) medians for cooling-tower plants. Including hydro evaporation (as LBNL's 4.4 L/kWh national figure does) would raise hydro-heavy grids a lot. |
| V4 | **Operators whose reported generation is more than 3× what running at peak all year would produce are treated as bad data** (e.g. BANC reports ~100× its output). Their 40 counties use the state median and are flagged. | EIA-930 has known reporting errors for some small operators. |
| V5 ⚑ | **Environmental score = 50% low grid CO₂ + 30% low water stress (see W4) + 20% clean power planned nearby by 2029** (solar, wind, batteries, nuclear, hydro, geothermal in EIA-860M). | Carbon is the biggest and most comparable impact. Water stress matters locally. New clean supply nearby makes it easier to match the campus with clean power. |
| V6 | **Footprints are per year for the campus the county can host (the same one the cost is for) at 70% load:** CO₂ = kWh × grid rate; water = on-site cooling (cooling design × local heat) + power-plant water. Equivalents: trees 60 kg CO₂/yr, homes 12,194 kWh/yr (EPA), cars 4.6 t CO₂/yr (EPA), Olympic pool 2.5 million L. | These are the AI Energy Bill conventions. We say "equivalent", never "offset". |
| V7 | **Figures are location-based.** Clean-power purchase contracts would lower a company's market-based figure, but not what the local grid actually burns. | It is the conservative, comparable choice (same as AI Energy Bill A3). |

## Your company: emissions and SB 253 (G)
| # | Assumption | Reason |
|---|---|---|
| G1 | **Emissions are location-based: the company's kWh a year (B1/T2) × the grid CO₂ factor where the AI runs.** | It is the activity-based method; a provider rarely gives customer-specific data. |
| G2 | **Where the AI runs:** the US average grid (0.35 kg/kWh) by default ⚑. Otherwise one of six common cloud regions, each mapped to one county in it, or any county clicked on the map. That place uses its grid operator's 12-month mix (V1). | Providers don't say which data center served a request. The regions are approximate public locations: Northern Virginia (Loudoun), Ohio (Franklin), Iowa (Pottawattamie), Texas (Dallas), Oregon (Morrow) and Central Washington (Grant). A provider can serve any request from any region. |
| G3 | **It is reported as Scope 3, Category 1 (purchased goods and services).** | GHG Protocol: buying AI through an API is a purchased service. The provider's electricity is its Scope 2, not the customer's. |
| G4 | **SB 253 timeline (checked 2026-11-06):** applies to US companies with over $1B revenue doing business in California. Scope 3 starts with the 2027 cycle, and CARB's proposal phases in five categories first, including Category 1. The first Scope 1 and 2 reports were due Nov 10, 2026. | Greenberg Traurig (Oct 2026), Fenwick (Jul 2026), Vinson & Elkins via JD Supra (Apr 2026). The Scope 3 rules are still a proposal, and SB 253 faces litigation in the Ninth Circuit. |
| G5 | **Small footprints are shown in kg, large ones in tonnes, and the worksheet keeps full precision.** | A small team's AI use is tens of kg a year; showing "0.0 t" would read as zero. |
| G6 | **The worksheet lists, per model: tokens, kWh a year, the grid factor and where it runs, kg and t CO₂e a year, the reporting line and the method, plus the same usage in other regions and the sources.** | It gives a reporting team a documented, activity-based starting point. It is not a filing. |
