"""Download 2026 FIRMS detections (not in the yearly archive yet) via the FIRMS area API.

    .venv/bin/python scripts/fetch_firms_2026.py [India]

Standard-processing (SP) files are used for as long as they exist; near-real-time (NRT, provisional) after that.
Availability comes from /api/data_availability, so re-running later picks up newer SP data and new NRT days.
Writes data/raw_2026/<SOURCE>_<start>.csv (one file per 5-day window, the API maximum). Needs FIRMS_MAP_KEY in .env.
The key is read from .env and never printed.
"""
import os, sys, time, io, urllib.request
import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = f"{ROOT}/data/raw_2026"
API = "https://firms.modaps.eosdis.nasa.gov/api"
BBOX = {"India": "68,6,98,38"}                     # west,south,east,north; trimmed to the country boundary later
PAIRS = [("MODIS_SP", "MODIS_NRT"), ("VIIRS_SNPP_SP", "VIIRS_SNPP_NRT"), ("VIIRS_NOAA20_SP", "VIIRS_NOAA20_NRT")]
START, DAYS = pd.Timestamp("2026-01-01"), 5


def key():
    for line in open(f"{ROOT}/.env"):
        if line.startswith("FIRMS_MAP_KEY="): return line.split("=", 1)[1].strip()
    sys.exit("FIRMS_MAP_KEY missing in .env")


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r: return r.read().decode()
        except Exception as e:
            if i == tries - 1: raise RuntimeError(f"download failed: {type(e).__name__}") from None  # no URL (has the key)
            time.sleep(5 * (i + 1))


def main(country="India"):
    k = key(); os.makedirs(OUT, exist_ok=True)
    av = pd.read_csv(io.StringIO(get(f"{API}/data_availability/csv/{k}/ALL"))).set_index("data_id")
    jobs = []
    for sp, nrt in PAIRS:
        sp_end = pd.Timestamp(av.loc[sp, "max_date"]); nrt_end = pd.Timestamp(av.loc[nrt, "max_date"])
        for src, a, b in [(sp, START, sp_end), (nrt, sp_end + pd.Timedelta(days=1), nrt_end)]:
            d = a
            while d <= b:
                n = min(DAYS, (b - d).days + 1); jobs.append((src, d, n)); d += pd.Timedelta(days=n)
        print(f"{sp}: to {sp_end.date()} | {nrt}: to {nrt_end.date()}")
    t0 = time.time(); got = 0
    for i, (src, d, n) in enumerate(jobs):
        f = f"{OUT}/{src}_{d.date()}_{n}d.csv"
        if os.path.exists(f) and "NRT" not in src: continue           # SP never changes; NRT windows are re-fetched
        txt = get(f"{API}/area/csv/{k}/{src}/{BBOX[country]}/{n}/{d.date()}")
        if not txt.startswith("latitude"): raise RuntimeError(f"{src} {d.date()}: unexpected reply: {txt[:80]}")
        open(f, "w").write(txt); got += 1
        if i % 20 == 0: print(f"{i+1}/{len(jobs)} {src} {d.date()} {time.time()-t0:.0f}s", flush=True)
    print(f"done: {got} files fetched, {len(jobs)} windows, {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main(*(sys.argv[1:] or ["India"]))
