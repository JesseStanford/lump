#!/usr/bin/env python3
"""
seabed_classify.py - turn a seabed elevation grid into substrate classes and
design geometry for the lumpfish habitat pipeline.

Input : a GeoTIFF elevation grid (bathymetry / topobathymetric lidar / multibeam),
        metres, depth negative (use --depth-positive if depths are positive).
        Optional: a co-registered backscatter or lidar-intensity GeoTIFF.
Output: (in --out folder)
  classes.tif        substrate classes (see CLASSES below)
  metrics.tif        multiband: bed slope, VRM, residual relief, broad BPI, local relief, roughness
  boulders.csv       one row per detected boulder: x, y, z_top, z_base, height_m,
                     diameter_m, nn_spacing_m  (ready for Rhino point import)
  geometry_stats.json  numbers that map onto parameters.csv rule_ids
                     (R01/R02 slope, R03 boulder size, R06 spacing, R07 relief,
                     R08 cover, zone areas Z1-Z4)
  transect.csv       shore-normal cross-section (x_offshore, z, class) for the schematic
  preview.png        quick-look map

Method (rule-based, after Lundblad et al. 2006 Benthic Terrain Modeler and
boulder-detection practice): boulders stand above a robust local background
(median filter), rock shelves are steps or raised platforms at broad scale (BPI) or
steep bed slope, rough cobble beds have high residual roughness, sediment is smooth.
Thresholds are parameters; calibrate them on a site with known ground truth
(diver video, grab samples, or a reef map) or pass --train to fit a
random forest instead.

Resolution matters: boulders are detected only if diameter >= ~3 grid cells.
A 0.5 m grid finds boulders >= ~1.5 m; Denmark's 50 m depth model finds none
and can only give slope and zone geometry.
"""
import argparse, json, os, sys
import numpy as np
from scipy import ndimage as ndi

CLASSES = {0: "nodata", 1: "sand_flat", 2: "sediment_slope", 3: "cobble_gravel_rough",
           4: "boulder", 5: "rock_shelf", 6: "dry_land"}

# ---------------------------------------------------------------- terrain metrics
def slope_aspect(z, res):
    gy, gx = np.gradient(z, res)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    aspect = np.degrees(np.arctan2(-gx, gy)) % 360
    return slope, aspect, gx, gy

def vrm(z, res, win):
    """Vector ruggedness measure (Sappington et al. 2007): 0 smooth .. 1 rough."""
    gy, gx = np.gradient(z, res)
    s = np.arctan(np.hypot(gx, gy)); a = np.arctan2(gy, gx)
    x = np.sin(s) * np.cos(a); y = np.sin(s) * np.sin(a); zc = np.cos(s)
    n = win * win
    sx, sy, sz = (ndi.uniform_filter(v, win) * n for v in (x, y, zc))
    return 1 - np.sqrt(sx**2 + sy**2 + sz**2) / n

def bpi(z, inner, outer):
    """Bathymetric position index: cell minus annulus mean (m). + = raised."""
    yy, xx = np.mgrid[-outer:outer+1, -outer:outer+1]
    r = np.hypot(xx, yy); k = ((r >= inner) & (r <= outer)).astype(float); k /= k.sum()
    return z - ndi.convolve(z, k, mode="nearest")

def local_relief(z, win):
    return ndi.maximum_filter(z, win) - ndi.minimum_filter(z, win)

# ---------------------------------------------------------------- classification
def classify(z, res, valid, p, backscatter=None):
    # bed slope from a smoothed surface (ignores ripples and boulders)
    sm = ndi.gaussian_filter(z, p["bed_smooth_m"] / res)
    slope, aspect, _, _ = slope_aspect(sm, res)
    win_f = max(3, int(round(p["fine_window_m"] / res)) | 1)
    win_b = max(win_f + 2, int(round(p["broad_window_m"] / res)) | 1)
    rug = vrm(z, res, win_f)
    # residual relief above a robust local background (median filter)
    bg = ndi.median_filter(z, size=win_f)
    resid = z - bg
    rough_std = np.sqrt(np.maximum(ndi.uniform_filter(resid**2, win_f) - ndi.uniform_filter(resid, win_f)**2, 0))
    bb = bpi(sm, max(1, win_b // 4), win_b // 2 + 1)
    rel = local_relief(z, win_f)

    cls = np.full(z.shape, 1, np.uint8)                       # sand_flat
    cls[slope > p["sediment_slope_deg"]] = 2                  # sediment_slope
    rough = rough_std > p["rough_std_m"]
    cls[rough] = 3                                            # cobble / gravel / rough
    if backscatter is not None:                               # hard acoustic return = harder bed
        cls[(backscatter > np.nanpercentile(backscatter[valid], p["bs_hard_pct"])) & (cls < 3)] = 3
    shelf = (slope > p["shelf_slope_deg"]) | (bb > p["shelf_bpi_m"])
    shelf = ndi.binary_opening(ndi.binary_fill_holes(ndi.binary_closing(shelf, iterations=2)), iterations=2)
    cls[shelf] = 5                                            # rock shelf / outcrop / step
    boulder = (resid > p["boulder_min_height_m"]) & ~shelf    # texture on a shelf stays shelf
    lab, n = ndi.label(boulder)                               # drop 1-cell specks
    if n:
        sizes = ndi.sum(boulder, lab, np.arange(1, n + 1))
        boulder &= np.isin(lab, np.nonzero(sizes >= 2)[0] + 1)
    cls[boulder] = 4
    cls[z > 0] = 6
    cls[~valid] = 0
    metrics = np.stack([slope, rug, resid, bb, rel, rough_std]).astype("float32")
    return cls, metrics

def train_classifier(metrics, valid, train_csv, transform, out_shape):
    """Optional: fit a random forest from labelled points (x,y,class)."""
    from sklearn.ensemble import RandomForestClassifier
    import csv
    inv = ~transform
    X, y = [], []
    for row in csv.DictReader(open(train_csv)):
        c, r = inv * (float(row["x"]), float(row["y"]))
        r, c = int(r), int(c)
        if 0 <= r < out_shape[0] and 0 <= c < out_shape[1] and valid[r, c]:
            X.append(metrics[:, r, c]); y.append(int(row["class"]))
    rf = RandomForestClassifier(n_estimators=300, oob_score=True, random_state=0).fit(X, y)
    flat = metrics.reshape(metrics.shape[0], -1).T
    pred = rf.predict(np.nan_to_num(flat)).reshape(out_shape).astype(np.uint8)
    pred[~valid] = 0
    return pred, rf.oob_score_

# ---------------------------------------------------------------- objects and stats
def boulders_table(cls, z, res, transform, p):
    lab, n = ndi.label(cls == 4)
    if n == 0:
        return []
    idx = np.arange(1, n + 1)
    areas = ndi.sum(np.ones_like(z), lab, idx) * res * res
    ztop = ndi.maximum(z, lab, idx)
    # base = median elevation of a 1-cell ring around each object
    ring = ndi.binary_dilation(lab > 0, iterations=2) & (lab == 0)
    grown = ndi.grey_dilation(lab, size=5); grown[~ring] = 0
    zbase = np.array([np.median(z[grown == i]) if (grown == i).any() else zt for i, zt in zip(idx, ztop)])
    cy, cx = np.array(ndi.center_of_mass(np.ones_like(z), lab, idx)).T
    xs, ys = transform * (cx + 0.5, cy + 0.5)
    rows = []
    for i in range(n):
        d = 2 * np.sqrt(areas[i] / np.pi); h = ztop[i] - zbase[i]
        if d < p["min_boulder_diam_m"] or h < p["boulder_min_height_m"]:
            continue
        rows.append(dict(x=float(xs[i]), y=float(ys[i]), z_top=float(ztop[i]), z_base=float(zbase[i]),
                         height_m=round(float(h), 3), diameter_m=round(float(d), 3)))
    if len(rows) > 1:
        from scipy.spatial import cKDTree
        pts = np.array([[r["x"], r["y"]] for r in rows])
        dist, _ = cKDTree(pts).query(pts, k=2)
        for r, dd in zip(rows, dist[:, 1]):
            r["nn_spacing_m"] = round(float(dd), 3)
    return rows

def pct(a, q):
    a = np.asarray(a); return None if a.size == 0 else round(float(np.percentile(a, q)), 3)

def geometry_stats(cls, z, metrics, res, valid, boulders, zones):
    slope = metrics[0]; out = {"grid_resolution_m": res, "classes": {}}
    tot = valid.sum()
    for k, name in CLASSES.items():
        if k == 0: continue
        out["classes"][name] = {"area_m2": round(float((cls == k).sum() * res * res), 1),
                                "fraction": round(float((cls == k).sum() / max(tot, 1)), 4)}
    out["zones"] = {}
    for zname, (top, bot) in zones.items():
        m = valid & (z <= top) & (z > bot)
        if not m.any(): continue
        hard = np.isin(cls, [3, 4, 5]) & m
        out["zones"][zname] = {
            "depth_band_m": [top, bot],
            "area_m2": round(float(m.sum() * res * res), 1),
            "slope_deg_p10_p50_p90": [pct(slope[m], 10), pct(slope[m], 50), pct(slope[m], 90)],
            "slope_rise_over_run_p50": round(float(np.tan(np.radians(np.median(slope[m])))), 4),
            "hard_substrate_fraction": round(float(hard.sum() / m.sum()), 4),
            "boulder_cover_fraction": round(float(((cls == 4) & m).sum() / m.sum()), 4),
            "relief_m_p90": pct(metrics[4][m], 90),
        }
    if boulders:
        d = [b["diameter_m"] for b in boulders]; h = [b["height_m"] for b in boulders]
        s = [b["nn_spacing_m"] for b in boulders if "nn_spacing_m" in b]
        out["boulders"] = {"count": len(boulders),
                           "diameter_m_p10_p50_p90": [pct(d, 10), pct(d, 50), pct(d, 90)],
                           "height_m_p10_p50_p90": [pct(h, 10), pct(h, 50), pct(h, 90)],
                           "nn_spacing_m_p10_p50_p90": [pct(s, 10), pct(s, 50), pct(s, 90)],
                           "density_per_100m2": round(len(boulders) / (tot * res * res) * 100, 3)}
    out["maps_to_rules"] = {
        "R01_R02_slope": "zones.*.slope_rise_over_run_p50",
        "R03_nest_boulder_diameter": "boulders.diameter_m_p10_p50_p90",
        "R06_cluster_spacing": "boulders.nn_spacing_m_p10_p50_p90",
        "R07_reef_relief": "zones.Z3_nest_reef.relief_m_p90",
        "R08_boulder_cover": "zones.Z3_nest_reef.boulder_cover_fraction"}
    return out

def shore_transect(z, cls, res, transform, valid, start=None, azimuth=None, length_m=400):
    """Profile from the shoreline offshore. Default: steepest-descent direction from the
    shallowest valid cell row-mean (good enough for a straight coast)."""
    if start is None:
        wet = valid & (z <= 0)
        rr, cc = np.nonzero(wet)
        i = np.argmax(z[rr, cc]); r0, c0 = rr[i], cc[i]
    else:
        c0, r0 = (~transform) * start; r0, c0 = int(r0), int(c0)
    if azimuth is None:
        gy, gx = np.gradient(ndi.gaussian_filter(np.nan_to_num(z), 5), res)
        az = np.arctan2(-gy[r0, c0], -gx[r0, c0])      # downhill in array coords
    else:
        az = np.radians(90 - azimuth)
    rows = []
    for k in range(int(length_m / res)):
        c = c0 + k * np.cos(az); r = r0 + k * np.sin(az)
        ri, ci = int(round(r)), int(round(c))
        if not (0 <= ri < z.shape[0] and 0 <= ci < z.shape[1]) or not valid[ri, ci]:
            break
        rows.append(dict(x_offshore_m=round(k * res, 2), z_m=round(float(z[ri, ci]), 3),
                         cls=CLASSES[int(cls[ri, ci])]))
    return rows

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dem"); ap.add_argument("--out", default="seabed_out")
    ap.add_argument("--backscatter"); ap.add_argument("--train", help="CSV x,y,class for random forest")
    ap.add_argument("--depth-positive", action="store_true")
    ap.add_argument("--params", help="JSON file overriding thresholds")
    ap.add_argument("--transect-start", nargs=2, type=float); ap.add_argument("--transect-azimuth", type=float)
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("XMIN","YMIN","XMAX","YMAX"),
                    help="crop to this box, in the raster's own coordinates")
    a = ap.parse_args()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sources
    sources.carry_args(a.out, a)
    import rasterio
    p = dict(fine_window_m=5.0, broad_window_m=60.0, bed_smooth_m=2.0, sediment_slope_deg=5.0,
             rough_std_m=0.08, shelf_slope_deg=12.0, shelf_bpi_m=0.6, boulder_min_height_m=0.3,
             min_boulder_diam_m=0.5, bs_hard_pct=80)
    if a.params: p.update(json.load(open(a.params)))
    zones = {"Z1_nursery": (0, -2), "Z2_transition": (-2, -5), "Z3_nest_reef": (-5, -10), "Z4_refuge": (-10, -15)}

    with rasterio.open(a.dem) as src:
        win = None
        if a.bbox:
            from rasterio.windows import from_bounds
            win = from_bounds(*a.bbox, transform=src.transform).round_offsets().round_lengths()
        z = src.read(1, masked=True, window=win).astype("float64"); prof = src.profile
        tr = src.window_transform(win) if win is not None else src.transform
        prof.update(height=z.shape[0], width=z.shape[1], transform=tr)
        res = abs(tr.a)
    valid = ~np.ma.getmaskarray(z) & np.isfinite(z.filled(np.nan))
    z = z.filled(np.nan)
    if a.depth_positive: z = -z
    zf = np.where(valid, z, np.nanmedian(z))
    bs = None
    if a.backscatter:
        with rasterio.open(a.backscatter) as b: bs = b.read(1).astype("float64")

    cls, metrics = classify(zf, res, valid, p, bs)
    rf_note = None
    if a.train:
        cls, oob = train_classifier(metrics, valid, a.train, tr, z.shape); rf_note = round(float(oob), 3)
    boulders = boulders_table(cls, zf, res, tr, p)
    stats = geometry_stats(cls, zf, metrics, res, valid, boulders, zones)
    stats["parameters_used"] = p
    if rf_note is not None: stats["random_forest_oob_accuracy"] = rf_note
    if res > 1.0:
        stats["warning"] = f"Grid is {res} m: boulders under ~{3*res:.1f} m cannot be resolved; use slope/zone stats only."

    os.makedirs(a.out, exist_ok=True)
    pr = prof.copy(); pr.update(dtype="uint8", count=1, nodata=0, compress="deflate")
    with rasterio.open(os.path.join(a.out, "classes.tif"), "w", **pr) as d: d.write(cls, 1)
    pr.update(dtype="float32", count=6, nodata=None)
    with rasterio.open(os.path.join(a.out, "metrics.tif"), "w", **pr) as d:
        d.write(metrics); [d.set_band_description(i+1, n) for i, n in enumerate(["bed_slope_deg","vrm","residual_relief_m","bpi_broad_m","local_relief_m","rough_std_m"])]
    import csv
    if boulders:
        keys = ["x","y","z_top","z_base","height_m","diameter_m","nn_spacing_m"]
        with open(os.path.join(a.out, "boulders.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, keys); w.writeheader(); [w.writerow(b) for b in boulders]
    tran = shore_transect(zf, cls, res, tr, valid, a.transect_start, a.transect_azimuth)
    with open(os.path.join(a.out, "transect.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, ["x_offshore_m","z_m","cls"]); w.writeheader(); [w.writerow(r) for r in tran]
    json.dump(stats, open(os.path.join(a.out, "geometry_stats.json"), "w"), indent=2)
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        from matplotlib.colors import ListedColormap
        cmap = ListedColormap(["#ffffff","#e8d8a8","#c9b27c","#9a8f7a","#5b4636","#2f2f2f","#7fae6a"])
        fig, ax = plt.subplots(1, 2, figsize=(12, 5.5))
        ls = ax[0].imshow(np.where(valid, z, np.nan), cmap="viridis"); fig.colorbar(ls, ax=ax[0], label="elevation m")
        ax[0].set_title("Elevation")
        ax[1].imshow(cls, cmap=cmap, vmin=0, vmax=6, interpolation="nearest"); ax[1].set_title("Substrate classes")
        import matplotlib.patches as mp
        ax[1].legend(handles=[mp.Patch(color=cmap(k), label=v) for k, v in CLASSES.items() if k], loc="lower right", fontsize=7)
        for x in ax: x.set_xticks([]); x.set_yticks([])
        fig.tight_layout(); fig.savefig(os.path.join(a.out, "preview.png"), dpi=110)
    except Exception as e:
        print("preview skipped:", e, file=sys.stderr)
    print(json.dumps({k: stats[k] for k in ("grid_resolution_m", "boulders") if k in stats}, indent=1))

if __name__ == "__main__":
    main()
