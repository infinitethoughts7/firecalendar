"""FireCalendar API + static web app.  Run:  uvicorn firecal.app:app --port 8000"""
import io, json, os, functools, numpy as np, pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from shapely.geometry import shape, box
from firecal.engine import Engine, season, outlook, SNPP_END
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
app = FastAPI(title="FireCalendar API", version="1.0",
              description="Harmonized MODIS + VIIRS active-fire calendar (MODIS-equivalent counts).")
ENG = {"India": Engine("India")}
SHAPES = {}
for kind in ["state", "district"]:
    for f in json.load(open(f"{ROOT}/data/boundaries/india_{kind}s_calc.geojson"))["features"]:
        SHAPES[f["properties"]["id"]] = (shape(f["geometry"]), f["properties"])

class Area(BaseModel):
    country: str = "India"
    id: Optional[str] = None             # e.g. "district-296" or "state-12"
    geometry: Optional[dict] = None      # GeoJSON geometry drawn by the user
    year: Optional[int] = None
    month: Optional[int] = None

MAX_VERTS, MAX_AREA_DEG2, MAX_BBOX_DEG2 = 2000, 40.0, 60.0          # drawn areas: bigger than any Indian state, far smaller than the country

def check_drawn(geom: dict):
    """reject drawn shapes that are invalid or big enough to exhaust memory on a public server."""
    if not isinstance(geom, dict) or geom.get("type") not in ("Polygon", "MultiPolygon"):
        raise HTTPException(400, "drawn area must be a GeoJSON Polygon or MultiPolygon")
    try: g = shape(geom)
    except Exception: raise HTTPException(400, "could not read the drawn area")
    n = sum(len(r.coords) for p in getattr(g, "geoms", [g]) for r in [p.exterior, *p.interiors])
    if n > MAX_VERTS: raise HTTPException(400, f"drawn area has too many points ({n} > {MAX_VERTS})")
    if not g.is_valid or g.is_empty: raise HTTPException(400, "drawn area is not a valid polygon (does it cross itself?)")
    x0, y0, x1, y1 = g.bounds                    # points are loaded per bounding box, so cap that too (thin rings / L-shapes)
    if g.area > MAX_AREA_DEG2 or (x1 - x0) * (y1 - y0) > MAX_BBOX_DEG2:
        raise HTTPException(400, "drawn area is too large; draw a smaller area or pick a state")
    return g

def resolve(a: Area):
    if a.country not in ENG: raise HTTPException(400, f"country not available: {a.country}")
    if a.id:
        if a.id not in SHAPES: raise HTTPException(404, "unknown area id")
        g, p = SHAPES[a.id]; return g, f"{p['name']}" + (f", {p['state']}" if p["kind"] == "district" else "")
    if a.geometry:
        g = check_drawn(a.geometry)
        x0, y0, x1, y1 = ENG[a.country].bounds
        if not g.intersects(box(x0, y0, x1, y1)): raise HTTPException(400, "drawn area is outside the country")
        return g, "Drawn area"
    raise HTTPException(400, "give an id or a geometry")

@functools.lru_cache(maxsize=64)
def compute(country, key, wkb):
    """cached per area: only small aggregates are kept (never the raw points)."""
    from shapely import from_wkb
    E = ENG[country]; g = from_wkb(wkb)
    d, pts = E.daily(g); m = E.monthly_from_daily(d); v = E.daily_value(d)
    return m, int(len(pts)), blind_spot(pts, E.calendar(m)), v, season(v, m, E.data_end)

def blind_spot(pts, cal):
    """Aqua (drifting later) vs S-NPP (fixed ~13:30) detections in this area's peak months, vs 2012-19 normal."""
    if len(pts) == 0: return None
    peak = cal.loc[2003:2021].median().nlargest(2).index.tolist()
    d = pts[(pts.satellite.isin(["Aqua", "N"]))].copy(); d["date"] = pd.to_datetime(d.date)
    d = d[d.date.dt.month.isin(peak) & (d.date.dt.year >= 2012) & (d.date <= SNPP_END)]   # only days S-NPP flew
    d["ist"] = (d.time_utc.str[:2].astype(int) * 60 + d.time_utc.str[2:].astype(int) + 330) / 60 % 24
    d = d[(d.ist > 8) & (d.ist < 20)]                       # daytime passes only
    g = d.groupby([d.date.dt.year, "satellite"]).size().unstack(fill_value=0)
    if "Aqua" not in g or "N" not in g: return None
    t = d[d.satellite == "Aqua"].groupby(d.date.dt.year).ist.median()
    r = (g.Aqua / g.N.replace(0, np.nan)); base = r.loc[2012:2019].mean()
    rows = [dict(year=int(y), aqua=int(g.Aqua[y]), snpp=int(g.N[y]), aqua_time_ist=round(float(t.get(y, np.nan)), 2),
                 relative=round(float(r[y] / base), 2) if base else None) for y in g.index]
    recent = [x for x in rows if x["year"] >= 2023 and x["aqua"] >= 50]
    flag = bool(recent) and max(x["relative"] for x in recent) >= 1.5
    return dict(peak_months=sorted(int(x) for x in peak), years=rows, flag=flag)

def clean(o):
    """replace NaN/inf (not valid JSON) with None, recursively; numpy -> python."""
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)): return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.integer): return int(o)
    return o

@app.post("/api/query")
def query(a: Area):
    g, name = resolve(a); E = ENG[a.country]
    m, n_points, blind, v, seas = compute(a.country, a.id or json.dumps(a.geometry, sort_keys=True), g.wkb)
    cal = E.calendar(m)
    # default: the area's peak month in the latest full calendar year in the data
    end = m.index.max()
    full = end.year if end.month == 12 else end.year - 1
    yv = m.value[m.index.year == full]
    peak = yv.idxmax() if yv.notna().any() and yv.max() > 0 else end
    yr, mo = a.year or peak.year, a.month or peak.month
    if yr not in cal.index: raise HTTPException(400, "year out of range")
    an = E.anomaly(m, yr, mo, partial=E.partial)
    yearly = m.assign(yr=m.index.year).groupby("yr").agg(value=("value", "sum"), lo=("lo", "sum"), hi=("hi", "sum"),
                                                        modis=("modis", "sum"), viirs_eq=("viirs_eq", "sum"))
    clim = cal.loc[2003:2021]
    return JSONResponse(clean(dict(
        name=name, country=a.country, n_points=n_points,
        monthly=[dict(date=d.strftime("%Y-%m"), value=round(float(r.value), 1), lo=round(float(r.lo), 1), hi=round(float(r.hi), 1),
                      method=r.method, terra=int(r.terra), aqua=int(r.aqua), snpp=int(r.snpp), n20=int(r.n20),
                      modis=int(r.modis), viirs_eq=None if np.isnan(r.viirs_eq) else round(float(r.viirs_eq), 1))
                 for d, r in m.iterrows()],
        calendar=dict(years=[int(y) for y in cal.index], values=[[None if np.isnan(v) else round(float(v), 1) for v in row] for row in cal.values]),
        climatology=dict(median=[None if np.isnan(v) else round(float(v), 1) for v in clim.median().values]),
        anomaly=an, yearly=[dict(year=int(y), **{k: round(float(v), 1) for k, v in r.items()}) for y, r in yearly.iterrows()],
        blind_spot=blind,
        season=seas, outlook=outlook(v, datetime.now(ZoneInfo("Asia/Kolkata")).date()),
        sensors=dict(starts=E.err["starts"], snpp_end="2026-11-02", modis_stable_end=E.stable_end,
                     errors={k: {kk: E.err[k][kk] for kk in ["block_month_R2", "block_month_median_rel_err", "yearly_bias_rms"]} for k in ["terra", "snpp", "n20"]}),
    )))

@app.post("/api/csv")
def csv(a: Area):
    g, name = resolve(a)
    m, *_ = compute(a.country, a.id or json.dumps(a.geometry, sort_keys=True), g.wkb)
    out = m.reset_index().rename(columns={"index": "month"})
    out["month"] = out.month.dt.strftime("%Y-%m"); out.insert(0, "area", name)
    out = out.rename(columns={"value": "fires_modis_equivalent", "lo": "low_estimate", "hi": "high_estimate",
                              "terra": "raw_terra_modis", "aqua": "raw_aqua_modis", "snpp": "raw_snpp_viirs", "n20": "raw_noaa20_viirs",
                              "modis": "raw_modis_total", "viirs_eq": "viirs_translated_modis_eq"})
    buf = io.StringIO(); out.round(1).to_csv(buf, index=False)
    fn = "firecalendar_" + "".join(ch if ch.isalnum() else "_" for ch in name).strip("_").lower() + ".csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={fn}"})

class PointsReq(Area):
    start: Optional[str] = None          # "YYYY-MM-DD", inclusive
    end: Optional[str] = None

MAX_POINTS = 1_000_000

@app.post("/api/points")
def points(a: PointsReq):
    """raw hotspot detections (vegetation, low confidence removed) inside the area, optionally within [start, end]."""
    g, name = resolve(a)
    pts = ENG[a.country].points(g)
    d = pd.to_datetime(pts.date)
    if a.start: pts = pts[d >= pd.Timestamp(a.start)]; d = d[d >= pd.Timestamp(a.start)]
    if a.end: pts = pts[d <= pd.Timestamp(a.end)]
    if len(pts) > MAX_POINTS: raise HTTPException(413, f"{len(pts):,} points; narrow the area or dates (limit {MAX_POINTS:,})")
    out = pts.sort_values(["date", "time_utc"]).rename(columns={"frp": "frp_mw"})
    out.insert(0, "area", name)
    buf = io.StringIO(); out.to_csv(buf, index=False)
    fn = "firecalendar_points_" + "".join(ch if ch.isalnum() else "_" for ch in name).strip("_").lower() + ".csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={fn}"})

@app.get("/api/boundaries/{kind}")
def boundaries(kind: str):
    if kind not in ("state", "district"): raise HTTPException(404)
    return FileResponse(f"{ROOT}/data/boundaries/india_{kind}s_web.geojson", media_type="application/geo+json")

@app.get("/api/areas")
def areas():
    return [dict(id=k, name=p["name"], state=p["state"], kind=p["kind"]) for k, (g, p) in SHAPES.items()]

app.mount("/", StaticFiles(directory=f"{ROOT}/web", html=True), name="web")
