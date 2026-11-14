"""Build the static site data (no server needed in production).

    .venv/bin/python -m firecal.export_static India            # all states + districts (~15-25 min)
    .venv/bin/python -m firecal.export_static India --only state-8,district-499

Writes web/data/:
  meta.json                                  sensors, validation, data-through date, countries
  <country>/areas.json                       id, name, state, kind for search
  <country>/areas/<id>.json                  monthly series (columnar), blind-spot, season clock, outlook table
  <country>/grid.json                        0.5 deg cell x month counts + MODIS-eq sums, for drawn areas (approximate)
  <country>/boundaries_{state,district}.geojson
The browser rebuilds calendar, anomaly, yearly totals and CSV from these (web/index.html, buildResponse()).
"""
import json, os, shutil, sys, time
import numpy as np, pandas as pd
from firecal.app import compute, SHAPES, ENG, clean, ROOT
from firecal.engine import outlook_table

OUT = f"{ROOT}/web/data"
METHOD_CODE = {"terra-adjusted": "t", "modis-measured": "m", "viirs-translated": "v"}


def r1(a, nd=1):
    return [None if (x is None or not np.isfinite(x)) else round(float(x), nd) for x in a]


def area_json(country, aid):
    g, p = SHAPES[aid]
    m, n_points, blind, v, seas = compute(country, aid, g.wkb)
    return clean(dict(
        id=aid, name=p["name"], state=p["state"], kind=p["kind"], country=country, n_points=n_points,
        monthly=dict(start=m.index[0].strftime("%Y-%m"), value=r1(m.value, 3), method="".join(METHOD_CODE[x] for x in m.method),
                     terra=m.terra.astype(int).tolist(), aqua=m.aqua.astype(int).tolist(),
                     snpp=m.snpp.astype(int).tolist(), n20=m.n20.astype(int).tolist(), viirs_eq=r1(m.viirs_eq, 3)),   # 3 dp: anomaly ties match the API
        blind_spot=blind, season=seas, outlook_table=outlook_table(v)))


def grid_json(country):
    """per 0.5 deg cell x month: raw counts per satellite, MODIS-eq sums, daytime Aqua/S-NPP counts (blind-spot test)."""
    E = ENG[country]; c = E.cell
    ist = "((CAST(substr(time_utc,1,2) AS INT)*60 + CAST(substr(time_utc,3,2) AS INT) + 330) / 60.0) % 24"
    df = E.db.execute(f"""
        SELECT floor(lat/{c})*{c} AS cy, floor(lon/{c})*{c} AS cx, year(CAST(date AS DATE)) AS yr, month(CAST(date AS DATE)) AS mo,
               satellite, count(*) AS n,
               count(*) FILTER (WHERE {ist} > 8 AND {ist} < 20) AS nd,
               sum({ist}) FILTER (WHERE {ist} > 8 AND {ist} < 20) AS ist_sum
        FROM {E.fires} WHERE type=0 AND conf_class<>'low' GROUP BY ALL""").df()
    w = df.pivot_table(index=["cy", "cx", "yr", "mo"], columns="satellite", values="n", aggfunc="sum", fill_value=0)
    w = w.rename(columns={"Terra": "terra", "Aqua": "aqua", "N": "snpp", "N20": "n20"}).reset_index()
    for col in ["terra", "aqua", "snpp", "n20"]:
        if col not in w: w[col] = 0
    for src in ["terra", "snpp", "n20"]:                       # same factor fallback chain as Engine._weights
        f = w[["cy", "cx", "mo"]].merge(E.fac[src], on=["cy", "cx", "mo"], how="left").merge(E.mo[src], on="mo", how="left")
        w[src + "_eq"] = w[src] * f.f.fillna(f.r_mo).fillna(E.err[src]["national"]).values
    day = df[df.satellite.isin(["Aqua", "N"])].pivot_table(index=["cy", "cx", "yr", "mo"], columns="satellite",
                                                          values=["nd", "ist_sum"], aggfunc="sum", fill_value=0)
    day.columns = [f"{a}_{b}" for a, b in day.columns]; day = day.reset_index()
    w = w.merge(day, on=["cy", "cx", "yr", "mo"], how="left").fillna(0)
    t0 = pd.Timestamp(*E.err["starts"]["terra"], 1)
    w["t"] = (w.yr - t0.year) * 12 + (w.mo - t0.month)
    w = w[w.t >= 0].sort_values(["t", "cy", "cx"])
    col = lambda s, nd=0: [round(float(x), nd) if nd else int(x) for x in w[s]]
    return dict(cell=c, month0=t0.strftime("%Y-%m"), n=len(w),
                cy=col("cy", 2), cx=col("cx", 2), t=col("t"),
                terra=col("terra"), aqua=col("aqua"), snpp=col("snpp"), n20=col("n20"),
                terra_eq=col("terra_eq", 2), snpp_eq=col("snpp_eq", 2), n20_eq=col("n20_eq", 2),
                aqua_day=col("nd_Aqua"), snpp_day=col("nd_N"), aqua_ist_sum=col("ist_sum_Aqua", 1))


def meta_json(countries):
    E = ENG[countries[0]]; e = E.err
    rel = {"t": e["terra"]["block_month_median_rel_err"], "m": 0.0,
           "v": max(e["snpp"]["block_month_median_rel_err"], e["n20"]["block_month_median_rel_err"])}
    return clean(dict(
        built=time.strftime("%Y-%m-%d %H:%M %Z"), countries=countries, data_end=E.data_end.strftime("%Y-%m-%d"),
        sensors=dict(starts=e["starts"], snpp_end="2026-11-02", modis_stable_end=E.stable_end,
                     errors={k: {kk: e[k][kk] for kk in ["block_month_R2", "block_month_median_rel_err", "yearly_bias_rms"]}
                             for k in ["terra", "snpp", "n20"]}),
        rel_err=rel, aqua_start=E.aqua_start.strftime("%Y-%m")))


def main(country="India", only=None):
    k = country.lower(); os.makedirs(f"{OUT}/{k}/areas", exist_ok=True)
    ids = only or list(SHAPES)
    t0 = time.time()
    for i, aid in enumerate(ids):
        json.dump(area_json(country, aid), open(f"{OUT}/{k}/areas/{aid}.json", "w"), separators=(",", ":"))
        compute.cache_clear()                                 # keep memory flat over ~680 areas
        if i % 25 == 0: print(f"{i+1}/{len(ids)} {aid} {time.time()-t0:.0f}s", flush=True)
    if only is None:
        json.dump([dict(id=a, name=p["name"], state=p["state"], kind=p["kind"]) for a, (g, p) in SHAPES.items()],
                  open(f"{OUT}/{k}/areas.json", "w"), separators=(",", ":"))
        json.dump(grid_json(country), open(f"{OUT}/{k}/grid.json", "w"), separators=(",", ":"))
        for kind in ["state", "district"]:
            shutil.copy(f"{ROOT}/data/boundaries/{k}_{kind}s_web.geojson", f"{OUT}/{k}/boundaries_{kind}.geojson")
        json.dump(meta_json([country]), open(f"{OUT}/meta.json", "w"), indent=1)
    print(f"done {len(ids)} areas in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]; only = None
    if "--only" in a: only = a[a.index("--only") + 1].split(","); a = [x for x in a if x != "--only" and x not in (",".join(only),)]
    main(a[0] if a else "India", only)
