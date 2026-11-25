#!/usr/bin/env python3
"""
fetch_datras.py - every ICES DATRAS trawl-survey haul in a box, with the lumpfish catch per haul
(0 when none was caught). Hauls without lumpfish are what make a spatial test possible: GBIF only
holds the hauls that caught one.

Surveys: NS-IBTS (North Sea, Skagerrak, Kattegat; quarters 1 and 3) and BITS (Kattegat, Belts,
Baltic; quarters 1 and 4). Raw XML is cached in --cache, so an interrupted run resumes.

Usage:
  python fetch_datras.py --bbox 7.5 54.4 15.3 57.9 --years 1991 2025 --out data/dk/datras_hauls.csv
"""
import argparse, csv, json, os, sys, time, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

WS = "https://datras.ices.dk/WebServices/DATRASWebService.asmx"
UA = {"User-Agent": "lumpfish-habitat-research/0.1"}
KEY = ("Survey", "Quarter", "Country", "Ship", "Gear", "StNo", "HaulNo", "Year")

def fetch(op, params, cache):
    fn = os.path.join(cache, f"{op}_{params['survey']}_{params['year']}_Q{params['quarter']}.xml")
    if os.path.exists(fn) and os.path.getsize(fn) > 0: return fn
    q = f"{WS}/{op}?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(q, headers=UA), timeout=600) as r, open(fn + ".part", "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b: break
                    f.write(b)
            os.replace(fn + ".part", fn); return fn
        except Exception as e:
            if attempt == 3: print(f"    {op} failed: {e}", file=sys.stderr); return None
            time.sleep(5 * (attempt + 1))

def records(fn):
    """Yield one dict per record, namespace stripped, values stripped."""
    for _, el in ET.iterparse(fn, events=("end",)):
        if el.tag.split("}")[-1].startswith("Cls_DatrasExchange"):
            yield {c.tag.split("}")[-1]: (c.text or "").strip() for c in el}; el.clear()

def num(v):
    try:
        x = float(v); return None if x <= -9 else x
    except (TypeError, ValueError): return None

def aphia_for(name):
    try:
        q = "https://www.marinespecies.org/rest/AphiaIDByName/" + urllib.parse.quote(name) + "?marine_only=true"
        with urllib.request.urlopen(urllib.request.Request(q, headers=UA), timeout=60) as r:
            return int(json.loads(r.read()))
    except Exception as e:
        print(f"WoRMS lookup failed ({e}); using 127214", file=sys.stderr); return 127214

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bbox", nargs=4, type=float, required=True, help="lon_min lat_min lon_max lat_max")
    ap.add_argument("--years", nargs=2, type=int, default=[1991, 2025])
    ap.add_argument("--surveys", nargs="+", default=["NS-IBTS", "BITS"])
    ap.add_argument("--quarters", nargs="+", type=int, default=[1, 3, 4])
    ap.add_argument("--species", default="Cyclopterus lumpus"); ap.add_argument("--aphia", type=int)
    ap.add_argument("--cache", default="data/datras_cache"); ap.add_argument("--out", default="data/dk/datras_hauls.csv")
    a = ap.parse_args()
    aphia = str(a.aphia or aphia_for(a.species)); print(f"{a.species}: AphiaID {aphia}", file=sys.stderr)
    os.makedirs(a.cache, exist_ok=True); os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    x0, y0, x1, y1 = a.bbox
    rows, n_pos = [], 0
    for sv in a.surveys:
        for yr in range(a.years[0], a.years[1] + 1):
            for qt in a.quarters:
                p = {"survey": sv, "year": yr, "quarter": qt}
                hh = fetch("getHHdata", p, a.cache)
                if not hh: continue
                hauls = {}
                for r in records(hh):
                    if r.get("HaulVal") not in ("V", ""): continue
                    la = [v for v in (num(r.get("ShootLat")), num(r.get("HaulLat"))) if v is not None]
                    lo = [v for v in (num(r.get("ShootLong")), num(r.get("HaulLong"))) if v is not None]
                    if not la or not lo: continue
                    lat, lon = sum(la) / len(la), sum(lo) / len(lo)
                    if not (x0 <= lon <= x1 and y0 <= lat <= y1): continue
                    hauls[tuple(r.get(k, "") for k in KEY)] = dict(
                        survey=sv, year=yr, quarter=qt, month=r.get("Month", ""), day=r.get("Day", ""), lat=round(lat, 5),
                        lon=round(lon, 5), depth_m=num(r.get("Depth")), haul_min=num(r.get("HaulDur")), gear=r.get("Gear", ""),
                        country=r.get("Country", ""), ship=r.get("Ship", ""), stno=r.get("StNo", ""), haulno=r.get("HaulNo", ""),
                        bot_temp=num(r.get("BotTemp")), bot_sal=num(r.get("BotSal")), lumpfish_n=0)
                if not hauls: continue
                hl = fetch("getHLdata", p, a.cache)
                if hl:
                    best = {}
                    for r in records(hl):
                        if r.get("Valid_Aphia") != aphia and not (r.get("SpecCodeType") == "W" and r.get("SpecCode") == aphia): continue
                        k = tuple(r.get(kk, "") for kk in KEY)
                        if k not in hauls: continue
                        tot = num(r.get("TotalNo")) or 0
                        alt = (num(r.get("HLNoAtLngt")) or 0) * (num(r.get("SubFactor")) or 1)
                        best[k] = max(best.get(k, 0), tot) if tot else best.get(k, 0) + alt
                    for k, n in best.items(): hauls[k]["lumpfish_n"] = round(max(n, 1), 1)
                pos = sum(1 for h in hauls.values() if h["lumpfish_n"] > 0); n_pos += pos
                print(f"  {sv} {yr} Q{qt}: {len(hauls)} hauls in box, {pos} with lumpfish", file=sys.stderr)
                rows += hauls.values()
    if not rows: raise SystemExit("No hauls found in the box.")
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f"Saved {len(rows)} hauls ({n_pos} with lumpfish) to {a.out}")

if __name__ == "__main__":
    main()
