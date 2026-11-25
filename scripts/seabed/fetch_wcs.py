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
    ap.add_argument("--out", default="clip.tif"); ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    ids = coverage_ids(a.url)
    if a.list or not ids:
        print("\n".join(ids) if ids else "No coverage ids found; open the GetCapabilities URL in a browser."); return
    cov = a.coverage or ids[0]
    from rasterio.warp import transform
    xs, ys = transform("EPSG:4326", a.crs, [a.lon], [a.lat]); x, y = xs[0], ys[0]
    h = a.half_size; t = a.tile
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    edges = lambda c: [c - h + i * t for i in range(int(np.ceil(2 * h / t)))]
    tiles = [(x0, y0, min(x0 + t, x + h), min(y0 + t, y + h)) for x0 in edges(x) for y0 in edges(y)]
    print(f"Requesting {cov} around {round(x)} {round(y)} in {len(tiles)} tile(s)", file=sys.stderr)
    parts = []
    for i, (x0, y0, x1, y1) in enumerate(tiles):
        params = [("service", "WCS"), ("request", "GetCoverage"), ("version", "2.0.1"), ("coverageId", cov),
                  ("format", "image/tiff"),
                  ("subset", f"{a.axes[0]}({x0:.1f},{x1:.1f})"), ("subset", f"{a.axes[1]}({y0:.1f},{y1:.1f})")]
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
        print(f"  tile {i + 1}/{len(tiles)} ok", file=sys.stderr)
    import rasterio
    from rasterio.merge import merge
    if len(parts) == 1:
        os.replace(parts[0], a.out)
    else:
        srcs = [rasterio.open(pp) for pp in parts]
        mosaic, mtr = merge(srcs); prof = srcs[0].profile
        prof.update(height=mosaic.shape[1], width=mosaic.shape[2], transform=mtr, compress="deflate")
        for sr in srcs: sr.close()
        with rasterio.open(a.out, "w", **prof) as d: d.write(mosaic)
        for pp in parts: os.remove(pp)
    with rasterio.open(a.out) as s:
        z = s.read(1, masked=True)
        print(f"Saved {a.out}: {s.width}x{s.height} px, {abs(s.transform.a)} m, CRS {s.crs}, "
              f"elevation {float(z.min()):.1f} to {float(z.max()):.1f} m, {100 * np.ma.getmaskarray(z).mean():.0f}% nodata")

if __name__ == "__main__":
    main()
