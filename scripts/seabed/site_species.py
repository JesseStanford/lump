#!/usr/bin/env python3
"""
site_species.py - which of the habitat-component species are recorded at each candidate reef patch?

1. Looks up every taxon in parameters/component_taxa.csv (component id -> species, genus, order or
   class) in the GBIF backbone.
2. Requests ONE GBIF occurrence download for those taxa inside the box around the shortlist patches.
   A GBIF download gets a DOI, which is the citation (written to sources.csv / SOURCES.md).
   It needs a free GBIF.org account, read from the environment:
       $env:GBIF_USER = "your GBIF user name"; $env:GBIF_PWD = "your password"; $env:GBIF_EMAIL = "your email"
   GBIF prepares the file on its side; this usually takes 2 to 15 minutes, and the script waits.
   Re-runs use the saved zip (--zip) instead of asking again.
3. For each patch in shortlist.csv: records within --radius-km of the patch edge (patch treated as a
   circle of its area around its centre), per component and per species: count, latest year, nearest km.

Caveat: GBIF records show where people looked and reported. No record is not the same as absent;
divers, beach walkers and monitoring programmes are unevenly spread.

Outputs in --out:
  site_components.csv   patch x component: records, species, latest year
  site_species.csv      patch, component, species: records, latest year, nearest km
  site_components.png   presence grid (patches x components)

Usage:
  python site_species.py --shortlist runs/oresund_shortlist/shortlist.csv --out runs/oresund_species
  python site_species.py --shortlist runs/oresund_shortlist/shortlist.csv --zip runs/oresund_species/gbif_download.zip --out runs/oresund_species
"""
import argparse, base64, csv, io, json, math, os, sys, time, urllib.parse, urllib.request, urllib.error, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://api.gbif.org/v1"
RANKS = {"KINGDOM": "kingdom", "PHYLUM": "phylum", "CLASS": "class", "ORDER": "order", "FAMILY": "family",
         "GENUS": "genus", "SPECIES": "species"}
NAMES = {"F1": "eelgrass", "F2": "kelp", "F3": "Fucus", "F4": "red algae", "F5": "filamentous algae", "S7": "blue mussel",
         "A1": "wrasse", "A2": "cod, blennies", "A3": "gulls, crows", "A4": "seals, otter", "A5": "copepods, amphipods",
         "A6": "jellyfish", "A7": "sea urchins", "A8": "starfish", "T0": "lumpfish"}

def get(url, params=None, auth=None, data=None, raw=False):
    if params: url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "lump-site-species", "Content-Type": "application/json"})
    if auth: req.add_header("Authorization", "Basic " + base64.b64encode(auth.encode()).decode())
    with urllib.request.urlopen(req, timeout=300) as r:
        b = r.read()
    return b if raw else json.loads(b)

def match_taxa(path, include_birds):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    out = []
    for r in rows:
        if r["component_id"] == "A3" and not include_birds: continue
        q = {"name": r["taxon"], "strict": "true"}
        for col, par in (("rank", "rank"), ("kingdom", "kingdom"), ("class_hint", "class")):
            if r.get(col): q[par] = r[col]
        m = get(f"{API}/species/match", q)
        rank = m.get("rank", "")
        want = (r.get("rank") or "").upper()
        # HIGHERRANK means GBIF fell back to a parent taxon (e.g. the whole phylum): never accept that
        if m.get("matchType") not in ("EXACT", "FUZZY") or "usageKey" not in m or (want and rank != want):
            print(f"  REJECTED match for {r['taxon']} ({r['component_id']}): {m.get('matchType')} {rank} "
                  f"{m.get('canonicalName', '')} - fix component_taxa.csv", file=sys.stderr); continue
        out.append({"component": r["component_id"], "taxon": r["taxon"], "key": m["usageKey"], "rank": rank,
                    "col": RANKS.get(rank, "species"), "name": m.get("canonicalName", r["taxon"])})
        print(f"  {r['component_id']:3s} {r['taxon']:24s} -> {m['usageKey']} {rank} ({m.get('status', '')})", file=sys.stderr)
        time.sleep(0.1)
    return out

def request_download(taxa, bbox, since):
    user, pwd, email = os.environ.get("GBIF_USER"), os.environ.get("GBIF_PWD"), os.environ.get("GBIF_EMAIL")
    if not (user and pwd and email):
        raise SystemExit('A GBIF download needs your GBIF.org login. In PowerShell, first run:\n'
                         '  $env:GBIF_USER = "your GBIF user name"\n  $env:GBIF_PWD = "your GBIF password"\n'
                         '  $env:GBIF_EMAIL = "the email on your GBIF account"\n'
                         'then run this again. No account yet: sign up free at https://www.gbif.org/user/profile')
    lo1, la1, lo2, la2 = bbox
    wkt = f"POLYGON(({lo1} {la1},{lo2} {la1},{lo2} {la2},{lo1} {la2},{lo1} {la1}))"
    pred = {"type": "and", "predicates": [
        {"type": "in", "key": "TAXON_KEY", "values": sorted({str(t["key"]) for t in taxa})},
        {"type": "within", "geometry": wkt},
        {"type": "equals", "key": "HAS_COORDINATE", "value": "true"},
        {"type": "equals", "key": "HAS_GEOSPATIAL_ISSUE", "value": "false"},
        {"type": "equals", "key": "OCCURRENCE_STATUS", "value": "PRESENT"},
        {"type": "greaterThanOrEquals", "key": "YEAR", "value": str(since)}]}
    body = json.dumps({"creator": user, "notificationAddresses": [email], "sendNotification": True,
                       "format": "SIMPLE_CSV", "predicate": pred}).encode()
    try:
        key = get(f"{API}/occurrence/download/request", auth=f"{user}:{pwd}", data=body, raw=True).decode().strip()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"GBIF refused the download request: HTTP {e.code} {e.read()[:300]!r}. Check the user name and password.")
    print(f"GBIF download {key} requested; waiting for GBIF to prepare it ...", file=sys.stderr)
    t0 = time.time()
    while True:
        st = get(f"{API}/occurrence/download/{key}")
        s = st.get("status")
        print(f"  {int(time.time() - t0):5d} s: {s}", file=sys.stderr)
        if s == "SUCCEEDED": return st, pred
        if s in ("FAILED", "KILLED", "CANCELLED"): raise SystemExit(f"GBIF download {key} {s}")
        if time.time() - t0 > 3600:
            raise SystemExit(f"Still not ready after an hour. Download it later from https://www.gbif.org/occurrence/download/{key} "
                             "and re-run with --zip <that file>.")
        time.sleep(30)

def haversine_km(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(a))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--shortlist", required=True); ap.add_argument("--out", default="runs/site_species")
    ap.add_argument("--taxa", default=os.path.join(HERE, "..", "..", "parameters", "component_taxa.csv"))
    ap.add_argument("--radius-km", type=float, default=2.0, help="search distance beyond the patch edge")
    ap.add_argument("--since", type=int, default=2000, help="earliest year")
    ap.add_argument("--max-uncertainty-m", type=float, default=2000, help="drop records with larger coordinate uncertainty")
    ap.add_argument("--include-birds", action="store_true", help="add gulls / crows (A3); makes the download much larger")
    ap.add_argument("--top", type=int, default=40, help="patches in the PNG")
    ap.add_argument("--zip", help="use this saved GBIF download instead of requesting a new one")
    a = ap.parse_args()
    sys.path.insert(0, HERE); import sources
    os.makedirs(a.out, exist_ok=True)

    patches = list(csv.DictReader(open(a.shortlist, encoding="utf-8")))
    for p in patches:
        p["lat"], p["lon"], p["area_km2"] = float(p["lat"]), float(p["lon"]), float(p["area_km2"])
        p["reach_km"] = math.sqrt(p["area_km2"] / math.pi) + a.radius_km
    pad_lat = max(p["reach_km"] for p in patches) / 111.0
    lat_mid = sum(p["lat"] for p in patches) / len(patches); pad_lon = pad_lat / math.cos(math.radians(lat_mid))
    bbox = [round(min(p["lon"] for p in patches) - pad_lon, 4), round(min(p["lat"] for p in patches) - pad_lat, 4),
            round(max(p["lon"] for p in patches) + pad_lon, 4), round(max(p["lat"] for p in patches) + pad_lat, 4)]
    print(f"{len(patches)} patches; download box {bbox}", file=sys.stderr)

    print("Matching taxa in the GBIF backbone:", file=sys.stderr)
    taxa = match_taxa(a.taxa, a.include_birds)

    zpath = a.zip
    if not zpath:
        st, pred = request_download(taxa, bbox, a.since)
        zpath = os.path.join(a.out, "gbif_download.zip")
        open(zpath, "wb").write(get(st["downloadLink"], raw=True))
        doi = st.get("doi", "")
        json.dump({"key": st.get("key"), "doi": doi, "totalRecords": st.get("totalRecords"), "created": st.get("created"),
                   "predicate": pred, "citation": f"GBIF.org ({st.get('created', '')[:10]}) GBIF Occurrence Download https://doi.org/{doi}"},
                  open(os.path.join(a.out, "gbif_download.json"), "w"), indent=1)
        sources.record(zpath, f"https://doi.org/{doi}", f"GBIF download {st.get('key')}: {st.get('totalRecords')} records; taxa "
                       f"{len(taxa)} from component_taxa.csv; box {bbox}; year >= {a.since}", key="gbif_site_species")
        print(f"Saved {zpath} ({st.get('totalRecords')} records). Cite: GBIF.org, https://doi.org/{doi}", file=sys.stderr)

    # assign records to components by matching the taxon's name at its rank column
    by_col = {}
    for t in taxa: by_col.setdefault(t["col"], {})[t["name"]] = t["component"]
    z = zipfile.ZipFile(zpath); member = [n for n in z.namelist() if n.endswith(".csv")][0]
    csv.field_size_limit(10 ** 8)
    recs = []
    with z.open(member) as fh:
        rd = csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE)
        for r in rd:
            try: lat, lon = float(r["decimalLatitude"]), float(r["decimalLongitude"])
            except (TypeError, ValueError): continue
            unc = r.get("coordinateUncertaintyInMeters") or ""
            if unc and float(unc) > a.max_uncertainty_m: continue
            comp = None
            for col in ("species", "genus", "family", "order", "class", "phylum"):
                c = by_col.get(col, {}).get(r.get(col, ""))
                if c: comp = c; break
            if not comp: continue
            recs.append((comp, r.get("species") or r.get("scientificName", ""), lat, lon, int(r["year"]) if r.get("year") else None))
    print(f"{len(recs)} usable records assigned to components", file=sys.stderr)

    comps = sorted({t["component"] for t in taxa}, key=lambda c: (c[0] != "T", c[0] != "F", c[0] != "S", c))
    wide, long_ = [], []
    for p in patches:
        hits = {}
        for comp, sp, lat, lon, yr in recs:
            if abs(lat - p["lat"]) > p["reach_km"] / 100: continue
            d = haversine_km(p["lat"], p["lon"], lat, lon)
            if d > p["reach_km"]: continue
            h = hits.setdefault((comp, sp), [0, None, 99.0]); h[0] += 1
            h[1] = max(h[1] or 0, yr or 0) or None; h[2] = min(h[2], d)
        row = {"patch": p["patch"], "lat": p["lat"], "lon": p["lon"], "area_km2": p["area_km2"], "search_km": round(p["reach_km"], 2)}
        for c in comps:
            ks = [k for k in hits if k[0] == c]
            row[f"{c}_records"] = sum(hits[k][0] for k in ks); row[f"{c}_species"] = len(ks)
            yrs = [hits[k][1] for k in ks if hits[k][1]]; row[f"{c}_latest"] = max(yrs) if yrs else ""
        row["components_present"] = sum(1 for c in comps if row[f"{c}_records"] > 0)
        wide.append(row)
        for (c, sp), (n, yr, d) in sorted(hits.items()):
            long_.append({"patch": p["patch"], "component": c, "component_name": NAMES.get(c, ""), "species": sp,
                          "records": n, "latest_year": yr or "", "nearest_km": round(d, 2)})
    with open(os.path.join(a.out, "site_components.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(wide[0])); w.writeheader(); w.writerows(wide)
    with open(os.path.join(a.out, "site_species.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["patch", "component", "component_name", "species", "records", "latest_year", "nearest_km"])
        w.writeheader(); w.writerows(long_)
    print(f"{'patch':>5s} " + " ".join(f"{c:>4s}" for c in comps))
    for r in wide[:a.top]:
        print(f"{r['patch']:>5s} " + " ".join(f"{r[c + '_records']:>4d}" for c in comps))

    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt; import numpy as np
    sub = wide[:a.top]
    M = np.array([[min(r[f"{c}_records"], 50) for c in comps] for r in sub], float)
    fig, ax = plt.subplots(figsize=(1 + 0.55 * len(comps), 1.5 + 0.28 * len(sub)))
    ax.imshow(np.where(M > 0, np.log1p(M), np.nan), cmap="Greens", aspect="auto", vmin=0, vmax=np.log1p(50))
    ax.set_xticks(range(len(comps))); ax.set_xticklabels([f"{c}\n{NAMES.get(c, '')}" for c in comps], fontsize=6, rotation=90)
    ax.set_yticks(range(len(sub))); ax.set_yticklabels([f"#{r['patch']}" for r in sub], fontsize=7)
    for i, r in enumerate(sub):
        for j, c in enumerate(comps):
            if r[f"{c}_records"]: ax.text(j, i, r[f"{c}_records"], ha="center", va="center", fontsize=5)
    ax.set_title(f"GBIF records within {a.radius_km:g} km of each patch (since {a.since}); blank = no record, not absence", fontsize=8)
    fig.savefig(os.path.join(a.out, "site_components.png"), dpi=170, bbox_inches="tight")
    sources.carry(a.out, [a.shortlist, zpath])
    print("Results in", a.out)

if __name__ == "__main__":
    main()
