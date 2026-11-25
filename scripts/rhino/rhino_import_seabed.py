# rhino_import_seabed.py  -  run inside Rhino 7 or 8 (EditPythonScript / ScriptEditor)
# Reads the outputs of seabed_classify.py and builds:
#   substrate::boulder_detected  - one ellipsoid per detected boulder (true size)
#   reference::transect          - shore-normal cross-section polyline (XZ plane)
# Coordinates: boulders keep their map coordinates (e.g. EPSG:25832 metres) minus an
# origin you pick, so the model stays near 0,0 in Rhino.
import rhinoscriptsyntax as rs
import csv, os

def ensure_layer(name, color):
    if not rs.IsLayer(name):
        rs.AddLayer(name, color)
    return name

def main():
    folder = rs.BrowseForFolder(message="Folder with boulders.csv and transect.csv")
    if not folder:
        return
    lay_b = ensure_layer("substrate::boulder_detected", (91, 70, 54))
    lay_t = ensure_layer("reference::transect", (220, 60, 60))
    bpath = os.path.join(folder, "boulders.csv")
    if os.path.exists(bpath):
        rows = list(csv.DictReader(open(bpath)))
        ox = min(float(r["x"]) for r in rows); oy = min(float(r["y"]) for r in rows)
        ox = rs.GetReal("Origin X (map units)", ox) ; oy = rs.GetReal("Origin Y (map units)", oy)
        rs.EnableRedraw(False)
        for r in rows:
            x = float(r["x"]) - ox; y = float(r["y"]) - oy
            d = float(r["diameter_m"]); h = float(r["height_m"]); zb = float(r["z_base"])
            # ellipsoid: sphere scaled to diameter d and height h, sitting on the bed
            s = rs.AddSphere((0, 0, 0), 0.5)
            rs.ScaleObject(s, (0, 0, 0), (d, d, 2 * h))      # half buried, like a real boulder
            rs.MoveObject(s, (x, y, zb))
            rs.ObjectLayer(s, lay_b)
            rs.SetUserText(s, "diameter_m", str(d)); rs.SetUserText(s, "height_m", str(h))
        rs.EnableRedraw(True)
        print("Boulders placed: %d (origin %.1f, %.1f)" % (len(rows), ox, oy))
    tpath = os.path.join(folder, "transect.csv")
    if os.path.exists(tpath):
        pts = [(float(r["x_offshore_m"]), 0, float(r["z_m"])) for r in csv.DictReader(open(tpath))]
        if len(pts) > 1:
            pl = rs.AddPolyline(pts); rs.ObjectLayer(pl, lay_t)
            print("Transect points: %d" % len(pts))

main()
