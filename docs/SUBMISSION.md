# Submission text (paste into the Space Apps form)
Every number below is in docs/FINDINGS.md with how it was checked. `[ROCKY]` = fill in yourself.

## F2. Project name
FireCalendar

## F3. High-level summary
FireCalendar answers one question for any place in India: is the burning here normal? It merges 25 years of NASA
satellite fire detections from MODIS (since 2000) and VIIRS (since 2012) into a single consistent series, then shows a
burning calendar, a comparison with history, critical fire seasons and downloadable data for any state, district,
drawn area or lat/lon point. VIIRS sees about 5.5× more fires than MODIS and the ratio changes by place and season, so
we translate between sensors per 55-km grid cell and month; this halves the error of a single multiplier. Each number
comes with an uncertainty band and a label saying how it was measured. The harmonized record also reveals a blind
spot: in Punjab, NASA's Aqua satellite now passes later in the afternoon and sees up to 3–4× more fires, relative to
earlier VIIRS passes, than it used to. This is consistent with reports that farmers now burn after the main satellite
passes, so some of the reported fall in farm fires may be fires the satellites no longer see.

## F6. Final project links
- Live app (no login): https://firecalendar-ten.vercel.app
- Code, data and method: https://github.com/infinitethoughts7/firecalendar

## F7. Detailed project description
**What it does.** FireCalendar is a free web app for emergency and early-warning teams, scientists and land managers.
Pick an area (36 states, 641 districts, a drawn polygon, or `lat, lon, radius`) and a month. The app shows:
- the number of fires in one consistent unit (MODIS-equivalent), with an uncertainty range;
- how that compares with the same month in other years: median, average, percentile, and a plain label such as
  "much lower than usual";
- a burning calendar (years × months, Dec 2000 → Nov 2026), monthly and yearly charts, the area's fire seasons with
  their trend (the Punjab Oct–Nov season now starts about 8 days later per decade), and a 4-week outlook from history;
- a blind-spot alert where satellite timing may now hide fires;
- downloads for any date range: monthly, yearly and per-grid-cell CSV, plus one PNG of all charts. An open API (local
  FastAPI, documented at /docs) also returns raw hotspot points.

**How it works.** We downloaded 14.6 million FIRMS detections for India (MODIS C6.1 2000–2025; VIIRS S-NPP 2012–2025;
VIIRS NOAA-20 2018–2025), plus 1.2 million detections for 2026 through the FIRMS API (near-real-time months are
labelled provisional). We keep vegetation fires only and remove low-confidence detections. MODIS is used as measured
for Aug 2002 – 2021. Before Aqua (to Jul 2002) we scale Terra with a learned factor. From 2022, both MODIS orbits had
drifted, so we translate VIIRS into MODIS units with factors learned per 0.5° cell × calendar month on the stable
years. Validation is leave-one-year-out: R² 0.978 (S-NPP) and 0.985 (NOAA-20) at about 200 km × monthly scale, with a
median monthly error of 16–18% and a yearly bias of 3.5–5.6%. That error becomes the uncertainty band shown in the
app. The public site is static (precomputed JSON), so it is fast and never sleeps. Drawn areas are harmonized in the
browser.

**Why it matters.** Fire statistics are used to judge policy, for example claims that farm fires in Punjab fell
sharply. Raw sensor counts can't be compared over time, and our data show that the time of the satellite's pass now
matters. Punjab Oct–Nov detections from the ~13:30 VIIRS pass fell 95% from 2021 to 2025. The later-passing Aqua
(about 15:15 IST in 2025) shows −81%. Aqua detections per VIIRS detection, against the 2012–19 normal, rose from
about 1.0× to 3.98× (2025), with no rise in a control region. This is consistent with ISRO SAC (Current Science,
Nov 2025) and iFOREST (Dec 2025) reports of burning moving to late afternoon. FireCalendar flags this per area
instead of hiding it.

**Tools.** Python (DuckDB, Polars, pandas, Shapely, FastAPI), JavaScript (Leaflet, Leaflet.draw, Apache ECharts),
Vercel (static hosting), GitHub.

## F8. NASA data
- FIRMS MODIS Collection 6.1 active fire / hotspot data (Terra and Aqua), 2000–2026: standard processing; near-real-time
  from Sep 2026.
- FIRMS VIIRS 375 m active fire data: Suomi NPP (2012 – 2 Nov 2026, end of S-NPP production) and NOAA-20 (2018–2026);
  standard processing, near-real-time from Aug 2026.
- Sources: FIRMS country archive (firms.modaps.eosdis.nasa.gov/data/country) and the FIRMS area API.
- MODIS C6/C6.1 Active Fire Product User Guide (confidence classes, §8.4.3).

## F9. Space-agency partner and other data
- India state and district boundaries: datameet (github.com/datameet/maps), based on Census 2011 districts reassigned to
  current states.
- Basemap tiles: © OpenStreetMap contributors.
- Published reports cited for context (not used as data): ISRO Space Applications Centre (Current Science, Nov 2025);
  iFOREST (Dec 2025).
- Libraries: Leaflet, Leaflet.draw, Apache ECharts, DuckDB, Polars, pandas, Shapely, FastAPI.

## F10. Use of AI
This project was built with Claude (Anthropic), using Claude Code as a coding assistant. Claude helped write the data
pipeline, the web app, the validation scripts and the documentation. The author directed, reviewed and tested
everything. Every number in the app, the README and this submission is computed by our code from NASA FIRMS data and
checked against the raw detections; none was generated by the AI. No AI-generated images, video or audio are used.
[If the video uses AI voice or images, add a visible "AI-generated" watermark and say so here.]

## F4. 30-second video: script (English subtitles)
| s | Screen | Subtitle |
|---|---|---|
| 0–4 | Punjab on the map | "Farm fires in Punjab fell sharply, the satellites say. Did they?" |
| 4–10 | Burning calendar, Punjab | "FireCalendar merges 25 years of NASA MODIS and VIIRS fire data into one comparable record." |
| 10–16 | Answer card: Nov 2024 "much lower than usual" | "Any area, any month: how much fire, compared with normal, and how sure we are." |
| 16–24 | Blind-spot chart, bars rising with the Aqua pass time | "But NASA's Aqua now passes later in the afternoon, and it sees up to 4× more fires than before, relative to earlier passes." |
| 24–30 | Logo + URL | "Some fires may be hiding from the satellites. FireCalendar shows where. firecalendar-ten.vercel.app" |

## F5. Slides (≤ 7)
1. Title: FireCalendar · team `[ROCKY]` · members `[ROCKY]` · challenge "Harmonization of MODIS and VIIRS Hot Spots".
2. Problem: two sensors, 5.5× different counts, and the ratio varies (3.6–7.8× by region); MODIS orbit drift after 2021.
3. Method: three periods (terra-adjusted / MODIS measured / VIIRS translated), per-cell × month factors, uncertainty
   band.
4. Validation: R² 0.978 / 0.985 / 0.801 table; the per-cell method halves the error of a single multiplier.
5. App: screenshot (calendar + answer card + downloads); states, districts, draw, lat/lon, date range, CSV/PNG.
6. Finding: Punjab blind spot, with the Aqua-vs-VIIRS bar chart, "consistent with" ISRO/iFOREST, and the control region.
7. Impact and next steps: daily updates, more countries, alerts; links to the app and the repo; built with Claude.
