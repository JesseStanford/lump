# -*- coding: utf-8 -*-
"""
rhino_build_module.py - build the lumpfish nest-reef module in Rhino from schematics/<module>/module.json.

Runs in Rhino 7 (IronPython 2.7) and Rhino 8 (Python 2 or 3): only rhinoscriptsyntax and the
standard json module, no f-strings. In Rhino: RunPythonScript, pick this file, then pick module.json.

Layers (match krea/image_manifest.csv so each object links to its reference image):
  substrate::sand, substrate::cobble, substrate::sand, substrate::boulder_nest,
  substrate::boulder_fill, fauna::Cyclopterus_lumpus_eggmass, reference::module_outline
Every object carries user text: id, layer role, and the rule values it was built from.
Units: metres. Coordinates: +X offshore, +Y alongshore, Z elevation (negative = depth).
"""
import json
import rhinoscriptsyntax as rs

COLORS = {
    "substrate::sand": (230, 216, 168), "substrate::cobble": (185, 171, 143), "substrate::sand": (240, 228, 190),
    "substrate::boulder_nest": (59, 46, 34), "substrate::boulder_fill": (156, 143, 124),
    "fauna::Cyclopterus_lumpus_eggmass": (242, 165, 65), "reference::module_outline": (228, 87, 46),
}

def layer(name):
    if not rs.IsLayer(name):
        parent = None
        for part in name.split("::"):
            full = part if parent is None else parent + "::" + part
            if not rs.IsLayer(full):
                rs.AddLayer(part, COLORS.get(full, (120, 120, 120)), parent=parent)
            parent = full
    return name

def tag(obj, d):
    for k, v in d.items():
        rs.SetUserText(obj, str(k), str(v))

def z_at(m, x):
    return m["module"]["z_landward"] - (x - m["module"]["x"][0]) * m["module"]["slope"]

def slab(m, x0, x1, y0, y1, dz0, dz1):
    """Box following the seabed slope between thickness offsets dz0 (bottom) and dz1 (top)."""
    pts = []
    for dz in (dz0, dz1):
        pts += [(x0, y0, z_at(m, x0) + dz), (x1, y0, z_at(m, x1) + dz), (x1, y1, z_at(m, x1) + dz), (x0, y1, z_at(m, x0) + dz)]
    return rs.AddBox(pts)

def build(path):
    m = json.load(open(path))
    rs.EnableRedraw(False)
    mx, my = m["module"]["x"], m["module"]["y"]

    # seabed: the section profile extruded alongshore, 10 m beyond the module each side
    prof = m["seabed_profile"]; ya, yb = my[0] - 10, my[1] + 10
    for (xa, za), (xb, zb) in zip(prof[:-1], prof[1:]):
        s = rs.AddSrfPt([(xa, ya, za), (xb, ya, zb), (xb, yb, zb), (xa, yb, za)])
        rs.ObjectLayer(s, layer("substrate::sand"))

    outline = rs.AddPolyline([(mx[0], my[0], z_at(m, mx[0])), (mx[1], my[0], z_at(m, mx[1])), (mx[1], my[1], z_at(m, mx[1])),
                              (mx[0], my[1], z_at(m, mx[0])), (mx[0], my[0], z_at(m, mx[0]))])
    rs.ObjectLayer(outline, layer("reference::module_outline")); tag(outline, {"checks": json.dumps(m["checks"])})

    t = m["cobble_apron"]["thickness"]
    for p in m["cobble_apron"]["patches"]:
        b = slab(m, p["x"][0], p["x"][1], p["y"][0], p["y"][1], 0.0, t)
        rs.ObjectLayer(b, layer("substrate::cobble")); tag(b, {"id": p["id"], "thickness_m": t, "cobble_size_m": m["cobble_apron"]["cobble_size"]})
    for ln in m["sand_lanes"]:
        s = rs.AddSrfPt([(ln["x"][0], ln["y"][0], z_at(m, ln["x"][0]) + 0.01), (ln["x"][1], ln["y"][0], z_at(m, ln["x"][1]) + 0.01),
                         (ln["x"][1], ln["y"][1], z_at(m, ln["x"][1]) + 0.01), (ln["x"][0], ln["y"][1], z_at(m, ln["x"][0]) + 0.01)])
        rs.ObjectLayer(s, layer("substrate::sand")); tag(s, {"id": ln["id"], "rule": "R15 edge distance"})

    for b in m["boulders"]:
        r = b["diameter"] / 2.0; zc = b["z_base"] + b["height"] / 2.0
        s = rs.AddSphere((b["x"], b["y"], zc), r)
        s = rs.ScaleObject(s, (b["x"], b["y"], zc), (1.0, 1.0, b["height"] / b["diameter"]))
        rs.ObjectLayer(s, layer(b["layer"]))
        tag(s, {"id": b["id"], "diameter_m": b["diameter"], "height_m": b["height"], "kelp_stipes": b["kelp_stipes"]})

    for c in m["nest_clusters"]:
        pt = rs.AddPoint(c["nest_point"])
        rs.ObjectLayer(pt, layer("fauna::Cyclopterus_lumpus_eggmass"))
        tag(pt, {"id": c["id"], "crevice_axis_deg": c["crevice_axis_deg"], "crevice_width_m": c["crevice_width"],
                 "crevice_depth_m": c["crevice_depth"], "edge_distance_m": c["edge_distance_m"], "egg_mass_m": "0.26 x 0.10 x 0.10 (P15)"})

    rs.EnableRedraw(True)
    print("Built %d boulders, %d nest clusters from %s" % (len(m["boulders"]), len(m["nest_clusters"]), path))

if __name__ == "__main__":
    f = rs.OpenFileName("Pick module.json", "JSON (*.json)|*.json||")
    if f: build(f)
