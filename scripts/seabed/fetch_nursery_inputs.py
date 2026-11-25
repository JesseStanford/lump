#!/usr/bin/env python3
"""
fetch_nursery_inputs.py - download the extra layer nursery_proxy.py uses.

  <out>/eelgrass_helcom.tif   HELCOM HOLAS II Zostera marina distribution, 1 km presence/absence
                              (Danish monitoring points 2007-2015; "not exhaustive"). Cite as
                              "HELCOM HOLAS II Dataset: Zostera marina distribution (2018)".

Usage:
  python fetch_nursery_inputs.py --out data/dk_test
"""
import argparse, io, os, shutil, sys, urllib.request, zipfile

HELCOM_ZIP = ("https://maps.helcom.fi/website/download/HOLAS%20II%202011-2015%20indicators%20and%20assessments%20data/"
              "Zostera_marina_distribution.zip")
UA = {"User-Agent": "lumpfish-habitat-research/0.1"}

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/dk"); ap.add_argument("--url", default=HELCOM_ZIP)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    print("Downloading HELCOM eelgrass ...", file=sys.stderr)
    with urllib.request.urlopen(urllib.request.Request(a.url, headers=UA), timeout=600) as r:
        z = zipfile.ZipFile(io.BytesIO(r.read()))
    names = z.namelist(); print("  zip holds:", names, file=sys.stderr)
    tifs = [n for n in names if n.lower().endswith((".tif", ".tiff"))]
    if not tifs:
        raise SystemExit("No GeoTIFF in the zip (contents above). Unzip it by hand and pass --eelgrass to nursery_proxy.py.")
    base = tifs[0].rsplit(".", 1)[0]
    members = [m for m in names if m.startswith(base + ".")]     # the tif plus sidecars (.tfw, .tif.aux.xml, .prj ...)
    tmp = os.path.join(a.out, "_helcom_eelgrass"); z.extractall(tmp, members=members)
    for m in members:
        shutil.move(os.path.join(tmp, m), os.path.join(a.out, "eelgrass_helcom" + m[len(base):]))
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"Saved {os.path.join(a.out, 'eelgrass_helcom.tif')}")

if __name__ == "__main__":
    main()
