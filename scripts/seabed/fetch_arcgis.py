#!/usr/bin/env python3
"""
fetch_arcgis.py - list the layers of an ArcGIS REST MapServer, or download one layer inside a
lat/lon box as GeoJSON (WGS84), paging through the server's record limit.

Default service: EMODnet Geology sea-floor geology, hosted by BGR. Layers (checked 2026-11-25):
  0 geomorphology line features   landform: marginal moraine, moraine ridge, esker, tunnel valley ...
  2 geomorphology                 landform: moraine, drumlin, esker, ice rafted debris field ...
  4 Quaternary lithology          lithology1: diamicton, boulder gravel size sediment, sand, mud ...
  5 Quaternary age                age_older: Weichselian, Holocene ...

Usage:
  python fetch_arcgis.py --list
  python fetch_arcgis.py --layer 4 --bbox 7.5 54.4 15.3 57.9 --out data/dk/quaternary_lithology.geojson
  python fetch_arcgis.py --layer 2 --where "landform LIKE '%moraine%'" --bbox ... --out ...
"""
import argparse, json, os, sys, time, urllib.parse, urllib.request

BGR = "https://services.bgr.de/arcgis/rest/services/geologie/emodnet_seafloor_geology/MapServer"
UA = {"User-Agent": "lumpfish-habitat-research/0.1"}

def get(url, params, timeout=300):
    q = url + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(q, headers=UA), timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:   # network hiccups: back off and retry
            if attempt == 3: raise
            print(f"  retry {attempt + 1} after {e}", file=sys.stderr); time.sleep(5 * (attempt + 1))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=BGR, help="MapServer or FeatureServer URL (no trailing /query)")
    ap.add_argument("--list", action="store_true"); ap.add_argument("--layer", type=int)
    ap.add_argument("--bbox", nargs=4, type=float, help="lon_min lat_min lon_max lat_max")
    ap.add_argument("--where", default="1=1"); ap.add_argument("--page", type=int, default=1000)
    ap.add_argument("--out", default="layer.geojson")
    a = ap.parse_args()
    url = a.url.rstrip("/")

    if a.list or a.layer is None:
        info = get(url, {"f": "json"})
        if "error" in info: raise SystemExit(f"Server error: {info['error']}")
        for L in info.get("layers", []):
            print(f"{L['id']:>3}  {L.get('geometryType', 'group'):24s} {L['name']}")
        return

    meta = get(f"{url}/{a.layer}", {"f": "json"})
    print(f"Layer {a.layer}: {meta.get('name')}  fields: {[f['name'] for f in meta.get('fields') or []]}", file=sys.stderr)
    base = {"where": a.where, "outFields": "*", "outSR": 4326, "f": "geojson", "returnGeometry": "true"}
    if a.bbox:
        base.update(geometry=",".join(str(v) for v in a.bbox), geometryType="esriGeometryEnvelope", inSR=4326,
                    spatialRel="esriSpatialRelIntersects")
    feats, off = [], 0
    while True:
        page = get(f"{url}/{a.layer}/query", dict(base, resultOffset=off, resultRecordCount=a.page))
        if "error" in page: raise SystemExit(f"Server error: {page['error']}")
        fs = page.get("features", []); feats += fs
        print(f"  {len(feats)} features", file=sys.stderr)
        more = page.get("exceededTransferLimit") or (page.get("properties") or {}).get("exceededTransferLimit")
        if not fs or (not more and len(fs) < a.page): break
        off += len(fs)
    if not feats: raise SystemExit("No features returned. Check the bbox (lon lat order) and --where.")
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    json.dump({"type": "FeatureCollection", "features": feats}, open(a.out, "w", encoding="utf-8"))
    print(f"Saved {len(feats)} features to {a.out}")

if __name__ == "__main__":
    main()
