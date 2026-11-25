#!/usr/bin/env python3
"""
erratic_overlay.py - where do coarse seabed classes, glacial source deposits and shallow depth
coincide? A screening map of likely glacial-erratic (boulder) ground, cross-referenced with sightings.

Idea: Danish seabed boulders are mostly glacial erratics. Waves and currents winnow the fine
fraction out of till (diamicton) and moraines, leaving a lag of stones and boulders on top. So a
cell is a stronger erratic candidate when it has
  1. a COARSE surface class (rock and boulders, coarse or mixed sediment, gravel, till/diamicton),
  2. a mapped glacial SOURCE (till / diamicton / boulder gravel / moraine / drumlin / esker
     polygon, or within --line-buffer of a moraine line), and
  3. depth inside the winnowing zone (default 0 to --wave-depth m).
Score = number of the three that hold (0-3). Categories:
  lag_on_till_shallow   coarse + source + shallow   (most likely erratic boulder ground)
  lag_on_till_deep      coarse + source, deeper      (relict lag, boulder ridges)
  coarse_no_source      coarse, no mapped source     (could be unmapped till, or bedrock)
  till_buried           source, fine surface         (boulders likely buried under sand/mud)
  other

All inputs are GeoJSON in WGS84 (from fetch_wfs.py / fetch_arcgis.py) plus an optional depth GeoTIFF.
Grid is built in --crs (default EPSG:25832, UTM 32N, metres) at --cell metres.

Usage:
  python erratic_overlay.py --bbox 11.9 55.9 12.7 56.2 \\
      --substrate data/dk/substrate.geojson folk_7cl \\
      --glacial data/dk/quaternary_lithology.geojson lithology1 \\
      --glacial data/dk/geomorphology.geojson landform \\
      --lines data/dk/geomorph_lines.geojson landform \\
      --depth data/dk/emodnet_dtm.tif \\
      --points runs/nest_candidates.csv --months 2,3,4,5 --drop "cruise haul" --out runs/dk_erratics
Omit a FIELD (pass "?") to print the layer's fields and the values of likely class fields.

Short form, after fetch_erratic_inputs.py has filled a folder (fields are picked automatically):
  python erratic_overlay.py --bbox 11.9 55.95 12.7 56.2 --data data/dk_test --points runs/nest_candidates.csv \
      --months 2,3,4,5 --drop "cruise haul" --out runs/dk_erratics_test
"""
import argparse, csv, json, os, re, sys
from collections import Counter, defaultdict
import numpy as np

COARSE = r"rock|boulder|coarse|mixed|gravel|diamict|till|stone|cobble|pebble|lag"
GLACIAL = r"till|diamict|boulder|morain|drumlin|esker|glacial|ice.?rafted|glacio|kame|outwash"
CATS = ["other", "till_buried", "coarse_no_source", "lag_on_till_deep", "lag_on_till_shallow"]

def load(path):
    return [f for f in json.load(open(path, encoding="utf-8"))["features"] if f.get("geometry")]

def describe(path, feats):
    keys = sorted({k for f in feats[:500] for k in (f.get("properties") or {})})
    print(f"\n{path}: {len(feats)} features\n  fields: {keys}")
    for k in keys:
        vals = Counter(str((f.get("properties") or {}).get(k)) for f in feats)
        if 1 < len(vals) <= 40:
            print(f"  {k}: " + "; ".join(f"{v} ({n})" for v, n in vals.most_common(15)))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bbox", nargs=4, type=float, required=True, help="lon_min lat_min lon_max lat_max")
    ap.add_argument("--crs", default="EPSG:25832"); ap.add_argument("--cell", type=float, default=250)
    ap.add_argument("--substrate", nargs=2, metavar=("GEOJSON", "FIELD"), help="surface substrate polygons and class field")
    ap.add_argument("--glacial", nargs=2, action="append", default=[], metavar=("GEOJSON", "FIELD"),
                    help="glacial source polygons (repeatable); features whose FIELD matches --glacial-match count")
    ap.add_argument("--lines", nargs=2, action="append", default=[], metavar=("GEOJSON", "FIELD"),
                    help="moraine / ice-margin lines (repeatable); FIELD '*' takes every line")
    ap.add_argument("--depth", help="elevation GeoTIFF (negative below sea level) e.g. EMODnet DTM")
    ap.add_argument("--depth-positive", action="store_true", help="depth raster is positive down")
    ap.add_argument("--unmapped-match", default=r"restricted|no data|not mapped|unknown|unclassified",
                    help="substrate classes treated as unmapped (left out of areas and use ratios)")
    ap.add_argument("--coarse-match", default=COARSE); ap.add_argument("--glacial-match", default=GLACIAL)
    ap.add_argument("--line-match", default=r"morain|ice.?margin|terminal|push")
    ap.add_argument("--line-buffer", type=float, default=2000, help="metres from a moraine line that count as source")
    ap.add_argument("--wave-depth", type=float, default=10, help="winnowing depth limit, m")
    ap.add_argument("--max-depth", type=float, default=30, help="ignore water deeper than this, m")
    ap.add_argument("--points"); ap.add_argument("--months", default=""); ap.add_argument("--drop", default="")
    ap.add_argument("--min-evidence", type=int, default=0)
    ap.add_argument("--snap-m", type=float, default=1000,
                    help="move a sighting on land / unmapped cells to the nearest mapped seabed cell within this distance")
    ap.add_argument("--data", help="folder from fetch_erratic_inputs.py; fills any layer not given explicitly")
    ap.add_argument("--out", default="runs/erratics")
    a = ap.parse_args()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sources
    sources.carry_args(a.out, a)
    if a.data:
        d = lambda f: os.path.join(a.data, f)
        if not a.substrate and os.path.exists(d("substrate.geojson")): a.substrate = [d("substrate.geojson"), "auto"]
        if not a.glacial:
            a.glacial = [[d(f), fl] for f, fl in (("quat_lithology.geojson", "lithology1"), ("geomorph_polys.geojson", "landform"))
                         if os.path.exists(d(f))]
        if not a.lines and os.path.exists(d("geomorph_lines.geojson")): a.lines = [[d("geomorph_lines.geojson"), "landform"]]
        if not a.depth and os.path.exists(d("emodnet_dtm.tif")): a.depth = d("emodnet_dtm.tif")
        print("Layers:", {"substrate": a.substrate, "glacial": a.glacial, "lines": a.lines, "depth": a.depth}, file=sys.stderr)

    import rasterio
    from rasterio import features as rf
    from rasterio.transform import from_origin
    from rasterio.warp import transform, transform_geom, reproject, Resampling
    from scipy import ndimage as ndi

    layers = ([("substrate", *a.substrate)] if a.substrate else []) + [("glacial", *g) for g in a.glacial] \
             + [("lines", *l) for l in a.lines]
    cache = {p: load(p) for _, p, _ in layers}
    if any(f == "?" for _, _, f in layers):
        for _, p, f in layers:
            if f == "?": describe(p, cache[p])
        return

    # grid
    bx, by = transform("EPSG:4326", a.crs, [a.bbox[0], a.bbox[2], a.bbox[0], a.bbox[2]], [a.bbox[1], a.bbox[1], a.bbox[3], a.bbox[3]])
    x0, x1, y0, y1 = min(bx), max(bx), min(by), max(by)
    W, H = int(np.ceil((x1 - x0) / a.cell)), int(np.ceil((y1 - y0) / a.cell))
    tr = from_origin(x0, y1, a.cell, a.cell); shape = (H, W)
    print(f"Grid {W} x {H} cells of {a.cell:g} m in {a.crs}", file=sys.stderr)
    geom = lambda g: transform_geom("EPSG:4326", a.crs, g)

    # 1. substrate class index per cell (0 = unmapped)
    names = ["unmapped"]; sub = np.zeros(shape, "int32")
    if a.substrate:
        p, fld = a.substrate; idx = {}
        if fld == "auto":
            keys = [k for k in {k for f in cache[p][:200] for k in (f.get("properties") or {})}]
            for pat in (r"folk.*7.*txt", r"folk.*5.*txt", r"folk.*txt", r"folk.*7", r"folk.*5", r"folk", r"substrat", r"class"):
                hit = sorted(k for k in keys if re.search(pat, k, re.I))
                if hit: fld = hit[0]; break
            else: raise SystemExit(f"No substrate class field found in {p}; fields are {sorted(keys)}. Pass it instead of 'auto'.")
            print("Substrate field:", fld, file=sys.stderr)
        shapes = []
        for f in cache[p]:
            v = str((f.get("properties") or {}).get(fld)); i = idx.setdefault(v, len(idx) + 1)
            shapes.append((geom(f["geometry"]), i))
        names += sorted(idx, key=idx.get)
        sub = rf.rasterize(shapes, out_shape=shape, transform=tr, fill=0, dtype="int32")
    ure = re.compile(a.unmapped_match, re.I)
    unm = [i for i, n in enumerate(names) if i and ure.search(n)]
    if unm: print("Treated as unmapped:", [names[i] for i in unm], file=sys.stderr); sub[np.isin(sub, unm)] = 0
    cre = re.compile(a.coarse_match, re.I)
    coarse_ids = [i for i, n in enumerate(names) if i and cre.search(n)]
    coarse = np.isin(sub, coarse_ids)
    print("Coarse classes:", [names[i] for i in coarse_ids] or "none (check --coarse-match)", file=sys.stderr)

    # 2. glacial source polygons and lines
    gre = re.compile(a.glacial_match, re.I); source = np.zeros(shape, bool); hits = Counter()
    for p, fld in a.glacial:
        shp = []
        present = {k for f in cache[p][:200] for k in (f.get("properties") or {})}
        flds = [k for k in fld.split(",") if k in present]
        if not flds:
            if cache[p]: print(f"  {fld} not in {p}; matching on all fields", file=sys.stderr)
            flds = sorted(present)
        for f in cache[p]:
            props = f.get("properties") or {}
            v = " ".join(str(props.get(k, "")) for k in flds)
            if gre.search(v): shp.append((geom(f["geometry"]), 1)); hits[v[:60]] += 1
        if shp: source |= rf.rasterize(shp, out_shape=shape, transform=tr, fill=0, dtype="uint8").astype(bool)
    lre = re.compile(a.line_match, re.I); line = np.zeros(shape, bool)
    for p, fld in a.lines:
        present = {k for f in cache[p][:200] for k in (f.get("properties") or {})}
        flds = sorted(present) if fld == "*" or fld not in present else [fld]
        shp = [(geom(f["geometry"]), 1) for f in cache[p]
               if lre.search(" ".join(str((f.get("properties") or {}).get(k, "")) for k in flds))]
        print(f"  {len(shp)} moraine lines from {p}", file=sys.stderr)
        if shp: line |= rf.rasterize(shp, out_shape=shape, transform=tr, fill=0, dtype="uint8", all_touched=True).astype(bool)
    d_line = ndi.distance_transform_edt(~line) * a.cell if line.any() else np.full(shape, np.inf)
    source_any = source | (d_line <= a.line_buffer)
    print("Glacial source classes used:", dict(hits.most_common(12)) or "none", file=sys.stderr)

    # 3. depth (positive down)
    depth = np.full(shape, np.nan, "float32")
    if a.depth:
        with rasterio.open(a.depth) as s:
            src = s.read(1, masked=True).filled(np.nan).astype("float32")
            reproject(src, depth, src_transform=s.transform, src_crs=s.crs, dst_transform=tr, dst_crs=a.crs,
                      src_nodata=np.nan, dst_nodata=np.nan, resampling=Resampling.average)
        depth = depth if a.depth_positive else -depth
        fin = depth[np.isfinite(depth)]; wet = fin[fin > 0]
        if wet.size: print(f"Water depth on grid: {100 * wet.size / fin.size:.0f}% of cells under water, "
                           f"p10 {np.percentile(wet, 10):.1f}  median {np.median(wet):.1f}  p90 {np.percentile(wet, 90):.1f} m", file=sys.stderr)
        else: print("No cells below sea level: the raster may be positive-down already, try --depth-positive", file=sys.stderr)
    has_depth = np.isfinite(depth)
    water = sub > 0 if a.substrate else source   # mapped seabed
    if a.depth:
        water &= has_depth & (depth > 0) & (depth <= a.max_depth)
    shallow = has_depth & (depth > 0) & (depth <= a.wave_depth)

    score = coarse.astype("uint8") + source_any + shallow
    cat = np.zeros(shape, "uint8")
    cat[source_any & ~coarse] = 1
    cat[coarse & ~source_any] = 2
    cat[coarse & source_any & ~shallow] = 3
    cat[coarse & source_any & shallow] = 4
    score[~water] = 0; cat[~water] = 0

    os.makedirs(a.out, exist_ok=True)
    with rasterio.open(os.path.join(a.out, "erratic_grid.tif"), "w", driver="GTiff", width=W, height=H, count=4,
                       dtype="float32", crs=a.crs, transform=tr, nodata=np.nan, compress="deflate") as d:
        for b, arr in enumerate([np.where(water, score, np.nan), np.where(water, cat, np.nan), depth,
                                 np.where(np.isfinite(d_line), d_line, np.nan)], 1):
            d.write(arr.astype("float32"), b)
        d.descriptions = ("score_0_3", "category", "depth_m", "dist_moraine_line_m")

    # cross-tab: substrate x source x depth band (km2)
    bands = [(0, 2, "Z1_0-2"), (2, 5, "Z2_2-5"), (5, 10, "Z3_5-10"), (10, 15, "Z4_10-15"), (15, 1e9, "15+")]
    bnames = [n for _, _, n in bands] + ["no_depth"]
    bidx = np.full(shape, len(bands), "int32")
    for i, (lo, hi, _) in enumerate(bands): bidx[has_depth & (depth > lo) & (depth <= hi)] = i
    cell_km2 = (a.cell / 1000) ** 2; xt = defaultdict(float)
    key = (sub[water].astype("int64") * 2 + source_any[water]) * (len(bnames) + 1) + bidx[water]
    for k, n in zip(*np.unique(key, return_counts=True)):
        si, rest = divmod(int(k), 2 * (len(bnames) + 1)); src, bi = divmod(rest, len(bnames) + 1)
        xt[(names[si], "glacial_source" if src else "no_source", bnames[bi])] += n * cell_km2
    with open(os.path.join(a.out, "crosstab_substrate_source_depth.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["substrate", "glacial_source", "depth_band", "area_km2"])
        for k in sorted(xt): w.writerow([*k, round(xt[k], 3)])
    area_cat = Counter({CATS[k]: float((cat[water] == k).sum()) * cell_km2 for k in range(len(CATS))})

    # sightings
    summary = []
    if a.points:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from overlay_points import load_points
        pts = load_points(a.points, a.bbox, a.min_evidence, a.months, None, a.drop)
        px, py = transform("EPSG:4326", a.crs, [p[0] for p in pts], [p[1] for p in pts]) if pts else ([], [])
        rows, used, why = [], Counter(), Counter()
        d_w, (wr_, wc_) = ndi.distance_transform_edt(~water, return_indices=True)
        deep = has_depth & (depth > a.max_depth)
        for (lon, lat, r), x, y in zip(pts, px, py):
            c, rr = ~tr * (x, y); rr, c = int(rr), int(c); moved = 0.0
            inside = 0 <= rr < H and 0 <= c < W and water[rr, c]
            if 0 <= rr < H and 0 <= c < W and not inside:
                if deep[rr, c]: why["deeper_than_max_depth"] += 1
                elif d_w[rr, c] * a.cell <= a.snap_m:
                    moved = float(d_w[rr, c] * a.cell); rr, c = int(wr_[rr, c]), int(wc_[rr, c]); inside = True
                elif has_depth[rr, c] and depth[rr, c] > 0: why["water_but_substrate_unmapped"] += 1
                else: why["on_land_beyond_snap"] += 1
            elif not inside: why["outside_box"] += 1
            k = CATS[cat[rr, c]] if inside else "outside_mapped_seabed"; used[k] += 1
            rows.append({"lat": lat, "lon": lon, "category": k, "moved_m": round(moved) if inside else "", "score": int(score[rr, c]) if inside else "",
                         "substrate": names[sub[rr, c]] if inside else "", "depth_m": round(float(depth[rr, c]), 1) if inside and has_depth[rr, c] else "",
                         "glacial_source": bool(source_any[rr, c]) if inside else "",
                         "dist_moraine_line_m": round(float(d_line[rr, c])) if inside and np.isfinite(d_line[rr, c]) else "",
                         "date": r.get("date", ""), "id": r.get("id", ""), "url": r.get("url", "")})
        if rows:
            with open(os.path.join(a.out, "points_with_erratic.csv"), "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
        n_in = sum(v for k, v in used.items() if k != "outside_mapped_seabed"); A = sum(area_cat.values())
        for k in CATS[::-1]:
            sp = used[k] / n_in if n_in else 0; sa = area_cat[k] / A if A else 0
            summary.append({"category": k, "points": used[k], "point_share": round(sp, 3), "area_km2": round(area_cat[k], 2),
                            "area_share": round(sa, 3), "use_ratio": round(sp / sa, 2) if sa and n_in else None})
        n_moved = sum(1 for r_ in rows if r_["moved_m"] not in ("", 0))
        print(f"{len(pts)} sightings kept, {n_in} on mapped seabed ({n_moved} moved up to {a.snap_m:g} m from shore), "
              f"{used['outside_mapped_seabed']} outside: {dict(why)}")
    else:
        A = sum(area_cat.values())
        summary = [{"category": k, "area_km2": round(area_cat[k], 2), "area_share": round(area_cat[k] / A, 3) if A else 0} for k in CATS[::-1]]
    with open(os.path.join(a.out, "categories.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, list(summary[0])); w.writeheader(); w.writerows(summary)
    for s in summary: print("  " + "  ".join(f"{k}={v}" for k, v in s.items()))

    # preview
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap; import matplotlib.patches as mp
    cols = ["#d9d9d9", "#9ecae1", "#fdd49e", "#fc8d59", "#b30000"]
    img = np.where(water, cat, np.nan)
    fig, ax = plt.subplots(figsize=(9, 9 * H / max(W, 1) + 1))
    ax.imshow(img, cmap=ListedColormap(cols), vmin=-0.5, vmax=4.5, extent=(x0, x0 + W * a.cell, y1 - H * a.cell, y1), interpolation="nearest")
    if line.any():
        ax.contour(np.flipud(line.astype(float)), levels=[0.5], colors="k", linewidths=0.6,
                   extent=(x0, x0 + W * a.cell, y1 - H * a.cell, y1), origin="lower")
    if a.points and pts:
        ax.scatter(px, py, s=8, c="k", marker="o", label="sightings")
    ax.legend(handles=[mp.Patch(color=c, label=n) for c, n in zip(cols, CATS)] + ([plt.Line2D([], [], color="k", marker="o", ls="", label="sightings")] if a.points else []),
              loc="lower left", fontsize=7)
    ax.set_title(f"Erratic screening: coarse + glacial source + depth <= {a.wave_depth:g} m"); ax.set_xticks([]); ax.set_yticks([])
    fig.savefig(os.path.join(a.out, "erratic_preview.png"), dpi=150, bbox_inches="tight")
    print("Results in", a.out)

if __name__ == "__main__":
    main()
