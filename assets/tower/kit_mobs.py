# SPDX-License-Identifier: GPL-2.0-or-later
"""Deterministic 24-frame mob atlases for the tower environment bank.

Six original identities, each with A and B structural variants.  Every atlas is
512x768 RGBA: four columns x six rows of 128x128 cells.  Rows are idle, walk,
warn, attack, hurt, death.  Frame 23 is a visible corpse.  Feet/corpse bases sit
at y=120 in every cell.  This file supplies art only: the two adapter roles are
the existing latchwing (class 15 CYBR) and relay_choir (class 16 PAIN) families.
All vertical-behaviour text in kit_common is a proposal, not implemented AI.
"""
from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import kit_common as K
from kit_art import bell_shape, root_branch

SIZE = 128
COLS, ROWS = 4, 6
STATES = K.STATES
FLOOR = 120


def pose(state, col):
    p = {'bob': 0.0, 'sway': 0.0, 'charge': 0.0, 'lunge': 0.0,
         'recoil': 0.0, 'fall': 0.0, 'phase': col, 'pulse': col,
         'gait': 1.0 if state == 'walk' else 0.0}
    if state == 'idle':
        p['bob'] = (0, 1, 0, -1)[col]
        p['sway'] = (-1, 0, 1, 0)[col]
    elif state == 'walk':
        p['bob'] = (0, 1, 1, 0)[col]
        p['sway'] = (-1, 0, 1, 0)[col]
        p['phase'] = (0, 1, 2, 3)[col]
    elif state == 'warn':
        p['charge'] = (0.35, 0.55, 0.8, 1.0)[col]
        p['bob'] = (1, 0, -1, -2)[col]
    elif state == 'attack':
        p['lunge'] = (0.5, 1.0, 0.8, 0.4)[col]
        p['bob'] = (0, -1, 0, 1)[col]
    elif state == 'hurt':
        p['recoil'] = (0.65, 0.8, 1.0, 0.5)[col]
        p['bob'] = (0, -1, -2, -1)[col]
    elif state == 'death':
        p['fall'] = (0.3, 0.5, 0.75, 1.0)[col]
    return p


def canvas():
    return Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))


def _chain_limb(pen, x0, y0, x1, y1, main, edge, links=4, r=3):
    pen.line((x0, y0, x1, y1), fill=edge, width=2)
    for i in range(links):
        t = i / (links - 1) if links > 1 else 0
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        pen.ellipse((x - r, y - r * 1.2, x + r, y + r * 1.2), outline=edge, width=2)
        pen.ellipse((x - r + 1, y - r + 1, x + r - 1, y + r - 1), outline=main, width=1)


def _hook_foot(pen, x, y, main, edge):
    pen.arc((x - 4, y - 8, x + 4, y), 0, 180, fill=edge, width=3)
    pen.arc((x - 3, y - 7, x + 3, y - 1), 0, 180, fill=main, width=1)
    pen.line((x - 4, y, x + 4, y), fill=edge, width=2)


def _suitcase(pen, x0, y0, w, h, body, edge, brass, handle=True):
    pen.rectangle((x0, y0, x0 + w, y0 + h), fill=body, outline=edge)
    pen.line((x0 + 2, y0 + 3, x0 + w - 2, y0 + 3), fill=brass)
    pen.line((x0 + 2, y0 + h - 3, x0 + w - 2, y0 + h - 3), fill=brass)
    if handle:
        pen.arc((x0 + w // 2 - 6, y0 - 4, x0 + w // 2 + 6, y0 + 4), 180, 360,
                fill=brass, width=2)
    pen.rectangle((x0 + w // 2 - 2, y0 + 2, x0 + w // 2 + 2, y0 + 5), fill=brass)


def _cap(pen, cx, top, w, body, dark, brass, tilt=0.0, badge=True):
    # peaked cap: a trapezoid crown and a forward peak
    crown = [(cx - w // 2 + tilt * 3, top + 6), (cx - w // 2 + 2 + tilt * 4, top),
             (cx + w // 2 - 2 + tilt * 4, top), (cx + w // 2 + tilt * 3, top + 6)]
    pen.polygon(crown, fill=body, outline=dark)
    pen.line((crown[1][0], crown[1][1] + 1, crown[2][0], crown[2][1] + 1), fill=brass)
    pen.polygon([(cx + w // 2 - 6 + tilt * 4, top + 6),
                 (cx + w // 2 + 10 + tilt * 4, top + 9),
                 (cx + w // 2 + 8 + tilt * 4, top + 12),
                 (cx + w // 2 - 8 + tilt * 4, top + 10)], fill=body, outline=dark)
    if badge:
        pen.ellipse((cx - 3, top + 7, cx + 3, top + 13), fill=brass, outline=dark)


def _blank_face(pen, box, skin, dark):
    x0, y0, x1, y1 = box
    pen.rounded_rectangle(box, radius=5, fill=skin, outline=dark)
    pen.ellipse((x0 + 4, y0 + 5, x0 + 7, y0 + 8), fill=dark)
    pen.ellipse((x1 - 7, y0 + 5, x1 - 4, y0 + 8), fill=dark)
    pen.line((x0 + 6, y1 - 6, x1 - 6, y1 - 6), fill=dark)


# -- 1. Chain Hound ----------------------------------------------------------
def draw_chain_hound(p, variant):
    sid = 'ashbell_foundry'
    soot, iron, iron_l = K.C(sid, 'soot'), K.C(sid, 'iron'), K.C(sid, 'iron_light')
    bronze, bronze_l = K.C(sid, 'bronze'), K.C(sid, 'bronze_light')
    verd, verd_l = K.C(sid, 'verdigris'), K.C(sid, 'verdigris_light')
    furn, furn_l = K.C(sid, 'furnace'), K.C(sid, 'furnace_light')
    im = canvas()
    pen = ImageDraw.Draw(im)
    charge, lunge, recoil, fall = p['charge'], p['lunge'], p['recoil'], p['fall']
    bob = p['bob']
    bx = int(p['sway'] + lunge * 9 - recoil * 5)
    by = int(bob + charge * 3 - lunge * 2 - recoil * 3 + fall * 24)
    # corpse is explicitly low and wide
    if fall > 0.82:
        pen.ellipse((30, 102, 96, 118), fill=iron, outline=soot)
        pen.polygon([(34, 104), (58, 98), (90, 100), (98, 110), (82, 118), (38, 118)],
                    fill=iron, outline=soot)
        for x in (38, 50, 62, 74, 86):
            pen.ellipse((x, 112, x + 10, 120), outline=bronze, width=2)
        # fallen muzzle and clapper
        pen.polygon([(92, 104), (114, 100), (118, 110), (112, 118), (94, 116)],
                    fill=bronze, outline=(54, 34, 16))
        pen.ellipse((110, 106, 118, 114), fill=furn, outline=furn_l)
        pen.ellipse((116, 108, 122, 114), fill=bronze_l, outline=soot)
        # chain pile and counterweight
        for x, y in ((14, 110), (22, 116), (30, 108), (8, 104)):
            pen.ellipse((x, y, x + 10, y + 8), outline=bronze, width=2)
        pen.rectangle((4, 100, 16, 112), fill=iron_l, outline=soot)
        return im
    torso = [(34 + bx, 62 + by), (86 + bx, 56 + by), (96 + bx, 66 + by),
             (92 + bx, 82 + by), (40 + bx, 84 + by), (28 + bx, 74 + by)]
    # tail chain and counterweight
    tail_len = 20 if variant == 'A' else 30
    pen.line((30 + bx, 64 + by, 30 + bx - tail_len, 70 + by + recoil * 4), fill=soot, width=2)
    for i in range(3 + (variant == 'B')):
        t = (i + 1) / (4 + (variant == 'B'))
        x = 30 + bx - tail_len * t
        y = 64 + by + (6 + recoil * 4) * t
        pen.ellipse((x - 3, y - 3, x + 3, y + 3), outline=bronze, width=2)
    if variant == 'A':
        pen.rectangle((30 + bx - tail_len - 8, 76 + by, 30 + bx - tail_len + 2, 88 + by),
                      fill=iron_l, outline=soot)
    else:
        pen.rectangle((30 + bx - tail_len - 10, 72 + by, 30 + bx - tail_len + 2, 84 + by),
                      fill=iron_l, outline=soot)
        pen.rectangle((30 + bx - tail_len + 2, 80 + by, 30 + bx - tail_len + 12, 90 + by),
                      fill=iron, outline=soot)
    # legs: A four, B six; feet stay on y=120
    hips = ([-16, -4, 12, 24] if variant == 'A' else [-22, -12, -2, 8, 18, 28])
    feet = ([30, 48, 72, 90] if variant == 'A' else [22, 40, 54, 68, 86, 100])
    for i, (hx, fx) in enumerate(zip(hips, feet)):
        phase = (p['phase'] + i) % 4
        amp = 4 if p['gait'] else 1
        stride = (0, amp, 0, -amp)[phase] if charge < 0.3 and lunge < 0.3 else 0
        coil = charge * 6
        hx2 = 64 + hx + bx * 0.5
        fy = FLOOR
        fx2 = fx + stride + bx * 0.2 + lunge * (6 if i < len(feet) // 2 else -2)
        midx = (hx2 + fx2) / 2 + (coil if i % 2 == 0 else -coil)
        midy = 100 + by * 0.34
        _chain_limb(pen, hx2, 80 + by * 0.3, midx, midy, bronze if i % 2 else iron_l, soot, 3, 3)
        _chain_limb(pen, midx, midy, fx2, fy - 2, bronze if i % 2 else iron_l, soot, 3, 3)
        _hook_foot(pen, fx2, fy, bronze, soot)
    # drum body
    pen.polygon(torso, fill=iron, outline=soot)
    pen.line((36 + bx, 60 + by, 84 + bx, 55 + by), fill=iron_l, width=2)
    for x in (44, 62, 80):
        pen.line((x + bx, 57 + by, x + bx, 83 + by), fill=bronze)
        pen.line((x + bx + 1, 58 + by, x + bx + 1, 82 + by), fill=(74, 48, 20))
        bolt = 2
        pen.ellipse((x - 2 + bx, 66 + by, x + 2 + bx, 70 + by), fill=bronze_l, outline=soot)
    # mane links
    count = 5 if variant == 'A' else 7
    for i in range(count):
        x = 38 + i * (46 // max(1, count - 1)) + bx
        sway = charge * (4 if i % 2 else -4) + recoil * 2 + (p['pulse'] - 1.5) * 1.5
        y = 54 + by + (i % 3) * 2 + (p['pulse'] % 2)
        pen.ellipse((x - 3 + sway, y, x + 3 + sway, y + 9), outline=verd, width=2)
    # neck and muzzle
    nx = 88 + bx + lunge * 6
    pen.line((nx - 4, 64 + by, nx + 8, 62 + by), fill=iron, width=7)
    if variant == 'A':
        mx = nx + 4 - recoil * 3
        pen.polygon([(mx, 56 + by), (mx + 20, 50 + by), (mx + 28, 58 + by),
                     (mx + 28, 76 + by), (mx + 20, 84 + by), (mx, 78 + by)],
                    fill=bronze, outline=(54, 34, 16))
        pen.ellipse((mx + 20, 54 + by, mx + 30, 80 + by), fill=(28, 18, 12), outline=bronze_l)
        pen.line((mx + 2, 58 + by, mx + 20, 54 + by), fill=bronze_l, width=2)
        pen.ellipse((mx + 22, 66 + by, mx + 27, 71 + by), fill=furn, outline=furn_l)
        pen.line((mx + 18, 70 + by, mx + 24, 76 + by), fill=soot, width=2)
        pen.ellipse((mx + 22, 74 + by, mx + 28, 80 + by), fill=bronze_l, outline=soot)
    else:
        mx = nx + 2 - recoil * 3
        for oy in (0, 14):
            pen.polygon([(mx, 54 + by + oy), (mx + 16, 50 + by + oy), (mx + 22, 58 + by + oy),
                         (mx + 22, 72 + by + oy), (mx + 16, 78 + by + oy), (mx, 74 + by + oy)],
                        fill=bronze, outline=(54, 34, 16))
            pen.ellipse((mx + 15, 56 + by + oy, mx + 24, 74 + by + oy), fill=(26, 18, 12),
                        outline=bronze_l)
            pen.ellipse((mx + 17, 63 + by + oy, mx + 22, 68 + by + oy), fill=furn, outline=furn_l)
        pen.polygon([(mx, 66 + by), (mx + 10, 62 + by), (mx + 10, 72 + by), (mx, 70 + by)],
                    fill=iron, outline=soot)
    # eye embers and a pulsing chest vent (per-frame shape, not translation)
    for ex in ((80, 58), (86, 57)) if variant == 'A' else ((78, 58), (84, 57), (90, 57)):
        pen.ellipse((ex[0] + bx, ex[1] + by, ex[0] + 2 + bx, ex[1] + 2 + by), fill=furn_l)
    for k in range(3):
        ex = 52 + ((p['pulse'] * 7 + k * 9) % 30) + bx
        ey = 62 + ((p['pulse'] * 5 + k * 4) % 14) + by
        r = 1 + ((p['pulse'] + k) % 3)
        pen.ellipse((ex - r, ey - r, ex + r, ey + r), fill=furn_l)
    # attack splash and hurt sparks
    if lunge > 0.7:
        for k in range(3):
            pen.line((nx + 28, 62 + by + k * 6, nx + 38, 60 + by + k * 8), fill=furn_l)
    if recoil > 0.7:
        for k in range(4):
            pen.line((30 + bx - tail_len - 6 + k * 4, 60 + by - k * 3,
                      24 + bx - tail_len - 6 + k * 4, 54 + by - k * 3), fill=bronze_l)
    return im


# -- 2. Pouring Choir --------------------------------------------------------
def draw_pouring_choir(p, variant):
    sid = 'ashbell_foundry'
    soot, iron, iron_l = K.C(sid, 'soot'), K.C(sid, 'iron'), K.C(sid, 'iron_light')
    bronze, bronze_l = K.C(sid, 'bronze'), K.C(sid, 'bronze_light')
    verd, verd_l = K.C(sid, 'verdigris'), K.C(sid, 'verdigris_light')
    furn, furn_l = K.C(sid, 'furnace'), K.C(sid, 'furnace_light')
    im = canvas()
    pen = ImageDraw.Draw(im)
    charge, lunge, recoil, fall = p['charge'], p['lunge'], p['recoil'], p['fall']
    by = int(p['bob'] + charge * 2 - recoil * 3 + fall * 20)
    bx = int(p['sway'] + p['gait'] * 2 + lunge * 3 - recoil * 4
             + fall * 5 + charge * 2)
    if fall > 0.82:
        # slag heap corpse
        pen.polygon([(22, 120), (28, 106), (42, 98), (58, 104), (72, 98), (88, 106), (94, 120)],
                    fill=(42, 34, 28), outline=soot)
        pen.ellipse((46, 104, 78, 120), fill=(60, 44, 30), outline=soot)
        pen.ellipse((58, 108, 70, 118), fill=furn, outline=furn_l)
        for x, y in ((30, 112), (38, 116), (84, 114), (90, 108)):
            pen.ellipse((x, y, x + 8, y + 5), fill=bronze, outline=(54, 34, 16))
        return im
    # base
    pen.ellipse((34 + bx, 106 + by, 94 + bx, 124 + by), fill=iron, outline=soot)
    pen.ellipse((38 + bx, 108 + by, 90 + bx, 120 + by), fill=iron_l, outline=soot)
    if variant == 'A':
        # tall three-flask stack
        bodies = ((42, 82, 88, 112), (46, 58, 84, 90), (50, 36, 78, 64))
        for i, (x0, y0, x1, y1) in enumerate(bodies):
            pen.rounded_rectangle((x0 + bx, y0 + by, x1 + bx, y1 + by), radius=6,
                                  fill=iron, outline=soot)
            pen.line((x0 + 3 + bx, y0 + 4 + by, x1 - 3 + bx, y0 + 4 + by), fill=iron_l)
            pen.rectangle((x0 - 2 + bx, y1 - 6 + by, x1 + 2 + bx, y1 - 2 + by),
                          fill=bronze, outline=(54, 34, 16))
        lips = ((36, 76, -1), (64, 48, 0), (94, 86, 1))
    else:
        # wide cauldron with side flasks
        pen.polygon([(28 + bx, 64 + by), (100 + bx, 64 + by), (94 + bx, 108 + by),
                     (34 + bx, 108 + by)], fill=iron, outline=soot)
        pen.ellipse((28 + bx, 54 + by, 100 + bx, 76 + by), fill=iron_l, outline=soot)
        pen.ellipse((36 + bx, 58 + by, 92 + bx, 72 + by), fill=(42, 34, 30), outline=soot)
        for x0 in (40, 60):
            pen.rounded_rectangle((x0 + bx, 78 + by, x0 + 18 + bx, 106 + by), radius=4,
                                  fill=iron, outline=soot)
        lips = ((32, 62, -1), (64, 54, 0), (96, 62, 1))
    # central seam and bands
    pen.line((64 + bx, 36 + by, 64 + bx, 110 + by), fill=(74, 48, 22), width=2)
    for y in (44, 68, 92, 106):
        pen.line((40 + bx, y + by, 88 + bx, y + by), fill=bronze)
    # three crucible lips with glow and molten beads
    extend = int(charge * 5 + lunge * 7)
    for i, (x, y, side) in enumerate(lips):
        x2 = x + bx + (-extend if side < 0 else extend if side > 0 else 0)
        y2 = y + by - (extend if side == 0 else 0)
        if side < 0:
            pen.polygon([(x2 + 6, y2 - 5), (x2 - 10, y2 - 3), (x2 - 10, y2 + 5), (x2 + 6, y2 + 5)],
                        fill=bronze, outline=(54, 34, 16))
            pen.ellipse((x2 - 13, y2 - 4, x2 - 6, y2 + 4), fill=furn, outline=furn_l)
        elif side > 0:
            pen.polygon([(x2 - 6, y2 - 5), (x2 + 10, y2 - 3), (x2 + 10, y2 + 5), (x2 - 6, y2 + 5)],
                        fill=bronze, outline=(54, 34, 16))
            pen.ellipse((x2 + 6, y2 - 4, x2 + 13, y2 + 4), fill=furn, outline=furn_l)
        else:
            pen.polygon([(x2 - 6, y2 + 4), (x2 - 4, y2 - 10), (x2 + 4, y2 - 10), (x2 + 6, y2 + 4)],
                        fill=bronze, outline=(54, 34, 16))
            pen.ellipse((x2 - 5, y2 - 14, x2 + 5, y2 - 7), fill=furn, outline=furn_l)
        if charge > 0.5 or lunge > 0.5:
            bead_y = y2 + (10 if side == 0 else 6)
            pen.ellipse((x2 - 2, bead_y, x2 + 2, bead_y + 4), fill=furn_l)
    # tapping bar
    pen.line((78 + bx, 88 + by, 96 + bx, 74 + by), fill=iron_l, width=3)
    pen.ellipse((94 + bx, 70 + by, 100 + bx, 76 + by), fill=bronze, outline=soot)
    # vents and pressure eyes with a visible per-frame flame pulse
    for i, (x, y) in enumerate(((52, 72), (64, 62), (76, 72))):
        pen.ellipse((x + bx - 3, y + by - 3, x + bx + 3, y + by + 3), fill=furn, outline=soot)
        if charge > 0.3:
            pen.ellipse((x + bx - 2, y + by - 2, x + bx + 2, y + by + 2), fill=furn_l)
        fh = 3 + ((p['pulse'] + i) % 4) * 3
        pen.polygon([(x - 2 + bx, y - 3 + by), (x + bx, y - 3 - fh + by),
                     (x + 2 + bx, y - 3 + by)], fill=furn_l if i % 2 else furn)
    if p['gait']:
        for k in range(4):
            dx = 28 + ((p['pulse'] * 9 + k * 11) % 44) + bx
            pen.ellipse((dx, 116 + by, dx + 4, 120 + by), fill=(96, 84, 66))
    # attack streams: three short molten fans, not a new projectile system
    if lunge > 0.55:
        for x, y, side in lips:
            if side < 0:
                pts = [(x - 12 + bx, y + by - 3), (x - 30 + bx, y + by - 6),
                       (x - 30 + bx, y + by + 8), (x - 12 + bx, y + by + 5)]
            elif side > 0:
                pts = [(x + 12 + bx, y + by - 3), (x + 30 + bx, y + by - 6),
                       (x + 30 + bx, y + by + 8), (x + 12 + bx, y + by + 5)]
            else:
                pts = [(x - 4 + bx, y - 14 + by), (x - 7 + bx, y - 32 + by),
                       (x + 7 + bx, y - 32 + by), (x + 4 + bx, y - 14 + by)]
            pen.polygon(pts, fill=furn, outline=furn_l)
    # hurt cracks and sparks
    if recoil > 0.5:
        pen.line((48 + bx, 60 + by, 56 + bx, 70 + by, 50 + bx, 82 + by), fill=(12, 10, 9), width=2)
        for k in range(5):
            pen.line((40 + bx + k * 9, 50 + by, 36 + bx + k * 9, 42 + by), fill=furn_l)
    # verdigris seam
    pen.line((52 + bx, 100 + by, 58 + bx, 92 + by, 54 + bx, 84 + by), fill=verd, width=1)
    return im


# -- 3. Root Stilt -----------------------------------------------------------
def draw_root_stilt(p, variant):
    sid = 'boneglass_conservatory'
    bone, chalk, pale = K.C(sid, 'bone'), K.C(sid, 'chalk'), K.C(sid, 'pale')
    lichen, moss, peat = K.C(sid, 'lichen'), K.C(sid, 'moss'), K.C(sid, 'peat')
    root, root_l = K.C(sid, 'root'), K.C(sid, 'root_light')
    wet, bruise = K.C(sid, 'wet'), K.C(sid, 'bruise')
    fungus, glow = K.C(sid, 'fungus'), K.C(sid, 'glow')
    im = canvas()
    pen = ImageDraw.Draw(im)
    charge, lunge, recoil, fall = p['charge'], p['lunge'], p['recoil'], p['fall']
    bx = int(p['sway'] + lunge * 7 - recoil * 5)
    by = int(p['bob'] - charge * 2 - lunge * 2 - recoil * 2 + fall * 26)
    if fall > 0.82:
        # collapsed root tangle with fallen bell head
        pen.polygon([(20, 120), (26, 108), (44, 102), (64, 106), (82, 102), (100, 110), (108, 120)],
                    fill=root, outline=peat)
        for x in (28, 40, 52, 68, 80, 94):
            pen.line((x, 120, x + 4, 106), fill=bone, width=2)
        pen.ellipse((66, 102, 94, 118), fill=(196, 202, 174), outline=lichen)
        pen.ellipse((76, 106, 86, 114), fill=peat)
        pen.line((70, 104, 90, 108), fill=bone)
        for _ in range(5):
            pen.ellipse((30 + _ * 12, 112, 36 + _ * 12, 118), fill=peat)
        return im
    # legs: A two stilts, B three
    if variant == 'A':
        legs = ((54, 80, 46, 120), (74, 80, 84, 120))
    else:
        legs = ((54, 78, 40, 120), (64, 80, 64, 120), (76, 78, 88, 120))
    for i, (hx, hy, fx, fy) in enumerate(legs):
        stride = 0
        if p['charge'] < 0.3 and p['lunge'] < 0.3:
            amp = 4 if p['gait'] else 1
            stride = (0, amp, 0, -amp)[(p['phase'] + i) % 4]
        lock = charge * 3
        hipx = hx + bx + (lock if i % 2 == 0 else -lock)
        footx = fx + stride + bx * 0.3 + lunge * (4 if i < len(legs) // 2 else -2)
        knee_x = (hipx + footx) / 2 + (6 if i % 2 == 0 else -6)
        knee_y = 100 + by * 0.25
        pen.line((hipx, hy + by * 0.3, knee_x, knee_y), fill=peat, width=4)
        pen.line((hipx + 1, hy + by * 0.3, knee_x + 1, knee_y), fill=bone, width=1)
        pen.line((knee_x, knee_y, footx, fy - 2), fill=peat, width=3)
        pen.line((knee_x + 1, knee_y, footx + 1, fy - 2), fill=bone, width=1)
        pen.line((footx - 4, fy, footx + 5, fy), fill=root, width=2)
    # pelvis knot
    pen.ellipse((56 + bx, 74 + by, 72 + bx, 86 + by), fill=root, outline=peat)
    pen.line((58 + bx, 78 + by, 70 + bx, 80 + by), fill=root_l)
    # torso hollow with ribs, open on warn
    flare = int(charge * 5)
    pen.polygon([(50 + bx - flare, 46 + by), (78 + bx + flare, 46 + by),
                 (74 + bx, 80 + by), (54 + bx, 80 + by)], fill=peat, outline=(52, 44, 34))
    pen.line((64 + bx, 42 + by, 64 + bx, 82 + by), fill=bone, width=2)
    for k in range(4):
        y = 50 + k * 8 + by
        pen.arc((50 + bx - flare, y - 4, 78 + bx + flare, y + 6), 190, 350,
                fill=bone, width=2)
        pen.arc((52 + bx - flare, y - 3, 76 + bx + flare, y + 5), 190, 350,
                fill=chalk, width=1)
    # shoulders and root arms
    pen.line((50 + bx, 48 + by, 42 + bx, 44 + by), fill=root, width=4)
    pen.line((78 + bx, 48 + by, 86 + bx, 44 + by), fill=root, width=4)
    for side in (-1, 1):
        sx = 64 + side * 15 + bx + int((p['pulse'] - 1.5) * 1.5)
        pts = [(sx, 48 + by), (sx + side * 10, 60 + by + recoil * 3),
               (sx + side * 6 + lunge * 6, 78 + by), (sx + side * 12 + lunge * 8, 92 + by)]
        pen.line(pts, fill=root, width=3)
        pen.line([(x + side, y) for x, y in pts], fill=bone, width=1)
        for k in range(2):
            px, py = pts[1 + k]
            pen.line((px, py, px + side * 8, py + 5), fill=root_l, width=1)
    if variant == 'B':
        for side in (-1, 1):
            sx = 64 + side * 9 + bx
            pen.line((sx, 78 + by, sx + side * 12, 96 + by), fill=root_l, width=2)
    # head: one drooping bell (A) or split double bell (B)
    neck_y = 38 + by
    pen.line((64 + bx, 42 + by, 64 + bx, neck_y), fill=bone, width=3)
    slit_open = 2 + int(charge * 8 + lunge * 4 + (p['pulse'] % 3))
    if variant == 'A':
        hx = 64 + bx + int(lunge * 6 - recoil * 2)
        bell_shape(pen, hx, 12 + by, 28, 30, (208, 212, 186), glow, lichen,
                   lip=(182, 194, 164))
        pen.rectangle((hx - slit_open // 2, 22 + by, hx + slit_open // 2, 36 + by), fill=peat)
        pen.ellipse((hx - 3, 16 + by, hx + 3, 21 + by), fill=glow)
    else:
        hx = 64 + bx + int(lunge * 6 - recoil * 2)
        for ox, w, top in ((-8, 20, 16), (9, 20, 20)):
            bell_shape(pen, hx + ox, top + by, w, 24, (206, 210, 182), glow, lichen,
                       lip=(180, 192, 162))
            pen.rectangle((hx + ox - slit_open // 3, top + 10 + by,
                           hx + ox + slit_open // 3, top + 24 + by), fill=peat)
        pen.line((hx - 8, 20 + by, hx + 8, 24 + by), fill=root_l, width=2)
    # motes drift in every state; reading as spores, not a new mechanic
    for k in range(3):
        mx = 32 + ((p['pulse'] * 11 + k * 17) % 62)
        my = 30 + ((p['pulse'] * 7 + k * 13) % 54)
        pen.ellipse((mx, my, mx + 2, my + 2), fill=glow)
    # warning spores and attack reach
    if charge > 0.5 or lunge > 0.5:
        for k in range(8):
            x = 30 + (k * 13) % 68
            y = 34 + (k * 17) % 56
            pen.ellipse((x, y, x + 2, y + 2), fill=glow)
    if lunge > 0.6:
        pen.line((86 + bx, 66 + by, 104 + bx, 60 + by), fill=bone, width=2)
        pen.line((86 + bx, 72 + by, 106 + bx, 74 + by), fill=bone, width=2)
    if recoil > 0.6:
        pen.line((54 + bx, 58 + by, 60 + bx, 70 + by, 56 + bx, 80 + by), fill=(18, 16, 14), width=2)
    return im


# -- 4. Hollow Nurse ---------------------------------------------------------
def draw_hollow_nurse(p, variant):
    sid = 'boneglass_conservatory'
    bone, chalk, pale = K.C(sid, 'bone'), K.C(sid, 'chalk'), K.C(sid, 'pale')
    lichen, moss, peat = K.C(sid, 'lichen'), K.C(sid, 'moss'), K.C(sid, 'peat')
    root, root_l = K.C(sid, 'root'), K.C(sid, 'root_light')
    wet, bruise = K.C(sid, 'wet'), K.C(sid, 'bruise')
    fungus, glow = K.C(sid, 'fungus'), K.C(sid, 'glow')
    im = canvas()
    pen = ImageDraw.Draw(im)
    charge, lunge, recoil, fall = p['charge'], p['lunge'], p['recoil'], p['fall']
    bx = int(p['sway'] + p['gait'] * 2 + lunge * 3 - recoil * 3
             + fall * 4 + charge * 2)
    by = int(charge - recoil * 2 + fall * 20)
    if fall > 0.82:
        # collapsed pod cluster
        pen.ellipse((18, 108, 100, 120), fill=root, outline=peat)
        for x, w in ((26, 20), (50, 26), (76, 20)):
            pen.ellipse((x, 98, x + w, 118), fill=(196, 202, 174), outline=lichen)
            pen.ellipse((x + 6, 104, x + w - 4, 114), fill=peat)
        pen.ellipse((56, 104, 72, 116), fill=glow, outline=lichen)
        for x in (34, 60, 86):
            pen.line((x, 120, x + 4, 108), fill=bone)
        return im
    # root socket
    pen.ellipse((46 + bx, 108 + by, 82 + bx, 122 + by), fill=root, outline=peat)
    pen.ellipse((50 + bx, 110 + by, 78 + bx, 118 + by), fill=(64, 52, 38), outline=(30, 26, 20))
    # central stalk
    pen.line((64 + bx, 44 + by, 64 + bx, 112 + by), fill=root, width=5)
    pen.line((65 + bx, 44 + by, 65 + bx, 112 + by), fill=bone, width=1)
    # root cords to the bells
    if variant == 'A':
        cords = ((64, 50, 36, 54), (64, 56, 92, 60), (64, 40, 65, 30))
        bells = ((36, 46, 18, 20), (92, 52, 18, 20), (65, 24, 18, 20))
        pod = (52, 50, 76, 88)
    else:
        cords = ((64, 44, 34, 58), (64, 46, 94, 62), (64, 46, 64, 32))
        bells = ((34, 50, 18, 22), (94, 54, 18, 22), (64, 26, 24, 24))
        pod = (46, 36, 82, 82)
    for x0, y0, x1, y1 in cords:
        pen.line((x0 + bx, y0 + by, x1 + bx, y1 + by), fill=root_l, width=2)
    # central pod with a blank, almost-face hollow
    x0, y0, x1, y1 = pod
    pen.rounded_rectangle((x0 + bx, y0 + by, x1 + bx, y1 + by), radius=14,
                          fill=(204, 208, 182), outline=lichen)
    pen.ellipse((x0 + 6 + bx, y0 + 8 + by, x1 - 6 + bx, y1 - 6 + by), fill=peat)
    pen.arc((x0 + 5 + bx, y0 + 7 + by, x1 - 5 + bx, y1 - 5 + by), 200, 340, fill=bone, width=1)
    if variant == 'B':
        for k in range(4):
            pen.line((x0 + 8 + k * 5 + bx, y0 + 8 + by, x0 + 10 + k * 5 + bx, y1 - 8 + by),
                     fill=root_l)
    # three fungal bells, inflated by charge and per-frame breath
    inflate = int(charge * 4 + (p['pulse'] % 2))
    for cx, top, w, h in bells:
        cx2 = cx + bx + int(lunge * (4 if cx > 64 else -4))
        bell_shape(pen, cx2, top + by - inflate, w + inflate, h + inflate,
                   (206, 212, 184), glow, lichen, lip=(180, 194, 164))
        slit = 2 + int(charge * 6 + lunge * 3)
        pen.rectangle((cx2 - slit // 2, top + by - inflate + 8,
                       cx2 + slit // 2, top + by + h + inflate - 2), fill=peat)
        pen.ellipse((cx2 - 2, top + by - inflate + 4, cx2 + 2, top + by - inflate + 8), fill=glow)
    # an always-present slow pulse inside the hollow; brighter on warning
    r = 2 + int(charge * 5 + (p['pulse'] * 2) % 4)
    pen.ellipse((64 - r + bx, 66 - r + by, 64 + r + bx, 66 + r + by), fill=glow)
    # spore fan
    if lunge > 0.55:
        for cx, cy, r in ((24, 56, 9), (104, 62, 9), (64, 12, 8)):
            for rr in (r, r - 4):
                pen.ellipse((cx + bx - rr, cy + by - rr, cx + bx + rr, cy + by + rr),
                            outline=glow, width=2)
            pen.ellipse((cx + bx - 2, cy + by - 2, cx + bx + 2, cy + by + 2), fill=fungus)
    if recoil > 0.6:
        pen.line((x0 + 8 + bx, y0 + 12 + by, x0 + 18 + bx, y0 + 30 + by,
                  x0 + 10 + bx, y0 + 44 + by), fill=(24, 22, 18), width=2)
        for k in range(4):
            pen.ellipse((30 + k * 18, 94 + (k % 2) * 8, 34 + k * 18, 98 + (k % 2) * 8), fill=glow)
    # hanging tendrils sway visibly per frame
    for side in (-1, 1):
        tx = 64 + side * 12 + bx + int((p['pulse'] - 1.5) * 2)
        pen.line((64 + side * 12 + bx, 82 + by, tx, 104 + by), fill=root_l)
    return im


# -- 5. Night Porter ---------------------------------------------------------
def draw_night_porter(p, variant):
    sid = 'skyhotel_service_well'
    night = K.C(sid, 'night')
    blue, blue_l = K.C(sid, 'blue'), K.C(sid, 'blue_light')
    amber, amber_l = K.C(sid, 'amber'), K.C(sid, 'amber_light')
    maroon, maroon_d = K.C(sid, 'maroon'), K.C(sid, 'maroon_dark')
    brass, linen = K.C(sid, 'brass'), K.C(sid, 'linen')
    im = canvas()
    pen = ImageDraw.Draw(im)
    charge, lunge, recoil, fall = p['charge'], p['lunge'], p['recoil'], p['fall']
    bx = int(p['sway'] + lunge * 8 - recoil * 5)
    by = int(p['bob'] - lunge * 1 - recoil * 2 + fall * 24)
    if fall > 0.82:
        # coat heap with fallen cap and case
        pen.polygon([(24, 120), (30, 106), (52, 100), (72, 104), (92, 100), (104, 110), (108, 120)],
                    fill=maroon, outline=maroon_d)
        pen.line((32, 112, 100, 112), fill=(128, 78, 84))
        pen.polygon([(88, 102), (112, 106), (110, 118), (86, 116)], fill=maroon, outline=maroon_d)
        pen.rectangle((90, 108, 106, 110), fill=brass)
        _cap(pen, 52, 96, 30, maroon, maroon_d, brass, tilt=0.6)
        pen.ellipse((98, 112, 106, 118), fill=(18, 14, 16), outline=brass)
        return im
    # coat-tail legs
    tails = 2 if variant == 'A' else 3
    for i in range(tails):
        x = 50 + i * (28 // max(1, tails - 1))
        stride = 0
        if charge < 0.3 and lunge < 0.3:
            amp = 4 if p['gait'] else 1
            stride = (0, amp, 0, -amp)[(p['phase'] + i) % 4]
        footx = x + stride + bx + lunge * (4 if i == tails - 1 else -2)
        pen.line((x + bx, 82 + by, footx, 120), fill=maroon_d, width=7)
        pen.line((x + 2 + bx, 84 + by, footx + 2, 118), fill=maroon, width=2)
        pen.line((footx - 4, 120, footx + 5, 120), fill=(22, 16, 18), width=2)
    # torso coat
    pen.polygon([(48 + bx, 44 + by), (80 + bx, 44 + by), (84 + bx, 84 + by),
                 (44 + bx, 84 + by)], fill=maroon, outline=maroon_d)
    pen.line((50 + bx, 78 + by, 78 + bx, 78 + by), fill=maroon_d, width=2)
    pen.line((51 + bx, 46 + by, 51 + bx, 82 + by), fill=(126, 76, 82))
    # lapels and buttons
    pen.polygon([(56 + bx, 44 + by), (64 + bx, 60 + by), (60 + bx, 44 + by)], fill=maroon_d)
    pen.polygon([(72 + bx, 44 + by), (64 + bx, 60 + by), (68 + bx, 44 + by)], fill=maroon_d)
    for y in (54, 66, 78):
        pen.ellipse((62 + bx, y + by, 66 + bx, y + 4 + by), fill=brass, outline=(54, 38, 18))
    # arms and cases
    pen.line((48 + bx, 50 + by, 36 + bx, 72 + by, 40 + bx, 82 + by), fill=maroon, width=5)
    pen.line((80 + bx, 50 + by, 94 + bx + lunge * 6, 66 + by, 96 + bx + lunge * 6, 78 + by),
             fill=maroon, width=5)
    if variant == 'A':
        _suitcase(pen, 84 + bx + int(lunge * 8), 66 + by, 22, 24, maroon, maroon_d, brass)
    else:
        _suitcase(pen, 82 + bx + int(lunge * 8), 62 + by, 20, 20, maroon, maroon_d, brass)
        _suitcase(pen, 26 + bx, 72 + by, 18, 22, (88, 50, 56), maroon_d, brass)
    # head: blank face under a peaked cap
    pen.rectangle((60 + bx, 36 + by, 68 + bx, 46 + by), fill=linen, outline=maroon_d)
    _blank_face(pen, (54 + bx, 22 + by, 74 + bx, 42 + by), (196, 186, 164), (38, 30, 32))
    tilt = 0.2 + charge * 0.8 + p['pulse'] * 0.12 + (0.4 if variant == 'B' else 0.0)
    _cap(pen, 64 + bx + int(lunge * 4), 12 + by, 34, maroon, maroon_d, brass, tilt=tilt)
    # a small brass key-fob swings on every frame
    kx = 48 + bx + int((p['pulse'] - 1.5) * 2)
    pen.line((46 + bx, 76 + by, kx, 88 + by), fill=brass)
    pen.ellipse((kx - 2, 88 + by, kx + 2, 92 + by), outline=brass, width=1)
    # tell: case seam opens and amber light gathers
    if charge > 0.3:
        seam = 2 + int(charge * 5 + p['pulse'] % 3)
        pen.rectangle((86 + bx + int(lunge * 8), 72 + by, 104 + bx + int(lunge * 8), 72 + seam + by),
                      fill=(18, 14, 16))
        pen.line((86 + bx + int(lunge * 8), 72 + by, 104 + bx + int(lunge * 8), 72 + by), fill=amber)
        pen.ellipse((92 + bx, 96 + by, 100 + bx, 102 + by), fill=amber, outline=amber_l)
    if lunge > 0.6:
        pen.line((96 + bx, 60 + by, 112 + bx, 58 + by), fill=amber_l)
        pen.line((96 + bx, 64 + by, 114 + bx, 66 + by), fill=amber_l)
    if recoil > 0.4:
        pen.line((56 + bx, 30 + by, 62 + bx, 40 + by), fill=(26, 22, 24), width=2)
        pen.line((34 + bx, 78 + by, 44 + bx, 96 + by), fill=(18, 14, 16), width=2)
        pen.rectangle((30 + bx, 94 + by, 48 + bx, 112 + by), fill=maroon, outline=maroon_d)
        pen.line((32 + bx, 98 + by, 46 + bx, 98 + by), fill=brass)
    return im


# -- 6. Call-Bell Choir ------------------------------------------------------
def draw_call_bell_choir(p, variant):
    sid = 'skyhotel_service_well'
    night, night_d = K.C(sid, 'night'), K.C(sid, 'night_dark')
    blue, blue_l = K.C(sid, 'blue'), K.C(sid, 'blue_light')
    amber, amber_l = K.C(sid, 'amber'), K.C(sid, 'amber_light')
    maroon, maroon_d = K.C(sid, 'maroon'), K.C(sid, 'maroon_dark')
    brass, linen = K.C(sid, 'brass'), K.C(sid, 'linen')
    im = canvas()
    pen = ImageDraw.Draw(im)
    charge, lunge, recoil, fall = p['charge'], p['lunge'], p['recoil'], p['fall']
    bx = int(p['sway'] + p['gait'] * 3 + lunge * 2 - recoil * 3
             + fall * 4 + charge * 2)
    by = int(charge - recoil * 2 + fall * 20)
    if fall > 0.82:
        # collapsed trolley with one lit bell
        pen.rectangle((22, 108, 98, 120), fill=(52, 48, 40), outline=(20, 18, 16))
        pen.ellipse((26, 114, 42, 120), fill=(34, 30, 26), outline=(14, 12, 10))
        pen.ellipse((80, 114, 96, 120), fill=(34, 30, 26), outline=(14, 12, 10))
        pen.rectangle((42, 100, 74, 112), fill=maroon, outline=maroon_d)
        pen.line((46, 104, 70, 104), fill=(126, 76, 82))
        bell_shape(pen, 60, 92, 22, 20, brass, amber_l, (52, 38, 18), lip=amber)
        pen.ellipse((58, 104, 64, 110), fill=amber, outline=amber_l)
        return im
    # cart and wheels (wheels bottom at y=120)
    pen.rectangle((24 + bx, 90 + by, 92 + bx, 104 + by), fill=(58, 62, 60), outline=(22, 24, 24))
    pen.line((26 + bx, 92 + by, 90 + bx, 92 + by), fill=brass)
    for cx in (34, 80):
        pen.ellipse((cx - 6 + bx, 108 + by, cx + 6 + bx, 120 + by), fill=(34, 36, 36),
                    outline=(14, 16, 16))
        pen.ellipse((cx - 2 + bx, 112 + by, cx + 2 + bx, 116 + by), fill=brass)
        for k in range(4):
            a = math.tau * k / 4 + p['pulse'] * 0.26
            pen.line((cx + bx, 114 + by, cx + bx + math.cos(a) * 5,
                      114 + by + math.sin(a) * 5), fill=(92, 88, 76))
    # luggage stack
    cases = ((30, 68, 58, 92), (54, 74, 82, 94)) if variant == 'A' else (
        (28, 78, 60, 98), (44, 58, 74, 80), (60, 68, 88, 92))
    for x0, y0, x1, y1 in cases:
        pen.rectangle((x0 + bx, y0 + by, x1 + bx, y1 + by), fill=maroon, outline=maroon_d)
        pen.line((x0 + 2 + bx, y0 + 4 + by, x1 - 2 + bx, y0 + 4 + by), fill=(128, 78, 84))
        pen.rectangle((x0 + 4 + bx, y0 + 10 + by, x0 + 8 + bx, y0 + 14 + by), fill=brass)
    # bells: three, at different heights
    if variant == 'A':
        bells = ((34, 46, 18, 20), (60, 32, 20, 24), (84, 48, 16, 18))
    else:
        bells = ((32, 38, 18, 22), (58, 26, 20, 24), (84, 42, 18, 22))
    rise = int(charge * 4 + (p['pulse'] % 3))
    for cx, top, w, h in bells:
        cx2 = cx + bx + (lunge * 2 if cx < 64 else -lunge * 2)
        top2 = top + by - rise
        pen.line((cx2, 92 + by, cx2, top2 + h), fill=brass, width=2)
        bell_shape(pen, cx2, top2, w, h, brass, (226, 190, 120), (52, 38, 18), lip=amber)
        pen.ellipse((cx2 - 3, top2 + h - 2, cx2 + 3, top2 + h + 4),
                    fill=amber_l if charge > 0.25 else amber, outline=(52, 38, 18))
        if charge > 0.25:
            pen.ellipse((cx2 - 4, top2 + h - 3, cx2 + 4, top2 + h + 5), outline=amber_l)
    # room-number paddle, leaning as the cart begins to fail
    px = 94 + bx + int(fall * 4)
    pen.line((px, 30 + by, px, 92 + by), fill=brass, width=3)
    if variant == 'A':
        pen.rectangle((px - 2, 28 + by, px + 10, 74 + by), fill=(46, 52, 58), outline=brass)
        for y in (34, 44, 54, 64):
            pen.line((px + 1, y + by, px + 7, y + by), fill=amber)
    else:
        pen.line((px, 44 + by, px + 10, 30 + by), fill=brass, width=3)
        pen.rectangle((px + 4, 26 + by, px + 16, 62 + by), fill=(46, 52, 58), outline=brass)
        for y in (32, 40, 48, 56):
            pen.line((px + 7, y + by, px + 13, y + by), fill=amber)
    # cart shudder / attack resonance arcs
    if charge > 0.4 or lunge > 0.3:
        for cx, top, w, h in bells:
            for rr in (10, 15):
                pen.arc((cx + bx - rr, top + by - rr + h, cx + bx + rr,
                         top + by + rr + h), 200, 340, fill=amber_l, width=1)
    if recoil > 0.55:
        pen.line((48 + bx, 70 + by, 56 + bx, 80 + by, 48 + bx, 88 + by), fill=(22, 18, 20), width=2)
        for k in range(4):
            pen.ellipse((30 + k * 16 + bx, 84 + by, 34 + k * 16 + bx, 88 + by), fill=amber)
    # early collapse crack so the first death frame reads as damage
    if fall > 0.2:
        pen.line((44 + bx, 68 + by, 52 + bx, 80 + by, 46 + bx, 92 + by),
                 fill=(22, 18, 20), width=2)
        pen.line((72 + bx, 74 + by, 78 + bx, 86 + by), fill=(22, 18, 20), width=2)
        pen.ellipse((58 + bx, 82 + by, 64 + bx, 88 + by), fill=amber)
    # small floor brake
    pen.rectangle((20 + bx, 104 + by, 30 + bx, 110 + by), fill=(34, 38, 38), outline=(14, 16, 16))
    return im


DRAW = {
    'ashbell_foundry': {'latchwing': draw_chain_hound, 'relay_choir': draw_pouring_choir},
    'boneglass_conservatory': {'latchwing': draw_root_stilt, 'relay_choir': draw_hollow_nurse},
    'skyhotel_service_well': {'latchwing': draw_night_porter, 'relay_choir': draw_call_bell_choir},
}


def render_frame(set_id, role, variant, state, col, seed):
    p = pose(state, col)
    im = DRAW[set_id][role](p, variant)
    a = np.array(im, dtype=np.uint8)
    a[:, :, 3] = np.where(a[:, :, 3] > 0, 255, 0)
    ys, xs = np.where(a[:, :, 3] > 0)
    if len(xs):
        x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
        cx = (x0 + x1) / 2.0
        dx = 0
        if cx > 74:
            dx = -int(round(cx - 72))
        elif cx < 54:
            dx = int(round(54 - cx))
        if x0 + dx < 4:
            dx = 4 - x0
        if x1 + dx > 123:
            dx = 123 - x1
        dy = 120 - y1
        out = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
        out.alpha_composite(Image.fromarray(a, 'RGBA'), (dx, dy))
        a = np.array(out, dtype=np.uint8)
    # cosmetic seed weathering: four existing opaque pixels tinted per frame.
    # Identity, silhouette, anchors and frame counts do not depend on the seed.
    accent = {'ashbell_foundry': K.C('ashbell_foundry', 'furnace_light'),
              'boneglass_conservatory': K.C('boneglass_conservatory', 'glow'),
              'skyhotel_service_well': K.C('skyhotel_service_well', 'amber_light')}[set_id]
    wrng = random.Random(seed + 977 * STATES.index(state) + 31 * col
                        + 13 * len(role) + (0 if variant == 'A' else 7))
    for _ in range(4):
        wx, wy = wrng.randint(8, 119), wrng.randint(8, 119)
        if a[wy, wx, 3] > 0:
            a[wy, wx, :3] = accent
    # hard safety: transparent margin and crisp alpha only
    a[:3, :, 3] = 0
    a[-4:, :, 3] = 0
    a[:, :3, 3] = 0
    a[:, -4:, 3] = 0
    return Image.fromarray(a, 'RGBA')


def build_atlas(set_id, role, variant, seed):
    atlas = Image.new('RGBA', (SIZE * COLS, SIZE * ROWS), (0, 0, 0, 0))
    for row, state in enumerate(STATES):
        for col in range(COLS):
            frame = render_frame(set_id, role, variant, state, col, seed)
            atlas.alpha_composite(frame, (col * SIZE, row * SIZE))
    return atlas


# -- contact sheet -----------------------------------------------------------
def _font(size, bold=False):
    path = ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold
            else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def compose_mob_sheet(sid, atlases, meta, seed, out_path):
    """atlases: {(role, variant): PIL atlas}; meta: MOBS[sid]."""
    W, H = 720, 1010
    im = Image.new('RGB', (W, H), (20, 22, 26))
    pen = ImageDraw.Draw(im)
    pen.text((18, 12), f'{K.SETS[sid]["name"]} - signature mobs', font=_font(22, True),
             fill=(240, 234, 220))
    pen.text((18, 42), '512x768 RGBA atlases; rows idle / walk / warn / attack / hurt / death; '
             'frame 23 is a corpse.', font=_font(11), fill=(178, 188, 188))
    scale = 0.5
    aw, ah = int(512 * scale), int(768 * scale)
    for i, role in enumerate(K.MOB_ROLES):
        identity = meta[role]
        y0 = 80 + i * 440
        pen.text((92, y0 - 20), f'{identity["name"]}  [{role} adapter role]', font=_font(16, True),
                 fill=(238, 214, 150))
        for j, variant in enumerate('AB'):
            x = 96 + j * (aw + 20)
            atlas = atlases[(role, variant)].convert('RGBA')
            bg = Image.new('RGBA', atlas.size, (50, 54, 60, 255))
            bg.alpha_composite(atlas)
            disp = bg.convert('RGB').resize((aw, ah), Image.LANCZOS)
            im.paste(disp, (x, y0))
            pen.text((x, y0 + ah + 2), f'variant {variant}', font=_font(11, True),
                     fill=(220, 220, 210))
        for r, state in enumerate(STATES):
            pen.text((12, y0 + int(r * 128 * scale) + 28), state, font=_font(10),
                     fill=(255, 214, 130))
    y = 80 + 2 * 440 + 4
    for role in K.MOB_ROLES:
        identity = meta[role]
        note = identity['tells'] + ' Counterplay: ' + identity['counterplay']
        pen.text((18, y), f'{role}: ' + note[:96], font=_font(10), fill=(186, 192, 190))
        y += 13
    im.save(out_path)
    return im
