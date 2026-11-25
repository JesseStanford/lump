#!/usr/bin/env python3
"""
overlay_points.py - cross-reference sighting points with a polygon habitat/substrate map.

For each point, finds the polygon class it falls in. Then compares the share of points in each class
with the share of map area in that class (use vs availability). A class with a ratio well above 1
is used more than its area would predict.

Usage:
  python overlay_points.py --polys data/dk/substrate.geojson --field folk_5cl --points runs/nest_candidates.csv \
      --bbox 7.5 54.5 15.5 58.0 --min-evidence 1 --out runs/dk_substrate_overlay

Points CSV needs lat, lon; optional evidence, month, depth_m columns are used as filters/kept.
"""
import argparse, csv, json, math, os
from collections import Counter, defaultdict
import numpy as np
from matplotlib.path import Path

def rings(geom):
    t, c = geom["type"], geom["coordinates"]
    if t == "Polygon": return [c]
    if t == "MultiPolygon": return c
    return []

def ring_area(r, lat0):
    a = np.asarray(r, float); x = a[:, 0] * 111320 * math.cos(math.radians(lat0)); y = a[:, 1] * 110540
    return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))

def load_points(path, bbox=None, min_evidence=0, months="", max_depth=None, drop=""):
    """Read a sightings CSV (lat, lon[, evidence, month/date, depth_m, notes/dataset/basis]) with filters.
    Returns a list of (lon, lat, row)."""
    import re
    drop = re.compile(drop, re.I) if drop else None
    months = {int(m) for m in str(months).split(",") if m.strip()}
    pts = []
    for r in csv.DictReader(open(path, encoding="utf-8")):
        try: lat, lon = float(r["lat"]), float(r["lon"])
        except (KeyError, ValueError): continue
        if bbox and not (bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]): continue
        try: ev = int(r.get("evidence") or 0)
        except ValueError: ev = 0
        if ev < min_evidence: continue
        if drop and drop.search(" ".join(r.get(k) or "" for k in ("notes", "dataset", "basis"))): continue
        if months:
            try: m = int(r.get("month") or (r.get("date") or "")[5:7])
            except ValueError: continue
            if m not in months: continue
        if max_depth is not None and (r.get("depth_m") or "").strip():
            try:
                if abs(float(r["depth_m"])) > max_depth: continue
            except ValueError: pass
        pts.append((lon, lat, r))
    return pts

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--polys", required=True); ap.add_argument("--field", help="attribute holding the class (omit to list fields)")
    ap.add_argument("--points", required=True); ap.add_argument("--bbox", nargs=4, type=float)
    ap.add_argument("--min-evidence", type=int, default=0); ap.add_argument("--months", default="", help="e.g. 2,3,4,5")
    ap.add_argument("--max-depth", type=float, default=None, help="keep points with depth_m <= this (blank depths kept)")
    ap.add_argument("--drop", default="", help="regex; drop points whose notes/dataset/basis match (e.g. 'cruise haul' for trawl surveys)")
    ap.add_argument("--out", default="runs/overlay")
    a = ap.parse_args()

    feats = json.load(open(a.polys, encoding="utf-8"))["features"]
    if not a.field:
        print("Fields:", sorted({k for f in feats[:200] for k in (f.get("properties") or {})})); return
    polys = []
    for f in feats:
        cls = str((f.get("properties") or {}).get(a.field, "")); g = f.get("geometry")
        if not g: continue
        for poly in rings(g):
            outer = np.asarray(poly[0], float)[:, :2]; holes = [np.asarray(h, float)[:, :2] for h in poly[1:]]
            lat0 = outer[:, 1].mean()
            area = ring_area(outer, lat0) - sum(ring_area(h, lat0) for h in holes)
            polys.append((cls, Path(outer), [Path(h) for h in holes], outer.min(0), outer.max(0), area))
    area_by = defaultdict(float)
    for p in polys: area_by[p[0]] += p[5]

    pts = load_points(a.points, a.bbox, a.min_evidence, a.months, a.max_depth, a.drop)

    out_rows, used = [], Counter()
    for lon, lat, r in pts:
        hit = "outside_map"
        for cls, path, holes, lo, hi, _ in polys:
            if lo[0] <= lon <= hi[0] and lo[1] <= lat <= hi[1] and path.contains_point((lon, lat)) \
               and not any(h.contains_point((lon, lat)) for h in holes):
                hit = cls; break
        used[hit] += 1
        out_rows.append({"lat": lat, "lon": lon, "class": hit, "evidence": r.get("evidence", ""), "date": r.get("date", ""),
                         "depth_m": r.get("depth_m", ""), "id": r.get("id", ""), "url": r.get("url", "")})

    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "points_with_class.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(out_rows[0].keys()) if out_rows else ["lat"]); w.writeheader(); w.writerows(out_rows)
    n_in = sum(v for k, v in used.items() if k != "outside_map"); A = sum(area_by.values())
    summary = []
    for cls in sorted(set(area_by) | set(used)):
        if cls == "outside_map": continue
        sp = used[cls] / n_in if n_in else 0; sa = area_by[cls] / A if A else 0
        summary.append({"class": cls, "points": used[cls], "point_share": round(sp, 3), "area_km2": round(area_by[cls] / 1e6, 2),
                        "area_share": round(sa, 3), "use_ratio": round(sp / sa, 2) if sa else None})
    summary.sort(key=lambda s: -(s["use_ratio"] or 0))
    with open(os.path.join(a.out, "use_vs_availability.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(summary[0].keys())); w.writeheader(); w.writerows(summary)
    print(f"{len(pts)} points kept, {n_in} inside the map, {used['outside_map']} outside.")
    print(f"{'class':30s} {'points':>6s} {'pt_share':>8s} {'area_share':>10s} {'ratio':>6s}")
    for s in summary: print(f"{s['class'][:30]:30s} {s['points']:6d} {s['point_share']:8.3f} {s['area_share']:10.3f} {str(s['use_ratio']):>6s}")
    print("Results in", a.out)

if __name__ == "__main__":
    main()
