"""Route graph derived from real sector adjacency, plus 3D-floor deck levels."""
import math
from collections import defaultdict, deque
from .nrlib import point_in_poly

def _centroid(s):
    xs = [p[0] for p in s.poly]; ys = [p[1] for p in s.poly]
    return int(round(sum(xs) / len(xs))), int(round(sum(ys) / len(ys)))

def _length(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])

def build_graph(b):
    walk = {s.name: s for s in b.sectors if s.walk and s.kind != "control"}
    tag_sector = {}
    for s in b.sectors:
        if s.tag:
            if s.tag in tag_sector:
                raise ValueError("duplicate sector tag %d" % s.tag)
            tag_sector[s.tag] = s
    ctrl_by_tag = {}
    for c in b.controls:
        if c["tag"] not in tag_sector:
            raise ValueError("control tag %d has no target sector" % c["tag"])
        ctrl_by_tag.setdefault(c["tag"], []).append(c)
    nodes = {}
    adj = defaultdict(list)
    def add_node(nid, sector, z, kind):
        x, y = _centroid(sector)
        nodes[nid] = {"id": nid, "sector": sector.name, "x": x, "y": y, "z": int(z),
                      "kind": kind, "floor": sector.floor, "ceiling": sector.ceil}
        return nid
    for name, s in walk.items():
        add_node(name, s, s.floor, "sector")
    deck_nodes = {}
    for tag, cs in ctrl_by_tag.items():
        s = tag_sector[tag]
        for c in cs:
            nid = "%s@deck%d" % (s.name, c["top"])
            add_node(nid, s, c["top"], "deck")
            deck_nodes[(s.name, c["top"])] = nid
    edge_map = {}
    def add_edge(a, b_, kind, width, note=""):
        if a == b_:
            return
        key = (a, b_) if a < b_ else (b_, a)
        rise = abs(nodes[a]["z"] - nodes[b_]["z"])
        e = {"a": key[0], "b": key[1], "kind": kind, "width": round(width, 1),
             "rise": rise, "note": note}
        old = edge_map.get(key)
        if old is None or e["width"] > old["width"] or kind == "3dfloor":
            edge_map[key] = e
    for ln in b.lines:
        if not ln["two"]:
            continue
        s0, s1 = ln["front"], ln["back"]
        if s0.name not in walk or s1.name not in walk:
            continue
        width = _length(ln["a"], ln["b"])
        if abs(s0.floor - s1.floor) <= 16:
            kind = "walk" if s0.floor == s1.floor else "stair"
            add_edge(s0.name, s1.name, kind, width)
        # deck-level adjacency for tagged target sectors
        for s_t, s_o in ((s0, s1), (s1, s0)):
            for c in ctrl_by_tag.get(s_t.tag, []):
                top = c["top"]
                if abs(s_o.floor - top) <= 1:
                    dn = deck_nodes.get((s_t.name, top))
                    if dn:
                        add_edge(dn, s_o.name, "3dfloor", width,
                                 "deck top %d flush with %s floor" % (top, s_o.name))
    edges = list(edge_map.values())
    for e in edges:
        adj[e["a"]].append(e["b"])
        adj[e["b"]].append(e["a"])
    specs = getattr(b, "anchor_specs", [])
    start = getattr(b, "start_sector", None)
    anchors = []
    for role, sname, z, required in specs:
        s = b.by_name[sname]
        nid = None
        if sname in nodes and s.floor == z:
            nid = sname
        elif (sname, z) in deck_nodes:
            nid = deck_nodes[(sname, z)]
        if nid is None:
            raise ValueError("anchor %s: no node for %s at z=%s" % (role, sname, z))
        n = nodes[nid]
        anchors.append({"role": role, "node": nid, "sector": sname, "x": n["x"], "y": n["y"],
                        "z": int(z), "required": bool(required)})
    if start not in nodes:
        raise ValueError("start sector %s is not walkable" % start)
    seen = {start}
    q = deque([start])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in seen:
                seen.add(v); q.append(v)
    # cycle detection in the reachable component
    color = {}
    has_cycle = False
    def dfs(u, parent):
        nonlocal has_cycle
        color[u] = 1
        for v in adj[u]:
            if v == parent:
                continue
            if color.get(v, 0) == 1:
                has_cycle = True
            elif color.get(v, 0) == 0:
                dfs(v, u)
        color[u] = 2
    dfs(start, None)
    levels = sorted({nodes[n]["z"] for n in seen})
    graph = {
        "start": start,
        "nodes": [nodes[n] for n in sorted(nodes)],
        "edges": sorted(edges, key=lambda e: (e["a"], e["b"])),
        "anchors": anchors,
        "metrics": {
            "nodes": len(nodes), "edges": len(edges),
            "reachable_nodes": len(seen),
            "levels": levels,
            "vertical_span": (max(levels) - min(levels)) if levels else 0,
            "has_cycle": has_cycle,
            "unreachable_anchors": [a["role"] for a in anchors if a["required"] and a["node"] not in seen],
            "deck_nodes": sorted(deck_nodes.values()),
            "control_tags": {str(k): [c["top"] for c in v] for k, v in ctrl_by_tag.items()},
        },
    }
    return graph

def anchor_map(graph):
    return {a["role"]: a for a in graph["anchors"]}
