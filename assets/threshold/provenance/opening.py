#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Threshold: an original opening floor for the Null Run Argon build.

The plan is hand-authored: a foyer, a two-tile north gallery, a service atrium
around a solid dry-stack landmark, a two-door pump/relay works, a return
connection back to the atrium and an exit vestibule. The south service corridor
and the works links make genuine alternate loops. The seed only varies creature
rolls, small light trims and cosmetic side-cache loot; geometry is fixed.

generate(seed, number=1) returns rogue.maps.Floor. Put the tested game root on
PYTHONPATH (read-only) before importing this module.
"""
from collections import deque
import hashlib
import json
import random

from PIL import Image, ImageDraw

from rogue.maps import Floor
from rogue.inhabitants import options

SIZE, TILE = 33, 128
SEED_SCHEME = '(seed << 8) | number'
START, EXIT = (5, 27), (7, 6)
THEME = ('THRESHOLD / SERVICE FOYER', 'NWALL01', 'NFLAT01', 'NFLAT03', 176)
RESERVED = {'latchwing': 69, 'relay_choir': 71}
EXISTING = {'surveyor': 9, 'wire_shambler': 84}
CLASSES = {'surveyor': 11, 'wire_shambler': 12, 'latchwing': 15, 'relay_choir': 16}
NEW_FLAG = 7

# -- authored plan -----------------------------------------------------------
ROOMS = [
    ('foyer', 'foyer', (3, 25, 5, 5)),
    ('service-atrium', 'atrium-ring', (9, 9, 13, 13)),
    ('pump-hall', 'pump-hall', (24, 5, 6, 7)),
    ('relay-bay', 'relay-bay', (24, 15, 6, 6)),
    ('exit-vestibule', 'exit-vestibule', (6, 5, 4, 3)),
    ('side-cache', 'side-cache', (31, 10, 1, 2)),
]
SOLID = {
    'landmark': [(x, y) for x in range(14, 17) for y in range(14, 17)],
    'pump-block': [(x, y) for x in range(26, 28) for y in range(7, 9)],
}
CORRIDORS = {
    'north-gallery': [(x, y) for x in range(5, 7) for y in range(21, 25)],
    'west-approach': [(x, y) for x in range(7, 9) for y in range(20, 22)],
    'east-approach': [(x, y) for x in range(22, 24) for y in range(18, 20)],
    'works-link-north': [(21, 8), (22, 7), (22, 8), (23, 7), (23, 8)],
    'works-link-south': [(25, 12), (25, 13), (25, 14), (29, 12), (29, 13), (29, 14)],
    'return-connector': [(27, y) for y in range(21, 26)],
    'exit-corridor': [(10, 7), (10, 8)],
    'foyer-return-link': [(8, 26), (8, 27)],
    'south-return': [(x, y) for x in range(9, 29) for y in range(26, 28)],
    'cache-mouth': [(30, 10), (30, 11)],
}
FLOOR_Z = {}
for name, cells in CORRIDORS.items():
    for p in cells:
        FLOOR_Z[p] = 0
for p in CORRIDORS['south-return'] + CORRIDORS['foyer-return-link']:
    FLOOR_Z[p] = 8
for p in CORRIDORS['return-connector']:
    FLOOR_Z[p] = 16 if p[1] <= 22 else 8
for p in CORRIDORS['works-link-north']:
    FLOOR_Z[p] = 0 if p in [(21, 8), (22, 7), (22, 8)] else 16
for p in CORRIDORS['works-link-south']:
    FLOOR_Z[p] = 16
for p in CORRIDORS['east-approach']:
    FLOOR_Z[p] = 0 if p[0] == 22 else 8
for p in CORRIDORS['cache-mouth']:
    FLOOR_Z[p] = 16
for p in CORRIDORS['exit-corridor']:
    FLOOR_Z[p] = 0

ROUTE = (
    [(5, 27), (5, 26), (5, 25), (5, 24), (5, 23), (5, 22), (5, 21),
     (6, 21), (7, 21), (8, 21), (9, 21)]
    + [(x, 21) for x in range(10, 22)]
    + [(21, 20), (21, 19), (21, 18), (22, 18), (23, 18), (24, 18), (25, 18),
       (25, 17), (25, 16), (25, 15), (25, 14), (25, 13), (25, 12), (25, 11),
       (25, 10), (25, 9), (24, 9), (24, 8), (24, 7), (23, 7), (22, 7), (22, 8),
       (21, 8), (21, 9)]
    + [(x, 9) for x in range(20, 9, -1)]
    + [(10, 8), (10, 7), (9, 7), (8, 7), (7, 7), (7, 6)]
)

PICKUPS = [
    (2001, (6, 28)), (2008, (4, 26)), (2008, (4, 28)), (2011, (6, 26)),
    (2012, (10, 19)), (2008, (18, 20)), (2011, (12, 9)), (2002, (25, 5)),
    (2012, (24, 6)), (2008, (28, 16)), (2018, (8, 6)),
    # optional side cache
    (2008, (30, 10)), (2012, (31, 10)), (2018, (31, 11)),
]
ENEMIES = [
    ('wire_shambler', 84, (8, 20), 180),
    ('surveyor', 9, (17, 21), 90),
    ('latchwing', 69, (13, 10), 180),
    ('relay_choir', 71, (24, 9), 90),
    ('wire_shambler', 84, (26, 17), 270),
    ('latchwing', 69, (14, 27), 0),
    ('relay_choir', 71, (28, 10), 270),
    ('surveyor', 9, (10, 10), 180),
]
PROPS = [
    ('directory_sign', (7, 25), 270),
    ('service_lamp', (4, 29), 0),
    ('directory_sign', (9, 9), 90),
    ('service_lamp', (24, 20), 180),
    ('cable_shrine', (30, 11), 90),
    ('service_lamp', (6, 5), 0),
]

# -- geometry helpers --------------------------------------------------------
def neighbours(p):
    x, y = p
    return ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def distances(cells, start):
    parent = {start: None}
    queue = deque([start])
    while queue:
        p = queue.popleft()
        for q in neighbours(p):
            if q in cells and q not in parent:
                parent[q] = p
                queue.append(q)
    return parent


def path(cells, a, b, blocked=frozenset()):
    if a in blocked or b in blocked or a not in cells or b not in cells:
        return None
    parent = {a: None}
    queue = deque([a])
    while queue:
        p = queue.popleft()
        if p == b:
            out = [p]
            while parent[out[-1]] is not None:
                out.append(parent[out[-1]])
            return out[::-1]
        for q in neighbours(p):
            if q in cells and q not in parent and q not in blocked:
                parent[q] = p
                queue.append(q)
    return None


def node_disjoint(cells, a, b):
    first = path(cells, a, b)
    if first is None:
        return 0, first
    second = path(cells, a, b, frozenset(first[1:-1]))
    return (1 + (second is not None)), second


def cycle_rank(cells):
    edges = sum(1 for p in cells for q in neighbours(p) if q in cells) // 2
    return edges - len(cells) + 1


def clear_line(cells, a, b):
    """Axis-aligned cell-centre sightline; every cell crossed must be open."""
    x0, y0 = a
    x1, y1 = b
    if x0 != x1 and y0 != y1:
        return False
    dx = (x1 > x0) - (x1 < x0)
    dy = (y1 > y0) - (y1 < y0)
    p = (x0, y0)
    while True:
        if p not in cells:
            return False
        if p == (x1, y1):
            return True
        p = (p[0] + dx, p[1] + dy)


def room_cells(bounds):
    x, y, w, h = bounds
    return {(a, b) for a in range(x, x + w) for b in range(y, y + h)}


# -- profiles ----------------------------------------------------------------
ATRIUM = room_cells(ROOMS[1][2]) - set(SOLID['landmark'])
PUMP = room_cells(ROOMS[2][2]) - set(SOLID['pump-block'])
RELAY = room_cells(ROOMS[3][2])
FOYER = room_cells(ROOMS[0][2])
EXIT_ROOM = room_cells(ROOMS[4][2])
CACHE = room_cells(ROOMS[5][2])
CORRIDOR_CELLS = {name: set(cells) for name, cells in CORRIDORS.items()}
ALL_CORRIDOR = set().union(*CORRIDOR_CELLS.values())
CELLS = FOYER | ATRIUM | PUMP | RELAY | EXIT_ROOM | CACHE | ALL_CORRIDOR | {(5, 24)}


def base_profile(shape, floor_z, height, light, wall, flat, ceiling):
    return {'floor': floor_z, 'height': height, 'light': light, 'wall': wall,
            'flat': flat, 'ceiling': ceiling, 'shape': shape}


def build_profiles(rng):
    profiles = {}
    for p in FOYER:
        profiles[p] = base_profile('foyer', 0, 192, 176 + rng.choice([-8, 0, 0, 8]),
                                   'NWALL01', 'NFLAT01', 'NFLAT03')
    for p in ATRIUM:
        edge = p[0] in (9, 21) or p[1] in (9, 21)
        near = manhattan(p, (15, 15)) <= 3
        profiles[p] = base_profile('atrium-ring', 0, 384, 200 if near else 160,
                                   'NWALL06' if edge else 'NWALL02', 'NFLAT01', 'NFLAT03')
    for p in PUMP:
        profiles[p] = base_profile('pump-hall', 16, 224, 160, 'NWALL04', 'NFLAT02', 'NFLAT04')
    for p in RELAY:
        profiles[p] = base_profile('relay-bay', 16, 208, 176, 'NWALL05', 'NFLAT02', 'NFLAT04')
    for p in EXIT_ROOM:
        profiles[p] = base_profile('exit-vestibule', 0, 192, 208, 'NWALL06', 'NFLAT01', 'NFLAT03')
    for p in CACHE:
        profiles[p] = base_profile('side-cache', 16, 128, 112, 'NWALL05', 'NFLAT02', 'NFLAT03')
    styles = {
        'north-gallery': (112, 152, 'NWALL01', 'NFLAT02', 'NFLAT03', 'passage'),
        'west-approach': (128, 160, 'NWALL01', 'NFLAT02', 'NFLAT03', 'passage'),
        'east-approach': (128, 168, 'NWALL03', 'NFLAT02', 'NFLAT04', 'passage'),
        'works-link-north': (112, 144, 'NWALL04', 'NFLAT02', 'NFLAT04', 'passage'),
        'works-link-south': (112, 144, 'NWALL04', 'NFLAT02', 'NFLAT04', 'passage'),
        'return-connector': (112, 136, 'NWALL04', 'NFLAT02', 'NFLAT04', 'passage'),
        'exit-corridor': (128, 176, 'NWALL06', 'NFLAT01', 'NFLAT03', 'passage'),
        'foyer-return-link': (112, 136, 'NWALL04', 'NFLAT02', 'NFLAT04', 'passage'),
        'south-return': (128, 136, 'NWALL04', 'NFLAT02', 'NFLAT04', 'return-corridor'),
        'cache-mouth': (112, 112, 'NWALL05', 'NFLAT02', 'NFLAT03', 'side-cache'),
    }
    for name, cells in CORRIDOR_CELLS.items():
        height, light, wall, flat, ceiling, shape = styles[name]
        for p in cells:
            profiles[p] = base_profile(shape, FLOOR_Z[p], height, light, wall, flat, ceiling)
    # The 23-link works elbow sits two units above the pump-hall lip.
    for p in [(23, 7), (23, 8)]:
        profiles[p]['floor'] = 8
    return profiles


# -- floor assembly ----------------------------------------------------------
def _new_options(kind, roll):
    if kind in RESERVED:
        return 1799 | (roll << 11)
    return options(kind, roll)


def generate(seed, number=1):
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 0xffffffff:
        raise ValueError('seed must be an unsigned 32-bit integer')
    if number != 1:
        raise ValueError('Threshold is the opening floor; number must be 1')
    rng = random.Random((seed << 8) | number)
    profiles = build_profiles(rng)
    # Static light trim only; no animated or strobing sectors.
    for p in sorted(profiles):
        profiles[p]['light'] = max(0, min(255, profiles[p]['light'] + rng.choice([-8, 0, 0, 8])))
    route = [tuple(p) for p in ROUTE]
    things = [(START[0] * TILE + 64, START[1] * TILE + 64, 270, 1, 7)]
    occupied = {START, EXIT}
    for kind, cell in PICKUPS:
        if cell in occupied or cell not in CELLS:
            raise ValueError(f'pickup cell {cell} unavailable')
        occupied.add(cell)
        things.append((cell[0] * TILE + 64, cell[1] * TILE + 64, 0, kind, 7))
    variants = []
    for kind, type_id, cell, angle in ENEMIES:
        if cell in occupied or cell not in CELLS:
            raise ValueError(f'enemy cell {cell} unavailable')
        occupied.add(cell)
        roll = rng.randrange(16)
        things.append((cell[0] * TILE + 64, cell[1] * TILE + 64, angle, type_id,
                       _new_options(kind, roll)))
        variants.append({'kind': kind, 'roll': roll,
                         'x': cell[0] * TILE + 64, 'y': cell[1] * TILE + 64})
    for name, cell, angle in PROPS:
        if cell in occupied or cell not in CELLS:
            raise ValueError(f'prop cell {cell} unavailable')
        occupied.add(cell)
    architecture = build_architecture(profiles, route)
    return Floor(1, set(CELLS), [r[2] for r in ROOMS], START, EXIT, route, things,
                 THEME, architecture, profiles, variants)


def build_architecture(profiles, route):
    cells = set(CELLS)
    foyer_to_atrium, second = node_disjoint(cells, (5, 27), (9, 21))
    works_paths, second_works = node_disjoint(cells, (9, 21), (25, 9))
    inner_loops, _ = node_disjoint(cells, (25, 9), (28, 15))
    runs, inside = 0, False
    for p in route:
        here = p in ATRIUM
        if here and not inside:
            runs += 1
        inside = here
    sightlines = []
    for name, a, b in [
        ('atrium-south', (9, 21), (21, 21)),
        ('atrium-north', (9, 9), (21, 9)),
        ('atrium-west', (9, 9), (9, 21)),
        ('atrium-east', (21, 9), (21, 21)),
        ('threshold-view', (10, 8), (10, 21)),
        ('foyer-gallery', (5, 27), (5, 21)),
    ]:
        sightlines.append({'name': name, 'a': list(a), 'b': list(b),
                           'tiles': manhattan(a, b) + 1, 'clear': clear_line(cells, a, b)})
    room_docs = [{'name': name, 'shape': shape, 'bounds': list(bounds),
                  'cells': len(room_cells(bounds) & cells), 'solid_cells': 0}
                 for name, shape, bounds in ROOMS]
    for name, solid in SOLID.items():
        room_docs.append({'name': name, 'shape': 'solid', 'cells': 0,
                          'solid_cells': len(solid),
                          'bounds': [min(p[0] for p in solid), min(p[1] for p in solid),
                                     max(p[0] for p in solid) - min(p[0] for p in solid) + 1,
                                     max(p[1] for p in solid) - min(p[1] for p in solid) + 1]})
    wide = sum(1 for name in ['north-gallery', 'west-approach', 'east-approach', 'south-return']
               if name in CORRIDOR_CELLS)
    return {
        'plan': 'hand-authored threshold service floor; seed varies rolls and light trim only',
        'rooms': room_docs,
        'landmark': {'name': 'THE DRY STACK', 'cells': [list(p) for p in sorted(SOLID['landmark'])],
                     'note': 'A solid three-by-three ceramic exhaust core in the atrium ring; '
                             'lit at 200 from the surrounding tiles, visible along all four atrium edges.'},
        'loops': [
            {'name': 'atrium ring', 'kind': 'ring around landmark',
             'evidence': 'the 13x13 atrium minus its 3x3 core is one open ring; cycle rank '
                         f'{cycle_rank(cells)} for the whole floor'},
            {'name': 'foyer two-way', 'kind': 'node-disjoint paths foyer to atrium',
             'paths': foyer_to_atrium, 'route': 'north gallery, or south return and works'},
            {'name': 'works two-way', 'kind': 'node-disjoint paths atrium to pump hall',
             'paths': works_paths, 'route': 'east approach through relay bay, or north link'},
            {'name': 'relay-pump pair', 'kind': 'two vertical service shafts', 'paths': inner_loops,
             'route': 'x=25 and x=29 between the relay bay and the pump hall'},
        ],
        'route': [list(p) for p in route],
        'route_notes': 'foyer -> north gallery -> atrium south -> east approach -> relay bay -> '
                       'pump/relay works -> north link -> atrium north -> exit corridor. The south '
                       'return corridor and both works shafts are genuine alternate loops.',
        'atrium_visits': runs,
        'max_step': max(abs(profiles[p]['floor'] - profiles[q]['floor'])
                        for p in cells for q in neighbours(p) if q in cells),
        'start_clearance': 6,
        'sightlines': sightlines,
        'two_wide_corridors': wide,
        'props_note': 'props are metadata only; Codex chooses native decor actors and collision. '
                      'Every prop cell is off the authored route and the floor stays connected '
                      'with all prop cells removed.',
        'secret_design': 'The side cache (a two-tile maintenance recess off the pump hall) is an '
                         'optional resource detour, not a native secret. No sector tag, secret '
                         'flag or trigger is set; Codex may treat it as ordinary geometry.',
        'enemy_plan': 'Eight spaced encounters, no boss: husk in the west approach, surveyor on '
                      'the atrium south edge, latchwing over the atrium north side, relay choir at '
                      'the pump-hall mouth, husk in the relay bay, latchwing on the south return, '
                      'relay choir guarding the cache mouth, surveyor before the exit vestibule.',
        'theme_hints': {'wall': 'NWALL01..06', 'flat': 'NFLAT01..02', 'ceiling': 'NFLAT03..04',
                        'note': 'metadata hints only; the current writer expects its own names'},
        'reserved_types': {'latchwing': {'type': 69, 'class': 15, 'flag': 7},
                           'relay_choir': {'type': 71, 'class': 16, 'flag': 7}},
        'max_enemy_budget': 12,
    }


# -- checks ------------------------------------------------------------------
CHECK_SEEDS = [0, 1, 2, 3, 42, 255, 1234, 65535, 0xdeadbeef, 20261030, 20261031, 0xffffffff]


def _floor_signature(f):
    geo = {str(k): {key: v[key] for key in ('floor', 'height', 'shape', 'wall', 'flat', 'ceiling')}
           for k, v in sorted(f.profiles.items())}
    things = [(t[0], t[1], t[2], t[3]) for t in f.things]
    return json.dumps({'cells': sorted(f.cells), 'start': f.start, 'exit': f.exit,
                       'route': f.route, 'things': things, 'profiles': geo, 'props': PROPS},
                      sort_keys=True)


def run_checks(seeds=CHECK_SEEDS):
    checks = []

    def add(name, ok, detail):
        checks.append({'name': name, 'pass': bool(ok), 'detail': detail})

    failures = []
    signatures, roll_sets, light_sets = [], [], []
    for seed in seeds:
        f = generate(seed)
        cells = set(f.cells)
        tag = f'seed {seed}'
        add(f'floor_type [{tag}]', isinstance(f, Floor) and f.number == 1,
            type(f).__name__ + ', number 1')
        ok = (all(0 <= x < SIZE and 0 <= y < SIZE for x, y in cells) and f.start in cells
              and f.exit in cells and len(cells) == len(CELLS))
        add(f'grid_bounds [{tag}]', ok, f'{len(cells)} open cells inside 33x33')
        parents = distances(cells, f.start)
        add(f'connectivity [{tag}]', len(parents) == len(cells),
            f'{len(parents)}/{len(cells)} cells reachable from start')
        rt = [tuple(p) for p in f.route]
        step_ok = all(manhattan(a, b) == 1 for a, b in zip(rt, rt[1:]))
        add(f'route [{tag}]', rt[0] == f.start and rt[-1] == f.exit and step_ok
            and all(p in cells for p in rt), f'{len(rt)} cells, adjacent, start to exit')
        enemies = [(t, (t[0] // TILE, t[1] // TILE)) for t in f.things if t[4] >= 1799]
        add(f'no_boss [{tag}]', all(t[3] not in (3003, 3005, 7) for t, p in enemies),
            'no boss or player thing among the encounters')
        min_start = min(manhattan(p, f.start) for t, p in enemies)
        add(f'start_clearance [{tag}]', min_start >= 6,
            f'nearest enemy is {min_start} Manhattan tiles from the foyer start')
        count = len(enemies)
        types = {t[3] for t, p in enemies}
        add(f'enemy_budget [{tag}]', 8 <= count <= 12 and 69 in types and 71 in types
            and bool(types & {9, 84}), f'{count} enemies; types {sorted(types)}')
        pair_min = min((manhattan(a, b) for i, (t, a) in enumerate(enemies)
                        for u, b in enemies[i + 1:]), default=0)
        add(f'enemy_spacing [{tag}]', pair_min >= 3, f'closest pair {pair_min} tiles')
        exit_dist = min(manhattan(p, f.exit) for t, p in enemies)
        add(f'exit_clear [{tag}]', exit_dist >= 2 and f.exit not in [p for t, p in enemies],
            f'nearest enemy {exit_dist} tiles from the exit')
        deltas = [abs(f.profiles[p]['floor'] - f.profiles[q]['floor'])
                  for p in cells for q in neighbours(p) if q in cells]
        add(f'step_heights [{tag}]', max(deltas) <= 16, f'max adjacent floor delta {max(deltas)} units')
        badp = [p for p in cells if f.profiles[p]['height'] < 96 or not 0 <= f.profiles[p]['light'] <= 255]
        add(f'profile_ranges [{tag}]', not badp, 'headroom >= 96, light 0..255')
        add(f'loops [{tag}]', cycle_rank(cells) >= 2
            and node_disjoint(cells, (5, 27), (9, 21))[0] >= 2
            and node_disjoint(cells, (9, 21), (25, 9))[0] >= 2,
            f'cycle rank {cycle_rank(cells)}; foyer<->atrium and atrium<->works each have '
            'two node-disjoint paths')
        prop_cells = [tuple(p) for _, p, _ in PROPS]
        prop_ok = (all(p in cells and p != f.start and p != f.exit for p in prop_cells)
                   and not (set(prop_cells) & set(rt))
                   and len(distances(cells - set(prop_cells), f.start)) == len(cells) - len(prop_cells))
        add(f'props_nonblocking [{tag}]', prop_ok,
            f'{len(prop_cells)} props off-route; floor connected with props removed')
        pickup_cells = [(t[0] // TILE, t[1] // TILE) for t in f.things
                        if t[3] in {kind for kind, _ in PICKUPS}]
        add(f'pickups_connected [{tag}]',
            all(p in cells and p in parents for p in pickup_cells)
            and len(pickup_cells) == len(PICKUPS),
            f'{len(pickup_cells)} pickups on the connected floor')
        roll_at = {(v['x'] // TILE, v['y'] // TILE): v['roll'] for v in f.variants}
        opts_ok = all(t[4] == (1799 | (roll_at[(t[0] // TILE, t[1] // TILE)] << 11))
                      for t, p in enemies) and {t[3] for t, p in enemies} >= {9, 84, 69, 71}
        add(f'reserved_options [{tag}]', opts_ok,
            'eight creatures carry options 1799 + roll*2048; existing 9/84 and reserved 69/71 all present')
        names = {f.profiles[p]['wall'] for p in cells} | {f.profiles[p]['flat'] for p in cells} | \
                {f.profiles[p]['ceiling'] for p in cells}
        add(f'art_names [{tag}]', names <= {f'NWALL0{i}' for i in range(1, 7)} |
            {f'NFLAT0{i}' for i in range(1, 5)}, 'profiles reference only the generated art names')
        sight = f.architecture['sightlines']
        add(f'sightlines [{tag}]', all(s['clear'] for s in sight),
            ', '.join(f"{s['name']}={s['tiles']}" for s in sight))
        landmark = set(SOLID['landmark'])
        add(f'landmark [{tag}]', not (landmark & cells) and all(
                q in cells or q in landmark
                for p in landmark for q in neighbours(p)),
            'solid dry-stack core fully surrounded by open atrium ring')
        add(f'atrium_revisit [{tag}]', f.architecture['atrium_visits'] >= 2,
            f"route enters the atrium in {f.architecture['atrium_visits']} separate runs")
        signatures.append(_floor_signature(f))
        roll_sets.append(tuple(v['roll'] for v in f.variants))
        light_sets.append(tuple(f.profiles[p]['light'] for p in sorted(cells)))
    add('deterministic_geometry', len(set(signatures)) == 1,
        f'{len(seeds)} seeds share one floor plan, route, profile set and thing layout')
    add('seeded_variation', len(set(roll_sets)) > 1 and len(set(light_sets)) > 1,
        'creature rolls and light trims vary with the seed; geometry does not')
    passed = all(c['pass'] for c in checks)
    return {'passed': passed, 'seeds': seeds, 'checks': checks,
            'summary': {'total': len(checks), 'passed': sum(c['pass'] for c in checks),
                        'failed': sum(not c['pass'] for c in checks),
                        'open_cells': len(CELLS), 'route_cells': len(ROUTE)}}


# -- overview ----------------------------------------------------------------
SHAPE_COLOR = {
    'foyer': (188, 176, 148), 'atrium-ring': (96, 110, 122), 'pump-hall': (72, 96, 104),
    'relay-bay': (92, 98, 88), 'exit-vestibule': (168, 148, 100), 'side-cache': (142, 112, 64),
    'passage': (112, 118, 120), 'return-corridor': (102, 112, 114),
}
SOLID_COLOR = {'landmark': (122, 74, 46), 'pump-block': (80, 72, 60)}
ENEMY_LETTER = {'wire_shambler': 'H', 'surveyor': 'S', 'latchwing': 'L', 'relay_choir': 'R'}


def overview_document(seed=20261030):
    f = generate(seed)
    checks = run_checks()
    props = [{'name': name, 'cell': list(cell), 'angle': angle} for name, cell, angle in PROPS]
    things = [{'x': t[0], 'y': t[1], 'cell': [t[0] // TILE, t[1] // TILE],
               'angle': t[2], 'type': t[3], 'options': t[4]} for t in f.things]
    shapes = {}
    for p in sorted(f.cells):
        s = f.profiles[p]['shape']
        d = shapes.setdefault(s, {'cells': 0, 'floors': set(), 'heights': set(), 'lights': set()})
        d['cells'] += 1
        d['floors'].add(f.profiles[p]['floor'])
        d['heights'].add(f.profiles[p]['height'])
        d['lights'].add(f.profiles[p]['light'])
    profile_summary = {k: {'cells': v['cells'], 'floors': sorted(v['floors']),
                           'heights': sorted(v['heights']), 'lights': sorted(v['lights'])}
                       for k, v in shapes.items()}
    return {
        'floor': 'Threshold / opening service floor', 'seed': seed, 'number': f.number,
        'seed_scheme': SEED_SCHEME, 'theme': list(f.theme),
        'start': list(f.start), 'exit': list(f.exit),
        'cells': [list(p) for p in sorted(f.cells)],
        'solid_cells': {k: [list(p) for p in v] for k, v in SOLID.items()},
        'rooms': f.architecture['rooms'],
        'route': f.architecture['route'], 'route_notes': f.architecture['route_notes'],
        'things': things, 'variants': f.variants, 'props': props,
        'architecture': {k: f.architecture[k] for k in
                         ('landmark', 'loops', 'sightlines', 'secret_design', 'props_note',
                          'enemy_plan', 'reserved_types', 'max_step', 'start_clearance',
                          'two_wide_corridors', 'atrium_visits', 'theme_hints')},
        'profile_summary': profile_summary,
        'checks': checks['summary'],
        'interface': {
            'generate': 'generate(seed, number=1) -> rogue.maps.Floor',
            'things': '(x, y, angle, type, options); reserved types 69/71 use options 1799 + roll*2048',
            'props': 'metadata only; no native thing IDs or collision are guessed',
            'provenance': 'original plan; no existing map traced or copied',
        },
    }


def draw_overview(path, seed=20261030, scale=18, margin=20, legend=170):
    doc = overview_document(seed)
    f = generate(seed)
    width = max(SIZE * scale + 2 * margin, 980)
    height = SIZE * scale + 2 * margin + legend + 18
    image = Image.new('RGB', (width, height), (18, 22, 24))
    pen = ImageDraw.Draw(image)
    ox, oy = margin, margin + 18
    for p in f.cells:
        x, y = p
        color = SHAPE_COLOR.get(f.profiles[p]['shape'], (100, 104, 104))
        image.paste(color, (ox + x * scale, oy + y * scale,
                            ox + (x + 1) * scale - 1, oy + (y + 1) * scale - 1))
    for name, solid in SOLID.items():
        for x, y in solid:
            image.paste(SOLID_COLOR[name], (ox + x * scale, oy + y * scale,
                                            ox + (x + 1) * scale - 1, oy + (y + 1) * scale - 1))
    pen.line([(ox + p[0] * scale + scale // 2, oy + p[1] * scale + scale // 2) for p in f.route],
             fill=(232, 174, 76), width=2, joint='curve')
    sx, sy = f.start
    pen.ellipse((ox + sx * scale + 4, oy + sy * scale + 4,
                 ox + (sx + 1) * scale - 5, oy + (sy + 1) * scale - 5), fill=(120, 206, 126))
    ex, ey = f.exit
    pen.rectangle((ox + ex * scale + 4, oy + ey * scale + 4,
                   ox + (ex + 1) * scale - 5, oy + (ey + 1) * scale - 5), fill=(224, 92, 64))
    for kind, cell, angle in PROPS:
        x, y = cell
        pen.rectangle((ox + x * scale + 5, oy + y * scale + 5,
                       ox + (x + 1) * scale - 6, oy + (y + 1) * scale - 6),
                      outline=(120, 178, 230), width=2)
    for t in f.things:
        x, y = t[0] // TILE, t[1] // TILE
        cx, cy = ox + x * scale + scale // 2, oy + y * scale + scale // 2
        if t[4] >= 1799:
            pen.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=(196, 70, 62), outline=(28, 20, 20))
            kind = next((k for k, tid, _, _ in ENEMIES if tid == t[3]), None)
            if kind:
                pen.text((cx - 3, cy - 4), ENEMY_LETTER[kind], fill=(255, 236, 200))
        elif t[3] != 1:
            pen.rectangle((cx - 3, cy - 3, cx + 3, cy + 3), fill=(236, 226, 196))
    pen.text((margin, 8), 'THRESHOLD / OPENING FLOOR - original plan, seed '
             f'{seed} - amber line is the authored route', fill=(224, 218, 198))
    y0 = oy + SIZE * scale + 12
    lines = [
        'start green; exit red; red dots enemies (H husk, S surveyor, L latchwing, R relay choir)',
        'white dots pickups; blue squares metadata props; solid core is THE DRY STACK',
        f"open cells {len(f.cells)}; route {len(f.route)}; enemies 8; props {len(PROPS)}; "
        f"max step {f.architecture['max_step']} units; two-wide corridors "
        f"{f.architecture['two_wide_corridors']}",
        'loops: atrium ring; foyer via north gallery or south return+works; works via east '
        'approach or north link; relay/pump via x=25 and x=29 shafts',
        'secret: optional side cache off the pump hall; no native secret tag or trigger is set',
        'theme hints NWALL01-06 / NFLAT01-04 are generated metadata, not a WAD claim',
        f"geometry checks {doc['checks']['passed']}/{doc['checks']['total']} across "
        f"{len(CHECK_SEEDS)} seeds; see opening-overview.json",
    ]
    for i, line in enumerate(lines):
        pen.text((margin, y0 + i * 18), line, fill=(196, 202, 196))
    image.save(path)
    return doc


def main():
    from pathlib import Path
    root = Path(__file__).resolve().parent
    doc = draw_overview(root / 'opening-overview.png')
    (root / 'opening-overview.json').write_text(json.dumps(doc, indent=2) + '\n')
    checks = run_checks()
    print(json.dumps(checks['summary'], indent=2))
    failed = [c['name'] for c in checks['checks'] if not c['pass']]
    if failed:
        print('FAILED:', failed)
    return 0 if checks['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
