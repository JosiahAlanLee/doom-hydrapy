"""Six genuinely different Null Run room/floor archetypes.

Each builder follows the original Builder/routegraph convention: ordinary
walkable sectors are real collision floors, stairs are ordinary step sectors,
3D decks use isolated control sectors. No engine API is invented.
"""
import math
from . import roomkit as rk
from .roomkit import (add, rect, add_stairs, add_control, mapped, wedge,
                     WALL, WALL2, WALL3, FLOOR, FLOOR2, FLOOR3, WATER, VOID,
                     GLOW, GLASS, ALL_TEX, RISE)

# ---------------------------------------------------------------------------
# A. Oblique Switchback Quarry
# ---------------------------------------------------------------------------
def build_quarry(seed):
    b = rk.Builder("Oblique Switchback Quarry", ALL_TEX)
    entry_side = (seed % 5) % 3
    # rim arena (B), 1120 x 360 at 320
    add(b, "quarry.rim", rect(-560, 880, 560, 1240), 320, 832, FLOOR, VOID,
        175, "arena", tw=WALL, note="upper ritual shelf, 360 deep")
    # seal pair on the rim, same level, two north alcoves
    add(b, "quarry.rim.seal_w", rect(-480, 1240, -340, 1400), 320, 640, FLOOR2, VOID,
        185, "seal", tw=WALL2, note="rim seal west; 140 opening")
    add(b, "quarry.rim.seal_e", rect(340, 1240, 480, 1400), 320, 640, FLOOR2, VOID,
        185, "seal", tw=WALL2, note="rim seal east; 140 opening")
    # switchback descent rim -> shelf S (256)
    add_stairs(b, "quarry.st1", (-560, 720, -320, 880), 4, 320, axis="y",
               high_end="hi", tf=FLOOR2, tw=WALL, light=160)
    add(b, "quarry.shelf1", rect(-560, 400, 560, 720), 256, 768, FLOOR, VOID,
        160, "terrace", tw=WALL, note="long mid shelf")
    # S -> T (192), stair at the east end
    add_stairs(b, "quarry.st2", (320, 240, 560, 400), 4, 256, axis="y",
               high_end="hi", tf=FLOOR2, tw=WALL, light=160)
    add(b, "quarry.shelf2", rect(-560, -80, 560, 240), 192, 704, FLOOR, VOID,
        150, "terrace", tw=WALL)
    # T -> U (64), 8 steps at the west end
    add_stairs(b, "quarry.st3", (-560, -260, -320, -80), 8, 192, axis="y",
               high_end="hi", tf=FLOOR2, tw=WALL, light=150)
    add(b, "quarry.floor1", rect(-560, -560, 560, -260), 64, 576, FLOOR2, VOID,
        135, "terrace", tw=WALL)
    # U -> V (0), main 4-step stair at the east end
    add_stairs(b, "quarry.st4", (320, -720, 560, -560), 4, 64, axis="y",
               high_end="hi", tf=FLOOR2, tw=WALL, light=130)
    # quarry floor arena (A), 1200 x 400 at 0
    add(b, "quarry.floor2", rect(-560, -1120, 640, -720), 0, 512, FLOOR3, VOID,
        120, "arena", tw=WALL3, note="lower ritual floor, 400 deep")
    add(b, "quarry.floor2.seal_w", rect(-720, -1000, -560, -860), 0, 320, FLOOR3, VOID,
        150, "seal", tw=WALL3, note="pit seal west; 140 opening")
    add(b, "quarry.floor2.seal_e", rect(640, -1000, 800, -860), 0, 320, FLOOR3, VOID,
        150, "seal", tw=WALL3, note="pit seal east; 140 opening")
    # exit vestibule south of the floor
    add(b, "quarry.exit", rect(200, -1280, 440, -1120), 0, 512, FLOOR, VOID,
        140, "exit", tw=WALL, note="240-wide exit mouth")
    # vendor on shelf S east side
    add(b, "quarry.vendor", rect(560, 520, 780, 700), 256, 416, FLOOR2, VOID,
        200, "vendor", tw=WALL2, note="180 opening")
    # optional side chamber off shelf T east
    add(b, "quarry.optional", rect(560, 0, 800, 200), 192, 448, FLOOR2, VOID,
        190, "optional", tw=WALL3, note="240-wide optional side chamber")
    # west overlook route: N -> 4-step up -> overlook 384 -> gallery -> 8-step down -> S
    add_stairs(b, "quarry.ovst", (-720, 1040, -560, 1200), 4, 384, axis="x",
               high_end="lo", tf=FLOOR2, tw=WALL3, light=185)
    add(b, "quarry.overlook", rect(-880, 1040, -720, 1280), 384, 896, FLOOR, GLOW,
        195, "overlook", tw=GLASS, note="overlook balcony above the rim")
    add(b, "quarry.gallery", rect(-880, 592, -720, 1040), 384, 896, FLOOR, VOID,
        175, "gallery", tw=WALL3, note="long west high gallery, loop bypass")
    add_stairs(b, "quarry.gst", (-880, 400, -720, 592), 8, 384, axis="y",
               high_end="hi", tf=FLOOR2, tw=WALL3, light=170)
    add(b, "quarry.gland", rect(-880, 280, -560, 400), 256, 768, FLOOR, VOID,
        165, "landing", tw=WALL)
    add(b, "quarry.glink", rect(-700, 400, -560, 520), 256, 768, FLOOR, VOID,
        165, "link", tw=WALL, note="120 opening to shelf S")
    # entry dogleg, three variants; all start three sectors from the rim
    add(b, "quarry.entry.c1", rect(560, 880, 680, 1120), 320, 832, FLOOR2, VOID,
        180, "entry", tw=WALL2, note="chicane leg; 240 rim opening")
    add(b, "quarry.entry.c2", rect(680, 1000, 800, 1240), 320, 832, FLOOR2, VOID,
        180, "entry", tw=WALL2, note="chicane leg")
    if entry_side == 0:
        add(b, "quarry.entry", rect(680, 1240, 960, 1480), 320, 832, FLOOR2, VOID,
            190, "entry", tw=WALL2, note="north-east vestibule")
        start = "quarry.entry"
    elif entry_side == 1:
        add(b, "quarry.entry", rect(800, 1000, 1080, 1240), 320, 832, FLOOR2, VOID,
            190, "entry", tw=WALL2, note="east vestibule")
        start = "quarry.entry"
    else:
        add(b, "quarry.entry.c3", rect(680, 1240, 800, 1480), 320, 832, FLOOR2, VOID,
            180, "entry", tw=WALL2, note="chicane leg")
        add(b, "quarry.entry", rect(500, 1280, 680, 1520), 320, 832, FLOOR2, VOID,
            190, "entry", tw=WALL2, note="north vestibule")
        start = "quarry.entry"
    # rotate the whole plan: oblique silhouette
    rk.rotate_builder(b, (seed * 17) % 360)
    b.debug["landmark"] = "quarry.floor2"
    b.start_sector = start
    b.anchor_specs = [
        ("entry", start, 320, True),
        ("exit", "quarry.exit", 0, True),
        ("vendor", "quarry.vendor", 256, True),
        ("encounter_a", "quarry.floor2", 0, True),
        ("encounter_b", "quarry.rim", 320, True),
        ("seal_a", "quarry.floor2.seal_w", 0, True),
        ("seal_b", "quarry.floor2.seal_e", 0, True),
        ("seal_c", "quarry.rim.seal_w", 320, True),
        ("seal_d", "quarry.rim.seal_e", 320, True),
        ("overlook", "quarry.overlook", 384, True),
        ("pit_recovery", "quarry.floor2", 0, True),
        ("optional_reward", "quarry.optional", 192, False),
    ]
    b.debug["levels"] = [0, 64, 192, 256, 320, 384]
    b.debug["entry_variant"] = entry_side
    b.debug["route_note"] = ("Altar rim -> four switchback flights down the quarry cut -> "
                             "floor; a west high gallery loops rim to shelf S, and the "
                             "floor stair is the pit recovery.")
    b.finish()
    return b

BUILDERS = {"oblique-switchback-quarry": build_quarry}

# ---------------------------------------------------------------------------
# B. Radial Negative Cathedral
# ---------------------------------------------------------------------------
def _oct_points(r, phase=22.5):
    return [(round(r * math.cos(math.radians(phase + 45 * i))),
             round(r * math.sin(math.radians(phase + 45 * i)))) for i in range(8)]

def build_cathedral(seed):
    b = rk.Builder("Radial Negative Cathedral", ALL_TEX)
    P_IN = _oct_points(240)
    P_NAVE = _oct_points(700)
    P_GAL = _oct_points(900)
    # choose two non-adjacent chapel octants and one free entry octant
    base_oct = (seed // 3) % 8
    c1 = base_oct
    c2 = (base_oct + 2) % 8          # chapels two octants apart, never adjacent
    entry_oct = (base_oct + 1) % 8   # fills the contiguous non-gallery block
    chapels = {c1, c2}
    gal_octs = [i for i in range(8) if i not in chapels and i != entry_oct]
    # central negative centre: visual abyss, never a path
    add(b, "cath.void", P_IN, -256, 512, WATER, VOID, 70, "decor", walk=False,
        tw=WALL3, note="negative centre; visual abyss, not a route or collision path")
    # nave ring, eight simple octagon wedges at 0
    for i in range(8):
        add(b, "cath.nave.%d" % i,
            rk.wedge(0, 0, 240, 700, 22.5 + 45 * i, 67.5 + 45 * i, step=45),
            0, 512, FLOOR2, VOID, 150, "nave", tw=WALL, note="processional octant")
    # radial chapels: free-standing halls outside the nave, seal pairs on the outer wall
    chapel_attach = {}
    for ci, cn in ((c1, "a"), (c2, "b")):
        A, B = P_NAVE[ci], P_NAVE[(ci + 1) % 8]
        nx, ny = rk.outward(A, B, (0, 0))
        depth = 360
        C = (B[0] + round(nx * depth), B[1] + round(ny * depth))
        D = (A[0] + round(nx * depth), A[1] + round(ny * depth))
        poly = [A, B, C, D]
        add(b, "cath.chapel.%s" % cn, poly, 0, 512, FLOOR2, VOID, 170, "arena",
            tw=WALL2, note="ritual chapel, 536x360 clear")
        if cn == "a":
            s1, _ = rk.out_rect(C, D, 0.10, 0.30, 180, away=rk.centroid(poly))
            s2, _ = rk.out_rect(C, D, 0.70, 0.90, 180, away=rk.centroid(poly))
        else:
            s1, _ = rk.out_rect(C, D, 0.05, 0.25, 180, away=rk.centroid(poly))
            s2, _ = rk.out_rect(C, D, 0.55, 0.75, 180, away=rk.centroid(poly))
        add(b, "cath.chapel.%s.seal1" % cn, s1, 0, 320, FLOOR, VOID, 195,
            "seal", tw=WALL3, note="118 opening, chapel floor")
        add(b, "cath.chapel.%s.seal2" % cn, s2, 0, 320, FLOOR, VOID, 195,
            "seal", tw=WALL3, note="118 opening, chapel floor")
        chapel_attach[cn] = (C, D, poly)
    # vendor on chapel a outer wall; crypt stair and exit on chapel b outer wall
    C, D, poly = chapel_attach["a"]
    v, _ = rk.out_rect(C, D, 0.38, 0.62, 190, away=rk.centroid(poly))
    add(b, "cath.vendor", v, 0, 320, FLOOR2, VOID, 200, "vendor", tw=WALL2,
        note="107 opening, chapel level")
    C, D, poly = chapel_attach["b"]
    cr, (a0, bb0, dvec) = rk.out_rect(C, D, 0.30, 0.52, 160, away=rk.centroid(poly))
    add(b, "cath.crypt.head", cr, 0, 320, FLOOR2, VOID, 150, "hall", tw=WALL3,
        note="head of the crypt stair, 150 opening")
    # crypt flight descends further outward from the chapel head
    ex, ey = bb0[0] - a0[0], bb0[1] - a0[1]
    L = math.hypot(ex, ey) or 1.0
    ux, uy = ex / L, ey / L
    nx2, ny2 = dvec[0] / 160.0, dvec[1] / 160.0
    def at(pt, d, e=0.0):
        return (round(pt[0] + ux * e + nx2 * d), round(pt[1] + uy * e + ny2 * d))
    for k in range(16):
        d0 = 160 + 352 * k / 16
        d1 = 160 + 352 * (k + 1) / 16
        z = -16 * (k + 1)
        quad = [at(a0, d0), at(bb0, d0), at(bb0, d1), at(a0, d1)]
        add(b, "cath.crypt.st%02d" % k, quad, z, z + 512, FLOOR2, VOID,
            120 + k, "stair", tw=WALL3, note="crypt flight rise 16")
    mid = ((a0[0] + bb0[0]) / 2.0, (a0[1] + bb0[1]) / 2.0)
    hall = [at(mid, 512, -150), at(mid, 512, 150), at(mid, 812, 150), at(mid, 812, -150)]
    add(b, "cath.crypt", hall, -256, 256, FLOOR3, VOID, 95, "pit", tw=WALL3,
        note="lower crypt, recovery via the 16-step flight")
    # exit on chapel b outer wall
    e, _ = rk.out_rect(C, D, 0.79, 0.99, 260, away=rk.centroid(poly))
    add(b, "cath.exit", e, 0, 400, FLOOR, VOID, 150, "exit", tw=WALL,
        note="exit apse, chapel level")
    # gallery band: flats at 256, two tangential stairs, all on octagon chords
    stair_pick = []
    for i in gal_octs:
        if len(stair_pick) == 2:
            break
        if ((i + 1) % 8 in gal_octs and (i + 1) % 8 not in stair_pick) or \
           ((i - 1) % 8 in gal_octs and (i - 1) % 8 not in stair_pick):
            if i not in stair_pick:
                stair_pick.append(i)
    while len(stair_pick) < 2:
        for i in gal_octs:
            if i not in stair_pick:
                stair_pick.append(i)
                break
    flats = [i for i in gal_octs if i not in stair_pick]
    for i in flats:
        add(b, "cath.gal.%d" % i, rk.wedge(0, 0, 700, 900,
            22.5 + 45 * i, 67.5 + 45 * i, step=45),
            256, 768, FLOOR, VOID, 180, "gallery", tw=WALL,
            note="high processional gallery, 200 deep")
    for gi, i in enumerate(stair_pick):
        if (i + 1) % 8 in flats:
            d = 1
        elif (i - 1) % 8 in flats:
            d = -1
        else:
            d = 1
        base = 22.5 + 45 * i
        def rp(r, a):
            return (round(r * math.cos(math.radians(a))),
                    round(r * math.sin(math.radians(a))))
        # step angular boundaries; first step is widened to 8 degrees
        if d == 1:
            slices = [(base, base + 8)]
            rest0 = base + 8
            for k in range(15):
                slices.append((rest0 + 37.0 * k / 15, rest0 + 37.0 * (k + 1) / 15))
        else:
            slices = [(base + 37, base + 45)]
            for k in range(15):
                slices.append((base + 37.0 * (15 - k) / 15,
                               base + 37.0 * (14 - k) / 15))
        # landing band 700..800, outer boundary follows every step inner chord
        bounds = sorted({round(a, 6) for a, b in slices for a in (a, b)})
        outer = [rp(800, a) for a in bounds]
        land = [rp(700, base), rp(700, base + 45)] + list(reversed(outer))
        add(b, "cath.gs%d.land" % gi, land, 0, 512, FLOOR, VOID, 165, "hall",
            tw=WALL, note="gallery stair foot, full chord to the nave")
        for k, (aa, ab) in enumerate(slices):
            z = 16 * (k + 1)
            quad = [rp(800, aa), rp(900, aa), rp(900, ab), rp(800, ab)]
            add(b, "cath.gs%d.%02d" % (gi, k), quad, z, z + 512, FLOOR2, VOID,
                160 + k, "stair", tw=WALL2, note="gallery stair rise 16")
    ov = flats[seed % len(flats)]
    opt_cands = [i for i in flats if i != ov] or [ov]
    opt = opt_cands[seed % len(opt_cands)]
    A, B = P_GAL[opt], P_GAL[(opt + 1) % 8]
    o, _ = rk.out_rect(A, B, 0.36, 0.64, 190, away=(0, 0))
    add(b, "cath.optional", o, 256, 448, FLOOR2, GLOW, 205, "optional", tw=GLASS,
        note="cabinet of relics, optional high alcove")
    # entry on the free octant: a straight outward approach, no adjacent-octant overlap
    A, B = P_NAVE[entry_oct], P_NAVE[(entry_oct + 1) % 8]
    leg1p, (a, bb, dvec) = rk.out_rect(A, B, 0.30, 0.70, 250, away=(0, 0))
    add(b, "cath.entry.leg1", leg1p, 0, 512, FLOOR2, VOID, 175, "entry", tw=WALL2,
        note="entry leg, 215 opening from the nave")
    q0 = (a[0] + dvec[0], a[1] + dvec[1])
    q1 = (bb[0] + dvec[0], bb[1] + dvec[1])
    leg2p, _ = rk.out_rect(q0, q1, 0.12, 0.88, 220, away=(0, 0))
    add(b, "cath.entry", leg2p, 0, 512, FLOOR2, VOID, 190, "entry", tw=WALL2,
        note="outer vestibule at the end of the entry leg")
    rk.rotate_builder(b, (seed * 23) % 360)
    b.debug["landmark"] = "cath.void"
    b.start_sector = "cath.entry"
    b.anchor_specs = [
        ("entry", "cath.entry", 0, True),
        ("exit", "cath.exit", 0, True),
        ("vendor", "cath.vendor", 0, True),
        ("encounter_a", "cath.chapel.a", 0, True),
        ("encounter_b", "cath.chapel.b", 0, True),
        ("seal_a", "cath.chapel.a.seal1", 0, True),
        ("seal_b", "cath.chapel.a.seal2", 0, True),
        ("seal_c", "cath.chapel.b.seal1", 0, True),
        ("seal_d", "cath.chapel.b.seal2", 0, True),
        ("overlook", "cath.gal.%d" % ov, 256, True),
        ("pit_recovery", "cath.crypt", -256, True),
        ("optional_reward", "cath.optional", 256, False),
    ]
    b.debug["levels"] = [-256, 0, 256]
    b.debug["chapels"] = sorted(chapels)
    b.debug["entry_oct"] = entry_oct
    b.debug["gallery_flats"] = flats
    b.debug["gallery_stairs"] = stair_pick
    b.debug["route_note"] = ("Octagonal nave ring around a non-traversable negative centre; "
                             "two radial chapels hold the seal pairs, two tangential gallery "
                             "stairs climb to the high ring, and a crypt flight recovers from the "
                             "lower ritual pit.")
    b.finish()
    return b

BUILDERS["radial-negative-cathedral"] = build_cathedral

# ---------------------------------------------------------------------------
# C. Amphitheatre Pump Organ
# ---------------------------------------------------------------------------
def build_amphitheatre(seed):
    b = rk.Builder("Amphitheatre Pump Organ", ALL_TEX)
    # orchestra half-disc at 0 plus deep stage box
    disc = [(200, 0)] + rk.arc(0, 0, 200, 0, 180, 30)[1:]
    add(b, "amp.orchestra", disc, 0, 512, FLOOR2, VOID, 150, "arena", tw=WALL2,
        note="orchestra half-disc")
    add(b, "amp.lip", rk.wedge(0, 0, 200, 300, 0, 180, step=30), 0, 512,
        FLOOR2, VOID, 155, "orchestra", tw=WALL2,
        note="flat orchestra lip; keeps the first terrace tread readable")
    add(b, "amp.stage", rect(-200, -500, 200, 0), 0, 512, FLOOR3, VOID, 145, "arena",
        tw=WALL3, note="stage box, 600x500 clear")
    # 16 concentric seating rings, each a single half-annulus at +16
    for i in range(16):
        r0, r1 = 300 + 50 * i, 350 + 50 * i
        z = 16 * (i + 1)
        add(b, "amp.ring.%02d" % i, rk.wedge(0, 0, r0, r1, 0, 180, step=30),
            z, z + 512, FLOOR, VOID, 120 + i, "terrace", tw=WALL,
            note="seating terrace, rise 16")
    add(b, "amp.top", rk.wedge(0, 0, 1100, 1400, 0, 180, step=30),
        256, 768, FLOOR, VOID, 185, "plaza", tw=WALL, note="top plaza, overlook")
    # east ritual annex (arena B) on the flat east edge, same 256 level
    add(b, "amp.annex", rect(1100, -340, 1440, 0), 256, 640, FLOOR2, VOID, 180,
        "arena", tw=WALL2, note="ritual terrace, 300x340 clear")
    for k, (y0, y1) in enumerate([(-320, -180), (-160, -20)]):
        add(b, "amp.annex.seal%d" % k, rect(1440, y0, 1580, y1), 256, 480,
            FLOOR, VOID, 195, "seal", tw=WALL3, note="140 opening, plaza level")
    # stage seal pair, same 0 level
    add(b, "amp.stage.sealw", rect(-360, -280, -200, -140), 0, 300, FLOOR2, VOID,
        195, "seal", tw=WALL3, note="140 opening, stage level")
    add(b, "amp.stage.seale", rect(200, -280, 360, -140), 0, 300, FLOOR2, VOID,
        195, "seal", tw=WALL3, note="140 opening, stage level")
    # vendor and exit on the stage box
    add(b, "amp.vendor", rect(200, -460, 360, -340), 0, 300, FLOOR, VOID, 200,
        "vendor", tw=WALL2, note="120 opening")
    add(b, "amp.exit", rect(-120, -720, 120, -500), 0, 400, FLOOR, VOID, 150,
        "exit", tw=WALL, note="240 exit mouth")
    # west bypass: long stair from top plaza to a low west corridor to the stage
    add_stairs(b, "amp.bst", (-1400, -320, -1200, 0), 16, 256, axis="y",
               high_end="hi", tf=FLOOR2, tw=WALL, light=150)
    add(b, "amp.bcor1", rect(-1400, -500, -1200, -320), 0, 512, FLOOR2, VOID, 120,
        "walkway", tw=WALL, note="low west bypass")
    add(b, "amp.bcor2", rect(-1200, -500, -200, -360), 0, 512, FLOOR2, VOID, 120,
        "walkway", tw=WALL, note="bypass link to the stage box")
    # entry corridor outside a chord of the outer plaza arc
    entry_variant = (seed % 11) % 3
    segs = [(30, 60), (60, 90), (90, 120)]
    ea0, ea1 = segs[entry_variant]
    outer = rk.arc(0, 0, 1400, ea0, ea1, 30)
    cor, (a, bb, dv) = rk.out_rect(outer[0], outer[1], 0.25, 0.75, 250, away=(0, 0))
    add(b, "amp.entry.cor", cor, 256, 768, FLOOR2, VOID, 180, "entry", tw=WALL2,
        note="215 opening from the top plaza")
    q0 = (a[0] + dv[0], a[1] + dv[1]); q1 = (bb[0] + dv[0], bb[1] + dv[1])
    vest, _ = rk.out_rect(q0, q1, 0.15, 0.85, 220, away=(0, 0))
    add(b, "amp.entry", vest, 256, 768, FLOOR2, VOID, 190, "entry", tw=WALL2,
        note="outer vestibule; start faces the fan")
    # optional relic alcove on the outer plaza arc
    optpts = rk.arc(0, 0, 1400, 120, 150, 30)
    o, _ = rk.out_rect(optpts[0], optpts[1], 0.30, 0.70, 200, away=(0, 0))
    add(b, "amp.optional", o, 256, 448, FLOOR2, GLOW, 205, "optional", tw=GLASS,
        note="organ loft relic alcove, optional")
    # decorative pump pipes outside the fan; never walkable, never a path
    for k, ang in enumerate((20, 40, 160, 170)):
        c = (round(2100 * math.cos(math.radians(ang))), round(2100 * math.sin(math.radians(ang))))
        poly = [(c[0] - 30, c[1] - 30), (c[0] + 30, c[1] - 30), (c[0] + 30, c[1] + 30), (c[0] - 30, c[1] + 30)]
        add(b, "amp.pipe%d" % k, poly, 256, 1024, WALL3, VOID, 90, "decor", walk=False,
            tw=WALL3, note="solid organ pipe, decorative only")
    if seed % 2:
        rk.rotate_builder(b, 180)
    b.debug["landmark"] = "amp.pipe2"
    b.start_sector = "amp.entry"
    b.anchor_specs = [
        ("entry", "amp.entry", 256, True),
        ("exit", "amp.exit", 0, True),
        ("vendor", "amp.vendor", 0, True),
        ("encounter_a", "amp.stage", 0, True),
        ("encounter_b", "amp.annex", 256, True),
        ("seal_a", "amp.stage.sealw", 0, True),
        ("seal_b", "amp.stage.seale", 0, True),
        ("seal_c", "amp.annex.seal0", 256, True),
        ("seal_d", "amp.annex.seal1", 256, True),
        ("overlook", "amp.top", 256, True),
        ("pit_recovery", "amp.stage", 0, True),
        ("optional_reward", "amp.optional", 256, False),
    ]
    b.debug["levels"] = [0, 256]
    b.debug["entry_variant"] = entry_variant
    b.debug["route_note"] = ("Stage bowl -> sixteen concentric seating rings -> top plaza; "
                             "a long west bypass stair loops from the top back to the stage, "
                             "and the east ritual terrace holds the second seal pair.")
    b.finish()
    return b

BUILDERS["amphitheatre-pump-organ"] = build_amphitheatre

# ---------------------------------------------------------------------------
# D. Split-Level Transit Hall (two real 3D bridge decks)
# ---------------------------------------------------------------------------
def build_transit(seed):
    b = rk.Builder("Split-Level Transit Hall", ALL_TEX)
    # north platform split around a trench-recovery notch
    add(b, "tr.north.w", rect(-900, 60, -170, 380), 0, 512, FLOOR2, VOID, 145, "platform", tw=WALL)
    add(b, "tr.north.e", rect(170, 60, 900, 380), 0, 512, FLOOR2, VOID, 145, "platform", tw=WALL)
    add(b, "tr.north.strip", rect(-170, 240, 170, 380), 0, 512, FLOOR2, VOID, 140, "platform", tw=WALL)
    add(b, "tr.south", rect(-900, -300, 900, -60), 0, 512, FLOOR2, VOID, 140, "platform", tw=WALL)
    add(b, "tr.west", rect(-1000, -300, -900, 380), 0, 512, FLOOR, VOID, 130, "plaza", tw=WALL)
    add(b, "tr.east", rect(900, -360, 1300, 380), 0, 512, FLOOR3, VOID, 155, "arena", tw=WALL3,
        note="east concourse arena, 400x740 clear")
    # continuous sunken track bed at -120; notch stair is its reliable recovery
    add(b, "tr.trench", rect(-900, -60, 900, 60), -120, 392, WATER, VOID, 100, "track",
        tw=WALL, note="continuous sunken track bed")
    add_stairs(b, "tr.recover", (-150, 60, 150, 240), 8, 0, rise=15, axis="y",
               high_end="hi", tf=FLOOR2, tw=WALL, light=135)
    # alternating side mezzanines at 96 and 192
    mezz = [
        ("tr.mezz.nw", (-800, 512, -200, 792), 96, (-800, 380, -640, 512), "hi", 6),
        ("tr.mezz.ne", (200, 644, 800, 924), 192, (200, 380, 360, 644), "hi", 12),
        ("tr.mezz.sw", (-800, -712, -200, -432), 96, (-800, -432, -640, -300), "lo", 6),
        ("tr.mezz.se", (200, -924, 800, -564), 192, (200, -564, 360, -300), "lo", 12),
    ]
    for name, box, z, sb, he, n in mezz:
        add(b, name, rect(*box), z, z + 384, FLOOR, VOID, 165, "mezzanine", tw=WALL,
            note="split-level side mezzanine")
        add_stairs(b, name + ".st", sb, n, z, axis="y", high_end=he,
                   tf=FLOOR2, tw=WALL, light=150)
    arena_b = "tr.mezz.ne" if ((seed // 11) % 2 == 0) else "tr.mezz.se"
    other_high = "tr.mezz.se" if arena_b == "tr.mezz.ne" else "tr.mezz.ne"
    ab = b.by_name[arena_b].poly
    xs = [p[0] for p in ab]; ys = [p[1] for p in ab]
    y_out = max(ys) if ys[0] > 0 else min(ys)
    sgn = 1 if y_out > 0 else -1
    x_lo, x_hi = min(xs), max(xs)
    for k, (x0, x1) in enumerate([(x_lo + 110, x_lo + 250), (x_hi - 250, x_hi - 110)]):
        yy0, yy1 = sorted((y_out, y_out + sgn * 140))
        add(b, "tr.arenaB.seal%d" % k, rect(x0, yy0, x1, yy1), 192, 512, FLOOR2, VOID,
            195, "seal", tw=WALL3, note="140 opening at mezzanine level")
    add(b, "tr.arenaA.sealn", rect(1050, 380, 1250, 520), 0, 300, FLOOR, VOID, 195,
        "seal", tw=WALL3, note="200 opening")
    add(b, "tr.arenaA.seals", rect(1050, -500, 1250, -360), 0, 300, FLOOR, VOID, 195,
        "seal", tw=WALL3, note="200 opening")
    add(b, "tr.vendor", rect(-150, 380, 150, 540), 0, 300, FLOOR2, VOID, 200,
        "vendor", tw=WALL2, note="300-wide concourse kiosk")
    ob = b.by_name[other_high].poly
    oxs = [p[0] for p in ob]; oys = [p[1] for p in ob]
    oy = max(oys) if oys[0] > 0 else min(oys)
    sy = 1 if oy > 0 else -1
    add(b, "tr.optional", rect(min(oxs) + 100, min(oy, oy + sy * 200),
                              min(oxs) + 300, max(oy, oy + sy * 200)), 192, 448,
        FLOOR2, GLOW, 200, "optional", tw=GLASS, note="left-luggage room, optional")
    add(b, "tr.exit", rect(1300, -100, 1560, 100), 0, 400, FLOOR, VOID, 150,
        "exit", tw=WALL, note="200 exit mouth")
    if ((seed // 5) % 2 == 0):
        add(b, "tr.entry.cor", rect(-800, 792, -660, 992), 96, 480, FLOOR2, VOID, 175,
            "entry", tw=WALL2, note="140 mezzanine opening")
        add(b, "tr.entry", rect(-1000, 992, -660, 1232), 96, 480, FLOOR2, VOID, 190,
            "entry", tw=WALL2, note="north-west vestibule")
    else:
        add(b, "tr.entry.cor", rect(-800, -912, -660, -712), 96, 480, FLOOR2, VOID, 175,
            "entry", tw=WALL2, note="140 mezzanine opening")
        add(b, "tr.entry", rect(-1000, -1152, -660, -912), 96, 480, FLOOR2, VOID, 190,
            "entry", tw=WALL2, note="south-west vestibule")
    rk.rotate_builder(b, (seed * 17) % 360)
    b.debug["landmark"] = "tr.east"
    b.start_sector = "tr.entry"
    b.anchor_specs = [
        ("entry", "tr.entry", 96, True),
        ("exit", "tr.exit", 0, True),
        ("vendor", "tr.vendor", 0, True),
        ("encounter_a", "tr.east", 0, True),
        ("encounter_b", arena_b, 192, True),
        ("seal_a", "tr.arenaA.sealn", 0, True),
        ("seal_b", "tr.arenaA.seals", 0, True),
        ("seal_c", "tr.arenaB.seal0", 192, True),
        ("seal_d", "tr.arenaB.seal1", 192, True),
        ("overlook", other_high, 192, True),
        ("pit_recovery", "tr.trench", -120, True),
        ("optional_reward", "tr.optional", 192, False),
    ]
    b.debug["levels"] = [-120, 0, 96, 192]
    b.debug["arena_b"] = arena_b
    b.debug["route_note"] = ("North and south platforms loop the continuous sunken track; "
                             "a notched 15-rise stair recovers from the bed, and alternating "
                             "96/192 mezzanines split the hall sides.")
    b.finish()
    return b

BUILDERS["split-level-transit-hall"] = build_transit
