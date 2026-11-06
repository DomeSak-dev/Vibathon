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
| P1 ⚑ | **Deliverable MW by highest line voltage in the county: 230 kV → 250 MW, 345 kV → 500 MW, 500 kV+ → 1,000 MW, none → 50 MW.** HVDC is treated as 500 kV. | Typical single-circuit carrying ranges: 230 kV ~200–400 MW, 345 kV ~400–900 MW, 500 kV 1,000+ MW. We use the low-middle because some capacity is already used. |
| P2 ⚑ | **Planned generation within the county by 2029 adds 25% per GW (max +50%). Retirements by 2030 remove 15% per GW.** | New local supply eases connection, and retirements tighten it. Source: EIA-860M Sep 2026. |
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
| T2 | **Wh per 1,000 output tokens: small 0.3, medium 1.5, large 4.5, with low/high ranges** (PUE included). | The figures are reused from the AI Energy Bill project; see its ASSUMPTIONS.md section C. |
| T3 | **Tokens are output tokens; all campus energy goes to inference.** | It keeps the headline simple. Training would lower the count. |

## Pricing
Cost per year = energy + capacity + water and sewer + a yearly charge on the land. Missing inputs stay missing: a county with no electricity rate, or no room for a campus, gets no cost, never $0. All numbers are in `data/siting_factors.json` → `pricing`.

| # | Assumption | Reason |
|---|---|---|
| C1 | **Energy = MWh × the state industrial average rate (EIA, Jan–Aug 2026).** | Large campuses buy on industrial or large-load tariffs. A real tariff quote can differ a lot. |
| C2 ⚑ | **PPA option: solar $60/MWh or wind $70/MWh, plus 2.25¢/kWh for delivery (the midpoint of 1.5–3¢).** | From the LevelTen Q2 2026 index, approximate because the full index is paid. A PPA covers energy only, so delivery is added. |
| C3 ⚑ | **Capacity: PJM counties pay $333.44/MW-day × campus MW (2027/28 auction, RTO-wide, at the cap). Other grids are assumed to be inside the energy price.** | Source: [PJM, Dec 17 2025](https://insidelines.pjm.com/pjm-auction-procures-134479-mw-of-generation-resources/). MISO, ISO-NE and NYISO run capacity markets too but aren't priced yet. Part of the PJM price is already in 2026 state rates, so this may double count some of it. |
| C4 ⚑ | **882 counties have no grid operator on file (no generator there). They take the nearest county in the same state that has one.** | Shown as "est." in the app. |
| C5 ⚑ | **The $6 default water rate is scaled ×0.75 (no stress) to ×1.5 (highest stress). Verified local rates are used as they are.** | Scarce water tends to cost more. A starting guess. |
| C6 ⚑ | **Sewer is charged on 20% of the water volume, at the water rate.** | Cooling towers discharge part of what they take. |
| C7 | **Land price = state farm real estate value per acre (USDA NASS Land Values 2026; US average $4,500). Alaska, Hawaii and DC aren't reported and use the US average, flagged.** | The only current national series. County values from NASS Quick Stats would be better. Source: [USDA NASS](https://esmis.nal.usda.gov/sites/default/release-files/795999/land0726.txt). |
| C8 ⚑ | **Land near big lines costs more: ×1 with no 230 kV+ line, ×10 at 230 kV, ×20 at 345 kV, ×25 at 500 kV.** | Sites near 230–500 kV lines sold for about 2.4× those near 138 kV or lower (Altus Group, 80 deals), and powered land in Northern Virginia sells for $4–6M an acre. This puts rural land near a big line in the six figures per acre. |
| C9 ⚑ | **Land is bought once and carried at 8% of its price a year.** | A common capital charge. It puts a one-time cost on the same yearly basis as the rest. |
| C10 | **Cost per MWh = yearly total ÷ MWh at 70% load. The Cost map colors counties by its percentile (lighter = cheaper).** | Per-MWh cost compares counties of different sizes. |

## Scoring
| # | Assumption | Reason |
|---|---|---|
| R1 | **Every sub-score is a 0–100 percentile against all US counties.** | Units don't mix, so percentiles make them comparable. |
| R2 | **Power score = 55% capacity + line length, 20% planned + firm generation, 25% cheap power.** **Water = 60% water-limited MW + 40% low stress.** **Land = 50% land MW + 50% low density.** | — |
| R3 ⚑ | **Default weights are power 45 / water 30 / land 25, and users can change them.** | Power is the main constraint in this theme. |
