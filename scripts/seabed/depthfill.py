"""depthfill.py - extend a coarse depth grid to the coastline before it is resampled onto photo pixels.

The depth band of erratic_grid.tif comes from EMODnet DTM (about 115 x 65 m cells here). Coastal
cells are often empty (land, or partly land) and bilinear resampling turns every photo pixel next to an
empty cell into "no depth", so a strip up to one cell wide along the shore was silently left out of
ortho_compare, boulders and flora (seen as straight inshore edges on the maps). fill_coast() gives
empty or dry cells within `cells` grid cells of wet ones the depth of the nearest wet cell. That
overstates depth right at the shore; the photo's own water test (blue > red) still keeps beach and
land out.
"""
import numpy as np
from scipy import ndimage as ndi


def fill_coast(a, cells=2):
    a = np.asarray(a, dtype="float32")
    wet = np.isfinite(a) & (a > 0)
    if not wet.any() or wet.all():
        return a
    dist, idx = ndi.distance_transform_edt(~wet, return_distances=True, return_indices=True)
    out = a.copy(); m = ~wet & (dist <= cells)
    out[m] = a[idx[0][m], idx[1][m]]
    return out


def sea(R, G, B, valid, d, min_depth, res, buffer_m=5.0):
    """Water mask from the photo, not the coarse depth grid, plus a depth that is never below min_depth in it.

    The depth grid's shallow contours can sit 100 m or more offshore of the real waterline, so a depth
    cut (d >= 0.3 m) dropped clearly submerged ground near the shore. Here water = photo pixels that
    look like water (blue > red, not red-dominated) AND are connected to water the depth grid calls
    at least 2 x min_depth deep (so roads or roofs inland are not taken). The first buffer_m from the
    waterline (swash, foam, wet sand) is left out; beyond it, depth is floored at min_depth.
    Returns (water, depth_adjusted, swash) where swash marks the excluded strip."""
    cand = valid & np.isfinite(d) & (B > R) & (G >= R - 5)
    core = cand & (d > 2 * min_depth)
    lab, nl = ndi.label(cand)
    keep = np.zeros(nl + 1, bool); keep[np.unique(lab[core])] = True; keep[0] = False
    w = keep[lab]
    f = max(1, int(round(1.0 / res)))                       # distance to the waterline on a ~1 m grid
    ws = w[::f, ::f]; dist = ndi.distance_transform_edt(ws) * res * f
    dist = np.repeat(np.repeat(dist, f, 0), f, 1)[:w.shape[0], :w.shape[1]]
    swash = w & (dist <= buffer_m)
    d2 = np.where(w & ~swash, np.maximum(np.nan_to_num(d, nan=min_depth), min_depth), d).astype("float32")
    return w & ~swash, d2, swash
