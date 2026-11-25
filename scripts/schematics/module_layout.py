#!/usr/bin/env python3
"""
module_layout.py - build the 20 x 40 m lumpfish nest-reef module from parameters.csv and write
module.json (geometry for Rhino / three.js), plan.svg and section.svg.

Coordinates follow the project convention: metres, origin at the shoreline at mean sea level,
+X offshore, +Y alongshore, Z elevation (negative = depth). The module sits in zone Z3.

Rules used (parameters/parameters.csv):
  R14a/R14b module size, R02 Z3 slope, R03 nest boulder diameter, R04 boulders per cluster,
  R05a/R05b crevice width/depth, R06 cluster spacing, R07a relief, R07b surface clearance,
  R08 boulder cover, R09a-c cobble apron, R10 crevice angle to current, R11 kelp density,
  R15 distance from any nest to a hard/soft edge (gives the sand lanes), Z1-Z4 depth bands.

Usage:
  python module_layout.py --out schematics/module_20x40 [--x0 80] [--z0 -6] [--lanes 2] [--seed 1]
"""
import argparse, csv, json, math, os, random

def load_params(path):
    P = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        def f(k):
            try: return float(r[k])
            except (ValueError, TypeError): return None
        P[r["rule_id"]] = dict(min=f("min"), lo=f("optimum_low"), hi=f("optimum_high"), max=f("max"), unit=r["unit"], var=r["variable"])
    return P

def opt(P, rid, default):
    p = P.get(rid, {}); lo, hi = p.get("lo"), p.get("hi")
    if lo is None and hi is None: return default
    return (lo + hi) / 2 if lo is not None and hi is not None else (lo if lo is not None else hi)

def main():
    here = os.path.dirname(os.path.abspath(__file__)); root = os.path.dirname(os.path.dirname(here))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--params", default=os.path.join(root, "parameters", "parameters.csv"))
    ap.add_argument("--out", default=os.path.join(root, "schematics", "module_20x40"))
    ap.add_argument("--x0", type=float, default=None, help="offshore distance of the module's landward edge (m); default from slope so the module sits at --z0")
    ap.add_argument("--z0", type=float, default=-6.0, help="seabed elevation at the module's landward edge (m)")
    ap.add_argument("--y0", type=float, default=0.0, help="alongshore start of the module (m)")
    ap.add_argument("--lanes", type=int, default=2, help="sand lanes across the module (edge rule R15)")
    ap.add_argument("--lane-width", type=float, default=2.0)
    ap.add_argument("--current-deg", type=float, default=90.0, help="main current direction in the XY plane, deg from +X (90 = alongshore)")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    P = load_params(a.params); rnd = random.Random(a.seed)

    L = opt(P, "R14a", 40.0); W = opt(P, "R14b", 20.0)          # alongshore length, offshore width
    slope = opt(P, "R02", 0.05)                                   # rise/run in Z3
    s12 = opt(P, "R01", 0.035)                                    # Z1-Z2 slope
    x0 = a.x0 if a.x0 is not None else (2 / s12 + (abs(a.z0) - 2) / slope)   # Z1+Z2 at s12, rest at Z3 slope
    z_at = lambda x: a.z0 - (x - x0) * slope                       # seabed inside the module
    d_lo, d_hi = opt(P, "R03", 1.0), P["R03"]["hi"] or 1.2
    n_per = int(round(opt(P, "R04", 4))); spacing = opt(P, "R06", 3.5)
    cw, cd = opt(P, "R05a", 0.2), opt(P, "R05b", 0.35)
    apron_t, apron_m = opt(P, "R09b", 0.3), opt(P, "R09c", 2.0); cob = opt(P, "R09a", 0.15)
    kelp = opt(P, "R11", 10.0); clearance = P.get("R07b", {}).get("min") or 3.0
    edge_max = P.get("R15", {}).get("hi") or 10.0
    cover_lo, cover_hi = P["R08"]["lo"] or 0.3, P["R08"]["hi"] or 0.5

    # reef patches between sand lanes (alongshore), each inset by the apron margin
    n_p = a.lanes + 1; pl = (L - a.lanes * a.lane_width) / n_p
    patches = []
    for i in range(n_p):
        ys = a.y0 + i * (pl + a.lane_width)
        patches.append(dict(id=f"patch_{i+1}", x=[x0 + apron_m, x0 + W - apron_m], y=[ys + apron_m, ys + pl - apron_m]))
    lanes = [dict(id=f"sand_lane_{i+1}", x=[x0, x0 + W], y=[a.y0 + (i + 1) * pl + i * a.lane_width, a.y0 + (i + 1) * (pl + a.lane_width)]) for i in range(a.lanes)]

    # nest clusters on a jittered grid at R06 spacing; crevice axis at R10 to the current
    cur = math.radians(a.current_deg); crev_axis = cur + math.radians(90)
    boulders, clusters = [], []
    for p in patches:
        nx = max(1, int((p["x"][1] - p["x"][0]) // spacing)); ny = max(1, int((p["y"][1] - p["y"][0]) // spacing))
        gx = (p["x"][1] - p["x"][0]) / nx; gy = (p["y"][1] - p["y"][0]) / ny
        for i in range(nx):
            for j in range(ny):
                cx = p["x"][0] + (i + 0.5) * gx + rnd.uniform(-0.3, 0.3); cy = p["y"][0] + (j + 0.5) * gy + rnd.uniform(-0.3, 0.3)
                ang = crev_axis + math.radians(rnd.uniform(-15, 15)); ux, uy = math.cos(ang), math.sin(ang); vx, vy = -uy, ux
                cid = f"{p['id']}_c{i+1}{j+1}"; members = []
                for k in range(n_per):
                    d = rnd.uniform(d_lo, d_hi); side = -1 if k % 2 == 0 else 1; along = (k // 2 - (n_per - 1) / 4) * d * 0.95
                    off = side * (d / 2 + cw / 2)                      # two rows either side of the crevice
                    bx, by = cx + ux * along + vx * off, cy + uy * along + vy * off
                    h = d * rnd.uniform(0.7, 0.9); zb = z_at(bx) + apron_t * 0.5
                    b = dict(id=f"{cid}_b{k+1}", layer="substrate::boulder_nest", x=round(bx, 3), y=round(by, 3), z_base=round(zb, 3),
                             diameter=round(d, 3), height=round(h, 3), z_top=round(zb + h, 3),
                             kelp_stipes=int(round(kelp * math.pi * (d / 2) ** 2)))
                    boulders.append(b); members.append(b["id"])
                edge_d = min(cx - x0, x0 + W - cx, min(abs(cy - ly) for ln in lanes for ly in ln["y"]) if lanes else 99, cy - a.y0, a.y0 + L - cy)
                clusters.append(dict(id=cid, x=round(cx, 3), y=round(cy, 3), crevice_axis_deg=round(math.degrees(ang) % 180, 1),
                                     crevice_width=cw, crevice_depth=cd, boulders=members, nest_point=[round(cx, 3), round(cy, 3), round(z_at(cx) + apron_t, 3)],
                                     edge_distance_m=round(edge_d, 2)))

    # filler boulders between clusters until reef cover reaches the middle of R08 (keeps crevices clear)
    reef_area = sum((p["x"][1] - p["x"][0] + 2 * apron_m) * (p["y"][1] - p["y"][0] + 2 * apron_m) for p in patches)
    target = (cover_lo + cover_hi) / 2; tries = 0
    area_now = lambda: sum(math.pi * (b["diameter"] / 2) ** 2 for b in boulders)
    while area_now() / reef_area < target and tries < 20000:
        tries += 1; p = rnd.choice(patches)
        bx = rnd.uniform(p["x"][0] - apron_m * 0.5, p["x"][1] + apron_m * 0.5); by = rnd.uniform(p["y"][0] - apron_m * 0.5, p["y"][1] + apron_m * 0.5)
        d = rnd.uniform(0.5, d_hi)
        if any(math.hypot(bx - b["x"], by - b["y"]) < (d + b["diameter"]) / 2 + 0.05 for b in boulders): continue
        if any(math.hypot(bx - c["x"], by - c["y"]) < d / 2 + 0.6 for c in clusters): continue
        h = d * rnd.uniform(0.6, 0.85); zb = z_at(bx) + apron_t * 0.5
        boulders.append(dict(id=f"fill_{len(boulders)+1}", layer="substrate::boulder_fill", x=round(bx, 3), y=round(by, 3), z_base=round(zb, 3),
                             diameter=round(d, 3), height=round(h, 3), z_top=round(zb + h, 3), kelp_stipes=int(round(kelp * math.pi * (d / 2) ** 2))))

    reef_area = sum((p["x"][1] - p["x"][0] + 2 * apron_m) * (p["y"][1] - p["y"][0] + 2 * apron_m) for p in patches)
    cover = sum(math.pi * (b["diameter"] / 2) ** 2 for b in boulders) / reef_area
    top = max(b["z_top"] for b in boulders); relief = max(b["z_top"] - z_at(b["x"]) for b in boulders)
    checks = {
        "boulder_cover_R08": [round(cover, 3), f"{cover_lo}-{cover_hi}", cover_lo <= cover <= cover_hi],
        "max_edge_distance_R15_m": [max(c["edge_distance_m"] for c in clusters), f"<= {edge_max}", max(c["edge_distance_m"] for c in clusters) <= edge_max],
        "relief_R07a_m": [round(relief, 2), f"{P['R07a']['min']}-{P['R07a']['max']}", P["R07a"]["min"] <= relief <= P["R07a"]["max"]],
        "surface_clearance_R07b_m": [round(-top, 2), f">= {clearance}", -top >= clearance],
        "module_depth_band_Z3": [[round(z_at(x0), 2), round(z_at(x0 + W), 2)], "-5 to -10", -10 <= z_at(x0 + W) and z_at(x0) <= -5],
    }
    module = {
        "schema": "lumpfish-module/v1", "convention": "m; origin shoreline MSL; +X offshore; +Y alongshore; z negative = depth",
        "module": dict(x=[round(x0, 2), round(x0 + W, 2)], y=[a.y0, a.y0 + L], z_landward=a.z0, slope=slope, current_deg=a.current_deg, seed=a.seed),
        "seabed_profile": [[0, 0], [round(2 / s12, 2), -2], [round(x0, 2), a.z0], [round(x0 + W, 2), round(z_at(x0 + W), 3)], [round(x0 + W + 60, 2), round(z_at(x0 + W + 60), 3)]],
        "zones": {k: P[k]["lo"] and [P[k]["min"], P[k]["max"]] for k in ("Z1", "Z2", "Z3", "Z4") if k in P},
        "cobble_apron": dict(layer="substrate::cobble", patches=[dict(id=p["id"], x=[p["x"][0] - apron_m, p["x"][1] + apron_m], y=[p["y"][0] - apron_m, p["y"][1] + apron_m]) for p in patches],
                             thickness=apron_t, cobble_size=cob),
        "sand_lanes": [dict(l, layer="substrate::sand") for l in lanes],
        "nest_clusters": clusters, "boulders": boulders, "checks": checks,
        "rules_used": {k: P[k] for k in ("R02", "R03", "R04", "R05a", "R05b", "R06", "R07a", "R07b", "R08", "R09a", "R09b", "R09c", "R10", "R11", "R14a", "R14b", "R15") if k in P},
    }
    os.makedirs(a.out, exist_ok=True)
    json.dump(module, open(os.path.join(a.out, "module.json"), "w"), indent=1)
    draw_plan(module, os.path.join(a.out, "plan.svg")); draw_section(module, os.path.join(a.out, "section.svg"))
    draw_detail(module, os.path.join(a.out, "section_module.svg"))
    print(f"{len(clusters)} nest clusters, {len(boulders)} boulders ({sum(b['layer'].endswith('fill') for b in boulders)} filler), cover {cover:.2f}")
    for k, v in checks.items(): print(f"  {'OK ' if v[2] else 'FAIL'} {k}: {v[0]} (target {v[1]})")
    print("Wrote", a.out)

def draw_plan(m, path, s=20, pad=60):
    x0, x1 = m["module"]["x"]; y0, y1 = m["module"]["y"]
    W, H = (y1 - y0) * s + 2 * pad, (x1 - x0) * s + 2 * pad + 40
    X = lambda y: pad + (y - y0) * s; Y = lambda x: pad + (x1 - x) * s       # alongshore → right, offshore → up
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" font-family="Helvetica,Arial" font-size="11">',
         f'<rect width="100%" height="100%" fill="#f4f1ea"/>',
         f'<rect x="{X(y0)}" y="{Y(x1)}" width="{(y1-y0)*s}" height="{(x1-x0)*s}" fill="#e6d8a8" stroke="#333"/>']
    for p in m["cobble_apron"]["patches"]:
        o.append(f'<rect x="{X(p["y"][0])}" y="{Y(p["x"][1])}" width="{(p["y"][1]-p["y"][0])*s}" height="{(p["x"][1]-p["x"][0])*s}" fill="#b9ab8f" stroke="#7a6d55" stroke-dasharray="4 3"/>')
    for l in m["sand_lanes"]:
        o.append(f'<text x="{X(sum(l["y"])/2)}" y="{Y(x1)-6}" text-anchor="middle" fill="#7a6d55">sand lane</text>')
    for b in m["boulders"]:
        nest = b["layer"].endswith("nest")
        o.append(f'<circle cx="{X(b["y"]):.1f}" cy="{Y(b["x"]):.1f}" r="{b["diameter"]/2*s:.1f}" fill="{"#3b2e22" if nest else "#9c8f7c"}" stroke="{"#1a130d" if nest else "#7d715f"}"/>')
    for c in m["nest_clusters"]:
        a = math.radians(c["crevice_axis_deg"]); dx, dy = math.sin(a) * 0.8 * s, math.cos(a) * 0.8 * s
        o.append(f'<line x1="{X(c["y"])-dx:.1f}" y1="{Y(c["x"])+dy:.1f}" x2="{X(c["y"])+dx:.1f}" y2="{Y(c["x"])-dy:.1f}" stroke="#e4572e" stroke-width="2"/>')
    cur = math.radians(m["module"]["current_deg"])
    o += [f'<text x="{pad}" y="{H-30}">Plan, module {y1-y0:.0f} m alongshore × {x1-x0:.0f} m offshore. Offshore is up. Dark = nest boulders, red = crevice (nest) axis; light = filler boulders; dashed = cobble apron.</text>',
          f'<text x="{pad}" y="{H-14}">Scale bar 5 m:</text><line x1="{pad+90}" y1="{H-18}" x2="{pad+90+5*s}" y2="{H-18}" stroke="#000" stroke-width="3"/>',
          f'<text x="{W-pad}" y="{H-14}" text-anchor="end">current → {m["module"]["current_deg"]:.0f}° from +X</text>', '</svg>']
    open(path, "w").write("\n".join(o))

def draw_section(m, path, s=8, vz=20, pad=50):
    prof = m["seabed_profile"]; xmax = prof[-1][0]; zmin = prof[-1][1] - 2
    W, H = xmax * s + 2 * pad, (-zmin + 3) * vz * s / 4 + 2 * pad
    X = lambda x: pad + x * s; Z = lambda z: pad + (1.5 - z) * vz * s / 4
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" font-family="Helvetica,Arial" font-size="11">',
         f'<rect width="100%" height="100%" fill="#f4f1ea"/>',
         f'<rect x="{X(0)}" y="{Z(0)}" width="{xmax*s}" height="{Z(zmin)-Z(0)}" fill="#dfeaf0"/>',
         f'<line x1="{X(0)}" y1="{Z(0)}" x2="{X(xmax)}" y2="{Z(0)}" stroke="#3a7ca5"/><text x="{X(0)+4}" y="{Z(0)-4}" fill="#3a7ca5">MSL 0 m</text>']
    for name, (zt, zb), col in (("Z1 nursery", (0, -2), "#cfe8d5"), ("Z2 eelgrass", (-2, -5), "#b7dcc1"), ("Z3 nest reef", (-5, -10), "#e8dcc0"), ("Z4 refuge", (-10, -15), "#d9d4cc")):
        o.append(f'<text x="{X(xmax)-4}" y="{Z((zt+zb)/2)}" text-anchor="end" fill="#555">{name} ({zt} to {zb} m)</text>')
        o.append(f'<line x1="{X(0)}" y1="{Z(zb)}" x2="{X(xmax)}" y2="{Z(zb)}" stroke="#bbb" stroke-dasharray="3 4"/>')
    pts = " ".join(f"{X(x):.1f},{Z(z):.1f}" for x, z in prof) + f" {X(xmax):.1f},{Z(zmin):.1f} {X(0):.1f},{Z(zmin):.1f}"
    o.append(f'<polygon points="{pts}" fill="#e6d8a8" stroke="#333"/>')
    x0, x1 = m["module"]["x"]
    yc = sorted(m["boulders"], key=lambda b: abs(b["y"] - (m["module"]["y"][0] + 6)))[:12]
    for b in yc:
        o.append(f'<ellipse cx="{X(b["x"]):.1f}" cy="{Z(b["z_base"]+b["height"]/2):.1f}" rx="{b["diameter"]/2*s:.1f}" ry="{b["height"]/2*vz*s/4:.1f}" fill="#5a4a3a"/>')
    o += [f'<line x1="{X(x0)}" y1="{Z(prof[2][1])+16}" x2="{X(x1)}" y2="{Z(prof[2][1])+16}" stroke="#e4572e" stroke-width="2"/>',
          f'<text x="{X((x0+x1)/2)}" y="{Z(prof[2][1])+30}" text-anchor="middle" fill="#e4572e">module {x1-x0:.0f} m</text>',
          f'<text x="{pad}" y="{H-12}">Section XZ through the module (vertical exaggeration {vz/4*1:.0f}×). Offshore →. Seabed slope from R01/R02; boulders from module.json.</text>', '</svg>']
    open(path, "w").write("\n".join(o))

def draw_detail(m, path, s=40, pad=50, strip=3.0):
    """True-scale XZ slice through one nest cluster row: apron, nest boulders, crevice."""
    x0, x1 = m["module"]["x"]; c = m["nest_clusters"][0]; yc = c["y"]
    zl = m["module"]["z_landward"]; sl = m["module"]["slope"]; t = m["cobble_apron"]["thickness"]
    z_at = lambda x: zl - (x - x0) * sl
    ztop = max(b["z_top"] for b in m["boulders"]) + 1; zbot = z_at(x1) - 1.5
    W, H = (x1 - x0 + 4) * s + 2 * pad, (ztop - zbot) * s + 2 * pad + 30
    X = lambda x: pad + (x - x0 + 2) * s; Z = lambda z: pad + (ztop - z) * s
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" font-family="Helvetica,Arial" font-size="12">',
         f'<rect width="100%" height="100%" fill="#dfeaf0"/>']
    bed = [(x0 - 2, z_at(x0 - 2)), (x1 + 2, z_at(x1 + 2))]
    o.append(f'<polygon points="{X(bed[0][0])},{Z(bed[0][1])} {X(bed[1][0])},{Z(bed[1][1])} {X(bed[1][0])},{Z(zbot)} {X(bed[0][0])},{Z(zbot)}" fill="#e6d8a8" stroke="#333"/>')
    for p in m["cobble_apron"]["patches"]:
        if p["y"][0] <= yc <= p["y"][1]:
            a, b = p["x"]
            o.append(f'<polygon points="{X(a)},{Z(z_at(a))} {X(b)},{Z(z_at(b))} {X(b)},{Z(z_at(b)+t)} {X(a)},{Z(z_at(a)+t)}" fill="#b9ab8f" stroke="#7a6d55"/>')
    for b in sorted(m["boulders"], key=lambda b: -abs(b["y"] - yc)):
        if abs(b["y"] - yc) > strip / 2: continue
        nest = b["layer"].endswith("nest")
        o.append(f'<ellipse cx="{X(b["x"]):.1f}" cy="{Z(b["z_base"] + b["height"]/2):.1f}" rx="{b["diameter"]/2*s:.1f}" ry="{b["height"]/2*s:.1f}" fill="{"#3b2e22" if nest else "#9c8f7c"}" opacity="{1 if nest else 0.8}"/>')
    for cl in m["nest_clusters"]:
        if abs(cl["y"] - yc) <= strip / 2:
            nx, ny, nz = cl["nest_point"]
            o.append(f'<circle cx="{X(nx):.1f}" cy="{Z(nz):.1f}" r="5" fill="#f2a541" stroke="#e4572e" stroke-width="2"/>')
    o += [f'<text x="{pad}" y="{H-36}">True-scale slice through the module at y = {yc:.1f} m (±{strip/2:.1f} m strip). Offshore →. Orange = egg-mass position in the crevice.</text>',
          f'<text x="{pad}" y="{H-18}">Scale bar 1 m:</text><line x1="{pad+90}" y1="{H-22}" x2="{pad+90+s}" y2="{H-22}" stroke="#000" stroke-width="3"/>', '</svg>']
    open(path, "w").write("\n".join(o))

if __name__ == "__main__":
    main()
