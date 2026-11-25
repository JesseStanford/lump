#!/usr/bin/env python3
"""
fetch_wfs.py - list layers on an OGC WFS, or download one layer inside a lat/lon box as GeoJSON.

Usage:
  python fetch_wfs.py --url <wfs> --list [--grep substrate]
  python fetch_wfs.py --url <wfs> --layer <typeName> --bbox 11.9 55.6 12.8 56.2 --out data/dk/substrate.geojson

Bbox is lon_min lat_min lon_max lat_max (WGS84). Output is GeoJSON in WGS84 when the server supports it.
"""
import argparse, json, os, re, sys, urllib.parse, urllib.request

UA = {"User-Agent": "lumpfish-habitat-research/0.1"}

def get(url, params, timeout=300):
    q = url.split("?")[0] + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(q, headers=UA), timeout=timeout) as r:
        return r.read()

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True); ap.add_argument("--list", action="store_true"); ap.add_argument("--grep", default="")
    ap.add_argument("--layer"); ap.add_argument("--bbox", nargs=4, type=float); ap.add_argument("--out", default="layer.geojson")
    ap.add_argument("--version", default="2.0.0"); ap.add_argument("--page", type=int, default=5000)
    a = ap.parse_args()

    if a.list or not a.layer:
        xml = get(a.url, {"service": "WFS", "request": "GetCapabilities", "version": a.version}).decode("utf-8", "replace")
        blocks = re.findall(r"<(?:wfs:)?FeatureType>(.*?)</(?:wfs:)?FeatureType>", xml, re.S)
        for b in blocks:
            name = re.search(r"<(?:wfs:)?Name>([^<]+)<", b); title = re.search(r"<(?:wfs:)?Title>([^<]*)<", b)
            line = f"{name.group(1) if name else '?'}\t{title.group(1) if title else ''}"
            if a.grep.lower() in line.lower(): print(line)
        if not blocks: print(xml[:1500])
        return

    feats, start = [], 0
    while True:
        p = {"service": "WFS", "request": "GetFeature", "version": a.version, "typeNames": a.layer, "typeName": a.layer,
             "outputFormat": "application/json", "srsName": "EPSG:4326", "count": a.page, "maxFeatures": a.page, "startIndex": start}
        if a.bbox:
            x0, y0, x1, y1 = a.bbox
            # WFS 2.0 with EPSG:4326 URN uses lat,lon axis order
            p["bbox"] = f"{y0},{x0},{y1},{x1},urn:ogc:def:crs:EPSG::4326" if a.version.startswith("2") else f"{x0},{y0},{x1},{y1},EPSG:4326"
        raw = get(a.url, p)
        try: gj = json.loads(raw)
        except ValueError:
            print(raw[:1500].decode("utf-8", "replace"), file=sys.stderr)
            raise SystemExit("Server did not return GeoJSON (above). Try --version 1.1.0, or check the layer name with --list.")
        batch = gj.get("features", []); feats += batch
        print(f"  {len(feats)} features", file=sys.stderr)
        if len(batch) < a.page: break
        start += a.page
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    json.dump({"type": "FeatureCollection", "features": feats}, open(a.out, "w"))
    keys = sorted({k for f in feats[:200] for k in (f.get("properties") or {})})
    print(f"Saved {a.out}: {len(feats)} features. Attribute fields: {', '.join(keys[:25])}")

if __name__ == "__main__":
    main()
