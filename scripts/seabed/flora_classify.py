#!/usr/bin/env python3
"""
flora_classify.py - tell hard ground (boulders, nearly always weed-covered) from seaweed / eelgrass on sand,
using several years of spring aerial photos of the same area.

Three clues
  1. Persistence (main test). Boulders stay put; weed beds, eelgrass and drift weed move, grow and die
     back. A dark object (same dark rule as ortho_compare.py / boulder_measure.py, not re-tuned) is
     checked in every other year by its mean darkness ratio there, over the same footprint (best fit
     within --tol m, after each other year is shifted to best match the reference year, tile by tile,
     by cross-correlation, max --max-shift m). The mean over the whole footprint is far less noisy than
     single pixels, and the confirming threshold (--confirm 0.7) is looser than the finding one (0.6),
     so an object near the line in one year is not called temporary because light or clarity differed.
     Only years that see the bottom there count.
       hard        mean ratio < --confirm in at least --hard-share (0.75)  boulders / stone reef
                   of the other years (all of them with 2 or 3 years; with
                   4 or more, one poor photo is tolerated)
       changing    sand-bright (ratio >= --gone 0.85) in most other years eelgrass, drift weed, annual
                                                                          weed on sand, or moved sand ripples
       uncertain   in between
  2. Shape. Per object: plan size, elongation, solidity (area / convex hull) and edge sharpness (brightness
     gradient across the outline per metre, divided by the object's contrast with the sand around it: about
     1/edge width in m, so a crisp 0.3 m edge gives about 3, a soft 2 m fringe about 0.5). Boulders: compact, solid, sharp-edged.
     Weed: soft, streaky, ragged.
  3. Colour, only where the depth grid says <= --colour-depth (default 2 m); deeper, the water takes the
     red out and everything is blue-green. The deep-water colour (surface glare and water haze, the same
     over dark and bright bottom) is subtracted first; then the object's colour balance is compared with
     the sand ring around it:
       brown_olive   redder and less blue than the sand   (Fucus, kelp, most weed-covered stones)
       green         greener                              (sea lettuce, green filamentous algae, eelgrass)
       grey_dark     darker with no colour shift          (bare stone, deep shadow)
The photo cannot see bare vs weed-covered stone underneath a canopy: "hard" means hard ground with or
without weed on it.

Inputs: two or more fetch_ortho.py output folders (same --tile-m and --res, same box), given as
YEAR=FOLDER. The first is the reference year (objects are taken from it).

Outputs in --out
  flora_objects.csv        one row per dark object: position (EPSG:25832 and lat/lon), area, diameter,
                           elongation, solidity, edge_sharpness, overlap per year, class, colour
  flora_objects.geojson    the same as points (WGS84)
  flora_classes.tif        per pixel (at --map-res m): 1 sand, 2 hard,
                           3 changing, 4 uncertain, 0 not visible / land
  flora_summary.csv        area per class and depth band, object counts per class and colour
  flora_map.png            reference photo with hard (orange) and changing (green) overlaid
  sources.csv / SOURCES.md carried from the photo folders

Usage:
  python flora_classify.py --years 2026=runs/ortho_nakkehoved_12cm 2022=runs/ortho_nakkehoved_2022 \
      2019=runs/ortho_nakkehoved_2019 --erratic runs/dk_erratics/erratic_grid.tif --out runs/flora_nakkehoved
"""
import argparse, csv, glob, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

def tiles_of(folder):
    d = os.path.join(folder, "tiles") if os.path.isdir(os.path.join(folder, "tiles")) else folder
    out = {}
    for p in glob.glob(os.path.join(d, "ortho_*_*.tif")):
        x, y = os.path.basename(p)[6:-4].split("_"); out[(int(x), int(y))] = p
    return out

def lum(img):
    R, G, B = img.astype("float32"); return 0.299 * R + 0.587 * G + 0.114 * B

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--years", nargs="+", required=True, help="YEAR=FOLDER ...; the first is the reference year")
    ap.add_argument("--erratic", required=True)
    ap.add_argument("--min-depth", type=float, default=0.3); ap.add_argument("--max-depth", type=float, default=5.0)
    ap.add_argument("--dark-ratio", type=float, default=0.6); ap.add_argument("--sand-pct", type=float, default=80)
    ap.add_argument("--min-contrast", type=float, default=0.25); ap.add_argument("--bg-m", type=float, default=40)
    ap.add_argument("--min-area", type=float, default=0.5, help="smallest object, m2")
    ap.add_argument("--tol", type=float, default=1.0, help="misregistration allowed when checking another year, m")
    ap.add_argument("--max-shift", type=float, default=3.0, help="largest shift searched between years, m")
    ap.add_argument("--confirm", type=float, default=0.7, help="mean dark ratio over the footprint that confirms an object in another year")
    ap.add_argument("--hard-share", type=float, default=0.75, help="share of other years that must confirm an object for 'hard' (with 4+ years, one poor photo is tolerated)")
    ap.add_argument("--gone", type=float, default=0.85, help="mean ratio at or above this in most other years = 'changing' (sand-bright)")
    ap.add_argument("--colour-depth", type=float, default=2.0)
    ap.add_argument("--map-res", type=float, default=0.5)
    ap.add_argument("--out", default="runs/flora")
    a = ap.parse_args()
    sys.path.insert(0, HERE); import sources
    os.makedirs(a.out, exist_ok=True)
    years = [y.split("=", 1) for y in a.years]
    if len(years) < 2: raise SystemExit("Give at least two years (YEAR=FOLDER).")
    for _, f in years:
        if not os.path.isdir(f): raise SystemExit(f"Not a folder: {f}")
    sources.carry(a.out, [f for _, f in years] + [a.erratic])

    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import from_origin
    from rasterio.warp import reproject, transform
    from scipy import ndimage as ndi
    from scipy.spatial import ConvexHull

    tl = [tiles_of(f) for _, f in years]
    keys = sorted(set(tl[0]).intersection(*map(set, tl[1:])))
    if not keys: raise SystemExit("No tiles common to all years: fetch them with the same --bbox, --tile-m and --res.")
    with rasterio.open(tl[0][keys[0]]) as s: crs, res, tile_m, n = s.crs, s.res[0], s.width * s.res[0], s.width
    for t in tl[1:]:
        with rasterio.open(t[keys[0]]) as s:
            if abs(s.res[0] - res) > 1e-6: raise SystemExit("The years have different pixel sizes: fetch them with the same --res.")
    print(f"{len(keys)} tiles of {tile_m:g} m at {res:g} m in all {len(years)} years ({', '.join(y for y, _ in years)})", file=sys.stderr)
    es = rasterio.open(a.erratic)
    def depth_for(tx, ty):
        d = np.full((n, n), np.nan, "float32")
        reproject(es.read(3).astype("float32"), d, src_transform=es.transform, src_crs=es.crs,
                  dst_transform=from_origin(tx, ty + tile_m, res, res), dst_crs=crs, src_nodata=np.nan, dst_nodata=np.nan,
                  resampling=Resampling.bilinear)
        return d
    def water_of(img, d):
        R, G, B = img.astype("float32")
        return (img.sum(0) > 0) & np.isfinite(d) & (d > 0) & (B > R) & (G >= R - 5)

    # pass 1: deep-water and sand brightness per year (sampled)
    stats = []
    for yi, (yname, _) in enumerate(years):
        Ls, Ds, Hs, Cs = [], [], [], []
        for k in keys:
            with rasterio.open(tl[yi][k]) as s: img = s.read([1, 2, 3])
            d = depth_for(*k); w = water_of(img, d)
            L = ndi.uniform_filter(lum(img), 3)
            hp = L - ndi.uniform_filter(L, 31)
            Ls.append(L[w][::37]); Ds.append(d[w][::37]); Hs.append(hp[w & (d < 2)][::37]); Cs.append(img[:, w][:, ::37].T)
        L = np.concatenate(Ls); D = np.concatenate(Ds); H = np.concatenate(Hs); C = np.concatenate(Cs).astype("float32")
        noise = float(1.4826 * np.median(np.abs(H - np.median(H)))) if H.size else 0.0
        deep = float(np.percentile(L, 1)); nb = 41; b = np.clip((D / 0.5).astype(int), 0, nb - 1)
        sand = np.array([np.percentile(L[b == i], a.sand_pct) if (b == i).sum() > 100 else np.nan for i in range(nb)])
        ok = np.isfinite(sand); cmax = np.nanmax(sand - deep)
        cdeep = C[L <= deep].mean(axis=0) if (L <= deep).any() else np.zeros(3)   # glare + water haze colour
        stats.append((deep, (np.flatnonzero(ok) + 0.5) * 0.5, sand[ok], cmax, noise, cdeep))
        print(f"  {yname}: deep-water brightness {deep:.0f}, sand at 1 m {np.interp(1, stats[-1][1], stats[-1][2]):.0f}, pixel noise {noise:.1f}", file=sys.stderr)

    def dark_of(img, d, st):
        deep, cen, sandv, cmax, noise, _ = st
        w = water_of(img, d); L = ndi.uniform_filter(lum(img), 3)
        idx = ndi.distance_transform_edt(~w, return_distances=False, return_indices=True) if w.any() else None
        if idx is None: z = np.zeros_like(w); return z, z, L, z, np.ones(w.shape, "float32")
        Lf = ndi.uniform_filter(L, 3)[tuple(idx)]; f = max(1, int(round(1.0 / res)))
        sm = Lf[::f, ::f]; loc = ndi.zoom(ndi.percentile_filter(sm, a.sand_pct, size=max(3, int(a.bg_m / (res * f)))), f, order=1)
        loc = np.pad(loc, ((0, max(0, n - loc.shape[0])), (0, max(0, n - loc.shape[1]))), mode="edge")[:n, :n]
        byd = np.interp(np.nan_to_num(d), cen, sandv)
        # visible: sand clearly brighter than deep water, and the dark step (1 - dark_ratio) of that contrast is >= 3 x pixel noise
        vis = w & (d >= a.min_depth) & (d <= a.max_depth) & ((byd - deep) >= a.min_contrast * cmax) \
              & ((byd - deep) * (1 - a.dark_ratio) >= 3 * noise)
        ratio = (L - deep) / np.maximum(np.maximum(loc, byd) - deep, 1)
        dk = vis & (ratio < a.dark_ratio); cf = vis & (ratio < a.confirm)
        md = lambda m: ndi.median_filter(m.astype("uint8"), 3).astype(bool) & vis
        return md(dk), vis, L, md(cf), ratio

    def best_shift(Lref, Lo, vis):
        if vis.mean() < 0.05: return None          # too little shared bottom in this tile to align on
        f = max(1, int(round(0.25 / res))); A = np.where(vis, Lref, np.nan)[::f, ::f]; B = np.where(vis, Lo, np.nan)[::f, ::f]
        A = np.nan_to_num(A - np.nanmean(A)); B = np.nan_to_num(B - np.nanmean(B))
        if not A.any() or not B.any(): return 0, 0
        X = np.fft.irfft2(np.fft.rfft2(A) * np.conj(np.fft.rfft2(B)), s=A.shape)
        m = int(a.max_shift / (res * f)); X = np.fft.fftshift(X); cy, cx = np.array(X.shape) // 2
        win = X[cy - m:cy + m + 1, cx - m:cx + m + 1]; dy, dx = np.unravel_index(np.argmax(win), win.shape)
        return (dy - m) * f, (dx - m) * f

    # pass 2: per tile
    mf = max(1, int(round(a.map_res / res))); mn = n // mf
    xs0, ys1 = min(k[0] for k in keys), max(k[1] for k in keys) + tile_m
    MW = int(round((max(k[0] for k in keys) + tile_m - xs0) / (res * mf))); MH = int(round((ys1 - min(k[1] for k in keys)) / (res * mf)))
    cmap = np.zeros((MH, MW), "uint8"); ref_small = np.zeros((3, MH, MW), "uint8")
    cdeep0 = stats[0][5]; sstep = max(1, int(round(0.25 / res)))
    rows = []; tolpx = max(1, int(round(a.tol / res))); px = res * res; shifts = []; visfrac = [[] for _ in years[1:]]; conf = [[] for _ in years[1:]]
    for ti, (tx, ty) in enumerate(keys, 1):
        d = depth_for(tx, ty)
        with rasterio.open(tl[0][(tx, ty)]) as s: img0 = s.read([1, 2, 3])
        dk0, vis0, L0, _, _ = dark_of(img0, d, stats[0])
        others = []
        for yi in range(1, len(years)):
            with rasterio.open(tl[yi][(tx, ty)]) as s: img = s.read([1, 2, 3])
            _, vis, L, cf, rt = dark_of(img, d, stats[yi])
            sh = best_shift(L0, L, vis0 & vis)
            if sh is None: sy = sx = 0
            else: sy, sx = sh; shifts.append((sy * res, sx * res))
            dk = np.roll(np.roll(cf, sy, 0), sx, 1); vis = np.roll(np.roll(vis, sy, 0), sx, 1); rt = np.roll(np.roll(rt, sy, 0), sx, 1)
            others.append((ndi.binary_dilation(dk, iterations=tolpx), vis, rt))
        # a pixel is judged on the years where the bottom is visible there (a windy or murky year drops out locally)
        nvis = np.zeros(dk0.shape, "uint8"); ndark = np.zeros(dk0.shape, "uint8")
        for dkd, v, _ in others: nvis += v; ndark += (dkd & dk0 & v)
        for yi, (dkd, v, _) in enumerate(others):
            visfrac[yi].append((float((v & vis0).sum()), float(vis0.sum())))
            # leave-one-out check: on dark ground that the OTHER comparison years mostly confirm, does this year confirm it?
            if len(others) > 1:
                nv = sum(o[1] for j, o in enumerate(others) if j != yi); nd = sum(o[0] & o[1] for j, o in enumerate(others) if j != yi)
                cons = dk0 & v & (nv > 0) & (nd >= 0.5 * nv)
                conf[yi].append((float((dkd & cons).sum()), float(cons.sum())))
        both = vis0 & (nvis >= 1)
        # pixel classes
        cls = np.zeros(dk0.shape, "uint8")
        cls[both] = 1
        hard_px = ndark >= np.ceil(a.hard_share * nvis - 1e-9)
        cls[both & dk0 & ~hard_px] = 4
        cls[both & dk0 & (ndark < 0.5 * nvis)] = 3
        cls[both & dk0 & hard_px] = 2
        r0 = int(round((ys1 - ty - tile_m) / (res * mf))); c0 = int(round((tx - xs0) / (res * mf)))
        cmap[r0:r0 + mn, c0:c0 + mn] = cls[:mn * mf:mf, :mn * mf:mf]
        ref_small[:, r0:r0 + mn, c0:c0 + mn] = img0[:, :mn * mf:mf, :mn * mf:mf]
        # objects
        lab, nl = ndi.label(dk0 & both, structure=np.ones((3, 3)))
        if not nl: continue
        objs = ndi.find_objects(lab); gy, gx = np.gradient(ndi.gaussian_filter(L0, 1))
        grad = np.hypot(gx, gy); R, G, B = img0.astype("float32"); S = R + G + B + 1
        for k, sl in enumerate(objs, 1):
            m = lab[sl] == k; ar = m.sum() * px
            if ar < a.min_area: continue
            yy, xx = np.nonzero(m); yy = yy + sl[0].start; xx = xx + sl[1].start
            # overlap per other year, only where that year sees the bottom over at least half the object
            ov, rv = [], []
            for dkd, v, rt in others:
                if v[yy, xx].mean() < 0.5: ov.append(np.nan); rv.append(np.nan); continue
                ov.append(float(dkd[yy, xx][v[yy, xx]].mean()))
                best = np.inf     # darkest fit of the same footprint within --tol (misregistration)
                for dy in range(-tolpx, tolpx + 1, sstep):
                    for dx in range(-tolpx, tolpx + 1, sstep):
                        y2, x2 = yy + dy, xx + dx; inb = (y2 >= 0) & (y2 < n) & (x2 >= 0) & (x2 < n)
                        if inb.mean() < 0.8: continue
                        y2, x2 = y2[inb], x2[inb]; vv = v[y2, x2]
                        if vv.mean() >= 0.5: best = min(best, float(rt[y2, x2][vv].mean()))
                rv.append(best if np.isfinite(best) else np.nan)
            ok = [r for r in rv if not np.isnan(r)]
            if not ok: continue
            share = np.mean(np.array(ok) < a.confirm)
            cls_o = "hard" if share >= a.hard_share - 1e-9 else ("changing" if np.median(ok) >= a.gone else "uncertain")
            cov = np.cov(np.vstack([xx, yy])) if len(xx) > 2 else np.eye(2); ev = np.sort(np.linalg.eigvalsh(cov))
            try: sol = float(len(xx) / ConvexHull(np.c_[xx, yy]).volume) if len(xx) > 10 else 1.0
            except Exception: sol = 1.0
            mm = np.zeros(dk0.shape, bool); mm[yy, xx] = True
            pad = slice(max(sl[0].start - 3 * tolpx, 0), sl[0].stop + 3 * tolpx), slice(max(sl[1].start - 3 * tolpx, 0), sl[1].stop + 3 * tolpx)
            mloc = mm[pad]; edge = mloc & ~ndi.binary_erosion(mloc)
            ring = ndi.binary_dilation(mloc, iterations=max(2, int(1.5 / res))) & ~ndi.binary_dilation(mloc, iterations=1) & ~dk0[pad] & vis0[pad]
            contrast = (L0[pad][ring].mean() - L0[pad][mloc].mean()) if ring.any() else np.nan
            sharp = float(grad[pad][edge].mean() / res / contrast) if ring.any() and contrast > 1 else np.nan
            cy, cx = yy.mean(), xx.mean(); X, Y = tx + (cx + 0.5) * res, ty + tile_m - (cy + 0.5) * res
            dep = float(d[int(cy), int(cx)]); colour = ""; dcol = ["", "", ""]
            if ring.any() and dep <= a.colour_depth:
                # bottom-leaving colour: subtract glare + haze (deep-water colour), then compare colour balance
                ob = [max(float(c[pad][mloc].mean()) - cd, 0.5) for c, cd in zip((R, G, B), cdeep0)]
                sb = [max(float(c[pad][ring].mean()) - cd, 0.5) for c, cd in zip((R, G, B), cdeep0)]
                oc = np.array(ob) / sum(ob); sc = np.array(sb) / sum(sb); dc = oc - sc
                dcol = [round(float(v) * 100, 1) for v in dc]
                colour = "brown_olive" if dc[0] > 0.01 and dc[2] < 0 else ("green" if dc[1] > 0.01 and dc[0] <= 0.01 else "grey_dark")
            rows.append({"x": round(X, 2), "y": round(Y, 2), "area_m2": round(ar, 2), "diameter_m": round(2 * np.sqrt(ar / np.pi), 2),
                         "elongation": round(float(np.sqrt(ev[1] / max(ev[0], 1e-6))), 2), "solidity": round(min(sol, 1.0), 2),
                         "edge_sharpness": "" if np.isnan(sharp) else round(sharp, 2), "depth_m": round(dep, 1),
                         **{f"overlap_{years[i + 1][0]}": ("" if np.isnan(o) else round(o, 2)) for i, o in enumerate(ov)},
                         **{f"ratio_{years[i + 1][0]}": ("" if np.isnan(r) else round(r, 2)) for i, r in enumerate(rv)},
                         "years_compared": len(ok), "class": cls_o, "colour": colour,
                         "d_red_pct": dcol[0], "d_green_pct": dcol[1], "d_blue_pct": dcol[2]})
        print(f"  tile {ti}/{len(keys)}", end="\r", file=sys.stderr)
    print(file=sys.stderr)
    if shifts:
        sh = np.array(shifts); print(f"Shift between years (median |dy|, |dx|, over {len(sh)} tile pairs with enough bottom): "
                                    f"{np.median(np.abs(sh[:, 0])):.2f} m, {np.median(np.abs(sh[:, 1])):.2f} m (step {max(1, int(round(0.25 / res))) * res:.2f} m)", file=sys.stderr)
    rates = [sum(x for x, _ in c) / max(sum(t for _, t in c), 1) if c else np.nan for c in conf]
    for yi, vf in enumerate(visfrac):
        f = sum(x for x, _ in vf) / max(sum(t for _, t in vf), 1); r = rates[yi]
        bad = bool(np.isfinite(r) and r < 0.7)
        print(f"Year {years[yi + 1][0]}: sees the bottom on {100 * f:.0f}% of the reference year's visible area"
              + (f"; confirms {100 * r:.0f}% of the dark ground the other years agree on" if np.isfinite(r) else "")
              + ("  <- disagrees with the other years: probably a poor photo (waves, glare, murky water); check its overview and consider dropping it" if bad else ""),
              file=sys.stderr)
    if not rows: raise SystemExit("No dark objects visible in the reference year and at least one other year.")
    lon, lat = transform(crs, "EPSG:4326", [r["x"] for r in rows], [r["y"] for r in rows])
    for r, lo, la in zip(rows, lon, lat): r["lat"], r["lon"] = round(la, 6), round(lo, 6)
    flds = list(rows[0])
    with open(os.path.join(a.out, "flora_objects.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, flds); w.writeheader(); w.writerows(rows)
    json.dump({"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
               "properties": {k: v for k, v in r.items() if k not in ("lat", "lon")}} for r in rows]}, open(os.path.join(a.out, "flora_objects.geojson"), "w"))
    mtr = from_origin(xs0, ys1, res * mf, res * mf)
    with rasterio.open(os.path.join(a.out, "flora_classes.tif"), "w", driver="GTiff", width=MW, height=MH, count=1, dtype="uint8",
                       crs=crs, transform=mtr, nodata=0, compress="deflate") as dd:
        dd.write(cmap, 1); dd.descriptions = ("1 sand, 2 hard, 3 changing, 4 uncertain",)

    # summary
    sumrows = []
    dmap = np.full((MH, MW), np.nan, "float32")
    reproject(es.read(3).astype("float32"), dmap, src_transform=es.transform, src_crs=es.crs, dst_transform=mtr, dst_crs=crs,
              src_nodata=np.nan, dst_nodata=np.nan, resampling=Resampling.bilinear)
    for lo, hi in ((0, 1), (1, 2), (2, 3), (3, 5)):
        m = (dmap > lo) & (dmap <= hi) & (cmap > 0); tot = m.sum()
        if not tot: continue
        sumrows.append({"what": f"area {lo}-{hi} m", **{c: round(100 * float(((cmap == v) & m).sum()) / tot, 1) for v, c in
                        ((1, "sand_%"), (2, "hard_%"), (3, "changing_%"), (4, "uncertain_%"))}, "area_ha": round(tot * (res * mf) ** 2 / 1e4, 1)})
    for c in ("hard", "changing", "uncertain"):
        sub = [r for r in rows if r["class"] == c]
        cols = {k: sum(r["colour"] == k for r in sub) for k in ("brown_olive", "green", "grey_dark")}
        sh = [r["edge_sharpness"] for r in sub if r["edge_sharpness"] != ""]
        sumrows.append({"what": f"objects {c}", "count": len(sub), "median_diameter_m": round(float(np.median([r["diameter_m"] for r in sub])), 2) if sub else "",
                        "median_solidity": round(float(np.median([r["solidity"] for r in sub])), 2) if sub else "",
                        "median_edge_sharpness": round(float(np.median(sh)), 2) if sh else "", **cols})
    keys_ = []
    for r in sumrows: keys_ += [k for k in r if k not in keys_]
    with open(os.path.join(a.out, "flora_summary.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, keys_); w.writeheader(); [w.writerow({k: r.get(k, "") for k in keys_}) for r in sumrows]
    for r in sumrows: print("  " + ", ".join(f"{k} {v}" for k, v in r.items()))

    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    step = max(1, int(max(MW, MH) / 4000))
    fig, ax = plt.subplots(figsize=(14, 14 * MH / MW + 0.6)); ext = (xs0, xs0 + MW * res * mf, ys1 - MH * res * mf, ys1)
    ax.imshow(np.moveaxis(ref_small[:, ::step, ::step], 0, -1), extent=ext)
    ov = np.zeros((MH, MW, 4), "float32"); ov[cmap == 2] = (1, 0.55, 0, 0.75); ov[cmap == 3] = (0.1, 0.9, 0.2, 0.6); ov[cmap == 4] = (1, 1, 0.2, 0.45)
    ax.imshow(ov[::step, ::step], extent=ext, interpolation="nearest")
    ax.legend(handles=[Patch(color=(1, 0.55, 0), label=f"hard: dark in the reference year and >= {100 * a.hard_share:.0f}% of the others (boulders, usually weed-covered)"),
                       Patch(color=(0.1, 0.9, 0.2), label="changing: dark in under half of the other years (eelgrass, drift weed, moved sand)"),
                       Patch(color=(1, 1, 0.2), label="uncertain: in between")],
              fontsize=8, loc="lower left")
    ax.set_title(f"Spring photos {', '.join(y for y, _ in years)} (SDFI), {a.min_depth:g}-{a.max_depth:g} m", fontsize=9)
    ax.set_xticks([]); ax.set_yticks([])
    fig.savefig(os.path.join(a.out, "flora_map.png"), dpi=200, bbox_inches="tight"); plt.close(fig)
    print(f"{len(rows)} objects; wrote {a.out}")

if __name__ == "__main__":
    main()
