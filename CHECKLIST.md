# FireCalendar — Master checklist (deadline: Sun 15 Nov 2026, 11:59 pm IST; target submit 6 pm)
Mark each item [x] only after verifying it works (open it / run it / test it). Note evidence next to it.
Live: https://firecalendar-ten.vercel.app  ·  Evidence below = checks run on 15 Nov 2026 unless noted.

## A. What the CHALLENGE asks for ("Harmonization of MODIS and VIIRS Hot Spots")
- [x] A1. Harmonize MODIS + VIIRS → one series. — One MODIS-equivalent series Dec 2000 → 14 Nov 2026 (terra-adjusted / modis-measured / viirs-translated); validation in errors_india.json; live JSON == raw parquet (B10).
- [x] A2. Web application that takes the harmonized data as input. — Live site reads precomputed harmonized JSON (web/data); static == API 180/180 cases (test/compare_static.js, after 2026 re-export).
- [x] A3. Draw area of interest on map. — Live: 1°×1° box near Sangrur → "approx., 4 cells", answer + CSV (303 rows).
- [x] A4. Enter latitude/longitude. — Search box accepts `lat, lon [, radius km]` (default 25 km, 5–150) → circle analysed like a drawn area; outside India → "That point is outside India." (local test, commit 78213f1).
- [x] A5. States/districts. — 36 states + 641 districts (677 JSON files); search "Sangrur, Punjab", "Odisha" etc. work on live site.
- [x] A6. Date range. — From/To month pickers in the download card: zoom the time series, show a range total (Sangrur 2020-01→2026-11: "83 months · 7,494 fires, range 6,823–8,165") and filter every download.
- [x] A7. Burning activity CALENDAR (years × months). — Heatmap 2000–2026 on live site (log colour scale).
- [x] A8. Which months have more fires. — Calendar + 2003–21 monthly normal + fire-season clock (e.g. Punjab Oct–Nov 82% / Apr–May 16%).
- [x] A9. Which years had more burning. — Yearly bars with error bars; 2026 tooltip marked "year not finished".
- [x] A10. Current month vs historical MEDIAN. — Answer card: value vs median, % of normal, percentile (static == API).
- [x] A11. Anomalies vs multi-year average. — Answer shows "(median; average X)"; `mean` in API + static anomaly, parity test 30/30.
- [x] A12. Number of fires per period. — Monthly + yearly MODIS-eq counts, raw counts per satellite in CSV and tooltip.
- [x] A13. Accessible colours. — Text labels always shown (not colour-only); calendar = single-hue luminance ramp; answer labels now red/orange ↔ blue + slate (no red/green pair; commit 087fe80).
- [x] A14. Raw hotspot CSV for area + date range. — "Raw hotspots (CSV)" button (lat, lon, date, time, satellite, sensor, confidence, FRP). 1° tile × year gzipped files on GitHub Pages (108 MB > Vercel Hobby 100 MB upload limit; FIRMS archive has no deep link). Live: Sangrur Oct–Nov 2024 → 3,886 points vs 3,900 in monthly raw counts (0.4%, simplified outline); lat/lon 17.17,79.99 r20 all years → 4,678 points; Madhya Pradesh all years → clear "narrow the date range" message (2.2 M > 2 M limit). Also `/api/points` locally.
- [x] A15. Analytics CSV. — Monthly (value, lo, hi, method, raw per satellite) + yearly (n_months, value, lo, hi, methods); both respect the date range (Sangrur 2020–26: 84 / 8 lines).
- [x] A16. PNG export. — "Charts (PNG)" stitches every visible chart with headings, area, answer and source line into one image (Sangrur: 450 KB, checked visually).
- [x] A17. Interactive map. — Leaflet: states/districts toggle, hover, click, draw, zoom (live).
- [x] A18. Plain-language answer + details. — e.g. "October 2026: much lower than usual … 4% of normal … but see the warning below" (live).

## B. Core science (Validity)
- [x] B1. Vegetation only, low-confidence removed; documented. — Code filter `type=0 AND conf_class<>'low'`; stated in Methods ("Data" paragraph). NRT (no type): static-source location mask, validated (FINDINGS #26).
- [x] B2. MODIS confidence classes verified. — MODIS C6/C6.1 Active Fire User Guide v1.0 §8.4.3 Table 11: low 0–<30%, nominal 30–<80%, high 80–100% = our code.
- [x] B3. Terra-only period adjusted. — Months before Aug 2002 method "terra-adjusted" (Terra × learned factor), ±24.5% band.
- [x] B4. MODIS only for stable years; drift handled. — modis_stable_end=2021; 2022→ "viirs-translated" (Punjab 2024-11 method v).
- [x] B5. Factors per 0.5° cell × month, trained ≤2021, correct starts. — errors_india.json cell_deg 0.5, starts snpp 2012-02, n20 2018-05; S-NPP stops 2 Nov 2026 (engine SNPP_END).
- [x] B6. Validation numbers in app + README. — App Methods table + README table (0.978 / 0.985 / 0.801; 16.3 / 18.1 / 24.5 %).
- [x] B7. vs single multiplier. — Methods text: per-cell × month halves the error (S-NPP MAE per 2° block-month 12.8 vs 25.7, leave-one-year-out, scripts/harmonize.py).
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
- [x] D5. Live "Ask FireCalendar" (Vercel function, key secret, rate limit + daily cap + small max_tokens) — LIVE 15 Nov (dpl_G7FQHNvkr2gxZNmanVAWRoPPjgTs). web/api/ask.js: Claude Opus 5.5 with 4 tools over the static JSON only; 4/min + 30/day per IP (x-real-ip), 300/day per instance, max_tokens 800, ASK_ENABLED=0 kill switch. Live test: Sangrur May 2025 answer 197 (161–233), median 115, avg 122, 86th pct = buildResponse exactly; Punjab Nov 2025 538 vs 5,545 ✓; Hindi/Telugu, follow-up, off-topic decline ✓ (preview); 390 px no h-scroll, console clean. Hard cost cap = Anthropic workspace spend limit (Rocky to set).
- [ ] D6. Alert demo (Telegram/WhatsApp)
- [ ] D7. Open data + data README + API docs
- [x] D8. 2026 data via FIRMS API, labelled provisional. — 1,217,490 detections 1 Jan–14 Nov 2026; SP to Jul/Aug, NRT after (provisional label + grey band); NRT static mask validated. NOAA-21 not used (no training overlap).
- [ ] D9. Daily auto-update (GitHub Actions)

## E. Deployment
- [x] E1. Static export under size limits. — web/ 23 MB total (largest file grid.json 7.9 MB).
- [x] E2. Public repo. — https://github.com/infinitethoughts7/firecalendar (200 without login; .env → 404; no keys in history; 46 MB tracked). Linked from site header + download card.
- [x] E3. Vercel; public URL, no login. — https://firecalendar-ten.vercel.app returns 200 without auth; .env.local / .vercel → 404.
- [x] E4. No API key in repo or browser. — Only FIRMS/Anthropic keys in .env (git-ignored); grep of web/ for key names: none. Re-checked after D5: ANTHROPIC_API_KEY only as encrypted Vercel env var; live page HTML has no "sk-ant"; no key in web/.
- [x] E5. README. — Screenshot, features, method, validation, afternoon-witness finding ("consistent with"), limits, run locally, open API, credits (FIRMS, datameet, OSM, libs), AI use, MIT LICENSE.

## F. Submission (official form fields)
- [x] F1. Team page — https://www.spaceappschallenge.org/2026/find-a-team/swinfy-space/ (team Swinfy Space, challenge attached).
- [x] F2. Project name — Final in docs/SUBMISSION.md §1 (ready to paste).
- [x] F3. High-level summary — Final in docs/SUBMISSION.md §2 (no placeholders; numbers from FINDINGS.md).
- [x] F4. 30-second video with English subtitles — 29.6 s, live screen recording, burned-in subtitles + VTT track, AI voice labelled. Plays without login: https://infinitethoughts7.github.io/firecalendar/demo.html (verified in a fresh browser: plays, 1920×1080).
- [x] F5. ≤7 slides — 7 slides (title, team, members, challenge, app image, user experience, NASA FIRMS). PDF public without login: https://github.com/infinitethoughts7/firecalendar/blob/master/docs/FireCalendar_slides.pdf (checked in a logged-out browser, 15 Nov). The claude.ai deck link needs sign-in, so don't submit that one.
- [x] F6. Final project link. — https://firecalendar-ten.vercel.app and https://github.com/infinitethoughts7/firecalendar, both 200 without login (curl).
- [x] F7. Detailed project description — Final in docs/SUBMISSION.md §5 (all ⟪IF BUILT⟫ features verified live; Ask added; 180/180 parity; OSM not CARTO).
- [x] F8. NASA data section — Final in docs/SUBMISSION.md §6.
- [x] F9. Other data / references — Final in docs/SUBMISSION.md §7 (adds Claude API, ElevenLabs, globe source).
- [x] F10. Use of Super Intelligence (SI) — Final in docs/SUBMISSION.md §8 (Claude Code, Ask FireCalendar, ElevenLabs voice; planning line removed).
- [x] F11. All links tested in a fresh logged-out browser (15 Nov): app 200, repo 200, slides PDF 200 + renders, demo page 200 + video plays; no sign-in walls.
- [x] F12. Submitted for judging 15 Nov 2026 19:26 IST (status "Project Submitted for Judging"; all 4 form sections Complete; 6 NASA + 15 other data links; reloaded page shows full text). Can be edited and resubmitted until 11:59 pm.

## G. After the hackathon
- [ ] G1. Remind Rocky to revisit and learn VIIRS ti4/ti5 brightness temperatures + infrared physics
