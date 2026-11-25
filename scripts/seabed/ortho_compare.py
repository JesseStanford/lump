#!/usr/bin/env python3
"""
ortho_compare.py - do the aerial photos agree with the substrate maps and the reef screen?

Puts the spring orthophoto mosaic (from fetch_ortho.py) under
  - the EMODnet seabed substrate polygons (Folk classes) and glacial source polygons,
  - the erratic screen (score 0-3 and category, erratic_grid.tif),
  - the mapped reefs (HELCOM Reefs 1170),
and measures, for every 250 m screen cell where the seabed can be seen, how much of it looks like
boulders / weed (dark patches) versus clean sand (pale, even).

How "dark patch" is measured
  The seabed is only visible in shallow water (--visible-depth, default 6 m), and water gets darker
  with depth anyway. So each water pixel's brightness is compared with the typical brightness of
  water pixels at the same depth (0.5 m depth bins from the screen's depth band). A pixel counts as
  dark when it is more than --k robust standard deviations darker than that. Boulders with seaweed,
  eelgrass and mussel beds all read as dark: the photo cannot tell them apart, the maps can help.
  Per cell: dark_frac = dark pixels / visible water pixels. Classes:
    patchy_dark    dark_frac >= --dark-hi (default 0.25)    boulders / weed likely
    pale_even      dark_frac <= --dark-lo (default 0.08)    sand likely
    mixed          in between
  Cells with less than --min-visible (default 0.25) of their area as visible water are "not_visible".

Outputs in --out:
  ortho_compare.png            4 panels: substrate on photo; screen + mapped reefs on photo;
                               dark pixels; agreement per cell
  ortho_compare_zoom.png       the same for --zoom (lon/lat box), if given
  ortho_compare_cells.csv      one row per visible cell: photo metrics and every map value
  ortho_compare_summary.csv    dark share by substrate class, screen score, category, mapped reef,
                               and agreement tables (percent agreement and Cohen's kappa)
  ortho_agreement.tif          per cell: 1 both say hard, 2 maps only, 3 photo only, 4 both say soft
  sources.csv / SOURCES.md     carried from the inputs

Usage:
  python ortho_compare.py --ortho runs/ortho_gilleleje_hornbaek --erratic runs/dk_erratics/erratic_grid.tif \
      --data data/dk --reefs data/dk/reefs_helcom_1170.tif --out runs/ortho_compare_gh \
      --zoom 12.33 56.11 12.40 56.13
"""
import argparse, csv, json, os, re, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
COARSE = r"rock|boulder|coarse|mixed|gravel|diamict|till|stone|cobble|pebble|lag"
GLACIAL = r"till|diamict|boulder|morain|drumlin|esker|glacial|ice.?rafted|glacio|kame|outwash"
CATS = ["other", "till_buried", "coarse_no_source", "lag_on_till_deep", "lag_on_till_shallow"]
AGREE = {1: "both hard", 2: "maps hard, photo soft", 3: "photo hard, maps soft", 4: "both soft"}

def load(path):
    return [f for f in json.load(open(path, encoding="utf-8"))["features"] if f.get("geometry")]

def substrate_field(feats):
    keys = {k for f in feats[:200] for k in (f.get("properties") or {})}
    for pat in (r"folk.*7.*txt", r"folk.*5.*txt", r"folk.*txt", r"folk.*7", r"folk.*5", r"folk", r"substrat", r"class"):
        hit = sorted(k for k in keys if re.search(pat, k, re.I))
        if hit: return hit[0]
    raise SystemExit(f"No substrate class field found; fields are {sorted(keys)}")

def kappa(t):
    t = np.asarray(t, float); n = t.sum()
    if n == 0: return None, None
    po = np.trace(t) / n; pe = (t.sum(0) * t.sum(1)).sum() / n ** 2
    return round(100 * po, 1), (round((po - pe) / (1 - pe), 2) if pe < 1 else None)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ortho", required=True, help="folder from fetch_ortho.py (ortho_mosaic.tif), or the mosaic itself")
    ap.add_argument("--erratic", required=True, help="erratic_grid.tif (score, category, depth)")
    ap.add_argument("--data", help="folder with substrate.geojson, quat_lithology.geojson, geomorph_polys.geojson")
    ap.add_argument("--substrate"); ap.add_argument("--glacial", action="append", default=[])
    ap.add_argument("--reefs", help="HELCOM Reefs 1170 raster or polygons")
    ap.add_argument("--res", type=float, default=2.0, help="analysis resolution, m (mosaic is read decimated)")
    ap.add_argument("--visible-depth", type=float, default=6.0, help="deepest water where the seabed shows, m")
    ap.add_argument("--k", type=float, default=2.0, help="darker than depth-typical by k robust SD = dark pixel")
    ap.add_argument("--dark-hi", type=float, default=0.25); ap.add_argument("--dark-lo", type=float, default=0.08)
    ap.add_argument("--min-visible", type=float, default=0.25)
    ap.add_argument("--zoom", nargs=4, type=float, help="lon_min lat_min lon_max lat_max for a close-up figure")
    ap.add_argument("--out", default="runs/ortho_compare")
    a = ap.parse_args()
    sys.path.insert(0, HERE); import sources
    os.makedirs(a.out, exist_ok=True); sources.carry_args(a.out, a)
    if a.data:
        d = lambda f: os.path.join(a.data, f)
        if not a.substrate and os.path.exists(d("substrate.geojson")): a.substrate = d("substrate.geojson")
        if not a.glacial: a.glacial = [d(f) for f in ("quat_lithology.geojson", "geomorph_polys.geojson") if os.path.exists(d(f))]
        if not a.reefs and os.path.exists(d("reefs_helcom_1170.tif")): a.reefs = d("reefs_helcom_1170.tif")
    print("Layers:", {"substrate": a.substrate, "glacial": a.glacial, "reefs": a.reefs}, file=sys.stderr)

    import rasterio
    from rasterio import features as rf
    from rasterio.enums import Resampling
    from rasterio.warp import reproject, transform, transform_geom
    from rasterio.transform import Affine
    from scipy import ndimage as ndi
    from reef_nursery_overlay import to_grid

    # ---------- photo at --res
    mpath = os.path.join(a.ortho, "ortho_mosaic.tif") if os.path.isdir(a.ortho) else a.ortho
    with rasterio.open(mpath) as s:
        crs = s.crs; f = a.res / s.res[0]
        H, W = int(s.height / f), int(s.width / f)
        img = s.read([1, 2, 3], out_shape=(3, H, W), resampling=Resampling.average).astype("float32")
        ftr = s.transform * Affine.scale(s.width / W, s.height / H)
    R, G, B = img; valid = (R + G + B) > 0
    L = 0.299 * R + 0.587 * G + 0.114 * B
    print(f"Photo {W} x {H} px at {a.res:g} m", file=sys.stderr)

    # ---------- screen grid and maps on it
    with rasterio.open(a.erratic) as s:
        etr, ecrs = s.transform, s.crs
        score, cat, edepth = s.read(1), s.read(2), s.read(3)
    eshape = score.shape
    depth = np.full((H, W), np.nan, "float32")   # positive down, smooth
    reproject(edepth.astype("float32"), depth, src_transform=etr, src_crs=ecrs, dst_transform=ftr, dst_crs=crs,
              src_nodata=np.nan, dst_nodata=np.nan, resampling=Resampling.bilinear)
    geom = lambda g: transform_geom("EPSG:4326", ecrs, g)

    sub = np.zeros(eshape, "int32"); names = ["unmapped"]; subfeats = []
    if a.substrate:
        subfeats = load(a.substrate); fld = substrate_field(subfeats); idx = {}
        shp = []
        for ft in subfeats:
            v = str((ft.get("properties") or {}).get(fld)); shp.append((geom(ft["geometry"]), idx.setdefault(v, len(idx) + 1)))
        names += sorted(idx, key=idx.get)
        sub = rf.rasterize(shp, out_shape=eshape, transform=etr, fill=0, dtype="int32")
        print("Substrate field:", fld, "classes:", names[1:], file=sys.stderr)
    coarse_ids = [i for i, n in enumerate(names) if i and re.search(COARSE, n, re.I)]
    coarse = np.isin(sub, coarse_ids)
    glac = np.zeros(eshape, bool)
    for p in a.glacial:
        shp = [(geom(ft["geometry"]), 1) for ft in load(p)
               if re.search(GLACIAL, " ".join(str(v) for v in (ft.get("properties") or {}).values()), re.I)]
        if shp: glac |= rf.rasterize(shp, out_shape=eshape, transform=etr, fill=0, dtype="uint8").astype(bool)
    reef = to_grid(a.reefs, eshape, etr, ecrs)[0] if a.reefs else np.zeros(eshape, bool)

    # ---------- dark pixels
    water = valid & np.isfinite(depth) & (depth > 0) & (B > R) & (G >= R - 5)
    vis = water & (depth <= a.visible_depth)
    if vis.sum() < 1000: raise SystemExit("Almost no visible shallow water in the photo area: check --visible-depth and the inputs.")
    bins = np.clip((depth / 0.5).astype("int32"), 0, int(a.visible_depth / 0.5) + 1)
    nb = bins.max() + 1; expect = np.zeros(nb, "float32")
    for b in range(nb):
        m = vis & (bins == b)
        expect[b] = np.median(L[m]) if m.sum() > 200 else np.nan
    ok = np.isfinite(expect)   # smooth in depth (bin centres), so bin edges leave no stripes
    centres = (np.flatnonzero(ok) + 0.5) * 0.5
    resid = np.where(vis, L - np.interp(np.nan_to_num(depth), centres, expect[ok]), np.nan)
    rv = resid[vis]; scale = 1.4826 * np.median(np.abs(rv - np.median(rv)))
    dark = vis & (resid < -a.k * scale)
    m1 = ndi.uniform_filter(np.where(vis, L, 0), 5); m2 = ndi.uniform_filter(np.where(vis, L * L, 0), 5)
    texture = np.sqrt(np.maximum(m2 - m1 * m1, 0))
    print(f"Visible water {vis.sum() * a.res ** 2 / 1e6:.2f} km2; dark {100 * dark.sum() / vis.sum():.0f}% of it "
          f"(robust SD {scale:.1f} brightness units)", file=sys.stderr)

    # ---------- per screen cell
    rr, cc = np.mgrid[0:H, 0:W]
    xs, ys = ftr * (cc + 0.5, rr + 0.5)
    ec, er = ~etr * (xs, ys); ec, er = np.floor(ec).astype("int64"), np.floor(er).astype("int64")
    inside = (er >= 0) & (er < eshape[0]) & (ec >= 0) & (ec < eshape[1])
    lin = np.where(inside, er * eshape[1] + ec, -1).ravel(); keep = lin >= 0; lin = lin[keep]
    n = eshape[0] * eshape[1]
    cnt = lambda m: np.bincount(lin, weights=m.ravel()[keep].astype("float64"), minlength=n).reshape(eshape)
    npx, nvis, ndark = cnt(valid), cnt(vis), cnt(dark)
    tsum = cnt(np.where(vis, texture, 0))
    cell_px = (abs(etr.a) / a.res) ** 2
    visfrac = nvis / cell_px
    looked = (visfrac >= a.min_visible) & (npx >= 0.5 * cell_px)
    dfrac = np.where(nvis > 0, ndark / np.maximum(nvis, 1), np.nan)
    tex = np.where(nvis > 0, tsum / np.maximum(nvis, 1), np.nan)
    pclass = np.full(eshape, "not_visible", object)
    pclass[looked & (dfrac >= a.dark_hi)] = "patchy_dark"
    pclass[looked & (dfrac <= a.dark_lo)] = "pale_even"
    pclass[looked & (dfrac > a.dark_lo) & (dfrac < a.dark_hi)] = "mixed"
    s3 = np.nan_to_num(score) >= 3
    maps_hard = s3 | coarse | reef
    photo_hard = pclass == "patchy_dark"; photo_soft = pclass == "pale_even"
    agree = np.zeros(eshape, "uint8")
    agree[looked & maps_hard & photo_hard] = 1; agree[looked & maps_hard & photo_soft] = 2
    agree[looked & ~maps_hard & photo_hard] = 3; agree[looked & ~maps_hard & photo_soft] = 4

    # ---------- tables
    rows = []
    def group(kind, labels, arr):
        for k, lab in labels:
            m = looked & (arr == k); N = int(m.sum())
            if not N: continue
            rows.append({"by": kind, "class": lab, "cells": N, "mean_dark_frac": round(float(np.nanmean(dfrac[m])), 3),
                         "patchy_dark_%": round(100 * (pclass[m] == "patchy_dark").mean(), 1),
                         "mixed_%": round(100 * (pclass[m] == "mixed").mean(), 1),
                         "pale_even_%": round(100 * (pclass[m] == "pale_even").mean(), 1)})
    group("substrate", list(enumerate(names)), sub)
    group("glacial_source", [(True, "till/moraine mapped"), (False, "no source mapped")], glac)
    group("screen_score", [(k, str(k)) for k in range(4)], np.nan_to_num(score).astype(int))
    group("screen_category", list(enumerate(CATS)), np.nan_to_num(cat).astype(int))
    group("mapped_reef", [(True, "HELCOM reef"), (False, "not mapped reef")], reef)
    for lab, mh in (("screen score 3", s3), ("coarse substrate", coarse), ("HELCOM reef", reef), ("any of the three", maps_hard)):
        m = looked & (photo_hard | photo_soft)
        t = [[int((m & mh & photo_hard).sum()), int((m & mh & photo_soft).sum())],
             [int((m & ~mh & photo_hard).sum()), int((m & ~mh & photo_soft).sum())]]
        pa, kp = kappa(t)
        rows.append({"by": "agreement", "class": lab, "cells": int(np.sum(t)),
                     "both_hard": t[0][0], "maps_hard_photo_soft": t[0][1], "photo_hard_maps_soft": t[1][0], "both_soft": t[1][1],
                     "agreement_%": pa, "kappa": kp})
    keys = []
    for r in rows: keys += [k for k in r if k not in keys]
    with open(os.path.join(a.out, "ortho_compare_summary.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, keys); w.writeheader(); w.writerows(rows)
    print(f"\n{'by':16s} {'class':28s} {'cells':>5s} {'dark':>5s} {'patchy%':>7s} {'pale%':>6s}")
    for r in rows:
        if r["by"] == "agreement":
            print(f"{'agreement':16s} {r['class']:28s} {r['cells']:5d}  both hard {r['both_hard']}, maps only {r['maps_hard_photo_soft']}, "
                  f"photo only {r['photo_hard_maps_soft']}, both soft {r['both_soft']}: {r['agreement_%']}% kappa {r['kappa']}")
        else:
            print(f"{r['by']:16s} {r['class'][:28]:28s} {r['cells']:5d} {r['mean_dark_frac']:5.2f} {r['patchy_dark_%']:7.1f} {r['pale_even_%']:6.1f}")

    ri, ci = np.nonzero(looked)
    cx, cy = etr * (ci + 0.5, ri + 0.5); lon, lat = transform(ecrs, "EPSG:4326", list(cx), list(cy))
    with open(os.path.join(a.out, "ortho_compare_cells.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "col", "lat", "lon", "depth_m", "visible_frac", "dark_frac", "texture", "photo_class",
                    "screen_score", "screen_category", "substrate", "glacial_source", "helcom_reef", "agreement"])
        for k, (r, c) in enumerate(zip(ri, ci)):
            w.writerow([r, c, round(lat[k], 5), round(lon[k], 5), round(float(edepth[r, c]), 1), round(float(visfrac[r, c]), 2),
                        round(float(dfrac[r, c]), 3), round(float(tex[r, c]), 1), pclass[r, c],
                        "" if np.isnan(score[r, c]) else int(score[r, c]), CATS[int(cat[r, c])] if np.isfinite(cat[r, c]) else "",
                        names[sub[r, c]], int(glac[r, c]), int(reef[r, c]), AGREE.get(int(agree[r, c]), "")])
    with rasterio.open(os.path.join(a.out, "ortho_agreement.tif"), "w", driver="GTiff", width=eshape[1], height=eshape[0],
                       count=2, dtype="float32", crs=ecrs, transform=etr, nodata=np.nan, compress="deflate") as dd:
        dd.write(np.where(agree > 0, agree, np.nan).astype("float32"), 1)
        dd.write(np.where(looked, dfrac, np.nan).astype("float32"), 2)
        dd.descriptions = ("agreement_1both_2maps_3photo_4soft", "dark_frac")

    # ---------- figures
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from matplotlib.colors import ListedColormap
    rgb = np.moveaxis(np.clip(img / 255, 0, 1), 0, -1)
    fext = (ftr.c, ftr.c + W * ftr.a, ftr.f + H * ftr.e, ftr.f)
    eext = (etr.c, etr.c + eshape[1] * etr.a, etr.f + eshape[0] * etr.e, etr.f)
    pal = plt.get_cmap("tab10"); scol = {i: pal((i - 1) % 10) for i in range(1, len(names))}
    rings = []
    for ft in subfeats:
        v = str((ft.get("properties") or {}).get(substrate_field(subfeats)))
        g = geom(ft["geometry"]); polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            for ring in poly: rings.append((names.index(v), np.asarray(ring)))
    def panels(view, fname, title):
        x0, x1, y0, y1 = view
        fig, axs = plt.subplots(2, 2, figsize=(16, 16 * (y1 - y0) / (x1 - x0) + 1.2))
        for ax in axs.flat:
            ax.imshow(rgb, extent=fext); ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_xticks([]); ax.set_yticks([])
        ax = axs[0, 0]; used = set()
        for i, ring in rings:
            if ring[:, 0].max() < x0 or ring[:, 0].min() > x1 or ring[:, 1].max() < y0 or ring[:, 1].min() > y1: continue
            ax.plot(ring[:, 0], ring[:, 1], color=scol.get(i, "w"), lw=1.2); used.add(i)
        ax.legend(handles=[Patch(color=scol[i], label=names[i][:40]) for i in sorted(used)], fontsize=7, loc="lower left")
        ax.set_title("(a) EMODnet substrate polygons on the photo", fontsize=9)
        ax = axs[0, 1]
        xs_, ys_ = np.linspace(eext[0], eext[1], eshape[1]), np.linspace(eext[3], eext[2], eshape[0])
        ax.contour(xs_, ys_, s3.astype(float), levels=[0.5], colors="r", linewidths=1.2)
        if reef.any(): ax.contour(xs_, ys_, reef.astype(float), levels=[0.5], colors="yellow", linewidths=1.2)
        if glac.any(): ax.contour(xs_, ys_, glac.astype(float), levels=[0.5], colors="orange", linewidths=0.8, linestyles="--")
        ax.legend(handles=[Patch(color="r", label="screen score 3"), Patch(color="yellow", label="HELCOM reef 1170"),
                           Patch(color="orange", label="till / moraine mapped")], fontsize=7, loc="lower left")
        ax.set_title("(b) Reef screen and mapped reefs", fontsize=9)
        ax = axs[1, 0]
        ov = np.zeros((H, W, 4), "float32"); ov[dark] = (1, 0.1, 0.6, 0.75); ov[vis & ~dark] = (0.2, 0.9, 1, 0.12)
        ax.imshow(ov, extent=fext)
        ax.set_title(f"(c) Dark pixels (magenta) in visible water 0-{a.visible_depth:g} m (cyan tint)", fontsize=9)
        ax = axs[1, 1]
        cm = ListedColormap(["#1a9850", "#fdae61", "#d73027", "#4575b4"])
        ax.imshow(np.where(agree > 0, agree, np.nan), extent=eext, cmap=cm, vmin=0.5, vmax=4.5, alpha=0.6, interpolation="nearest")
        ax.legend(handles=[Patch(color=cm(i - 1), label=AGREE[i]) for i in range(1, 5)], fontsize=7, loc="lower left")
        ax.set_title("(d) Agreement per 250 m cell ('maps hard' = score 3, coarse substrate or HELCOM reef)", fontsize=9)
        fig.suptitle(title, fontsize=11); fig.tight_layout()
        fig.savefig(os.path.join(a.out, fname), dpi=170, bbox_inches="tight"); plt.close(fig)
    yy, xx = np.nonzero(vis)
    pad = 300
    view = (fext[0] + xx.min() * a.res - pad, fext[0] + xx.max() * a.res + pad, fext[3] - yy.max() * a.res - pad, fext[3] - yy.min() * a.res + pad)
    panels(view, "ortho_compare.png", "Aerial photo vs substrate maps and reef screen (SDFI spring orthophoto; EMODnet; HELCOM)")
    if a.zoom:
        zx, zy = transform("EPSG:4326", crs, [a.zoom[0], a.zoom[2]], [a.zoom[1], a.zoom[3]])
        panels((min(zx), max(zx), min(zy), max(zy)), "ortho_compare_zoom.png", f"Close-up {a.zoom}")
    print(f"\nWrote {a.out}: ortho_compare.png, ortho_compare_cells.csv, ortho_compare_summary.csv, ortho_agreement.tif")

if __name__ == "__main__":
    main()
