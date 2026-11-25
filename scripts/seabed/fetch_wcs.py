#!/usr/bin/env python3
"""
fetch_wcs.py - download a small GeoTIFF clip from an OGC WCS 2.0.1 service around a point.

Default service: Environment Agency SurfZone DEM 2019 (2 m, merged lidar + nearshore
multibeam, England coast, Open Government Licence; elevations in m to Newlyn / ODN, which is
close to mean sea level). Attribution: "© Environment Agency copyright and/or database
right 2019. All rights reserved."

Usage:
  python fetch_wcs.py --lat 50.6892 --lon -1.0709 --half-size 500 --out data/gb_bembridge/surfzone_2m.tif
  python fetch_wcs.py --list            # show coverage ids offered by the service
  # a lat/lon box instead of a point (tile is in the coverage CRS units, so degrees for EPSG:4326):
  python fetch_wcs.py --url https://ows.emodnet-bathymetry.eu/wcs --coverage emodnet__mean --crs EPSG:4326 \
      --axes Long Lat --bbox 7.5 54.4 15.3 57.9 --tile 1 --out data/dk/emodnet_dtm.tif
"""
import argparse, os, re, sys, time, urllib.error, urllib.parse, urllib.request
import numpy as np

SURFZONE = "https://environment.data.gov.uk/spatialdata/ea-surfzone-dem-2019/wcs"
UA = {"User-Agent": "lumpfish-habitat-research/0.1"}

def fetch(url, params):
    q = url + "?" + urllib.parse.urlencode(params, doseq=True)
    with urllib.request.urlopen(urllib.request.Request(q, headers=UA), timeout=120) as r:
        return r.read(), r.headers.get("Content-Type", "")

def coverage_ids(url):
    xml, _ = fetch(url, {"service": "WCS", "request": "GetCapabilities", "version": "2.0.1"})
    return re.findall(r"<(?:wcs:)?CoverageId>([^<]+)</", xml.decode("utf-8", "replace"))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=SURFZONE)
    ap.add_argument("--coverage", help="coverage id (default: first one the service lists)")
    ap.add_argument("--lat", type=float); ap.add_argument("--lon", type=float)
    ap.add_argument("--half-size", type=float, default=500, help="metres either side of the point")
    ap.add_argument("--crs", default="EPSG:27700", help="CRS of the coverage axes (SurfZone: British National Grid)")
    ap.add_argument("--axes", nargs=2, default=["E", "N"], help="axis labels used in subset= (try x y if E N fails)")
    ap.add_argument("--tile", type=float, default=500, help="request tile size in metres (smaller if the server times out)")
    ap.add_argument("--bbox", nargs=4, type=float, help="lon_min lat_min lon_max lat_max instead of --lat/--lon/--half-size")
    ap.add_argument("--out", default="clip.tif"); ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    ids = coverage_ids(a.url)
    if a.list or not ids:
        print("\n".join(ids) if ids else "No coverage ids found; open the GetCapabilities URL in a browser."); return
    cov = a.coverage or ids[0]
    from rasterio.warp import transform
    t = a.tile
    if a.bbox:
        bx, by = transform("EPSG:4326", a.crs, [a.bbox[0], a.bbox[2], a.bbox[0], a.bbox[2]],
                           [a.bbox[1], a.bbox[1], a.bbox[3], a.bbox[3]])
        X0, X1, Y0, Y1 = min(bx), max(bx), min(by), max(by)
    else:
        xs, ys = transform("EPSG:4326", a.crs, [a.lon], [a.lat]); h = a.half_size
        X0, X1, Y0, Y1 = xs[0] - h, xs[0] + h, ys[0] - h, ys[0] + h
    x, y = (X0 + X1) / 2, (Y0 + Y1) / 2
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    edges = lambda lo, hi: [lo + i * t for i in range(int(np.ceil((hi - lo) / t - 1e-9)))]
    tiles = [(x0, y0, min(x0 + t, X1), min(y0 + t, Y1)) for x0 in edges(X0, X1) for y0 in edges(Y0, Y1)]
    print(f"Requesting {cov} around {x:.4f} {y:.4f} in {len(tiles)} tile(s)", file=sys.stderr)
    parts = []
    for i, (x0, y0, x1, y1) in enumerate(tiles):
        params = [("service", "WCS"), ("request", "GetCoverage"), ("version", "2.0.1"), ("coverageId", cov),
                  ("format", "image/tiff"),
                  ("subset", f"{a.axes[0]}({x0:.6f},{x1:.6f})"), ("subset", f"{a.axes[1]}({y0:.6f},{y1:.6f})")]
        q = a.url + "?" + urllib.parse.urlencode(params)
        for attempt in range(4):
            try:
                with urllib.request.urlopen(urllib.request.Request(q, headers=UA), timeout=300) as r:
                    data, ctype = r.read(), r.headers.get("Content-Type", "")
                break
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
                print(f"  tile {i + 1}: {e}; retrying" if attempt < 3 else f"  tile {i + 1}: {e}", file=sys.stderr)
                if attempt == 3:
                    raise SystemExit("Server kept failing. Try a smaller --tile (e.g. 250) or try again later.")
                time.sleep(5 * (attempt + 1))
        if b"ExceptionReport" in data[:2000] or "xml" in ctype:
            print(data[:1500].decode("utf-8", "replace"), file=sys.stderr)
            raise SystemExit("Service returned an error (above). Try --axes x y, or --list to check the coverage id.")
        part = f"{a.out}.part{i}.tif"; open(part, "wb").write(data); parts.append(part)
        print(f"  tile {i + 1}/{len(tiles)} ok ({describe(part)})", file=sys.stderr)
    mosaic_tiles(parts, a.out)
    for pp in parts: os.remove(pp)
    import rasterio
    with rasterio.open(a.out) as s:
        z = s.read(1); ok = np.isfinite(z)
        if not ok.any():
            raise SystemExit(f"Saved {a.out} but every cell is nodata: the service has no data here.")
        print(f"Saved {a.out}: {s.width}x{s.height} px, {abs(s.transform.a)} m, CRS {s.crs}, "
              f"elevation {z[ok].min():.1f} to {z[ok].max():.1f} m, {100 * (~ok).mean():.0f}% nodata")

def read_clean(path):
    """Read band 1 as float32 with every nodata flavour (declared value, huge negatives, NaN) set to NaN."""
    import rasterio
    with rasterio.open(path) as s:
        z = s.read(1).astype("float32"); nd = s.nodata; tr = s.transform; crs = s.crs
    bad = ~np.isfinite(z) | (np.abs(z) > 1e30)
    if nd is not None and np.isfinite(nd): bad |= np.isclose(z, np.float32(nd))
    z[bad] = np.nan
    return z, tr, crs

def describe(path):
    z, tr, _ = read_clean(path); ok = np.isfinite(z)
    return f"{z.shape[1]}x{z.shape[0]} px, " + (f"{z[ok].min():.1f} to {z[ok].max():.1f} m, {100 * ok.mean():.0f}% valid" if ok.any() else "all nodata")

def mosaic_tiles(parts, out):
    """Place tiles on one grid by their geotransforms (no resampling; tiles share the service grid)."""
    import rasterio
    from rasterio.transform import from_origin
    tiles = [read_clean(p) for p in parts]
    res = abs(tiles[0][1].a)
    x0 = min(t[1].c for t in tiles); y1 = max(t[1].f for t in tiles)
    x1 = max(t[1].c + t[0].shape[1] * res for t in tiles); y0 = min(t[1].f - t[0].shape[0] * res for t in tiles)
    W, H = int(round((x1 - x0) / res)), int(round((y1 - y0) / res))
    grid = np.full((H, W), np.nan, dtype="float32")
    for z, tr, _ in tiles:
        c, r = int(round((tr.c - x0) / res)), int(round((y1 - tr.f) / res))
        h, w = z.shape; dst = grid[r:r + h, c:c + w]; z = z[:dst.shape[0], :dst.shape[1]]
        m = np.isfinite(z) & ~np.isfinite(dst); dst[m] = z[m]
    with rasterio.open(out, "w", driver="GTiff", width=W, height=H, count=1, dtype="float32", crs=tiles[0][2],
                       transform=from_origin(x0, y1, res, res), nodata=float("nan"), compress="deflate") as d:
        d.write(grid, 1)

if __name__ == "__main__":
    main()
