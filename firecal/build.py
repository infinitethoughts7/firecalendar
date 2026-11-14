"""Precompute translation factors + their validated error for one country.
Output: data/processed/factors_<country>.parquet and errors_<country>.json"""
import duckdb, json, os, sys, numpy as np, pandas as pd
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CELL, K = 0.5, 20
STABLE_END = 2021                      # MODIS orbits stable through 2021 (Terra/Aqua drift visible from 2022 in our data)

def cell_month(fires):
    c = duckdb.connect(); c.execute("SET memory_limit='2GB'")
    return c.sql(f"""SELECT floor(lat/{CELL})*{CELL} cy, floor(lon/{CELL})*{CELL} cx, year(date) yr, month(date) mo,
      sum((satellite='Terra')::INT) terra, sum((satellite='Aqua')::INT) aqua,
      sum((sensor='viirs-snpp')::INT) snpp, sum((sensor='viirs-jpss1')::INT) n20
      FROM '{fires}' WHERE type=0 AND conf_class<>'low' GROUP BY ALL""").df()

def shrunk(train, num, den):
    """ratio num/den per cell x month, shrunk toward the per-month ratio (pseudo-count K)."""
    nat = train[num].sum() / train[den].sum()
    m = train.groupby("mo")[[num, den]].sum(); r_mo = (m[num] / m[den]).fillna(nat).rename("r_mo").reset_index()
    g = train.groupby(["cy", "cx", "mo"])[[num, den]].sum().reset_index().merge(r_mo, on="mo")
    g["f"] = (g[num] + K * g.r_mo) / (g[den] + K)
    return nat, r_mo, g[["cy", "cx", "mo", "f"]]

def apply(test, den, nat, r_mo, g):
    t = test.merge(r_mo, on="mo", how="left").merge(g, on=["cy", "cx", "mo"], how="left")
    t["f"] = t.f.fillna(t.r_mo).fillna(nat)
    return t[den] * t.f

def loyo(d, num, den, years):
    """leave-one-year-out; returns relative errors at 2-degree block-month and yearly-total level."""
    out = []
    for y in years:
        tr, te = d[d.yr != y], d[d.yr == y].copy()
        te["pred"] = apply(te, den, *shrunk(tr, num, den)).values
        out.append(te)
    P = pd.concat(out); P["truth"] = P[num]
    B = P.assign(by=(P.cy // 2) * 2, bx=(P.cx // 2) * 2).groupby(["by", "bx", "yr", "mo"])[["truth", "pred"]].sum()
    B = B[B.truth >= 20]                                   # blocks with meaningful activity
    rel_block = float(np.median(np.abs(B.pred - B.truth) / B.truth))
    Y = P.groupby("yr")[["truth", "pred"]].sum(); yb = (Y.pred - Y.truth) / Y.truth
    ss = ((B.truth - B.truth.mean()) ** 2).sum()
    r2 = float(1 - ((B.truth - B.pred) ** 2).sum() / ss)
    return dict(block_month_median_rel_err=rel_block, yearly_bias_rms=float(np.sqrt((yb ** 2).mean())),
                yearly_bias=dict(zip(map(int, yb.index), yb.round(4))), block_month_R2=r2)

def build(country):
    fires = f"{ROOT}/data/processed/fires_{country.lower()}.parquet"
    cm = cell_month(fires); cm["modis"] = cm.terra + cm.aqua
    def first(col):
        ym = (cm[cm[col] > 0].yr * 100 + cm[cm[col] > 0].mo).min()
        y, m = divmod(int(ym), 100)
        return [y, m + 1] if m < 12 else [y + 1, 1]       # skip the partial first month
    starts = {s: first(s) for s in ["terra", "aqua", "snpp", "n20"]}
    after = lambda d, ym: d[(d.yr > ym[0]) | ((d.yr == ym[0]) & (d.mo >= ym[1]))]
    # Terra-only -> Terra+Aqua equivalent: train on full-Aqua years up to STABLE_END
    dta = after(cm, [starts["aqua"][0] + 1, 1]); dta = dta[dta.yr <= STABLE_END]
    dta = dta[(dta.modis > 0)]
    # VIIRS -> MODIS equivalent: train on overlap up to STABLE_END
    ds = after(cm, starts["snpp"]); ds = ds[(ds.yr <= STABLE_END) & ((ds.modis > 0) | (ds.snpp > 0))]
    dn = after(cm, starts["n20"])
    dn = dn[(dn.yr <= STABLE_END) & ((dn.modis > 0) | (dn.n20 > 0))]
    facs, errs = [], {"starts": {k: [int(v[0]), int(v[1])] for k, v in starts.items()}, "stable_end": STABLE_END, "cell_deg": CELL}
    for name, d, num, den in [("terra", dta, "modis", "terra"), ("snpp", ds, "modis", "snpp"), ("n20", dn, "modis", "n20")]:
        nat, r_mo, g = shrunk(d, num, den)
        g["src"] = name; facs.append(g)
        errs[name] = dict(national=float(nat), **loyo(d, num, den, sorted(d.yr.unique())))
        r_mo.assign(src=name).to_parquet(f"{ROOT}/data/processed/monthratio_{name}_{country.lower()}.parquet", index=False)
    pd.concat(facs).to_parquet(f"{ROOT}/data/processed/factors_{country.lower()}.parquet", index=False)
    json.dump(errs, open(f"{ROOT}/data/processed/errors_{country.lower()}.json", "w"), indent=1)
    return errs

if __name__ == "__main__":
    e = build(sys.argv[1] if len(sys.argv) > 1 else "India")
    for k in ["terra", "snpp", "n20"]:
        v = e[k]; print(f"{k:6s} national={v['national']:.3f}  block-month R2={v['block_month_R2']:.3f}  median rel err={v['block_month_median_rel_err']*100:.1f}%  yearly bias rms={v['yearly_bias_rms']*100:.1f}%")
    print("starts", e["starts"])
