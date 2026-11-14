# CLAUDE.md — FireCalendar (NASA Space Apps Challenge 2026)

Read this first. It is the full handoff from the planning/build chat (14–15 Nov 2026).

## 0. Who / what / when
- **Owner:** Rocky (Rakesh Ganji), Hyderabad. Software engineer; intermediate pandas, fine with polars/duckdb/any language.
- **How Rocky wants to work:** direct, compressed answers. Precise diagnosis over broad rewrites. Iterative, approval-based changes (no unrequested overhauls). When teaching: one step at a time, small hand-worked example first, visuals/playable demos preferred. **Never hallucinate** — verify facts against data or sources; say "I don't know" or label assumptions.
- **Challenge:** NASA Space Apps 2026 — *"Harmonization of MODIS and VIIRS Hot Spots"* (Advanced/Intermediate). Build a web app that harmonizes MODIS + VIIRS active-fire hotspots into a **burning activity calendar** for a selected area: historical patterns, anomalies vs history, critical periods, CSV download. Audience: early-warning/emergency responders, scientists, land managers.
- **DEADLINE: Sunday 15 Nov 2026, 11:59 pm IST (local event time). Submit early (target 6 pm).**

## 1. Submission requirements (from the official 2025 guide; assume same for 2026)
1. Project name, high-level summary.
2. **Demo link** (public, external): video ≤ 30 s with English subtitles **or** ≤ 7 slides (English, incl. title slide, team name, member names, challenge).
3. **Final project link**: public, no login (live app + GitHub repo).
4. Detailed description (what/how/benefits/tools).
5. NASA data used (required for global awards) — FIRMS MODIS C6.1 + VIIRS 375 m.
6. Space-agency-partner & other data (datameet boundaries, OpenStreetMap basemap tiles, CDN libs).
7. **Use of AI** — must disclose: built with Claude (Anthropic). AI images/videos need visible watermark; AI code/data acknowledged in text + metadata.
8. Judging criteria: **Impact, Creativity, Validity, Relevance, Presentation** (presentation weighted equally).

## 2. Data (already downloaded — do not re-download)
- `data/raw/*_India.csv` — 48 FIRMS country-yearly CSVs (1.1 GB): MODIS 2000–2025, VIIRS S-NPP (`viirs-snpp`) 2012–2025, VIIRS NOAA-20 (`viirs-jpss1`) 2018–2025. No 2026 (yearly zips 404). NOAA-21 not in country zips.
- Source: `https://firms.modaps.eosdis.nasa.gov/data/country/zips/{src}_{yr}_all_countries.zip`; `scripts/download_firms.py <Country>` extracts only that country's CSV via HTTP range requests (fast). Works for any country name used by FIRMS (e.g. Brazil, Australia, Indonesia, Canada).
- `data/processed/fires_india.parquet` — 14,633,820 rows, unified schema: `lat, lon, date, time_utc (HHMM UTC), sensor (modis|viirs-snpp|viirs-jpss1), satellite (Terra|Aqua|N|N20), confidence_raw, bright_k, bright2_k, scan, track (km), frp (MW), daynight (D/N), type (0 veg fire, 1 volcano, 2 static/industrial, 3 offshore), conf_class (low|nominal|high)`. Built by `scripts/build_parquet.py` (streams per file; reads `*_India.csv` — generalize for other countries).
- conf_class: MODIS numeric → low <30, nominal 30–79, high ≥80 (common FIRMS convention — **still to verify against NASA MODIS user guide**); VIIRS l/n/h.
- **Always filter `type=0 AND conf_class<>'low'`** for counts.
- Boundaries: `data/boundaries/india_{states,districts}_{web,calc}.geojson` (datameet: current 36 states; 641 Census-2011 districts re-assigned to current states, e.g. Adilabad→Telangana). `web` = simplified for map, `calc` = for point-in-polygon. Built by `firecal/boundaries.py`.

## 3. Key facts learned (verified in our data — use in pitch)
- VIIRS reports ~5.5× more detections than MODIS (pixels 375 m vs ~1 km; sees smaller fires). Ratio varies by region (3.6 NE India … 7.8 central) and month (4.2–8.8) → one multiplier is wrong.
- MODIS has a break: Terra-only until Aqua (Aqua data from Jul 2002; first full month Aug 2002).
- **MODIS orbit drift:** median day-pass over India — Terra ~11:00 IST until 2021 → 10:02 (2025); Aqua ~13:30 → 14:35 (2025). MODIS is not a stable ruler after 2021.
- **Flagship finding ("Aqua as accidental afternoon witness"):** Punjab-Haryana Oct–Nov, Aqua detections per S-NPP detection vs 2012–19 normal: ~1.0× through 2022 → 1.38× (2023, Aqua 14:07) → 2.10× (2024, 14:37) → 3.30× (2025, 15:14). Control region (central India Mar–May): no rise (0.68–1.20×). Consistent with ISRO SAC (Current Science, Nov 2025) and iFOREST (Dec 2025) reports that Punjab/Haryana farmers shifted burning to late afternoon (~17:00) to evade polar-satellite passes. Present as **evidence consistent with**, not proof. Saved: `data/processed/aqua_witness_test.csv`.
- S-NPP fire data production ceased 2 Nov 2026 15:40 UTC (FIRMS FAQ). NOAA-20/21 continue.
- First VIIRS 2024 row (17.17N, 79.99E) is in Khammam district, Telangana (~161 km from Hyderabad) — verified with boundaries.

## 4. Method (implemented)
- One unit: **MODIS-equivalent fire counts** (Terra+Aqua).
  - 2000-12 … 2002-07: Terra × learned Terra→(Terra+Aqua) factor ("terra-adjusted").
  - 2002-08 … 2021-12: MODIS measured ("modis-measured").
  - 2022-01 → : VIIRS translated → MODIS-eq; mean of S-NPP and NOAA-20 translations when both exist ("viirs-translated").
- Factors per **0.5° cell × calendar month**, ratio shrunk toward the monthly national ratio with pseudo-count K=20; fallback month ratio → national. Trained only on stable years ≤ 2021 and only months the satellite actually operated (S-NPP from 2012-02, NOAA-20 from 2018-05; partial first months skipped — this caused a bug before, keep it).
- **Validation (leave-one-year-out), `data/processed/errors_india.json`:**
  | translator | R² (2° block-month) | median monthly rel. err | yearly bias RMS |
  |---|---|---|---|
  | S-NPP→MODIS-eq | 0.978 | 16.3% | 5.6% |
  | NOAA-20→MODIS-eq | 0.985 | 18.1% | 3.5% |
  | Terra→Terra+Aqua | 0.801 | 24.5% | 9.2% |
  Earlier comparison (scripts/harmonize.py): per-cell×month translator halves MAE vs one national multiplier (S-NPP block-month MAE 12.8 vs 25.7).
- Uncertainty band in app = value × (1 ± median rel err of the method); 0 for MODIS-measured.
- Anomaly: same month across years ≥2003 excl. target (earlier years only if ≥8 exist); median = normal; percentile with ties counted half; labels: ≥90 much higher, ≥75 higher, ≤10 much lower, ≤25 lower; "too little fire to compare" if median<3 and value<3.
- Blind-spot check: in the area's 2 peak months (2003–2021 climatology), Aqua/S-NPP daytime detections per year vs 2012–19 mean; flag if any year ≥2023 with ≥50 Aqua detections has ratio ≥1.5×.

## 5. Code map
- `firecal/build.py <Country>` → `data/processed/factors_<c>.parquet`, `monthratio_{terra,snpp,n20}_<c>.parquet`, `errors_<c>.json`.
- `firecal/engine.py` — `Engine(country)`: `points(geom)`, `daily(geom)`, `monthly(geom)` → DataFrame (terra, aqua, snpp, n20, modis, method, value, rel_err, lo, hi, viirs_eq), `calendar(m)`, `anomaly(m, year, month)`. ~1–2.5 s for big areas.
- `firecal/app.py` — FastAPI: `POST /api/query {country,id|geometry,year?,month?}` (monthly, calendar, climatology, anomaly, yearly, blind_spot, sensors+errors), `POST /api/csv`, `GET /api/boundaries/{state|district}`, `GET /api/areas`, `/docs`; serves `web/` as static. NaN→None via `clean()`. LRU cache per area.
- `web/index.html` — single page: Leaflet (+leaflet.draw) map with States/Districts toggle, search, draw polygon; ECharts: answer card + stats, blind-spot alert (bar + Aqua time line), calendar heatmap (log colour, click a cell → that month), monthly time series with band + MODIS/VIIRS dotted, yearly bars with error bars, satellite-team timeline, CSV download, methods/validation section.
- `scripts/` — download, build_parquet, harmonize (validation comparison), overview_figs. `figures/01_data_overview.png`.

## 6. Run
```bash
cd /Users/Apple/Desktop/0.1/nasa-sc
.venv/bin/uvicorn firecal.app:app --host 127.0.0.1 --port 8765 --reload
# open http://127.0.0.1:8765
```
`.venv` = Homebrew Python 3.13 with requirements.txt installed. Do not use /usr/bin/python3 (3.9). A uvicorn may already be running on 8765 from the chat session — `lsof -ti:8765 | xargs kill` before restarting. Logs went to `data/server.log`.

## 7. Task list (priority order) — core first, extras only after core works end to end
1. **[Done 15 Nov] Web app polish + test** (Task 3). Fixed: default = peak month of latest full year; engine series now ends at dataset end for every area (was each area's last fire); calendar colour used raw counts not log (`visualMap.dimension:2`); CARTO tiles now need an API key → switched to OSM standard tiles; search matches full "district, state" (13 duplicate names); stale-response race guard; peak months sorted; favicon; mobile header. Tested in Playwright: state, district, drawn polygon, selectors, calendar click, CSV, 390 px mobile, console clean.
2. **Fire-season clock + 4-week outlook** (Task 4): per area & "fire year" (start at climatology minimum month), daily MODIS-eq → onset (10% cumulative), peak (max 15-day rolling), end (90%); Theil–Sen trend of onset (days/decade); outlook = climatology for next 4 weeks with spread.
3. **Worldwide** (Task 5): run download → build_parquet (generalize) → firecal/build.py for 3–4 countries (Brazil, Australia, Indonesia, Canada); country switcher; boundaries for others via geoBoundaries ADM1 (or drawn areas only). Note blind-spot logic is generic.
4. **Claude features** (Task 6): Rocky has Anthropic API credits. Put key in `.env` as `ANTHROPIC_API_KEY` (never commit, never print). "Ask FireCalendar": Claude answers questions **only from engine numbers** (tool use: query area/month → JSON) — no invented facts. Plain-language summaries in **English, Hindi, Telugu**. Alert demo: WhatsApp/Telegram message "your district is burning 2× normal this week" (Rocky builds WhatsApp bots professionally).
5. **Open data + API docs** (Task 7): export harmonized cell-month dataset (CSV/Parquet) + README; FastAPI /docs already exists.
6. **2026 NRT data** (Task 8): needs Rocky's FIRMS MAP_KEY (`https://firms.modaps.eosdis.nasa.gov/api/map_key/`), put in `.env` as `FIRMS_MAP_KEY`. Area API: `/api/area/csv/{KEY}/{SOURCE}/{bbox}/{days≤10}/{date}`, sources VIIRS_NOAA20_NRT, VIIRS_NOAA21_NRT, VIIRS_SNPP_NRT, MODIS_NRT. NRT ≠ standard (SP) processing — label it. (Verify endpoint format in the FIRMS API docs before use.) NOAA-21 has no training overlap → use NOAA-20 factors as proxy and say so.
7. **Deploy** (Task 9): public URL, no login (Hugging Face Spaces Docker / Render / Railway). Data ~450 MB processed — consider shipping only fires parquet + factors; or pre-aggregate daily per 0.1° to shrink. GitHub public repo + README.
8. **Submission** (Task 10): 30-s video (story: *"Punjab says farm fires fell 80%. Did they?"* → calendar → blind-spot → answer), ≤7 slides, all form text incl. AI disclosure.
9. **Verify** (Task 11): numbers vs raw data, every feature, public links, proofread.

## 8. Rules for this project
- Keep science honest: show uncertainty, label NRT/estimated periods, say "consistent with" for the blind-spot finding.
- Never add the sensors' counts together (double counting across passes); a "fire count" = flagged pixels per pass, not fires on the ground.
- Don't touch `data/raw`. Keep scripts re-runnable. Small, reviewable changes; tell Rocky what changed.
- Remind Rocky after the project: he asked to revisit and properly learn VIIRS ti4/ti5 brightness temperatures + infrared/wavelength physics.
