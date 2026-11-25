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
import argparse, os, re, sys, urllib.parse, urllib.request

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
    ap.add_argument("--out", default="clip.tif"); ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    ids = coverage_ids(a.url)
    if a.list or not ids:
        print("\n".join(ids) if ids else "No coverage ids found; open the GetCapabilities URL in a browser."); return
    cov = a.coverage or ids[0]
    from rasterio.warp import transform
    xs, ys = transform("EPSG:4326", a.crs, [a.lon], [a.lat]); x, y = xs[0], ys[0]
    h = a.half_size
    params = [("service", "WCS"), ("request", "GetCoverage"), ("version", "2.0.1"), ("coverageId", cov),
              ("format", "image/tiff"),
              ("subset", f"{a.axes[0]}({x - h:.1f},{x + h:.1f})"), ("subset", f"{a.axes[1]}({y - h:.1f},{y + h:.1f})")]
    q = a.url + "?" + urllib.parse.urlencode(params)
    print("Requesting", cov, "around", round(x), round(y), file=sys.stderr)
    with urllib.request.urlopen(urllib.request.Request(q, headers=UA), timeout=300) as r:
        data, ctype = r.read(), r.headers.get("Content-Type", "")
    if b"ExceptionReport" in data[:2000] or "xml" in ctype:
        print(data[:1500].decode("utf-8", "replace"), file=sys.stderr)
        raise SystemExit("Service returned an error (above). Try --axes x y, or --list to check the coverage id.")
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    open(a.out, "wb").write(data)
    import rasterio
    with rasterio.open(a.out) as s:
        z = s.read(1, masked=True)
        print(f"Saved {a.out}: {s.width}x{s.height} px, {abs(s.transform.a)} m, CRS {s.crs}, "
              f"elevation {float(z.min()):.1f} to {float(z.max()):.1f} m, {100 * z.mask.mean():.0f}% nodata")

if __name__ == "__main__":
    main()
