"""Raw hotspot points for the static site, split into 1 deg tile x year gzipped CSVs (hosted on GitHub Pages,
because the points (~106 MB gz) don't fit Vercel Hobby's 100 MB upload limit next to the rest of the site).

    .venv/bin/python -m firecal.export_points India        # -> pages/points/<country>/

Writes pages/points/<country>/<year>/<lat>_<lon>.csv.gz (lat/lon = floor of the tile's south-west corner) and
index.json {"tiles": {"<year>/<lat>_<lon>": n_points}, ...}. Same filter as every count in the app:
vegetation fires (type 0), low confidence removed -> point counts match the raw counts in the monthly CSV.
"""
import gzip, json, os, shutil, sys, time
import polars as pl
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

COLS = ["lat", "lon", "date", "time_utc", "satellite", "sensor", "conf_class", "frp_mw"]


def main(country="India"):
    k = country.lower(); out = f"{ROOT}/pages/points/{k}"; t0 = time.time()
    files = [f for f in [f"{ROOT}/data/processed/fires_{k}.parquet", f"{ROOT}/data/processed/fires_{k}_2026.parquet"] if os.path.exists(f)]
    df = (pl.scan_parquet(files).filter((pl.col("type") == 0) & (pl.col("conf_class") != "low"))
          .select(pl.col("lat").round(4), pl.col("lon").round(4), pl.col("date").cast(pl.Utf8), "time_utc", "satellite",
                  "sensor", "conf_class", pl.col("frp").round(1).alias("frp_mw"))
          .sort(["date", "time_utc"]).collect()
          .with_columns(ty=pl.col("lat").floor().cast(pl.Int32), tx=pl.col("lon").floor().cast(pl.Int32),
                        yr=pl.col("date").str.slice(0, 4)))
    shutil.rmtree(out, ignore_errors=True)
    tiles, size = {}, 0
    for (ty, tx, yr), g in df.group_by(["ty", "tx", "yr"]):
        os.makedirs(f"{out}/{yr}", exist_ok=True)
        b = gzip.compress(g.select(COLS).write_csv().encode(), 9, mtime=0)
        open(f"{out}/{yr}/{ty}_{tx}.csv.gz", "wb").write(b)
        tiles[f"{yr}/{ty}_{tx}"] = len(g); size += len(b)
    json.dump(dict(country=country, tile_deg=1, columns=COLS, n_points=len(df), date_min=df["date"].min(),
                   date_max=df["date"].max(), filter="type=0 (vegetation), conf_class != low",
                   tiles=dict(sorted(tiles.items()))), open(f"{out}/index.json", "w"), separators=(",", ":"))
    print(f"{len(df):,} points, {len(tiles)} files, {size/1e6:.1f} MB, {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main(*(sys.argv[1:] or ["India"]))
