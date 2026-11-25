#!/usr/bin/env python3
"""
fetch_wfs.py - list layers on an OGC WFS, or download one layer inside a lat/lon box as GeoJSON.

Usage:
  python fetch_wfs.py --url <wfs> --list [--grep substrate]
  python fetch_wfs.py --url <wfs> --layer <typeName> --bbox 11.9 55.6 12.8 56.2 --out data/dk/substrate.geojson

Bbox is lon_min lat_min lon_max lat_max (WGS84). Output is GeoJSON in WGS84 when the server supports it.
"""
import argparse, json, os, re, sys, urllib.error, urllib.parse, urllib.request

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

    def params(mode, start):
        p = {"service": "WFS", "request": "GetFeature", "outputFormat": "application/json", "srsName": "EPSG:4326"}
        x0, y0, x1, y1 = a.bbox if a.bbox else (None,) * 4
        if mode in ("v2_paged", "v2_single"):
            p.update(version=a.version, typeNames=a.layer, count=a.page if mode == "v2_paged" else 1000000)
            if mode == "v2_paged": p["startIndex"] = start
            if a.bbox: p["bbox"] = f"{y0},{x0},{y1},{x1},urn:ogc:def:crs:EPSG::4326"   # WFS 2.0 URN: lat,lon order
        elif mode == "v11":
            p.update(version="1.1.0", typeName=a.layer, maxFeatures=1000000)
            if a.bbox: p["bbox"] = f"{y0},{x0},{y1},{x1},urn:x-ogc:def:crs:EPSG:4326"
        else:   # v10: plain lon,lat
            p.update(version="1.0.0", typeName=a.layer, maxFeatures=1000000)
            if a.bbox: p["bbox"] = f"{x0},{y0},{x1},{y1}"
        return p

    def try_get(p):
        try: raw = get(a.url, p)
        except urllib.error.HTTPError as e:
            body = e.read()[:800].decode("utf-8", "replace")
            print(f"  HTTP {e.code}: {re.sub(r'<[^>]+>', ' ', body).strip()[:400]}", file=sys.stderr); return None
        try: return json.loads(raw)
        except ValueError:
            print("  not GeoJSON: " + re.sub(r"<[^>]+>", " ", raw[:800].decode("utf-8", "replace")).strip()[:400], file=sys.stderr); return None

    feats, mode = [], None
    for m in ("v2_paged", "v2_single", "v11", "v10"):   # servers differ; take the first request form that works
        print(f"  trying {m}", file=sys.stderr)
        gj = try_get(params(m, 0))
        if gj is not None: mode = m; feats = gj.get("features", []); break
    if mode is None: raise SystemExit("Every request form failed (messages above). Check the layer name with --list.")
    print(f"  {len(feats)} features ({mode})", file=sys.stderr)
    start = len(feats)
    while mode == "v2_paged" and len(feats) and len(feats) % a.page == 0:
        gj = try_get(params(mode, start))
        batch = (gj or {}).get("features", [])
        if not batch: break
        feats += batch; start += len(batch); print(f"  {len(feats)} features", file=sys.stderr)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    json.dump({"type": "FeatureCollection", "features": feats}, open(a.out, "w"))
    keys = sorted({k for f in feats[:200] for k in (f.get("properties") or {})})
    print(f"Saved {a.out}: {len(feats)} features. Attribute fields: {', '.join(keys[:25])}")

if __name__ == "__main__":
    main()
