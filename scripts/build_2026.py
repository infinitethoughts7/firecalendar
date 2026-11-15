"""2026 detections (data/raw_2026, from fetch_firms_2026.py) -> data/processed/fires_<country>_2026.parquet, same schema
as fires_<country>.parquet, plus data/processed/fires_<country>_2026.json (provisional-from dates, mask check).

    .venv/bin/python scripts/build_2026.py [India]

- Only points inside the country boundary (box query -> point-in-polygon).
- Standard-processing (SP) rows keep FIRMS' `type` column.
- Near-real-time (NRT) rows have no `type` column, so static sources (industry, gas flares, volcanoes) can't be
  removed directly. We mark an NRT point as type 2 if it falls in a ~550 m (0.005 deg) cell where FIRMS flagged
  >= 10 non-vegetation detections in 2000-2025 (persistent industry / gas flares). Chosen on 2026 SP rows, which do
  have `type` (Jan-Jul 2026, kept detections): catches 95% of static sources, wrongly drops 1.3% of vegetation
  fires, lets 0.6% static through -> NRT counts ~0.7% low, far inside the +/-16-18% band.
"""
import glob, json, os, sys
import numpy as np, pandas as pd, polars as pl, shapely
from shapely.geometry import shape

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW, P = f"{ROOT}/data/raw_2026", f"{ROOT}/data/processed"
SENSOR = {"MODIS": "modis", "VIIRS_SNPP": "viirs-snpp", "VIIRS_NOAA20": "viirs-jpss1"}
G, MIN_STATIC = 0.005, 10


def load(f):
    name = os.path.basename(f); src = name.split("_20")[0]           # e.g. VIIRS_NOAA20_NRT
    df = pd.read_csv(f, dtype=str)
    if df.empty: return None
    nrt = src.endswith("_NRT"); sensor = SENSOR[src.rsplit("_", 1)[0]]
    b1 = "brightness" if "brightness" in df else "bright_ti4"; b2 = "bright_t31" if "bright_t31" in df else "bright_ti5"
    out = pd.DataFrame(dict(
        lat=df.latitude.astype("float32"), lon=df.longitude.astype("float32"), date=pd.to_datetime(df.acq_date).dt.date,
        time_utc=df.acq_time.str.zfill(4), sensor=sensor, satellite=df.satellite, confidence_raw=df.confidence,
        bright_k=df[b1].astype("float32"), bright2_k=df[b2].astype("float32"), scan=df.scan.astype("float32"),
        track=df.track.astype("float32"), frp=df.frp.astype("float32"), daynight=df.daynight,
        type=df["type"].astype("int8") if "type" in df else pd.Series(-1, index=df.index, dtype="int8")))
    out["nrt"] = nrt
    return out


def conf_class(df):
    m = df.sensor == "modis"; c = pd.to_numeric(df.confidence_raw, errors="coerce")
    cls = df.confidence_raw.map({"l": "low", "n": "nominal", "h": "high"})
    cls[m] = np.where(c[m] < 30, "low", np.where(c[m] < 80, "nominal", "high"))
    return cls


def keys(lat, lon):
    return (np.floor(np.asarray(lat) / G).astype(np.int64) * 1000000 + np.floor(np.asarray(lon) / G).astype(np.int64))


def main(country="India"):
    k = country.lower()
    df = pd.concat([x for x in map(load, sorted(glob.glob(f"{RAW}/*.csv"))) if x is not None], ignore_index=True)
    n0 = len(df)
    # SP and NRT windows never overlap by date per sensor, but drop exact duplicates just in case
    df = df.drop_duplicates(["lat", "lon", "date", "time_utc", "satellite"])
    geoms = [shape(f["geometry"]) for f in json.load(open(f"{ROOT}/data/boundaries/{k}_states_calc.geojson"))["features"]]
    border = shapely.union_all(geoms); shapely.prepare(border)
    df = df[shapely.contains_xy(border, df.lon.values, df.lat.values)].reset_index(drop=True)
    n_in = len(df)

    # static-source mask from the 2000-2025 archive (type 1/2/3)
    hist = pl.scan_parquet(f"{P}/fires_{k}.parquet").filter(pl.col("type") != 0).select("lat", "lon").collect().to_pandas()
    cnt = pd.Series(keys(hist.lat, hist.lon)).value_counts()
    in_mask = np.isin(keys(df.lat, df.lon), cnt[cnt >= MIN_STATIC].index.values)

    # check the mask on SP rows, which carry the real type
    sp = ~df.nrt.values & (conf_class(df).values != "low")          # detections we would keep
    real_static = sp & (df.type.values != 0)
    check = dict(sp_rows=int(sp.sum()), sp_static_by_type=int(real_static.sum()),
                 caught_by_mask=int((real_static & in_mask).sum()),
                 veg_wrongly_masked=int((sp & (df.type.values == 0) & in_mask).sum()))
    check["recall"] = round(check["caught_by_mask"] / max(check["sp_static_by_type"], 1), 3)
    check["veg_loss_share"] = round(check["veg_wrongly_masked"] / max(int((sp & (df.type.values == 0)).sum()), 1), 4)

    nrt = df.nrt.values
    df.loc[nrt, "type"] = np.where(in_mask[nrt], 2, 0).astype("int8")
    df["conf_class"] = conf_class(df)
    prov = {s: str(df.loc[nrt & (df.sensor == s), "date"].min()) for s in SENSOR.values() if (nrt & (df.sensor == s)).any()}
    out = df.drop(columns="nrt")
    pl.from_pandas(out).write_parquet(f"{P}/fires_{k}_2026.parquet", compression="zstd")
    info = dict(rows_downloaded=n0, rows_in_country=n_in, rows=len(out), date_min=str(out.date.min()),
                date_max=str(out.date.max()), provisional_from=prov, nrt_static_mask=check,
                note="NRT rows have no FIRMS type; static sources masked: 0.005 deg cells with >=10 type!=0 detections in 2000-2025.")
    json.dump(info, open(f"{P}/fires_{k}_2026.json", "w"), indent=1)
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main(*(sys.argv[1:] or ["India"]))
