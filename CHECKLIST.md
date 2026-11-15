# FireCalendar — Master checklist (deadline: Sun 15 Nov 2026, 11:59 pm IST; target submit 6 pm)
Mark each item [x] only after verifying it works (open it / run it / test it). Note evidence next to it.
Live: https://firecalendar-ten.vercel.app  ·  Evidence below = checks run on 15 Nov 2026 unless noted.

## A. What the CHALLENGE asks for ("Harmonization of MODIS and VIIRS Hot Spots")
- [x] A1. Harmonize MODIS + VIIRS → one series. — One MODIS-equivalent series Dec 2000 → 14 Nov 2026 (terra-adjusted / modis-measured / viirs-translated); validation in errors_india.json; live JSON == raw parquet (B10).
- [x] A2. Web application that takes the harmonized data as input. — Live site reads precomputed harmonized JSON (web/data); static == API 180/180 cases (test/compare_static.js, after 2026 re-export).
- [x] A3. Draw area of interest on map. — Live: 1°×1° box near Sangrur → "approx., 4 cells", answer + CSV (303 rows).
- [ ] A4. Enter latitude/longitude (point + radius or bbox)  ← not built yet
- [x] A5. States/districts. — 36 states + 641 districts (677 JSON files); search "Sangrur, Punjab", "Odisha" etc. work on live site.
- [ ] A6. DATE RANGE (start–end) and results/downloads respect it  ← not built yet
- [x] A7. Burning activity CALENDAR (years × months). — Heatmap 2000–2026 on live site (log colour scale).
- [x] A8. Which months have more fires. — Calendar + 2003–21 monthly normal + fire-season clock (e.g. Punjab Oct–Nov 82% / Apr–May 16%).
- [x] A9. Which years had more burning. — Yearly bars with error bars; 2026 tooltip marked "year not finished".
- [x] A10. Current month vs historical MEDIAN. — Answer card: value vs median, % of normal, percentile (static == API).
- [ ] A11. Anomalies vs multi-year AVERAGE (show mean as well)  ← add mean
- [x] A12. Number of fires per period. — Monthly + yearly MODIS-eq counts, raw counts per satellite in CSV and tooltip.
- [ ] A13. Accessible colour ramps (colour-blind safe; not colour-only meaning). — Text labels always shown (not colour-only ✔); calendar = single-hue luminance ramp ✔; but answer labels use red vs green → fix to CVD-safe.
- [ ] A14. Download CSV of hotspots (raw points for area + date range)  ← only monthly CSV now
- [ ] A15. Download analytics (harmonized monthly/yearly CSV). — Monthly CSV works (303 rows, live); yearly not downloadable yet.
- [ ] A16. Download visualizations (PNG export)  ← not built yet
- [x] A17. Interactive map. — Leaflet: states/districts toggle, hover, click, draw, zoom (live).
- [x] A18. Plain-language answer + details. — e.g. "October 2026: much lower than usual … 4% of normal … but see the warning below" (live).

## B. Core science (Validity)
- [x] B1. Vegetation only, low-confidence removed; documented. — Code filter `type=0 AND conf_class<>'low'`; stated in Methods ("Data" paragraph). NRT (no type): static-source location mask, validated (FINDINGS #26).
- [x] B2. MODIS confidence classes verified. — MODIS C6/C6.1 Active Fire User Guide v1.0 §8.4.3 Table 11: low 0–<30%, nominal 30–<80%, high 80–100% = our code.
- [x] B3. Terra-only period adjusted. — Months before Aug 2002 method "terra-adjusted" (Terra × learned factor), ±24.5% band.
- [x] B4. MODIS only for stable years; drift handled. — modis_stable_end=2021; 2022→ "viirs-translated" (Punjab 2024-11 method v).
- [x] B5. Factors per 0.5° cell × month, trained ≤2021, correct starts. — errors_india.json cell_deg 0.5, starts snpp 2012-02, n20 2018-05; S-NPP stops 2 Nov 2026 (engine SNPP_END).
- [ ] B6. Validation numbers in app + README. — In app ✔ (Methods table: 0.978 / 0.985 / 0.801); README missing.
- [ ] B7. Comparison vs naive single multiplier shown (error halved). — App says "one multiplier is wrong" but no number shown.
- [x] B8. Uncertainty band + method labelled per month incl. NRT. — Band on time series, lo/hi in CSV, "how this month was measured" tile, "Provisional" note + grey band from Aug 2026.
- [x] B9. Blind-spot per area, "consistent with", sources. — Alert text names ISRO and iFOREST ("fits … as ISRO and iFOREST studies have reported"); computed per area; 2026 S-NPP-end artefact fixed.
- [x] B10. Spot-check vs raw parquet. — Independent DuckDB+shapely counts == live JSON for Sangrur 2015-11, Khammam 2010-03, Odisha 2019-03, Punjab 2024-11 (4/4 exact, per satellite).
- [x] B11. Limits stated. — Methods "Limits" paragraph (pixels per pass, clouds/smoke, short fires).

## C. App quality
- [x] C1. Opens on peak month of latest full year. — Sangrur → May 2025, Odisha → Mar 2025, Punjab → May 2025 (live). Areas with no fire fall back to last month ("too little fire").
- [x] C2. States, districts, search, drawn polygon. — Live tests (Sangrur, Punjab, Odisha, Khammam, Mizoram, Chandigarh, drawn box).
- [x] C3. Selectors + calendar click. — Live: month selector Sangrur May→Mar; year/month → Oct/Nov 2026; real mouse click on calendar cell → "August 2017: normal".
- [x] C4. No NaN/undefined. — Live sweep of 8 areas incl. empty ones (Lakshadweep, Mumbai Suburban, Chandigarh): none.
- [x] C5. Satellite timeline + methods visible. — Both rendered on live site.
- [x] C6. Mobile layout. — 390 px: no horizontal scroll, stacked layout (screenshot .playwright-mcp/vercel-mobile.png).
- [x] C7. No console errors; first load < 3 s. — 0 errors / 0 warnings; DOMContentLoaded 0.17 s (warm); cold file fetches ≤ 0.9 s each (curl).
- [x] C8. Header "data through <date>". — "Data through 14 Nov 2026." (live).

## D. Extras (stand-out) — only after A–C work
- [x] D1. Fire-season clock. — Live; Punjab Oct–Nov onset +8.3 d/decade (6–10), Odisha −16.7.
- [x] D2. 4-week outlook (history, not forecast). — Live outlook card with p10–p90 and last-5-year median.
- [ ] D3. Worldwide: 3–4 more countries + switcher
- [ ] D4. Claude summaries (en/hi/te)  ← Rocky: low value; replace with something better from Claude (see D5)
- [ ] D5. Live "Ask FireCalendar" (Vercel function, key secret, rate limit + daily cap + small max_tokens)
- [ ] D6. Alert demo (Telegram/WhatsApp)
- [ ] D7. Open data + data README + API docs
- [x] D8. 2026 data via FIRMS API, labelled provisional. — 1,217,490 detections 1 Jan–14 Nov 2026; SP to Jul/Aug, NRT after (provisional label + grey band); NRT static mask validated. NOAA-21 not used (no training overlap).
- [ ] D9. Daily auto-update (GitHub Actions)

## E. Deployment
- [x] E1. Static export under size limits. — web/ 23 MB total (largest file grid.json 7.9 MB).
- [ ] E2. Public GitHub repo (no .env, no data/raw, no .venv)
- [x] E3. Vercel; public URL, no login. — https://firecalendar-ten.vercel.app returns 200 without auth; .env.local / .vercel → 404.
- [x] E4. No API key in repo or browser. — Only FIRMS/Anthropic keys in .env (git-ignored); grep of web/ for key names: none. Re-check when D5 adds a Vercel env var.
- [ ] E5. README

## F. Submission (official form fields)
- [ ] F1. Team page (Rocky)
- [ ] F2. Project name
- [ ] F3. High-level summary
- [ ] F4. 30-second video with English subtitles
- [ ] F5. ≤7 slides
- [ ] F6. Final project link: live app + GitHub repo
- [ ] F7. Detailed project description
- [ ] F8. NASA data section
- [ ] F9. Other data section
- [ ] F10. Use of AI section
- [ ] F11. All links tested in a private window
- [ ] F12. Submitted (Rocky)

## G. After the hackathon
- [ ] G1. Remind Rocky to revisit and learn VIIRS ti4/ti5 brightness temperatures + infrared physics
