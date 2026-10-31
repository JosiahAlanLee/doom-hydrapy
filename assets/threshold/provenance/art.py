#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Threshold art: original procedural creature atlases, wall/flat tiles and props.

All pixels are drawn here from geometric primitives and tileable value noise.
No existing sprite, texture or font is sampled. Creatures are 128x128 RGBA
frames in a 4-column x 6-row atlas: idle, walk, warning, attack, hurt, death.
Walls are 128x128 RGB, flats 64x64 RGB, props 96x128 RGBA. Run this file to
write the assets, contact sheets and art-checks.json.
"""
import hashlib
import json
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
ART = ROOT / 'art'
STATES = ('idle', 'walk', 'warning', 'attack', 'hurt', 'death')
FRAMES = 4
SIZE = 128
WALLS = [f'NWALL0{i}' for i in range(1, 7)]
FLATS = [f'NFLAT0{i}' for i in range(1, 5)]
FAMILIES = {'latchwing': ['A', 'B'], 'relay_choir': ['A', 'B']}
PROPS = ['service_lamp', 'cable_shrine', 'directory_sign']

# restrained municipal palette: bone/plaster, slate/petrol, oxidised metal, amber
BONE = (198, 190, 168, 255)
PLASTER = (162, 154, 132, 255)
SLATE = (74, 88, 96, 255)
PETROL = (34, 52, 58, 255)
DARK = (18, 26, 30, 255)
AMBER = (232, 158, 56, 255)
AMBER_HOT = (255, 202, 110, 255)
OXIDE = (146, 96, 58, 255)
VERDIGRIS = (86, 116, 106, 255)
STEEL = (104, 110, 110, 255)


def frame_seed(family, variant, state, frame):
    return 0x7A11 + 977 * (list(FAMILIES).index(family) + 1) + 131 * (ord(variant) - 64) \
        + 17 * STATES.index(state) + frame


def blank():
    return Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))


def poly(pen, points, fill, outline=DARK, width=2):
    pen.polygon(points, fill=fill, outline=outline, width=width)


def scratch(pen, rng, color, n, box):
    x0, y0, x1, y1 = box
    for _ in range(n):
        x, y = rng.randrange(x0, x1), rng.randrange(y0, y1)
        pen.point((x, y), fill=color)


# -- creature: Latchwing -----------------------------------------------------
def latchwing(variant, state, frame):
    """Low cable/moth inspection rig. The wing aperture opens in warning."""
    image = blank()
    pen = ImageDraw.Draw(image)
    rng = random.Random(frame_seed('latchwing', variant, state, frame))
    a = variant == 'A'
    wing = BONE if a else (176, 168, 146, 255)
    wing_dark = PLASTER if a else (132, 124, 104, 255)
    frame_col = OXIDE if a else VERDIGRIS
    body = PETROL if a else (44, 62, 62, 255)
    lens = AMBER_HOT if a else (236, 176, 80, 255)
    if state == 'death':
        return latchwing_death(image, pen, rng, variant, frame)
    bob = {'idle': (0, -2, -1, 1), 'walk': (0, -3, -1, 2),
           'warning': (1, 0, -1, -1), 'attack': (0, 2, 4, 3),
           'hurt': (3, 5, 6, 4)}[state][frame]
    sway = {'idle': (0, 1, 0, -1), 'walk': (-2, 0, 2, 0),
            'warning': (0, 0, 0, 0), 'attack': (-4, 2, 6, 9),
            'hurt': (5, 7, 4, 2)}[state][frame]
    aperture = {'idle': (10, 12, 11, 13), 'walk': (14, 22, 14, 22),
                'warning': (14, 18, 22, 26), 'attack': (8, 6, 4, 2),
                'hurt': (2, 4, 6, 8)}[state][frame]
    cx, cy = 64 + sway, 66 + bob
    tip_y = {'idle': 34, 'walk': 32, 'warning': 22, 'attack': 44, 'hurt': 40}[state]
    # wing rails and slatted panels: the aperture is the gap that opens in warning
    for side in (-1, 1):
        shoulder = (cx + side * 7, cy - 8)
        tip = (cx + side * (30 + aperture), tip_y + (0 if side < 0 else 4))
        low = (tip[0] - side * 9, tip[1] + 26)
        inner = (cx + side * 15, cy + 10)
        poly(pen, [shoulder, tip, low, inner], wing, outline=DARK, width=2)
        pen.line([shoulder, tip], fill=frame_col, width=2)
        for j in range(3):
            t = 0.25 + j * 0.22
            x1 = round(shoulder[0] + (tip[0] - shoulder[0]) * t)
            y1 = round(shoulder[1] + (tip[1] - shoulder[1]) * t)
            x2 = round(inner[0] + (low[0] - inner[0]) * (0.3 + j * 0.2))
            y2 = round(inner[1] + (low[1] - inner[1]) * (0.3 + j * 0.2))
            pen.line([(x1, y1), (x2, y2)], fill=wing_dark, width=1)
        if a:
            pen.rectangle((tip[0] - 3, tip[1] + 2, tip[0] + 3, tip[1] + 8),
                          fill=frame_col, outline=DARK)
        else:
            pen.polygon([(tip[0], tip[1]), (tip[0] + side * 5, tip[1] + 11),
                         (tip[0] - side * 2, tip[1] + 16)], fill=frame_col, outline=DARK)
    # folded apparatus body
    body_pts = [(cx - 11, cy - 14), (cx + 11, cy - 14), (cx + 8, cy + 18),
                (cx, cy + 27), (cx - 8, cy + 18)]
    poly(pen, body_pts, body, outline=wing_dark, width=2)
    if a:
        for j in range(3):
            y = cy - 8 + j * 7
            pen.line((cx - 8, y, cx + 8, y), fill=frame_col, width=2)
        pen.rectangle((cx - 4, cy + 2, cx + 4, cy + 10), fill=lens, outline=DARK)
    else:
        pen.ellipse((cx - 10, cy - 4, cx + 10, cy + 16), outline=frame_col, width=3)
        pen.ellipse((cx - 4, cy + 2, cx + 4, cy + 10), fill=lens, outline=DARK)
    # three low cable tendrils with plugs, anchored near the floor
    for j, dx in enumerate((-11, 0, 11)):
        knee = (cx + dx + (sway // 2), cy + 34 + j % 2 * 4)
        foot = (cx + dx * 2 - 4 + sway, 112 + (j % 2) * 3)
        pen.line([(cx + dx // 2, cy + 20), knee, foot], fill=(24, 32, 34, 255), width=2)
        pen.rectangle((foot[0] - 2, foot[1] - 3, foot[0] + 2, foot[1] + 1),
                      fill=frame_col, outline=DARK)
    if state == 'warning':
        for r in (16, 27, 39):
            pen.arc((cx - r - aperture // 3, cy - r - 4, cx + r + aperture // 3, cy + r + 26),
                    205, 335, fill=AMBER, width=2)
        pen.line((cx - 6, cy - 20, cx + 6, cy - 20), fill=AMBER_HOT, width=2)
    if state == 'attack':
        for j in range(3):
            pen.line((cx - 20 + j * 6, cy + 30, cx - 32 + j * 10, cy + 44),
                     fill=AMBER, width=1)
        pen.line((cx + 12, cy - 12, cx + 30, cy - 2), fill=AMBER, width=2)
    if state == 'hurt':
        scratch(pen, rng, AMBER_HOT, 10, (cx - 14, cy - 18, cx + 15, cy + 20))
        pen.line((cx - 9, cy - 12, cx + 3, cy - 2), fill=AMBER, width=1)
        for j in range(3):
            pen.line((cx + 14 + j * 5, cy - 16 + j * 3, cx + 24 + j * 4, cy - 22 + j * 2),
                     fill=(255, 220, 150, 255), width=1)
    if state == 'walk':
        for j, dx in enumerate((-14, 14)):
            pen.line((cx + dx, cy + 18, cx + dx + (4 if frame % 2 else -4), cy + 30),
                     fill=frame_col, width=2)
    scratch(pen, rng, (*DARK[:3], 160), 9, (cx - 14, cy - 16, cx + 14, cy + 22))
    return image


def latchwing_death(image, pen, rng, variant, frame):
    wing = BONE if variant == 'A' else (176, 168, 146, 255)
    wing_dark = PLASTER if variant == 'A' else (132, 124, 104, 255)
    frame_col = OXIDE if variant == 'A' else VERDIGRIS
    stage = frame
    cx = 64
    if stage < 3:
        drop = stage * 8
        spread = 34 - stage * 8
        pen.line([(cx - 22, 90 + drop), (cx - 6, 70 + drop), (cx + 4, 96 + drop)],
                 fill=(24, 32, 34, 255), width=3)
        poly(pen, [(cx - 6, 62 + drop), (cx - spread, 84 + drop),
                   (cx - 18, 104 + drop - stage * 2), (cx, 96 + drop)], wing, outline=DARK)
        poly(pen, [(cx + 6, 62 + drop), (cx + spread, 84 + drop),
                   (cx + 18, 104 + drop - stage * 2), (cx, 96 + drop)], wing_dark, outline=DARK)
        pen.rectangle((cx - 6, 84 + drop, cx + 6, 96 + drop), fill=PETROL, outline=frame_col)
        if stage == 2:
            pen.line((cx - 14, 108 + drop, cx + 18, 104 + drop), fill=AMBER, width=2)
    else:
        # final corpse: a flattened folded-wing tangle with one cable loop
        poly(pen, [(14, 108), (52, 96), (78, 104), (114, 100), (110, 116),
                   (72, 112), (40, 118), (16, 116)], wing, outline=DARK, width=2)
        poly(pen, [(36, 102), (58, 98), (66, 108), (44, 112)], wing_dark, outline=DARK)
        pen.ellipse((56, 100, 70, 110), fill=PETROL, outline=frame_col, width=2)
        pen.ellipse((60, 103, 64, 107), fill=(120, 78, 40, 255), outline=DARK)
        pen.arc((76, 88, 104, 118), 120, 330, fill=frame_col, width=3)
        pen.line((34, 100, 30, 88, 38, 84), fill=(24, 32, 34, 255), width=2)
        pen.line((92, 114, 104, 118), fill=frame_col, width=2)
        scratch(pen, rng, AMBER, 6, (32, 98, 100, 114))
    return image


# -- creature: Relay Choir ---------------------------------------------------
def relay_choir(variant, state, frame):
    """Stacked duct/ceramic masks on a cable frame; a three-spore fan in attack."""
    image = blank()
    pen = ImageDraw.Draw(image)
    rng = random.Random(frame_seed('relay_choir', variant, state, frame))
    a = variant == 'A'
    ceramic = BONE if a else (176, 170, 150, 255)
    ceramic_dark = (128, 120, 100, 255)
    duct = (62, 78, 84, 255) if a else (46, 64, 68, 255)
    metal = OXIDE if a else VERDIGRIS
    glow = AMBER if state != 'attack' else AMBER_HOT
    if state == 'death':
        return relay_choir_death(image, pen, rng, variant, frame)
    bob = {'idle': (0, 1, 0, -1), 'walk': (0, 2, 1, -1),
           'warning': (2, 1, 0, 2), 'attack': (4, 7, 5, 3),
           'hurt': (6, 8, 5, 3)}[state][frame]
    lean = {'idle': 0, 'walk': (1, 0, -1, 0)[frame], 'warning': -2,
            'attack': -5 + frame * 2, 'hurt': 7 - frame}[state]
    pressure = {'idle': 0, 'walk': 1, 'warning': (1, 3, 5, 7)[frame],
                'attack': 8, 'hurt': 2}[state]
    cx = 64 + lean
    top = 20 + bob
    base = 116
    # cable frame: two legs and a top yoke, always visible between the masks
    pen.line([(30, base), (36, 84), (42, top + 4)], fill=(24, 32, 34, 255), width=3)
    pen.line([(98, base), (92, 84), (86, top + 4)], fill=(24, 32, 34, 255), width=3)
    pen.line([(36, base - 4), (98, base - 4)], fill=metal, width=3)
    pen.line([(42, top + 2), (86, top + 2)], fill=metal, width=3)
    pen.rectangle((26, base - 2, 40, base + 2), fill=metal, outline=DARK)
    pen.rectangle((88, base - 2, 102, base + 2), fill=metal, outline=DARK)
    spans = (44, 34, 26)
    centers = (92 + bob, 66 + bob, 40 + bob)
    for i, (cy, span) in enumerate(zip(centers, spans)):
        lift = 0
        if state == 'warning':
            lift = -min(2, pressure // 3)
        if state == 'attack':
            lift = -3 + i
        if state == 'hurt':
            lift = 2 + i
        y = cy + lift
        if a:
            pen.ellipse((cx - span, y - 12, cx + span, y + 12),
                        fill=ceramic, outline=DARK, width=2)
            pen.ellipse((cx - span + 5, y - 8, cx + span - 5, y + 8),
                        outline=metal, width=2)
            for j in range(3):
                yy = y - 5 + j * 5
                pen.line((cx - span + 8, yy, cx + span - 8, yy), fill=ceramic_dark, width=1)
        else:
            pen.polygon([(cx - span + 4, y - 12), (cx + span - 4, y - 12),
                         (cx + span, y + 12), (cx - span, y + 12)],
                        fill=duct, outline=DARK, width=2)
            for j in range(5):
                xx = cx - span + 10 + j * max(4, (2 * span - 20) // 4)
                pen.line((xx, y - 7, xx, y + 7), fill=ceramic_dark, width=2)
            pen.rectangle((cx - span + 3, y - 12, cx - span + 9, y + 12),
                          outline=metal, width=1)
        if i < 2:
            gap_y = (centers[i] + centers[i + 1]) // 2 + bob - 1
            r = 5 + pressure
            pen.ellipse((cx - r, gap_y - r, cx + r, gap_y + r), outline=glow, width=2)
            pen.ellipse((cx - 2, gap_y - 2, cx + 2, gap_y + 2), fill=glow)
    # central slit pressure core
    pen.rectangle((cx - 3, 48 + bob, cx + 3, 84 + bob), fill=(30, 30, 26, 255), outline=metal)
    core_top = max(50 + bob, 82 + bob - 4 - pressure * 4)
    pen.rectangle((cx - 1, core_top, cx + 1, 82 + bob), fill=glow)
    if state == 'warning':
        for j in range(3):
            r = 8 + j * 4 + pressure
            pen.arc((cx - r, 30 + bob - r // 2, cx + r, 54 + bob + r // 2), 200, 340,
                    fill=AMBER, width=1)
        pen.line((cx - 22, 24 + bob, cx + 22, 24 + bob), fill=AMBER_HOT, width=2)
    if state == 'attack':
        for j, (dx, dy) in enumerate(((-22, 16), (0, 8), (22, 16))):
            mx = cx + dx
            my = 84 + bob + dy
            pen.line((cx + dx // 3, 100 + bob, mx, my), fill=metal, width=3)
            pen.ellipse((mx - 8, my - 8, mx + 8, my + 8), fill=duct, outline=DARK, width=2)
            pen.ellipse((mx - 4, my - 4, mx + 4, my + 4), fill=AMBER_HOT, outline=DARK)
            pen.ellipse((mx - 3, my - 12 - j * 2, mx + 3, my - 6 - j * 2),
                        fill=(210, 150, 66, 255), outline=DARK)
    if state == 'hurt':
        scratch(pen, rng, AMBER_HOT, 12, (cx - 26, 28 + bob, cx + 26, 104 + bob))
        pen.line((cx - 18, 44 + bob, cx - 4, 62 + bob), fill=AMBER, width=2)
        pen.line((cx + 10, 70 + bob, cx + 24, 82 + bob), fill=(240, 210, 160, 255), width=1)
    if state == 'walk':
        pen.line((30, base, 24 + frame, base - 10), fill=metal, width=2)
        pen.line((98, base, 104 - frame, base - 10), fill=metal, width=2)
    scratch(pen, rng, (*DARK[:3], 150), 14, (cx - 30, 24 + bob, cx + 30, 106 + bob))
    return image


def relay_choir_death(image, pen, rng, variant, frame):
    a = variant == 'A'
    ceramic = BONE if a else (176, 170, 150, 255)
    duct = (62, 78, 84, 255) if a else (46, 64, 68, 255)
    metal = OXIDE if a else VERDIGRIS
    stage = frame
    if stage < 3:
        tilt = 3 + stage * 9
        drop = stage * 10
        pen.line([(30, 116), (36 + tilt, 84), (44 + tilt, 44 + drop)],
                 fill=(24, 32, 34, 255), width=3)
        pen.line([(98, 116), (92 - tilt, 88), (80 - tilt, 52 + drop)],
                 fill=(24, 32, 34, 255), width=3)
        for i in range(3):
            x = 60 + tilt // 2 - i * 4
            y = 30 + i * 24 + drop
            pen.ellipse((x - 20 + i * 3, y - 9, x + 20 - i * 3, y + 9),
                        fill=ceramic if i % 2 == 0 else duct, outline=DARK, width=2)
        pen.line((40 + tilt, 70 + drop, 66 + tilt // 2, 76 + drop), fill=metal, width=2)
        if stage == 2:
            pen.ellipse((56, 92, 66, 102), fill=(140, 90, 44, 255), outline=DARK)
    else:
        # final corpse: a low pile of broken ceramic masks and slack cable
        pen.ellipse((22, 96, 66, 118), fill=ceramic, outline=DARK, width=2)
        pen.ellipse((30, 100, 58, 112), outline=(128, 120, 100, 255), width=1)
        pen.polygon([(54, 92), (84, 96), (92, 114), (62, 118)], fill=duct, outline=DARK, width=2)
        for j in range(4):
            pen.line((60 + j * 8, 98, 64 + j * 8, 112), fill=(128, 120, 100, 255), width=1)
        pen.arc((70, 72, 106, 110), 30, 150, fill=metal, width=3)
        pen.line((18, 108, 36, 114, 52, 110), fill=(24, 32, 34, 255), width=2)
        pen.ellipse((74, 106, 80, 112), fill=(180, 116, 52, 255), outline=DARK)
        scratch(pen, rng, AMBER, 7, (24, 96, 100, 118))
    return image


# -- tileable materials ------------------------------------------------------
def periodic_noise(w, h, cell, rng, octaves=3):
    total = np.zeros((h, w))
    norm, amp = 0.0, 1.0
    for _ in range(octaves):
        c = max(2, cell >> _)
        gw, gh = max(1, w // c), max(1, h // c)
        grid = np.array([[rng.random() for _ in range(gw)] for _ in range(gh)])
        xs, ys = np.arange(w) / c, np.arange(h) / c
        x0, y0 = np.floor(xs).astype(int), np.floor(ys).astype(int)
        fx, fy = xs - x0, ys - y0
        fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        g00 = grid[np.ix_(y0 % gh, x0 % gw)]
        g10 = grid[np.ix_(y0 % gh, (x0 + 1) % gw)]
        g01 = grid[np.ix_((y0 + 1) % gh, x0 % gw)]
        g11 = grid[np.ix_((y0 + 1) % gh, (x0 + 1) % gw)]
        total += amp * ((g00 * (1 - fx) + g10 * fx) * (1 - fy)
                        + (g01 * (1 - fx) + g11 * fx) * fy)
        norm += amp
        amp *= 0.55
    return total / norm


def rgb_array(w, h, color, noise, amount):
    base = np.array(color, dtype=float)
    wave = np.sin(np.arange(h) * 2 * math.pi / h)[:, None] * amount * 0.35
    arr = base[None, None, :] + (noise[:, :, None] - 0.5) * amount + wave[:, :, None]
    return np.clip(arr, 0, 255).astype(np.uint8)


def edge_groove(pen, w, h, dark=(38, 44, 44), light=(132, 128, 112), inset=1):
    pen.line((0, 0, w - 1, 0), fill=dark)
    pen.line((0, h - 1, w - 1, h - 1), fill=dark)
    pen.line((0, 0, 0, h - 1), fill=dark)
    pen.line((w - 1, 0, w - 1, h - 1), fill=dark)
    if inset:
        pen.line((1, 1, w - 2, 1), fill=light)
        pen.line((1, 1, 1, h - 2), fill=light)


def wall_plaster():
    rng = random.Random(101)
    w = h = 128
    n = periodic_noise(w, h, 32, rng, 4)
    image = Image.fromarray(rgb_array(w, h, (150, 145, 126), n, 26), 'RGB')
    pen = ImageDraw.Draw(image)
    for _ in range(5):
        x = rng.randrange(12, 116)
        y = rng.randrange(8, 62)
        pen.ellipse((x, y, x + rng.randrange(14, 34), y + rng.randrange(10, 24)),
                    fill=(132, 128, 110))
    for _ in range(4):
        x = rng.randrange(10, 118)
        pts = [(x, 0)]
        for y in range(10, 100, 10):
            pts.append((x + rng.choice((-1, 0, 1)), y))
        pen.line(pts, fill=(111, 108, 92), width=1)
    pen.rectangle((0, 98, w - 1, h - 1), fill=(126, 121, 104))
    pen.line((0, 97, w - 1, 97), fill=(176, 170, 150))
    pen.line((0, 113, w - 1, 113), fill=(100, 96, 82))
    for _ in range(9):
        x, y = rng.randrange(0, 128), rng.randrange(100, 127)
        pen.line((x, y, x + rng.randrange(4, 12), y), fill=(112, 108, 92))
    edge_groove(pen, w, h, dark=(58, 58, 50), light=(178, 172, 152))
    return image


def wall_acoustic():
    rng = random.Random(102)
    w = h = 128
    n = periodic_noise(w, h, 16, rng, 3)
    image = Image.fromarray(rgb_array(w, h, (78, 92, 98), n, 18), 'RGB')
    pen = ImageDraw.Draw(image)
    for x in range(0, w, 32):
        pen.line((x, 0, x, h - 1), fill=(44, 54, 60))
        pen.line(((x + 1) % w, 0, (x + 1) % w, h - 1), fill=(104, 116, 120))
    for y in range(0, h, 32):
        pen.line((0, y, w - 1, y), fill=(44, 54, 60))
        pen.line((0, (y + 1) % h, w - 1, (y + 1) % h), fill=(104, 116, 120))
    for px in range(0, w, 32):
        for py in range(0, h, 32):
            shade = 84 + (px // 32 + py // 32) % 3 * 4
            for j in range(4):
                for i in range(4):
                    pen.point((px + 9 + i * 5, py + 9 + j * 5), fill=(shade, 100, 104))
    for _ in range(6):
        x, y = rng.randrange(4, 120), rng.randrange(4, 120)
        pen.line((x, y, x + 6, y + 2), fill=(66, 78, 82))
    edge_groove(pen, w, h, dark=(42, 50, 54), light=(108, 118, 120))
    return image


def wall_ceramic():
    rng = random.Random(103)
    w = h = 128
    n = periodic_noise(w, h, 16, rng, 3)
    image = Image.fromarray(rgb_array(w, h, (64, 94, 90), n, 20), 'RGB')
    pen = ImageDraw.Draw(image)
    size = 32
    for ty in range(0, h, size):
        for tx in range(0, w, size):
            tone = 6 * ((tx // size + ty // size) % 3) - 4
            pen.rectangle((tx + 2, ty + 2, tx + size - 3, ty + size - 3),
                          fill=(68 + tone, 98 + tone, 94 + tone))
            pen.line((tx + 2, ty + 2, tx + size - 3, ty + 2), fill=(94 + tone, 124, 118))
            pen.line((tx + 2, ty + 2, tx + 2, ty + size - 3), fill=(88 + tone, 118, 112))
            pen.line((tx + 2, ty + size - 3, tx + size - 3, ty + size - 3),
                     fill=(44, 70, 68))
            if rng.random() < 0.35:
                cx, cy = tx + rng.randrange(9, 24), ty + rng.randrange(9, 24)
                pen.polygon([(cx, cy), (cx + 4, cy + 2), (cx + 1, cy + 5)],
                            fill=(40, 62, 60))
    pen.rectangle((0, 70, w - 1, 78), fill=(120, 90, 62))
    pen.line((0, 70, w - 1, 70), fill=(168, 126, 82))
    pen.line((0, 78, w - 1, 78), fill=(74, 56, 42))
    for x in (10, 42, 74, 106):
        pen.rectangle((x, 68, x + 6, 80), fill=(90, 74, 56), outline=(52, 44, 36))
    pen.rectangle((96, 72, 103, 76), fill=(228, 158, 60), outline=(60, 44, 30))
    edge_groove(pen, w, h, dark=(38, 56, 54), light=(96, 126, 118))
    return image


def wall_duct():
    rng = random.Random(104)
    w = h = 128
    n = periodic_noise(w, h, 32, rng, 3)
    arr = rgb_array(w, h, (108, 96, 78), n, 22).astype(float)
    rib = np.sin(np.arange(h) * 2 * math.pi / 16)[:, None, None] * 12
    image = Image.fromarray(np.clip(arr + rib, 0, 255).astype(np.uint8), 'RGB')
    pen = ImageDraw.Draw(image)
    for y in (8, 40, 72, 104):
        pen.line((0, y, w - 1, y), fill=(74, 66, 54))
        pen.line((0, y + 1, w - 1, y + 1), fill=(142, 124, 96))
        for x in range(6, w, 16):
            pen.ellipse((x - 1, y - 1, x + 1, y + 1), fill=(66, 58, 48))
            pen.point((x - 1, y), fill=(160, 142, 112))
    for _ in range(14):
        x = rng.randrange(4, 124)
        y = rng.choice((8, 40, 72, 104))
        length = rng.randrange(5, 18)
        pen.line((x, y + 2, x - 1, y + length), fill=(122, 72, 40))
    for _ in range(5):
        y = rng.randrange(16, 120)
        pen.line((0, y, w - 1, y), fill=(96, 86, 70))
    edge_groove(pen, w, h, dark=(58, 50, 40), light=(148, 130, 100))
    return image


def wall_service_panel():
    rng = random.Random(105)
    w = h = 128
    n = periodic_noise(w, h, 16, rng, 3)
    image = Image.fromarray(rgb_array(w, h, (92, 100, 98), n, 14), 'RGB')
    pen = ImageDraw.Draw(image)
    pen.rectangle((10, 12, 117, 112), fill=(84, 92, 90), outline=(50, 58, 58), width=2)
    pen.line((12, 14, 115, 14), fill=(120, 128, 124))
    pen.line((12, 14, 12, 110), fill=(116, 124, 120))
    pen.line((12, 110, 115, 110), fill=(58, 66, 66))
    for y in (32, 92):
        pen.rectangle((14, y, 24, y + 12), fill=(72, 80, 78), outline=(44, 52, 52))
        pen.point((20, y + 4), fill=(110, 116, 112))
    pen.rectangle((92, 56, 112, 66), fill=(64, 72, 72), outline=(40, 48, 48))
    pen.rectangle((96, 59, 108, 63), fill=(120, 128, 122))
    for j in range(4):
        pen.rectangle((30, 86 + j * 5, 68, 88 + j * 5), fill=(46, 54, 54))
    pen.rectangle((98, 20, 108, 30), fill=(52, 50, 42), outline=(36, 34, 30))
    pen.rectangle((101, 23, 105, 27), fill=(226, 156, 58))
    for _ in range(12):
        x, y = rng.randrange(14, 114), rng.randrange(16, 108)
        pen.line((x, y, x + rng.randrange(2, 7), y + rng.choice((-1, 0, 1))),
                 fill=(70, 78, 76))
    edge_groove(pen, w, h, dark=(44, 50, 50), light=(122, 128, 122))
    return image


def wall_wayfinding():
    rng = random.Random(106)
    w = h = 128
    n = periodic_noise(w, h, 32, rng, 3)
    image = Image.fromarray(rgb_array(w, h, (158, 152, 132), n, 18), 'RGB')
    pen = ImageDraw.Draw(image)
    pen.rectangle((0, 46, w - 1, 78), fill=(52, 72, 80))
    pen.line((0, 44, w - 1, 44), fill=(112, 88, 58))
    pen.line((0, 80, w - 1, 80), fill=(112, 88, 58))
    for x in (18, 52, 86):
        pen.polygon([(x, 56), (x + 12, 62), (x, 68), (x + 4, 62)], fill=(226, 162, 64))
        pen.rectangle((x + 18, 59, x + 24, 65), fill=(226, 162, 64))
    for _ in range(7):
        x, y = rng.randrange(6, 120), rng.randrange(84, 122)
        pen.line((x, y, x + rng.randrange(4, 10), y), fill=(136, 130, 112))
    for _ in range(4):
        x = rng.randrange(8, 118)
        pen.line((x, 12, x + 1, 34), fill=(138, 132, 114))
    edge_groove(pen, w, h, dark=(70, 68, 58), light=(180, 174, 154))
    return image


WALL_BUILDERS = {
    'NWALL01': wall_plaster, 'NWALL02': wall_acoustic, 'NWALL03': wall_ceramic,
    'NWALL04': wall_duct, 'NWALL05': wall_service_panel, 'NWALL06': wall_wayfinding,
}


def flat_carpet():
    rng = random.Random(201)
    w = h = 64
    n = periodic_noise(w, h, 16, rng, 4)
    image = Image.fromarray(rgb_array(w, h, (94, 90, 80), n, 34), 'RGB')
    pen = ImageDraw.Draw(image)
    for _ in range(240):
        x, y = rng.randrange(0, 64), rng.randrange(0, 64)
        c = rng.choice(((112, 106, 92), (78, 76, 68), (102, 96, 82)))
        pen.point((x, y), fill=c)
    for x in range(0, 64, 8):
        pen.line((x, 0, x, h - 1), fill=(88, 84, 74))
    return image


def flat_utility():
    rng = random.Random(202)
    w = h = 64
    n = periodic_noise(w, h, 16, rng, 3)
    image = Image.fromarray(rgb_array(w, h, (84, 92, 96), n, 18), 'RGB')
    pen = ImageDraw.Draw(image)
    for x in range(0, 64, 16):
        pen.line((x, 0, x, h - 1), fill=(52, 60, 64))
        pen.line(((x + 1) % w, 0, (x + 1) % w, h - 1), fill=(102, 110, 112))
    for y in range(0, 64, 16):
        pen.line((0, y, w - 1, y), fill=(52, 60, 64))
        pen.line((0, (y + 1) % h, w - 1, (y + 1) % h), fill=(102, 110, 112))
    for _ in range(18):
        x, y = rng.randrange(2, 62), rng.randrange(2, 62)
        pen.line((x, y, x + rng.randrange(2, 8), y), fill=(72, 80, 84))
    return image


def flat_ceiling():
    rng = random.Random(203)
    w = h = 64
    n = periodic_noise(w, h, 16, rng, 3)
    image = Image.fromarray(rgb_array(w, h, (166, 164, 152), n, 12), 'RGB')
    pen = ImageDraw.Draw(image)
    for x in range(0, 64, 32):
        pen.line((x, 0, x, h - 1), fill=(138, 136, 124))
    for y in range(0, 64, 32):
        pen.line((0, y, w - 1, y), fill=(138, 136, 124))
    for px in range(0, 64, 32):
        for py in range(0, 64, 32):
            for j in range(5):
                for i in range(5):
                    pen.point((px + 6 + i * 5, py + 6 + j * 5), fill=(150, 148, 136))
    for _ in range(3):
        x, y = rng.randrange(3, 60), rng.randrange(3, 60)
        pen.ellipse((x, y, x + 5, y + 3), fill=(158, 156, 144))
    return image


def flat_fluorescent():
    rng = random.Random(204)
    w = h = 64
    n = periodic_noise(w, h, 16, rng, 3)
    image = Image.fromarray(rgb_array(w, h, (58, 64, 66), n, 12), 'RGB')
    pen = ImageDraw.Draw(image)
    for y in (8, 36):
        pen.rectangle((7, y, 57, y + 20), fill=(146, 146, 136))
        pen.rectangle((9, y + 2, 55, y + 18), fill=(222, 218, 200))
        pen.rectangle((9, y + 2, 55, y + 6), fill=(208, 204, 188))
    for x in range(0, 64, 32):
        pen.line((x, 0, x, h - 1), fill=(46, 52, 54))
    for y in (0, 32):
        pen.line((0, y, w - 1, y), fill=(46, 52, 54))
    return image


FLAT_BUILDERS = {
    'NFLAT01': flat_carpet, 'NFLAT02': flat_utility,
    'NFLAT03': flat_ceiling, 'NFLAT04': flat_fluorescent,
}


# -- environmental props -----------------------------------------------------
def prop_service_lamp():
    image = Image.new('RGBA', (96, 128), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    pen.rectangle((22, 116, 74, 124), fill=(52, 58, 58, 255), outline=DARK)
    pen.rectangle((18, 121, 78, 126), fill=(38, 44, 44, 255), outline=DARK)
    pen.rectangle((44, 70, 52, 118), fill=(74, 82, 82, 255), outline=DARK)
    pen.rectangle((46, 72, 49, 116), fill=(112, 118, 114, 255))
    pen.rounded_rectangle((22, 26, 74, 74), radius=6, fill=(58, 68, 70, 255), outline=DARK, width=2)
    pen.rectangle((28, 34, 68, 64), fill=(226, 158, 56, 255), outline=(120, 78, 32, 255))
    pen.rectangle((30, 36, 66, 44), fill=(244, 190, 96, 255))
    for x in (34, 46, 58, 66):
        pen.line((x, 30, x, 70), fill=(36, 44, 46, 255), width=2)
    pen.rectangle((18, 20, 78, 30), fill=(74, 82, 80, 255), outline=DARK)
    pen.rectangle((38, 14, 58, 20), fill=(96, 104, 100, 255), outline=DARK)
    for x in (26, 70):
        pen.rectangle((x - 2, 76, x + 2, 80), fill=OXIDE, outline=DARK)
    pen.line((20, 118, 14, 124), fill=(40, 46, 46, 255), width=3)
    pen.line((76, 118, 82, 124), fill=(40, 46, 46, 255), width=3)
    return image


def prop_cable_shrine():
    image = Image.new('RGBA', (96, 128), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    pen.rectangle((18, 112, 78, 122), fill=(54, 60, 58, 255), outline=DARK)
    pen.rectangle((14, 120, 82, 126), fill=(38, 44, 44, 255), outline=DARK)
    for r, color, width in ((26, (30, 38, 40, 255), 5), (20, (116, 98, 66, 255), 3),
                            (14, (34, 42, 44, 255), 4)):
        pen.arc((48 - r, 82 - r, 48 + r, 82 + r), 185, 355, fill=color, width=width)
    pen.rectangle((40, 92, 56, 114), fill=(70, 78, 76, 255), outline=DARK)
    pen.ellipse((36, 30, 60, 46), fill=BONE, outline=DARK, width=2)
    pen.ellipse((38, 42, 58, 54), fill=PLASTER, outline=DARK, width=2)
    pen.ellipse((40, 52, 56, 62), fill=BONE, outline=DARK, width=2)
    pen.rectangle((42, 60, 54, 94), fill=(88, 94, 90, 255), outline=DARK)
    pen.rectangle((44, 64, 52, 90), fill=(118, 122, 114, 255))
    pen.line((30, 20, 30, 70), fill=(28, 36, 38, 255), width=2)
    pen.line((66, 20, 66, 74), fill=(28, 36, 38, 255), width=2)
    pen.rectangle((22, 66, 38, 78), fill=(176, 166, 142, 255), outline=DARK)
    pen.rectangle((60, 70, 74, 80), fill=(176, 166, 142, 255), outline=DARK)
    for x, y in ((26, 70), (64, 74)):
        pen.line((x, y + 2, x + 8, y + 2), fill=(96, 92, 78, 255))
    pen.rectangle((24, 90, 32, 99), fill=(214, 146, 48, 255), outline=(92, 60, 28, 255))
    pen.rectangle((64, 94, 72, 103), fill=(214, 146, 48, 255), outline=(92, 60, 28, 255))
    pen.ellipse((30, 16, 36, 22), fill=OXIDE, outline=DARK)
    return image


def prop_directory_sign():
    image = Image.new('RGBA', (96, 128), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    for x in (20, 70):
        pen.rectangle((x, 66, x + 6, 122), fill=(72, 80, 80, 255), outline=DARK)
        pen.line((x + 2, 68, x + 2, 120), fill=(112, 118, 112, 255))
        pen.polygon([(x - 4, 122), (x + 10, 122), (x + 8, 126), (x - 2, 126)],
                    fill=(44, 50, 50, 255), outline=DARK)
    pen.rectangle((8, 12, 88, 82), fill=(52, 70, 78, 255), outline=DARK, width=2)
    pen.rectangle((12, 16, 84, 78), outline=(112, 90, 58), width=2)
    for row in range(4):
        for col in range(4):
            x = 18 + col * 16
            y = 22 + row * 12
            pen.rectangle((x, y, x + 10, y + 7), fill=(32, 44, 48, 255))
            pen.line((x, y, x + 10, y), fill=(78, 96, 102, 255))
    pen.polygon([(24, 70), (34, 74), (24, 78), (27, 74)], fill=(224, 158, 60))
    pen.rectangle((38, 72, 76, 76), fill=(224, 158, 60))
    pen.rectangle((42, 8, 54, 12), fill=(90, 98, 96, 255), outline=DARK)
    return image


PROP_BUILDERS = {'service_lamp': prop_service_lamp, 'cable_shrine': prop_cable_shrine,
                 'directory_sign': prop_directory_sign}


# -- assembly ----------------------------------------------------------------
def creature_atlas(family, variant):
    atlas = Image.new('RGBA', (FRAMES * SIZE, len(STATES) * SIZE), (0, 0, 0, 0))
    draw = latchwing if family == 'latchwing' else relay_choir
    for row, state in enumerate(STATES):
        for col in range(FRAMES):
            atlas.alpha_composite(draw(variant, state, col), (col * SIZE, row * SIZE))
    return atlas


def silhouette(image):
    alpha = np.asarray(image)[:, :, 3] > 0
    ys, xs = np.nonzero(alpha)
    return alpha, (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))


def tiled(tile):
    w, h = tile.size
    out = Image.new(tile.mode, (w * 2, h * 2))
    for j in range(2):
        for i in range(2):
            out.paste(tile, (i * w, j * h))
    return out


def build_all():
    assets = {}
    for family, variants in FAMILIES.items():
        for variant in variants:
            assets[f'creatures/{family}_{variant}.png'] = creature_atlas(family, variant)
    for name, builder in WALL_BUILDERS.items():
        tile = builder()
        assets[f'walls/{name}.png'] = tile
        assets[f'sheets/{name}_2x2.png'] = tiled(tile)
    for name, builder in FLAT_BUILDERS.items():
        tile = builder()
        assets[f'flats/{name}.png'] = tile
        assets[f'sheets/{name}_2x2.png'] = tiled(tile)
    for name, builder in PROP_BUILDERS.items():
        assets[f'props/{name}.png'] = builder()
    return assets


# -- contact sheets ----------------------------------------------------------
def label(pen, xy, text, fill=(210, 206, 188)):
    pen.text(xy, text, fill=fill)


def contact_creatures(assets):
    cw, ch, m, lab = 256, 384, 20, 18
    sheet = Image.new('RGB', (2 * cw + 3 * m, 2 * (ch + lab) + 3 * m), (22, 26, 28))
    pen = ImageDraw.Draw(sheet)
    for i, (family, variant) in enumerate((f, v) for f, vs in FAMILIES.items() for v in vs):
        atlas = assets[f'creatures/{family}_{variant}.png']
        x, y = m + (i % 2) * (cw + m), m + (i // 2) * (ch + lab + m)
        sheet.paste(atlas.resize((cw, ch), Image.Resampling.LANCZOS), (x, y))
        label(pen, (x, y + ch + 3), f'{family.upper()} {variant} - 6 states x 4 frames')
    return sheet


def contact_materials(assets):
    m = 16
    sheet = Image.new('RGB', (900, 300), (22, 26, 28))
    pen = ImageDraw.Draw(sheet)
    x = m
    for name in WALLS:
        sheet.paste(assets[f'walls/{name}.png'], (x, 24))
        label(pen, (x, 8), name)
        x += 128 + 10
    x = m
    for name in FLATS:
        sheet.paste(assets[f'flats/{name}.png'], (x, 190))
        label(pen, (x, 172), name)
        x += 64 + 12
    label(pen, (m, 158), 'walls 128x128, flats 64x64; 2x2 tiling sheets are in art/sheets/')
    label(pen, (m, 274), 'generated procedural surfaces; no sampled texture or text')
    return sheet


def contact_props(assets):
    m, scale = 20, 2
    sheet = Image.new('RGB', (3 * 96 * scale + 4 * m, 128 * scale + 58), (22, 26, 28))
    pen = ImageDraw.Draw(sheet)
    for i, name in enumerate(PROPS):
        x = m + i * (96 * scale + m)
        image = assets[f'props/{name}.png']
        sheet.paste(image.resize((96 * scale, 128 * scale), Image.Resampling.NEAREST), (x, 22))
        label(pen, (x, 8), name)
    return sheet


# -- checks ------------------------------------------------------------------
def pixels_differ(a, b):
    x = np.asarray(a).astype(int)
    y = np.asarray(b).astype(int)
    return int((np.abs(x - y).max(axis=2) > 16).sum())


def seam_metrics(tile):
    arr = np.asarray(tile).astype(float)
    wrap_col = float(np.abs(arr[:, 0] - arr[:, -1]).mean())
    wrap_row = float(np.abs(arr[0, :] - arr[-1, :]).mean())
    col_steps = np.abs(arr[:, 1:] - arr[:, :-1]).mean(axis=2)
    row_steps = np.abs(arr[1:, :] - arr[:-1, :]).mean(axis=2)
    return {'wrap_col': wrap_col, 'wrap_row': wrap_row,
            'inner_col': float(np.percentile(col_steps, 95)),
            'inner_row': float(np.percentile(row_steps, 95))}


def check_assets(assets):
    checks = []

    def add(name, ok, detail):
        checks.append({'name': name, 'pass': bool(ok), 'detail': detail})

    frames = {}
    for family, variants in FAMILIES.items():
        for variant in variants:
            key = f'{family}_{variant}'
            atlas = assets[f'creatures/{key}.png']
            add(f'atlas_geometry [{key}]', atlas.size == (512, 768) and atlas.mode == 'RGBA',
                f'{atlas.size} {atlas.mode}')
            for row, state in enumerate(STATES):
                for col in range(FRAMES):
                    frames[(key, state, col)] = atlas.crop(
                        (col * SIZE, row * SIZE, (col + 1) * SIZE, (row + 1) * SIZE))
            if family == 'latchwing':
                idle_w = max(silhouette(frames[(key, 'idle', i)])[1][2]
                             - silhouette(frames[(key, 'idle', i)])[1][0] for i in range(4))
                warn_w = max(silhouette(frames[(key, 'warning', i)])[1][2]
                             - silhouette(frames[(key, 'warning', i)])[1][0] for i in range(4))
                add(f'warning_aperture [{key}]', warn_w >= idle_w + 10,
                    f'warning silhouette {warn_w}px wide vs idle {idle_w}px')
            motions = []
            for state in STATES:
                for i in range(3):
                    motions.append(pixels_differ(frames[(key, state, i)],
                                                 frames[(key, state, i + 1)]))
            add(f'frame_motion [{key}]', min(motions) >= 24,
                f'min consecutive frame difference {min(motions)} px, max {max(motions)} px')
            border = True
            alpha_frac = []
            bottoms, tops = [], []
            for state in STATES:
                for i in range(4):
                    alpha, box = silhouette(frames[(key, state, i)])
                    a = np.asarray(frames[(key, state, i)])[:, :, 3]
                    border = border and not a[0].any() and not a[-1].any() \
                        and not a[:, 0].any() and not a[:, -1].any()
                    alpha_frac.append(float(alpha.mean()))
                    if state != 'death':
                        bottoms.append(box[3])
                        tops.append(box[1])
            add(f'transparent_padding [{key}]', border and 0.02 < min(alpha_frac)
                and max(alpha_frac) < 0.62,
                f'alpha {min(alpha_frac):.3f}..{max(alpha_frac):.3f}; border fully transparent')
            add(f'feet_anchor [{key}]', min(bottoms) >= 104 and max(bottoms) - min(bottoms) <= 10,
                f'non-death bottom row {min(bottoms)}..{max(bottoms)}; top {min(tops)}..{max(tops)}')
            alpha, corpse = silhouette(frames[(key, 'death', 3)])
            add(f'visible_corpse [{key}]', alpha.mean() > 0.02 and corpse[3] >= 110
                and corpse[3] - corpse[1] <= 60,
                f'final corpse bbox {corpse}, alpha {alpha.mean():.3f}')
            add(f'state_contrast [{key}]',
                pixels_differ(frames[(key, 'idle', 0)], frames[(key, 'hurt', 2)]) >= 200
                and pixels_differ(frames[(key, 'warning', 3)], frames[(key, 'attack', 2)]) >= 150,
                'hurt and attack poses differ strongly from idle and warning')
        va, vb = frames[(f'{family}_A', 'idle', 0)], frames[(f'{family}_B', 'idle', 0)]
        add(f'variant_silhouettes [{family}]', pixels_differ(va, vb) >= 300,
            f'variants differ in {pixels_differ(va, vb)} pixels at idle frame 0')
    la = np.asarray(frames[('latchwing_A', 'idle', 0)])[:, :, 3] > 0
    ra = np.asarray(frames[('relay_choir_A', 'idle', 0)])[:, :, 3] > 0
    iou = float((la & ra).sum() / max(1, (la | ra).sum()))
    add('family_distinct', iou < 0.6, f'latchwing/relay-choir idle mask IoU {iou:.2f}')

    for name in WALLS:
        tile = assets[f'walls/{name}.png']
        m = seam_metrics(tile)
        ok = (tile.size == (128, 128) and tile.mode == 'RGB'
              and m['wrap_col'] <= max(8.0, m['inner_col'] * 1.35 + 3)
              and m['wrap_row'] <= max(8.0, m['inner_row'] * 1.35 + 3))
        add(f'wall [{name}]', ok,
            f'{tile.size} {tile.mode}; wrap col {m["wrap_col"]:.2f} row {m["wrap_row"]:.2f} '
            f'vs inner {m["inner_col"]:.2f}/{m["inner_row"]:.2f}')
        sheet = assets[f'sheets/{name}_2x2.png']
        arr = np.asarray(tile)
        ok = sheet.size == (256, 256) and all(
            np.array_equal(np.asarray(sheet.crop((i * 128, j * 128, (i + 1) * 128, (j + 1) * 128))), arr)
            for j in range(2) for i in range(2))
        add(f'wall_2x2 [{name}]', ok, '2x2 sheet is the identical tile repeated')
        add(f'wall_relief [{name}]', len(np.unique(arr.reshape(-1, 3), axis=0)) >= 24,
            f'{len(np.unique(arr.reshape(-1, 3), axis=0))} colours')
    for name in FLATS:
        tile = assets[f'flats/{name}.png']
        m = seam_metrics(tile)
        ok = (tile.size == (64, 64) and tile.mode == 'RGB'
              and m['wrap_col'] <= max(8.0, m['inner_col'] * 1.35 + 3)
              and m['wrap_row'] <= max(8.0, m['inner_row'] * 1.35 + 3))
        add(f'flat [{name}]', ok,
            f'{tile.size} {tile.mode}; wrap col {m["wrap_col"]:.2f} row {m["wrap_row"]:.2f} '
            f'vs inner {m["inner_col"]:.2f}/{m["inner_row"]:.2f}')
        sheet = assets[f'sheets/{name}_2x2.png']
        ok = sheet.size == (128, 128) and all(
            np.array_equal(np.asarray(sheet.crop((i * 64, j * 64, (i + 1) * 64, (j + 1) * 64))),
                           np.asarray(tile)) for j in range(2) for i in range(2))
        add(f'flat_2x2 [{name}]', ok, '2x2 sheet is the identical tile repeated')
    for name in PROPS:
        image = assets[f'props/{name}.png']
        alpha, box = silhouette(image)
        a = np.asarray(image)[:, :, 3]
        border = not a[0].any() and not a[-1].any() and not a[:, 0].any() and not a[:, -1].any()
        add(f'prop [{name}]', image.size == (96, 128) and image.mode == 'RGBA' and border
            and 0.03 < alpha.mean() < 0.7 and box[3] >= 120,
            f'{image.size} {image.mode}; alpha {alpha.mean():.3f}; bbox {box}')
    generated = {k: v for k, v in assets.items() if not k.startswith('contact')}
    hashes = {}
    for key, image in sorted(generated.items()):
        hashes[key] = hashlib.sha256(image.tobytes()).hexdigest()
    add('deterministic_art', hashes == {k: hashlib.sha256(v.tobytes()).hexdigest()
                                        for k, v in sorted(generated.items())},
        f'{len(assets)} assets; two builds are byte-identical')
    return {'passed': all(c['pass'] for c in checks), 'checks': checks,
            'summary': {'total': len(checks), 'passed': sum(c['pass'] for c in checks),
                        'failed': sum(not c['pass'] for c in checks)},
            'asset_hashes': hashes}


def main():
    assets = build_all()
    for key, image in assets.items():
        target = ART / key
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target)
    assets['contact_creatures.png'] = contact_creatures(assets)
    assets['contact_materials.png'] = contact_materials(assets)
    assets['contact_props.png'] = contact_props(assets)
    for key in ('contact_creatures.png', 'contact_materials.png', 'contact_props.png'):
        assets[key].save(ART / key)
    result = check_assets(assets)
    (ROOT / 'art-checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result['summary'], indent=2))
    failed = [c['name'] for c in result['checks'] if not c['pass']]
    if failed:
        print('FAILED:', failed)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
