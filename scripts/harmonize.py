"""Step 1 of FireCalendar: build cell-month counts per satellite, fit VIIRS->MODIS-equivalent
translators, and validate them with leave-one-year-out cross-validation."""
import duckdb, numpy as np, pandas as pd, os
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CELL = 0.5                      # degrees (~55 km)
K = 20                          # shrinkage strength (pseudo-count of VIIRS rows) toward the parent ratio
c = duckdb.connect(); c.execute("SET memory_limit='2GB'")

# 1) cell-month counts per sensor group (vegetation fires, low confidence removed)
cm = c.sql(f"""
SELECT floor(lat/{CELL})*{CELL} AS cy, floor(lon/{CELL})*{CELL} AS cx,
       year(date) AS yr, month(date) AS mo,
       sum((sensor='modis')::INT)        AS modis,
       sum((satellite='Terra')::INT)     AS terra,
       sum((satellite='Aqua')::INT)      AS aqua,
       sum((sensor='viirs-snpp')::INT)   AS snpp,
       sum((sensor='viirs-jpss1')::INT)  AS n20,
       sum(CASE WHEN sensor='modis' THEN frp END)       AS frp_modis,
       sum(CASE WHEN sensor='viirs-snpp' THEN frp END)  AS frp_snpp
FROM '{ROOT}/data/processed/fires_india.parquet'
WHERE type=0 AND conf_class<>'low'
GROUP BY ALL""").df()
cm.to_parquet(f"{ROOT}/data/processed/cell_month_counts.parquet", index=False)
print(f"cell-month rows: {len(cm):,}  cells: {cm[['cy','cx']].drop_duplicates().shape[0]:,}")

def fit_ratios(train, src):
    """Return ratio lookups: national, per-month, per cell x month (shrunk toward per-month)."""
    nat = train.modis.sum() / train[src].sum()
    m = train.groupby("mo")[["modis", src]].sum(); r_mo = (m.modis / m[src]).rename("r_mo")
    cmm = train.groupby(["cy", "cx", "mo"])[["modis", src]].sum().reset_index().merge(r_mo, on="mo")
    cmm["r_cell"] = (cmm.modis + K * cmm.r_mo) / (cmm[src] + K)   # Bayesian-style shrinkage
    return nat, r_mo, cmm[["cy", "cx", "mo", "r_cell"]]

def predict(test, src, nat, r_mo, r_cell):
    t = test.merge(r_mo, on="mo", how="left").merge(r_cell, on=["cy", "cx", "mo"], how="left")
    t["r_mo"] = t.r_mo.fillna(nat); t["r_cell"] = t.r_cell.fillna(t.r_mo)
    t["p_nat"] = t[src] * nat; t["p_mo"] = t[src] * t.r_mo; t["p_cell"] = t[src] * t.r_cell
    return t

def metrics(t, col):
    y, p = t.modis.values, t[col].values
    ss = ((y - y.mean())**2).sum()
    return dict(R2=1 - ((y - p)**2).sum() / ss, MAE=np.abs(y - p).mean(), bias_pct=100 * (p.sum() - y.sum()) / y.sum())

rows = []
for src, years in [("snpp", range(2013, 2026)), ("n20", range(2019, 2026))]:
    # only months when this VIIRS satellite was actually operating (S-NPP from 2012-01-20, NOAA-20 from 2018-04-01)
    sy, sm = (2012, 2) if src == "snpp" else (2018, 4)
    d = cm[((cm.yr > sy) | ((cm.yr == sy) & (cm.mo >= sm))) & (cm.yr <= 2025)].copy()
    d = d[(d.modis > 0) | (d[src] > 0)]
    preds = []
    for y in years:                                    # leave-one-year-out
        tr, te = d[d.yr != y], d[d.yr == y]
        preds.append(predict(te, src, *fit_ratios(tr, src)))
    P = pd.concat(preds)
    P.to_parquet(f"{ROOT}/data/processed/loyo_predictions_{src}.parquet", index=False)
    for level, g in [("cell-month", P),
                     ("state-ish 2° block-month", P.assign(by=(P.cy//2)*2, bx=(P.cx//2)*2).groupby(["by","bx","yr","mo"])[["modis","p_nat","p_mo","p_cell"]].sum()),
                     ("India-month", P.groupby(["yr","mo"])[["modis","p_nat","p_mo","p_cell"]].sum())]:
        for col, name in [("p_nat","1 number for India"),("p_mo","1 number per month"),("p_cell","per cell x month (shrunk)")]:
            rows.append(dict(viirs=src, level=level, translator=name, **metrics(g, col)))
    yb = P.groupby("yr")[["modis","p_cell"]].sum(); yb["bias_pct"] = 100*(yb.p_cell-yb.modis)/yb.modis
    print(f"\n[{src}] held-out-year bias of best translator (%):", yb.bias_pct.round(1).to_dict())
res = pd.DataFrame(rows)
res.to_csv(f"{ROOT}/data/processed/validation_metrics.csv", index=False)
pd.set_option("display.width", 200)
print(res.round({"R2":3,"MAE":1,"bias_pct":1}).to_string(index=False))
