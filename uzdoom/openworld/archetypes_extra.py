"""Two new Null Run archetypes: ossuary conservatory and inhabited archive."""
import math
from . import roomkit_extra as rk
from .roomkit_extra import (add, rect, add_stairs, WALL, WALL2, WALL3, FLOOR,
                     FLOOR2, FLOOR3, WATER, VOID, GLOW, GLASS, ALL_TEX)

def build_ossuary(seed):
    b = rk.Builder("Asymmetrical Ossuary Conservatory", ALL_TEX)
    # hub, arena annex, north library, south conservatory pit
    add(b, "oss.hub", rect(-300, -200, 300, 200), 0, 512, FLOOR2, VOID, 150, "hall", tw=WALL)
    add(b, "oss.arenaA", rect(300, -170, 700, 170), 0, 512, FLOOR3, VOID, 160, "arena",
        tw=WALL3, note="ritual ossuary, 400x340 clear")
    add(b, "oss.arenaA.seal1", rect(700, -160, 760, -20), 0, 320, FLOOR, VOID, 195,
        "seal", tw=WALL3, note="140 opening, same level")
    add(b, "oss.arenaA.seal2", rect(700, 20, 760, 160), 0, 320, FLOOR, VOID, 195,
        "seal", tw=WALL3, note="140 opening, same level")
    add(b, "oss.library", rect(-200, 500, 200, 900), 96, 608, FLOOR, VOID, 170, "arena",
        tw=WALL, note="bone library, 400x400 clear")
    add(b, "oss.library.seal1", rect(-340, 540, -200, 680), 96, 416, FLOOR2, VOID, 195,
        "seal", tw=WALL3, note="140 opening, library level")
    add(b, "oss.library.seal2", rect(-340, 720, -200, 860), 96, 416, FLOOR2, VOID, 195,
        "seal", tw=WALL3, note="140 opening, library level")
    add(b, "oss.crypt", rect(-200, -720, 200, -376), -128, 384, FLOOR3, VOID, 95, "pit",
        tw=WALL3, note="lower conservatory; recovery stair to the hub")
    # hub -> library, hub -> crypt
    add_stairs(b, "oss.st.lib", (-100, 200, 100, 500), 6, 96, axis="y", high_end="hi",
               tf=FLOOR2, tw=WALL, light=160)
    add_stairs(b, "oss.st.crypt", (-100, -376, 100, -200), 8, 0, axis="y",
               high_end="hi", tf=FLOOR2, tw=WALL3, light=110)
    # east conservatory wing and exit
    add(b, "oss.exit", rect(-100, -920, 100, -720), -128, 256, FLOOR, VOID, 110,
        "exit", tw=WALL, note="200 exit mouth at crypt level")
    # vendor, entry dogleg, tower/overlook
    add(b, "oss.vendor", rect(-460, 80, -300, 220), 0, 300, FLOOR2, VOID, 200,
        "vendor", tw=WALL2, note="140 opening")
    add(b, "oss.entry.cor", rect(-450, -80, -300, 80), 0, 512, FLOOR2, VOID, 175,
        "entry", tw=WALL2, note="160 hub opening")
    add(b, "oss.entry", rect(-650, -220, -450, 60), 0, 512, FLOOR2, VOID, 190,
        "entry", tw=WALL2, note="outer vestibule")
    add_stairs(b, "oss.st.tower", (-100, 900, 100, 1194), 14, 320, axis="y",
               high_end="hi", tf=FLOOR2, tw=WALL, light=180)
    add(b, "oss.tower", rect(-170, 1194, 170, 1534), 320, 832, FLOOR, GLOW, 195,
        "overlook", tw=GLASS, note="overlook tower")
    add(b, "oss.optional", rect(-340, 1314, -170, 1454), 320, 512, FLOOR2, VOID, 205,
        "optional", tw=WALL3, note="reliquary, optional")
    # high cloister loop: library -> upper -> vertical -> down stair -> crypt
    add(b, "oss.cloister.up", rect(200, 700, 900, 820), 96, 608, FLOOR2, VOID, 170,
        "gallery", tw=WALL, note="120 opening from the library")
    add(b, "oss.cloister.v", rect(780, 60, 900, 700), 96, 608, FLOOR2, VOID, 165,
        "gallery", tw=WALL, note="high spine")
    add_stairs(b, "oss.st.cloister", (780, -248, 900, 60), 14, 96, axis="y",
               high_end="hi", tf=FLOOR2, tw=WALL3, light=140)
    add(b, "oss.cloister.land", rect(780, -496, 900, -248), -128, 384, FLOOR, VOID, 110,
        "landing", tw=WALL3)
    add(b, "oss.cloister.low", rect(200, -496, 780, -376), -128, 384, FLOOR2, VOID, 110,
        "link", tw=WALL3, note="120 opening to the crypt")
    # seeded optional branch A: a bypass from library straight to the high spine
    branch_a = (seed % 3 == 2)
    if branch_a:
        add(b, "oss.bypass.room", rect(200, 560, 400, 660), 96, 608, FLOOR2, VOID, 175,
            "optional", tw=WALL2, note="seeded bypass room")
        add(b, "oss.bypass.link", rect(400, 560, 780, 660), 96, 608, FLOOR2, VOID, 175,
            "optional", tw=WALL2, note="seeded bypass link; changes graph adjacency")
    branch_b = (seed % 7 == 1)
    if branch_b:
        add(b, "oss.optional.side", rect(120, 200, 260, 360), 0, 320, FLOOR2, VOID, 190,
            "optional", tw=WALL3, note="seeded optional side chamber")
    b._reconcile()
    rk.rotate_builder(b, (seed * 17) % 360)
    b.debug["landmark"] = "oss.tower"
    b.start_sector = "oss.entry"
    opt = "oss.optional.side" if branch_b else "oss.optional"
    b.anchor_specs = [
        ("entry", "oss.entry", 0, True), ("exit", "oss.exit", -128, True),
        ("vendor", "oss.vendor", 0, True),
        ("encounter_a", "oss.arenaA", 0, True), ("encounter_b", "oss.library", 96, True),
        ("seal_a", "oss.arenaA.seal1", 0, True), ("seal_b", "oss.arenaA.seal2", 0, True),
        ("seal_c", "oss.library.seal1", 96, True), ("seal_d", "oss.library.seal2", 96, True),
        ("overlook", "oss.tower", 320, True), ("pit_recovery", "oss.crypt", -128, True),
        ("optional_reward", opt, 320 if not branch_b else 0, False),
    ]
    b.debug["levels"] = [-128, 0, 96, 320]
    b.debug["bypass_A"] = branch_a
    b.debug["branch_B"] = branch_b
    b.debug["route_note"] = ("Hub -> bone library -> high cloister spine -> crypt -> hub; "
                             "tower stair rises to the overlook. Even seeds add a B-to-spine "
                             "bypass; seeds with seed%7==1 add an optional side chamber.")
    b.finish()
    return b

def build_archive(seed):
    b = rk.Builder("Inhabited Archive", ALL_TEX)
    # square-spiral stack carousel: west 0, north 96, east 192, south 96
    add(b, "arc.g0", rect(-800, -400, -400, 400), 0, 512, FLOOR, VOID, 135, "gallery",
        tw=WALL, note="west stack gallery, 400x800")
    add(b, "arc.g1", rect(-400, 400, 400, 800), 96, 608, FLOOR2, VOID, 160, "arena",
        tw=WALL2, note="north stack gallery, 800x400 clear")
    add(b, "arc.g2", rect(400, -400, 800, 400), 192, 704, FLOOR3, VOID, 165, "arena",
        tw=WALL3, note="east stack gallery, 400x800 clear")
    add(b, "arc.g3", rect(-400, -800, 400, -400), 96, 608, FLOOR2, VOID, 155, "gallery",
        tw=WALL2, note="south stack gallery")
    add(b, "arc.core", rect(-400, -400, 400, 400), -96, 512, WALL3, VOID, 70, "decor",
        walk=False, tw=WALL3, note="inhabited central stack void; never a path")
    # corner landings and 6-step stairs
    add(b, "arc.l1", rect(-800, 532, -400, 800), 96, 608, FLOOR, VOID, 155, "landing", tw=WALL)
    add_stairs(b, "arc.s1", (-760, 400, -560, 532), 6, 96, axis="y", high_end="hi",
               tf=FLOOR2, tw=WALL, light=150)
    add(b, "arc.l2", rect(532, 400, 800, 800), 192, 704, FLOOR, VOID, 165, "landing", tw=WALL)
    add_stairs(b, "arc.s2", (400, 600, 532, 760), 6, 192, axis="x", high_end="hi",
               tf=FLOOR2, tw=WALL, light=160)
    add(b, "arc.l3", rect(400, -800, 800, -532), 96, 608, FLOOR, VOID, 155, "landing", tw=WALL)
    add_stairs(b, "arc.s3", (560, -532, 720, -400), 6, 192, axis="y", high_end="hi",
               tf=FLOOR2, tw=WALL, light=145)
    add(b, "arc.l4", rect(-800, -800, -400, -532), 96, 608, FLOOR, VOID, 150, "landing", tw=WALL)
    add_stairs(b, "arc.s4", (-760, -532, -560, -400), 6, 96, axis="y", high_end="lo",
               tf=FLOOR2, tw=WALL, light=145)
    # seals: north and east arenas, pairs on one level
    add(b, "arc.g1.seal1", rect(-300, 800, -160, 940), 96, 416, FLOOR2, VOID, 195,
        "seal", tw=WALL3, note="140 opening, north gallery level")
    add(b, "arc.g1.seal2", rect(160, 800, 300, 940), 96, 416, FLOOR2, VOID, 195,
        "seal", tw=WALL3, note="140 opening, north gallery level")
    add(b, "arc.g2.seal1", rect(800, -300, 940, -160), 192, 512, FLOOR, VOID, 195,
        "seal", tw=WALL3, note="140 opening, east gallery level")
    add(b, "arc.g2.seal2", rect(800, 160, 940, 300), 192, 512, FLOOR, VOID, 195,
        "seal", tw=WALL3, note="140 opening, east gallery level")
    # pit sub-archive and exit
    add_stairs(b, "arc.st.pit", (-932, -300, -800, -160), 6, 0, axis="x", high_end="hi",
               tf=FLOOR2, tw=WALL3, light=90)
    add(b, "arc.sub", rect(-1272, -400, -932, -120), -96, 320, FLOOR3, VOID, 85, "pit",
        tw=WALL3, note="sub-archive, recovery stair")
    add(b, "arc.exit", rect(-1472, -360, -1272, -140), -96, 256, FLOOR, VOID, 100,
        "exit", tw=WALL, note="220 exit mouth")
    # tower overlook
    add_stairs(b, "arc.st.tower", (800, -80, 976, 80), 8, 320, axis="x", high_end="hi",
               tf=FLOOR2, tw=WALL, light=180)
    add(b, "arc.tower", rect(976, -170, 1316, 170), 320, 832, FLOOR, GLOW, 195,
        "overlook", tw=GLASS, note="stack catwalk tower")
    # entry, vendor, optional fallback room
    add(b, "arc.entry.cor", rect(-920, 140, -800, 300), 0, 512, FLOOR2, VOID, 175,
        "entry", tw=WALL2, note="160 opening")
    add(b, "arc.entry", rect(-1120, 160, -920, 400), 0, 512, FLOOR2, VOID, 190,
        "entry", tw=WALL2, note="outer vestibule")
    add(b, "arc.vendor", rect(-960, -80, -800, 60), 0, 300, FLOOR2, VOID, 200,
        "vendor", tw=WALL2, note="140 opening")
    add(b, "arc.optional", rect(-500, 400, -400, 500), 0, 300, FLOOR2, VOID, 195,
        "optional", tw=WALL3, note="restricted-stack room, optional")
    # seeded optional branches: A off north gallery (even), B off south (seed%7==1)
    branch_a = (seed % 3 == 2)
    branch_b = (seed % 7 == 1)
    if branch_a:
        add(b, "arc.sideA", rect(-100, 800, 100, 1000), 96, 608, FLOOR2, VOID, 190,
            "optional", tw=WALL3, note="seeded optional north stack room")
    if branch_b:
        add(b, "arc.sideB", rect(100, -1000, 300, -800), 96, 608, FLOOR2, VOID, 190,
            "optional", tw=WALL3, note="seeded optional south stack room")
    b._reconcile()
    rk.rotate_builder(b, (seed * 31) % 360)
    b.debug["landmark"] = "arc.tower"
    b.start_sector = "arc.entry"
    opt = "arc.sideA" if branch_a else ("arc.sideB" if branch_b else "arc.optional")
    optz = 96 if (branch_a or branch_b) else 0
    b.anchor_specs = [
        ("entry", "arc.entry", 0, True), ("exit", "arc.exit", -96, True),
        ("vendor", "arc.vendor", 0, True),
        ("encounter_a", "arc.g1", 96, True), ("encounter_b", "arc.g2", 192, True),
        ("seal_a", "arc.g1.seal1", 96, True), ("seal_b", "arc.g1.seal2", 96, True),
        ("seal_c", "arc.g2.seal1", 192, True), ("seal_d", "arc.g2.seal2", 192, True),
        ("overlook", "arc.tower", 320, True), ("pit_recovery", "arc.sub", -96, True),
        ("optional_reward", opt, optz, False),
    ]
    b.debug["levels"] = [-96, 0, 96, 192, 320]
    b.debug["branch_A"] = branch_a
    b.debug["branch_B"] = branch_b
    b.debug["route_note"] = ("West gallery -> NW stair -> north gallery -> NE stair -> east "
                             "gallery -> SE stair -> south gallery -> SW stair -> west gallery; "
                             "a tower stair rises to the catwalk and a pit stair drops to the "
                             "sub-archive. Seeded side stack rooms add branches.")
    b.finish()
    return b

BUILDERS = {
    "asymmetrical-ossuary-conservatory": build_ossuary,
    "inhabited-archive": build_archive,
}
