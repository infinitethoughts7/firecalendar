# FireCalendar — findings log (for slides, video, README, submission text)

Every number here was computed from our data (NASA FIRMS standard-processing archive, India, 2000-11 → 2025-12)
unless marked otherwise. Counts are **MODIS-equivalent fire detections** (flagged pixels per pass, not fires on the
ground), vegetation fires only (`type=0`), low-confidence removed. "Normal" = median of the same month in other years
since 2003. Update this file whenever a new finding is made; note the date and how it was checked.

Claim-strength labels: **[verified]** computed and cross-checked · **[consistent with]** pattern fits an outside
report, not proof · **[hypothesis]** plausible explanation, not yet checked against a source — don't put on a slide
as fact.

---

## A. Headline story — "Punjab says farm fires fell 80%. Did they?"

1. **Punjab, Oct+Nov stubble season: the drop is real, but its size depends on *when* the satellite looks.** [verified, 15 Nov]
   | Oct+Nov, Punjab state | 2021 | 2023 | 2024 | 2025 | 2021→2025 |
   |---|---|---|---|---|---|
   | S-NPP VIIRS raw (passes ~13:30) | 74,434 | 30,078 | 8,502 | 3,859 | **−95%** |
   | Aqua MODIS raw (pass drifted to ~15:15 IST in 2025) | 15,713 | 8,158 | 3,748 | 2,949 | **−81%** |
   | FireCalendar harmonized (MODIS-eq.) | 17,191 | 6,716 | 1,990 | 871 | −95% |
   The later-afternoon satellite sees a much smaller decline. Burning clearly fell a lot, but early-afternoon sensors
   overstate the fall.
2. **Blind-spot signal, Punjab state, Oct–Nov daytime:** Aqua detections per S-NPP detection, relative to the
   2012–19 normal: 1.07× (2021) → 1.13× (2022) → **1.38× (2023, Aqua ~14:07 IST) → 2.28× (2024, ~14:37) → 3.98×
   (2025, ~15:15)**. [verified, 15 Nov]
   - Earlier analysis on the Punjab–Haryana region (CLAUDE.md §3; `data/processed/aqua_witness_test.csv`): 1.38× / 2.10× / 3.30×
     for 2023/24/25, with **no rise in a control region** (central India Mar–May: 0.68–1.20×). [verified, 14 Nov]
   - **Sangrur district** (Punjab), same test: 1.34× (2023) → 2.64× (2024) → **6.15× (2025)**; Aqua pass 15:15 IST in 2025.
     S-NPP Oct–Nov detections there: 8,738 (2021) → 457 (2025). [verified, 15 Nov]
   - Framing: **consistent with** ISRO SAC (Current Science, Nov 2025) and iFOREST (Dec 2025) reports that farmers shifted
     burning to late afternoon (~17:00) to avoid satellite passes. Say "consistent with", not "proves".
2b. **NEW 2026 (provisional NRT data for Oct–Nov): the afternoon witness now sees MORE fires than VIIRS.** Punjab,
   1 Oct–14 Nov daytime, like-for-like every year: Aqua vs NOAA-20 VIIRS (~13:30 pass, same orbit as S-NPP) [verified, 15 Nov;
   interpretation = consistent with]
   | Punjab | Aqua pass IST | Aqua | NOAA-20 | Aqua/NOAA-20 vs 2018–21 normal |
   |---|---|---|---|---|
   | 2021 | ~13:50 | 14,106 | 67,393 | 1.03× |
   | 2024 | ~14:35 | 2,462 | 6,692 | 1.81× |
   | 2025 | ~15:15 | 2,825 | 3,576 | 3.89× |
   | **2026** | **~15:50** | **5,196** | **3,806** | **6.72×** |
   - Aqua (1 km pixels) counted more fires than NOAA-20 (375 m), which normally sees ~5× more. Aqua's count rose 84% vs
     2025 while NOAA-20 was flat (+6%). Sangrur: 13.7× normal (Aqua 810 vs NOAA-20 332).
   - Harmonized Punjab Oct 1–Nov 14: 15,521 (2021) → 1,352 (2024) → 801 (2025) → 841 (2026): the VIIRS-based count
     has stopped falling, and the later the witness looks, the more it sees.
   - Caveats: 2026 Oct–Nov = FIRMS near-real-time (provisional); fires naturally peak in the afternoon, so part of the
     rise is the diurnal cycle — which is exactly why a 13:30-only count undercounts if burning moved later.
   - App blind-spot ratio (Aqua/S-NPP, only days S-NPP flew, to 2 Nov 2026): Punjab 3.68× (2026), Sangrur 7.66×.
   - Bug caught before release: S-NPP stopped 2 Nov 2026, so an Aqua/S-NPP ratio over all of Nov gave fake 19×/80×.
     Fixed: blind-spot test uses only days both satellites flew.
3. **Anomaly calls the app makes** (what a user would see): [verified, 15 Nov]
   - Punjab, Nov 2024: 1,443 vs normal 5,697 → "much lower than usual" (lower than ~90% of past Novembers), **with the
     blind-spot warning attached**.
   - Sangrur, Nov 2024: 239 vs normal 870 → "much lower than usual" (lowest on record), blind-spot warning attached.

## B. Why harmonization is needed (the challenge's core problem)

4. **VIIRS reports ~5.5× more detections than MODIS** (375 m vs ~1 km pixels; sees smaller fires). The ratio varies by
   region (3.6× NE India … 7.8× central India) and month (4.2–8.8×), so **one multiplier is wrong**. [verified, 14 Nov]
5. **Our per-0.5°-cell × month translator halves the error** of a single national multiplier (S-NPP block-month MAE
   12.8 vs 25.7). [verified, 14 Nov, `scripts/harmonize.py`]
6. **Validation, leave-one-year-out** (`data/processed/errors_india.json`): [verified, 14 Nov]
   | Translator | R² (≈200 km block, monthly) | Median monthly rel. error | Yearly bias RMS |
   |---|---|---|---|
   | S-NPP → MODIS-eq | 0.978 | 16.3% | 5.6% |
   | NOAA-20 → MODIS-eq | 0.985 | 18.1% | 3.5% |
   | Terra-only → Terra+Aqua | 0.801 | 24.5% | 9.2% |
7. **MODIS is no longer a stable ruler after 2021 — orbit drift.** Median day-pass over India: Terra ~11:00 IST until
   2021 → 10:02 (2025); Aqua ~13:30 → 14:35 (2025). So from 2022 we use VIIRS translated into MODIS units. [verified, 14 Nov]
8. **MODIS has a break in 2002:** Terra only until Aqua data begin (Jul 2002; first full month Aug 2002). We scale
   Terra-only months with a learned Terra→Terra+Aqua factor. [verified, 14 Nov]
9. **S-NPP fire data production ceased 2 Nov 2026 15:40 UTC** (FIRMS FAQ); NOAA-20/21 continue. Our method already
   averages S-NPP and NOAA-20, so it survives the loss of S-NPP. [source: FIRMS FAQ]

## C. Fire-season clock (new, 15 Nov)

Method: seasons found from the 2003–21 monthly normal; per season-year, start = date 10% of that season's fires were
seen, end = 90%, peak = busiest 15 days; trend = Theil–Sen slope of the start date with Sen's 95% interval.

10. **Some areas have two burning seasons, and treating them as one gives wrong answers.** Punjab: Oct–Nov (rice
    stubble) = 82% of fires, Apr–May (wheat) = 16%. Sangrur: 92% / 8%. A single "fire year" would smear Oct→May and, once
    Oct–Nov fires collapsed, mis-place Punjab's 2024 peak in April. [verified, 15 Nov]
11. **Punjab's Oct–Nov season is starting later: +8.3 days per decade** (95% range +6.0 to +10.0; 2003–2025). Typical
    season: starts ~19 Oct, peaks ~2 Nov, 90% done by ~12 Nov. Holds in MODIS-measured years only (2003–21: +10.0, 95%
    range +7.5 to +12.0), so it's **not an artefact of switching to VIIRS**. [verified, 15 Nov]
    - Possible cause [hypothesis — check source before using]: Punjab's 2009 groundwater law delaying rice transplanting
      → later harvest → later burning.
12. **Odisha's Feb–May season is starting earlier: −16.7 days per decade** (95% range −21.8 to −10.8; 2003–2025). Typical:
    starts ~25 Feb, peaks ~24 Mar, 90% done by ~4 May. MODIS-only 2003–21: −16.7 (−22.0 to −10.0). [verified, 15 Nov]
13. Stable seasons (good controls): Mizoram Mar–Apr, 0.0 days/decade (−2.9 to +3.8), typical 5 Mar → 15 Mar → 2 Apr;
    Khammam (Telangana) Jan–May, −4.4 (−12.0 to +3.3) = no clear shift. [verified, 15 Nov]
14. **4-week outlook (history, not a forecast)**, e.g. Punjab from 15 Nov: week of 15–21 Nov typically 628 fires (8 in 10
    years between 24 and 1,378; last-5-years median 869), dropping to ~16–42 per week by early December. [verified, 15 Nov]

## D. Other area facts (useful in the demo)

15. Telangana, Mar 2025: 1,208 vs normal 688 → "much higher than usual". Khammam, Mar 2025: 326 vs normal 199 (1.6×,
    higher than 86% of past Marches). [verified, 15 Nov]
16. Punjab's biggest month of 2025 was **May** (wheat, 2,658 vs normal 2,214), not Oct/Nov, because Oct–Nov detections
    fell so far. [verified, 15 Nov]
17. First VIIRS 2024 row in the file (17.17N, 79.99E) is in Khammam district, Telangana (~161 km from Hyderabad). [verified, 14 Nov]

## E. Quality work (for the "Validity" criterion and the README)

18. Tested in a real browser at desktop and phone widths: states, districts, drawn polygon, month/year selectors,
    calendar click, CSV download, console clean. [15 Nov]
19. Data issues found and fixed: 13 district names repeat across states (Aurangabad, Bilaspur, Hamirpur, Bijapur,
    Pratapgarh, Raigarh, Delhi's North/South/East/West…) → search matches "district, state"; sparse areas had their time
    series cut at their last fire (gave blank months instead of zero) → every area now runs to the dataset end; calendar
    colour scale used raw counts instead of log → fixed. [15 Nov]
20. Daily series checked against monthly: identical to floating-point precision (max diff ~1e-13). Theil–Sen
    implementation checked on a known line (slope 2.0 exactly). [15 Nov]
21. Public-server hardening: drawn areas are capped (≤2,000 vertices, ≤40 sq° area, ≤60 sq° bounding box, must overlap
    the country); only small aggregates are cached. [15 Nov]
22. **Static site == live API:** browser data layer reproduces `/api/query` for 200 of 200 random area/month cases
    (`test/compare_static.js`). Drawn areas use 0.5° cells: cell-aligned shapes match exactly; other shapes within ~5–8%,
    same anomaly labels. [verified, 15 Nov]
23. **Live, no login:** https://firecalendar-ten.vercel.app (Vercel, static, 22 MB). Tested 15 Nov: Sangrur, Odisha,
    month selector, drawn area (4 cells), CSV (303 rows), 390 px phone width, console clean. [verified, 15 Nov]

24. **MODIS confidence classes verified** against NASA's MODIS C6/C6.1 Active Fire User Guide v1.0, §8.4.3 Table 11:
    low 0–<30%, nominal 30–<80%, high 80–100% (= our code). §8.4.2 recommends nominal+high for fewer false alarms. [verified, 15 Nov]
25. **Spot-check vs raw data:** independent DuckDB+shapely count from the parquet == live site, per satellite, for Sangrur
    Nov 2015, Khammam Mar 2010, Odisha Mar 2019, Punjab Nov 2024 (4/4 exact). [verified, 15 Nov]
26. **2026 data added** (FIRMS area API): 1,217,490 detections in India, 1 Jan–14 Nov 2026. Standard processing to Jul
    (MODIS to Aug); near-real-time after (labelled provisional). NRT has no `type` field → static sources masked by
    location (0.005° cells with ≥10 non-vegetation detections 2000–25). Tested on Jan–Jul 2026 SP rows that have `type`:
    catches 95.4% of static detections, wrongly drops 1.3% of vegetation fires, 0.6% static leak → NRT ~0.7% low,
    far inside the ±16–18% band. [verified, 15 Nov]

## F. Honest limitations (say these before a judge does)

- A "fire count" is pixels flagged per satellite pass, not individual fires; we never add sensors together.
- From 2022, values are VIIRS translated into MODIS units, with an uncertainty band (±16–18% monthly, ±3.5–5.6% yearly).
- The blind-spot result is **evidence consistent with** late-afternoon burning, not proof; cloud, smoke and pass geometry also matter.
- 2026 from Aug (VIIRS) / Sep (MODIS) is near-real-time, provisional; Nov 2026 is an unfinished month. The outlook is climatology, not a forecast.
