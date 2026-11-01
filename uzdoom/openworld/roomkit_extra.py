"""roomkit - small reusable plan/level helpers over the original nrlib Builder.

Original helper code for this job. No engine API is called; polygons are map
units (integers) and all level changes are explicit sector floors.
"""
import math
from .nrlib import Builder, cw, point_in_poly

WALL, WALL2, WALL3 = "NRRUST1", "NRCELAD1", "NRBONE1"
FLOOR, FLOOR2, FLOOR3 = "NRFLOOR1", "NRFLOOR2", "NRMOSS1"
WATER, VOID, GLOW, GLASS = "NRWATER1", "NRVOID1", "NRGLOW1", "NRGLASS1"
ALL_TEX = [WALL, WALL2, WALL3, FLOOR, FLOOR2, FLOOR3, WATER, VOID, GLOW, GLASS]

RISE = 16

def rect(x0, y0, x1, y1):
    return [(x0, y0), (x0, y1), (x1, y1), (x1, y0)]

def rotate(cx, cy, deg, p):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    x, y = p[0] - cx, p[1] - cy
    return (round(cx + x * ca - y * sa), round(cy + x * sa + y * ca))

def mapped(points, deg=0.0, cx=0.0, cy=0.0, ox=0, oy=0):
    return [(round(x + ox), round(y + oy)) for x, y in
            (rotate(cx, cy, deg, p) for p in points)]

def arc(cx, cy, r, a0, a1, step=15.0, include_end=True):
    """Integer points along an arc, endpoints included when they land on step grid."""
    n = max(1, int(round(abs(a1 - a0) / step)))
    pts = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts.append((round(cx + r * math.cos(a)), round(cy + r * math.sin(a))))
    clean = []
    for p in pts:
        if not clean or clean[-1] != p:
            clean.append(p)
    if not include_end and len(clean) > 1:
        clean = clean[:-1]
    return clean

def poly_ring(cx, cy, r0, r1, a0, a1, step=15.0, notches=()):
    """Half/annulus sector polygon with optional angular notches cut radially.

    `notches` is a list of (start,end) degree pairs, sorted, inside [a0,a1].
    The notch void is exactly the footprint a stair sector may fill.
    """
    notches = sorted(notches)
    pts = []
    cur = a0
    # inner arc from a0 to first notch, jogs across each notch, then to a1
    for ns, ne in notches + [(a1, a1)]:
        if ns > cur:
            pts += arc(cx, cy, r0, cur, ns, step)[:-1]
        if ne > ns:
            pts.append((round(cx + r0 * math.cos(math.radians(ns))),
                        round(cy + r0 * math.sin(math.radians(ns)))))
            pts.append((round(cx + r1 * math.cos(math.radians(ns))),
                        round(cy + r1 * math.sin(math.radians(ns)))))
            pts += arc(cx, cy, r1, ns, ne, step)
            pts.append((round(cx + r1 * math.cos(math.radians(ne))),
                        round(cy + r1 * math.sin(math.radians(ne)))))
            pts.append((round(cx + r0 * math.cos(math.radians(ne))),
                        round(cy + r0 * math.sin(math.radians(ne)))))
        cur = ne
    # outer arc back from a1 to a0 (if not already emitted by final notch)
    if not notches or notches[-1][1] < a1:
        pts += arc(cx, cy, r1, a1, a0, step)
    elif notches and notches[-1][1] == a1:
        pass
    # close: radial at a0 from r1 back to r0 handled by cw()/repeated point
    clean = []
    for p in pts:
        if not clean or clean[-1] != p:
            clean.append(p)
    if clean and clean[0] == clean[-1]:
        clean.pop()
    return clean

def wedge(cx, cy, r0, r1, a0, a1, step=15.0):
    pts = arc(cx, cy, r1, a0, a1, step) + list(reversed(arc(cx, cy, r0, a0, a1, step)))
    clean = []
    for p in pts:
        if not clean or clean[-1] != p:
            clean.append(p)
    if clean and clean[0] == clean[-1]:
        clean.pop()
    return clean

def octagon(cx, cy, r, phase=22.5):
    return [(round(cx + r * math.cos(math.radians(phase + 45 * i))),
             round(cy + r * math.sin(math.radians(phase + 45 * i)))) for i in range(8)]

def add(b, name, poly, floor, ceil, tf=FLOOR, tc=VOID, light=160, kind="walk",
        walk=True, tag=0, tw=WALL, note=""):
    return b.sector(name, poly, floor, ceil, tf, tc, light=light, tag=tag,
                    kind=kind, walk=walk, note=note, tw=tw)

def add_stairs(b, prefix, box, nsteps, zhi, rise=RISE, axis="y", high_end="hi",
               tf=FLOOR2, tc=VOID, tw=WALL, light=150, note="", kind="stair"):
    """Split a rectangle into nsteps ordinary sectors along axis, descending.

    The first returned sector is the highest step (floor zhi-rise); its outer
    edge lies on the high end of the box. Floors are zhi-rise*i for i=1..n.
    """
    x0, y0, x1, y1 = box
    assert nsteps >= 1
    names = []
    lo, hi = (y0, y1) if axis == "y" else (x0, x1)
    span = hi - lo
    assert span >= nsteps * 20, "tread too short: %d/%d" % (span, nsteps)
    bounds = [lo + round(span * i / nsteps) for i in range(nsteps + 1)]
    for k in range(nsteps):
        z = zhi - rise * (k + 1)
        if high_end == "hi":
            a, c = bounds[nsteps - k - 1], bounds[nsteps - k]
        else:
            a, c = bounds[k], bounds[k + 1]
        sub = (x0, a, x1, c) if axis == "y" else (a, y0, c, y1)
        name = "%s.%02d" % (prefix, k)
        add(b, name, rect(*sub), z, z + 512, tf, tc, light, kind=kind,
            tw=tw, note=note or ("stair %d, rise %d" % (z, rise)))
        names.append(name)
    return names

def add_control(b, name, target_tag, top, slot):
    cx, cy = 9200, 9200 + slot * 180
    add(b, name, rect(cx, cy, cx + 64, cy + 64), top - 8, top, GLOW, VOID,
        light=255, kind="control", walk=False, tw=GLOW)
    b.control(name, target_tag, top)

def attach_rect(edge_a, edge_b, depth, out_sign=1):
    """Rectangle projecting from segment a->b along its outward normal."""
    dx, dy = edge_b[0] - edge_a[0], edge_b[1] - edge_a[1]
    L = math.hypot(dx, dy) or 1.0
    nx, ny = dy / L * out_sign, -dx / L * out_sign
    d = (round(nx * depth), round(ny * depth))
    return [edge_a, edge_b, (edge_b[0] + d[0], edge_b[1] + d[1]),
            (edge_a[0] + d[0], edge_a[1] + d[1])]

def bbox_area(poly):
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    return (max(xs) - min(xs)) * (max(ys) - min(ys))

def centroid(poly):
    return (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))

def rotate_builder(b, deg, ox=0, oy=0):
    """Rigidly rotate every non-control sector polygon; controls stay isolated."""
    if not deg:
        return
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    cache = {}
    for s in b.sectors:
        if s.kind == "control":
            continue
        out = []
        for x, y in s.poly:
            key = (x, y)
            if key not in cache:
                cache[key] = (round(x * ca - y * sa + ox), round(x * sa + y * ca + oy))
            out.append(cache[key])
        s.poly = cw(out)
    b.debug["rotation_deg"] = deg

def lerp_pt(a, b, t):
    return (round(a[0] + (b[0] - a[0]) * t), round(a[1] + (b[1] - a[1]) * t))

def outward(a, b, away=(0, 0)):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1.0
    nx, ny = dy / L, -dx / L
    mx, my = (a[0] + b[0]) / 2 - away[0], (a[1] + b[1]) / 2 - away[1]
    if nx * mx + ny * my < 0:
        nx, ny = -nx, -ny
    return nx, ny

def out_rect(p0, p1, t0, t1, depth, away=(0, 0)):
    a, b = lerp_pt(p0, p1, t0), lerp_pt(p0, p1, t1)
    nx, ny = outward(a, b, away)
    d = (round(nx * depth), round(ny * depth))
    return [a, b, (b[0] + d[0], b[1] + d[1]), (a[0] + d[0], a[1] + d[1])], (a, b, d)

def rect_on_edge(p0, p1, t0, t1, depth, away, side=1):
    """Rectangle on a segment, offset along one of its two normals."""
    a, b = lerp_pt(p0, p1, t0), lerp_pt(p0, p1, t1)
    nx, ny = outward(a, b, away)
    d = (round(nx * depth * side), round(ny * depth * side))
    return [a, b, (b[0] + d[0], b[1] + d[1]), (a[0] + d[0], a[1] + d[1])], (a, b, d)
