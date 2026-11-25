#!/usr/bin/env python3
"""
fetch_nursery_inputs.py - download the extra layers for the nursery proxy and the reef comparison.

  <out>/eelgrass_helcom.tif   HELCOM HOLAS II Zostera marina distribution, 1 km presence/absence
                              (Danish monitoring 2007-2015, "not exhaustive").
                              Cite: "HELCOM HOLAS II Dataset: Zostera marina distribution (2018)".
  <out>/reefs_helcom_1170.tif HELCOM HOLAS II Reefs (1170), presence/absence raster. Danish input is
                              "polygon data on reefs found within Natura 2000 sites" (Danish Nature Agency).
                              HELCOM area only: Kattegat, Belts, Øresund, Baltic (not Skagerrak / North Sea).
                              Cite: "HELCOM HOLAS II Dataset: Natura 2000 habitats: Reefs (1170) (2017)".
  <out>/n2000_sites.geojson   Natura 2000 site boundaries (EEA ArcGIS service) in --bbox: where reefs
                              were actually mapped, so the comparison only counts surveyed water.

Usage:
  python fetch_nursery_inputs.py --out data/dk                         # eelgrass only (old behaviour)
  python fetch_nursery_inputs.py --out data/dk --what eelgrass reefs n2000 --bbox 7.5 54.4 15.3 57.9
"""
import argparse, io, json, os, re, shutil, subprocess, sys, urllib.request, zipfile

HELCOM = "https://maps.helcom.fi/website/download/HOLAS%20II%202011-2015%20indicators%20and%20assessments%20data/"
ZIPS = {"eelgrass": ("Zostera_marina_distribution.zip", "eelgrass_helcom"), "reefs": ("Reefs_1170.zip", "reefs_helcom_1170")}
EEA_N2000 = "https://bio.discomap.eea.europa.eu/arcgis/rest/services/ProtectedSites/Natura2000Sites/MapServer"
UA = {"User-Agent": "lumpfish-habitat-research/0.1"}
HERE = os.path.dirname(os.path.abspath(__file__))

def helcom_zip(fname, base_out, out):
    print(f"Downloading HELCOM {fname} ...", file=sys.stderr)
    with urllib.request.urlopen(urllib.request.Request(HELCOM + fname, headers=UA), timeout=600) as r:
        z = zipfile.ZipFile(io.BytesIO(r.read()))
    names = z.namelist(); print("  zip holds:", names, file=sys.stderr)
    tifs = [n for n in names if n.lower().endswith((".tif", ".tiff"))]
    if not tifs: raise RuntimeError("no GeoTIFF in the zip (contents above); unzip it by hand")
    base = tifs[0].rsplit(".", 1)[0]
    members = [m for m in names if m.startswith(base + ".")]     # the tif plus sidecars (.tfw, .tif.aux.xml, .prj ...)
    tmp = os.path.join(out, "_helcom_tmp"); z.extractall(tmp, members=members)
    for m in members:
        shutil.move(os.path.join(tmp, m), os.path.join(out, base_out + m[len(base):]))
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"Saved {os.path.join(out, base_out + '.tif')}")
    sys.path.insert(0, HERE); import sources
    for m in members:
        sources.record(os.path.join(out, base_out + m[len(base):]), HELCOM + fname, f"zip member {m}")

def n2000(bbox, out):
    info = json.loads(urllib.request.urlopen(urllib.request.Request(EEA_N2000 + "?f=json", headers=UA), timeout=120).read())
    layers = [(L["id"], L["name"]) for L in info.get("layers", []) if L.get("geometryType", "").endswith("Polygon")]
    print("  EEA Natura 2000 polygon layers:", layers, file=sys.stderr)
    pick = [i for i, n in layers if re.search(r"habitat|sci|sac|natura", n, re.I)] or [i for i, _ in layers]
    if not pick: raise RuntimeError("no polygon layer on the EEA service")
    r = subprocess.run([sys.executable, os.path.join(HERE, "fetch_arcgis.py"), "--url", EEA_N2000, "--layer", str(pick[0]),
                        "--bbox", *map(str, bbox), "--out", os.path.join(out, "n2000_sites.geojson")])
    if r.returncode: raise RuntimeError("fetch_arcgis failed")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/dk"); ap.add_argument("--what", nargs="+", default=["eelgrass"],
                                                                 choices=["eelgrass", "reefs", "n2000"])
    ap.add_argument("--bbox", nargs=4, type=float, help="needed for n2000")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True); ok = {}
    for w in a.what:
        try:
            if w == "n2000":
                if not a.bbox: raise RuntimeError("--bbox is needed for n2000")
                n2000(a.bbox, a.out)
            else:
                helcom_zip(*ZIPS[w], a.out)
            ok[w] = True
        except Exception as e:
            print(f"  {w} FAILED: {e}", file=sys.stderr); ok[w] = False
    print("Summary:", {k: "OK" if v else "FAILED" for k, v in ok.items()})
    if not any(ok.values()): sys.exit(1)

if __name__ == "__main__":
    main()
