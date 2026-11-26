#!/usr/bin/env python3
"""
boulder_measure.py - measure boulders seen in the spring aerial photos (0.4 m tiles from fetch_ortho.py)
and set the numbers against the geometry rules in parameters/parameters.csv.

What it can and cannot measure
  In clear water down to about 3-5 m, single boulders of about 1 m and more show as dark blobs on pale
  sand. From the photo we get their FOOTPRINT (plan size and shape), spacing, clusters, cover and the
  boulder patches. Heights, crevices and overhangs cannot be seen from above. A dark blob can also be
  a clump of seaweed or a shadow: the numbers are "dark objects", read as boulders.

How a pixel is called dark (same rule as ortho_compare.py, not re-tuned)
  Brightness is compared with bare sand: the 80th percentile of brightness (a) in a --bg-m window
  around the pixel and (b) at the same depth (0.5 m bins), whichever is brighter. A pixel with less
  than --dark-ratio (0.6) of the sand's brightness above deep water is dark. Only water from
  --min-depth to --max-depth (screen depth grid) where the bottom still shows is used. Water itself comes
  from the photo (connected to water the grid calls deep), minus --shore-buffer m at the waterline.

Objects
  boulder   dark blob of --min-area to --max-area m2 (default 0.5 to 12 m2, about 0.8 to 3.9 m across)
  patch     boulders and dark ground joined by closing gaps of --gap m (default 2.5 m); patch outlines
  cluster   boulders whose edges are within --cluster-gap m of each other (default 1 m)

Outputs in --out
  boulders.csv              x, y (EPSG:25832), lat, lon, area_m2, diameter_m, elongation, depth_m,
                            dist_shore_m, dist_patch_edge_m, cluster_id
  boulders.geojson          the same as points (WGS84), for QGIS; boulders.csv is in metres for Rhino
  boulder_patches.geojson   patch outlines with area, depth and distance from shore
  boulder_cells.csv         per --cell m square: boulders per 100 m2, dark cover, median diameter
  boulder_vs_rules.csv      measured value next to rules R03, R04, R06, R08, R15
  boulder_map.png           photo with boulders (circles to scale) and patch outlines
  boulder_hist.png          diameter, nearest-neighbour distance, cluster size, cover
  sources.csv / SOURCES.md  carried from the tiles

Usage:
  python boulder_measure.py --tiles runs/ortho_gilleleje_hornbaek/tiles --erratic runs/dk_erratics/erratic_grid.tif \
      --bbox 12.335 56.110 12.395 56.127 --out runs/boulders_nakkehoved
"""
import argparse, csv, glob, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tiles", required=True, help="folder of ortho_<x>_<y>.tif tiles (or the fetch_ortho output folder)")
    ap.add_argument("--erratic", required=True, help="erratic_grid.tif (band 3 = depth, positive down)")
    ap.add_argument("--bbox", nargs=4, type=float, help="lon_min lat_min lon_max lat_max: only tiles touching this box")
    ap.add_argument("--min-depth", type=float, default=0.3); ap.add_argument("--max-depth", type=float, default=5.0)
    ap.add_argument("--shore-buffer", type=float, default=5.0, help="strip along the photo waterline left out (swash, foam), m")
    ap.add_argument("--dark-ratio", type=float, default=0.6); ap.add_argument("--sand-pct", type=float, default=80)
    ap.add_argument("--min-contrast", type=float, default=0.25)
    ap.add_argument("--bg-m", type=float, default=40, help="window for the local sand reference, m")
    ap.add_argument("--min-area", type=float, default=0.5); ap.add_argument("--max-area", type=float, default=12)
    ap.add_argument("--min-px", type=int, help="smallest object in pixels (default: 6 on 0.4 m tiles, --min-area on fine tiles)")
    ap.add_argument("--max-elong", type=float, default=3.0, help="drop thin streaks longer than this many times their width")
    ap.add_argument("--core", type=float, default=0.1, help="object must have a core this much darker than --dark-ratio (drops threshold-edge specks)")
    ap.add_argument("--gap", type=float, default=2.5); ap.add_argument("--cluster-gap", type=float, default=1.0)
    ap.add_argument("--cell", type=float, default=50)
    ap.add_argument("--params", default=os.path.join(ROOT, "parameters", "parameters.csv"))
    ap.add_argument("--out", default="runs/boulders")
    a = ap.parse_args()
    sys.path.insert(0, HERE); import sources
    from depthfill import fill_coast, sea
    os.makedirs(a.out, exist_ok=True)
    sources.carry_args(a.out, argparse.Namespace(**{k: v for k, v in vars(a).items() if k != "params"}))   # our own rules file is not a data source

    import rasterio
    from rasterio import features as rf
    from rasterio.enums import Resampling
    from rasterio.transform import from_origin
    from rasterio.warp import reproject, transform, transform_geom
    from scipy import ndimage as ndi
    from scipy.spatial import cKDTree

    tdir = os.path.join(a.tiles, "tiles") if os.path.isdir(os.path.join(a.tiles, "tiles")) else a.tiles
    paths = sorted(glob.glob(os.path.join(tdir, "ortho_*_*.tif")))
    if not paths: raise SystemExit(f"No ortho_<x>_<y>.tif tiles in {tdir}")
    with rasterio.open(paths[0]) as s: crs, res, tile_m = s.crs, s.res[0], s.width * s.res[0]
    keys = [tuple(map(int, os.path.basename(p)[6:-4].split("_"))) for p in paths]
    if a.bbox:
        bx, by = transform("EPSG:4326", crs, [a.bbox[0], a.bbox[2], a.bbox[0], a.bbox[2]], [a.bbox[1], a.bbox[1], a.bbox[3], a.bbox[3]])
        sel = [(p, k) for p, k in zip(paths, keys) if k[0] < max(bx) and k[0] + tile_m > min(bx) and k[1] < max(by) and k[1] + tile_m > min(by)]
        if not sel: raise SystemExit("No tiles touch --bbox.")
        paths, keys = map(list, zip(*sel))
    x0, y0 = min(k[0] for k in keys), min(k[1] for k in keys)
    x1, y1 = max(k[0] for k in keys) + tile_m, max(k[1] for k in keys) + tile_m
    n = int(round(tile_m / res)); W, H = int(round((x1 - x0) / res)), int(round((y1 - y0) / res))
    tr = from_origin(x0, y1, res, res); img = np.zeros((3, H, W), "uint8")
    for p, (tx, ty) in zip(paths, keys):
        with rasterio.open(p) as s: arr = s.read([1, 2, 3])
        r, c = int(round((y1 - ty - tile_m) / res)), int(round((tx - x0) / res))
        img[:, r:r + n, c:c + n] = arr[:, :n, :n]
    print(f"{len(paths)} tiles, {W} x {H} px at {res:g} m", file=sys.stderr)
    R, G, B = img.astype("float32"); valid = img.sum(0) > 0
    Lraw = 0.299 * R + 0.587 * G + 0.114 * B
    L = ndi.uniform_filter(Lraw, 3)     # smoothed: for the sand reference only, so edges are not blurred into blobs

    with rasterio.open(a.erratic) as s:
        depth = np.full((H, W), np.nan, "float32")
        reproject(fill_coast(s.read(3)), depth, src_transform=s.transform, src_crs=s.crs, dst_transform=tr, dst_crs=crs,
                  src_nodata=np.nan, dst_nodata=np.nan, resampling=Resampling.bilinear)
    water, depth, swash = sea(R, G, B, valid, depth, a.min_depth, res, a.shore_buffer)
    land = valid & ~water & ~swash & ~(np.isfinite(depth) & (depth > 2))
    land = ndi.binary_opening(land, iterations=3)
    deep = float(np.percentile(L[water], 1))

    # sand reference: local window and same-depth, the brighter of the two
    idx = ndi.distance_transform_edt(~water, return_distances=False, return_indices=True)
    Lf = L[tuple(idx)]; f = max(1, int(round(2.0 / res)))
    small = Lf[::f, ::f]; w = max(3, int(a.bg_m / (res * f)))
    loc = ndi.zoom(ndi.percentile_filter(small, a.sand_pct, size=w), f, order=1)[:H, :W]
    if loc.shape != (H, W): loc = np.pad(loc, ((0, H - loc.shape[0]), (0, W - loc.shape[1])), mode="edge")
    nb = 41; bins = np.clip((np.nan_to_num(depth) / 0.5).astype("int32"), 0, nb - 1)
    sandb = np.full(nb, np.nan, "float32")
    for b in range(nb):
        m = water & (bins == b)
        if m.sum() > 500: sandb[b] = np.percentile(L[m], a.sand_pct)
    ok = np.isfinite(sandb)
    byd = np.interp(np.nan_to_num(depth), (np.flatnonzero(ok) + 0.5) * 0.5, sandb[ok])
    sand = np.maximum(loc, byd)
    cmax = np.nanmax(sandb - deep)
    # noise of the 3x3-smoothed brightness: raw-pixel noise at 12.5 cm is too strict and hides real boulders
    hp = L - ndi.uniform_filter(L, 31); sh = water & (depth < 2)
    if sh.sum() > 100: sh &= L >= np.percentile(L[sh], 60)     # sand-bright pixels only: boulder texture is not noise
    hpw = hp[sh]
    noise = float(1.4826 * np.median(np.abs(hpw - np.median(hpw)))) if hpw.size else 0.0
    vis = water & (depth >= a.min_depth) & (depth <= a.max_depth) & ((byd - deep) >= a.min_contrast * cmax) \
          & ((byd - deep) * (1 - a.dark_ratio) >= 3 * noise)    # the dark step must stand clear of pixel noise
    print(f"Pixel noise {noise:.1f}; deep-water brightness {deep:.0f}", file=sys.stderr)
    ratio = (Lraw - deep) / np.maximum(sand - deep, 1)
    dark = vis & (ratio < a.dark_ratio)
    dark = ndi.median_filter(dark.astype("uint8"), 3).astype(bool) & vis
    if vis.sum() == 0: raise SystemExit("No visible water between --min-depth and --max-depth in these tiles.")
    print(f"Visible water {vis.sum() * res * res / 1e4:.1f} ha, dark {100 * dark.sum() / vis.sum():.1f}%", file=sys.stderr)

    # boulders
    lab, nlab = ndi.label(dark, structure=np.ones((3, 3)))
    px = res * res
    areas = ndi.sum(np.ones_like(lab), lab, index=np.arange(1, nlab + 1)) * px
    npxs = areas / px
    min_px = a.min_px or max(6, int(np.ceil(a.min_area / px)))
    core = ndi.minimum(ratio, lab, index=np.arange(1, nlab + 1)) if nlab else np.array([])
    keep = np.flatnonzero((areas >= a.min_area) & (areas <= a.max_area) & (npxs >= min_px) & (core <= a.dark_ratio - a.core)) + 1
    print(f"Dark objects of boulder size: {int(((areas >= a.min_area) & (areas <= a.max_area)).sum())}; kept after pixel-count and dark-core checks: {len(keep)}", file=sys.stderr)
    if res > 0.2: print(f"Note: tiles are {res:g} m/pixel, so a 1 m boulder is only {1 / res:.1f} pixels across. Fetch 0.125 m tiles (--layer orto_foraar_12_5 --res 0.125 --tile-m 250) for real boulder counts.", file=sys.stderr)
    objs = ndi.find_objects(lab)
    shore_d = ndi.distance_transform_edt(~land) * res if land.any() else np.full((H, W), np.nan)
    patch = ndi.binary_closing(dark, structure=np.ones((3, 3)), iterations=max(1, int(round(a.gap / 2 / res))))
    patch = ndi.binary_opening(patch, iterations=2) & vis
    plab, npl = ndi.label(patch)
    parea = ndi.sum(np.ones_like(plab), plab, index=np.arange(1, npl + 1)) * px
    big = np.flatnonzero(parea >= 100) + 1                      # patches of 100 m2 or more
    patch = np.isin(plab, big)
    edge_d = ndi.distance_transform_edt(patch) * res            # inside a patch: distance to its edge
    rows = []
    for k in keep:
        sl = objs[k - 1]; m = lab[sl] == k
        yy, xx = np.nonzero(m); yy = yy + sl[0].start; xx = xx + sl[1].start
        cy, cx = yy.mean(), xx.mean()
        cov = np.cov(np.vstack([xx, yy])) if len(xx) > 2 else np.eye(2)
        ev = np.sort(np.linalg.eigvalsh(cov)); elong = float(np.sqrt(ev[1] / max(ev[0], 1e-6)))
        X, Y = tr * (cx + 0.5, cy + 0.5); ar = m.sum() * px
        ri, ci = int(round(cy)), int(round(cx))
        rows.append({"x": round(X, 2), "y": round(Y, 2), "area_m2": round(ar, 2), "diameter_m": round(2 * np.sqrt(ar / np.pi), 2),
                     "elongation": round(elong, 2), "depth_m": round(float(depth[ri, ci]), 1),
                     "dist_shore_m": round(float(shore_d[ri, ci]), 1) if land.any() else "",
                     "dist_patch_edge_m": round(float(edge_d[ri, ci]), 1) if patch[ri, ci] else ""})
    nstreak = sum(r["elongation"] > a.max_elong for r in rows)
    rows = [r for r in rows if r["elongation"] <= a.max_elong]
    print(f"Dropped {nstreak} thin streaks (elongation > {a.max_elong:g}); {len(rows)} boulders left", file=sys.stderr)
    if not rows: raise SystemExit("No boulder-sized dark objects found: check --max-depth, or the water may be too murky in this photo.")
    xy = np.array([[r["x"], r["y"]] for r in rows]); rad = np.array([r["diameter_m"] / 2 for r in rows])
    lon, lat = transform(crs, "EPSG:4326", list(xy[:, 0]), list(xy[:, 1]))
    tree = cKDTree(xy); dd, _ = tree.query(xy, k=2); nn = dd[:, 1]
    parent = list(range(len(rows)))
    def find(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for i, j in tree.query_pairs(r=2 * rad.max() + a.cluster_gap):
        if np.hypot(*(xy[i] - xy[j])) - rad[i] - rad[j] <= a.cluster_gap: parent[find(i)] = find(j)
    roots = [find(i) for i in range(len(rows))]; ids = {r: k for k, r in enumerate(sorted(set(roots)))}
    for i, r in enumerate(rows):
        r.update(lat=round(lat[i], 6), lon=round(lon[i], 6), nn_m=round(float(nn[i]), 2), cluster_id=ids[roots[i]])
    csize = np.bincount([ids[r] for r in roots])
    ccent = np.array([xy[[i for i in range(len(rows)) if ids[roots[i]] == c]].mean(0) for c in range(len(csize))])
    cnn = cKDTree(ccent).query(ccent, k=2)[0][:, 1] if len(ccent) > 1 else np.array([np.nan])
    multi = csize >= 2

    flds = ["x", "y", "lat", "lon", "area_m2", "diameter_m", "elongation", "depth_m", "dist_shore_m", "dist_patch_edge_m", "nn_m", "cluster_id"]
    with open(os.path.join(a.out, "boulders.csv"), "w", newline="") as fh:
        wr = csv.DictWriter(fh, flds); wr.writeheader(); wr.writerows(rows)
    json.dump({"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
               "properties": {k: r[k] for k in flds if k not in ("lat", "lon")}} for r in rows]},
              open(os.path.join(a.out, "boulders.geojson"), "w"))
    feats = []
    for g, v in rf.shapes(np.where(patch, plab, 0).astype("int32"), mask=patch, transform=tr):
        m = plab == v; feats.append({"type": "Feature", "geometry": transform_geom(crs, "EPSG:4326", g),
            "properties": {"patch": int(v), "area_m2": round(float(m.sum() * px), 0),
                           "depth_min_m": round(float(np.nanmin(depth[m])), 1), "depth_max_m": round(float(np.nanmax(depth[m])), 1),
                           "dark_cover": round(float(dark[m].mean()), 2),
                           "dist_shore_min_m": round(float(shore_d[m].min()), 0) if land.any() else None}})
    json.dump({"type": "FeatureCollection", "features": feats}, open(os.path.join(a.out, "boulder_patches.geojson"), "w"))

    # per cell
    cs = int(round(a.cell / res)); cells = []
    bx_ = ((xy[:, 0] - x0) / a.cell).astype(int); by_ = ((y1 - xy[:, 1]) / a.cell).astype(int)
    for r0 in range(0, H, cs):
        for c0 in range(0, W, cs):
            v = vis[r0:r0 + cs, c0:c0 + cs]; nv = v.sum()
            if nv * px < 0.5 * a.cell ** 2: continue
            sel = (by_ == r0 // cs) & (bx_ == c0 // cs)
            X, Y = tr * (c0 + cs / 2, r0 + cs / 2)
            cells.append({"x": round(X), "y": round(Y), "visible_m2": round(nv * px), "boulders": int(sel.sum()),
                          "per_100m2": round(100 * sel.sum() / (nv * px), 2), "dark_cover": round(float(dark[r0:r0 + cs, c0:c0 + cs][v].mean()), 3),
                          "boulder_cover": round(float(sum(rows[i]["area_m2"] for i in np.flatnonzero(sel)) / (nv * px)), 3),
                          "median_diameter_m": round(float(np.median(np.array([rows[i]["diameter_m"] for i in np.flatnonzero(sel)]))), 2) if sel.any() else "",
                          "depth_m": round(float(np.nanmean(depth[r0:r0 + cs, c0:c0 + cs][v])), 1)})
    with open(os.path.join(a.out, "boulder_cells.csv"), "w", newline="") as fh:
        wr = csv.DictWriter(fh, list(cells[0])); wr.writeheader(); wr.writerows(cells)

    # against the rules
    rules = {}
    if os.path.exists(a.params):
        for r in csv.DictReader(open(a.params, encoding="utf-8")): rules[r["rule_id"]] = r
    q = lambda v, p: round(float(np.nanpercentile(v, p)), 2) if len(v) else ""
    diam = np.array([r["diameter_m"] for r in rows]); occ = [c for c in cells if c["boulders"] > 0]
    edge = np.array([r["dist_patch_edge_m"] for r in rows if r["dist_patch_edge_m"] != ""], float)
    meas = [("R03", "nest_boulder_diameter", diam, "m", f"plan diameter of dark objects; smallest detectable about {2 * np.sqrt(a.min_area / np.pi):.1f} m"),
            ("R04", "boulders_per_nest_cluster", csize[multi].astype(float), "count", f"boulders with edges within {a.cluster_gap:g} m (clusters of 2+); touching boulders merge into one object"),
            ("R06", "nest_cluster_spacing", cnn[multi] if len(ccent) > 1 else np.array([]), "m", "centre-to-centre distance to the nearest other cluster or single boulder"),
            ("R08", "boulder_cover_fraction", np.array([c["dark_cover"] for c in occ], float), "fraction", f"dark cover in {a.cell:g} m cells that hold boulders"),
            ("R15", "nest_to_hard_soft_edge_distance", edge, "m", "distance from boulders inside a patch to the patch edge (sand)")]
    out = []
    for rid, var, v, unit, how in meas:
        r = rules.get(rid, {})
        out.append({"rule_id": rid, "variable": var, "unit": unit, "n": int(len(v)), "p10": q(v, 10), "median": q(v, 50), "p90": q(v, 90),
                    "rule_min": r.get("min", ""), "rule_opt_low": r.get("optimum_low", ""), "rule_opt_high": r.get("optimum_high", ""),
                    "rule_max": r.get("max", ""), "rule_basis": r.get("basis", ""), "how_measured": how})
    out.append({"rule_id": "", "variable": "boulder_nearest_neighbour", "unit": "m", "n": len(nn), "p10": q(nn, 10), "median": q(nn, 50),
                "p90": q(nn, 90), "how_measured": "centre-to-centre, any boulder"})
    out.append({"rule_id": "", "variable": "boulders_per_100m2", "unit": "per 100 m2", "n": len(occ),
                "p10": q([c["per_100m2"] for c in occ], 10), "median": q([c["per_100m2"] for c in occ], 50),
                "p90": q([c["per_100m2"] for c in occ], 90), "how_measured": f"{a.cell:g} m cells that hold boulders"})
    with open(os.path.join(a.out, "boulder_vs_rules.csv"), "w", newline="") as fh:
        wr = csv.DictWriter(fh, list(out[0]) if "how_measured" in out[0] else list(out[0])); wr.writeheader()
        for r in out: wr.writerow({k: r.get(k, "") for k in out[0]})
    print(f"\n{len(rows)} boulders, {int(multi.sum())} clusters of 2+, {len(feats)} patch outlines")
    print(f"{'rule':5s} {'variable':34s} {'n':>5s} {'p10':>6s} {'median':>7s} {'p90':>6s}   rule (min / optimum / max)")
    for r in out:
        print(f"{r['rule_id']:5s} {r['variable']:34s} {r['n']:5d} {str(r['p10']):>6s} {str(r['median']):>7s} {str(r['p90']):>6s}   "
              f"{r.get('rule_min', '')} / {r.get('rule_opt_low', '')}-{r.get('rule_opt_high', '')} / {r.get('rule_max', '')}")

    # figures
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.collections import PatchCollection
    from matplotlib.patches import Circle
    step = max(1, int(max(W, H) / 4000))
    fig, ax = plt.subplots(figsize=(14, 14 * H / W + 0.6))
    ax.imshow(np.moveaxis(img[:, ::step, ::step], 0, -1), extent=(x0, x1, y0, y1))
    ax.contour(np.linspace(x0, x1, W)[::step], np.linspace(y1, y0, H)[::step], patch[::step, ::step].astype(float), levels=[0.5], colors="yellow", linewidths=0.7)
    ax.add_collection(PatchCollection([Circle((r["x"], r["y"]), max(r["diameter_m"] / 2, 0.6)) for r in rows], facecolor="none", edgecolor="#ff2d95", linewidth=0.5))
    ax.set_title(f"{len(rows)} boulder-sized dark objects (magenta, to scale) and boulder patches (yellow); water from the photo, "
                 f"depth grid up to {a.max_depth:g} m. SDFI spring orthophoto", fontsize=9)
    ax.set_xticks([]); ax.set_yticks([])
    fig.savefig(os.path.join(a.out, "boulder_map.png"), dpi=220, bbox_inches="tight"); plt.close(fig)
    fig, axs = plt.subplots(1, 4, figsize=(16, 3.6))
    def band(ax, rid):
        r = rules.get(rid)
        if r and r.get("optimum_low") and r.get("optimum_high"):
            ax.axvspan(float(r["optimum_low"]), float(r["optimum_high"]), color="g", alpha=0.15, label=f"{rid} optimum")
            ax.legend(fontsize=7)
    axs[0].hist(diam, bins=30, color="#555"); band(axs[0], "R03"); axs[0].set_xlabel("plan diameter, m")
    axs[1].hist(nn, bins=30, color="#555"); band(axs[1], "R06"); axs[1].set_xlabel("nearest boulder, m (centres)")
    axs[2].hist(csize, bins=np.arange(1, max(csize.max(), 6) + 2) - 0.5, color="#555"); band(axs[2], "R04"); axs[2].set_xlabel("boulders per cluster")
    axs[3].hist([c["dark_cover"] for c in occ], bins=20, color="#555"); band(axs[3], "R08"); axs[3].set_xlabel(f"dark cover per {a.cell:g} m cell")
    fig.tight_layout(); fig.savefig(os.path.join(a.out, "boulder_hist.png"), dpi=170); plt.close(fig)
    print(f"Wrote {a.out}")

if __name__ == "__main__":
    main()
