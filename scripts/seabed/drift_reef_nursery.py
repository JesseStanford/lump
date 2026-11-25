#!/usr/bin/env python3
"""
drift_reef_nursery.py - where do young lumpfish drifting at the surface from candidate reefs end up?

Particles are released from the candidate reef patches of site_shortlist.py (same box, same patch
numbers) and carried by the daily surface currents from fetch_currents.py, with a random walk for the
mixing the daily means smooth out. Each particle records when it first reaches hard nursery (stony
shore or 0-3 m hard bottom) and eelgrass on the nursery grid, and whether it strands on a shore.

This is a screening model: daily mean surface currents, no tide, no direct wind drag on drift weed,
no larval behaviour (lumpfish larvae cling to algae near the nest, and juveniles ride drifting weed).
Read it as "which shores are downstream of which reefs", not as a dispersal kernel.

Outputs in --out:
  drift_by_patch.csv     per patch: particles, share reaching hard nursery / eelgrass within --days,
                         median days to first hard-nursery contact, share stranded, share still within
                         --retain-km of the release patch at the end, share carried out of the box
  drift_arrivals.tif     on the nursery grid: first hard-nursery / eelgrass contacts per cell
  drift_map.png          release patches, sample tracks and arrival density

Usage:
  python drift_reef_nursery.py --bbox 12.3 55.45 12.95 56.15 --currents data/dk_currents/currents_daily_surface.npz \\
      --erratic runs/dk_erratics/erratic_grid.tif --reefs data/dk/reefs_helcom_1170.tif \\
      --nursery runs/dk_nursery/nursery_grid.tif --out runs/oresund_drift
"""
import argparse, csv, os, sys
import numpy as np

M_PER_DEG = 111320.0

def bilinear(F, lon, lat, x, y):
    """F (ny, nx) on ascending lon/lat; returns values at (x, y), NaN outside or next to land."""
    fx = (x - lon[0]) / (lon[1] - lon[0]); fy = (y - lat[0]) / (lat[1] - lat[0])
    i0 = np.floor(fx).astype(int); j0 = np.floor(fy).astype(int)
    out = np.full(x.shape, np.nan)
    ok = (i0 >= 0) & (j0 >= 0) & (i0 < len(lon) - 1) & (j0 < len(lat) - 1)
    i, j, tx, ty = i0[ok], j0[ok], fx[ok] - i0[ok], fy[ok] - j0[ok]
    f00, f10, f01, f11 = F[j, i], F[j, i + 1], F[j + 1, i], F[j + 1, i + 1]
    w = np.stack([(1 - tx) * (1 - ty), tx * (1 - ty), (1 - tx) * ty, tx * ty])
    f = np.stack([f00, f10, f01, f11]); wet = np.isfinite(f)
    ws = (w * wet).sum(0)
    val = np.where(ws > 0.25, (np.nan_to_num(f) * w).sum(0) / np.maximum(ws, 1e-9), np.nan)  # tolerate partial land
    out[ok] = val
    return out

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bbox", nargs=4, type=float, required=True)
    ap.add_argument("--currents", required=True); ap.add_argument("--erratic", required=True)
    ap.add_argument("--reefs"); ap.add_argument("--nursery", required=True)
    ap.add_argument("--max-depth", type=float, default=10); ap.add_argument("--min-cells", type=int, default=2)
    ap.add_argument("--per-cell", type=int, default=2, help="particles per 250 m reef cell per release")
    ap.add_argument("--every-days", type=float, default=7, help="days between releases")
    ap.add_argument("--days", type=float, default=30, help="drift duration (days)")
    ap.add_argument("--dt-hours", type=float, default=1.0)
    ap.add_argument("--k", type=float, default=10.0, help="horizontal diffusivity m2/s for the random walk")
    ap.add_argument("--retain-km", type=float, default=5.0)
    ap.add_argument("--shore-km", type=float, default=1.5, help="stranded particles count the nearest nursery within this distance")
    ap.add_argument("--seed", type=int, default=1); ap.add_argument("--out", default="runs/drift")
    a = ap.parse_args()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sources
    sources.carry_args(a.out, a)
    import rasterio
    from rasterio.warp import transform
    from rasterio.windows import from_bounds
    from scipy import ndimage as ndi
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from reef_nursery_overlay import to_grid
    rng = np.random.default_rng(a.seed)

    # ---------- release patches, exactly as site_shortlist.py numbers them
    with rasterio.open(a.erratic) as s:
        bx, by = transform("EPSG:4326", s.crs, [a.bbox[0], a.bbox[2], a.bbox[0], a.bbox[2]], [a.bbox[1], a.bbox[1], a.bbox[3], a.bbox[3]])
        win = from_bounds(min(bx), min(by), max(bx), max(by), s.transform).round_offsets().round_lengths()
        score, depth = s.read(1, window=win), s.read(3, window=win); tr = s.window_transform(win); crs = s.crs
    shape = score.shape; res = abs(tr.a)
    reef = to_grid(a.reefs, shape, tr, crs)[0] if a.reefs else np.zeros(shape, bool)
    cand = (np.nan_to_num(score) >= 3) | (reef & np.isfinite(depth) & (depth > 0) & (depth <= a.max_depth))
    lab, n = ndi.label(cand, structure=np.ones((3, 3)))
    sizes = np.bincount(lab.ravel()); keep = [k for k in range(1, n + 1) if sizes[k] >= a.min_cells]
    rr, cc = np.nonzero(np.isin(lab, keep)); cell_patch = lab[rr, cc]
    print(f"{len(keep)} release patches, {len(rr)} reef cells")

    # ---------- currents
    C = np.load(a.currents, allow_pickle=False)
    lon, lat, td, U, V = C["lon"], C["lat"], C["tdays"], C["u"], C["v"]
    if lon[0] > lon[-1]: lon, U, V = lon[::-1], U[:, :, ::-1], V[:, :, ::-1]
    if lat[0] > lat[-1]: lat, U, V = lat[::-1], U[:, ::-1], V[:, ::-1]
    td = td + 0.5 if np.allclose(td % 1, 0) else td        # daily means: centre on noon
    gap = np.r_[np.diff(td) > 1.5, True]                    # last day of each contiguous run (year)
    print(f"Currents: {len(td)} days, {len(lon)} x {len(lat)} grid, source {C['source'] if 'source' in C else '?'}")

    # ---------- nursery grid
    with rasterio.open(a.nursery) as s:
        nbx, nby = transform("EPSG:4326", s.crs, [a.bbox[0], a.bbox[2], a.bbox[0], a.bbox[2]], [a.bbox[1], a.bbox[1], a.bbox[3], a.bbox[3]])
        nwin = from_bounds(min(nbx), min(nby), max(nbx), max(nby), s.transform).round_offsets().round_lengths()
        ncls = s.read(1, window=nwin, boundless=True, fill_value=255); ntr, ncrs = s.window_transform(nwin), s.crs
    NH, NW = ncls.shape; nres = abs(ntr.a)
    hard_m, eel_m = np.isin(ncls, [1, 2]), ncls == 3
    # the current model's coastline is ~1 nautical mile coarse: a particle stranded on it is credited with
    # the nearest nursery within --shore-km of where it stopped
    near = {}
    for nm, msk in (("hard", hard_m), ("eel", eel_m)):
        dd, (ir, ic) = ndi.distance_transform_edt(~msk, return_indices=True) if msk.any() else (np.full(msk.shape, np.inf), (None, None))
        near[nm] = (dd * nres / 1000, ir, ic)

    # ---------- releases: every --every-days inside each contiguous run, leaving room for --days where possible
    runs, start = [], 0
    for i, g in enumerate(gap):
        if g: runs.append((td[start], td[i])); start = i + 1
    rel_t = np.concatenate([np.arange(t0, max(t0, t1 - a.days) + 1e-9, a.every_days) for t0, t1 in runs])
    cx, cy = tr * (cc + 0.5, rr + 0.5)
    clon, clat = (np.array(v) for v in transform(crs, "EPSG:4326", list(cx), list(cy)))
    nrel = len(rel_t) * len(rr) * a.per_cell
    print(f"{len(rel_t)} release dates x {len(rr)} cells x {a.per_cell} = {nrel} particles, {a.days:g} days each")

    rep = np.repeat(np.arange(len(rr)), a.per_cell)
    P_cell = np.tile(rep, len(rel_t)); P_t0 = np.repeat(rel_t, len(rep))
    jit = res / M_PER_DEG
    x = clon[P_cell] + (rng.random(nrel) - 0.5) * jit / np.cos(np.radians(clat[P_cell]))
    y = clat[P_cell] + (rng.random(nrel) - 0.5) * jit
    x0, y0 = x.copy(), y.copy()
    t_hard = np.full(nrel, np.nan); t_eel = np.full(nrel, np.nan)
    stranded = np.zeros(nrel, bool); left = np.zeros(nrel, bool); active = np.ones(nrel, bool)
    hard_hits = np.zeros((NH, NW), "int32"); eel_hits = np.zeros((NH, NW), "int32")
    sample = rng.choice(nrel, size=min(300, nrel), replace=False); tracks = {int(i): [(x[i], y[i])] for i in sample}

    dt = a.dt_hours / 24.0; nsteps = int(round(a.days / dt)); sig = np.sqrt(2 * a.k * dt * 86400)

    def uv_at(xq, yq, tq):
        k = np.clip(np.searchsorted(td, tq) - 1, 0, len(td) - 2)
        w = np.clip((tq - td[k]) / (td[k + 1] - td[k]), 0, 1)
        broken = gap[k] & (tq > td[k])                     # beyond the end of a year's run
        uq = np.empty(xq.shape); vq = np.empty(xq.shape)
        for kk in np.unique(k):
            m = k == kk
            u0 = bilinear(U[kk], lon, lat, xq[m], yq[m]); v0 = bilinear(V[kk], lon, lat, xq[m], yq[m])
            u1 = bilinear(U[kk + 1], lon, lat, xq[m], yq[m]); v1 = bilinear(V[kk + 1], lon, lat, xq[m], yq[m])
            uq[m] = (1 - w[m]) * u0 + w[m] * np.where(gap[kk], u0, u1)
            vq[m] = (1 - w[m]) * v0 + w[m] * np.where(gap[kk], v0, v1)
        return uq, vq, broken

    def check_nursery(idx, tnow, strand):
        if not len(idx): return
        nx, ny = transform("EPSG:4326", ncrs, list(x[idx]), list(y[idx]))
        col, row = ~ntr * (np.array(nx), np.array(ny))
        col = np.floor(col).astype(int); row = np.floor(row).astype(int)
        inb = (row >= 0) & (row < NH) & (col >= 0) & (col < NW)
        r, c, ii, tn, st = row[inb], col[inb], idx[inb], tnow[inb], strand[inb]
        for nm, msk, tarr, hits in (("hard", hard_m, t_hard, hard_hits), ("eel", eel_m, t_eel, eel_hits)):
            dd, ir, ic = near[nm]
            rr_, cc_ = r.copy(), c.copy()
            snap = st & ~msk[r, c] & (dd[r, c] <= a.shore_km)
            if ir is not None: rr_[snap], cc_[snap] = ir[r[snap], c[snap]], ic[r[snap], c[snap]]
            hit = (msk[r, c] | snap) & np.isnan(tarr[ii])
            tarr[ii[hit]] = tn[hit]
            np.add.at(hits, (rr_[hit], cc_[hit]), 1)

    for step in range(nsteps):
        idx = np.nonzero(active)[0]
        if not len(idx): break
        tq = P_t0[idx] + step * dt
        u1, v1, br = uv_at(x[idx], y[idx], tq)
        coslat = np.cos(np.radians(y[idx]))
        xm = x[idx] + 0.5 * dt * 86400 * np.nan_to_num(u1) / (M_PER_DEG * coslat)
        ym = y[idx] + 0.5 * dt * 86400 * np.nan_to_num(v1) / M_PER_DEG
        u2, v2, _ = uv_at(xm, ym, tq + 0.5 * dt)               # midpoint (RK2)
        u2 = np.where(np.isfinite(u2), u2, u1); v2 = np.where(np.isfinite(v2), v2, v1)
        nx_ = x[idx] + (dt * 86400 * u2 + sig * rng.standard_normal(len(idx))) / (M_PER_DEG * coslat)
        ny_ = y[idx] + (dt * 86400 * v2 + sig * rng.standard_normal(len(idx))) / M_PER_DEG
        out_box = (nx_ < a.bbox[0]) | (nx_ > a.bbox[2]) | (ny_ < a.bbox[1]) | (ny_ > a.bbox[3])
        ut, _, _ = uv_at(nx_, ny_, tq + dt)
        land = ~np.isfinite(ut) & ~out_box
        # a step into land strands the particle on the shore it hit (its last wet position + half the step)
        x[idx] = np.where(land, 0.5 * (x[idx] + nx_), nx_); y[idx] = np.where(land, 0.5 * (y[idx] + ny_), ny_)
        check_nursery(idx, tq + dt, land)
        stranded[idx[land]] = True; left[idx[out_box]] = True
        stop = land | out_box | br | ~np.isfinite(u1)
        active[idx[stop]] = False
        for i in tracks:
            if active[i]: tracks[i].append((x[i], y[i]))
        if step % 24 == 0: print(f"  day {step * dt:4.0f}: {int(active.sum())} drifting", end="\r", file=sys.stderr)
    print()

    # ---------- per patch table
    P_patch = cell_patch[P_cell]
    dkm = np.hypot((x - x0) * M_PER_DEG * np.cos(np.radians(y0)), (y - y0) * M_PER_DEG) / 1000
    d_hard = t_hard - P_t0; d_eel = t_eel - P_t0
    rows = []
    for k in keep:
        m = P_patch == k; nk = int(m.sum())
        if not nk: continue
        ccx, ccy = tr * (cc[cell_patch == k] + 0.5, rr[cell_patch == k] + 0.5)
        plon, plat = transform(crs, "EPSG:4326", [float(np.mean(ccx))], [float(np.mean(ccy))])
        hd = d_hard[m]
        rows.append({"patch": int(k), "lat": round(plat[0], 4), "lon": round(plon[0], 4), "particles": nk,
                     "reach_hard_nursery": round(float(np.isfinite(hd).mean()), 3),
                     "median_days_to_hard": round(float(np.nanmedian(hd)), 1) if np.isfinite(hd).any() else "",
                     "reach_eelgrass": round(float(np.isfinite(d_eel[m]).mean()), 3),
                     "stranded": round(float(stranded[m].mean()), 3),
                     f"within_{a.retain_km:g}km_at_end": round(float((dkm[m] <= a.retain_km).mean()), 3),
                     "left_box": round(float(left[m].mean()), 3)})
    rows.sort(key=lambda r: -r["reach_hard_nursery"])
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "drift_by_patch.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f"{'#':>3s} {'n':>6s} {'hard':>5s} {'days':>5s} {'eel':>5s} {'strand':>6s} {'stay':>5s} {'left':>5s}")
    for r in rows[:30]:
        print(f"{r['patch']:>3d} {r['particles']:>6d} {r['reach_hard_nursery']:>5.2f} {str(r['median_days_to_hard']):>5s} "
              f"{r['reach_eelgrass']:>5.2f} {r['stranded']:>6.2f} {r[f'within_{a.retain_km:g}km_at_end']:>5.2f} {r['left_box']:>5.2f}")
    print(f"All particles: {np.isfinite(d_hard).mean():.2f} reach hard nursery, {np.isfinite(d_eel).mean():.2f} eelgrass, "
          f"{stranded.mean():.2f} strand, {left.mean():.2f} leave the box")

    with rasterio.open(os.path.join(a.out, "drift_arrivals.tif"), "w", driver="GTiff", height=NH, width=NW, count=2,
                       dtype="int32", crs=ncrs, transform=ntr, compress="deflate") as d:
        d.write(hard_hits, 1); d.write(eel_hits, 2)
        d.set_band_description(1, "first_hard_nursery_contacts"); d.set_band_description(2, "first_eelgrass_contacts")

    # ---------- map in lon/lat
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 9))
    wet = np.isfinite(U).any(0)
    ax.pcolormesh(lon, lat, np.where(wet, np.nan, 1.0), cmap="Greys", vmin=0, vmax=2.5, shading="nearest")
    for i, pts in tracks.items():
        p = np.array(pts); ax.plot(p[:, 0], p[:, 1], lw=0.3, c="0.4", alpha=0.6)
    hr, hc = np.nonzero(hard_hits)
    if len(hr):
        hx, hy = ntr * (hc + 0.5, hr + 0.5); hlon, hlat = transform(ncrs, "EPSG:4326", list(hx), list(hy))
        ax.scatter(hlon, hlat, s=3 + 20 * hard_hits[hr, hc] / hard_hits.max(), c="#7f2704", label="hard nursery reached")
    ax.scatter(clon, clat, s=4, c="#cb181d", label="release reef cells")
    for r in rows[:25]:
        ax.annotate(str(r["patch"]), (r["lon"], r["lat"]), fontsize=7, ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.15", fc="w", ec="0.5", lw=0.5))
    ax.set_xlim(a.bbox[0], a.bbox[2]); ax.set_ylim(a.bbox[1], a.bbox[3])
    ax.set_aspect(1 / np.cos(np.radians(np.mean(a.bbox[1::2])))); ax.legend(loc="lower left", fontsize=7)
    ax.set_title(f"Surface drift from candidate reefs, {a.days:g} days (grey: sample tracks)")
    fig.savefig(os.path.join(a.out, "drift_map.png"), dpi=170, bbox_inches="tight")
    print("Results in", a.out)

if __name__ == "__main__":
    main()
