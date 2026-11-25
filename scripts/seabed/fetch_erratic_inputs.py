#!/usr/bin/env python3
"""
fetch_erratic_inputs.py - download every layer erratic_overlay.py needs for a lat/lon box, in one go.

  <out>/quat_lithology.geojson   EMODnet Geology Quaternary lithology (BGR ArcGIS layer 4)
  <out>/geomorph_polys.geojson   EMODnet Geology geomorphology polygons (layer 2)
  <out>/geomorph_lines.geojson   EMODnet Geology geomorphology lines (layer 0)
  <out>/substrate.geojson        EMODnet Geology seabed substrate 1:250k (WFS gtk:seabed_substrate_250k)
  <out>/emodnet_dtm.tif          EMODnet Bathymetry mean depth DTM (WCS)

A layer that fails is reported and skipped; the rest still download. Layer and coverage names are
looked up from the services, so nothing has to be typed in by hand.

Usage:
  python fetch_erratic_inputs.py --bbox 11.9 55.95 12.7 56.2 --out data/dk_test
"""
import argparse, os, re, subprocess, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
GEOL_WFS = "https://drive.emodnet-geology.eu/geoserver/gtk/wfs"
BATHY_WCS = "https://ows.emodnet-bathymetry.eu/wcs"
UA = {"User-Agent": "lumpfish-habitat-research/0.1"}

def caps(url, service, version):
    q = url + "?" + urllib.parse.urlencode({"service": service, "request": "GetCapabilities", "version": version})
    with urllib.request.urlopen(urllib.request.Request(q, headers=UA), timeout=180) as r:
        return r.read().decode("utf-8", "replace")

def run(name, args):
    print(f"\n=== {name}", flush=True)
    r = subprocess.run([sys.executable, *args])
    ok = r.returncode == 0
    print(f"--- {name}: {'OK' if ok else 'FAILED (skipped)'}", flush=True)
    return ok

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bbox", nargs=4, required=True, help="lon_min lat_min lon_max lat_max")
    ap.add_argument("--out", default="data/dk"); ap.add_argument("--tile", default="0.5", help="WCS tile, degrees")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True); o = lambda f: os.path.join(a.out, f); res = {}

    arc = os.path.join(HERE, "fetch_arcgis.py")
    for lyr, f in (("4", "quat_lithology.geojson"), ("2", "geomorph_polys.geojson"), ("0", "geomorph_lines.geojson")):
        res[f] = run(f"EMODnet Geology layer {lyr} -> {f}", [arc, "--layer", lyr, "--bbox", *a.bbox, "--out", o(f)])

    # seabed substrate: prefer the 1:250k layer, else the finest multiscale/100k one the WFS lists
    layer = None
    try:
        names = re.findall(r"<(?:wfs:)?Name>([^<]*substrate[^<]*)</", caps(GEOL_WFS, "WFS", "2.0.0"), re.I)
        print("Substrate layers on the WFS:", names)
        for pref in ("seabed_substrate_250k", "seabed_substrate_100k", "multiscale", "substrate"):
            hit = [n for n in names if pref in n]
            if hit: layer = hit[0]; break
    except Exception as e:
        print("Could not read the geology WFS capabilities:", e)
    layer = layer or "gtk:seabed_substrate_250k"
    res["substrate.geojson"] = run(f"Seabed substrate {layer} -> substrate.geojson",
                                   [os.path.join(HERE, "fetch_wfs.py"), "--url", GEOL_WFS, "--layer", layer,
                                    "--bbox", *a.bbox, "--out", o("substrate.geojson")])

    # depth: EMODnet mean DTM; the coverage id differs between service versions, so look it up
    cov = None
    try:
        ids = re.findall(r"<(?:wcs:)?CoverageId>([^<]+)</", caps(BATHY_WCS, "WCS", "2.0.1"))
        means = [i for i in ids if re.search(r"mean", i, re.I)]
        print("Bathymetry coverages:", ids[:12], "..." if len(ids) > 12 else "")
        cov = (["emodnet__mean"] if "emodnet__mean" in ids else []) + means
        cov = cov[0] if cov else (ids[0] if ids else None)
    except Exception as e:
        print("Could not read the bathymetry WCS capabilities:", e)
    cov = cov or "emodnet__mean"
    res["emodnet_dtm.tif"] = run(f"Bathymetry {cov} -> emodnet_dtm.tif",
                                 [os.path.join(HERE, "fetch_wcs.py"), "--url", BATHY_WCS, "--coverage", cov,
                                  "--crs", "EPSG:4326", "--axes", "Long", "Lat", "--bbox", *a.bbox,
                                  "--tile", a.tile, "--out", o("emodnet_dtm.tif")])

    print("\nSummary:")
    for f, ok in res.items(): print(f"  {'OK    ' if ok else 'FAILED'}  {o(f)}")
    if not any(res.values()): sys.exit(1)

if __name__ == "__main__":
    main()
