#!/usr/bin/env python3
"""
sources.py - keep track of where every downloaded file and every result came from.

Every fetch script calls record() after it writes a file: a row goes into sources.csv in the same
folder (file, source key, URL, query, access time). Every analysis script calls carry() with its
input files: the matching rows are copied into sources.csv in its output folder, and SOURCES.md there
lists the full citations, looked up by key in citations/references.csv. So any results folder can be
cited on its own.

Backfill (for folders made before this existed, using file names and file dates):
  python sources.py --backfill data runs
"""
import argparse, csv, datetime as dt, fnmatch, glob, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REFS = os.path.join(HERE, "..", "..", "citations", "references.csv")
FIELDS = ["file", "source_key", "url", "query", "accessed_utc", "how"]

# URL fragment -> dataset key in citations/references.csv
URL_KEYS = [
    ("emodnet_seafloor_geology", "emodnet_seafloorgeology"),
    ("seabed_substrate", "emodnet_substrate250k"),
    ("emodnet-geology.eu", "emodnet_substrate250k"),
    ("emodnet-bathymetry", "emodnet_dtm2024"),
    ("Zostera_marina", "helcom_zostera"),
    ("Reefs_1170", "helcom_reefs1170"),
    ("Natura2000", "eea_natura2000"),
    ("ea-surfzone-dem", "ea_surfzone2019"),
    ("lidar-composite-digital-terrain-model", "ea_lidar_dtm1m"),
    ("BALTICSEA_MULTIYEAR_PHY", "cmems_bal_phy_my"),
    ("api.gbif.org", "gbif_occurrences"),
    ("inaturalist.org", "inaturalist_observations"),
    ("datras.ices.dk", "ices_datras"),
    ("marinespecies.org", "worms"),
]

# downloaded file name -> dataset keys (for backfill)
FILE_KEYS = [
    ("quat_lithology.geojson", ["emodnet_seafloorgeology"]),
    ("geomorph_polys.geojson", ["emodnet_seafloorgeology"]),
    ("geomorph_lines.geojson", ["emodnet_seafloorgeology"]),
    ("substrate.geojson", ["emodnet_substrate250k"]),
    ("emodnet_dtm.tif", ["emodnet_dtm2024"]),
    ("eelgrass_helcom.*", ["helcom_zostera"]),
    ("reefs_helcom_1170.*", ["helcom_reefs1170"]),
    ("n2000_sites.geojson", ["eea_natura2000"]),
    ("surfzone_2m.tif", ["ea_surfzone2019"]),
    ("lidar_dtm_1m.tif", ["ea_lidar_dtm1m"]),
    ("currents_*", ["cmems_bal_phy_my"]),
    ("nest_candidates*.csv", ["gbif_occurrences", "inaturalist_observations"]),
    ("nest_candidates*.geojson", ["gbif_occurrences", "inaturalist_observations"]),
    ("datras_hauls*.csv", ["ices_datras", "worms"]),
]

# result file name -> dataset keys its inputs came from (for backfill of runs/)
RESULT_KEYS = [
    ("erratic_grid.tif", ["emodnet_substrate250k", "emodnet_seafloorgeology", "emodnet_dtm2024"]),
    ("crosstab_substrate_source_depth.csv", ["emodnet_substrate250k", "emodnet_seafloorgeology", "emodnet_dtm2024"]),
    ("categories.csv", ["emodnet_substrate250k", "emodnet_seafloorgeology", "emodnet_dtm2024"]),
    ("erratic_preview.png", ["emodnet_substrate250k", "emodnet_seafloorgeology", "emodnet_dtm2024"]),
    ("points_with_erratic.csv", ["emodnet_substrate250k", "emodnet_seafloorgeology", "emodnet_dtm2024",
                                 "gbif_occurrences", "inaturalist_observations"]),
    ("nursery_*", ["emodnet_substrate250k", "emodnet_dtm2024", "helcom_zostera"]),
    ("screen_vs_mapped_reefs.csv", ["emodnet_substrate250k", "emodnet_seafloorgeology", "emodnet_dtm2024", "helcom_reefs1170"]),
    ("reef_to_nursery_distance.csv", ["emodnet_substrate250k", "emodnet_seafloorgeology", "emodnet_dtm2024",
                                      "helcom_reefs1170", "helcom_zostera"]),
    ("reef_nursery_map.png", ["emodnet_substrate250k", "emodnet_seafloorgeology", "emodnet_dtm2024",
                              "helcom_reefs1170", "helcom_zostera"]),
    ("shortlist*", ["emodnet_substrate250k", "emodnet_seafloorgeology", "emodnet_dtm2024", "helcom_reefs1170",
                    "helcom_zostera", "gbif_occurrences", "inaturalist_observations"]),
    ("drift_*", ["emodnet_substrate250k", "emodnet_seafloorgeology", "emodnet_dtm2024", "helcom_reefs1170",
                 "helcom_zostera", "cmems_bal_phy_my"]),
    ("trawl_*", ["ices_datras", "worms", "emodnet_substrate250k", "emodnet_seafloorgeology", "emodnet_dtm2024"]),
]

def key_for_url(url):
    for frag, key in URL_KEYS:
        if frag.lower() in (url or "").lower(): return key
    return "unknown"

def _now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _read(path):
    if not os.path.exists(path): return []
    with open(path, newline="", encoding="utf-8") as f:
        return [{k: r.get(k, "") for k in FIELDS} for r in csv.DictReader(f)]

def _write(folder, rows):
    path = os.path.join(folder or ".", "sources.csv")
    old = _read(path); seen = {(r["file"], r["source_key"], r["url"]) for r in old}
    new = []
    for r in rows:
        k = (r["file"], r["source_key"], r["url"])
        if k not in seen: seen.add(k); new.append(r)
    # a new download row replaces any older row (download, backfilled or guessed) for the same file and source;
    # a backfilled row is skipped where the file is already described
    files_new = {(r["file"], r["source_key"]) for r in new if r["how"].startswith("download")}
    keep = [r for r in old if (r["file"], r["source_key"]) not in files_new]
    described = {(r["file"], r["source_key"]) for r in keep}
    new = [r for r in new if r["how"].startswith("download") or (r["file"], r["source_key"]) not in described]
    os.makedirs(folder or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS); w.writeheader(); w.writerows(keep + new)
    write_md(folder)

def record(out_file, url, query="", key=None, how="download"):
    """Call after a fetch script writes out_file (downloaded from url)."""
    try:
        _write(os.path.dirname(os.path.abspath(out_file)),
               [{"file": os.path.basename(out_file), "source_key": key or key_for_url(url), "url": url,
                 "query": query, "accessed_utc": _now(), "how": how}])
    except Exception as e:                      # provenance must never break a download
        print(f"(could not write sources.csv: {e})", file=sys.stderr)

def _rows_for_input(path):
    """(rows, folder the rows' file names are relative to) for an input file or folder."""
    if os.path.isdir(path):
        return _read(os.path.join(path, "sources.csv")), os.path.abspath(path)
    folder, base = os.path.split(os.path.abspath(path))
    rows = _read(os.path.join(folder, "sources.csv"))
    mine = [r for r in rows if r["file"] == base or fnmatch.fnmatch(base, r["file"])]
    if not mine and any(r["how"].startswith("input") for r in rows):
        mine = rows                      # a results folder: its files inherit all of the folder's inputs
    if mine: return mine, folder
    for pat, keys in FILE_KEYS + RESULT_KEYS:
        if fnmatch.fnmatch(base, pat):
            ts = dt.datetime.fromtimestamp(os.path.getmtime(path), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if os.path.exists(path) else ""
            return [{"file": base, "source_key": k, "url": "", "query": "", "accessed_utc": ts, "how": "guessed from file name"} for k in keys], folder
    return [], folder

def carry(out_dir, inputs, extra_keys=()):
    """Call at the end of an analysis: copy the provenance of every input into out_dir/sources.csv."""
    try:
        rows = []
        for p in inputs:
            if not p: continue
            got, base = _rows_for_input(p)
            if not got:
                got = [{"file": os.path.basename(p), "source_key": "unknown_source", "url": "", "query": "", "accessed_utc": "",
                        "how": "input with no recorded source: run sources --backfill or add a row to its sources.csv"}]
            for r in got:
                r = dict(r); r["how"] = r["how"] if r["how"].startswith("input") else f"input: {r['how']}"
                if r["file"] and not os.path.isabs(r["file"]):
                    r["file"] = os.path.relpath(os.path.join(base, r["file"]), os.path.abspath(out_dir))
                rows.append(r)
        for k in extra_keys:
            rows.append({"file": "", "source_key": k, "url": "", "query": "", "accessed_utc": "", "how": "method"})
        _write(out_dir, rows)
    except Exception as e:
        print(f"(could not write sources.csv: {e})", file=sys.stderr)

def _paths_in(v):
    if isinstance(v, (list, tuple)):
        for x in v: yield from _paths_in(x)
    elif isinstance(v, str) and v and os.path.exists(v):
        yield v

def carry_args(out_dir, args, extra_keys=()):
    """Register carry() for every existing file or folder named in an argparse namespace; runs at exit."""
    import atexit
    ins = [p for k, v in vars(args).items() if k not in ("out", "run") for p in _paths_in(v)]
    def _go():
        if out_dir and os.path.isdir(out_dir): carry(out_dir, ins, extra_keys)
    atexit.register(_go)

def load_refs():
    if not os.path.exists(REFS): return {}
    with open(REFS, newline="", encoding="utf-8") as f:
        return {r["key"]: r for r in csv.DictReader(f)}

def citation(r):
    bits = [r.get("authors", "").strip("{}"), f"({r['year']})" if r.get("year") else "", r.get("title", ""), r.get("venue", "")]
    s = ". ".join(b for b in bits if b).replace(". (", " (")
    if r.get("doi"): s += f". https://doi.org/{r['doi']}"
    elif r.get("url"): s += f". {r['url']}"
    if r.get("licence"): s += f". Licence: {r['licence']}"
    return s.rstrip(".") + "."

def write_md(folder):
    rows = _read(os.path.join(folder, "sources.csv")); refs = load_refs()
    keys = []
    for r in rows:
        if r["source_key"] not in keys: keys.append(r["source_key"])
    lines = ["# Sources for this folder", "", "Generated from sources.csv and citations/references.csv. Cite these when using the files here.", ""]
    for k in keys:
        ref = refs.get(k)
        acc = sorted({r["accessed_utc"][:10] for r in rows if r["source_key"] == k and r["accessed_utc"]})
        files = sorted({r["file"] for r in rows if r["source_key"] == k and r["file"]})
        lines.append(f"- **{k}**: {citation(ref) if ref else 'NOT IN citations/references.csv - add it'}"
                     + (f" Accessed {', '.join(acc)}." if acc else "") + (f" Files: {', '.join(files)}." if files else ""))
    with open(os.path.join(folder, "SOURCES.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def backfill(roots):
    for root in roots:
        for folder, _, files in os.walk(root):
            if ".venv" in folder or "__pycache__" in folder: continue
            rows = []
            for fn in files:
                if fn in ("sources.csv", "SOURCES.md"): continue
                p = os.path.join(folder, fn)
                for pat, keys in FILE_KEYS + RESULT_KEYS:
                    if fnmatch.fnmatch(fn, pat):
                        ts = dt.datetime.fromtimestamp(os.path.getmtime(p), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                        rows += [{"file": fn, "source_key": k, "url": "", "query": "", "accessed_utc": ts,
                                  "how": "backfilled from file name (date = file date)"} for k in keys]
                        break
            if rows:
                _write(folder, rows); print(f"{folder}: {len(rows)} rows -> sources.csv, SOURCES.md")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backfill", nargs="+", metavar="FOLDER", help="write sources.csv into existing data / runs folders")
    ap.add_argument("--check", action="store_true", help="list source keys used in sources.csv files that citations/references.csv lacks")
    ap.add_argument("roots", nargs="*", default=["data", "runs"])
    a = ap.parse_args()
    if a.backfill: backfill(a.backfill)
    refs = load_refs(); missing = set()
    for root in (a.backfill or a.roots):
        for p in glob.glob(os.path.join(root, "**", "sources.csv"), recursive=True):
            missing |= {r["source_key"] for r in _read(p)} - set(refs)
    print("All source keys are in citations/references.csv." if not missing else f"Keys missing from references.csv: {sorted(missing)}")

if __name__ == "__main__":
    main()
