# Suggestions: Theme 3, "Time to power"

This is what the prototype does now, what I'd change in the plan, and ideas to add if there's time. ⚑ marks a decision the team should make.

---

## 1. Sharpen the problem and the user (15% + 20% of the score)

The kickoff asks us to "pick a person or business and solve a problem they have." Our three factors are a method, not a user yet. Suggested framing:

> **User:** a site-selection lead at a mid-size AI or colocation company. These are firms without a hyperscaler's in-house team.
> **Problem:** they spend months and consultant fees ruling out counties. The thing that actually kills a site is **time to power**: the grid connection can take years even when the building takes months.
> **Product:** in 5 minutes, see which US counties can host a campus of *X* MW, what limits each one (power, water or land), how long power is likely to take, what it costs to run, and how much AI it could serve.

Other users worth one slide, because the same data serves them:
- **A town or county** deciding whether to welcome a data center. It can flip the question: "how much of our water and grid would a 300 MW campus take?" The detail panel already shows "water need vs. county public supply."
- **An investor** screening data-center land deals.

⚑ Pick one primary user for the pitch. I'd pick the site-selection lead.

## 2. The three factors: what we built and what to change

### ⚡ Power (grid lines)
**Built:** every ≥230 kV transmission line (HIFLD, 10,692 lines), every operating, planned and retiring generator (EIA-860M, Sep 2026), and state industrial power prices (EIA, Jan–Aug 2026). Each county gets:
- **Indicative MW** from its highest-voltage line: 230 kV ≈ 250 MW, 345 kV ≈ 500 MW, 500 kV+ ≈ 1 GW. This is adjusted up for new generation planned nearby and down for retirements.
- **Months to power:** 24–36 months on an existing 500 kV line, 60–96 months if a new line is needed. These ranges are rules of thumb.

**Suggestions:**
- **Add the LBNL "Queued Up" interconnection queue.** It's the single best "time to power" signal, because it shows how many GW are already waiting at each grid operator and the median wait. The site blocked our script (403), so download it by hand and we'll join it by county/ISO. This would turn "months to power" from a rule of thumb into data. **Highest-value next step.**
- **Add substations.** A line passing through isn't enough; you connect at a substation. HIFLD substations are no longer public, but OpenStreetMap has them (`power=substation`).
- **Add hourly grid stress** (EIA Hourly Grid Monitor): grid operators with thin reserve margins at peak are worse bets.
- **Rename it "power headroom (indicative)"** everywhere in the pitch. We know where the big lines are, but not how much of their capacity is already sold. Saying this up front scores on *Feasibility and risks*.

### 💧 Water
**Built:**
- Public-supply water by county from USGS (2015, the latest national county data).
- Climate from NOAA 1991–2020 normals: rainfall and cooling degree days.
- A water-stress index built from withdrawals compared with rainfall, aridity, and the irrigation share.
- **A cooling-design switch** (evaporative 1.8 L/kWh, hybrid 0.5, closed-loop 0.05). Each county's water-limited MW comes from 10% of its public supply ⚑, adjusted for local heat.

**Insight for the pitch:** cooling design often decides whether water is the limit at all. Under hybrid cooling, water is the binding limit in about 2/3 of counties. Under closed-loop cooling, it binds in about 1 in 5. The "Same county, different cooling" chart shows this for any county. That's a decision the user controls, which makes it a strong business-value point.

**Commercial water price:** **there is no national dataset of commercial water rates.** I searched and found only individual city tariffs. Right now we use a **$6.00 / 1,000 gal national default ⚑**, plus 4 verified city rates (Carson City NV, Orange City FL, Webster FL, Lucas TX). Options:
1. Have one teammate collect commercial rates for the ~25 biggest data-center markets (Loudoun, Maricopa, Dallas, Atlanta, Columbus, Des Moines, Reno, Quincy WA, etc.) from utility tariff PDFs and put them in `data/siting_factors.json`. It takes about 2 hours and is good enough for a demo.
2. Show water cost as a range ($3–$12/kgal) except where we have a local rate.

Water is about 1% of running cost next to electricity (e.g. Coconino at about 1 GW: about $4M of water vs. about $507M of electricity a year). So the price matters less than **availability and stress**. Say that in the pitch.

**Further ideas:**
- Replace our stress index with **WRI Aqueduct 4.0** baseline water stress. It's the industry standard but a very large download.
- Add **reclaimed-water availability**. Loudoun's data centers largely use reclaimed water, which is why our model calls Loudoun "water-limited" when the real industry there isn't.

### 🏞 Land (space)
**Built:** land area and population density (Census 2024) give an estimate of open acres. We assume 0.5% of those are realistically available as large parcels ⚑, at 1 acre per MW ⚑.

**Suggestions:**
- **Use the theme-1 satellite data to find actual parcels.** That would be the most original part of the project:
  - **USDA Cropland Data Layer / NLCD:** find flat, undeveloped, non-wetland 100+ acre blocks near a ≥230 kV line.
  - **Microsoft Building Footprints:** confirm the land is empty.
  - **Sentinel-2:** show a "before" image of the candidate site in the detail panel.

  This would also move us from county level to **site level** (see §3).
- Add **slope** (USGS 3DEP), **flood zones** (FEMA NFHL) and **farmland price per acre** (USDA NASS) as filters and costs.

## 3. Granularity

| Level | Pros | Cons |
|---|---|---|
| **County (built)** | All data joins cleanly by FIPS; 3,144 shapes render fast; easy to explain | A big western county hides a lot of variation |
| H3 hexagons (~250 km², res 5) | Even tiles, nicer heat map, lines and water snap to cells | Water and population data are county-level anyway, so we'd fake precision |
| Candidate sites (points) | Real "build here" answer | Needs the land work above |

**Recommendation:** keep counties for the heat map, and add a **"candidate sites" layer inside the selected county**. Show 3–5 points that are within 5 km of a ≥345 kV line, on open, flat land, outside flood zones. That's "zoom from region → county → site," which matches the dashboard idea.

## 4. Dashboard: what's built and ideas

**Built:**
- **Globe intro:** the globe spins, you pick a region (North America; Europe and APAC are listed as "coming soon"), and it rotates and zooms into North America.
- **Heat map:** US counties colored by overall, power, water or land score, with an overlay of 500 / 345 / 230 kV lines.
- **Controls:**
  - A **"Highlight space that can host ≥ X MW"** slider greys out counties that can't host that size.
  - **Weight sliders** let the user say what matters to them.
  - A **cooling-design** switch.
  - A **Top counties** list.
- **Click a county** to open a detail panel with:
  - the largest campus the county could support and **which factor limits it**;
  - months to power;
  - power / water / land MW cards;
  - **tokens per day** for small, medium and large models, with ranges;
  - yearly electricity and water cost;
  - a cooling comparison;
  - the raw data behind the estimate.

**Ideas, roughly by impact:**
1. **"Ask the analyst" box (Smart use of AI, 10%).** The user types a request like "300 MW, closed-loop, in PJM or ERCOT, power within 3 years". Claude turns it into filters and weights and writes a short memo on the top 3 counties. Every number in the memo comes from the API, and the AI only explains. This reuses the pattern from the AI Energy Bill project (`recommend.py`).
2. **Compare two or three counties side by side.**
3. **"Community impact" view for towns:**
   - the campus's share of local water and grid;
   - its likely effect on power bills, citing the PJM capacity-cost finding from our theme-1 research.
4. **Export a one-page site memo as a PDF** (reuse `report.py` from the AI Energy Bill project).
5. **Animate the interconnection queue over time** once we have LBNL data.

## 5. Token estimate: how it works
`tokens/day = MW × 70% average load × 24 h ÷ (Wh per 1,000 output tokens)`

The Wh-per-token factors come from the AI Energy Bill project (`data/energy_factors.json`: small 0.3, medium 1.5, large 4.5 Wh per 1,000 output tokens, with low/high ranges). A 1 GW campus serves about 11 trillion medium-model output tokens a day. That's a nice headline number for the pitch, and the ranges stop it being over-precise.

## 6. Risks to say out loud (Feasibility, 10%)
- **Power MW is a screening estimate, not an interconnection study.** We don't know how much of each line's capacity is already sold.
- **USGS water data is from 2015**, the latest national county-level data.
- **Coconino County, AZ ranks #1 with default weights.** It has 500 kV lines, cheap power and lots of land, but it's arid and water-limited. Judges may question it, so either:
  - demo with closed-loop cooling and say "this is why cooling choice matters," or
  - raise the water weight live to show the ranking respond. ⚑
- Counties are large, so "can host 1 GW" means *somewhere in the county*.

## 7. Suggested next steps (in order)
1. ⚑ Agree on the primary user and the pitch story (§1).
2. Get the LBNL queue data into `data/raw/` (manual download).
3. Collect commercial water rates for ~25 major markets.
4. Build the Claude "Ask the analyst" box.
5. Build the candidate-sites layer from land cover (theme-1 crossover).
