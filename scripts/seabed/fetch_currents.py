#!/usr/bin/env python3
"""
fetch_currents.py - spring current fields for the reef -> nursery drift, from the Copernicus Marine
Baltic Sea physics reanalysis (BALTICSEA_MULTIYEAR_PHY_003_011, DMI NEMO, ~1 nautical mile, Kattegat,
Belts, Oresund and the Baltic; western Skagerrak is outside it).

Access, tried in this order:
  1. anonymous read of the public ARCO Zarr copy (no account): the dataset is located through the
     public STAC catalogue and opened over HTTPS with xarray
  2. the copernicusmarine toolbox, if it is installed and logged in (only needed if 1 is refused)
Run with --test first: it only checks access and prints what it finds.

Outputs in --out:
  currents_mean.tif        EPSG:4326, mean over the chosen months and years, bands:
                           1 u_surface 2 v_surface 3 u_0_10m 4 v_0_10m 5 u_bottom 6 v_bottom (m/s,
                           u east, v north; bottom = deepest wet level down to --max-depth) 7 bottom_level_m
  currents_mean.png        arrows of the surface and near-bottom means
  currents_daily_surface.npz   daily surface u, v for the chosen months and years (input to drift_reef_nursery.py)

Usage:
  python fetch_currents.py --test
  python fetch_currents.py --bbox 11.5 55.3 13.2 56.3 --years 2019 2023 --months 4 5 6 7 --out data/dk_currents
"""
import argparse, json, os, re, sys, time, urllib.request, urllib.error
import numpy as np
import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)

STAC_BASES = ["https://stac.marine.copernicus.eu/metadata",
              "https://s3.waw3-1.cloudferro.com/mdl-metadata/metadata"]

def get_json(url, tries=3):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "lump-currents"}), timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (403, 404): raise
            err = e
        except Exception as e:
            err = e
        time.sleep(2 * (k + 1))
    raise err

def find_dataset(product, pattern):
    """Return (dataset id, {asset name: href}) for the newest dataset of `product` whose id matches `pattern`."""
    last = None
    for base in STAC_BASES:
        try:
            prod = get_json(f"{base}/{product}/product.stac.json")
        except Exception as e:
            last = f"{base}: {e}"; continue
        items = [l["href"] for l in prod.get("links", []) if l.get("rel") == "item"]
        hits = sorted(h for h in items if re.search(pattern, h))
        if not hits:
            raise SystemExit(f"No dataset matching {pattern} in {product}. Datasets listed:\n  " + "\n  ".join(items))
        href = hits[-1]
        url = href if href.startswith("http") else f"{base}/{product}/{href.lstrip('./')}"
        item = get_json(url)
        assets = {k: v.get("href") for k, v in item.get("assets", {}).items()}
        return item.get("id", href), assets
    raise SystemExit(f"Could not read the Copernicus Marine catalogue ({last}). Check the internet connection.")

def open_any(product, pattern, prefer="geoChunked"):
    import xarray as xr
    did, assets = find_dataset(product, pattern)
    print(f"Dataset {did}; assets: {', '.join(assets)}")
    order = [prefer] + [k for k in ("geoChunked", "timeChunked") if k != prefer]
    errs = []
    for k in order:
        href = assets.get(k)
        if not href: continue
        try:
            ds = xr.open_zarr(href, consolidated=None, chunks=None)
            print(f"Opened {k} anonymously: {href}")
            return ds, did
        except Exception as e:
            errs.append(f"{k}: {type(e).__name__}: {str(e)[:200]}")
    print("Anonymous read refused:\n  " + "\n  ".join(errs))
    try:
        import copernicusmarine
    except ImportError:
        raise SystemExit("No anonymous access, and the copernicusmarine toolbox is not installed.\n"
                         "If you get a Copernicus Marine login later:  .venv\\Scripts\\python -m pip install copernicusmarine\n"
                         "then:  .venv\\Scripts\\copernicusmarine login   and run this again.")
    base_id = re.sub(r"_\d{6}$", "", did)
    print(f"Trying the copernicusmarine toolbox with dataset {base_id} ...")
    return copernicusmarine.open_dataset(dataset_id=base_id), did

def coord(ds, *names):
    for n in names:
        if n in ds.coords or n in ds.dims: return n
    raise SystemExit(f"None of {names} in dataset coords {list(ds.coords)}")

def velocity_vars(ds):
    u = v = None
    for n, var in ds.data_vars.items():
        sn = var.attrs.get("standard_name", "")
        if sn == "eastward_sea_water_velocity" or n == "uo": u = u or n
        if sn == "northward_sea_water_velocity" or n == "vo": v = v or n
    if not (u and v): raise SystemExit(f"No current variables found; variables: {list(ds.data_vars)}")
    return u, v

def subset(ds, a):
    lon, lat = coord(ds, "longitude", "lon"), coord(ds, "latitude", "lat")
    lo, la = ds[lon].values, ds[lat].values
    ds = ds.sel({lon: slice(a.bbox[0], a.bbox[2]) if lo[0] < lo[-1] else slice(a.bbox[2], a.bbox[0]),
                 lat: slice(a.bbox[1], a.bbox[3]) if la[0] < la[-1] else slice(a.bbox[3], a.bbox[1])})
    t = coord(ds, "time")
    tt = ds[t].dt
    keep = tt.month.isin(a.months) & (tt.year >= a.years[0]) & (tt.year <= a.years[1])
    return ds.isel({t: np.nonzero(keep.values)[0]}), lon, lat, t

def north_up(arr, latv):
    return arr[..., ::-1, :] if latv[0] < latv[-1] else arr

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bbox", nargs=4, type=float, default=[11.5, 55.3, 13.2, 56.3], help="lon_min lat_min lon_max lat_max")
    ap.add_argument("--years", nargs=2, type=int, default=[2019, 2023])
    ap.add_argument("--months", nargs="+", default=["4", "5", "6", "7"])
    ap.add_argument("--max-depth", type=float, default=30, help="deepest level read for the near-bottom mean (m)")
    ap.add_argument("--product", default="BALTICSEA_MULTIYEAR_PHY_003_011")
    ap.add_argument("--monthly", default=r"_P1M-m"); ap.add_argument("--daily", default=r"_P1D-m")
    ap.add_argument("--skip-daily", action="store_true", help="only the monthly means")
    ap.add_argument("--test", action="store_true", help="only check access and describe the datasets")
    ap.add_argument("--out", default="data/dk_currents")
    a = ap.parse_args()
    a.months = [int(m) for s in a.months for m in re.split(r"[,\s]+", str(s)) if m]

    if a.test:
        for pat in (a.monthly, a.daily):
            ds, did = open_any(a.product, pat)
            u, v = velocity_vars(ds)
            t = coord(ds, "time")
            print(f"  {did}: {u}/{v}, dims {dict(ds[u].sizes)}, time {str(ds[t].values[0])[:10]} to {str(ds[t].values[-1])[:10]}")
            lon, lat = coord(ds, "longitude", "lon"), coord(ds, "latitude", "lat")
            print(f"  lon {float(ds[lon].min()):.2f}..{float(ds[lon].max()):.2f}, lat {float(ds[lat].min()):.2f}..{float(ds[lat].max()):.2f}")
        print("Access OK.")
        return

    import rasterio
    from rasterio.transform import from_origin
    os.makedirs(a.out, exist_ok=True)

    # ---------- monthly means: surface, 0-10 m, near bottom
    ds, did = open_any(a.product, a.monthly)
    u, v = velocity_vars(ds)
    ds, lon, lat, t = subset(ds, a)
    dep = coord(ds, "depth")
    ds = ds.sel({dep: slice(0, a.max_depth)})
    z = ds[dep].values; nt = ds.sizes[t]
    if nt == 0: raise SystemExit("No time steps in the chosen years and months.")
    print(f"Monthly: {nt} months, {len(z)} levels to {z[-1]:.1f} m, grid {ds.sizes[lon]} x {ds.sizes[lat]}")
    H, W = ds.sizes[lat], ds.sizes[lon]
    acc = {k: np.zeros((H, W)) for k in ("us", "vs", "u10", "v10", "ub", "vb")}; cnt = np.zeros((H, W))
    botz = np.full((H, W), np.nan); upper = z <= 10
    for i in range(nt):
        U = ds[u].isel({t: i}).values.astype("float64"); V = ds[v].isel({t: i}).values.astype("float64")  # depth, lat, lon
        wet = np.isfinite(U)
        last = np.where(wet.any(0), wet.shape[0] - 1 - np.argmax(wet[::-1], axis=0), -1)
        ok = last >= 0
        ii, jj = np.nonzero(ok)
        acc["ub"][ok] += U[last[ok], ii, jj]; acc["vb"][ok] += V[last[ok], ii, jj]
        botz[ok] = z[last[ok]]
        acc["us"][ok] += np.nan_to_num(U[0][ok]); acc["vs"][ok] += np.nan_to_num(V[0][ok])
        acc["u10"][ok] += np.nan_to_num(np.nanmean(U[upper], 0)[ok]); acc["v10"][ok] += np.nan_to_num(np.nanmean(V[upper], 0)[ok])
        cnt[ok] += 1
        print(f"  month {i + 1}/{nt}", end="\r", file=sys.stderr)
    cnt[cnt == 0] = np.nan
    bands = [acc[k] / cnt for k in ("us", "vs", "u10", "v10", "ub", "vb")] + [botz]
    lonv, latv = ds[lon].values, ds[lat].values
    dx, dy = float(abs(lonv[1] - lonv[0])), float(abs(latv[1] - latv[0]))
    tr = from_origin(lonv.min() - dx / 2, latv.max() + dy / 2, dx, dy)
    names = ["u_surface", "v_surface", "u_0_10m", "v_0_10m", "u_bottom", "v_bottom", "bottom_level_m"]
    with rasterio.open(os.path.join(a.out, "currents_mean.tif"), "w", driver="GTiff", height=H, width=W, count=7,
                       dtype="float32", crs="EPSG:4326", transform=tr, nodata=np.nan, compress="deflate") as d:
        for k, (b, n) in enumerate(zip(bands, names), 1):
            d.write(north_up(b, latv).astype("float32"), k); d.set_band_description(k, n)
        d.update_tags(source=did, years=f"{a.years[0]}-{a.years[1]}", months=",".join(map(str, a.months)))
    sp = np.hypot(bands[0], bands[1])
    print(f"\nMean surface speed {np.nanmedian(sp):.3f} m/s (median), {np.nanpercentile(sp, 90):.3f} m/s (p90)")

    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 2, figsize=(13, 6.5))
    X, Y = np.meshgrid(lonv, latv); step = max(1, int(max(H, W) / 45))
    for ax, (bu, bv, title) in zip(axs, ((bands[0], bands[1], "surface"), (bands[4], bands[5], f"near bottom (to {a.max_depth:g} m)"))):
        s = np.hypot(bu, bv)
        im = ax.pcolormesh(lonv, latv, s, cmap="Blues", shading="nearest", vmin=0, vmax=np.nanpercentile(s, 98))
        ax.quiver(X[::step, ::step], Y[::step, ::step], bu[::step, ::step], bv[::step, ::step], scale=None, width=0.002)
        ax.set_title(f"Mean {title} current, months {','.join(map(str, a.months))}, {a.years[0]}-{a.years[1]}")
        ax.set_aspect(1 / np.cos(np.radians(np.mean(latv)))); fig.colorbar(im, ax=ax, shrink=0.7, label="m/s")
    fig.savefig(os.path.join(a.out, "currents_mean.png"), dpi=150, bbox_inches="tight")

    # ---------- daily surface fields for the drift
    if a.skip_daily:
        print("Results in", a.out); return
    ds, did = open_any(a.product, a.daily, prefer="geoChunked")
    u, v = velocity_vars(ds)
    ds, lon, lat, t = subset(ds, a)
    if "depth" in ds.dims: ds = ds.isel(depth=0)
    nt = ds.sizes[t]
    print(f"Daily surface: {nt} days, grid {ds.sizes[lon]} x {ds.sizes[lat]} - downloading by year")
    times = ds[t].values; years = sorted(set(times.astype("datetime64[Y]").astype(int) + 1970))
    Us, Vs = [], []
    for y in years:
        idx = np.nonzero(times.astype("datetime64[Y]").astype(int) + 1970 == y)[0]
        Us.append(ds[u].isel({t: idx}).values.astype("float32")); Vs.append(ds[v].isel({t: idx}).values.astype("float32"))
        print(f"  {y}: {len(idx)} days", file=sys.stderr)
    Ud, Vd = np.concatenate(Us), np.concatenate(Vs)
    latv = ds[lat].values
    if latv[0] > latv[-1]: Ud, Vd, latv = Ud[:, ::-1], Vd[:, ::-1], latv[::-1]
    tdays = (times - np.datetime64("1970-01-01")) / np.timedelta64(1, "D")
    np.savez_compressed(os.path.join(a.out, "currents_daily_surface.npz"), lon=ds[lon].values, lat=latv,
                        tdays=tdays.astype("float64"), u=Ud, v=Vd, source=did)
    print("Results in", a.out)

if __name__ == "__main__":
    main()
