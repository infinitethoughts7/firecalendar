"""Build simplified India state + district boundaries (datameet / Census 2011 districts, current states)."""
import json, os, shapefile
from shapely.geometry import shape, mapping
from shapely import make_valid
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
B = f"{ROOT}/data/boundaries"

def read(path, keys):
    r = shapefile.Reader(path); out = []
    for sr in r.iterShapeRecords():
        g = make_valid(shape(sr.shape.__geo_interface__)); rec = sr.record.as_dict()
        out.append((g, {k: rec[k] for k in keys}))
    return out

states = read(f"{B}/raw/Admin2", ["ST_NM"])
dists = read(f"{B}/raw/2011_Dist", ["DISTRICT", "ST_NM"])
for g, p in dists:                                    # re-assign district to its CURRENT state (e.g. Telangana)
    pt = g.representative_point()
    for sg, sp in states:
        if sg.contains(pt): p["ST_NM"] = sp["ST_NM"]; break

def fc(items, kind, tol):
    feats = []
    for i, (g, p) in enumerate(items):
        name = p.get("DISTRICT") or p["ST_NM"]
        props = {"id": f"{kind}-{i}", "name": name, "state": p["ST_NM"], "kind": kind}
        feats.append({"type": "Feature", "properties": props, "geometry": mapping(g.simplify(tol, preserve_topology=True))})
    return {"type": "FeatureCollection", "features": feats}

for kind, items in [("state", states), ("district", dists)]:
    for tag, tol in [("web", 0.01 if kind == "district" else 0.02), ("calc", 0.002)]:
        d = fc(items, kind, tol)
        json.dump(d, open(f"{B}/india_{kind}s_{tag}.geojson", "w"), separators=(",", ":"))
        print(kind, tag, len(d["features"]), f"{os.path.getsize(f'{B}/india_{kind}s_{tag}.geojson')/1e6:.1f} MB")
