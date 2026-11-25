#!/usr/bin/env python3
"""
reef_nursery_overlay.py - (1) check the glacial-erratic screen against mapped reefs, (2) measure how far
reefs are from nursery habitat, (3) draw them together.

Inputs
  --erratic   erratic_grid.tif from erratic_overlay.py (band 1 score 0-3, band 2 category)
  --reefs     mapped reefs: presence raster (HELCOM Reefs 1170, value 1) or polygons (.geojson)
  --surveyed  optional polygons where reefs were mapped (Natura 2000 sites); without it the whole
              area covered by the reef raster counts as surveyed, which makes precision look worse
  --nursery   nursery_grid.tif from nursery_proxy.py (1 shore_hard, 2 shallow_hard, 3 eelgrass, 4 kelp_hard, 5 shore_soft)

(1) On the erratic grid, inside surveyed mapped seabed:
    recall    = share of mapped-reef cells the screen puts in each score / category
    precision = share of each score / category that is mapped reef; lift = precision / base rate
(2) On the nursery grid: distance from every reef cell (screen score 3, mapped reef, both) to the nearest
    hard nursery (shore_hard or shallow_hard) and to eelgrass; shares within 1, 2, 5, 10 km.

Usage:
  python reef_nursery_overlay.py --erratic runs/dk_erratics/erratic_grid.tif --reefs data/dk/reefs_helcom_1170.tif \\
      --surveyed data/dk/n2000_sites.geojson --nursery runs/dk_nursery/nursery_grid.tif --out runs/dk_reef_nursery
"""
import argparse, csv, json, os, sys
import numpy as np

CATS = ["other", "till_buried", "coarse_no_source", "lag_on_till_deep", "lag_on_till_shallow"]

def to_grid(path, shape, tr, crs, value=1, polygon_all_touched=False):
    """Presence mask of a raster (== value, or >= 1) or polygon file on the target grid."""
    import rasterio
    from rasterio import features as rf
    from rasterio.warp import reproject, Resampling, transform_geom
    if path.lower().endswith((".geojson", ".json")):
        feats = [f for f in json.load(open(path, encoding="utf-8"))["features"] if f.get("geometry")]
        if not feats: return np.zeros(shape, bool), np.zeros(shape, bool)
        shp = [(transform_geom("EPSG:4326", crs, f["geometry"]), 1) for f in feats]
        m = rf.rasterize(shp, out_shape=shape, transform=tr, fill=0, dtype="uint8", all_touched=polygon_all_touched).astype(bool)
        return m, np.ones(shape, bool)
    dst = np.full(shape, 255, "uint8")
    with rasterio.open(path) as s:
        src = s.read(1); nod = s.nodata
        src = np.where(np.isfinite(src), src, 255) if src.dtype.kind == "f" else src
        src = src.astype("float32"); valid = np.ones(src.shape, bool) if nod is None else (src != nod)
        code = np.where(~valid, 255, np.where(src >= value, 1, 0)).astype("uint8")
        reproject(code, dst, src_transform=s.transform, src_crs=s.crs, dst_transform=tr, dst_crs=crs,
                  src_nodata=255, dst_nodata=255, resampling=Resampling.nearest)
    return dst == 1, dst != 255

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--erratic", required=True); ap.add_argument("--reefs", required=True)
    ap.add_argument("--surveyed"); ap.add_argument("--nursery")
    ap.add_argument("--bands-km", default="1,2,5,10"); ap.add_argument("--out", default="runs/reef_nursery")
    a = ap.parse_args()
    import rasterio
    from scipy import ndimage as ndi
    os.makedirs(a.out, exist_ok=True)

    # ---------- (1) screen vs mapped reefs, on the erratic grid
    with rasterio.open(a.erratic) as s:
        score, cat = s.read(1), s.read(2); tr, crs, shape = s.transform, s.crs, s.shape
    seabed = np.isfinite(score)
    reef, covered = to_grid(a.reefs, shape, tr, crs)
    surveyed = covered & seabed
    if a.surveyed and not os.path.exists(a.surveyed):
        print(f"--surveyed file {a.surveyed} not found: using the whole reef-raster area (precision will read low)"); a.surveyed = None
    if a.surveyed:
        sv, _ = to_grid(a.surveyed, shape, tr, crs); surveyed &= sv
    reef_s = reef & surveyed; n_reef = int(reef_s.sum()); n_sv = int(surveyed.sum())
    km2 = (abs(tr.a) / 1000) ** 2
    print(f"Surveyed mapped seabed {n_sv * km2:.0f} km2; mapped reef in it {n_reef * km2:.0f} km2 "
          f"(base rate {n_reef / max(n_sv, 1):.3f})")
    if n_reef == 0: print("No mapped reef inside the surveyed area: check the --reefs and --surveyed files.")
    base = n_reef / max(n_sv, 1); rows = []
    for kind, arr, labels in (("score", score, {k: f"score {k}" for k in range(4)}), ("category", cat, dict(enumerate(CATS)))):
        for k, lab in labels.items():
            m = surveyed & (arr == k); n = int(m.sum()); hit = int((m & reef).sum())
            rows.append({"by": kind, "class": lab, "area_km2": round(n * km2, 1), "reef_km2": round(hit * km2, 1),
                         "recall": round(hit / n_reef, 3) if n_reef else None,
                         "precision": round(hit / n, 3) if n else None,
                         "lift": round(hit / n / base, 2) if n and base else None})
    with open(os.path.join(a.out, "screen_vs_mapped_reefs.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f"{'class':24s} {'area_km2':>9s} {'reef_km2':>9s} {'recall':>7s} {'precision':>9s} {'lift':>5s}")
    for r in rows: print(f"{r['class']:24s} {r['area_km2']:9.1f} {r['reef_km2']:9.1f} {str(r['recall']):>7s} {str(r['precision']):>9s} {str(r['lift']):>5s}")

    # ---------- (2) reefs vs nursery, on the nursery grid
    if a.nursery:
        from rasterio.warp import reproject, Resampling
        with rasterio.open(a.nursery) as s:
            ncls = s.read(1); ntr, ncrs, nshape = s.transform, s.crs, s.shape
        res = abs(ntr.a) / 1000.0
        def onto(arr, fill):
            d = np.full(nshape, fill, "uint8")
            reproject(arr.astype("uint8"), d, src_transform=tr, src_crs=crs, dst_transform=ntr, dst_crs=ncrs,
                      src_nodata=None, dst_nodata=None, resampling=Resampling.nearest)
            return d
        scr3 = onto(np.where(seabed, score, 0) >= 3, 0).astype(bool)
        mreef, _ = to_grid(a.reefs, nshape, ntr, ncrs)
        targets = {"hard_nursery": np.isin(ncls, [1, 2]), "eelgrass": ncls == 3, "any_nursery": np.isin(ncls, [1, 2, 3])}
        dist = {k: (ndi.distance_transform_edt(~m) * res if m.any() else np.full(nshape, np.inf)) for k, m in targets.items()}
        groups = {"screen_score3": scr3, "mapped_reef": mreef, "both": scr3 & mreef, "screen_only": scr3 & ~mreef, "mapped_only": mreef & ~scr3}
        bands = [float(b) for b in a.bands_km.split(",")]; out = []
        for g, m in groups.items():
            n = int(m.sum())
            for t, d in dist.items():
                dv = d[m] if n else np.array([])
                row = {"reef_group": g, "reef_km2": round(n * res * res, 1), "nursery": t,
                       "median_km": round(float(np.median(dv)), 2) if n else None}
                for b in bands: row[f"share_within_{b:g}km"] = round(float((dv <= b).mean()), 3) if n else None
                out.append(row)
        with open(os.path.join(a.out, "reef_to_nursery_distance.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, list(out[0])); w.writeheader(); w.writerows(out)
        print("\nDistance from reef to nursery (median km; share within " + ", ".join(f"{b:g}" for b in bands) + " km):")
        for r in out:
            if r["nursery"] != "any_nursery":
                print(f"  {r['reef_group']:14s} -> {r['nursery']:13s} {str(r['median_km']):>6s}  "
                      + " ".join(str(r[f'share_within_{b:g}km']) for b in bands))

        # ---------- (3) combined map on the nursery grid
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        from matplotlib.colors import ListedColormap; import matplotlib.patches as mp
        img = np.full(nshape, np.nan)
        img[ncls != 255] = 0                       # water
        img[targets["eelgrass"]] = 1; img[targets["hard_nursery"]] = 2
        img[mreef & ~scr3] = 3; img[scr3 & ~mreef] = 4; img[scr3 & mreef] = 5
        labs = ["water", "eelgrass", "hard nursery (shore / 0-3 m)", "mapped reef only", "screen score 3 only", "screen 3 + mapped reef"]
        cols = ["#eeeeee", "#41ab5d", "#7f2704", "#6baed6", "#fdae6b", "#cb181d"]
        H, W = nshape; x0, y1 = ntr.c, ntr.f
        fig, ax = plt.subplots(figsize=(10, 10 * H / max(W, 1) + 1))
        ax.imshow(img, cmap=ListedColormap(cols), vmin=-0.5, vmax=5.5, interpolation="nearest",
                  extent=(x0, x0 + W * abs(ntr.a), y1 - H * abs(ntr.a), y1))
        ax.legend(handles=[mp.Patch(color=c, label=l) for c, l in zip(cols, labs)], loc="lower left", fontsize=7)
        ax.set_title("Reefs (screened and mapped) and nursery habitat"); ax.set_xticks([]); ax.set_yticks([])
        fig.savefig(os.path.join(a.out, "reef_nursery_map.png"), dpi=170, bbox_inches="tight")
    print("Results in", a.out)

if __name__ == "__main__":
    main()
