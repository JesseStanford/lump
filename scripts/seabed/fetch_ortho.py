#!/usr/bin/env python3
"""
fetch_ortho.py - Danish aerial photos (orthophotos) of shallow candidate reefs, to look for boulders.

Source: SDFI / Dataforsyningen WMS (free data, needs a free Dataforsyningen user and token):
  1. create a user at https://dataforsyningen.dk (log in -> "Mine tokens" / "Opret token")
  2. in PowerShell:  $env:DATAFORSYNINGEN_TOKEN = "the token text"
Default service is the spring orthophoto (orto_foraar_DAF). Spring photos are taken before algae and
plankton blooms, so the seabed is often visible down to a few metres. Run --list to see the layers
(older years can be clearer than the latest).

Only 1 km tiles that contain shallow water (0 < depth <= --max-depth on the erratic grid) are fetched,
so a coastal strip costs a fraction of the whole box.

Outputs in --out:
  tiles/ortho_<x>_<y>.tif   full-resolution GeoTIFF tiles (EPSG:25832, --res m, default 0.4)
  ortho_mosaic.tif          the tiles merged at --mosaic-res (default 1 m), for GIS
  ortho_overview.png        overview with screen-score-3 cells outlined
  sources.csv / SOURCES.md  citation (key sdfi_orto_foraar)

Usage:
  python fetch_ortho.py --list
  python fetch_ortho.py --bbox 12.28 56.08 12.48 56.15 --erratic runs/dk_erratics/erratic_grid.tif --out runs/ortho_gilleleje_hornbaek
"""
import argparse, io, os, re, sys, time, urllib.error, urllib.parse, urllib.request
import numpy as np
import warnings
warnings.filterwarnings("ignore", message="Dataset has no geotransform")

HERE = os.path.dirname(os.path.abspath(__file__))
WMS = "https://api.dataforsyningen.dk/orto_foraar_DAF"

def token(a):
    t = a.token or os.environ.get("DATAFORSYNINGEN_TOKEN")
    if not t:
        raise SystemExit("A Dataforsyningen token is needed (free). Create a user at https://dataforsyningen.dk, make a token\n"
                         "under your user page, then in PowerShell:\n  $env:DATAFORSYNINGEN_TOKEN = \"the token text\"\nand run this again.")
    return t

def fetch(url, params, tries=4):
    q = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(q, headers={"User-Agent": "lump-ortho"}), timeout=180) as r:
                return r.read(), r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            body = e.read()[:400]
            if e.code in (401, 403): raise SystemExit(f"Dataforsyningen refused the token (HTTP {e.code}): {body!r}")
            err = f"HTTP {e.code} {body!r}"
        except Exception as e:
            err = str(e)
        time.sleep(3 * (k + 1))
    raise RuntimeError(err)

def layers(url, tok):
    xml, _ = fetch(url, {"service": "WMS", "request": "GetCapabilities", "version": "1.3.0", "token": tok})
    x = xml.decode("utf-8", "replace")
    names = re.findall(r"<Layer[^>]*>\s*<Name>([^<]+)</Name>\s*<Title>([^<]*)</Title>", x)
    return names

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=WMS); ap.add_argument("--layer", help="WMS layer (default: first 'orto_foraar' layer)")
    ap.add_argument("--list", action="store_true"); ap.add_argument("--token")
    ap.add_argument("--bbox", nargs=4, type=float, default=[12.28, 56.08, 12.48, 56.15], help="lon_min lat_min lon_max lat_max")
    ap.add_argument("--erratic", help="erratic_grid.tif: limits tiles to shallow water and outlines score-3 cells")
    ap.add_argument("--max-depth", type=float, default=12); ap.add_argument("--tile-m", type=float, default=1000)
    ap.add_argument("--res", type=float, default=0.4, help="tile resolution, m per pixel")
    ap.add_argument("--mosaic-res", type=float, default=1.0)
    ap.add_argument("--out", default="runs/ortho")
    a = ap.parse_args()
    tok = token(a)
    names = layers(a.url, tok)
    if a.list or not names:
        print("\n".join(f"{n}  ({t})" for n, t in names) or "No layers found in GetCapabilities."); return
    layer = a.layer or next((n for n, _ in names if "orto_foraar" in n.lower()), names[0][0])
    print(f"Layer: {layer}  (others: {', '.join(n for n, _ in names if n != layer)[:300]})", file=sys.stderr)

    import rasterio
    from rasterio.transform import from_origin
    from rasterio.warp import transform, reproject, Resampling
    sys.path.insert(0, HERE); import sources
    crs = "EPSG:25832"
    xs, ys = transform("EPSG:4326", crs, [a.bbox[0], a.bbox[2], a.bbox[0], a.bbox[2]], [a.bbox[1], a.bbox[1], a.bbox[3], a.bbox[3]])
    x0, x1 = np.floor(min(xs) / a.tile_m) * a.tile_m, np.ceil(max(xs) / a.tile_m) * a.tile_m
    y0, y1 = np.floor(min(ys) / a.tile_m) * a.tile_m, np.ceil(max(ys) / a.tile_m) * a.tile_m
    tiles = [(tx, ty) for tx in np.arange(x0, x1, a.tile_m) for ty in np.arange(y0, y1, a.tile_m)]

    score = depth = etr = None
    if a.erratic:
        with rasterio.open(a.erratic) as s:
            from rasterio.windows import from_bounds
            win = from_bounds(x0, y0, x1, y1, s.transform).round_offsets().round_lengths()
            score, depth = s.read(1, window=win, boundless=True, fill_value=np.nan), s.read(3, window=win, boundless=True, fill_value=np.nan)
            etr = s.window_transform(win)
        def shallow(tx, ty):
            c0, r0 = ~etr * (tx, ty + a.tile_m); c1, r1 = ~etr * (tx + a.tile_m, ty)
            d = depth[max(int(r0), 0):max(int(np.ceil(r1)), 0), max(int(c0), 0):max(int(np.ceil(c1)), 0)]
            return bool(np.any((d > 0) & (d <= a.max_depth)))
        tiles = [t for t in tiles if shallow(*t)]
    print(f"{len(tiles)} tiles of {a.tile_m:g} m at {a.res:g} m/pixel", file=sys.stderr)

    tdir = os.path.join(a.out, "tiles"); os.makedirs(tdir, exist_ok=True)
    px = int(round(a.tile_m / a.res)); done = []
    for i, (tx, ty) in enumerate(tiles, 1):
        path = os.path.join(tdir, f"ortho_{int(tx)}_{int(ty)}.tif")
        if os.path.exists(path): done.append(path); continue
        img, ctype = fetch(a.url, {"service": "WMS", "request": "GetMap", "version": "1.3.0", "layers": layer, "styles": "",
                                   "crs": crs, "bbox": f"{tx},{ty},{tx + a.tile_m},{ty + a.tile_m}", "width": px, "height": px,
                                   "format": "image/jpeg", "token": tok})
        if "xml" in ctype or img[:5] == b"<?xml":
            raise SystemExit(f"WMS error for tile {i}: {img[:400]!r}")
        with rasterio.open(io.BytesIO(img)) as src:
            arr = src.read()[:3]
        with rasterio.open(path, "w", driver="GTiff", width=px, height=px, count=3, dtype="uint8", crs=crs,
                           transform=from_origin(tx, ty + a.tile_m, a.res, a.res), compress="jpeg", photometric="ycbcr",
                           tiled=True) as d:
            d.write(arr)
        done.append(path); print(f"  tile {i}/{len(tiles)}", end="\r", file=sys.stderr)
        sources.record(path, f"{a.url} (layer {layer})", f"GetMap {tx},{ty} {a.tile_m:g} m at {a.res:g} m", key="sdfi_orto_foraar")
    print(file=sys.stderr)
    if not done: raise SystemExit("No tiles (box all land or deeper than --max-depth?).")

    # mosaic at --mosaic-res, over the fetched tiles only (decimated reads, pasted into place)
    from rasterio.enums import Resampling as R
    keys = [tuple(map(int, os.path.basename(p)[6:-4].split("_"))) for p in done]
    x0, y0 = min(k[0] for k in keys), min(k[1] for k in keys)
    x1, y1 = max(k[0] for k in keys) + a.tile_m, max(k[1] for k in keys) + a.tile_m
    n = int(round(a.tile_m / a.mosaic_res)); W = int(round((x1 - x0) / a.mosaic_res)); H = int(round((y1 - y0) / a.mosaic_res))
    mtr = from_origin(x0, y1, a.mosaic_res, a.mosaic_res); mos = np.zeros((3, H, W), "uint8")
    for p, (tx, ty) in zip(done, keys):
        with rasterio.open(p) as s:
            arr = s.read(out_shape=(3, n, n), resampling=R.average)
        r = int(round((y1 - ty - a.tile_m) / a.mosaic_res)); c = int(round((tx - x0) / a.mosaic_res))
        mos[:, r:r + n, c:c + n] = arr
    mpath = os.path.join(a.out, "ortho_mosaic.tif")
    with rasterio.open(mpath, "w", driver="GTiff", width=W, height=H, count=3, dtype="uint8", crs=crs, transform=mtr,
                       compress="jpeg", photometric="ycbcr", tiled=True, nodata=0) as d:
        d.write(mos)
    sources.record(mpath, f"{a.url} (layer {layer})", f"mosaic of {len(done)} tiles at {a.mosaic_res:g} m; box {a.bbox}", key="sdfi_orto_foraar")

    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    step = max(1, int(max(W, H) / 3000)); show = np.moveaxis(mos[:, ::step, ::step], 0, -1)
    fig, ax = plt.subplots(figsize=(14, 14 * H / max(W, 1) + 0.5))
    ext = (x0, x1, y0, y1); ax.imshow(show, extent=ext)
    if score is not None:
        sc3 = (np.nan_to_num(score) >= 3).astype(float)
        H2, W2 = sc3.shape
        ex2 = (etr.c, etr.c + W2 * etr.a, etr.f + H2 * etr.e, etr.f)
        ax.contour(np.linspace(ex2[0], ex2[1], W2), np.linspace(ex2[3], ex2[2], H2), sc3, levels=[0.5], colors="r", linewidths=0.6)
    ax.set_title(f"SDFI {layer}: shallow tiles; red = screen score 3 (coarse substrate on till, 0-10 m)", fontsize=9)
    ax.set_xticks([]); ax.set_yticks([])
    fig.savefig(os.path.join(a.out, "ortho_overview.png"), dpi=200, bbox_inches="tight")
    sources.carry_args(a.out, a)
    print(f"{len(done)} tiles in {tdir}; mosaic {mpath}; overview ortho_overview.png")

if __name__ == "__main__":
    main()
