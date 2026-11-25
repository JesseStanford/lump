#!/usr/bin/env python3
"""
sample_nest_sites.py - measure the seabed around documented nest points and compare it
with random points nearby (use vs availability), then write calibrated parameter ranges.

Inputs:
  --run     an output folder of seabed_classify.py (classes.tif, metrics.tif, boulders.csv)
  --dem     the elevation GeoTIFF used for that run
  --points  nest_candidates.csv from nest_records.py (lat, lon, evidence[, reviewed, uncertainty_m])
Options:
  --min-evidence 3        keep records at this evidence level or above
  --reviewed-only         keep only rows with reviewed = yes
  --radius 15             metres around each point to summarise (raise for vague coordinates)
  --background 20         random comparison points per nest point
  --bg-distance 1000      metres; background drawn within this distance and same depth band (+-3 m)

Outputs (in --run folder):
  nest_site_samples.csv       one row per nest point and per background point
  nest_vs_background.json     medians, p10-p90, and a simple effect size per variable
  parameters_calibrated.csv   rows in the same format as parameters.csv (rule_id, min, optimum, max ...)
"""
import argparse, csv, json, os
import numpy as np

VARS = ["class_shannon", "class_richness", "depth_m", "bed_slope_deg", "rough_std_m", "hard_fraction", "boulder_fraction",
        "shelf_fraction", "boulders_in_radius", "nearest_boulder_m", "nearest_hard_m", "relief_m"]

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True); ap.add_argument("--dem", required=True)
    ap.add_argument("--points", required=True); ap.add_argument("--min-evidence", type=int, default=3)
    ap.add_argument("--floor", type=float, default=None, help="ignore cells at or below this elevation (lidar water-surface fill)")
    ap.add_argument("--reviewed-only", action="store_true"); ap.add_argument("--radius", type=float, default=15)
    ap.add_argument("--background", type=int, default=20); ap.add_argument("--bg-distance", type=float, default=1000)
    ap.add_argument("--depth-positive", action="store_true"); ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    import rasterio
    from rasterio.warp import transform as warp
    from scipy import ndimage as ndi
    rng = np.random.default_rng(a.seed)

    with rasterio.open(a.dem) as s:
        z = s.read(1, masked=True).filled(np.nan).astype(float); crs = s.crs; tr = s.transform
    if a.depth_positive: z = -z
    with rasterio.open(os.path.join(a.run, "classes.tif")) as s: cls = s.read(1); ctr = s.transform
    with rasterio.open(os.path.join(a.run, "metrics.tif")) as s: met = s.read()
    if cls.shape != z.shape:   # run was cropped with --bbox: crop the DEM the same way
        c0, r0 = (~tr) * (ctr.c, ctr.f); r0, c0 = int(round(r0)), int(round(c0))
        z = z[r0:r0 + cls.shape[0], c0:c0 + cls.shape[1]]; tr = ctr
    res = abs(tr.a); inv = ~tr
    hard = np.isin(cls, [3, 4, 5]); boul = cls == 4; shelf = cls == 5; valid = cls > 0
    d_hard = ndi.distance_transform_edt(~hard) * res
    d_boul = ndi.distance_transform_edt(~boul) * res
    bpts = []
    bfile = os.path.join(a.run, "boulders.csv")
    if os.path.exists(bfile):
        bpts = np.array([[float(r["x"]), float(r["y"])] for r in csv.DictReader(open(bfile))])

    pts = []
    for r in csv.DictReader(open(a.points, encoding="utf-8")):
        try: ev = int(r.get("evidence", 0))
        except ValueError: ev = 0
        if ev < a.min_evidence: continue
        if a.reviewed_only and str(r.get("reviewed", "")).strip().lower() not in ("yes", "y", "1", "true"): continue
        pts.append((float(r["lon"]), float(r["lat"]), r.get("id", ""), r.get("url", "")))
    if not pts:
        raise SystemExit("No points pass the evidence/review filter.")
    xs, ys = warp("EPSG:4326", crs, [p[0] for p in pts], [p[1] for p in pts])

    rr = max(1, int(round(a.radius / res)))
    yy, xx = np.mgrid[-rr:rr + 1, -rr:rr + 1]; disk = (xx**2 + yy**2) <= rr**2

    def summarise(x, y):
        c, r = inv * (x, y); r, c = int(r), int(c)
        if not (rr <= r < z.shape[0] - rr and rr <= c < z.shape[1] - rr) or not valid[r, c]:
            return None
        sl = (slice(r - rr, r + rr + 1), slice(c - rr, c + rr + 1)); m = disk & valid[sl]
        if m.sum() < 3: return None
        zz = z[sl][m]
        if a.floor is not None and np.nanmedian(zz) <= a.floor: return None
        if met.shape[0] > 5 and np.nanmedian(met[5][sl][m]) < 1e-4: return None   # dead-flat fill, not real bed
        nb = int(((np.hypot(bpts[:, 0] - x, bpts[:, 1] - y) <= a.radius).sum())) if len(bpts) else 0
        cc = cls[sl][m]; cc = cc[cc > 0]; pk = np.bincount(cc, minlength=7)[1:] / max(1, cc.size); pk = pk[pk > 0]
        return dict(class_shannon=float(-(pk * np.log(pk)).sum()), class_richness=int(pk.size),
                    depth_m=float(np.nanmedian(z[sl][m])), bed_slope_deg=float(np.nanmedian(met[0][sl][m])),
                    rough_std_m=float(np.nanmedian(met[5][sl][m])) if met.shape[0] > 5 else np.nan,
                    hard_fraction=float(hard[sl][m].mean()), boulder_fraction=float(boul[sl][m].mean()),
                    shelf_fraction=float(shelf[sl][m].mean()), boulders_in_radius=nb,
                    nearest_boulder_m=float(d_boul[r, c]), nearest_hard_m=float(d_hard[r, c]),
                    relief_m=float(np.nanmax(z[sl][m]) - np.nanmin(z[sl][m])))

    rows = []
    for (lon, lat, pid, url), x, y in zip(pts, xs, ys):
        s = summarise(x, y)
        if s is None: continue
        rows.append(dict(kind="nest", id=pid, x=x, y=y, url=url, **s))
        got, tries = 0, 0
        while got < a.background and tries < a.background * 50:
            tries += 1; ang = rng.uniform(0, 2 * np.pi); dist = a.radius * 2 + rng.uniform(0, a.bg_distance)
            bx, by = x + dist * np.cos(ang), y + dist * np.sin(ang); b = summarise(bx, by)
            if b is None or abs(b["depth_m"] - s["depth_m"]) > 3: continue
            rows.append(dict(kind="background", id=pid, x=bx, y=by, url="", **b)); got += 1
    nest = [r for r in rows if r["kind"] == "nest"]; bg = [r for r in rows if r["kind"] == "background"]
    if not nest:
        raise SystemExit("No nest points fall inside the seabed grid. Check coordinates and CRS.")

    with open(os.path.join(a.run, "nest_site_samples.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, ["kind", "id", "x", "y", "url"] + VARS); w.writeheader(); [w.writerow(r) for r in rows]

    def q(v, p): v = np.array(v, float); v = v[np.isfinite(v)]; return None if v.size == 0 else round(float(np.percentile(v, p)), 3)
    summary = {"n_nest": len(nest), "n_background": len(bg), "radius_m": a.radius, "variables": {}}
    for v in VARS:
        nv = [r[v] for r in nest]; bv = [r[v] for r in bg]
        sd = np.nanstd(np.array(nv + bv, float)) or 1.0
        summary["variables"][v] = {"nest_p10_p50_p90": [q(nv, 10), q(nv, 50), q(nv, 90)],
                                   "background_p10_p50_p90": [q(bv, 10), q(bv, 50), q(bv, 90)],
                                   "effect_size": round(float((np.nanmean(nv) - np.nanmean(bv)) / sd), 3) if bv else None}
    if len(nest) < 10:
        summary["warning"] = f"Only {len(nest)} nest points: ranges are indicative, not robust."
    json.dump(summary, open(os.path.join(a.run, "nest_vs_background.json"), "w"), indent=2)

    def row(rid, var, applies, vals, unit, note):
        v = [x for x in vals if x is not None]
        return dict(rule_id=rid, category="calibrated", variable=var, applies_to=applies,
                    min=q(v, 5), optimum_low=q(v, 25), optimum_high=q(v, 75), max=q(v, 95), unit=unit,
                    confidence="medium" if len(nest) >= 10 else "low", basis="measured_at_nest_sites",
                    source=f"sample_nest_sites.py, n={len(nest)}, radius {a.radius} m", source_url="")
    out = [row("P01c", "nest_depth", "spawning_nest", [-r["depth_m"] for r in nest], "m", ""),
           row("R02c", "bed_slope_at_nest", "zone_Z3", [r["bed_slope_deg"] for r in nest], "deg", ""),
           row("R08c", "boulder_cover_at_nest", "zone_Z3", [r["boulder_fraction"] for r in nest], "fraction", ""),
           row("R07c", "relief_within_radius", "zone_Z3", [r["relief_m"] for r in nest], "m", ""),
           row("R13c", "nearest_hard_substrate", "spawning_nest", [r["nearest_hard_m"] for r in nest], "m", "")]
    with open(os.path.join(a.run, "parameters_calibrated.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, list(out[0].keys())); w.writeheader(); [w.writerow(r) for r in out]
    print(json.dumps({k: summary["variables"][k] for k in ("depth_m", "hard_fraction", "boulder_fraction", "nearest_hard_m")}, indent=1))

if __name__ == "__main__":
    main()
