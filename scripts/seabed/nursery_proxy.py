#!/usr/bin/env python3
"""
nursery_proxy.py - a proxy map of lumpfish juvenile (nursery) habitat, since no direct map exists.

What juveniles use (parameters/habitat_components.csv): shoreline algae and intertidal pools
(F3 Fucus, prey A5 harpacticoids, 0-2 m), drift weed sourced from attached algae (F6), kelp on
stable stones (F2, 3 m+). Eelgrass (F1) is shown separately: no source reports lumpfish juveniles
using it.

Classes (first match wins):
  1 shore_hard     water cell next to land, on coarse/hard substrate  (Fucus, rock pools)
  2 shallow_hard   coarse/hard substrate 0-3 m                        (Fucus belt)
  3 eelgrass       HELCOM eelgrass present, 0-8 m                     (indirect, unproven for lumpfish)
  4 kelp_hard      coarse/hard substrate 3-10 m                       (kelp; juveniles reported with kelp)
  5 shore_soft     water cell next to land, on sand/mud
Substrate polygons often stop short of the coast, so shore cells take the class of the nearest
mapped substrate within --fill-m metres.

Usage (after fetch_erratic_inputs.py and fetch_nursery_inputs.py):
  python nursery_proxy.py --bbox 11.9 55.95 12.7 56.2 --data data/dk_test --out runs/dk_nursery_test
"""
import argparse, csv, json, os, re, sys
import numpy as np

COARSE = r"rock|boulder|coarse|mixed|gravel|diamict|till|stone|cobble|pebble|lag"
UNMAPPED = r"restricted|no data|not mapped|unknown|unclassified"
CLASSES = ["other_water", "shore_hard", "shallow_hard", "eelgrass", "kelp_hard", "shore_soft"]
COLS = ["#e8e8e8", "#7f2704", "#d94801", "#41ab5d", "#fdae6b", "#c6dbef"]

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bbox", nargs=4, type=float, required=True)
    ap.add_argument("--data", required=True, help="folder with substrate.geojson, emodnet_dtm.tif [, eelgrass_helcom.tif]")
    ap.add_argument("--substrate-field", default="auto"); ap.add_argument("--eelgrass", help="presence raster (default <data>/eelgrass_helcom.tif)")
    ap.add_argument("--crs", default="EPSG:25832"); ap.add_argument("--cell", type=float, default=100)
    ap.add_argument("--shallow", type=float, default=3); ap.add_argument("--kelp-max", type=float, default=10)
    ap.add_argument("--eelgrass-max", type=float, default=8); ap.add_argument("--fill-m", type=float, default=1000)
    ap.add_argument("--coarse-match", default=COARSE); ap.add_argument("--unmapped-match", default=UNMAPPED)
    ap.add_argument("--out", default="runs/nursery")
    a = ap.parse_args()
    import rasterio
    from rasterio import features as rf
    from rasterio.transform import from_origin
    from rasterio.warp import transform, transform_geom, reproject, Resampling
    from scipy import ndimage as ndi

    bx, by = transform("EPSG:4326", a.crs, [a.bbox[0], a.bbox[2], a.bbox[0], a.bbox[2]], [a.bbox[1], a.bbox[1], a.bbox[3], a.bbox[3]])
    x0, x1, y0, y1 = min(bx), max(bx), min(by), max(by)
    W, H = int(np.ceil((x1 - x0) / a.cell)), int(np.ceil((y1 - y0) / a.cell)); shape = (H, W)
    tr = from_origin(x0, y1, a.cell, a.cell)
    print(f"Grid {W} x {H} cells of {a.cell:g} m", file=sys.stderr)

    # depth (positive down; land <= 0)
    elev = np.full(shape, np.nan, "float32")
    with rasterio.open(os.path.join(a.data, "emodnet_dtm.tif")) as s:
        reproject(s.read(1, masked=True).filled(np.nan).astype("float32"), elev, src_transform=s.transform, src_crs=s.crs,
                  dst_transform=tr, dst_crs=a.crs, src_nodata=np.nan, dst_nodata=np.nan, resampling=Resampling.bilinear)
    depth = -elev; water = np.isfinite(depth) & (depth > 0); land = np.isfinite(depth) & (depth <= 0)
    shore = water & ndi.binary_dilation(land, structure=np.ones((3, 3), bool))

    # substrate -> coarse flag, filled to the coast from the nearest mapped cell
    feats = [f for f in json.load(open(os.path.join(a.data, "substrate.geojson"), encoding="utf-8"))["features"] if f.get("geometry")]
    fld = a.substrate_field
    if fld == "auto":
        keys = {k for f in feats[:200] for k in (f.get("properties") or {})}
        for pat in (r"folk.*7.*txt", r"folk.*5.*txt", r"folk.*txt", r"folk", r"substrat"):
            hit = sorted(k for k in keys if re.search(pat, k, re.I))
            if hit: fld = hit[0]; break
    cre, ure = re.compile(a.coarse_match, re.I), re.compile(a.unmapped_match, re.I)
    shapes = []
    for f in feats:
        v = str((f.get("properties") or {}).get(fld, ""))
        if ure.search(v): continue
        shapes.append((transform_geom("EPSG:4326", a.crs, f["geometry"]), 2 if cre.search(v) else 1))
    sub = rf.rasterize(shapes, out_shape=shape, transform=tr, fill=0, dtype="uint8") if shapes else np.zeros(shape, "uint8")
    d_map, (ir, ic) = ndi.distance_transform_edt(sub == 0, return_indices=True)
    filled = np.where(d_map * a.cell <= a.fill_m, sub[ir, ic], 0)
    hard = filled == 2; soft = filled == 1
    print(f"Substrate field {fld}; shore cells {int(shore.sum())}, of which mapped {int((shore & (filled > 0)).sum())}", file=sys.stderr)

    # eelgrass presence
    eel = np.zeros(shape, bool); ep = a.eelgrass or os.path.join(a.data, "eelgrass_helcom.tif")
    if os.path.exists(ep):
        e = np.zeros(shape, "float32")
        with rasterio.open(ep) as s:
            src = s.read(1).astype("float32")
            if s.nodata is not None: src[src == s.nodata] = 0
            reproject(src, e, src_transform=s.transform, src_crs=s.crs, dst_transform=tr, dst_crs=a.crs, resampling=Resampling.nearest)
        eel = (e >= 1) & water & (depth <= a.eelgrass_max)
        print(f"Eelgrass cells: {int(eel.sum())} (HELCOM 1 km presence, so blocky)", file=sys.stderr)
    else:
        print("No eelgrass raster; run fetch_nursery_inputs.py to add it", file=sys.stderr)

    cls = np.zeros(shape, "uint8")
    for k, m in [(5, shore & soft), (4, water & hard & (depth > a.shallow) & (depth <= a.kelp_max)), (3, eel),
                 (2, water & hard & (depth <= a.shallow)), (1, shore & hard)]:
        cls[m] = k   # later assignments win, so the list runs lowest to highest priority
    cls[~water] = 255

    os.makedirs(a.out, exist_ok=True)
    with rasterio.open(os.path.join(a.out, "nursery_grid.tif"), "w", driver="GTiff", width=W, height=H, count=1, dtype="uint8",
                       crs=a.crs, transform=tr, nodata=255, compress="deflate") as d:
        d.write(cls, 1); d.update_tags(classes=json.dumps(CLASSES))
    km2 = (a.cell / 1000) ** 2
    rows = [{"class": n, "area_km2": round(float((cls == k).sum()) * km2, 2)} for k, n in enumerate(CLASSES)]
    shore_n = int(shore.sum())
    rows.append({"class": "shore_cells_hard_share", "area_km2": round(float((shore & hard).sum()) / shore_n, 3) if shore_n else 0})
    with open(os.path.join(a.out, "nursery_areas.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, ["class", "area_km2"]); w.writeheader(); w.writerows(rows)
    for r in rows: print(f"  {r['class']:24s} {r['area_km2']}")

    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap; import matplotlib.patches as mp
    img = np.where(cls == 255, np.nan, cls).astype(float)
    fig, ax = plt.subplots(figsize=(9, 9 * H / max(W, 1) + 1))
    ext = (x0, x0 + W * a.cell, y1 - H * a.cell, y1)
    ax.imshow(np.where(land, 1, np.nan), cmap=ListedColormap(["#f4f1e8"]), extent=ext, interpolation="nearest")
    ax.imshow(img, cmap=ListedColormap(COLS), vmin=-0.5, vmax=5.5, extent=ext, interpolation="nearest")
    ax.legend(handles=[mp.Patch(color=c, label=n) for c, n in zip(COLS, CLASSES)], loc="lower left", fontsize=7)
    ax.set_title("Lumpfish nursery proxy (juvenile habitat)"); ax.set_xticks([]); ax.set_yticks([])
    fig.savefig(os.path.join(a.out, "nursery_preview.png"), dpi=150, bbox_inches="tight")
    print("Results in", a.out)

if __name__ == "__main__":
    main()
