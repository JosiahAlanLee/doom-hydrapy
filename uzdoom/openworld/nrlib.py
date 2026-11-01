"""nrlib - CPU-only blockout geometry, UDMF writer, validator and previews.

No UZDoom runtime is used here. Structural checks are geometric only.
"""
import json, math, os, hashlib, zipfile, struct, io
from collections import defaultdict, deque

# ---------- small geometry helpers ----------

def area2(poly):
    s = 0
    for i, (x, y) in enumerate(poly):
        x2, y2 = poly[(i + 1) % len(poly)]
        s += x * y2 - x2 * y
    return s / 2.0

def signed_area(poly):
    return area2(poly)

def is_clockwise(poly):
    return signed_area(poly) < 0

def ccw(poly):
    return list(poly) if signed_area(poly) > 0 else list(reversed(poly))

def cw(poly):
    p = [(round(x), round(y)) for x, y in poly]
    if len(p) > 1 and p[0] == p[-1]:
        p = p[:-1]
    return p if signed_area(p) < 0 else list(reversed(p))

def polar(cx, cy, r, deg):
    a = math.radians(deg)
    return (cx + r * math.cos(a), cy + r * math.sin(a))

def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])

def seg_intersect(a, b, c, d, eps=1e-9):
    """True if open segments ab and cd properly intersect (shared endpoints excluded)."""
    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    if a in (c, d) or b in (c, d):
        return False
    d1, d2 = cross(c, d, a), cross(c, d, b)
    d3, d4 = cross(a, b, c), cross(a, b, d)
    return (d1 * d2 < -eps) and (d3 * d4 < -eps)

def point_in_poly(x, y, poly, eps=1e-9):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < xin:
                inside = not inside
    return inside

def poly_simple(poly):
    n = len(poly)
    if n < 3:
        return False, "fewer than 3 vertices"
    for i in range(n):
        if poly[i] == poly[(i + 1) % n]:
            return False, "duplicate consecutive vertex"
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        for j in range(i + 1, n):
            c, d = poly[j], poly[(j + 1) % n]
            if j == i or (j + 1) % n == i or (i + 1) % n == j:
                continue
            if seg_intersect(a, b, c, d):
                return False, "self-intersection at edges %d/%d" % (i, j)
    return True, "ok"

def min_width(poly):
    """Approximate minimum width: min distance between non-adjacent edges, plus 2*inradius fallback."""
    best = float("inf")
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or (i + 1) % n == j:
                continue
            c, d = poly[j], poly[(j + 1) % n]
            best = min(best, seg_seg_dist(a, b, c, d))
    return best

def seg_seg_dist(a, b, c, d):
    return min(point_seg_dist(a, c, d), point_seg_dist(b, c, d),
               point_seg_dist(c, a, b), point_seg_dist(d, a, b))

def point_seg_dist(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

# ---------- map model ----------

class Sector:
    def __init__(self, name, poly, floor, ceil, tf, tc, light=160, tag=0,
                 kind="walk", walk=True, note="", tw="NRRUST1"):
        self.name = name
        self.poly = cw(poly)
        self.floor = int(floor)
        self.ceil = int(ceil)
        self.tf = tf
        self.tc = tc
        self.light = int(light)
        self.tag = int(tag)
        self.kind = kind
        self.walk = walk
        self.note = note
        self.tw = tw
        self.index = -1

class Builder:
    def __init__(self, title, texture_names):
        self.title = title
        self.textures = set(texture_names)
        self.sectors = []
        self.nodes = []
        self.edges = []
        self.anchors = {}
        self.debug = {}
        self.by_name = {}
        self.controls = []

    def sector(self, name, poly, floor, ceil, tf, tc, light=160, tag=0,
               kind="walk", walk=True, note="", tw="NRRUST1"):
        if name in self.by_name:
            raise ValueError("duplicate sector name " + name)
        s = Sector(name, poly, floor, ceil, tf, tc, light, tag, kind, walk, note, tw)
        s.index = len(self.sectors)
        self.sectors.append(s)
        self.by_name[name] = s
        return s

    def node(self, nid, sector, x, y, z, role="route", **kw):
        if sector not in self.by_name:
            raise ValueError("node %s: unknown sector %s" % (nid, sector))
        self.nodes.append({"id": nid, "sector": sector, "x": int(x), "y": int(y),
                           "z": int(z), "role": role, **kw})
        if role not in ("route", "stair", "under", "optional"):
            self.anchors[role] = self.nodes[-1]
        return self.nodes[-1]

    def edge(self, a, b, kind="walk", note=""):
        self.edges.append({"a": a, "b": b, "kind": kind, "note": note})

    def control(self, name, target_tag, top):
        self.controls.append({"sector": name, "tag": int(target_tag), "top": int(top)})

    def _reconcile(self):
        """Insert T-junction vertices into polygon edges so shared boundaries match."""
        for _pass in range(3):
            changed = 0
            allpts = sorted({p for s in self.sectors for p in s.poly})
            for s in self.sectors:
                newpoly = []
                own = set(s.poly)
                for i in range(len(s.poly)):
                    a = s.poly[i]
                    b = s.poly[(i + 1) % len(s.poly)]
                    newpoly.append(a)
                    ax, ay = a; bx, by = b
                    dx, dy = bx - ax, by - ay
                    L = math.hypot(dx, dy)
                    if L < 1:
                        continue
                    inserts = []
                    for p in allpts:
                        if p in own or p == a or p == b:
                            continue
                        t = ((p[0] - ax) * dx + (p[1] - ay) * dy) / (L * L)
                        if t <= 2.0 / L or t >= 1.0 - 2.0 / L:
                            continue
                        px = ax + t * dx; py = ay + t * dy
                        if math.hypot(p[0] - px, p[1] - py) < 1.1:
                            inserts.append((t, p))
                    inserts.sort()
                    for t, p in inserts:
                        newpoly.append(p); changed += 1
                s.poly = newpoly
            if not changed:
                break

    def _build_lines(self):
        emap = defaultdict(list)
        for s in self.sectors:
            p = s.poly
            for i in range(len(p)):
                a, b = p[i], p[(i + 1) % len(p)]
                key = (a, b) if a < b else (b, a)
                direction = 1 if (a, b) == key else -1
                emap[key].append((s, direction, a, b))
        lines = []
        for key, uses in emap.items():
            if len(uses) > 2:
                raise ValueError("edge used %d times: %s" % (len(uses), key))
            if len(uses) == 2 and uses[0][1] == uses[1][1]:
                raise ValueError("edge used twice in same direction: %s" % (key,))
            if len(uses) == 2:
                s0, d0, a, b = uses[0]
                s1, d1 = uses[1][0], uses[1][1]
                # keep vertices consistently oriented from the first use
                lines.append({"a": a, "b": b, "front": s0, "back": s1, "two": True})
            else:
                s0, d0, a, b = uses[0]
                lines.append({"a": a, "b": b, "front": s0, "back": None, "two": False})
        return lines

    def finish(self):
        self._reconcile()
        self.lines = self._build_lines()
        self.verts = sorted({p for s in self.sectors for p in s.poly})
        self.vindex = {p: i for i, p in enumerate(self.verts)}

    # ---------- output ----------

def write_udmf(builder, player_start, path):
    """Write a UDMF TEXTMAP. Side indices are assigned here."""
    sides = []
    for ln in builder.lines:
        f = len(sides)
        sides.append({"sector": ln["front"], "kind": "front"})
        b = -1
        if ln["two"]:
            b = len(sides)
            sides.append({"sector": ln["back"], "kind": "back"})
        ln["sidefront"] = f
        ln["sideback"] = b
    L = ['namespace = "zdoom";', '']
    for p in builder.verts:
        L.append("vertex { x = %d; y = %d; }" % p)
    L.append('')
    ctrl_by_sector = {builder.by_name[c["sector"]].index: c for c in builder.controls}
    for ln in builder.lines:
        flags = "twosided = true; blocking = false;" if ln["two"] else "blocking = true;"
        extra = ""
        cinfo = ctrl_by_sector.get(ln["front"].index)
        if cinfo is not None and not ln["two"] and cinfo.get("used", 0) == 0:
            extra = " special = 160; arg0 = %d; arg1 = 1; arg2 = 0; arg3 = 255; arg4 = 0;" % cinfo["tag"]
            cinfo["used"] = 1
        L.append("linedef { v1 = %d; v2 = %d; sidefront = %d; sideback = %d; %s%s }" % (
            builder.vindex[ln["a"]], builder.vindex[ln["b"]], ln["sidefront"], ln["sideback"], flags, extra))
    L.append('')
    # map linedef index -> two-sided
    two_by_side = {}
    for li, ln in enumerate(builder.lines):
        two_by_side[ln["sidefront"]] = ln["two"]
        if ln["two"]:
            two_by_side[ln["sideback"]] = True
    for i, sd in enumerate(sides):
        s = sd["sector"]
        if two_by_side.get(i, False):
            top, bottom, mid = s.tw, s.tw, "-"
        else:
            top, bottom, mid = "-", "-", s.tw
        L.append("sidedef { sector = %d; texturetop = \"%s\"; texturebottom = \"%s\"; texturemiddle = \"%s\"; }" % (
            s.index, top, bottom, mid))
    L.append('')
    for i, s in enumerate(builder.sectors):
        L.append("sector { id = %d; heightfloor = %d; heightceiling = %d; texturefloor = \"%s\"; textureceiling = \"%s\"; lightlevel = %d; special = 0; }" % (
            s.tag, s.floor, s.ceil, s.tf, s.tc, s.light))
    L.append('')
    px, py, pz, pang = player_start
    L.append("thing { type = 1; x = %d; y = %d; z = %d; angle = %d; }" % (px, py, pz, pang))
    L.append('')
    text = "\n".join(L) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return text

def write_wad(textmap, path):
    data = textmap.encode("utf-8")
    lumps = [(b"MAP01", b""), (b"TEXTMAP", data), (b"ENDMAP", b"")]
    out = io.BytesIO()
    data_size = sum(len(d) for name, d in lumps)
    infotableofs = 12 + data_size
    out.write(b"PWAD")
    out.write(struct.pack("<ii", len(lumps), infotableofs))
    offset = 12
    dirents = []
    for name, d in lumps:
        out.write(d)
        dirents.append((offset, len(d), name))
        offset += len(d)
    for off, size, name in dirents:
        out.write(struct.pack("<ii", off, size))
        out.write(name.ljust(8, b"\0"))
    with open(path, "wb") as f:
        f.write(out.getvalue())
    return out.getvalue()

def write_pk3(path, wad_bytes, mapinfo, textures, flats, texdir):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        def add(name, data):
            zi = zipfile.ZipInfo(name, date_time=(2026, 10, 31, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, data)
        add("MAPINFO", mapinfo.encode("utf-8"))
        add("maps/MAP01.wad", wad_bytes)
        for n in sorted(textures):
            p = os.path.join(texdir, n + ".png")
            add("textures/%s.png" % n, open(p, "rb").read())
        for n in sorted(flats):
            p = os.path.join(texdir, n + ".png")
            add("flats/%s.png" % n, open(p, "rb").read())
