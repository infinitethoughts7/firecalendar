# Space Apps 2026 — submission text (copy field by field into the project page)
Every number below comes from docs/FINDINGS.md (verified). All features named here are live (checked 15 Nov 2026).

---
## 1. Project name
FireCalendar — 25 years of NASA fire data, made comparable

## 2. High-level project summary
FireCalendar turns two decades of NASA satellite fire detections into one consistent burning calendar that anyone can read. MODIS (since 2000) and VIIRS (since 2012) count fires very differently: VIIRS reports about 5.5 times more detections over India, and the gap changes by region (3.6× to 7.8×) and by season. We built a validated translator, learned for every 55 km cell and calendar month, that converts all records into one unit, so the sensor no longer matters. Pick a state or district, draw an area or enter coordinates, and FireCalendar answers in plain words: "November 2024 in Sangrur, Punjab: much lower than usual." It shows the 2000–2026 calendar, the normal for each month, uncertainty bands, the fire-season start and peak, and a 4-week outlook, with CSV and chart downloads. It is also honest about what satellites cannot see. Our analysis found that as NASA's Aqua satellite drifted to later afternoon passes, it began seeing 3.9 times (2025) and 6.7 times (2026, provisional) its usual share of Punjab stubble fires relative to the early-afternoon VIIRS satellite, consistent with reports that burning moved to late afternoon. So FireCalendar warns users when a falling fire count may partly be fires the satellites missed. Users can also ask questions in English, Hindi or Telugu; Claude answers only from FireCalendar's own numbers.

## 3. Link to project demo
Video (29.6 s, English subtitles burned in): https://github.com/infinitethoughts7/firecalendar/blob/master/docs/FireCalendar_demo_30s.mp4
Slides (7, PDF, backup): https://github.com/infinitethoughts7/firecalendar/blob/master/docs/FireCalendar_slides.pdf

## 4. Link to final project
Live app (no login): https://firecalendar-ten.vercel.app
Code: https://github.com/infinitethoughts7/firecalendar

## 5. Detailed project description
**What it does**
- One harmonized burning calendar (years × months, Dec 2000 → Nov 2026) for any Indian state (36), district (641), drawn area, or latitude/longitude point, in a single unit: MODIS-equivalent fire detections.
- A plain-language answer for any month: how many fires, the normal for that month (median and average of past years), the percentile, and a label from "much lower" to "much higher than usual".
- Fire-season clock: when each burning season starts, peaks and ends every year, and whether it is shifting. Punjab's Oct–Nov stubble season now starts 8.3 days per decade later (95% range +6.0 to +10.0); Odisha's Feb–May forest-fire season starts 16.7 days per decade earlier.
- A 4-week outlook from history: what the next weeks usually look like in this area (a climatology, clearly labelled as not a forecast).
- A blind-spot warning: polar-orbiting satellites only look at fixed times of day. When an area's fires appear to be falling but the later-afternoon satellite keeps seeing more, FireCalendar warns that part of the drop may be unseen fires.
- Downloads: monthly harmonized CSV with low/high estimates and the raw count from every satellite, raw hotspot CSV for the area and date range, and PNG images of the charts.
- Ask FireCalendar: type a question in English, Hindi or Telugu ("Did farm fires in Punjab really fall in 2025?"). Claude looks up FireCalendar's own numbers with tools and answers only from them, listing the data it used. Rate-limited, with a daily cap and a kill switch.
- Works on desktop and phone; static site, loads fast, no login.

**How it works**
1. Data: NASA FIRMS active-fire records for India, 14.6 million detections (2000–2025) plus 1.2 million for 2026 (Jan–14 Nov). We keep vegetation fires only and remove low-confidence detections (classes per NASA's MODIS C6.1 user guide).
2. The problem: MODIS pixels are about 1 km and VIIRS pixels 375 m, so VIIRS sees smaller fires and splits big ones into more pixels. The ratio between them changes by place and season, so one multiplier is wrong.
3. One unit: MODIS (Terra + Aqua) is the reference for 2002–2021, when both orbits were stable. Before Aqua (2000–02), Terra-only counts are scaled by a learned factor. From 2022, Terra and Aqua orbits drift to different times of day (Aqua from ~13:30 to ~15:50 IST), so we translate VIIRS (S-NPP and NOAA-20) into MODIS units. Translation factors are learned per 0.5° cell and calendar month on 2012–2021 and shrunk toward the monthly average where data are thin. The method already survives the end of S-NPP fire data (2 Nov 2026), because NOAA-20 carries on.
4. Validation: each year was hidden in turn, the translator learned on the other years, and the hidden year predicted from VIIRS alone. Accuracy at ~200 km, monthly: R² 0.978 (S-NPP) and 0.985 (NOAA-20); typical monthly error ±16–18%; yearly totals within ±3.5–5.6%. That halves the error of a single national multiplier. These errors become the uncertainty band on every number in the app.
5. Checks: the static site reproduces our Python API in 180 of 180 test cases; independent counts from the raw data match the site exactly in 4 of 4 spot checks; 2026 near-real-time data are labelled provisional.

**Benefits**
- Emergency and forest officers see at a glance whether this month is unusual and when the season usually starts, to plan crews and patrols.
- Pollution and agriculture departments can target stubble-burning districts and weeks, and see when official declines may be overstated.
- Scientists get a consistent, open, uncertainty-aware fire record that continues after MODIS retires.
- Citizens and journalists can check fire claims in plain language.

**Goals**
Make NASA fire data comparable across sensors and years, readable by non-scientists, and honest about its limits.

**Tools**
Python (pandas, Polars, DuckDB, Shapely, NumPy), FastAPI (API and local development), JavaScript, Leaflet and Leaflet.draw (map), Apache ECharts (charts), Vercel (static hosting + one serverless function), Anthropic Claude API (Ask FireCalendar), Playwright (testing), ffmpeg (demo video), Git.

**Who it's for and how to use it**
1. Pick a state or district, draw an area, or enter coordinates. 2. Read the answer card. 3. Explore the calendar, season clock and outlook, then download the data.
- District disaster-management and forest officers: "Is burning unusual this month? When does our season start?"
- Pollution control boards and air-quality planners: "How much burning is upwind, and can we trust the drop?"
- Agriculture departments: "Which districts and weeks need crop-residue support?"
- Scientists and students: "I need a consistent fire record since 2000, with uncertainty."
- Journalists, NGOs and citizens: "Is the claim that fires fell by X% true?"
- Land and protected-area managers: "Is this forest's fire pattern abnormal this year?"

**Future scope**
- Close the evening blind spot with geostationary fire data (ISRO's INSAT-3D series, Meteosat over the Indian Ocean, Himawari), which look every 10–30 minutes.
- Cross-check counts with burned-area products and with Landsat/Sentinel-2 for small fires.
- Energy-based harmonization using fire radiative power, leading to smoke-emission estimates.
- Link fires to air quality (ground stations, Sentinel-5P) downwind.
- Weather-driven fire forecasts instead of history-only outlooks.
- Continuity with NOAA-21 and future JPSS satellites after MODIS retires.
- More countries, block/village boundaries, offline mode, and WhatsApp/SMS alerts in regional languages.

## 6. NASA data
- NASA FIRMS (Fire Information for Resource Management System) active-fire / hotspot data:
  - MODIS Collection 6.1 (Terra and Aqua), 1 km, Nov 2000 – Nov 2026.
  - VIIRS 375 m active fire product, Suomi NPP (Jan 2012 – 2 Nov 2026) and NOAA-20 (Apr 2018 – Nov 2026).
  - Standard-processing country archives (2000–2025) and the FIRMS area API for 2026 (standard processing to Jul/Aug, near-real-time after, labelled provisional).
- How we used it: cleaned and unified 15.8 million detections; learned and validated a cell-by-month translator between sensors; built the harmonized calendar, anomaly, season and outlook views; analysed satellite overpass times to detect the afternoon blind spot.
- Reference: NASA MODIS C6/C6.1 Active Fire Product User Guide (confidence classes); FIRMS FAQ (pixel sizes, overpass times, S-NPP end of production).

## 7. Space agency partner & other data
- ISRO Space Applications Centre study (Current Science, Nov 2025) and iFOREST Stubble Burning Status Report 2025 (Dec 2025): cited as outside evidence for the late-afternoon burning shift. Their data are not used in our calculations.
- India state and district boundaries: DataMeet "maps" project (Census 2011 districts re-assigned to current states), open licence.
- Basemap: © OpenStreetMap contributors (standard tiles).
- Open-source libraries: Leaflet, Leaflet.draw, Apache ECharts, pandas, Polars, DuckDB, Shapely, FastAPI.
- Anthropic Claude API (Claude Opus 5.5): powers the in-app "Ask FireCalendar" answers.
- ElevenLabs: AI voice for the demo video narration (voice "Manish").
- The demo video globe is rendered by our own script from real NASA VIIRS 2024 detections; app shots are a live screen recording of the public site.
- No copyrighted images or media are used.

## 8. Use of Super Intelligence (SI)
Yes. We used Claude (Anthropic) as an assistant during the hackathon:
- To write and debug code: the data pipeline, harmonization and validation scripts, the API and the web app (via Claude Code). All AI-written code was run, tested and checked against the raw NASA data by the team (see Validation and Checks above).
- To explain satellite fire-detection details while we worked, and to draft documentation and this submission text, which the team reviewed.
- Inside the app, "Ask FireCalendar" uses Claude to answer user questions. It can only read FireCalendar's computed numbers through tools, is told not to add outside facts, and shows the data it looked up. The app labels these answers as written by Claude.
- Audio: the demo video's voiceover is an AI voice generated with ElevenLabs. This is stated on screen for the whole video ("AI voice: ElevenLabs") and in the video file's metadata.
- No AI-generated images or video footage are used. The globe is rendered from real NASA VIIRS detections; app shots are a live screen recording. The repository README also records this.

## 9. Team
Team name: Guardians of Galaxy · Members: Nagesh V, Rakesh G, Praveen G · Challenge: Harmonization of MODIS and VIIRS Hot Spots
