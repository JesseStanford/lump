#!/usr/bin/env python3
"""
nest_records.py - collect located lumpfish (Cyclopterus lumpus) records that point to
nests: egg masses, males guarding eggs, or spawning fish in shallow water.

Sources (public APIs, no key needed; run on a machine with normal internet):
  - GBIF occurrence API (includes iNaturalist research-grade, Seasearch, museum and
    survey datasets that are shared to GBIF)
  - iNaturalist API text search, for casual/needs-ID photos GBIF does not carry
Plus any hand-entered literature sites in --literature CSV (lat,lon,label,source,evidence).

Each record gets an evidence level:
  3 = nest/egg evidence (lifeStage Egg/Embryo, or egg/nest/guard words in notes)
  2 = spawning season + shallow (<= 20 m) + adult, no egg note
  1 = any record in the spawning season
Records are NOT proof of a nest until a person checks the photo/notes; the CSV has a
'reviewed' column for that. Keep only level 3 (and checked level 2) for parameterising.

Usage:
  python nest_records.py --countries DK SE NO GB IE FR IS --months 1 2 3 4 5 6 \
      --out nest_candidates.csv [--bbox lonmin latmin lonmax latmax] [--literature lit.csv]
"""
import argparse, csv, json, re, sys, time, urllib.parse, urllib.request

UA = {"User-Agent": "lumpfish-habitat-research/0.1"}
NEST_WORDS = re.compile(r"\b(egg|eggs|egg ?mass|nest|guard\w*|spawn\w*|roe|clutch|"
                        r"æg|rogn|gyd\w*|reir|rognklase|ägg|lek|oeuf|oeufs|ponte|nid|gelege|laich)\b", re.I)

def get(url, params):
    q = url + "?" + urllib.parse.urlencode(params, doseq=True)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(q, headers=UA), timeout=60) as r:
                return json.load(r)
        except Exception as e:
            if attempt == 3: raise
            time.sleep(2 ** attempt)

def gbif_taxon_key():
    return get("https://api.gbif.org/v1/species/match", {"name": "Cyclopterus lumpus"})["usageKey"]

def gbif_records(countries, months, bbox, limit_total):
    key = gbif_taxon_key(); out = []; offset = 0
    base = {"taxonKey": key, "hasCoordinate": "true", "hasGeospatialIssue": "false",
            "month": months, "limit": 300}
    if countries: base["country"] = countries
    if bbox:
        lo1, la1, lo2, la2 = bbox
        base["geometry"] = f"POLYGON(({lo1} {la1},{lo2} {la1},{lo2} {la2},{lo1} {la2},{lo1} {la1}))"
    while offset < limit_total:
        page = get("https://api.gbif.org/v1/occurrence/search", dict(base, offset=offset))
        for o in page["results"]:
            text = " ".join(str(o.get(k, "")) for k in ("occurrenceRemarks", "lifeStage", "behavior",
                            "reproductiveCondition", "dynamicProperties", "fieldNotes", "eventRemarks"))
            media = ";".join(m.get("identifier", "") for m in o.get("media", []) if m.get("identifier"))
            out.append(dict(source="GBIF", id=o.get("key"), lat=o.get("decimalLatitude"), lon=o.get("decimalLongitude"),
                            uncertainty_m=o.get("coordinateUncertaintyInMeters"), date=o.get("eventDate", "")[:10],
                            month=o.get("month"), depth_m=o.get("depth"), life_stage=o.get("lifeStage", ""),
                            dataset=o.get("datasetName", ""), basis=o.get("basisOfRecord", ""),
                            notes=text.strip()[:500], media=media[:500],
                            url=f"https://www.gbif.org/occurrence/{o.get('key')}"))
        offset += page["limit"]
        if page.get("endOfRecords"): break
        time.sleep(0.3)
    return out

def inat_records(months, bbox, words=("egg", "eggs", "nest", "guarding", "spawning")):
    out, seen = [], set()
    for w in words:
        params = {"taxon_name": "Cyclopterus lumpus", "q": w, "search_on": "description",
                  "month": ",".join(map(str, months)), "per_page": 200, "geo": "true"}
        if bbox:
            params.update(swlng=bbox[0], swlat=bbox[1], nelng=bbox[2], nelat=bbox[3])
        for page in range(1, 6):
            params["page"] = page
            res = get("https://api.inaturalist.org/v1/observations", params)
            for o in res["results"]:
                if o["id"] in seen or not o.get("geojson"): continue
                seen.add(o["id"]); lon, lat = o["geojson"]["coordinates"]
                out.append(dict(source="iNaturalist", id=o["id"], lat=lat, lon=lon,
                                uncertainty_m=o.get("positional_accuracy"), date=o.get("observed_on") or "",
                                month=(o.get("observed_on_details") or {}).get("month"), depth_m="",
                                life_stage="", dataset="iNaturalist " + o.get("quality_grade", ""),
                                basis="HUMAN_OBSERVATION", notes=(o.get("description") or "")[:500],
                                media=";".join(p["url"].replace("square", "large") for p in o.get("photos", []))[:500],
                                url=f"https://www.inaturalist.org/observations/{o['id']}"))
            if len(res["results"]) < 200: break
            time.sleep(1.0)
    return out

def evidence(r):
    ls = str(r.get("life_stage", "")).lower()
    if ls in ("egg", "eggs", "embryo") or NEST_WORDS.search(r.get("notes", "")):
        return 3
    try: d = abs(float(r["depth_m"]))
    except (TypeError, ValueError): d = None
    if r.get("month") and int(r["month"]) <= 6 and d is not None and d <= 20:
        return 2
    return 1

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--countries", nargs="*", default=["DK", "SE", "NO", "GB", "IE", "FR", "IS", "DE"])
    ap.add_argument("--months", nargs="*", type=int, default=[1, 2, 3, 4, 5, 6])
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("LONMIN", "LATMIN", "LONMAX", "LATMAX"))
    ap.add_argument("--max-gbif", type=int, default=20000)
    ap.add_argument("--no-inat", action="store_true")
    ap.add_argument("--literature", help="CSV with lat,lon,label,source,evidence (hand-entered sites)")
    ap.add_argument("--out", default="nest_candidates.csv")
    a = ap.parse_args()

    rows = gbif_records(a.countries, a.months, a.bbox, a.max_gbif)
    print(f"GBIF: {len(rows)} records", file=sys.stderr)
    if not a.no_inat:
        ir = inat_records(a.months, a.bbox); print(f"iNaturalist text hits: {len(ir)}", file=sys.stderr)
        rows += ir
    for r in rows: r["evidence"] = evidence(r)
    if a.literature:
        for l in csv.DictReader(open(a.literature)):
            rows.append(dict(source="literature", id=l.get("label"), lat=float(l["lat"]), lon=float(l["lon"]),
                             uncertainty_m=l.get("uncertainty_m", ""), date=l.get("date", ""), month="", depth_m=l.get("depth_m", ""),
                             life_stage="", dataset=l.get("source", ""), basis="LITERATURE", notes=l.get("notes", ""),
                             media="", url=l.get("url", ""), evidence=int(l.get("evidence", 2))))
    rows.sort(key=lambda r: -r["evidence"])
    keys = ["evidence", "reviewed", "source", "id", "lat", "lon", "uncertainty_m", "date", "month", "depth_m",
            "life_stage", "dataset", "basis", "notes", "media", "url"]
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, keys, extrasaction="ignore"); w.writeheader()
        for r in rows: r.setdefault("reviewed", ""); w.writerow(r)
    gj = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
         "properties": {k: r.get(k) for k in keys if k not in ("lat", "lon")}} for r in rows if r["lat"] is not None]}
    json.dump(gj, open(a.out.rsplit(".", 1)[0] + ".geojson", "w"), default=str)
    from collections import Counter
    print("evidence levels:", dict(Counter(r["evidence"] for r in rows)), file=sys.stderr)

if __name__ == "__main__":
    main()
