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
