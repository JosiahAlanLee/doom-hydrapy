#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Null Run signature mobs: six original designs on the two existing behavior slots.

Every frame is drawn from geometric primitives with Pillow.  Each atlas is
512x768 RGBA: four columns x six rows of 128x128 cells.  Rows are idle, walk,
warning, attack, hurt, death.  Cells keep >=3 px transparent padding, the floor
anchor is y=120 in every frame, and the final death cell remains a visible
corpse.  No game sprite, texture or font is sampled.

The six identities use the existing latchwing (class 15, CYBR) and relay_choir
(class 16, PAIN) behavior families.  This file supplies art only: no actor IDs,
AI, frame mapping, engine code or new mechanics.

CLI: python mob_art.py --out DIRECTORY --seed INTEGER
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SIZE = 128
COLS, ROWS = 4, 6
STATES = ('idle', 'walk', 'warning', 'attack', 'hurt', 'death')
SLOTS = ('latchwing', 'relay_choir')
SET_IDS = ('drowned_records', 'switchyard_chapel', 'after_hours_pavilion')
DEFAULT_SEED = 20261031
FLOOR = 120

PAL = {
    'drowned_records': {
        'chalk': '#E8E1CC', 'bone': '#D8CFB6', 'paper': '#C4B99C',
        'silt': '#A79778', 'petrol': '#2F4147', 'slate': '#566A70',
        'copper': '#9A6238', 'copper_l': '#C98B56', 'ink': '#1B2528',
        'glass': '#9DAA9E',
    },
    'switchyard_chapel': {
        'ivory': '#DDD6C0', 'porcelain': '#EFEAD8', 'bone': '#BFB7A1',
        'rust': '#8E3F2B', 'rust_l': '#B65C3B', 'iron': '#3B3734',
        'charcoal': '#252423', 'cable': '#171818', 'amber': '#E0A13C',
        'amber_l': '#FFD487', 'oxide': '#6D3927',
    },
    'after_hours_pavilion': {
        'plum': '#6E5768', 'plum_d': '#463645', 'plum_l': '#8D7488',
        'slate': '#5D6872', 'terra': '#D9D3C5', 'terra_d': '#B3AA99',
        'brass': '#A8864C', 'brass_l': '#D2B06E', 'cream': '#EFE7D6',
        'ink': '#241F28', 'dust': '#A79C90',
    },
}

# set -> slot -> (design id, display name, fiction, warning, limits)
IDENTITIES = {
    'drowned_records': {
        'latchwing': (
            'shelf_widow', 'SHELF WIDOW',
            ('An ordinary bowed filing shelf that has learned to stand. Its front '
             'splits into a long, low negative-space body; paper folds become limbs '
             'and open drawers become wet mouths. It is found-object architecture '
             'first and an animal only when it unfolds.'),
            ('Warning is a slow separation of the cabinet face: drawer gaps widen, '
             'the dark interior lengthens, and folded paper limbs slide out. The '
             'locked-direction dash is shown as a low, committed lunge, never a '
             'teleport. Keep the empty cavity and drawer mouths readable at 128 px.'),
            ('Existing latchwing family only: class 15 CYBR, telegraphed '
             'locked-direction dash. No new AI, phasing, teleportation, gaze or '
             'actor ID. Codex owns behavior and frame mapping.'),
        ),
        'relay_choir': (
            'redacted_choir', 'REDACTED CHOIR',
            ('A hunched stack of waterlogged registrars and paper-veiled almost-faces. '
             'The blank regions are the point: no eyes, only seams and slowly rising '
             'ink pressure behind the paper. When it opens, three wet paper tongues '
             'fan out from the stack.'),
            ('Warning is the ink level visibly climbing inside the blank face panels '
             'across four frames, with a copper pressure needle. It is slow, quiet '
             'and readable without a flash or a dark outline. The three-projectile '
             'fan is composed as three paper tongues, not a new mechanic.'),
            ('Existing relay_choir family only: class 16 PAIN, anchored telegraphed '
             'slow three-projectile fan. No new AI, projectile count, phasing or '
             'actor ID. Codex owns behavior and frame mapping.'),
        ),
    },
    'switchyard_chapel': {
        'latchwing': (
            'insulator_widow', 'INSULATOR WIDOW',
            ('A fluted ceramic and cable arthropod assembled from petticoat '
             'insulators, rust iron joints and heavy cable legs. Amber pressure '
             'glows between cracked ivory segments; it moves like a low, cautious '
             'machine that has been left energized too long.'),
            ('Warning separates the ceramic discs and shows amber pressure in the '
             'gaps while the cable legs coil. The dash is a stretched, low directional '
             'lunge with trailing cable, clearly different from the drowned shelf.'),
            ('Existing latchwing family only: class 15 CYBR, telegraphed '
             'locked-direction dash. No new AI, electric damage, phasing or actor ID. '
             'Codex owns behavior and frame mapping.'),
        ),
        'relay_choir': (
            'transformer_cantor', 'TRANSFORMER CANTOR',
            ('A stationary radial insulator and conductor body: a rust iron core '
             'inside a crown of ivory ceramic fins, braided cable roots and small '
             'amber pressure gauges. It does not walk; it rotates, opens and sings '
             'a wide three-part fan.'),
            ('Warning is a slow outward rotation of the fin crown, three amber '
             'pressure eyes rising and three ceramic nozzles extending. The '
             'three-projectile fan is the existing anchored relay pattern, shown '
             'as a spreading mechanical fan, not a new attack.'),
            ('Existing relay_choir family only: class 16 PAIN, anchored telegraphed '
             'slow three-projectile fan. No new AI, beam, chain lightning or actor '
             'ID. Codex owns behavior and frame mapping.'),
        ),
    },
    'after_hours_pavilion': {
        'latchwing': (
            'queue_stalker', 'QUEUE STALKER',
            ('An empty folded service coat suspended on low articulated queue '
             'struts. The collar is an unfilled opening, the sleeves are flat '
             'pleats and a retractable belt hangs where an arm should be. It moves '
             'in short, over-civil scuttles.'),
            ('Warning unfolds the coat into a wider baffle, lifts the empty sleeves '
             'and opens the collar while the struts spread. The lunge is a low, '
             'compressed dash; the silhouette stays a coat and stand, never a '
             'soldier.'),
            ('Existing latchwing family only: class 15 CYBR, telegraphed '
             'locked-direction dash. No new AI, possession, phasing or actor ID. '
             'Codex owns behavior and frame mapping.'),
        ),
        'relay_choir': (
            'usher_cluster', 'USHER CLUSTER',
            ('A split-faced unattended ticket and usher arrangement: overlapping '
             'kiosk faces, folded brass baffles and three empty apertures of '
             'different sizes. The symmetry is deliberately broken; nothing inside '
             'the apertures is shown.'),
            ('Warning unfolds the brass baffles and widens the empty apertures while '
             'small brass pressure flags rise. The three dark apertures become the '
             'three-tongue fan of the existing anchored relay pattern. No fake '
             'portal or gaze is drawn.'),
            ('Existing relay_choir family only: class 16 PAIN, anchored telegraphed '
             'slow three-projectile fan. No new AI, portal, gaze or actor ID. Codex '
             'owns behavior and frame mapping.'),
        ),
    },
}


def hx(value):
    value = value.lstrip('#')
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def C(set_id, name):
    return hx(PAL[set_id][name])


def blank():
    return Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))


def poly(pen, points, fill, outline=None, width=1):
    pen.polygon(points, fill=fill, outline=outline, width=width)


def line(pen, points, fill, width=2):
    pen.line(points, fill=fill, width=width, joint='curve')


def ellipse(pen, box, fill, outline=None, width=1):
    pen.ellipse(box, fill=fill, outline=outline, width=width)


def bolt(pen, x, y, r, face, edge, shine=None):
    pen.ellipse((x - r, y - r, x + r, y + r), fill=face, outline=edge)
    if shine:
        pen.point((x - max(1, r // 2), y - max(1, r // 2)), fill=shine)


def foot(pen, x, color, edge, w=6):
    """A small floor pad; every frame has at least one pad reaching y=120."""
    x = max(8, min(119, x))
    poly(pen, [(x - w // 2, FLOOR - 3), (x + w // 2, FLOOR - 3),
               (x + w // 2 - 1, FLOOR), (x - w // 2 + 1, FLOOR)], edge)
    poly(pen, [(x - w // 2 + 1, FLOOR - 3), (x + w // 2 - 1, FLOOR - 3),
               (x + w // 2 - 2, FLOOR - 1), (x - w // 2 + 2, FLOOR - 1)], color)


def cable(pen, points, color, width=3):
    line(pen, points, color, width)


def paper_fold(pen, points, fill, edge, fold=None):
    poly(pen, points, fill, edge)
    if fold:
        line(pen, fold, edge, 1)


def fluted_disc(pen, cx, cy, rx, ry, body, light, dark, ridges=5):
    ellipse(pen, (cx - rx, cy - ry, cx + rx, cy + ry), body, dark)
    for k in range(ridges):
        t = (k + 0.5) / ridges
        x = cx - rx + int(2 * rx * t)
        line(pen, [(x, cy - ry + 2), (x, cy + ry - 2)], light, 1)
    line(pen, [(cx - rx + 2, cy - ry + 1), (cx + rx - 2, cy - ry + 1)], light, 1)


def jitter(rng, amount):
    return rng.randint(-amount, amount)

def finalize(frame):
    """Clip to >=4 px side/top padding and the y=120 floor anchor."""
    a = np.array(frame, dtype=np.uint8)
    a[:4, :, 3] = 0
    a[:, :4, 3] = 0
    a[:, 124:, 3] = 0
    a[121:, :, 3] = 0
    return Image.fromarray(a, 'RGBA')


# -- Drowned Records: shelf widow -------------------------------------------
def shelf_widow(variant, state, frame, rng):
    sid = 'drowned_records'
    chalk, bone, paper, silt = C(sid, 'chalk'), C(sid, 'bone'), C(sid, 'paper'), C(sid, 'silt')
    petrol, slate = C(sid, 'petrol'), C(sid, 'slate')
    copper, copper_l, ink = C(sid, 'copper'), C(sid, 'copper_l'), C(sid, 'ink')
    im = blank()
    pen = ImageDraw.Draw(im)
    wide = variant == 'B'
    if state == 'death':
        return shelf_widow_death(variant, frame, rng)
    bob = {'idle': (0, -1, 0, 1), 'walk': (-1, -3, 1, 2),
           'warning': (-2, -1, 0, 1), 'attack': (2, 3, 4, 4),
           'hurt': (4, 6, 3, 1)}[state][frame]
    sway = {'idle': (0, 1, 0, -1), 'walk': (-4, 0, 4, 0),
            'warning': (-1, 0, 1, 0), 'attack': (-3, -5, -7, -8),
            'hurt': (-5, -2, 2, 3)}[state][frame]
    opening = {'idle': 0, 'walk': 0, 'warning': (3, 6, 9, 13)[frame],
               'attack': 18, 'hurt': (11, 7, 4, 1)[frame]}[state]
    # body shell: A tall two-column cabinet, B low four-drawer credenza
    if not wide:
        x0, x1, top, bottom = 31 + sway, 97 + sway, 54 + bob, 106
        legs = (36, 50, 78, 92)
        left_panel, right_panel = (x0 + 4, x0 + 29), (x0 + 37, x0 + 62)
        rows, cols = 3, 1
    else:
        x0, x1, top, bottom = 17 + sway, 111 + sway, 70 + bob, 108
        legs = (24, 40, 58, 74, 92, 106)
        left_panel, right_panel = (x0 + 5, x0 + 43), (x0 + 47, x0 + 89)
        rows, cols = 1, 2
    # legs and feet, drawn behind the cabinet
    for i, lx in enumerate(legs):
        step = 0
        if state == 'walk':
            step = (-7, 4, 7, -4)[(frame + i) % 4]
        elif state == 'warning':
            step = (-2, -1, 1, 2)[(frame + i) % 4]
        elif state == 'attack':
            step = (-8, -11, -13, -14)[(frame + i) % 4]
        elif state == 'hurt':
            step = (-4, -2, 2, 4)[(frame + i) % 4]
        hip = (lx + sway // 2, bottom - 3)
        knee = (lx + step // 2, 111)
        ankle = (max(8, min(119, lx + step)), FLOOR - 3)
        line(pen, [hip, knee, ankle], (80, 70, 54), 3)
        line(pen, [(hip[0] + 1, hip[1]), (knee[0] + 1, knee[1])], copper, 1)
        foot(pen, ankle[0], (72, 62, 48), ink, 7 if wide else 6)
    # dark negative-space core sits behind the opening faces
    core = (max(5, left_panel[1] - opening // 2), top + 9,
            min(122, right_panel[0] + opening // 2), bottom - 3)
    if core[2] > core[0]:
        poly(pen, [(core[0], core[1]), (core[2], core[1]),
                   (core[2] + 2, core[3]), (core[0] - 2, core[3])], petrol, ink, 2)
        for k in range(3):
            y = core[1] + 6 + k * 9
            line(pen, [(core[0] + 3, y), (core[2] - 3, y)], ink, 2)
        for k in range(3):
            x = core[0] + 5 + k * 7
            poly(pen, [(x, core[3] - 8), (x + 5, core[3] - 12), (x + 4, core[3] - 1)],
                 chalk, (126, 114, 92))
    # shell top and side posts
    sag = 4 if state in ('idle', 'walk', 'warning') else 1
    poly(pen, [(x0, top), (x0 + 7, top - 5), ((x0 + x1) // 2, top - 1 - sag),
               (x1 - 7, top - 5), (x1, top), (x1, bottom), (x0, bottom)],
         paper, ink, 2)
    poly(pen, [(x0 + 5, top + 2), (x0 + 10, top - 1), ((x0 + x1) // 2, top + 2 - sag),
               (x1 - 10, top - 1), (x1 - 5, top + 2), (x1 - 5, top + 7),
               (x0 + 5, top + 7)], bone, None)
    # bent paper title plate
    tcx = (x0 + x1) // 2
    poly(pen, [(tcx - 15, top + 10), (tcx + 15, top + 9), (tcx + 13, top + 18),
               (tcx - 13, top + 19)], chalk, (128, 116, 94))
    line(pen, [(tcx - 10, top + 13), (tcx + 8, top + 12)], silt, 1)
    line(pen, [(tcx - 10, top + 16), (tcx + 4, top + 15)], silt, 1)
    # two face banks containing the drawers; they pull outward when opening
    os = min(11, opening // 2)
    banks = ((left_panel[0] - os, left_panel[1] - os, cols, rows),
             (right_panel[0] + os, right_panel[1] + os, cols, rows))
    for bx0, bx1, bcols, brows in banks:
        by0, by1 = top + 20, bottom - 4
        poly(pen, [(bx0, by0), (bx1, by0), (bx1 + 1, by1), (bx0 - 1, by1)],
             bone, ink, 2)
        cw = max(8, (bx1 - bx0 - 4) // bcols)
        ch = max(8, (by1 - by0 - 4) // brows)
        for r in range(brows):
            for c in range(bcols):
                dx0 = bx0 + 2 + c * cw
                dy0 = by0 + 2 + r * ch
                dx1 = min(bx1 - 1, dx0 + cw - 3)
                dy1 = min(by1 - 1, dy0 + ch - 3)
                poly(pen, [(dx0, dy0), (dx1, dy0), (dx1, dy1), (dx0, dy1)], slate, ink, 1)
                line(pen, [(dx0 + 1, dy0 + 1), (dx1 - 1, dy0 + 1)], (126, 146, 150), 1)
                poly(pen, [(dx0 + 3, dy0 + 2), (dx1 - 3, dy0 + 2),
                           (dx1 - 3, dy0 + 6), (dx0 + 3, dy0 + 6)],
                     paper, (128, 116, 94))
                line(pen, [(dx0 + 4, dy0 + 4), (dx1 - 5, dy0 + 4)], silt, 1)
                line(pen, [(dx0 + 4, dy1 - 4), (dx1 - 4, dy1 - 4)], copper, 2)
                bolt(pen, dx0 + 3, dy1 - 4, 1, copper_l, ink)
        # a peeled paper corner that never quite closes
        poly(pen, [(bx0 + 2, by1 - 9), (bx0 + 12, by1 - 11), (bx0 + 9, by1 - 1)],
             chalk, (128, 116, 94))
    # paper folds hanging from the shell
    for k, fx in enumerate((x0 + 10, x0 + 24, x1 - 12)):
        line(pen, [(fx, bottom - 2), (fx - 2, bottom + 5 + k * 2)], chalk, 2)
    # long paper-fold limbs
    if state in ('warning', 'attack', 'hurt'):
        reach = (4, 8, 12, 16)[frame] if state == 'warning' else (20, 26, 30, 32)[frame]
        if state == 'hurt':
            reach = (12, 7, 4, 2)[frame]
        for side in (-1, 1):
            shoulder = (x0 if side < 0 else x1, top + 24)
            elbow = (max(7, min(120, shoulder[0] + side * (7 + reach // 2))), 96)
            wrist = (max(7, min(120, shoulder[0] + side * (11 + reach))), 118)
            line(pen, [shoulder, elbow, wrist], bone, 4)
            line(pen, [(shoulder[0] + side, shoulder[1]), (elbow[0] + side, elbow[1])],
                 chalk, 1)
            poly(pen, [(wrist[0] - 3, wrist[1] - 3), (wrist[0] + side * 6, wrist[1] - 1),
                       (wrist[0] + side * 3, wrist[1] + 3)], paper, ink)
        for side in (-1, 1):
            start = ((x0 + x1) // 2 + side * 14, bottom - 8)
            end = (max(8, min(119, start[0] + side * (9 + reach // 2))), 118)
            line(pen, [start, ((start[0] + end[0]) // 2, 108), end], paper, 2)
            foot(pen, end[0], (92, 82, 64), ink, 5)
    # airborne paper scraps on the active frames
    if state in ('warning', 'attack', 'hurt'):
        for k in range(3):
            x = (x0 + x1) // 2 + rng.randint(-28, 28)
            y = top + 12 + rng.randint(0, 30)
            poly(pen, [(x, y), (x + 5, y + 1), (x + 4, y + 4), (x - 1, y + 3)],
                 chalk, (126, 114, 92))
    return im

def shelf_widow_death(variant, frame, rng):
    sid = 'drowned_records'
    chalk, bone, paper, silt = C(sid, 'chalk'), C(sid, 'bone'), C(sid, 'paper'), C(sid, 'silt')
    petrol, slate = C(sid, 'petrol'), C(sid, 'slate')
    copper, copper_l, ink = C(sid, 'copper'), C(sid, 'copper_l'), C(sid, 'ink')
    im = blank()
    pen = ImageDraw.Draw(im)
    wide = variant == 'B'
    fall = (0, 5, 10, 14)[frame]
    cx = 64 + (4 if frame > 1 else 0)
    if not wide:
        box = [(20, 78 + fall), (92, 76 + fall), (104, 100 + fall), (12, 102 + fall)]
        mouth = (34, 86 + fall, 68, 98 + fall)
        legs = ((26, 98 + fall, 20), (90, 98 + fall, 98), (36, 100 + fall, 46))
    else:
        box = [(12, 84 + fall), (100, 82 + fall), (108, 104 + fall), (8, 106 + fall)]
        mouth = (28, 92 + fall, 58, 104 + fall)
        legs = ((20, 104 + fall, 14), (98, 104 + fall, 104), (38, 106 + fall, 30))
    for hip_x, hip_y, ankle_x in legs:
        line(pen, [(hip_x, hip_y), (ankle_x, FLOOR - 3)], (78, 68, 52), 3)
        foot(pen, ankle_x, (70, 60, 46), ink, 6)
    poly(pen, box, paper, ink, 2)
    poly(pen, [(box[0][0] + 6, box[0][1] + 4), (box[1][0] - 6, box[1][1] + 4),
               (box[2][0] - 8, box[2][1] - 4), (box[3][0] + 8, box[3][1] - 4)],
         bone, None)
    # spilled drawers and the mouth that is still open
    for k, (dx, dy) in enumerate(((16, 96), (58, 102), (86, 92))):
        top = dy + fall // 2
        poly(pen, [(dx, top), (dx + 24, top), (dx + 22, top + 10), (dx + 2, top + 10)],
             slate, ink, 1)
        line(pen, [(dx + 4, top + 3), (dx + 19, top + 3)], copper, 2)
    poly(pen, [(mouth[0], mouth[1]), (mouth[2], mouth[1]),
               (mouth[2] - 2, mouth[3]), (mouth[0] + 2, mouth[3])], petrol, ink, 2)
    for k in range(2):
        line(pen, [(mouth[0] + 4, mouth[1] + 4 + k * 5),
                   (mouth[2] - 5, mouth[1] + 4 + k * 5)], ink, 2)
    # curled paper limbs and loose sheets
    for side in (-1, 1):
        line(pen, [(cx + side * 34, 100 + fall // 2),
                   (cx + side * 44, 112), (cx + side * 50, FLOOR - 4)], paper, 2)
        poly(pen, [(cx + side * 50 - 2, FLOOR - 4),
                   (cx + side * 56, FLOOR - 2), (cx + side * 50, FLOOR)],
             bone, ink)
    for k in range(4):
        x, y = rng.randint(20, 100), rng.randint(98, 114)
        poly(pen, [(x, y), (x + rng.randint(4, 9), y), (x + rng.randint(2, 7), y + 4)],
             chalk, (126, 114, 92))
    foot(pen, 64, (60, 52, 42), ink, 10)
    return im

# -- Drowned Records: redacted choir ----------------------------------------
def redacted_choir(variant, state, frame, rng):
    sid = 'drowned_records'
    chalk, bone, paper, silt = C(sid, 'chalk'), C(sid, 'bone'), C(sid, 'paper'), C(sid, 'silt')
    petrol, slate = C(sid, 'petrol'), C(sid, 'slate')
    copper, copper_l, ink = C(sid, 'copper'), C(sid, 'copper_l'), C(sid, 'ink')
    im = blank()
    if state == 'death':
        return redacted_choir_death(variant, frame, rng)
    pen = ImageDraw.Draw(im)
    wide = variant == 'B'
    bob = (0, -1, 0, 1)[frame] if state in ('idle', 'walk') else (-1, -2, 0, 1)[frame]
    sway = {'idle': (0, 1, 0, -1), 'walk': (-3, 0, 3, 0),
            'warning': (-3, -2, 1, 2), 'attack': (0, 1, 2, 3),
            'hurt': (-5, -2, 2, 4)}[state][frame]
    pressure = {'idle': (0, 0, 0, 1), 'walk': (0, 1, 1, 2),
                'warning': (4, 8, 12, 16), 'attack': (16, 16, 16, 16),
                'hurt': (11, 7, 3, 1)}[state][frame]
    # thin wet paper legs
    feet = (40, 52, 76, 88) if not wide else (28, 42, 58, 72, 88, 102)
    for i, fx in enumerate(feet):
        step = 0
        if state == 'walk':
            step = (-4, 2, 4, -2)[(frame + i) % 4]
        elif state == 'warning':
            step = (-1, 0, 1, 2)[(frame + i) % 4]
        elif state == 'attack':
            step = (-3, -4, -2, -1)[(frame + i) % 4]
        line(pen, [(fx, 104), (fx + step, 114), (fx + step, FLOOR - 3)], slate, 2)
        foot(pen, fx + step, (76, 68, 54), ink, 5)
    # overlapping paper veils; A is a tall three-veil hunch, B a wider four-register pile
    if not wide:
        veils = [(37, 78, 92, 105, -2, 1.0), (31, 52, 97, 82, 2, 1.0),
                 (39, 30, 91, 58, -4, 0.9)]
    else:
        veils = [(22, 82, 72, 108, -2, 0.9), (57, 74, 105, 102, 3, 1.0),
                 (28, 56, 88, 84, 1, 1.0), (49, 36, 99, 64, -3, 0.9)]
    for i, (x0, y0, x1, y1, tilt, face_scale) in enumerate(veils):
        x0 += sway + tilt
        x1 += sway + tilt
        top = y0 + bob
        shoulder = 7 if i >= len(veils) - 2 else 4
        # hunched paper drape, wider at the shoulder, torn at the hem
        pts = [(x0 + 5, top), (x0 + 12, top - shoulder), (x1 - 15, top - shoulder + 2),
               (x1 - 3, top + 4), (x1, top + 12), (x1 - 4, y1),
               (x1 - 12, y1 - 3), (x0 + 14, y1 - 1), (x0 + 3, y1 - 5),
               (x0, top + 10)]
        poly(pen, pts, paper, ink, 2)
        # a second, lighter paper layer showing the hunch
        poly(pen, [(x0 + 9, top + 4), (x0 + 15, top - shoulder + 2),
                   (x1 - 17, top - shoulder + 4), (x1 - 7, top + 7),
                   (x1 - 12, top + 14), (x0 + 12, top + 14)], bone, None)
        # large blank almost-face. No eyes: a seam and rising ink only.
        inset = 11 if not wide else 9
        face = (x0 + inset, top + 10, x1 - inset, y1 - 7)
        if face[2] - face[0] > 10 and face[3] - face[1] > 10:
            poly(pen, [(face[0], face[1] + 2), (face[2], face[1]),
                       (face[2] - 2, face[3]), (face[0] + 2, face[3] - 2)],
                 chalk, (146, 134, 110))
            seam_y = face[1] + (face[3] - face[1]) * 2 // 3
            line(pen, [(face[0] + 3, seam_y), (face[2] - 3, seam_y)], slate, 2)
            if pressure:
                ph = max(2, (face[3] - face[1] - 4) * pressure // 16)
                poly(pen, [(face[0] + 3, face[3] - 2 - ph),
                           (face[2] - 3, face[3] - 3 - ph),
                           (face[2] - 3, face[3] - 2), (face[0] + 3, face[3] - 1)],
                     petrol, ink)
                line(pen, [(face[0] + 4, face[3] - 2 - ph),
                           (face[2] - 4, face[3] - 3 - ph)], copper, 1)
                if pressure >= 8:
                    dx = face[0] + 5 + (pressure * 3) % max(6, face[2] - face[0] - 10)
                    line(pen, [(dx, face[3] - 3), (dx, face[3] + 3 + pressure // 6)],
                         petrol, 2)
        # vertical drape folds and a wet edge
        for k in range(3):
            xx = x0 + 11 + k * max(5, (x1 - x0) // 4)
            line(pen, [(xx, top + 9), (xx - 2, y1 - 3)], (136, 124, 100), 1)
        line(pen, [(x0 + 8, y1 - 3), (x1 - 8, y1 - 5)], silt, 2)
        # B has side register drawers, making it read as a waterlogged filing stack
        if wide:
            side = x0 - 3 if i % 2 else x1 - 8
            poly(pen, [(side, top + 14), (side + 11, top + 16),
                       (side + 10, y1 - 10), (side - 1, y1 - 8)], slate, ink, 1)
            line(pen, [(side + 3, top + 18), (side + 8, top + 19)], copper, 2)
    # large copper pressure gauge, readable without a dark outline
    gx, gy = (30 if not wide else 20), (31 if not wide else 35)
    ellipse(pen, (gx - 9, gy - 9, gx + 9, gy + 9), copper, ink)
    ellipse(pen, (gx - 6, gy - 6, gx + 6, gy + 6), bone, ink)
    ang = math.radians(-150 + pressure * 8.5)
    line(pen, [(gx, gy), (gx + math.cos(ang) * 8, gy + math.sin(ang) * 8)], petrol, 2)
    for k in range(3):
        line(pen, [(gx - 5 + k * 4, gy + 5), (gx - 5 + k * 4, gy + 7)], slate, 1)
    # three wet paper tongues; warning is slow, attack is the existing fan pose
    if state in ('warning', 'attack', 'hurt'):
        reach = (6, 12, 18, 24)[frame] if state == 'warning' else (28, 34, 38, 40)[frame]
        if state == 'hurt':
            reach = (16, 10, 5, 2)[frame]
        for k, ang_deg in enumerate((-38, 0, 38)):
            ang = math.radians(ang_deg - 90)
            sx, sy = 64 + sway, 72 + bob
            ex = sx + math.cos(ang) * reach
            ey = sy + math.sin(ang) * reach
            poly(pen, [(sx - 5, sy), (sx + 5, sy), (ex + 4, ey + 4), (ex, ey + 10)],
                 paper, ink, 1)
            line(pen, [(sx, sy), (ex, ey + 5)], petrol, 2)
            if state == 'attack':
                ellipse(pen, (ex - 2, ey + 4, ex + 2, ey + 10), ink, None)
    return im

def redacted_choir_death(variant, frame, rng):
    sid = 'drowned_records'
    chalk, bone, paper, silt = C(sid, 'chalk'), C(sid, 'bone'), C(sid, 'paper'), C(sid, 'silt')
    petrol, slate = C(sid, 'petrol'), C(sid, 'slate')
    copper, copper_l, ink = C(sid, 'copper'), C(sid, 'copper_l'), C(sid, 'ink')
    im = blank()
    pen = ImageDraw.Draw(im)
    wide = variant == 'B'
    fall = (0, 4, 8, 12)[frame]
    # collapsed waterlogged paper heap, one blank face still visible
    for i in range(5 if wide else 4):
        x = 18 + i * (16 if wide else 20) + (4 if frame > 1 else 0)
        y = 96 + fall // 3 + (i % 2) * 4
        poly(pen, [(x, y), (x + 24, y - 3), (x + 28, y + 10), (x + 5, y + 13)],
             paper if i % 2 else bone, ink, 1)
    if wide:
        poly(pen, [(22, 94 + fall // 2), (102, 92 + fall // 2),
                   (104, 108 + fall // 2), (18, 110 + fall // 2)], paper, ink, 2)
        face = (34, 98 + fall // 2, 72, 106 + fall // 2)
    else:
        poly(pen, [(30, 98 + fall // 2), (94, 98 + fall // 2),
                   (98, 110 + fall // 2), (26, 110 + fall // 2)], paper, ink, 2)
        face = (40, 100 + fall // 2, 82, 108 + fall // 2)
    poly(pen, [(face[0], face[1]), (face[2], face[1]), (face[2], face[3]),
               (face[0], face[3])], chalk, (146, 134, 110))
    line(pen, [(face[0] + 4, face[1] + 5), (face[2] - 4, face[1] + 5)], slate, 2)
    # ink pool and a dark mouth
    poly(pen, [(34, 108 + fall // 3), (70, 106 + fall // 3),
               (74, 118), (30, 118)], petrol, ink)
    for k in range(4):
        x, y = rng.randint(24, 96), rng.randint(100, 114)
        poly(pen, [(x, y), (x + rng.randint(3, 7), y + 1),
                   (x + rng.randint(1, 5), y + 4)], (120, 108, 86), None)
    line(pen, [(30, 118), (78, 118)], copper, 1)
    foot(pen, 64, (58, 50, 40), ink, 10)
    return im


# -- Switchyard Chapel: insulator widow -------------------------------------
def insulator_widow(variant, state, frame, rng):
    sid = 'switchyard_chapel'
    ivory, porcelain, bone = C(sid, 'ivory'), C(sid, 'porcelain'), C(sid, 'bone')
    rust, rust_l, iron = C(sid, 'rust'), C(sid, 'rust_l'), C(sid, 'iron')
    charcoal, amber, amber_l = C(sid, 'charcoal'), C(sid, 'amber'), C(sid, 'amber_l')
    cable, oxide = C(sid, 'cable'), C(sid, 'oxide')
    im = blank()
    pen = ImageDraw.Draw(im)
    if state == 'death':
        return insulator_widow_death(variant, frame, rng)
    tall = variant == 'B'
    bob = {'idle': (0, -1, 0, 1), 'walk': (0, -2, 0, 2),
           'warning': (-2, -4, -5, -6), 'attack': (1, 2, 2, 3),
           'hurt': (3, 5, 3, 1)}[state][frame]
    sway = {'idle': (0, 1, 0, -1), 'walk': (-3, 0, 3, 0),
            'warning': (-1, 0, 1, 0), 'attack': (-6, -9, -11, -12),
            'hurt': (-4, -1, 2, 3)}[state][frame]
    rear = {'idle': 0, 'walk': 0, 'warning': (3, 6, 9, 11)[frame],
            'attack': 2, 'hurt': (1, 4, 6, 3)[frame]}[state]
    # cable legs first
    if not tall:
        body_y = 88 + bob - rear
        leg_xs = (26, 38, 50, 62, 76, 88, 100)
    else:
        body_y = 82 + bob - rear
        leg_xs = (46, 54, 62, 70, 78, 86)
    for i, lx in enumerate(leg_xs):
        step = 0
        if state == 'walk':
            step = (-5, 3, 5, -3)[(frame + i) % 4]
        elif state == 'warning':
            step = (-2, -1, 1, 2)[(frame + i) % 4]
        elif state == 'attack':
            step = (4, 7, 9, 10)[(frame + i) % 4]
        elif state == 'hurt':
            step = (-3, -2, 2, 3)[(frame + i) % 4]
        hip = (lx + sway // 2, body_y + 6)
        knee = (lx + step // 2, 107)
        ankle = (max(8, min(119, lx + step)), FLOOR - 3)
        line(pen, [hip, knee, ankle], cable, 4)
        line(pen, [(hip[0] + 1, hip[1]), (knee[0] + 1, knee[1])], (74, 68, 58), 1)
        poly(pen, [(knee[0] - 3, knee[1] - 2), (knee[0] + 4, knee[1] - 3),
                   (knee[0] + 3, knee[1] + 3), (knee[0] - 2, knee[1] + 2)], rust, oxide, 1)
        foot(pen, ankle[0], iron, oxide, 6)
    # ceramic body segments
    if not tall:
        discs = [(32 + sway, body_y - 2, 14, 10), (50 + sway, body_y - 6, 14, 10),
                 (68 + sway, body_y - 3, 14, 10), (86 + sway, body_y + 1, 13, 9)]
        head = (102 + sway, body_y - 1)
    else:
        discs = [(64 + sway, body_y + 8, 15, 10), (64 + sway, body_y - 7, 14, 9),
                 (64 + sway, body_y - 22, 13, 8)]
        head = (64 + sway, body_y - 34)
    for i, (cx, cy, rx, ry) in enumerate(discs):
        fluted_disc(pen, cx, cy, rx, ry, ivory if i % 2 else porcelain, bone, oxide, 4)
        # rust iron collar
        line(pen, [(cx - rx, cy + ry - 1), (cx + rx, cy + ry - 1)], rust, 2)
        bolt(pen, cx - rx + 3, cy, 1, rust_l, oxide)
    # amber pressure gaps in warning/attack
    if state in ('warning', 'attack', 'hurt'):
        spread = {'warning': (1, 2, 3, 4)[frame], 'attack': 4,
                  'hurt': (3, 2, 1, 0)[frame]}[state]
        for i in range(len(discs) - 1):
            x0 = (discs[i][0] + discs[i + 1][0]) // 2
            y0 = (discs[i][1] + discs[i + 1][1]) // 2
            for k in range(spread):
                poly(pen, [(x0 - 3, y0 - 2 + k * 3), (x0 + 3, y0 - 1 + k * 3),
                           (x0 + 2, y0 + 2 + k * 3), (x0 - 2, y0 + 1 + k * 3)],
                     amber, oxide)
    # head cap and amber lens
    hx, hy = head
    fluted_disc(pen, hx, hy, 8, 7, rust, rust_l, oxide, 3)
    ellipse(pen, (hx - 5, hy - 5, hx + 5, hy + 5), amber, oxide)
    ellipse(pen, (hx - 2, hy - 2, hx + 2, hy + 2), amber_l, None)
    line(pen, [(hx - 7, hy + 5), (hx + 7, hy + 5)], iron, 2)
    # cable whips / tail
    if tall:
        tail = [(64 + sway, body_y - 30), (80 + sway, body_y - 40),
                (92, body_y - 26), (88, body_y - 12)]
        line(pen, tail, cable, 4)
        line(pen, [(tail[0][0], tail[0][1] - 1), (tail[2][0], tail[2][1] - 1)],
             (88, 68, 52), 1)
        for x, y in ((92, body_y - 26), (88, body_y - 12)):
            bolt(pen, x, y, 2, rust_l, oxide)
    else:
        for side, sy in ((-1, body_y + 4), (1, body_y - 2)):
            start = (64 + sway + side * 20, sy)
            mid = (start[0] + side * 22, sy - 16 - rear)
            end = (start[0] + side * 30, sy - 6 - rear)
            line(pen, [start, mid, end], cable, 3)
            line(pen, [(start[0], start[1] - 1), (end[0], end[1] - 1)], (78, 70, 58), 1)
    # cracks on hurt / weathered ceramic
    if state == 'hurt':
        for cx, cy, rx, ry in discs[:2]:
            pts = [(cx - rx // 2, cy - ry // 2)]
            for k in range(3):
                pts.append((cx - rx // 2 + k * 5 + jitter(rng, 2),
                            cy - ry // 2 + 4 + k * 4))
            line(pen, pts, oxide, 1)
    if state in ('warning', 'attack'):
        for k in range(2):
            x = 64 + rng.randint(-26, 26)
            y = body_y - 18 + rng.randint(0, 18)
            ellipse(pen, (x - 2, y - 2, x + 2, y + 2), amber, oxide)
    return im


def insulator_widow_death(variant, frame, rng):
    sid = 'switchyard_chapel'
    ivory, porcelain, bone = C(sid, 'ivory'), C(sid, 'porcelain'), C(sid, 'bone')
    rust, rust_l, iron = C(sid, 'rust'), C(sid, 'rust_l'), C(sid, 'iron')
    charcoal, amber, amber_l = C(sid, 'charcoal'), C(sid, 'amber'), C(sid, 'amber_l')
    cable, oxide = C(sid, 'cable'), C(sid, 'oxide')
    im = blank()
    pen = ImageDraw.Draw(im)
    tall = variant == 'B'
    fall = (0, 4, 8, 12)[frame]
    # cable legs curled around a collapsed ceramic heap
    for i, lx in enumerate((30, 44, 58, 74, 88, 100)):
        line(pen, [(lx, 104 + fall // 2), (lx + (i % 2) * 8 - 4, 114),
                   (lx + (i % 3) * 6 - 6, FLOOR - 3)], cable, 3)
        foot(pen, lx + (i % 3) * 6 - 6, iron, oxide, 5)
    for i in range(3):
        cx = 34 + i * 22 + (8 if tall else 0)
        cy = 103 + fall // 2 + (i % 2) * 4
        fluted_disc(pen, cx, cy, 15, 7, ivory if i % 2 else porcelain, bone, oxide, 3)
        line(pen, [(cx - 10, cy - 2), (cx + 6, cy + 2)], oxide, 2)
        line(pen, [(cx + 2, cy - 5), (cx - 4, cy + 3)], rust, 2)
    ellipse(pen, (52, 108 + fall // 2, 64, 118), amber, oxide)
    ellipse(pen, (55, 111, 61, 116), amber_l, None)
    foot(pen, 64, charcoal, oxide, 10)
    return im


# -- Switchyard Chapel: transformer cantor ---------------------------------
def transformer_cantor(variant, state, frame, rng):
    sid = 'switchyard_chapel'
    ivory, porcelain, bone = C(sid, 'ivory'), C(sid, 'porcelain'), C(sid, 'bone')
    rust, rust_l, iron = C(sid, 'rust'), C(sid, 'rust_l'), C(sid, 'iron')
    charcoal, amber, amber_l = C(sid, 'charcoal'), C(sid, 'amber'), C(sid, 'amber_l')
    cable, oxide = C(sid, 'cable'), C(sid, 'oxide')
    im = blank()
    pen = ImageDraw.Draw(im)
    if state == 'death':
        return transformer_cantor_death(variant, frame, rng)
    tall = variant == 'B'
    bob = {'idle': (0, -1, 0, 1), 'walk': (0, 0, 1, 0),
           'warning': (-1, -2, -2, -1), 'attack': (0, 0, 1, 1),
           'hurt': (2, 4, 2, 1)}[state][frame]
    sway = {'idle': (0, 1, 0, -1), 'walk': (-1, 0, 1, 0),
            'warning': (-1, 0, 1, 0), 'attack': (0, 1, 2, 2),
            'hurt': (-3, -1, 2, 2)}[state][frame]
    rot = {'idle': (0, 1, 0, -1), 'walk': (-2, 0, 2, 0),
           'warning': (-3, -1, 2, 4), 'attack': (0, 1, 2, 3),
           'hurt': (3, 1, -2, -3)}[state][frame]
    spread = {'idle': 0, 'walk': 0, 'warning': (1, 2, 3, 4)[frame],
              'attack': (4, 5, 6, 7)[frame], 'hurt': (3, 2, 1, 0)[frame]}[state]
    # squat plinth / base, always grounded
    base_y = 104
    poly(pen, [(38, base_y), (90, base_y), (96, FLOOR - 3), (32, FLOOR - 3)],
         iron, oxide, 2)
    poly(pen, [(40, base_y + 2), (88, base_y + 2), (91, base_y + 11),
               (37, base_y + 11)], rust, oxide)
    for x in (40, 88):
        bolt(pen, x, base_y + 7, 2, rust_l, oxide)
    foot(pen, 48, charcoal, oxide, 10)
    foot(pen, 80, charcoal, oxide, 10)
    if not tall:
        cx, cy = 64 + sway, 82 + bob
        # radial crown of nine porcelain fins
        for k in range(9):
            ang = math.radians(190 + k * 20 + rot)
            dx, dy = math.cos(ang), math.sin(ang)
            px, py = -dy, dx
            r0, r1 = 10, 42 + spread
            w0, w1 = 4, 7
            pts = [(cx + dx * r0 + px * w0, cy + dy * r0 + py * w0),
                   (cx + dx * r1 + px * w1, cy + dy * r1 + py * w1),
                   (cx + dx * r1 - px * w1, cy + dy * r1 - py * w1),
                   (cx + dx * r0 - px * w0, cy + dy * r0 - py * w0)]
            poly(pen, pts, porcelain if k % 2 == 0 else ivory, oxide, 1)
            for t in (0.4, 0.7):
                rx = cx + dx * (r0 + (r1 - r0) * t)
                ry = cy + dy * (r0 + (r1 - r0) * t)
                ww = w0 + (w1 - w0) * t
                line(pen, [(rx + px * ww, ry + py * ww),
                           (rx - px * ww, ry - py * ww)], bone, 1)
        # hub and pressure gauges
        ellipse(pen, (cx - 14, cy - 14, cx + 14, cy + 14), charcoal, iron)
        ellipse(pen, (cx - 10, cy - 10, cx + 10, cy + 10), rust, oxide, 2)
        ellipse(pen, (cx - 4, cy - 4, cx + 4, cy + 4), amber, oxide)
        ellipse(pen, (cx - 2, cy - 2, cx + 2, cy + 2), amber_l, None)
        for k, (gx, gy) in enumerate(((38, 100), (64, 100), (90, 100))):
            ellipse(pen, (gx - 5, gy - 5, gx + 5, gy + 5), rust, oxide)
            ellipse(pen, (gx - 3, gy - 3, gx + 3, gy + 3), bone, oxide)
            ang2 = math.radians(-140 + spread * 12 + k * 5)
            line(pen, [(gx, gy), (gx + math.cos(ang2) * 4, gy + math.sin(ang2) * 4)],
                 charcoal, 1)
        # three nozzles for the existing slow fan pose
        if state in ('warning', 'attack', 'hurt'):
            reach = (7, 12, 17, 22)[frame] if state == 'warning' else (26, 31, 34, 36)[frame]
            if state == 'hurt':
                reach = (14, 9, 5, 2)[frame]
            for k, deg in enumerate((-32, 0, 32)):
                ang = math.radians(deg - 90 + frame * 2)
                sx, sy = cx, cy - 8
                ex = sx + math.cos(ang) * reach
                ey = sy + math.sin(ang) * reach
                poly(pen, [(sx - 3, sy), (sx + 3, sy), (ex + 2, ey + 3),
                           (ex, ey + 6)], amber if k != 1 else amber_l, oxide, 1)
                ellipse(pen, (ex - 2, ey + 2, ex + 2, ey + 6), oxide, None)
        # cable roots
        for side in (-1, 1):
            start = (cx + side * 12, cy + 8)
            end = (48 + side * 20, 112)
            line(pen, [start, (start[0] + side * 8, 104), end], cable, 4)
            line(pen, [(start[0], start[1] - 1), (end[0], end[1] - 1)],
                 (88, 72, 54), 1)
    else:
        cx, cy = 64 + sway, 82 + bob
        # vertical stack of porcelain drums
        drums = [(cx, cy - 24, 15, 8), (cx, cy - 6, 16, 9), (cx, cy + 12, 17, 9)]
        for i, (dx, dy, rx, ry) in enumerate(drums):
            fluted_disc(pen, dx, dy, rx, ry, porcelain if i % 2 == 0 else ivory, bone, oxide, 5)
            line(pen, [(dx - rx, dy + ry - 1), (dx + rx, dy + ry - 1)], rust, 2)
        # six fins around the stack
        for k in range(6):
            ang = math.radians(210 + k * 24 + rot)
            dx, dy = math.cos(ang), math.sin(ang)
            px, py = -dy, dx
            r0, r1 = 12, 30 + spread
            pts = [(cx + dx * r0 + px * 5, cy + dy * r0 + py * 5),
                   (cx + dx * r1 + px * 7, cy + dy * r1 + py * 7),
                   (cx + dx * r1 - px * 7, cy + dy * r1 - py * 7),
                   (cx + dx * r0 - px * 5, cy + dy * r0 - py * 5)]
            poly(pen, pts, ivory if k % 2 else porcelain, oxide, 1)
            line(pen, [(cx + dx * 18 + px * 6, cy + dy * 18 + py * 6),
                       (cx + dx * 18 - px * 6, cy + dy * 18 - py * 6)], bone, 1)
        # cable halo and three top nozzles
        line(pen, [(cx - 28, cy + 8), (cx - 20, cy - 26), (cx, cy - 40),
                   (cx + 21, cy - 25), (cx + 28, cy + 8)], cable, 4)
        for k, deg in enumerate((-30, 0, 30)):
            ang = math.radians(deg - 90 + frame * 2)
            sx, sy = cx, cy - 34
            reach = 8
            if state in ('warning', 'attack', 'hurt'):
                reach = (10, 15, 20, 25)[frame] if state == 'warning' else (28, 33, 36, 38)[frame]
                if state == 'hurt':
                    reach = (14, 9, 5, 2)[frame]
            ex = sx + math.cos(ang) * reach
            ey = sy + math.sin(ang) * reach
            poly(pen, [(sx - 3, sy), (sx + 3, sy), (ex + 2, ey + 3), (ex, ey + 6)],
                 amber if k != 1 else amber_l, oxide, 1)
        for gx, gy in ((38, 102), (64, 102), (90, 102)):
            ellipse(pen, (gx - 5, gy - 5, gx + 5, gy + 5), rust, oxide)
            ellipse(pen, (gx - 3, gy - 3, gx + 3, gy + 3), bone, oxide)
            ang2 = math.radians(-140 + spread * 12)
            line(pen, [(gx, gy), (gx + math.cos(ang2) * 4, gy + math.sin(ang2) * 4)],
                 charcoal, 1)
        line(pen, [(48, 112), (80, 112)], cable, 3)
    # ceramic damage
    if state == 'hurt':
        for k in range(3):
            x = 64 + rng.randint(-20, 20)
            y = 64 + rng.randint(-18, 18)
            line(pen, [(x, y), (x + 4, y + 3), (x + 2, y + 7)], oxide, 1)
    return im


def transformer_cantor_death(variant, frame, rng):
    sid = 'switchyard_chapel'
    ivory, porcelain, bone = C(sid, 'ivory'), C(sid, 'porcelain'), C(sid, 'bone')
    rust, rust_l, iron = C(sid, 'rust'), C(sid, 'rust_l'), C(sid, 'iron')
    charcoal, amber, amber_l = C(sid, 'charcoal'), C(sid, 'amber'), C(sid, 'amber_l')
    cable, oxide = C(sid, 'cable'), C(sid, 'oxide')
    im = blank()
    pen = ImageDraw.Draw(im)
    fall = (0, 4, 8, 12)[frame]
    # base survives, ring of broken fins collapses
    poly(pen, [(34, 106), (94, 106), (98, FLOOR - 3), (30, FLOOR - 3)], iron, oxide, 2)
    for x in (38, 90):
        bolt(pen, x, 112, 2, rust_l, oxide)
    for k in range(8):
        ang = math.radians(200 + k * 20)
        cx, cy = 64, 96 + fall // 2
        dx, dy = math.cos(ang), math.sin(ang)
        ex, ey = cx + dx * (26 + k % 3 * 4), cy + dy * (10 + k % 2 * 3)
        poly(pen, [(cx, cy), (ex + 4, ey), (ex, ey + 5), (cx - 3, cy + 3)],
             ivory if k % 2 else porcelain, oxide, 1)
    ellipse(pen, (52, 102 + fall // 2, 76, 116), charcoal, oxide)
    ellipse(pen, (58, 106 + fall // 2, 64, 112), amber, oxide)
    ellipse(pen, (60, 108, 62, 110), amber_l, None)
    for i, lx in enumerate((32, 44, 78, 94)):
        line(pen, [(lx, 108), (lx + (i % 2) * 8 - 4, 114), (lx + 2, FLOOR - 3)],
             cable, 3)
    foot(pen, 64, charcoal, oxide, 12)
    return im


# -- After Hours Pavilion: queue stalker ------------------------------------
def queue_stalker(variant, state, frame, rng):
    sid = 'after_hours_pavilion'
    plum, plum_d, plum_l = C(sid, 'plum'), C(sid, 'plum_d'), C(sid, 'plum_l')
    slate, terra, terra_d = C(sid, 'slate'), C(sid, 'terra'), C(sid, 'terra_d')
    brass, brass_l, cream = C(sid, 'brass'), C(sid, 'brass_l'), C(sid, 'cream')
    ink, dust = C(sid, 'ink'), C(sid, 'dust')
    im = blank()
    pen = ImageDraw.Draw(im)
    if state == 'death':
        return queue_stalker_death(variant, frame, rng)
    short = variant == 'B'
    bob = {'idle': (0, -1, 0, 1), 'walk': (0, -2, 0, 2),
           'warning': (-2, -3, -4, -3), 'attack': (1, 2, 2, 1),
           'hurt': (3, 5, 3, 1)}[state][frame]
    sway = {'idle': (0, 1, 0, -1), 'walk': (-4, 0, 4, 0),
            'warning': (-1, 0, 1, 0), 'attack': (-5, -7, -9, -10),
            'hurt': (-4, -1, 2, 3)}[state][frame]
    billow = {'idle': 0, 'walk': 1, 'warning': (1, 3, 5, 7)[frame],
              'attack': 7, 'hurt': (5, 3, 2, 1)[frame]}[state]
    top = (64 if short else 36) + bob
    bottom = (100 if short else 100) + bob + (8 if state == 'attack' else 0)
    x0, x1 = ((28 - billow + sway, 100 + billow + sway) if short
              else (36 - billow + sway, 92 + billow + sway))
    # articulated struts and feet
    struts = (38, 50, 62, 74, 86) if short else (38, 48, 58, 70, 80, 90)
    for i, sx in enumerate(struts):
        step = 0
        if state == 'walk':
            step = (-5, 3, 5, -3)[(frame + i) % 4]
        elif state == 'warning':
            step = (-3, -1, 1, 3)[(frame + i) % 4]
        elif state == 'attack':
            step = (-8, -10, -11, -12)[(frame + i) % 4]
        elif state == 'hurt':
            step = (-3, -2, 2, 3)[(frame + i) % 4]
        hip = (sx + sway // 2, bottom - 4)
        knee = (sx + step // 2, 110)
        ankle = (max(8, min(119, sx + step)), FLOOR - 3)
        line(pen, [hip, knee, ankle], slate, 3)
        line(pen, [(hip[0] + 1, hip[1]), (knee[0] + 1, knee[1])], brass, 1)
        bolt(pen, knee[0], knee[1], 1, brass_l, ink)
        foot(pen, ankle[0], slate, ink, 5)
    # coat: a folded empty service garment with no head
    poly(pen, [(x0 + 8, top), (x0 + 18, top - 7), ((x0 + x1) // 2, top - 3),
               (x1 - 18, top - 7), (x1 - 8, top), (x1, bottom - 10),
               (x1 - 12, bottom), (x0 + 12, bottom), (x0, bottom - 10)],
         plum, ink, 2)
    # lighter lapels / folded front
    poly(pen, [(x0 + 14, top + 4), ((x0 + x1) // 2, top + 16),
               ((x0 + x1) // 2, bottom - 4), (x0 + 5, bottom - 10)], plum_l, plum_d, 1)
    poly(pen, [((x0 + x1) // 2, top + 16), (x1 - 14, top + 4),
               (x1 - 5, bottom - 10), ((x0 + x1) // 2, bottom - 4)],
         plum_d, ink, 1)
    for k in range(3):
        x = x0 + 20 + k * max(6, (x1 - x0 - 40) // 2)
        line(pen, [(x, top + 20), (x - 2, bottom - 12)], plum_d, 1)
    # empty collar/hood: no face, just a dark opening and a brass hanger
    cx = (x0 + x1) // 2
    ellipse(pen, (cx - 13, top - 4, cx + 13, top + 12), ink, plum_d)
    ellipse(pen, (cx - 9, top - 1, cx + 9, top + 9), (58, 44, 56), plum_l, 1)
    line(pen, [(cx - 10, top - 5), (cx, top - 10), (cx + 10, top - 5)], brass, 2)
    # brass buttons and a queue-number blank, no text
    for k in range(3):
        bolt(pen, cx + (k - 1) * 9, top + 20 + k * 5, 2, brass, plum_d)
    poly(pen, [(cx - 15, bottom - 22), (cx + 15, bottom - 23),
               (cx + 13, bottom - 14), (cx - 13, bottom - 13)], cream, terra_d)
    line(pen, [(cx - 10, bottom - 19), (cx + 8, bottom - 19)], plum_d, 1)
    # sleeves: flat folded strips, raised in warning/attack
    for side in (-1, 1):
        shoulder = (cx + side * (x1 - x0) // 3, top + 14)
        if state in ('warning', 'attack', 'hurt'):
            reach = (4, 8, 12, 16)[frame] if state == 'warning' else (22, 28, 32, 34)[frame]
            if state == 'hurt':
                reach = (12, 7, 4, 2)[frame]
            wrist = (max(7, min(120, shoulder[0] + side * (8 + reach))), top + 26 + reach // 3)
        else:
            wrist = (shoulder[0] + side * 6, bottom - 22)
        elbow = ((shoulder[0] + wrist[0]) // 2 + side * 4, (shoulder[1] + wrist[1]) // 2)
        line(pen, [shoulder, elbow, wrist], plum_l, 6)
        line(pen, [shoulder, elbow, wrist], plum_d, 2)
        poly(pen, [(wrist[0] - 4, wrist[1] - 2), (wrist[0] + side * 8, wrist[1] + 1),
                   (wrist[0] + side * 5, wrist[1] + 6)], plum_d, ink, 1)
    # belt / queue loop hanging from the waist
    belt_y = bottom - 16
    line(pen, [(x0 + 8, belt_y), (x1 - 8, belt_y)], brass, 3)
    for k in range(2):
        bay = belt_y + 10 + k * 8
        line(pen, [(cx + 8, belt_y), (cx + 20 + billow, bay),
                   (cx + 12, bay + 7), (cx + 5, bay + 1)], plum_d, 3)
        line(pen, [(cx + 8, belt_y), (cx + 20 + billow, bay),
                   (cx + 12, bay + 7), (cx + 5, bay + 1)], brass, 1)
    if short:
        # two short brass stanchion poles make B a different silhouette
        for side in (-1, 1):
            px = 20 if side < 0 else 108
            line(pen, [(px, 80), (px, FLOOR - 3)], brass, 3)
            ellipse(pen, (px - 4, 76, px + 4, 84), brass_l, ink)
            foot(pen, px, slate, ink, 6)
    if state == 'hurt':
        for k in range(3):
            x, y = cx + rng.randint(-24, 24), top + rng.randint(14, 50)
            ellipse(pen, (x - 2, y - 2, x + 2, y + 2), brass_l, ink)
    return im


def queue_stalker_death(variant, frame, rng):
    sid = 'after_hours_pavilion'
    plum, plum_d, plum_l = C(sid, 'plum'), C(sid, 'plum_d'), C(sid, 'plum_l')
    slate, terra, terra_d = C(sid, 'slate'), C(sid, 'terra'), C(sid, 'terra_d')
    brass, brass_l, cream = C(sid, 'brass'), C(sid, 'brass_l'), C(sid, 'cream')
    ink, dust = C(sid, 'ink'), C(sid, 'dust')
    im = blank()
    pen = ImageDraw.Draw(im)
    short = variant == 'B'
    fall = (0, 4, 8, 12)[frame]
    # folded coat heap with one empty collar still visible
    poly(pen, [(18, 100 + fall // 2), (86, 96 + fall // 2),
               (102, 112 + fall // 2), (26, 116 + fall // 2)], plum, ink, 2)
    poly(pen, [(30, 104 + fall // 2), (74, 100 + fall // 2),
               (88, 110 + fall // 2), (38, 114 + fall // 2)], plum_l, plum_d, 1)
    for k in range(4):
        x = 28 + k * 16
        line(pen, [(x, 106 + fall // 2), (x - 4, 116), (x + 2, FLOOR - 3)],
             slate if k % 2 else plum_d, 3)
    ellipse(pen, (46, 92 + fall // 2, 70, 108 + fall // 2), ink, plum_d)
    ellipse(pen, (51, 96 + fall // 2, 65, 104 + fall // 2), (64, 48, 62), plum_l, 1)
    poly(pen, [(46, 86 + fall // 2), (58, 82 + fall // 2), (70, 87 + fall // 2),
               (66, 94 + fall // 2), (50, 94 + fall // 2)], plum, ink, 1)
    line(pen, [(50, 114), (76, 111)], brass, 2)
    if short:
        line(pen, [(16, 100), (16, FLOOR - 3)], brass, 3)
        line(pen, [(104, 100), (104, FLOOR - 3)], brass, 3)
    for k in range(3):
        x, y = rng.randint(24, 96), rng.randint(96, 114)
        poly(pen, [(x, y), (x + 5, y + 1), (x + 3, y + 4)], brass_l, None)
    foot(pen, 64, plum_d, ink, 10)
    return im


# -- After Hours Pavilion: usher cluster ------------------------------------
def usher_cluster(variant, state, frame, rng):
    sid = 'after_hours_pavilion'
    plum, plum_d, plum_l = C(sid, 'plum'), C(sid, 'plum_d'), C(sid, 'plum_l')
    slate, terra, terra_d = C(sid, 'slate'), C(sid, 'terra'), C(sid, 'terra_d')
    brass, brass_l, cream = C(sid, 'brass'), C(sid, 'brass_l'), C(sid, 'cream')
    ink, dust = C(sid, 'ink'), C(sid, 'dust')
    im = blank()
    pen = ImageDraw.Draw(im)
    if state == 'death':
        return usher_cluster_death(variant, frame, rng)
    triple = variant == 'B'
    bob = {'idle': (0, -1, 0, 1), 'walk': (0, 0, 1, 0),
           'warning': (-1, -2, -2, -1), 'attack': (0, 0, 1, 1),
           'hurt': (2, 4, 2, 1)}[state][frame]
    sway = {'idle': (0, 1, 0, -1), 'walk': (-2, 0, 2, 0),
            'warning': (-1, 0, 1, 0), 'attack': (0, 1, 2, 2),
            'hurt': (-3, -1, 2, 2)}[state][frame]
    unfold = {'idle': 0, 'walk': 1, 'warning': (1, 3, 5, 7)[frame],
              'attack': (9, 10, 11, 12)[frame], 'hurt': (6, 4, 2, 1)[frame]}[state]
    open_ = {'idle': 0, 'walk': 0, 'warning': (1, 2, 3, 4)[frame],
             'attack': (5, 6, 7, 8)[frame], 'hurt': (3, 2, 1, 0)[frame]}[state]
    # heavy base
    poly(pen, [(24, 104), (100, 104), (106, FLOOR - 3), (18, FLOOR - 3)],
         plum_d, ink, 2)
    poly(pen, [(28, 106), (96, 106), (99, FLOOR - 5), (25, FLOOR - 5)],
         terra, terra_d, 1)
    line(pen, [(28, 110), (96, 110)], brass, 2)
    for x in (24, 100):
        bolt(pen, x, 112, 2, brass_l, ink)
    foot(pen, 40, slate, ink, 8)
    foot(pen, 88, slate, ink, 8)
    # faces: A twin, B triple, with split plum/terrazzo skins
    if not triple:
        faces = [(30, 30, 98, 68, 1, (38, 42, 76, open_)),
                 (26, 64, 100, 104, -1, (36, 78, 72, open_)),
                 (74, 84, 94, 98, 1, (78, 88, 90, open_))]
    else:
        faces = [(14, 54, 46, 104, 1, (20, 66, 40, open_)),
                 (42, 40, 76, 104, -1, (49, 54, 69, open_)),
                 (72, 48, 106, 104, 1, (79, 60, 100, open_)),
                 (50, 84, 86, 98, -1, (58, 87, 78, open_))]
    for i, (x0, y0, x1, y1, tilt, ap) in enumerate(faces):
        x0 += sway + tilt
        x1 += sway + tilt
        top = y0 + bob
        bottom = y1
        # brass frame and split skin
        poly(pen, [(x0, top), (x1, top + 2), (x1 + 1, bottom), (x0 - 1, bottom)],
             brass, (82, 58, 32), 2)
        mid = (x0 + x1) // 2
        poly(pen, [(x0 + 4, top + 4), (mid, top + 5), (mid, bottom - 4),
                   (x0 + 4, bottom - 4)], plum if i % 2 else terra, ink, 1)
        poly(pen, [(mid + 1, top + 5), (x1 - 4, top + 4),
                   (x1 - 4, bottom - 4), (mid + 1, bottom - 4)],
             terra if i % 2 else plum_l, ink, 1)
        line(pen, [(mid, top + 3), (mid, bottom - 3)], brass_l, 1)
        # empty aperture: no eye, no reflection; it widens only when warning
        ax0, ay0, ax1, _ = ap
        ax0 += sway
        ax1 += sway
        ay0 += bob
        grow = open_ * 2
        aperture = (max(x0 + 6, ax0 - grow), max(top + 6, ay0 - grow),
                    min(x1 - 6, ax1 + grow), min(bottom - 6, ay0 + 10 + grow))
        if aperture[2] > aperture[0] and aperture[3] > aperture[1]:
            poly(pen, [(aperture[0], aperture[1]), (aperture[2], aperture[1] + 1),
                       (aperture[2] - 1, aperture[3]), (aperture[0] + 1, aperture[3] - 1)],
                 ink, plum_d, 2)
            if open_ >= 2:
                # a shallow brass ticket lip, not a portal
                line(pen, [(aperture[0] + 2, aperture[3] - 1),
                           (aperture[2] - 2, aperture[3] - 2)], brass, 2)
        # blank directory plate / banner
        if y1 - y0 > 30:
            poly(pen, [(x0 + 7, bottom - 18), (x1 - 7, bottom - 19),
                       (x1 - 8, bottom - 12), (x0 + 8, bottom - 11)], cream, terra_d)
            line(pen, [(x0 + 11, bottom - 16), (x1 - 12, bottom - 16)], plum_d, 1)
        bolt(pen, x0 + 2, top + 3, 1, brass_l, ink)
    # folded brass baffles at the edges; they unfold in warning
    baffles = ((10, 58, 28, 100), (98, 54, 116, 100)) if not triple else (
        (6, 64, 24, 100), (66, 62, 84, 98), (98, 54, 118, 100))
    for bx0, by0, bx1, by1 in baffles:
        ext = unfold * 2
        poly(pen, [(bx0, by0), (bx0 + 9 - ext // 2, by0 - 3),
                   (bx0 + 18, by0 + 4), (bx1 + ext, by1), (bx0 + 2, by1)],
             brass, (82, 58, 32), 1)
        line(pen, [(bx0 + 4, by0 + 4), (bx1 + ext - 2, by1 - 2)], brass_l, 2)
        line(pen, [(bx0 + 9, by0 + 2), (bx0 + 13, by1 - 2)], plum_d, 1)
    # pressure flags and three tongues
    for k in range(3):
        fx = (40 + k * 20 + sway) if not triple else (26 + k * 28 + sway)
        poly(pen, [(fx, 100 - open_ * 2), (fx + 4, 100 - open_ * 3),
                   (fx + 7, 100 - open_ * 2)], brass_l, (82, 58, 32))
    if state in ('warning', 'attack', 'hurt'):
        reach = (6, 12, 18, 24)[frame] if state == 'warning' else (28, 34, 38, 40)[frame]
        if state == 'hurt':
            reach = (16, 10, 5, 2)[frame]
        for k, deg in enumerate((-34, 0, 34)):
            ang = math.radians(deg - 90 + (frame - 1.5) * 3)
            sx, sy = 64 + sway, 70 + bob
            ex = sx + math.cos(ang) * reach
            ey = sy + math.sin(ang) * reach
            poly(pen, [(sx - 4, sy), (sx + 4, sy), (ex + 4, ey + 4), (ex, ey + 9)],
                 cream if k == 1 else paper_color(sid), (82, 58, 32), 1)
            line(pen, [(sx, sy), (ex, ey + 5)], plum_d, 2)
    if state == 'hurt':
        for k in range(3):
            x, y = 64 + rng.randint(-30, 30), 60 + rng.randint(-18, 30)
            poly(pen, [(x, y), (x + 5, y + 1), (x + 3, y + 4)], cream, None)
    return im


def paper_color(sid):
    return C(sid, 'cream') if sid == 'after_hours_pavilion' else C(sid, 'bone')


def usher_cluster_death(variant, frame, rng):
    sid = 'after_hours_pavilion'
    plum, plum_d, plum_l = C(sid, 'plum'), C(sid, 'plum_d'), C(sid, 'plum_l')
    slate, terra, terra_d = C(sid, 'slate'), C(sid, 'terra'), C(sid, 'terra_d')
    brass, brass_l, cream = C(sid, 'brass'), C(sid, 'brass_l'), C(sid, 'cream')
    ink, dust = C(sid, 'ink'), C(sid, 'dust')
    im = blank()
    pen = ImageDraw.Draw(im)
    fall = (0, 4, 8, 12)[frame]
    poly(pen, [(18, 104), (96, 102), (106, 116), (14, 118)], plum_d, ink, 2)
    poly(pen, [(24, 98 + fall // 2), (92, 94 + fall // 2),
               (100, 110 + fall // 2), (20, 112 + fall // 2)], brass, (82, 58, 32), 2)
    for i in range(3):
        x = 24 + i * 24
        y = 92 + fall // 2 + (i % 2) * 4
        poly(pen, [(x, y), (x + 20, y - 2), (x + 22, y + 18), (x + 2, y + 20)],
             plum if i % 2 else terra, ink, 1)
        poly(pen, [(x + 7, y + 5), (x + 16, y + 4), (x + 15, y + 13), (x + 6, y + 14)],
             ink, plum_d, 1)
    for k in range(3):
        bx0, by0 = 14 + k * 30, 104
        poly(pen, [(bx0, by0), (bx0 + 18, by0 + 2), (bx0 + 24, by0 + 12),
                   (bx0 + 2, by0 + 12)], brass, (82, 58, 32), 1)
    for k in range(4):
        x, y = rng.randint(20, 94), rng.randint(94, 114)
        poly(pen, [(x, y), (x + 6, y + 1), (x + 4, y + 4)], cream, None)
    foot(pen, 64, plum_d, ink, 10)
    return im


DESIGNS = {
    'drowned_records': {
        'latchwing': ('shelf_widow', shelf_widow),
        'relay_choir': ('redacted_choir', redacted_choir),
    },
    'switchyard_chapel': {
        'latchwing': ('insulator_widow', insulator_widow),
        'relay_choir': ('transformer_cantor', transformer_cantor),
    },
    'after_hours_pavilion': {
        'latchwing': ('queue_stalker', queue_stalker),
        'relay_choir': ('usher_cluster', usher_cluster),
    },
}


def mob_seed(seed, set_index, slot_index, variant_index, state_index, frame):
    return (int(seed) * 1000003 + set_index * 104729 + slot_index * 7919
            + variant_index * 1291 + state_index * 137 + frame) & 0x7FFFFFFF


def build_atlas(set_id, slot, variant, seed):
    set_index = SET_IDS.index(set_id)
    slot_index = SLOTS.index(slot)
    variant_index = 0 if variant == 'A' else 1
    fn = DESIGNS[set_id][slot][1]
    atlas = Image.new('RGBA', (COLS * SIZE, ROWS * SIZE), (0, 0, 0, 0))
    for row, state in enumerate(STATES):
        for col in range(COLS):
            rng = random.Random(mob_seed(seed, set_index, slot_index, variant_index,
                                         row, col))
            frame = finalize(fn(variant, state, col, rng))
            atlas.paste(frame, (col * SIZE, row * SIZE))
    return atlas


def encounters_document(seed):
    sets = {}
    for set_id in SET_IDS:
        sets[set_id] = {}
        for slot in SLOTS:
            design, display, description, warning, limits = IDENTITIES[set_id][slot]
            sets[set_id][slot] = {
                'id': design,
                'name': display,
                'description': description,
                'behavior_family': slot,
                'warning_notes': warning,
                'limits': limits,
                'atlas': f'mobs/{set_id}/{slot}_A.png and mobs/{set_id}/{slot}_B.png',
            }
    return {
        'format': 'nullrun-environment-mobs-1',
        'source_seed': int(seed),
        'license': 'GPL-2.0-or-later',
        'title': 'Null Run signature mobs for the three environment kits',
        'behavior_families': {
            'latchwing': ('Existing class 15 CYBR family: telegraphed locked-direction '
                          'dash. These six designs use it unchanged.'),
            'relay_choir': ('Existing class 16 PAIN family: anchored telegraphed slow '
                            'three-projectile fan. These six designs use it unchanged.'),
        },
        'notes': [
            'Art only. Six new identities use two existing behavior families; no new AI, actor IDs, frame mapping or mechanics are introduced.',
            'A and B are two variants of the same design and behavior family; they differ in shape and detail, not merely color.',
            'Codex owns behavior, labels, native frame mapping, collision and visual validation.',
            'The atlases are static art: four frames per state, six states, 128x128 cells in a 512x768 RGBA sheet.',
        ],
        'sets': sets,
    }


def get_font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


SHEET_BG = (24, 24, 30)
SHEET_TEXT = (230, 226, 214)
SHEET_MUTED = (166, 164, 154)
SHEET_ACCENT = (214, 184, 120)


def checkerboard(w, h, cell=32):
    im = Image.new('RGB', (w, h), (54, 50, 60))
    d = ImageDraw.Draw(im)
    for y in range(0, h, cell):
        for x in range(0, w, cell):
            if (x // cell + y // cell) % 2:
                d.rectangle((x, y, min(w - 1, x + cell - 1), min(h - 1, y + cell - 1)),
                            fill=(72, 66, 78))
    return im


def centered(d, x, y, text, font, fill=SHEET_TEXT):
    d.text((x, y), text, font=font, fill=fill, anchor='mm')


def left_text(d, x, y, text, font, fill=SHEET_TEXT):
    d.text((x, y), text, font=font, fill=fill, anchor='la')


def compose_mob_sheet(set_id, seed):
    width, height = 1180, 1810
    sheet = Image.new('RGB', (width, height), SHEET_BG)
    d = ImageDraw.Draw(sheet)
    f_title, f_sub, f_head, f_label, f_small = (
        get_font(30), get_font(14), get_font(17), get_font(13), get_font(11))
    set_name = {
        'drowned_records': 'DROWNED RECORDS',
        'switchyard_chapel': 'SWITCHYARD CHAPEL',
        'after_hours_pavilion': 'AFTER HOURS PAVILION',
    }[set_id]
    left_text(d, 34, 22, f'{set_name} - signature mobs', f_title)
    left_text(d, 34, 62, f'Seed {seed}  |  512x768 RGBA atlases at 1x, all 24 frames. '
                         'Rows: idle, walk, warning, attack, hurt, death. Columns: frames 1-4. '
                         'Mid-dark checkerboard; no filtering.', f_sub, SHEET_MUTED)
    for design_index, slot in enumerate(SLOTS):
        design_id, display, _, _, _ = IDENTITIES[set_id][slot]
        block_y = 100 + design_index * 840
        left_text(d, 34, block_y, f'{slot.upper()} SLOT  /  {design_id}  /  {display}',
                  f_head, SHEET_ACCENT)
        for variant_index, variant in enumerate(('A', 'B')):
            atlas = build_atlas(set_id, slot, variant, seed)
            board = checkerboard(512, 768)
            board.paste(atlas, (0, 0), atlas)
            x = 74 + variant_index * 548
            y = block_y + 34
            sheet.paste(board, (x, y))
            d.rectangle((x - 1, y - 1, x + 512, y + 768), outline=(76, 78, 88))
            left_text(d, x, y - 20, f'variant {variant}', f_label, SHEET_TEXT)
            if variant == 'A':
                for row, state in enumerate(STATES):
                    left_text(d, 34, y + row * 128 + 58, state, f_small, SHEET_MUTED)
                for col in range(4):
                    centered(d, x + col * 128 + 64, y - 8, f'{col + 1}', f_small, SHEET_MUTED)
    left_text(d, 34, 1778, 'Static original art. A/B differ in shape and detail. '
                           'No fabricated screenshots or native renderer acceptance.',
              f_small, SHEET_MUTED)
    return sheet


def compose_creepy_board(seed):
    width, height = 1180, 1410
    sheet = Image.new('RGB', (width, height), SHEET_BG)
    d = ImageDraw.Draw(sheet)
    f_title, f_sub, f_head, f_label, f_small = (
        get_font(30), get_font(14), get_font(17), get_font(13), get_font(11))
    left_text(d, 34, 22, 'DROWNED RECORDS - creepy signature mobs', f_title)
    left_text(d, 34, 62, 'Detail board at 2x: idle, warning (frame 4), attack (frame 4), '
                         'death (frame 4). Original art, no game screenshots.', f_sub, SHEET_MUTED)
    states = (('idle', 0), ('warning', 3), ('attack', 3), ('death', 3))
    for design_index, slot in enumerate(SLOTS):
        design_id, display, _, _, _ = IDENTITIES['drowned_records'][slot]
        block_y = 100 + design_index * 650
        left_text(d, 34, block_y, f'{design_id}  /  {display}', f_head, SHEET_ACCENT)
        for variant_index, variant in enumerate(('A', 'B')):
            atlas = build_atlas('drowned_records', slot, variant, seed)
            row_y = block_y + 34 + variant_index * 268
            left_text(d, 34, row_y + 120, f'variant {variant}', f_label, SHEET_MUTED)
            for col, (state, frame) in enumerate(states):
                cell = atlas.crop((frame * 128, STATES.index(state) * 128,
                                   frame * 128 + 128, STATES.index(state) * 128 + 128))
                board = checkerboard(256, 256, 32)
                board.paste(cell.resize((256, 256), Image.Resampling.NEAREST), (0, 0),
                            cell.resize((256, 256), Image.Resampling.NEAREST))
                x = 100 + col * 264
                sheet.paste(board, (x, row_y))
                d.rectangle((x - 1, row_y - 1, x + 256, row_y + 256), outline=(78, 80, 90))
                centered(d, x + 128, row_y - 10, state, f_small,
                         SHEET_TEXT if variant == 'A' else SHEET_MUTED)
    left_text(d, 34, 1348, 'Shelf Widow: a filing shelf opening into a dark, long-limbed '
                           'negative space. Redacted Choir: blank paper veils with a slow '
                           'ink-pressure warning and three wet tongues.', f_sub, SHEET_MUTED)
    left_text(d, 34, 1378, 'These are art theses, not native sprites or gameplay claims.',
              f_small, SHEET_MUTED)
    return sheet


def write_mobs(out, seed=DEFAULT_SEED):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'sheets').mkdir(parents=True, exist_ok=True)
    for set_id in SET_IDS:
        for slot in SLOTS:
            for variant in ('A', 'B'):
                atlas = build_atlas(set_id, slot, variant, seed)
                path = out / 'mobs' / set_id / f'{slot}_{variant}.png'
                path.parent.mkdir(parents=True, exist_ok=True)
                atlas.save(path, format='PNG', compress_level=9)
        compose_mob_sheet(set_id, seed).save(
            out / 'sheets' / f'{set_id}-mobs.png', format='PNG', compress_level=9)
    compose_creepy_board(seed).save(
        out / 'sheets' / 'drowned-records-creepy.png', format='PNG', compress_level=9)
    doc = encounters_document(seed)
    (out / 'encounters.json').write_text(json.dumps(doc, indent=2) + '\n', encoding='utf-8')
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description='Generate six Null Run signature mob designs.')
    parser.add_argument('--out', required=True, help='output directory')
    parser.add_argument('--seed', type=int, default=DEFAULT_SEED,
                        help=f'integer seed (default {DEFAULT_SEED})')
    args = parser.parse_args(argv)
    out = write_mobs(args.out, args.seed)
    print(f'wrote 12 atlases (288 frames), 3 mob sheets, the creepy board and encounters.json to {out}')


if __name__ == '__main__':
    main()
