#!/usr/bin/env python3
"""
site_shortlist.py - group candidate reef cells into patches inside a box and list them with the facts a
site choice needs: size, depth, whether the reef is mapped, and how far the nearest nursery habitat is.

Candidate cell (erratic grid, 250 m):  screen score 3  OR  (mapped reef AND depth <= --max-depth)
Patches are 8-connected groups of candidate cells, at least --min-cells cells.
Per patch: area, centroid lat/lon, depth p10/median/p90, share of cells that are mapped reef and that
score 3, nearest hard nursery (shore_hard / shallow_hard) and eelgrass in km (from any patch cell),
nearest spring sighting (optional) and a plain flag "all_three" = mapped reef + score 3 + hard
nursery within --near-km. Sorted: all_three first, then nearest hard nursery, then area.

Usage:
  python site_shortlist.py --bbox 12.3 55.45 12.9 56.15 --erratic runs/dk_erratics/erratic_grid.tif \\
      --reefs data/dk/reefs_helcom_1170.tif --nursery runs/dk_nursery/nursery_grid.tif \\
      --points runs/nest_candidates.csv --out runs/oresund_shortlist
"""
import argparse, csv, os, sys
import numpy as np

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bbox", nargs=4, type=float, required=True, help="lon_min lat_min lon_max lat_max")
    ap.add_argument("--erratic", required=True); ap.add_argument("--reefs"); ap.add_argument("--nursery")
    ap.add_argument("--points"); ap.add_argument("--max-depth", type=float, default=10)
    ap.add_argument("--min-cells", type=int, default=2); ap.add_argument("--near-km", type=float, default=1.0)
    ap.add_argument("--out", default="runs/shortlist")
    a = ap.parse_args()
    import rasterio
    from rasterio.warp import transform, reproject, Resampling
    from rasterio.windows import from_bounds
    from scipy import ndimage as ndi
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from reef_nursery_overlay import to_grid

    with rasterio.open(a.erratic) as s:
        bx, by = transform("EPSG:4326", s.crs, [a.bbox[0], a.bbox[2], a.bbox[0], a.bbox[2]], [a.bbox[1], a.bbox[1], a.bbox[3], a.bbox[3]])
        win = from_bounds(min(bx), min(by), max(bx), max(by), s.transform).round_offsets().round_lengths()
        score, depth = s.read(1, window=win), s.read(3, window=win); tr = s.window_transform(win); crs = s.crs
    shape = score.shape; res = abs(tr.a); km2 = (res / 1000) ** 2
    reef = to_grid(a.reefs, shape, tr, crs)[0] if a.reefs else np.zeros(shape, bool)
    s3 = np.nan_to_num(score) >= 3
    cand = s3 | (reef & np.isfinite(depth) & (depth > 0) & (depth <= a.max_depth))
    lab, n = ndi.label(cand, structure=np.ones((3, 3)))
    print(f"Box grid {shape[1]} x {shape[0]} at {res:g} m: {int(cand.sum())} candidate cells in {n} patches", file=sys.stderr)

    d_hard = d_eel = None
    if a.nursery:
        with rasterio.open(a.nursery) as s:
            src = s.read(1); masks = {}
            for name, codes in (("hard", [1, 2]), ("eel", [3])):   # presence of any fine cell -> coarse cell (max)
                d = np.zeros(shape, "uint8")
                reproject(np.isin(src, codes).astype("uint8"), d, src_transform=s.transform, src_crs=s.crs,
                          dst_transform=tr, dst_crs=crs, resampling=Resampling.max)
                masks[name] = d.astype(bool)
        ncls = np.where(masks["hard"], 1, np.where(masks["eel"], 3, 0))
        d_hard = ndi.distance_transform_edt(~masks["hard"]) * res / 1000
        d_eel = ndi.distance_transform_edt(~masks["eel"]) * res / 1000
    pts = []
    if a.points:
        from overlay_points import load_points
        P = load_points(a.points, a.bbox, 0, "2,3,4,5", None, "cruise haul")
        if P:
            px, py = transform("EPSG:4326", crs, [p[0] for p in P], [p[1] for p in P]); pts = np.c_[px, py]

    rows = []
    for k in range(1, n + 1):
        m = lab == k; c = int(m.sum())
        if c < a.min_cells: continue
        rr, cc = np.nonzero(m); xs, ys = tr * (cc + 0.5, rr + 0.5)
        lon, lat = transform(crs, "EPSG:4326", [float(np.mean(xs))], [float(np.mean(ys))])
        dv = depth[m]; dv = dv[np.isfinite(dv)]
        hard = float(d_hard[m].min()) if d_hard is not None else None
        eel = float(d_eel[m].min()) if d_eel is not None else None
        near_pt = float(np.min(np.hypot(pts[:, 0, None] - xs[None], pts[:, 1, None] - ys[None])) / 1000) if len(pts) else None
        mapped = float(reef[m].mean()); sc3 = float(s3[m].mean())
        rows.append({"patch": k, "lat": round(lat[0], 4), "lon": round(lon[0], 4), "area_km2": round(c * km2, 2),
                     "depth_p10": round(float(np.percentile(dv, 10)), 1) if dv.size else "",
                     "depth_median": round(float(np.median(dv)), 1) if dv.size else "",
                     "depth_p90": round(float(np.percentile(dv, 90)), 1) if dv.size else "",
                     "mapped_reef_share": round(mapped, 2), "score3_share": round(sc3, 2),
                     "hard_nursery_km": round(hard, 2) if hard is not None else "", "eelgrass_km": round(eel, 2) if eel is not None else "",
                     "nearest_spring_sighting_km": round(near_pt, 1) if near_pt is not None else "",
                     "all_three": bool(mapped > 0 and sc3 > 0 and hard is not None and hard <= a.near_km)})
    rows.sort(key=lambda r: (not r["all_three"], r["hard_nursery_km"] if r["hard_nursery_km"] != "" else 99, -r["area_km2"]))
    os.makedirs(a.out, exist_ok=True)
    if not rows: raise SystemExit("No candidate patches in the box.")
    with open(os.path.join(a.out, "shortlist.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f"{'#':>3s} {'lat':>8s} {'lon':>8s} {'km2':>6s} {'depth':>11s} {'mapped':>6s} {'sc3':>5s} {'hard_km':>7s} {'eel_km':>6s} all3")
    for r in rows[:25]:
        print(f"{r['patch']:>3d} {r['lat']:>8.4f} {r['lon']:>8.4f} {r['area_km2']:>6.2f} {str(r['depth_p10'])+'-'+str(r['depth_p90']):>11s} "
              f"{r['mapped_reef_share']:>6.2f} {r['score3_share']:>5.2f} {str(r['hard_nursery_km']):>7s} {str(r['eelgrass_km']):>6s} {'yes' if r['all_three'] else ''}")

    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    H, W = shape; ext = (tr.c, tr.c + W * res, tr.f - H * res, tr.f)
    fig, ax = plt.subplots(figsize=(8, 8 * H / max(W, 1) + 1))
    ax.imshow(np.where(np.isfinite(score), 0, np.nan), cmap="Greys", vmin=0, vmax=4, extent=ext, interpolation="nearest")
    if a.nursery:
        ax.imshow(np.where(np.isin(ncls, [1, 2]), 1, np.nan), cmap="Oranges_r", vmin=0, vmax=2, extent=ext, interpolation="nearest")
        ax.imshow(np.where(ncls == 3, 1, np.nan), cmap="Greens", vmin=0, vmax=1.5, extent=ext, interpolation="nearest", alpha=0.6)
    ax.imshow(np.where(cand, 1, np.nan), cmap="Reds", vmin=0, vmax=1.2, extent=ext, interpolation="nearest")
    for r in rows[:25]:
        x, y = transform("EPSG:4326", crs, [r["lon"]], [r["lat"]])
        ax.annotate(str(r["patch"]), (x[0], y[0]), fontsize=7, fontweight="bold" if r["all_three"] else "normal",
                    color="k", ha="center", va="center", bbox=dict(boxstyle="round,pad=0.15", fc="w", ec="r" if r["all_three"] else "0.6", lw=0.6))
    if len(pts): ax.scatter(pts[:, 0], pts[:, 1], s=6, c="b", label="spring sightings")
    ax.set_title("Candidate reef patches (red), hard nursery (brown), eelgrass (green)"); ax.set_xticks([]); ax.set_yticks([])
    fig.savefig(os.path.join(a.out, "shortlist_map.png"), dpi=170, bbox_inches="tight")
    print("Results in", a.out)

if __name__ == "__main__":
    main()
