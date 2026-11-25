#!/usr/bin/env python3
"""
trawl_vs_reefs.py - are trawl hauls that caught lumpfish closer to candidate erratic reef ground
than hauls that caught none? Presence/absence test on DATRAS hauls (fetch_datras.py) against the
erratic screen (erratic_overlay.py -> erratic_grid.tif).

For every haul: distance to the nearest target cell (default category lag_on_till_shallow; or
--target-score 3/2), haul depth, quarter. Then per quarter:
  - median distance, lumpfish hauls vs empty hauls, with a Mann-Whitney U test
  - the same, restricted to the depth range where lumpfish were caught (depth confound)
  - share of hauls with lumpfish in distance bands
Quarter 1 (Feb-Mar) is the pre-spawning inshore migration, so it is the quarter that matters most.

Usage:
  python trawl_vs_reefs.py --hauls data/dk/datras_hauls.csv --grid runs/dk_erratics/erratic_grid.tif --out runs/dk_trawl_vs_reefs
"""
import argparse, csv, json, os, sys
import numpy as np

CATS = ["other", "till_buried", "coarse_no_source", "lag_on_till_deep", "lag_on_till_shallow"]

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hauls", required=True); ap.add_argument("--grid", required=True)
    ap.add_argument("--target", default="lag_on_till_shallow", help=f"category name, one of {CATS}")
    ap.add_argument("--target-score", type=int, help="use score >= this instead of a category")
    ap.add_argument("--bands", default="0,5,10,20,40,80", help="distance band edges, km")
    ap.add_argument("--out", default="runs/trawl_vs_reefs")
    a = ap.parse_args()
    import rasterio
    from rasterio.warp import transform
    from scipy import ndimage as ndi, stats

    with rasterio.open(a.grid) as s:
        score, cat = s.read(1), s.read(2); tr, crs = s.transform, s.crs; res = abs(tr.a)
    tgt = (score >= a.target_score) if a.target_score else (cat == CATS.index(a.target))
    label = f"score>={a.target_score}" if a.target_score else a.target
    if not tgt.any(): raise SystemExit(f"No {label} cells in the grid.")
    dist = ndi.distance_transform_edt(~tgt) * res / 1000.0   # km

    H = list(csv.DictReader(open(a.hauls, encoding="utf-8")))
    xs, ys = transform("EPSG:4326", crs, [float(h["lon"]) for h in H], [float(h["lat"]) for h in H])
    inv = ~tr; rows = []
    for h, x, y in zip(H, xs, ys):
        c, r = inv * (x, y); r, c = int(r), int(c)
        if not (0 <= r < dist.shape[0] and 0 <= c < dist.shape[1]): continue
        d = h.get("depth_m"); d = float(d) if d not in ("", "None", None) else np.nan
        rows.append(dict(h, dist_to_target_km=round(float(dist[r, c]), 2), depth_m=d,
                         present=int(float(h["lumpfish_n"] or 0) > 0)))
    if not rows: raise SystemExit("No hauls fall inside the grid.")
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "hauls_with_distance.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)

    edges = [float(e) for e in a.bands.split(",")] + [1e9]
    summary = {"target": label, "quarters": {}}
    lines = []
    for q in sorted({r["quarter"] for r in rows}) + ["all"]:
        R = rows if q == "all" else [r for r in rows if r["quarter"] == q]
        P = np.array([r["dist_to_target_km"] for r in R if r["present"]]); A = np.array([r["dist_to_target_km"] for r in R if not r["present"]])
        out = {"hauls": len(R), "with_lumpfish": int(P.size)}
        if P.size >= 3 and A.size >= 3:
            u = stats.mannwhitneyu(P, A, alternative="less")
            out.update(median_km_lumpfish=round(float(np.median(P)), 1), median_km_empty=round(float(np.median(A)), 1),
                       p_closer=float(f"{u.pvalue:.3g}"))
            dp = np.array([r["depth_m"] for r in R if r["present"]], float); dp = dp[np.isfinite(dp)]
            if dp.size >= 3:
                lo, hi = np.percentile(dp, 5), np.percentile(dp, 95)
                Rd = [r for r in R if np.isfinite(r["depth_m"]) and lo <= r["depth_m"] <= hi]
                P2 = np.array([r["dist_to_target_km"] for r in Rd if r["present"]]); A2 = np.array([r["dist_to_target_km"] for r in Rd if not r["present"]])
                if P2.size >= 3 and A2.size >= 3:
                    u2 = stats.mannwhitneyu(P2, A2, alternative="less")
                    out["depth_matched"] = {"depth_range_m": [round(lo, 1), round(hi, 1)], "hauls": len(Rd), "with_lumpfish": int(P2.size),
                                            "median_km_lumpfish": round(float(np.median(P2)), 1), "median_km_empty": round(float(np.median(A2)), 1),
                                            "p_closer": float(f"{u2.pvalue:.3g}")}
        bands = []
        for lo_, hi_ in zip(edges[:-1], edges[1:]):
            B = [r for r in R if lo_ <= r["dist_to_target_km"] < hi_]
            if B: bands.append({"band_km": f"{lo_:g}-{'' if hi_ > 1e8 else f'{hi_:g}'}", "hauls": len(B),
                                "with_lumpfish": sum(r["present"] for r in B), "share": round(sum(r["present"] for r in B) / len(B), 4)})
        out["by_distance"] = bands; summary["quarters"][str(q)] = out
        lines.append(f"Q{q}: {out['hauls']} hauls, {out['with_lumpfish']} with lumpfish"
                     + (f"; median distance {out['median_km_lumpfish']} vs {out['median_km_empty']} km (p={out['p_closer']})" if "p_closer" in out else "; too few for a test")
                     + (f"; depth-matched {out['depth_matched']['median_km_lumpfish']} vs {out['depth_matched']['median_km_empty']} km (p={out['depth_matched']['p_closer']})" if "depth_matched" in out else ""))
    json.dump(summary, open(os.path.join(a.out, "trawl_vs_reefs.json"), "w"), indent=2)
    with open(os.path.join(a.out, "presence_by_distance.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["quarter", "band_km", "hauls", "with_lumpfish", "share"])
        for q, o in summary["quarters"].items():
            for b in o["by_distance"]: w.writerow([q, b["band_km"], b["hauls"], b["with_lumpfish"], b["share"]])
    print(f"Target: {label}"); print("\n".join(lines)); print("Results in", a.out)

if __name__ == "__main__":
    main()
