"""Three parametric open, vertical blockout environments (original geometry)."""
import math, random
from .nrlib import Builder, point_in_poly

WALL, WALL2, WALL3 = "NRRUST1", "NRCELAD1", "NRBONE1"
FLOOR, FLOOR2, FLOOR3 = "NRFLOOR1", "NRFLOOR2", "NRMOSS1"
WATER, VOID, GLOW, GLASS = "NRWATER1", "NRVOID1", "NRGLOW1", "NRGLASS1"
ALL_TEX = [WALL, WALL2, WALL3, FLOOR, FLOOR2, FLOOR3, WATER, VOID, GLOW, GLASS]

def scale_pt(c, p, f):
    return (round(c[0] + (p[0] - c[0]) * f), round(c[1] + (p[1] - c[1]) * f))

def ring(c, angles, radii):
    return [(round(c[0] + r * math.cos(math.radians(a))),
             round(c[1] + r * math.sin(math.radians(a)))) for a, r in zip(angles, radii)]

def lerp_pt(a, b, t):
    return (round(a[0] + (b[0] - a[0]) * t), round(a[1] + (b[1] - a[1]) * t))

def wedge(inner, outer, i):
    n = len(inner)
    j = (i + 1) % n
    return [inner[i], outer[i], outer[j], inner[j]]

def strip_group(inner, outer, i0, nseg, counts, floors):
    """Angular strips from boundary i0 to i0+nseg. counts per segment sum to strip count."""
    assert sum(counts) == len(floors), (sum(counts), len(floors))
    n = len(inner)
    idx = [(i0 + k) % n for k in range(nseg + 1)]
    out = []
    fi = 0
    for k in range(nseg):
        a, b = idx[k], idx[k + 1]
        m = counts[k]
        for s in range(m):
            t0, t1 = s / m, (s + 1) / m
            p0 = lerp_pt(inner[a], inner[b], t0)
            p1 = lerp_pt(inner[a], inner[b], t1)
            q0 = lerp_pt(outer[a], outer[b], t0)
            q1 = lerp_pt(outer[a], outer[b], t1)
            out.append(([p0, q0, q1, p1], floors[fi]))
            fi += 1
    return out

def merge_strips(polys):
    """Union of consecutive strip quads sharing their cut edges."""
    out = [polys[0][0], polys[0][1]]
    for p in polys:
        out.append(p[2])
    for p in reversed(polys):
        out.append(p[3])
    # drop consecutive duplicates (none expected) and the closing duplicate
    clean = []
    for p in out:
        if not clean or clean[-1] != p:
            clean.append(p)
    if clean[0] == clean[-1]:
        clean.pop()
    return clean

def outward_normal(a, b, center=(0, 0)):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1.0
    nx, ny = dy / L, -dx / L
    mx, my = (a[0] + b[0]) / 2 - center[0], (a[1] + b[1]) / 2 - center[1]
    if nx * mx + ny * my < 0:
        nx, ny = -nx, -ny
    return nx, ny

def add_control(b, name, target_tag, top, slot):
    cx, cy = 9000, 9000 + slot * 200
    poly = [(cx, cy), (cx + 64, cy), (cx + 64, cy + 64), (cx, cy + 64)]
    b.sector(name, poly, top - 8, top, GLOW, VOID, light=255, kind="control",
             walk=False, tw=GLOW)
    b.control(name, target_tag, top)

def centroid(s):
    xs = [p[0] for p in s.poly]; ys = [p[1] for p in s.poly]
    x, y = sum(xs) / len(xs), sum(ys) / len(ys)
    if not point_in_poly(x, y, s.poly):
        x, y = s.poly[0]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        x, y = round(x * 0.7 + cx * 0.3), round(y * 0.7 + cy * 0.3)
    return int(round(x)), int(round(y))

# =====================================================================
# 1. Bent Relay Atrium
# =====================================================================
def build_atrium(seed):
    rng = random.Random(seed * 7919 + 11)
    N = 12
    rot = (seed * 17) % 360
    c = (0, 0)
    angles = [rot + i * (360.0 / N) + rng.uniform(-4.5, 4.5) for i in range(N)]
    radii = [900 + rng.uniform(-70, 90) for _ in range(N)]
    P = ring(c, angles, radii)
    Q = [scale_pt(c, P[i], 0.54 + 0.035 * math.sin(i * 1.7 + seed)) for i in range(N)]
    M = [scale_pt(c, P[i], 0.13 + 0.02 * math.cos(i * 2.1 + seed)) for i in range(N)]
    b = Builder("Bent Relay Atrium", ALL_TEX)

    # central crooked mast (decorative, non-walkable)
    b.sector("atrium.mast", M, 480, 512, GLOW, VOID, light=210, kind="decor",
             walk=False, tw=GLASS)
    # inner floor annulus (wedges 0-2 form the fan stair + top landing)
    for i in range(3, N):
        b.sector("atrium.inner.%02d" % i, wedge(M, Q, i), 0, 512, FLOOR, VOID,
                 light=150, kind="hall", tw=WALL)
    fan_floors = [16, 32, 48, 64, 80, 96, 112]
    for k, (poly, f) in enumerate(strip_group(M, Q, 0, 2, [4, 3], fan_floors)):
        b.sector("atrium.fan.%02d" % k, poly, f, 512, FLOOR2, VOID,
                 light=165, kind="stair", walk=True, tw=WALL, note="fan stair 0-112")
    b.sector("atrium.fan.landing", wedge(M, Q, 2), 128, 512, FLOOR2, VOID, light=175,
             kind="stair", walk=True, tw=WALL, note="fan stair top landing 128")

    # outer ring
    b.sector("atrium.bal.00", [Q[0], P[0], P[1], P[2], Q[2], Q[1]], 128, 512,
             FLOOR2, VOID, light=155, tw=WALL, note="broad two-bay balcony")
    asc_floors = [144 + 16 * k for k in range(9)]
    for k, (poly, f) in enumerate(strip_group(Q, P, 2, 3, [3, 3, 3], asc_floors)):
        b.sector("atrium.asc.%02d" % k, poly, f, 512, FLOOR2, VOID,
                 light=170, kind="stair", tw=WALL, note="tower stair up 128-272")
    for i in (5, 6, 7):
        b.sector("atrium.up.%02d" % i, wedge(Q, P, i), 272, 512, FLOOR, VOID,
                 light=185, kind="upper", tw=WALL)
    desc_floors = [256 - 16 * k for k in range(9)]
    for k, (poly, f) in enumerate(strip_group(Q, P, 8, 3, [3, 3, 3], desc_floors)):
        b.sector("atrium.desc.%02d" % k, poly, f, 512, FLOOR2, VOID,
                 light=165, kind="stair", tw=WALL, note="tower stair down 272-128")
    b.sector("atrium.gate", wedge(Q, P, 11), 0, 512, FLOOR, VOID, light=175,
             tag=901, kind="gate", tw=WALL, note="gate passage under 3D deck")

    # exterior relay bridge over the gate approach
    P10, P11, P0, P1 = P[10], P[11], P[0], P[1]
    nx, ny = outward_normal(P11, P0)
    def noff(d):
        return (round(nx * d), round(ny * d))
    n128, n380, n680 = noff(128), noff(380), noff(680)
    A = [P10, P11, (P11[0] + n128[0], P11[1] + n128[1]), (P10[0] + n128[0], P10[1] + n128[1])]
    B = [P0, P1, (P1[0] + n128[0], P1[1] + n128[1]), (P0[0] + n128[0], P0[1] + n128[1])]
    targ = [P11, P0, (P0[0] + n128[0], P0[1] + n128[1]), (P11[0] + n128[0], P11[1] + n128[1])]
    far = [(P11[0] + n128[0], P11[1] + n128[1]), (P0[0] + n128[0], P0[1] + n128[1]),
           (P0[0] + n380[0], P0[1] + n380[1]), (P11[0] + n380[0], P11[1] + n380[1])]
    b.sector("atrium.entry", A, 128, 512, FLOOR2, VOID, light=180, kind="entry", tw=WALL)
    b.sector("atrium.overlook", B, 128, 512, FLOOR, VOID, light=190, kind="overlook", tw=WALL)
    b.sector("atrium.bridge", targ, 0, 512, FLOOR2, VOID, light=170, tag=902,
             kind="bridge", tw=WALL, note="3D-floor relay bridge, 120-128")
    b.sector("atrium.under", far, 0, 512, FLOOR, VOID, light=120, kind="under", tw=WALL)
    C0 = (P11[0] + n380[0], P11[1] + n380[1])
    C1 = (P0[0] + n380[0], P0[1] + n380[1])
    C2 = (P0[0] + n680[0], P0[1] + n680[1])
    C3 = (P11[0] + n680[0], P11[1] + n680[1])
    court = [C0, C1, C2, C3]
    b.sector("atrium.court", court, 0, 512, FLOOR, VOID, light=150, kind="exit", tw=WALL)
    # vendor alcove off the courtyard's east side
    Mv = lerp_pt(C1, C2, 0.45)
    ex, ey = C1[0] - C0[0], C1[1] - C0[1]
    L = math.hypot(ex, ey) or 1
    dx, dy = round(ex / L * 230), round(ey / L * 230)
    alc = [Mv, C2, (C2[0] + dx, C2[1] + dy), (Mv[0] + dx, Mv[1] + dy)]
    b.sector("atrium.vendor", alc, 0, 160, FLOOR2, VOID, light=200, kind="vendor", tw=WALL2)
    add_control(b, "atrium.ctrl.gate", 901, 128, 0)
    add_control(b, "atrium.ctrl.bridge", 902, 128, 1)

    b.debug["landmark"] = "atrium.mast"
    b.start_sector = "atrium.entry"
    b.anchor_specs = [
        ("entry", "atrium.entry", 128, True),
        ("exit", "atrium.court", 0, True),
        ("vendor", "atrium.vendor", 0, True),
        ("encounter_a", "atrium.inner.08", 0, True),
        ("encounter_b", "atrium.up.05", 272, True),
        ("seal_a", "atrium.inner.04", 0, True),
        ("seal_b", "atrium.up.07", 272, True),
        ("overlook", "atrium.up.06", 272, True),
        ("pit_recovery", "atrium.under", 0, True),
        ("optional_reward", "atrium.overlook", 128, False),
    ]
    b.debug["levels"] = [0, 128, 272]
    b.finish()
    return b

# =====================================================================
# 2. Flooded Resonance Cistern
# =====================================================================
def build_cistern(seed):
    rng = random.Random(seed * 6151 + 29)
    N = 16
    rot = (seed * 23) % 360
    c = (0, 0)
    angles = [rot + i * (360.0 / N) + rng.uniform(-1.5, 1.5) for i in range(N)]
    radii = [1020 + rng.uniform(-80, 100) for _ in range(N)]
    P = ring(c, angles, radii)
    def fac(f):
        return [scale_pt(c, P[i], f) for i in range(N)]
    MAST, ISL, PIP, POP, TIN, TOUT = fac(0.07), fac(0.32), fac(0.44), fac(0.50), fac(0.62), fac(0.82)
    b = Builder("Flooded Resonance Cistern", ALL_TEX)
    b.sector("cistern.mast", MAST, 400, 512, GLOW, VOID, light=225, kind="decor",
             walk=False, tw=GLASS)
    # island ring (dry, 8)
    for i in range(N):
        b.sector("cistern.island.%02d" % i, wedge(MAST, ISL, i), 8, 512, FLOOR3, VOID,
                 light=160, kind="island", tw=WALL2)
    # water ring; choose causeways and bridge wedge
    # choose placements so no plain terrace wedge is walled in and each causeway
    # stair has a plain terrace neighbour at its 96 end
    cands = []
    for rg in range(N):
        rim_use = {rg, (rg + 1) % N, (rg + 2) % N}
        if ((rg - 1) % N) in rim_use:
            continue
        for c1 in range(N):
            if c1 in rim_use or ((c1 + 1) % N) in rim_use or ((c1 + 2) % N) in rim_use:
                continue
            for c2 in range(c1 + 1, N):
                if c2 in rim_use or ((c2 + 1) % N) in rim_use or ((c2 + 2) % N) in rim_use:
                    continue
                shore1 = {c1, (c1 + 1) % N}
                shore2 = {c2, (c2 + 1) % N}
                if shore1 & shore2:
                    continue
                if ((c1 + 2) % N) in shore2 or ((c2 + 2) % N) in shore1:
                    continue
                used0 = rim_use | shore1 | shore2
                bad = False
                for i in range(N):
                    if i in used0:
                        continue
                    if ((i - 1) % N) in used0 and ((i + 1) % N) in used0:
                        bad = True; break
                if bad:
                    continue
                # every plain terrace run must touch a 96-level link
                # (shore-stair top at c+1, or the rim stair's low end at rg-1)
                links = {((c1 + 2) % N), ((c2 + 2) % N), ((rg - 1) % N)}
                plain = [i for i in range(N) if i not in used0]
                # start after a used wedge so runs do not wrap awkwardly
                anchor = next(i for i in range(N) if i in used0)
                runs = []; cur = []
                for d in range(1, N + 1):
                    i = (anchor + d) % N
                    if i in used0:
                        if cur: runs.append(cur); cur = []
                    else:
                        cur.append(i)
                if cur: runs.append(cur)
                for run in runs:
                    if not any(i in links for i in run):
                        bad = True; break
                if bad:
                    continue
                for bi in range(N):
                    if bi in used0:
                        continue
                    cands.append((rg, c1, c2, bi))
    if not cands:
        raise RuntimeError("no valid cistern ring placement")
    _rg0, cw1, cw2, bi = cands[seed % len(cands)]
    causeways = []
    for i in range(N):
        if i == bi:
            Pin, Pout = PIP, POP
            b.sector("cistern.bayinner", wedge(ISL, Pin, i), -8, 512, WATER, VOID,
                     light=110, kind="water", tw=WALL)
            b.sector("cistern.pump", wedge(Pin, Pout, i), 96, 512, FLOOR2, VOID,
                     light=195, kind="pump", tw=WALL2)
            b.sector("cistern.bay", wedge(Pout, TIN, i), -8, 512, WATER, VOID,
                     light=130, tag=903, kind="bridge", tw=WALL,
                     note="3D-floor bridge 88-96 over shallow water")
        elif i in (cw1, cw2):
            causeways.append(i)
            b.sector("cistern.causeway.%02d" % i, wedge(ISL, TIN, i), 8, 512, FLOOR2, VOID,
                     light=150, kind="causeway", tw=WALL2, note="low service causeway")
        else:
            b.sector("cistern.water.%02d" % i, wedge(ISL, TIN, i), -8, 512, WATER, VOID,
                     light=105, kind="water", tw=WALL)
    # terrace ring: shore stairs over causeways, rim stair group elsewhere
    rim_group = _rg0
    rim_group_start = rim_group
    shore_groups = {}
    for i in causeways:
        fl = [24, 40, 56, 72, 88, 96]
        shore_groups[i] = []
        for k, (poly, f) in enumerate(strip_group(TIN, TOUT, i, 2, [3, 3], fl)):
            name = "cistern.shore.%02d.%02d" % (i, k)
            b.sector(name, poly, f, 512, FLOOR2, VOID, light=155, kind="stair",
                     tw=WALL2, note="causeway stair 8-96")
            shore_groups[i].append(name)
    used = set(causeways) | {((i + 1) % N) for i in causeways} | \
           {(rim_group + k) % N for k in range(3)}
    for i in range(N):
        if i in used:
            continue
        b.sector("cistern.terrace.%02d" % i, wedge(TIN, TOUT, i), 96, 512, FLOOR, VOID,
                 light=165, kind="terrace", tw=WALL)
    rim_floors = [112 + 16 * k for k in range(10)] + [256, 256]
    rim_strips = []
    rim_band = strip_group(TIN, TOUT, rim_group_start, 3, [4, 4, 4], rim_floors)
    for k, (poly, f) in enumerate(rim_band[:-3]):
        name = "cistern.rimstair.%02d" % k
        b.sector(name, poly, f, 512, FLOOR2, VOID, light=170, kind="stair",
                 tw=WALL, note="terrace-rim stair 112-240")
        rim_strips.append(name)
    rim_land = merge_strips([p for p, f in rim_band[-3:]])
    b.sector("cistern.rimstair.landing", rim_land, 256, 512, FLOOR2, VOID, light=185,
             kind="stair", tw=WALL, note="rim stair top landing 256")
    rim_strips.append("cistern.rimstair.landing")
    for i in range(N):
        b.sector("cistern.rim.%02d" % i, wedge(TOUT, P, i), 256, 512, FLOOR, VOID,
                 light=185, kind="rim", tw=WALL)
    # annexes on rim outer edges
    def annex(i, depth, ceil, name, light, tf=FLOOR, tw=WALL):
        a, bb = P[i], P[(i + 1) % N]
        nx, ny = outward_normal(a, bb)
        d = (round(nx * depth), round(ny * depth))
        poly = [a, bb, (bb[0] + d[0], bb[1] + d[1]), (a[0] + d[0], a[1] + d[1])]
        b.sector(name, poly, 256, ceil, tf, VOID, light=light, kind="annex", tw=tw)
        return poly
    entry_i = (seed + 5) % N
    exit_i = (seed + 9) % N
    vend_i = (seed + 13) % N
    annex(entry_i, 300, 512, "cistern.entry", 190, FLOOR2, WALL2)
    annex(exit_i, 260, 512, "cistern.exit", 175)
    annex(vend_i, 240, 352, "cistern.vendor", 200, FLOOR2, WALL2)
    add_control(b, "cistern.ctrl.bridge", 903, 96, 2)

    # ---- anchors (route edges are derived from real sector adjacency) ----
    tplain = [i for i in range(N) if i not in used]
    b.debug["landmark"] = "cistern.mast"
    b.start_sector = "cistern.entry"
    b.anchor_specs = [
        ("entry", "cistern.entry", 256, True),
        ("exit", "cistern.exit", 256, True),
        ("vendor", "cistern.vendor", 256, True),
        ("encounter_a", "cistern.terrace.%02d" % tplain[0], 96, True),
        ("encounter_b", "cistern.island.%02d" % ((seed + 1) % N), 8, True),
        ("seal_a", "cistern.island.%02d" % ((seed + 6) % N), 8, True),
        ("seal_b", "cistern.terrace.%02d" % tplain[-1], 96, True),
        ("overlook", "cistern.rim.%02d" % ((seed + 5) % N), 256, True),
        ("pit_recovery", "cistern.water.%02d" % next(
            i for i in range(N) if i not in causeways and i != bi), -8, True),
        ("optional_reward", "cistern.pump", 96, False),
    ]
    b.debug["levels"] = [-8, 8, 96, 256]
    b.debug["levels"] = [-8, 8, 96, 256]
    b.finish()
    return b

# =====================================================================
# 3. Hanging Boneglass Garden
# =====================================================================
def build_garden(seed):
    rng = random.Random(seed * 3323 + 53)
    s = 1.0 + 0.02 * ((seed % 7) - 3)
    ang = math.radians((seed * 13) % 360)
    ca, sa = math.cos(ang), math.sin(ang)
    cache = {}
    def X(p):
        if p not in cache:
            x, y = p
            cache[p] = (round((x * ca - y * sa) * s), round((x * sa + y * ca) * s))
        return cache[p]
    b = Builder("Hanging Boneglass Garden", ALL_TEX)
    def sect(name, poly, floor, ceil, tf, tc, light, kind="walk", tag=0, walk=True, tw=WALL3, note=""):
        return b.sector(name, [X(p) for p in poly], floor, ceil, tf, tc, light=light,
                        tag=tag, kind=kind, walk=walk, tw=tw, note=note)
    # central void / catch floor, split by the canopy bridge footprint
    vw = [(-420, -280), (-64, -280), (-64, 460), (-420, 460)]
    ve = [(64, -280), (420, -280), (420, 260), (160, 460), (64, 460)]
    strip = [(-64, -280), (64, -280), (64, 460), (-64, 460)]
    sect("garden.void_west", vw, -224, 1024, FLOOR2, VOID, 84, "pit", tw=WALL3,
         note="catch floor, recovery stair to entry")
    sect("garden.void_east", ve, -224, 1024, FLOOR2, VOID, 76, "pit", tw=WALL3)
    sect("garden.bridge", strip, -224, 1024, FLOOR2, VOID, 120, "bridge", tag=904,
         tw=WALL3, note="3D-floor canopy bridge 184-192 over catch floor")
    # south and north platforms at 192, main at 64, low at 0
    sect("garden.south", [(-220, -280), (64, -280), (64, -560), (-220, -560)], 192, 1024,
         FLOOR, VOID, 150, "platform", tw=WALL3, note="generous encounter ledge over the void")
    sect("garden.north", [(-220, 460), (64, 460), (64, 740), (-220, 740)], 192, 1024,
         FLOOR, VOID, 145, "platform", tw=WALL3)
    ex = 620 + 40 * (((seed // 3) % 3) - 1)
    sect("garden.main", [(320, -600), (ex, -600), (ex, -300), (320, -300)], 64, 1024,
         FLOOR3, VOID, 135, "platform", tw=WALL3, note="generous encounter zone, 20 units clear of the void edge")
    sect("garden.low", [(320, -720), (620, -720), (620, -1080), (320, -1080)], 0, 1024,
         FLOOR3, VOID, 115, "platform", tw=WALL3)
    sect("garden.upper", [(-220, 980), (220, 980), (220, 1240), (-220, 1240)], 320, 1024,
         FLOOR, VOID, 165, "upper", tw=WALL3)
    sect("garden.alcove", [(-100, 1240), (100, 1240), (100, 1440), (-100, 1440)], 320, 432,
         FLOOR, GLOW, 190, "alcove", tw=GLASS, note="sheltered observation alcove")
    sect("garden.vendor", [(ex, -520), (ex + 200, -520), (ex + 200, -360), (ex, -360)],
         64, 160, FLOOR2, GLOW, 195, "vendor", tw=WALL2)
    sect("garden.exit", [(400, -1080), (560, -1080), (560, -1260), (400, -1260)],
         0, 1024, FLOOR, VOID, 130, "exit", tw=WALL3)
    sect("garden.entry", [(-812, -400), (-812, 0), (-1112, 0), (-1112, -400)],
         0, 1024, FLOOR, VOID, 150, "entry", tw=WALL3)
    sect("garden.corridor", [(320, -880), (320, -1008), (-812, -336), (-812, -208)],
         0, 1024, FLOOR2, VOID, 118, "walkway", tw=WALL3, note="long diagonal ledge walk")
    # long west route: 20-step stair U(320) down to landing 0, then corridor to entry
    for k in range(20):
        x0 = -220 - 30 * k
        x1 = x0 - 30
        sect("garden.wstair.%02d" % k, [(x0, 1040), (x0, 1168), (x1, 1168), (x1, 1040)],
             304 - 16 * k, 1024, FLOOR2, VOID, 120, "stair", tw=WALL3,
             note="west flight, 16 rise")
    sect("garden.wlanding", [(-980, 1040), (-820, 1040), (-820, 1168), (-980, 1168)],
         0, 1024, FLOOR2, VOID, 100, "platform", tw=WALL3)
    sect("garden.wcorridor", [(-980, 0), (-852, 0), (-852, 1040), (-980, 1040)],
         0, 1024, FLOOR2, VOID, 100, "walkway", tw=WALL3)
    # recovery stair from the catch floor up to the entry platform
    for k in range(14):
        x0 = -420 - 28 * k
        x1 = x0 - 28
        sect("garden.recovery.%02d" % k, [(x0, -160), (x0, -32), (x1, -32), (x1, -160)],
             -208 + 16 * k, 1024, FLOOR2, VOID, 90, "stair", tw=WALL3,
             note="pit recovery, 16 rise")
    # platform stairs
    for k in range(8):
        x0 = 64 + 32 * k
        x1 = x0 + 32
        sect("garden.sm.%02d" % k, [(x0, -480), (x0, -320), (x1, -320), (x1, -480)],
             176 - 16 * k, 1024, FLOOR2, VOID, 130, "stair", tw=WALL3)
    for k in range(4):
        y0 = -600 - 30 * k
        y1 = y0 - 30
        sect("garden.ml.%02d" % k, [(400, y0), (560, y0), (560, y1), (400, y1)],
             48 - 16 * k, 1024, FLOOR2, VOID, 120, "stair", tw=WALL3)
    for k in range(8):
        y0 = 740 + 30 * k
        y1 = y0 + 30
        sect("garden.nu.%02d" % k, [(-64, y0), (64, y0), (64, y1), (-64, y1)],
             208 + 16 * k, 1024, FLOOR2, VOID, 150, "stair", tw=WALL3)
    # decorative-only boneglass ribs and suspended planters (raised, non-walkable)
    def hexpoly(cx, cy, r, n=6, phase=0.0):
        return [(round(cx + r * math.cos(phase + 2 * math.pi * i / n)),
                 round(cy + r * math.sin(phase + 2 * math.pi * i / n))) for i in range(n)]
    rib1 = hexpoly(720, 600, 70, 6, 0.3)
    sect("garden.rib1", rib1, 640, 1024, FLOOR2, VOID, 110, "decor", walk=False, tw=WALL3)
    # a branch attached to one hex edge, also raised and non-walkable
    a, bb = rib1[0], rib1[1]
    dx, dy = bb[0] - a[0], bb[1] - a[1]
    L = math.hypot(dx, dy) or 1
    px, py = -dy / L * 150, dx / L * 150
    mx, my = (a[0] + bb[0]) / 2 - 720, (a[1] + bb[1]) / 2 - 600
    if px * mx + py * my < 0:
        px, py = -px, -py
    branch = [bb, a, (a[0] + px, a[1] + py), (bb[0] + px, bb[1] + py)]
    sect("garden.rib1branch", branch, 700, 1024, FLOOR2, VOID, 90, "decor", walk=False, tw=WALL3)
    sect("garden.rib2", hexpoly(-650, 760, 55, 6, 1.1), 700, 1024, FLOOR2, VOID, 80,
         "decor", walk=False, tw=WALL3)
    sect("garden.rib3", hexpoly(760, -760, 48, 5, 0.7), 560, 1024, FLOOR2, VOID, 85,
         "decor", walk=False, tw=WALL3)
    sect("garden.planter1", hexpoly(300, -1250, 46, 8, 0.2), 520, 1024, FLOOR3, VOID, 90,
         "decor", walk=False, tw=WALL3)
    sect("garden.planter2", hexpoly(-300, 1350, 40, 8, 0.9), 560, 1024, FLOOR3, VOID, 95,
         "decor", walk=False, tw=WALL3)
    add_control(b, "garden.ctrl.bridge", 904, 192, 3)

    b.debug["landmark"] = "garden.rib1"
    b.start_sector = "garden.entry"
    b.anchor_specs = [
        ("entry", "garden.entry", 0, True),
        ("exit", "garden.exit", 0, True),
        ("vendor", "garden.vendor", 64, True),
        ("encounter_a", "garden.south", 192, True),
        ("encounter_b", "garden.main", 64, True),
        ("seal_a", "garden.entry", 0, True),
        ("seal_b", "garden.upper", 320, True),
        ("overlook", "garden.upper", 320, True),
        ("pit_recovery", "garden.void_west", -224, True),
        ("optional_reward", "garden.alcove", 320, False),
    ]
    b.debug["levels"] = [-224, 0, 64, 192, 320]
    b.debug["covers"] = [(0, 0, 0)]
    b.finish()
    return b

BUILDERS = {
    "bent-relay-atrium": build_atrium,
    "flooded-resonance-cistern": build_cistern,
    "hanging-boneglass-garden": build_garden,
}
