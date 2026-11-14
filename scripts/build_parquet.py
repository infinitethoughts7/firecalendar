"""Unify all FIRMS country CSVs (MODIS + VIIRS) into one Parquet file with a common schema."""
import glob, os, polars as pl

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW, OUT = f"{ROOT}/data/raw", f"{ROOT}/data/processed/fires_india.parquet"

def load(path):
    sensor = os.path.basename(path).split("_")[0]          # modis | viirs-snpp | viirs-jpss1
    df = pl.scan_csv(path, infer_schema_length=0)           # lazy; read all as string, cast explicitly
    cols = df.collect_schema().names()
    bright = "brightness" if "brightness" in cols else "bright_ti4"
    bright2 = "bright_t31" if "bright_t31" in cols else "bright_ti5"
    return df.select(
        pl.col("latitude").cast(pl.Float32).alias("lat"),
        pl.col("longitude").cast(pl.Float32).alias("lon"),
        pl.col("acq_date").str.to_date().alias("date"),
        pl.col("acq_time").str.zfill(4).alias("time_utc"),
        pl.lit(sensor).alias("sensor"),
        pl.col("satellite"),
        pl.col("confidence").alias("confidence_raw"),
        pl.col(bright).cast(pl.Float32).alias("bright_k"),
        pl.col(bright2).cast(pl.Float32).alias("bright2_k"),
        pl.col("scan").cast(pl.Float32), pl.col("track").cast(pl.Float32),
        pl.col("frp").cast(pl.Float32),
        pl.col("daynight"),
        pl.col("type").cast(pl.Int8),
    )

def conf(df):
    # Normalised confidence class: MODIS 0-100 -> low<30, nominal 30-79, high>=80 (FIRMS convention); VIIRS l/n/h
    df = df.with_columns(
    pl.when(pl.col("sensor") == "modis").then(
        pl.when(pl.col("confidence_raw").cast(pl.Int32, strict=False) < 30).then(pl.lit("low"))
          .when(pl.col("confidence_raw").cast(pl.Int32, strict=False) < 80).then(pl.lit("nominal")).otherwise(pl.lit("high")))
      .otherwise(pl.col("confidence_raw").replace({"l": "low", "n": "nominal", "h": "high"}))
      .alias("conf_class"))
    return df

PARTS = f"{ROOT}/data/processed/parts"; os.makedirs(PARTS, exist_ok=True)
for p in sorted(glob.glob(f"{RAW}/*_India.csv")):
    dest = f"{PARTS}/{os.path.basename(p)[:-4]}.parquet"
    if not os.path.exists(dest):
        conf(load(p)).sink_parquet(dest, compression="zstd")
pl.scan_parquet(f"{PARTS}/*.parquet").sink_parquet(OUT, compression="zstd")
n = pl.scan_parquet(OUT).select(pl.len()).collect().item()
print(f"{n:,} rows", f"{os.path.getsize(OUT)/1e6:.0f} MB")
