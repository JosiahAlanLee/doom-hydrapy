#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Null Run environment art: three original procedural municipal-horror kits.

Everything here is drawn from code with Pillow and numpy.  No game pixel,
texture, font or logo is sampled.  Walls are 128x128 RGB and seamless on both
axes; flats are 64x64 RGB and seamless on both axes; props are 96x128 RGBA,
bottom anchored with transparent padding.  A shared edge frame is drawn last so
opposite edge pixels are exactly equal.

CLI:
    python art.py --out DIRECTORY [--seed INTEGER]

The output is deterministic: local random.Random instances only, no global
random state and no hash-dependent values.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

DEFAULT_SEED = 20261031
FORMAT = 'nullrun-environment-kit-1'
SET_IDS = ('drowned_records', 'switchyard_chapel', 'after_hours_pavilion')
WALL_ROLES = (
    'primary wall', 'relief / panel', 'structural material', 'service hardware',
    'shutter / window', 'wayfinding / accent', 'landmark A', 'landmark B',
)
FLAT_ROLES = ('primary floor', 'utility floor', 'ordinary ceiling', 'lit ceiling')
PROP_SLOTS = ('service_lamp', 'cable_shrine', 'directory_sign')

# Named palettes.  The same hex values are published in environments.json.
PALETTES = {
    'drowned_records': {
        'chalk': '#E8E1CC', 'bone': '#D8CFB6', 'paper': '#C4B99C',
        'silt': '#A79778', 'petrol': '#2F4147', 'slate': '#566A70',
        'copper': '#9A6238', 'copper_light': '#C98B56', 'ink': '#1B2528',
        'glass': '#9DAA9E',
    },
    'switchyard_chapel': {
        'ivory': '#DDD6C0', 'porcelain': '#EFEAD8', 'bone': '#BFB7A1',
        'rust': '#8E3F2B', 'rust_light': '#B65C3B', 'iron': '#3B3734',
        'charcoal': '#252423', 'cable': '#171818', 'amber': '#E0A13C',
        'amber_light': '#FFD487', 'oxide': '#6D3927',
    },
    'after_hours_pavilion': {
        'plum': '#6E5768', 'plum_dark': '#463645', 'plum_light': '#8D7488',
        'slate': '#5D6872', 'terrazzo': '#D9D3C5', 'terrazzo_dark': '#B3AA99',
        'brass': '#A8864C', 'brass_light': '#D2B06E', 'cream': '#EFE7D6',
        'ink': '#241F28', 'dust': '#A79C90',
    },
}


def hx(value):
    value = value.lstrip('#')
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def C(set_id, name):
    return hx(PALETTES[set_id][name])


def asset_seed(seed, set_index, kind_index, index):
    """Stable, platform-independent seed derivation (never uses hash())."""
    return (int(seed) * 1000003 + set_index * 7919 + kind_index * 104729
            + index * 1291) & 0x7FFFFFFF


# -- periodic material helpers ----------------------------------------------
def periodic_noise(w, h, cell, rng, octaves=3):
    """Smooth value noise that wraps exactly at the tile edges."""
    total = np.zeros((h, w), dtype=float)
    norm, amp = 0.0, 1.0
    for octave in range(octaves):
        c = max(2, int(cell) >> octave)
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


def material(w, h, base, seed, cell=32, amount=10, octaves=3, tilt=0.0):
    """Broad, low-contrast material field; detail is drawn on top, not noise."""
    rng = random.Random(seed)
    n = periodic_noise(w, h, cell, rng, octaves)
    yy = np.arange(h)[:, None].astype(float) / max(1, h - 1)
    xx = np.arange(w)[None, :].astype(float) / max(1, w - 1)
    light = ((xx - 0.5) * tilt + (yy - 0.5) * tilt * 0.55)
    arr = (np.asarray(base, dtype=float)[None, None, :]
           + (n - 0.5)[:, :, None] * amount + light[:, :, None])
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), 'RGB')


def _overlay(im, draw_fn):
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(ov))
    if im.mode == 'RGBA':
        return Image.alpha_composite(im, ov)
    return Image.alpha_composite(im.convert('RGBA'), ov).convert('RGB')


def wash_rect(im, box, color, alpha):
    return _overlay(im, lambda d: d.rectangle(box, fill=tuple(color) + (alpha,)))


def wash_poly(im, points, color, alpha):
    return _overlay(im, lambda d: d.polygon(points, fill=tuple(color) + (alpha,)))


def wash_ellipse(im, box, color, alpha):
    return _overlay(im, lambda d: d.ellipse(box, fill=tuple(color) + (alpha,)))


def bevel(pen, box, fill, light, dark, depth=1):
    """Raised box: light top/left, dark bottom/right."""
    x0, y0, x1, y1 = box
    pen.rectangle(box, fill=fill)
    for i in range(depth):
        pen.line((x0 + i, y0 + i, x1 - i, y0 + i), fill=light)
        pen.line((x0 + i, y0 + i, x0 + i, y1 - i), fill=light)
        pen.line((x0 + i, y1 - i, x1 - i, y1 - i), fill=dark)
        pen.line((x1 - i, y0 + i, x1 - i, y1 - i), fill=dark)


def recess(pen, box, fill, dark, light, depth=1):
    """Recessed box: dark top/left, light bottom/right."""
    bevel(pen, box, fill, dark, light, depth)


def shadow(pen, box, color, offset=2):
    x0, y0, x1, y1 = box
    pen.rectangle((x0 + offset, y0 + offset, x1 + offset, y1 + offset), fill=color)


def bolt(pen, x, y, r, face, edge, shine=None):
    pen.ellipse((x - r, y - r, x + r, y + r), fill=face, outline=edge)
    if shine:
        pen.point((x - max(1, r // 2), y - max(1, r // 2)), fill=shine)
        pen.point((x - max(1, r // 2) + 1, y - max(1, r // 2)), fill=shine)


def flat_border(im, color):
    """One constant edge pixel: exact opposite-edge equality on both axes."""
    d = ImageDraw.Draw(im)
    w, h = im.size
    d.rectangle((0, 0, w - 1, h - 1), outline=color)


def wall_frame(im, edge, light, dark):
    """Constant 1px gasket, then a directional inset bevel. Edge rows match."""
    d = ImageDraw.Draw(im)
    w, h = im.size
    d.rectangle((0, 0, w - 1, h - 1), outline=edge)
    d.line((1, 1, w - 2, 1), fill=light)
    d.line((1, 1, 1, h - 2), fill=light)
    d.line((1, h - 2, w - 2, h - 2), fill=dark)
    d.line((w - 2, 1, w - 2, h - 2), fill=dark)


def scratches(pen, rng, color, count, box):
    x0, y0, x1, y1 = box
    for _ in range(count):
        x, y = rng.randrange(x0, x1), rng.randrange(y0, y1)
        length = rng.randrange(2, 7)
        if rng.random() < 0.5:
            pen.line((x, y, x + length, y + rng.choice((-1, 0, 1))), fill=color)
        else:
            pen.line((x, y, x + rng.choice((-1, 0, 1)), y + length), fill=color)


def chips(pen, rng, color, count, box, size=3):
    x0, y0, x1, y1 = box
    for _ in range(count):
        x, y = rng.randrange(x0, x1), rng.randrange(y0, y1)
        pen.polygon([(x, y), (x + rng.randrange(2, size + 2), y + 1),
                     (x + 1, y + rng.randrange(2, size + 2))], fill=color)


def insulator_stack(pen, cx, y0, y1, width, layers, body, light, shadow_col, edge):
    """Chunky flared ceramic petticoat stack, drawn front-on."""
    span = max(2, y1 - y0)
    pen.rectangle((cx - 2, y0, cx + 2, y1), fill=edge)
    step = max(4, span // max(1, layers))
    for layer in range(layers):
        y = y0 + round(span * layer / layers)
        h = max(3, step + 1)
        w = width - (layer % 2) * 2
        # flared lip at the bottom of each petticoat
        pen.ellipse((cx - w // 2 - 2, y + h - 2, cx + w // 2 + 2, y + h + 2),
                    fill=body, outline=edge)
        pen.rectangle((cx - w // 2, y, cx + w // 2, y + h), fill=body, outline=edge)
        pen.line((cx - w // 2, y, cx + w // 2, y), fill=light)
        pen.line((cx - w // 2, y + h, cx + w // 2, y + h), fill=shadow_col)
        pen.line((cx - w // 2 + 1, y + 1, cx - w // 2 + 1, y + h - 1), fill=light)
        pen.line((cx + w // 2 - 1, y + 1, cx + w // 2 - 1, y + h - 1), fill=shadow_col)
        for k in (-w // 4, 0, w // 4):
            pen.line((cx + k, y + 1, cx + k, y + h - 1),
                     fill=light if k == 0 else shadow_col)


def cable_path(points, sag, samples=40):
    """Sample a polyline with a downward parabolic sag between endpoints."""
    if len(points) != 2:
        return points
    (x0, y0), (x1, y1) = points
    out = []
    for i in range(samples + 1):
        t = i / samples
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t + sag * 4 * t * (1 - t)
        out.append((round(x), round(y)))
    return out


def braid(pen, path, main, accent, highlight, width=5):
    pen.line(path, fill=main, width=width, joint='curve')
    pen.line([(x, y - 1) for x, y in path], fill=accent, width=2, joint='curve')
    pen.line([(x, y - 2) for x, y in path], fill=highlight, width=1, joint='curve')


# -- Drowned Records ---------------------------------------------------------
def wall_drowned_01(seed):
    sid = 'drowned_records'
    ink, chalk, bone, paper = C(sid, 'ink'), C(sid, 'chalk'), C(sid, 'bone'), C(sid, 'paper')
    silt, petrol, slate = C(sid, 'silt'), C(sid, 'petrol'), C(sid, 'slate')
    copper, copper_l = C(sid, 'copper'), C(sid, 'copper_light')
    im = material(128, 128, bone, seed, cell=64, amount=9, tilt=8)
    im = wash_rect(im, (8, 4, 40, 122), chalk, 20)
    im = wash_rect(im, (70, 4, 104, 122), chalk, 14)
    im = wash_rect(im, (42, 4, 66, 122), silt, 16)
    tide = [(6, 79), (20, 76), (34, 80), (50, 77), (66, 80), (82, 76),
            (98, 79), (112, 77), (121, 80), (121, 92), (6, 92)]
    im = wash_poly(im, tide, petrol, 34)
    im = wash_poly(im, [(6, 79), (22, 77), (38, 80), (54, 78), (70, 80),
                        (88, 77), (104, 79), (121, 78), (121, 82), (6, 82)],
                   silt, 90)
    pen = ImageDraw.Draw(im)
    for y in (28, 56, 88):
        pen.line((7, y, 120, y), fill=silt)
        pen.line((7, y + 1, 120, y + 1), fill=chalk)
    pen.line((64, 8, 64, 112), fill=silt)
    pen.line((65, 8, 65, 112), fill=chalk)
    # copper shelf rail
    shadow(pen, (6, 104, 121, 109), ink, 2)
    bevel(pen, (6, 104, 121, 108), copper, copper_l, (96, 58, 34), 1)
    for x in (16, 108):
        bevel(pen, (x, 102, x + 5, 118), copper, copper_l, (94, 56, 32), 1)
        bolt(pen, x + 2, 114, 1, copper_l, ink)
    rng = random.Random(seed + 11)
    for _ in range(6):
        x, y = rng.randrange(12, 112), rng.randrange(10, 66)
        w, h = rng.randrange(4, 12), rng.randrange(3, 8)
        im = wash_ellipse(im, (x, y, x + w, y + h), silt, 50)
    pen = ImageDraw.Draw(im)
    scratches(pen, rng, (150, 138, 112), 5, (10, 8, 118, 100))
    chips(pen, rng, (120, 108, 86), 3, (10, 8, 118, 100))
    wall_frame(im, ink, chalk, silt)
    return im


def wall_drowned_02(seed):
    sid = 'drowned_records'
    ink, chalk, bone, paper = C(sid, 'ink'), C(sid, 'chalk'), C(sid, 'bone'), C(sid, 'paper')
    silt, petrol = C(sid, 'silt'), C(sid, 'petrol')
    copper, copper_l = C(sid, 'copper'), C(sid, 'copper_light')
    im = material(128, 128, silt, seed, cell=64, amount=10, tilt=6)
    pen = ImageDraw.Draw(im)
    bands = [(6, 30, paper), (30, 54, bone), (54, 72, (138, 122, 96)),
             (72, 100, paper), (100, 122, bone)]
    for y0, y1, col in bands:
        bevel(pen, (6, y0, 121, y1), col, chalk, (92, 80, 62), 2)
        for k in range(3):
            y = y0 + 4 + k * 5
            pen.line((9, y, 118, y), fill=(110, 96, 74))
            pen.line((9, y + 1, 118, y + 1), fill=chalk)
    # torn paper edge on the darkest stratum
    pen.polygon([(8, 58), (22, 54), (34, 59), (48, 55), (62, 60), (78, 56),
                 (94, 60), (108, 55), (120, 58), (120, 64), (8, 64)],
                fill=(176, 164, 136), outline=(112, 96, 76))
    for k in range(5):
        x = 112 + (k % 2) * 2
        y = 12 + k * 22
        bevel(pen, (x, y, x + 9, y + 6), copper, copper_l, (96, 58, 34), 1)
        pen.line((x + 2, y + 3, x + 7, y + 3), fill=ink)
    for x in (14, 102):
        bevel(pen, (x, 6, x + 4, 122), copper, copper_l, (96, 58, 34), 1)
        for y in range(14, 118, 20):
            bolt(pen, x + 2, y, 1, copper_l, ink)
    rng = random.Random(seed + 21)
    for _ in range(5):
        x, y = rng.randrange(10, 108), rng.randrange(10, 116)
        im = wash_ellipse(im, (x, y, x + rng.randrange(5, 14), y + rng.randrange(4, 9)),
                          silt, 55)
    pen = ImageDraw.Draw(im)
    scratches(pen, rng, (108, 94, 72), 6, (8, 8, 120, 120))
    chips(pen, rng, (92, 80, 62), 4, (8, 8, 120, 120))
    wall_frame(im, ink, bone, petrol)
    return im


def wall_drowned_03(seed):
    sid = 'drowned_records'
    ink, chalk, bone = C(sid, 'ink'), C(sid, 'chalk'), C(sid, 'bone')
    silt, petrol, slate = C(sid, 'silt'), C(sid, 'petrol'), C(sid, 'slate')
    copper, copper_l = C(sid, 'copper'), C(sid, 'copper_light')
    im = material(128, 128, petrol, seed, cell=32, amount=12, tilt=4)
    panels = [(3, 3, 60, 60), (67, 3, 124, 60), (3, 67, 60, 124), (67, 67, 124, 124)]
    for box in panels:
        im = wash_rect(im, box, slate, 52)
    pen = ImageDraw.Draw(im)
    for x0, y0, x1, y1 in panels:
        bevel(pen, (x0, y0, x1, y1), (74, 94, 100), (112, 132, 136),
              (39, 54, 60), 2)
        pen.line((x0 + 4, y0 + 4, x1 - 12, y1 - 12), fill=(92, 114, 120), width=2)
    # grout
    pen.rectangle((60, 2, 66, 125), fill=ink)
    pen.rectangle((2, 60, 125, 66), fill=ink)
    for x in (61, 62):
        pen.line((x, 4, x, 123), fill=(47, 63, 68))
    for y in (61, 62):
        pen.line((4, y, 123, y), fill=(47, 63, 68))
    # waterline and scum
    line = [(3, 89), (18, 87), (32, 90), (48, 88), (62, 91), (78, 87),
            (94, 90), (110, 88), (124, 90)]
    im = wash_poly(im, line + [(124, 124), (3, 124)], petrol, 70)
    pen = ImageDraw.Draw(im)
    pen.line(line, fill=(178, 170, 146), width=2)
    for x, y in line[1:-1:2]:
        pen.line((x, y - 2, x + 3, y - 2), fill=chalk)
    # drain plug
    pen.ellipse((26, 26, 38, 38), fill=copper, outline=ink)
    pen.ellipse((29, 29, 35, 35), fill=copper_l)
    pen.line((28, 32, 36, 32), fill=ink)
    pen.line((32, 28, 32, 36), fill=ink)
    # efflorescence and cracks
    rng = random.Random(seed + 31)
    for x, y in ((63, 63), (61, 62), (64, 64), (8, 62)):
        for k in range(4):
            pen.point((x + rng.randrange(-2, 3), y + rng.randrange(-2, 3)), fill=chalk)
    for x in (18, 90):
        pts = [(x, 8)]
        for y in range(18, 58, 8):
            pts.append((x + rng.choice((-2, -1, 0, 1, 2)), y))
        pen.line(pts, fill=(126, 144, 148))
    scratches(pen, rng, (70, 88, 94), 4, (8, 8, 120, 56))
    wall_frame(im, ink, slate, ink)
    return im


def wall_drowned_04(seed):
    sid = 'drowned_records'
    ink, chalk, bone = C(sid, 'ink'), C(sid, 'chalk'), C(sid, 'bone')
    silt, petrol, slate = C(sid, 'silt'), C(sid, 'petrol'), C(sid, 'slate')
    copper, copper_l = C(sid, 'copper'), C(sid, 'copper_light')
    im = material(128, 128, slate, seed, cell=64, amount=8, tilt=6)
    pen = ImageDraw.Draw(im)
    shadow(pen, (10, 16, 118, 112), ink, 2)
    bevel(pen, (10, 16, 118, 112), (70, 84, 90), (112, 128, 132), (40, 52, 58), 2)
    for x, y in ((16, 22), (112, 22), (16, 106), (112, 106)):
        bolt(pen, x, y, 2, (100, 112, 116), ink, chalk)
    # pump chest
    recess(pen, (34, 50, 94, 104), petrol, ink, slate, 2)
    for x in (50, 64, 78):
        pen.line((x, 54, x, 100), fill=(60, 78, 84), width=3)
        pen.line((x - 1, 54, x - 1, 100), fill=(88, 106, 112))
        pen.line((x + 2, 54, x + 2, 100), fill=ink)
    bevel(pen, (54, 58, 74, 72), copper, copper_l, (94, 56, 32), 1)
    pen.line((58, 62, 70, 62), fill=ink)
    pen.line((58, 66, 66, 66), fill=ink)
    # twin pipes
    for x0 in (40, 78):
        bevel(pen, (x0, 8, x0 + 10, 54), (86, 96, 100), (132, 142, 144), (48, 60, 66), 2)
        bevel(pen, (x0 - 3, 22, x0 + 13, 27), copper, copper_l, (94, 56, 32), 1)
        bevel(pen, (x0 - 3, 43, x0 + 13, 48), copper, copper_l, (94, 56, 32), 1)
        for bx in (x0, x0 + 10):
            bolt(pen, bx, 24, 1, copper_l, ink)
            bolt(pen, bx, 45, 1, copper_l, ink)
    # gauge
    bevel(pen, (88, 28, 110, 46), (72, 84, 88), (116, 128, 130), (40, 52, 56), 1)
    pen.ellipse((91, 30, 107, 44), fill=bone, outline=ink)
    pen.arc((93, 32, 105, 42), 200, 340, fill=petrol)
    pen.line((99, 37, 104, 33), fill=copper)
    bolt(pen, 99, 37, 1, copper_l, ink)
    # small handwheel
    pen.ellipse((14, 80, 32, 98), outline=copper, width=3)
    pen.line((23, 81, 23, 97), fill=copper)
    pen.line((15, 89, 31, 89), fill=copper)
    bolt(pen, 23, 89, 2, copper_l, ink)
    rng = random.Random(seed + 41)
    for _ in range(5):
        x = rng.randrange(12, 112)
        y = rng.randrange(28, 50)
        pen.line((x, y, x + rng.randrange(1, 3), y + rng.randrange(8, 20)),
                 fill=(116, 92, 68))
    scratches(pen, rng, (130, 142, 142), 4, (12, 12, 116, 108))
    chips(pen, rng, (48, 60, 64), 3, (12, 12, 116, 108))
    wall_frame(im, ink, slate, ink)
    return im


def wall_drowned_05(seed):
    sid = 'drowned_records'
    ink, chalk, bone, paper = C(sid, 'ink'), C(sid, 'chalk'), C(sid, 'bone'), C(sid, 'paper')
    silt, petrol, slate = C(sid, 'silt'), C(sid, 'petrol'), C(sid, 'slate')
    copper, copper_l = C(sid, 'copper'), C(sid, 'copper_light')
    im = material(128, 128, bone, seed, cell=64, amount=8, tilt=6)
    pen = ImageDraw.Draw(im)
    shadow(pen, (8, 16, 120, 112), ink, 3)
    recess(pen, (8, 16, 120, 112), petrol, ink, slate, 2)
    # closed roller shutter
    for y in range(20, 92, 7):
        shade = (86, 102, 108) if (y // 7) % 2 else (76, 92, 98)
        bevel(pen, (12, y, 116, y + 5), shade, (128, 142, 146), (39, 52, 58), 1)
        if y in (48, 76):
            pen.line((13, y + 4, 115, y + 4), fill=silt)
    bevel(pen, (12, 92, 116, 101), (92, 80, 64), (154, 132, 98), (58, 48, 40), 2)
    pen.rectangle((58, 94, 70, 99), fill=(64, 56, 46), outline=ink)
    # counter shelf
    shadow(pen, (6, 102, 122, 109), ink, 2)
    bevel(pen, (6, 101, 122, 107), copper, copper_l, (90, 52, 30), 2)
    # pull chain
    pen.line((112, 101, 112, 108), fill=(68, 70, 66), width=2)
    pen.ellipse((109, 107, 115, 113), outline=(92, 96, 90), width=1)
    # posted notice, blank bars only (no prose)
    shadow(pen, (28, 34, 72, 62), ink, 2)
    bevel(pen, (28, 33, 72, 61), paper, chalk, (126, 114, 92), 1)
    pen.line((32, 40, 62, 40), fill=(96, 84, 66))
    pen.line((32, 45, 56, 45), fill=(112, 100, 80))
    pen.line((32, 50, 60, 50), fill=(112, 100, 80))
    pen.polygon([(34, 58), (42, 54), (66, 55), (66, 61), (34, 61)], fill=(176, 164, 138),
                outline=(126, 114, 92))
    bolt(pen, 50, 37, 1, copper_l, ink)
    im = wash_poly(im, [(6, 105), (32, 102), (58, 106), (86, 103), (110, 106),
                        (122, 104), (122, 112), (6, 112)], silt, 45)
    pen = ImageDraw.Draw(im)
    rng = random.Random(seed + 51)
    scratches(pen, rng, (128, 138, 136), 5, (12, 20, 116, 100))
    chips(pen, rng, (122, 110, 88), 4, (10, 10, 118, 118))
    wall_frame(im, ink, chalk, ink)
    return im


def wall_drowned_06(seed):
    sid = 'drowned_records'
    ink, chalk, bone = C(sid, 'ink'), C(sid, 'chalk'), C(sid, 'bone')
    silt, petrol = C(sid, 'silt'), C(sid, 'petrol')
    copper, copper_l = C(sid, 'copper'), C(sid, 'copper_light')
    im = material(128, 128, bone, seed, cell=64, amount=7, tilt=5)
    pen = ImageDraw.Draw(im)
    shadow(pen, (4, 40, 124, 88), ink, 3)
    recess(pen, (4, 40, 124, 88), petrol, ink, (74, 90, 94), 2)
    pen.line((5, 42, 122, 42), fill=copper)
    pen.line((5, 43, 122, 43), fill=copper_l)
    pen.line((5, 85, 122, 85), fill=copper)
    pen.line((5, 84, 122, 84), fill=copper_l)
    # arrow
    pen.polygon([(14, 58), (34, 58), (34, 53), (44, 64), (34, 75), (34, 70),
                 (14, 70)], fill=chalk, outline=ink)
    # tide stair
    for k, (x, y) in enumerate(((54, 70), (60, 66), (66, 62), (72, 58))):
        pen.rectangle((x, y, x + 7, 78), fill=chalk, outline=ink)
        pen.line((x, y, x + 7, y), fill=(226, 218, 198))
    pen.polygon([(68, 47), (74, 55), (62, 55)], fill=copper_l, outline=ink)
    # sluice gate icon
    pen.ellipse((88, 52, 114, 78), outline=chalk, width=3)
    pen.rectangle((90, 63, 112, 67), fill=petrol)
    pen.line((90, 63, 112, 63), fill=chalk)
    pen.line((90, 67, 112, 67), fill=chalk)
    bolt(pen, 101, 65, 2, copper_l, ink)
    # blank plaques below
    for x in (16, 52, 88):
        bevel(pen, (x, 96, x + 24, 108), copper, copper_l, (92, 54, 32), 1)
        pen.line((x + 4, 100, x + 18, 100), fill=ink)
        pen.line((x + 4, 104, x + 13, 104), fill=ink)
    for x in (24, 64, 104):
        pen.line((x, 20, x, 32), fill=copper)
        pen.line((x + 1, 20, x + 1, 32), fill=copper_l)
    rng = random.Random(seed + 61)
    im = wash_poly(im, [(6, 88), (30, 86), (60, 89), (92, 86), (122, 88),
                        (122, 94), (6, 94)], silt, 34)
    pen = ImageDraw.Draw(im)
    scratches(pen, rng, (142, 132, 108), 4, (8, 8, 120, 120))
    chips(pen, rng, (138, 126, 102), 3, (8, 8, 120, 120))
    wall_frame(im, ink, chalk, ink)
    return im


def wall_drowned_07(seed):
    sid = 'drowned_records'
    ink, chalk, bone, paper = C(sid, 'ink'), C(sid, 'chalk'), C(sid, 'bone'), C(sid, 'paper')
    silt, petrol, slate = C(sid, 'silt'), C(sid, 'petrol'), C(sid, 'slate')
    copper, copper_l = C(sid, 'copper'), C(sid, 'copper_light')
    im = material(128, 128, bone, seed, cell=64, amount=9, tilt=6)
    pen = ImageDraw.Draw(im)
    shadow(pen, (6, 6, 122, 122), ink, 2)
    bevel(pen, (8, 8, 120, 120), (118, 108, 86), copper_l, (92, 58, 36), 3)
    bevel(pen, (11, 11, 117, 117), paper, chalk, (128, 116, 94), 1)
    # four rows of two drawers
    cells = []
    for row in range(4):
        for col in range(2):
            x0 = 14 + col * 50
            y0 = 14 + row * 26
            cells.append((x0, y0, x0 + 46, y0 + 23))
    for idx, (x0, y0, x1, y1) in enumerate(cells):
        ajar = idx == 4
        if ajar:
            y0 += 5
            y1 += 5
            pen.rectangle((x0, y0 - 7, x1, y0 - 1), fill=ink)
        shadow(pen, (x0, y0, x1, y1), ink, 1)
        bevel(pen, (x0, y0, x1, y1), slate, (126, 146, 150), (39, 52, 58), 2)
        bevel(pen, (x0 + 7, y0 + 3, x0 + 37, y0 + 11), paper, chalk, (128, 116, 94), 1)
        pen.line((x0 + 10, y0 + 6, x0 + 24, y0 + 6), fill=(92, 80, 62))
        pen.line((x0 + 10, y0 + 8, x0 + 20, y0 + 8), fill=(112, 100, 80))
        bevel(pen, (x0 + 11, y0 + 15, x0 + 33, y0 + 18), copper, copper_l, (91, 55, 32), 1)
        if ajar:
            pen.line((x1 - 6, y0 + 6, x1 - 2, y0 + 6), fill=chalk)
    # water damage across the lower two rows
    im = wash_poly(im, [(10, 84), (36, 81), (62, 86), (88, 82), (118, 85),
                        (118, 118), (10, 118)], petrol, 42)
    im = wash_poly(im, [(10, 84), (36, 81), (62, 86), (88, 82), (118, 85),
                        (118, 89), (10, 89)], silt, 80)
    pen = ImageDraw.Draw(im)
    for x, y in ((14, 14), (114, 14), (14, 114), (114, 114)):
        bolt(pen, x, y, 2, copper_l, ink)
    rng = random.Random(seed + 71)
    for _ in range(4):
        x, y = rng.randrange(16, 108), rng.randrange(14, 78)
        im = wash_ellipse(im, (x, y, x + rng.randrange(4, 10), y + rng.randrange(3, 7)),
                          silt, 45)
    pen = ImageDraw.Draw(im)
    scratches(pen, rng, (132, 144, 146), 5, (12, 12, 116, 116))
    chips(pen, rng, (96, 84, 66), 4, (12, 12, 116, 116))
    wall_frame(im, ink, chalk, ink)
    return im


def wall_drowned_08(seed):
    sid = 'drowned_records'
    ink, chalk, bone, paper = C(sid, 'ink'), C(sid, 'chalk'), C(sid, 'bone'), C(sid, 'paper')
    silt, petrol, slate = C(sid, 'silt'), C(sid, 'petrol'), C(sid, 'slate')
    copper, copper_l = C(sid, 'copper'), C(sid, 'copper_light')
    im = material(128, 128, paper, seed, cell=64, amount=9, tilt=5)
    pen = ImageDraw.Draw(im)
    shadow(pen, (8, 8, 120, 120), ink, 3)
    bevel(pen, (8, 8, 120, 120), petrol, slate, ink, 2)
    # circular tide register
    cx, cy, r = 64, 64, 48
    pen.ellipse((cx - r, cy - r, cx + r, cy + r), fill=bone, outline=ink, width=2)
    pen.ellipse((cx - r + 4, cy - r + 4, cx + r - 4, cy + r - 4), outline=copper, width=5)
    pen.ellipse((cx - r + 9, cy - r + 9, cx + r - 9, cy + r - 9), outline=(120, 108, 86))
    for rr in (38, 28, 18):
        pen.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=slate)
    for k in range(12):
        ang = math.radians(k * 30 + 15)
        x0, y0 = cx + math.cos(ang) * 15, cy + math.sin(ang) * 15
        x1, y1 = cx + math.cos(ang) * 43, cy + math.sin(ang) * 43
        pen.line((x0, y0, x1, y1), fill=slate, width=2)
    for k in range(24):
        ang = math.radians(k * 15)
        x0, y0 = cx + math.cos(ang) * 42, cy + math.sin(ang) * 42
        x1, y1 = cx + math.cos(ang) * 47, cy + math.sin(ang) * 47
        pen.line((x0, y0, x1, y1), fill=ink if k % 2 else copper_l)
    # two zero marks (deliberate impossible duplicate)
    for ang_deg in (90, 270):
        ang = math.radians(ang_deg)
        tx, ty = cx + math.cos(ang) * 33, cy + math.sin(ang) * 33
        pen.polygon([(tx, ty), (tx - 4, ty - 6), (tx + 4, ty - 6)], fill=copper)
    pen.ellipse((cx - 9, cy - 9, cx + 9, cy + 9), fill=copper, outline=ink)
    pen.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill=ink)
    pen.polygon([(cx, cy - 8), (cx - 4, cy - 30), (cx + 4, cy - 30)], fill=copper_l,
                outline=ink)
    for x, y in ((16, 16), (112, 16), (16, 112), (112, 112)):
        bolt(pen, x, y, 2, copper_l, ink)
    # pinned paper slip
    bevel(pen, (16, 98, 42, 114), bone, chalk, (126, 114, 92), 1)
    pen.line((20, 103, 37, 103), fill=(100, 86, 68))
    pen.line((20, 107, 33, 107), fill=(118, 104, 82))
    bolt(pen, 29, 100, 1, copper_l, ink)
    im = wash_poly(im, [(8, 106), (24, 102), (48, 108), (72, 104), (100, 108),
                        (120, 104), (120, 122), (8, 122)], silt, 40)
    pen = ImageDraw.Draw(im)
    rng = random.Random(seed + 81)
    scratches(pen, rng, (150, 140, 116), 4, (12, 12, 116, 116))
    wall_frame(im, ink, chalk, ink)
    return im


DROWNED_WALLS = [wall_drowned_01, wall_drowned_02, wall_drowned_03, wall_drowned_04,
                 wall_drowned_05, wall_drowned_06, wall_drowned_07, wall_drowned_08]


# -- Switchyard Chapel -------------------------------------------------------
def wall_switch_01(seed):
    sid = 'switchyard_chapel'
    ivory, porcelain = C(sid, 'ivory'), C(sid, 'porcelain')
    bone, rust, rust_l = C(sid, 'bone'), C(sid, 'rust'), C(sid, 'rust_light')
    iron, oxide = C(sid, 'iron'), C(sid, 'oxide')
    im = material(128, 128, ivory, seed, cell=64, amount=7, tilt=6)
    pen = ImageDraw.Draw(im)
    pen.rectangle((2, 2, 125, 125), fill=oxide)
    rng = random.Random(seed + 101)
    for row in range(4):
        y0 = 2 + row * 31
        y1 = y0 + 28
        start = -30 + (31 if row % 2 else 0)
        for col in range(3):
            x0 = start + col * 64
            x1 = x0 + 61
            if x1 < 2 or x0 > 125:
                continue
            x0, x1 = max(2, x0), min(125, x1)
            tone = rng.randrange(-6, 7)
            col_fill = tuple(max(0, min(255, v + tone)) for v in porcelain)
            bevel(pen, (x0, y0, x1, y1), col_fill, (250, 246, 232), bone, 2)
            pen.line((x0 + 4, y0 + 4, min(x1 - 4, x0 + 18), y0 + 4),
                     fill=(255, 252, 240))
            if (row + col) % 3 == 0:
                cx, cy = x0 + 8 + (col * 13) % 30, y1 - 4
                pen.polygon([(cx, cy), (cx + 5, cy - 3), (cx + 6, cy),
                             (cx + 2, cy + 2)], fill=oxide)
    for x, y in ((28, 30), (92, 61), (44, 92), (108, 123)):
        pen.line((x, y, x + 1, y + rng.randrange(7, 16)), fill=(112, 76, 54))
        pen.point((x + 1, y + 3), fill=rust_l)
    for _ in range(8):
        x, y = rng.randrange(10, 118), rng.randrange(10, 118)
        pen.point((x, y), fill=(238, 232, 212))
    scratches(pen, rng, (188, 178, 154), 4, (6, 6, 120, 120))
    wall_frame(im, iron, ivory, rust)
    return im


def wall_switch_02(seed):
    sid = 'switchyard_chapel'
    ivory, porcelain = C(sid, 'ivory'), C(sid, 'porcelain')
    bone, rust, rust_l = C(sid, 'bone'), C(sid, 'rust'), C(sid, 'rust_light')
    iron, charcoal, oxide = C(sid, 'iron'), C(sid, 'charcoal'), C(sid, 'oxide')
    amber, amber_l = C(sid, 'amber'), C(sid, 'amber_light')
    im = material(128, 128, iron, seed, cell=64, amount=7, tilt=5)
    pen = ImageDraw.Draw(im)
    shadow(pen, (6, 6, 121, 121), C(sid, 'cable'), 2)
    bevel(pen, (6, 6, 121, 121), rust, rust_l, oxide, 3)
    cells = [(10, 12, 60, 44), (66, 12, 116, 44),
             (10, 50, 60, 82), (66, 50, 116, 82),
             (10, 88, 60, 120), (66, 88, 116, 120)]
    for idx, (x0, y0, x1, y1) in enumerate(cells):
        shadow(pen, (x0, y0, x1, y1), C(sid, 'cable'), 1)
        recess(pen, (x0, y0, x1, y1), charcoal, C(sid, 'cable'), iron, 2)
        if idx in (0, 4):
            insulator_stack(pen, (x0 + x1) // 2, y0 + 4, y1 - 4, 22, 3,
                            ivory, porcelain, bone, oxide)
            pen.rectangle((x0 + 6, y1 - 5, x1 - 6, y1 - 3), fill=rust)
        elif idx == 1:
            pen.ellipse((x0 + 12, y0 + 8, x0 + 32, y0 + 28), outline=iron, width=3)
            pen.arc((x0 + 14, y0 + 10, x0 + 30, y0 + 26), 30, 320, fill=bone, width=2)
            pen.ellipse((x0 + 33, y0 + 12, x0 + 45, y0 + 24), fill=amber, outline=iron)
            pen.ellipse((x0 + 36, y0 + 15, x0 + 42, y0 + 21), fill=amber_l)
            pen.line((x0 + 8, y1 - 6, x1 - 8, y1 - 6), fill=oxide)
        elif idx == 2:
            for k in range(3):
                bx = x0 + 10 + k * 13
                bevel(pen, (bx, y0 + 8, bx + 9, y0 + 22), ivory, porcelain, bone, 1)
                pen.line((bx + 3, y0 + 11, bx + 6, y0 + 11), fill=oxide)
            for k in range(2):
                pen.ellipse((x0 + 13 + k * 18, y0 + 27, x0 + 18 + k * 18, y0 + 32),
                            fill=amber, outline=iron)
        elif idx == 3:
            cx, cy, r = (x0 + x1) // 2, (y0 + y1) // 2, 13
            pen.ellipse((cx - r, cy - r, cx + r, cy + r), fill=charcoal, outline=iron, width=2)
            for k in range(-2, 3):
                off = k * 4
                half = int(math.sqrt(max(0, r * r - off * off)))
                pen.line((cx - half, cy + off, cx + half, cy + off), fill=iron)
                pen.line((cx + off, cy - half, cx + off, cy + half), fill=iron)
            pen.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=amber, outline=iron)
        else:
            bevel(pen, (x0 + 8, y0 + 8, x0 + 32, y0 + 26), (92, 76, 56), (132, 112, 82),
                  (58, 46, 36), 1)
            pen.line((x0 + 12, y0 + 13, x0 + 26, y0 + 13), fill=charcoal)
            pen.line((x0 + 12, y0 + 18, x0 + 21, y0 + 18), fill=charcoal)
            pen.rectangle((x0 + 40, y0 + 9, x0 + 44, y0 + 19), fill=amber, outline=iron)
    for x in (9, 65, 120):
        for y in (55, 93):
            bolt(pen, x, y, 2, rust_l, oxide)
    rng = random.Random(seed + 102)
    for _ in range(5):
        x = rng.randrange(10, 116)
        y = rng.randrange(10, 40)
        pen.line((x, y, x + rng.randrange(0, 2), y + rng.randrange(8, 22)),
                 fill=(112, 76, 54))
    scratches(pen, rng, (166, 154, 130), 4, (8, 8, 120, 120))
    wall_frame(im, iron, rust_l, charcoal)
    return im


def wall_switch_03(seed):
    sid = 'switchyard_chapel'
    bone, rust, rust_l = C(sid, 'bone'), C(sid, 'rust'), C(sid, 'rust_light')
    iron, oxide = C(sid, 'iron'), C(sid, 'oxide')
    im = material(128, 128, rust, seed, cell=64, amount=12, tilt=6)
    for box, col, alpha in (((6, 6, 62, 62), rust_l, 38), ((66, 6, 121, 62), oxide, 40),
                            ((6, 66, 62, 121), oxide, 48), ((66, 66, 121, 121), rust_l, 22)):
        im = wash_rect(im, box, col, alpha)
    rng = random.Random(seed + 103)
    for _ in range(3):
        x, y = rng.randrange(12, 108), rng.randrange(12, 108)
        im = wash_ellipse(im, (x, y, x + rng.randrange(18, 40), y + rng.randrange(12, 28)),
                          oxide, 45)
    pen = ImageDraw.Draw(im)
    # plate seams and bevels
    pen.rectangle((63, 4, 66, 124), fill=(36, 32, 30))
    pen.rectangle((4, 63, 124, 66), fill=(36, 32, 30))
    for box in ((6, 6, 62, 62), (66, 6, 121, 62), (6, 66, 62, 121), (66, 66, 121, 121)):
        x0, y0, x1, y1 = box
        pen.line((x0, y0, x1, y0), fill=rust_l)
        pen.line((x0, y0, x0, y1), fill=rust_l)
        pen.line((x0, y1, x1, y1), fill=oxide)
        pen.line((x1, y0, x1, y1), fill=oxide)
    for y in range(12, 122, 16):
        bolt(pen, 64, y, 2, rust_l, (34, 28, 26))
    for x in range(12, 122, 16):
        bolt(pen, x, 64, 2, rust_l, (34, 28, 26))
    # blank embossed maker plate, no logo or text
    bevel(pen, (14, 84, 52, 106), (122, 58, 39), rust_l, oxide, 2)
    bevel(pen, (20, 89, 46, 101), (134, 68, 45), rust_l, oxide, 1)
    for x, y in ((17, 87), (49, 87), (17, 103), (49, 103)):
        bolt(pen, x, y, 1, rust_l, oxide)
    for _ in range(7):
        x = rng.randrange(8, 120)
        y = rng.randrange(8, 60)
        pen.line((x, y, x + rng.randrange(0, 2), y + rng.randrange(6, 20)),
                 fill=(105, 66, 46))
    scratches(pen, rng, (176, 112, 78), 7, (8, 8, 120, 120))
    chips(pen, rng, (54, 34, 28), 4, (8, 8, 120, 120), 4)
    wall_frame(im, oxide, rust_l, (36, 30, 28))
    return im


def wall_switch_04(seed):
    sid = 'switchyard_chapel'
    ivory, porcelain = C(sid, 'ivory'), C(sid, 'porcelain')
    bone, rust, rust_l = C(sid, 'bone'), C(sid, 'rust'), C(sid, 'rust_light')
    iron, charcoal, oxide = C(sid, 'iron'), C(sid, 'charcoal'), C(sid, 'oxide')
    amber, amber_l = C(sid, 'amber'), C(sid, 'amber_light')
    im = material(128, 128, charcoal, seed, cell=32, amount=6, tilt=4)
    pen = ImageDraw.Draw(im)
    bevel(pen, (4, 4, 124, 124), iron, (78, 74, 68), (26, 25, 24), 2)
    for y0 in (20, 98):
        bevel(pen, (6, y0, 121, y0 + 10), rust, rust_l, oxide, 2)
        for x in range(14, 120, 24):
            bolt(pen, x, y0 + 5, 2, rust_l, oxide)
    for cx in (26, 64, 102):
        pen.rectangle((cx - 3, 30, cx + 3, 96), fill=(30, 28, 26))
        insulator_stack(pen, cx, 32, 96, 26, 4, ivory, porcelain, bone, oxide)
        pen.polygon([(cx - 7, 32), (cx + 7, 32), (cx + 4, 26), (cx - 4, 26)],
                    fill=rust, outline=oxide)
        pen.polygon([(cx - 7, 96), (cx + 7, 96), (cx + 4, 102), (cx - 4, 102)],
                    fill=rust, outline=oxide)
        bolt(pen, cx, 28, 2, rust_l, oxide)
        bolt(pen, cx, 100, 2, rust_l, oxide)
    for cx in (26, 64, 102):
        pen.rectangle((cx - 3, 12, cx + 3, 20), fill=amber, outline=oxide)
        pen.point((cx, 14), fill=amber_l)
    rng = random.Random(seed + 104)
    for _ in range(6):
        x = rng.randrange(10, 116)
        y = rng.randrange(24, 50)
        pen.line((x, y, x + rng.randrange(0, 2), y + rng.randrange(5, 18)),
                 fill=(108, 70, 50))
    for _ in range(5):
        x, y = rng.randrange(12, 116), rng.randrange(30, 100)
        pen.point((x, y), fill=(228, 220, 200))
    scratches(pen, rng, (112, 100, 84), 4, (8, 8, 120, 120))
    wall_frame(im, (24, 23, 22), iron, (22, 21, 20))
    return im


def wall_switch_05(seed):
    sid = 'switchyard_chapel'
    ivory, porcelain = C(sid, 'ivory'), C(sid, 'porcelain')
    bone, rust, rust_l = C(sid, 'bone'), C(sid, 'rust'), C(sid, 'rust_light')
    iron, charcoal, oxide = C(sid, 'iron'), C(sid, 'charcoal'), C(sid, 'oxide')
    amber, amber_l = C(sid, 'amber'), C(sid, 'amber_light')
    im = material(128, 128, iron, seed, cell=64, amount=8, tilt=5)
    pen = ImageDraw.Draw(im)
    shadow(pen, (8, 10, 120, 116), charcoal, 3)
    bevel(pen, (8, 10, 120, 116), rust, rust_l, oxide, 3)
    recess(pen, (12, 14, 116, 100), charcoal, (24, 22, 21), iron, 2)
    panes = [(14, 16, 62, 56), (66, 16, 114, 56), (14, 60, 62, 98), (66, 60, 114, 98)]
    for idx, (x0, y0, x1, y1) in enumerate(panes):
        tone = (168, 112, 42) if idx != 3 else (72, 62, 50)
        pen.rectangle((x0, y0, x1, y1), fill=tone, outline=(40, 34, 30))
        if idx != 3:
            for y in range(y0 + 6, y1, 12):
                pen.line((x0 + 2, y, x1 - 2, y), fill=(134, 88, 38))
            pen.line((x0 + 4, y0 + 3, x0 + 24, y1 - 3), fill=(196, 146, 70))
        else:
            pen.line((x0 + 3, y0 + 4, x1 - 4, y1 - 3), fill=(102, 90, 72))
            pen.line((x1 - 4, y0 + 4, x0 + 3, y1 - 3), fill=(54, 48, 42))
    # mullions
    bevel(pen, (62, 14, 66, 100), iron, (94, 88, 80), (26, 24, 22), 1)
    bevel(pen, (12, 56, 116, 60), iron, (94, 88, 80), (26, 24, 22), 1)
    # heavy grille
    for x0 in (38, 64, 90):
        bevel(pen, (x0, 14, x0 + 5, 100), (52, 48, 44), (104, 96, 88), (24, 22, 21), 1)
    for y0 in (32, 74):
        bevel(pen, (12, y0, 116, y0 + 4), (52, 48, 44), (104, 96, 88), (24, 22, 21), 1)
    for x in (40, 66, 92):
        for y in (34, 76):
            bolt(pen, x, y, 2, (86, 78, 68), (22, 20, 19))
    # latch plate
    bevel(pen, (56, 92, 72, 104), (58, 54, 48), (116, 106, 94), (24, 22, 21), 1)
    pen.arc((60, 95, 68, 103), 200, 340, fill=(28, 26, 24), width=2)
    pen.line((61, 99, 67, 99), fill=(28, 26, 24))
    rng = random.Random(seed + 105)
    for _ in range(6):
        x = rng.randrange(12, 116)
        pen.line((x, 14, x + rng.randrange(0, 2), 14 + rng.randrange(5, 18)),
                 fill=(112, 72, 50))
    for _ in range(4):
        x, y = rng.randrange(16, 112), rng.randrange(18, 96)
        pen.point((x, y), fill=amber_l)
    scratches(pen, rng, (104, 94, 80), 4, (14, 16, 114, 98))
    wall_frame(im, (22, 20, 19), rust_l, iron)
    return im


def wall_switch_06(seed):
    sid = 'switchyard_chapel'
    ivory, porcelain = C(sid, 'ivory'), C(sid, 'porcelain')
    bone, rust, rust_l = C(sid, 'bone'), C(sid, 'rust'), C(sid, 'rust_light')
    iron, charcoal, oxide = C(sid, 'iron'), C(sid, 'charcoal'), C(sid, 'oxide')
    amber, amber_l = C(sid, 'amber'), C(sid, 'amber_light')
    im = material(128, 128, porcelain, seed, cell=32, amount=6, tilt=4)
    pen = ImageDraw.Draw(im)
    # chipped enamel under-layer
    pen.rectangle((4, 30, 123, 98), fill=iron)
    bevel(pen, (5, 32, 122, 96), rust, rust_l, oxide, 3)
    # lightning / distribution glyph
    pen.polygon([(16, 40), (32, 40), (26, 56), (40, 56), (22, 86),
                 (28, 64), (14, 64)], fill=amber_l, outline=charcoal)
    # ceramic pips and bar
    for k in range(3):
        y = 44 + k * 10
        pen.ellipse((54, y, 74, y + 7), fill=ivory, outline=oxide)
        pen.line((57, y + 2, 71, y + 2), fill=porcelain)
    pen.rectangle((52, 78, 76, 82), fill=ivory, outline=oxide)
    # looping route glyph
    pen.arc((86, 46, 116, 76), 35, 325, fill=ivory, width=4)
    pen.polygon([(112, 54), (118, 64), (108, 62)], fill=ivory, outline=oxide)
    pen.rectangle((95, 60, 107, 64), fill=ivory, outline=oxide)
    for x, y in ((18, 28), (64, 28), (110, 28)):
        bolt(pen, x, y, 1, (110, 88, 58), oxide)
    # indicator strip below
    bevel(pen, (6, 100, 121, 108), iron, (76, 68, 60), (22, 20, 19), 1)
    for k, x in enumerate((14, 38, 62, 86, 110)):
        pen.rectangle((x, 102, x + 6, 106), fill=amber if k % 2 else (86, 62, 34),
                      outline=(30, 26, 24))
    bevel(pen, (34, 112, 92, 120), (98, 78, 50), (144, 114, 70), (58, 44, 30), 1)
    for x in (42, 54, 66):
        pen.line((x, 115, x + 14, 115), fill=charcoal)
    # chipped corners
    for x, y, dx, dy in ((5, 32, 8, 6), (122, 32, -8, 6), (5, 96, 8, -6), (122, 96, -8, -6)):
        pen.polygon([(x, y), (x + dx, y), (x, y + dy)], fill=charcoal)
    rng = random.Random(seed + 106)
    for _ in range(5):
        x = rng.randrange(10, 118)
        pen.line((x, 34, x + rng.randrange(0, 2), 34 + rng.randrange(4, 14)),
                 fill=(112, 72, 50))
    scratches(pen, rng, (238, 232, 214), 4, (8, 8, 120, 120))
    wall_frame(im, iron, porcelain, rust)
    return im


def wall_switch_07(seed):
    sid = 'switchyard_chapel'
    ivory, porcelain = C(sid, 'ivory'), C(sid, 'porcelain')
    bone, rust, rust_l = C(sid, 'bone'), C(sid, 'rust'), C(sid, 'rust_light')
    iron, charcoal, oxide = C(sid, 'iron'), C(sid, 'charcoal'), C(sid, 'oxide')
    amber, amber_l = C(sid, 'amber'), C(sid, 'amber_light')
    cable = C(sid, 'cable')
    im = material(128, 128, rust, seed, cell=64, amount=10, tilt=5)
    im = wash_ellipse(im, (10, 18, 58, 62), oxide, 45)
    im = wash_ellipse(im, (74, 58, 120, 104), oxide, 35)
    pen = ImageDraw.Draw(im)
    # support
    bevel(pen, (58, 82, 70, 122), iron, (86, 80, 72), (26, 24, 22), 2)
    bevel(pen, (48, 116, 80, 122), rust, rust_l, oxide, 1)
    cx, cy = 64, 82
    n = 9
    for k in range(n):
        ang = math.radians(200 + k * (140 / (n - 1)))
        dx, dy = math.cos(ang), math.sin(ang)
        px, py = -dy, dx
        r0, r1 = 10, 46
        w0, w1 = 3.4, 5.6
        pts = [(cx + dx * r0 + px * w0, cy + dy * r0 + py * w0),
               (cx + dx * r1 + px * w1, cy + dy * r1 + py * w1),
               (cx + dx * r1 - px * w1, cy + dy * r1 - py * w1),
               (cx + dx * r0 - px * w0, cy + dy * r0 - py * w0)]
        col = porcelain if k % 2 == 0 else ivory
        pen.polygon(pts, fill=col, outline=oxide)
        for t in (0.45, 0.75):
            rx, ry = cx + dx * (r0 + (r1 - r0) * t), cy + dy * (r0 + (r1 - r0) * t)
            ww = w0 + (w1 - w0) * t
            pen.line((rx + px * ww, ry + py * ww, rx - px * ww, ry - py * ww),
                     fill=bone)
            pen.line((rx + px * ww, ry + py * ww - 1, rx - px * ww, ry - py * ww - 1),
                     fill=(252, 248, 236))
        pen.line((cx + dx * r0 + px * w0, cy + dy * r0 + py * w0,
                  cx + dx * r1 + px * w1, cy + dy * r1 + py * w1), fill=(248, 244, 230))
    pen.ellipse((cx - 15, cy - 15, cx + 15, cy + 15), fill=charcoal, outline=iron, width=2)
    pen.ellipse((cx - 12, cy - 12, cx + 12, cy + 12), outline=rust, width=3)
    pen.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill=amber, outline=oxide)
    for k in range(3):
        ang = math.radians(30 + k * 120)
        bolt(pen, round(cx + math.cos(ang) * 9), round(cy + math.sin(ang) * 9), 1,
             rust_l, oxide)
    # two cable braids; one ends in a blank porcelain cap (impossible detail)
    for side, cap in ((-1, True), (1, False)):
        path = cable_path([(cx + side * 11, cy + 6), (cx + side * 46, 120)], 10, 36)
        braid(pen, path, cable, rust, bone, 5)
        if cap:
            insulator_stack(pen, cx + side * 46, 106, 121, 18, 2, ivory, porcelain, bone, oxide)
        else:
            pen.rectangle((cx + side * 46 - 5, 114, cx + side * 46 + 5, 121),
                          fill=iron, outline=oxide)
    rng = random.Random(seed + 107)
    for _ in range(5):
        x = rng.randrange(10, 118)
        pen.line((x, rng.randrange(8, 40), x + rng.randrange(0, 2),
                  rng.randrange(40, 120)), fill=(116, 74, 52))
    scratches(pen, rng, (176, 104, 72), 5, (8, 8, 120, 120))
    chips(pen, rng, (60, 36, 28), 4, (8, 8, 120, 120))
    wall_frame(im, iron, rust_l, charcoal)
    return im


def wall_switch_08(seed):
    sid = 'switchyard_chapel'
    ivory, porcelain = C(sid, 'ivory'), C(sid, 'porcelain')
    bone, rust, rust_l = C(sid, 'bone'), C(sid, 'rust'), C(sid, 'rust_light')
    iron, charcoal, oxide = C(sid, 'iron'), C(sid, 'charcoal'), C(sid, 'oxide')
    amber, amber_l = C(sid, 'amber'), C(sid, 'amber_light')
    cable = C(sid, 'cable')
    im = material(128, 128, charcoal, seed, cell=64, amount=6, tilt=4)
    im = wash_rect(im, (4, 40, 124, 44), iron, 35)
    im = wash_rect(im, (4, 84, 124, 88), iron, 30)
    pen = ImageDraw.Draw(im)
    # relay niches behind the braids
    for x0 in (16, 82):
        recess(pen, (x0, 52, x0 + 30, 82), (28, 27, 26), cable, iron, 2)
        for k in range(3):
            pen.rectangle((x0 + 6 + k * 7, 58, x0 + 9 + k * 7, 66),
                          fill=amber if k != 1 else (96, 68, 36), outline=oxide)
        insulator_stack(pen, x0 + 15, 68, 80, 12, 2, ivory, porcelain, bone, oxide)
    for y in (42, 86):
        for x in range(12, 120, 20):
            bolt(pen, x, y, 2, (86, 78, 68), (22, 20, 19))
    # five sagging cable braids
    sag = (6, 10, 7, 12, 5)
    for idx, y in enumerate((26, 48, 66, 88, 110)):
        path = cable_path([(8, y), (120, y)], sag[idx], 40)
        braid(pen, path, cable, rust, bone, 5)
        thin = cable_path([(8, y - 3), (120, y - 3)], sag[idx] + 3, 40)
        pen.line(thin, fill=(44, 42, 40), width=2, joint='curve')
        pen.line([(x, yy - 1) for x, yy in thin], fill=rust_l, width=1, joint='curve')
        for x in (8, 120):
            bevel(pen, (x - 4, y - 7, x + 4, y + 7), iron, (86, 80, 72), (24, 22, 21), 1)
            bolt(pen, x, y, 1, rust_l, oxide)
    # porcelain clamp on the middle braid
    insulator_stack(pen, 64, 58, 74, 16, 2, ivory, porcelain, bone, oxide)
    rng = random.Random(seed + 108)
    for _ in range(6):
        x = rng.randrange(10, 116)
        pen.line((x, rng.randrange(8, 30), x + rng.randrange(0, 2),
                  rng.randrange(30, 50)), fill=(100, 66, 48))
    scratches(pen, rng, (112, 96, 78), 4, (8, 8, 120, 120))
    wall_frame(im, iron, (72, 68, 60), (20, 19, 18))
    return im


SWITCHYARD_WALLS = [wall_switch_01, wall_switch_02, wall_switch_03, wall_switch_04,
                    wall_switch_05, wall_switch_06, wall_switch_07, wall_switch_08]


# -- After Hours Pavilion ----------------------------------------------------
def wall_pav_01(seed):
    sid = 'after_hours_pavilion'
    plum, plum_d, plum_l = C(sid, 'plum'), C(sid, 'plum_dark'), C(sid, 'plum_light')
    slate, terra, terra_d = C(sid, 'slate'), C(sid, 'terrazzo'), C(sid, 'terrazzo_dark')
    brass, brass_l = C(sid, 'brass'), C(sid, 'brass_light')
    cream, ink, dust = C(sid, 'cream'), C(sid, 'ink'), C(sid, 'dust')
    im = material(128, 128, plum, seed, cell=64, amount=11, tilt=6)
    im = wash_rect(im, (8, 10, 120, 118), plum_l, 45)
    im = wash_rect(im, (10, 12, 72, 70), (168, 148, 166), 12)
    pen = ImageDraw.Draw(im)
    # a thin offset shadow only: an opaque shadow rectangle would hide the panel wash
    pen.rectangle((10, 118, 122, 120), fill=plum_d)
    pen.rectangle((120, 12, 122, 120), fill=plum_d)
    pen.line((8, 10, 120, 10), fill=plum_l)
    pen.line((8, 10, 8, 118), fill=plum_l)
    pen.line((8, 118, 120, 118), fill=ink)
    pen.line((120, 10, 120, 118), fill=ink)
    # ghost of a removed poster, blank bars only
    im = wash_rect(im, (20, 26, 76, 54), cream, 28)
    im = wash_poly(im, [(20, 50), (28, 54), (36, 50), (44, 55), (54, 51),
                        (62, 55), (70, 50), (76, 54), (76, 26), (20, 26)], cream, 18)
    pen = ImageDraw.Draw(im)
    pen.line((22, 34, 52, 34), fill=(126, 104, 120))
    pen.line((22, 39, 45, 39), fill=(126, 104, 120))
    pen.line((22, 44, 50, 44), fill=(126, 104, 120))
    bolt(pen, 48, 27, 1, brass_l, ink)
    # brass reveal and vertical seam
    shadow(pen, (8, 86, 120, 90), ink, 1)
    pen.line((8, 86, 120, 86), fill=brass)
    pen.line((8, 87, 120, 87), fill=brass_l)
    pen.line((64, 12, 64, 86), fill=plum_d)
    pen.line((65, 12, 65, 86), fill=plum_l)
    for x in (10, 118):
        bolt(pen, x, 88, 2, brass_l, ink)
    im = wash_rect(im, (10, 104, 118, 118), dust, 30)
    pen = ImageDraw.Draw(im)
    rng = random.Random(seed + 201)
    for _ in range(5):
        x, y = rng.randrange(12, 116), rng.randrange(14, 100)
        pen.line((x, y, x + rng.randrange(3, 9), y + rng.choice((-1, 0, 1))),
                 fill=(134, 112, 128))
    chips(pen, rng, terra, 3, (8, 10, 120, 118))
    chips(pen, rng, terra_d, 3, (8, 10, 120, 118))
    wall_frame(im, ink, plum_l, plum_d)
    return im


def wall_pav_02(seed):
    sid = 'after_hours_pavilion'
    plum, plum_d, plum_l = C(sid, 'plum'), C(sid, 'plum_dark'), C(sid, 'plum_light')
    slate, terra = C(sid, 'slate'), C(sid, 'terrazzo')
    brass, brass_l = C(sid, 'brass'), C(sid, 'brass_light')
    cream, ink, dust = C(sid, 'cream'), C(sid, 'ink'), C(sid, 'dust')
    im = material(128, 128, plum_d, seed, cell=32, amount=7, tilt=5)
    pen = ImageDraw.Draw(im)
    for i in range(8):
        x = 8 + i * 14
        x1 = x + 13
        # folded fabric: two faces and a central crease
        pen.polygon([(x, 12), (x + 6, 18), (x + 6, 110), (x, 116)], fill=plum_l,
                    outline=ink)
        pen.polygon([(x + 6, 18), (x1, 12), (x1, 116), (x + 6, 110)], fill=slate,
                    outline=ink)
        pen.line((x + 6, 18, x + 6, 110), fill=(158, 136, 154))
        pen.line((x, 30, x + 6, 36), fill=plum_d)
        pen.line((x + 7, 36, x1 - 1, 30), fill=plum_d)
        for y in (48, 82):
            pen.line((x + 1, y, x + 5, y + 2), fill=plum_d)
            pen.line((x + 7, y + 2, x1 - 1, y), fill=plum_d)
    shadow(pen, (4, 6, 124, 12), ink, 2)
    bevel(pen, (4, 6, 124, 12), brass, brass_l, (76, 56, 32), 1)
    bevel(pen, (4, 116, 124, 122), brass, brass_l, (76, 56, 32), 1)
    for x in (12, 64, 116):
        bolt(pen, x, 9, 1, brass_l, ink)
        bolt(pen, x, 119, 1, brass_l, ink)
    im = wash_poly(im, [(8, 12), (18, 16), (30, 12), (42, 16), (54, 12), (66, 16),
                        (78, 12), (90, 16), (102, 12), (114, 16), (122, 12),
                        (122, 20), (8, 20)], dust, 22)
    pen = ImageDraw.Draw(im)
    rng = random.Random(seed + 202)
    for _ in range(6):
        x, y = rng.randrange(10, 114), rng.randrange(20, 112)
        pen.line((x, y, x + rng.randrange(2, 6), y + rng.choice((-1, 0, 1))),
                 fill=(112, 92, 110))
    chips(pen, rng, terra, 2, (8, 18, 120, 112))
    wall_frame(im, ink, plum_l, ink)
    return im


def wall_pav_03(seed):
    sid = 'after_hours_pavilion'
    plum, plum_d, plum_l = C(sid, 'plum'), C(sid, 'plum_dark'), C(sid, 'plum_light')
    slate, terra, terra_d = C(sid, 'slate'), C(sid, 'terrazzo'), C(sid, 'terrazzo_dark')
    brass, brass_l = C(sid, 'brass'), C(sid, 'brass_light')
    cream, ink, dust = C(sid, 'cream'), C(sid, 'ink'), C(sid, 'dust')
    im = material(128, 128, slate, seed, cell=64, amount=9, tilt=6)
    pen = ImageDraw.Draw(im)
    # slate piers top and bottom
    for y0, y1 in ((6, 48), (80, 121)):
        bevel(pen, (6, y0, 121, y1), (98, 108, 118), (146, 156, 164), (64, 76, 86), 2)
        pen.line((64, y0 + 2, 64, y1 - 2), fill=brass)
        pen.line((65, y0 + 2, 65, y1 - 2), fill=brass_l)
        for x in (10, 118):
            bolt(pen, x, y0 + 6, 1, brass_l, ink)
    # pale terrazzo inlay band
    bevel(pen, (6, 50, 121, 78), terra, cream, terra_d, 2)
    rng = random.Random(seed + 203)
    for _ in range(34):
        x, y = rng.randrange(10, 118), rng.randrange(54, 75)
        s = rng.randrange(2, 6)
        col = rng.choice((terra_d, plum, slate, brass, terra_d))
        kind = rng.randrange(3)
        if kind == 0:
            pen.polygon([(x, y), (x + s, y), (x, y + s)], fill=col)
        elif kind == 1:
            pen.rectangle((x, y, x + s, y + s), fill=col)
        else:
            pen.polygon([(x, y), (x + s, y - s // 2), (x + s, y + s // 2)], fill=col)
    bevel(pen, (52, 58, 76, 70), brass, brass_l, (86, 64, 34), 1)
    pen.line((57, 62, 71, 62), fill=(86, 64, 34))
    pen.line((57, 66, 66, 66), fill=(86, 64, 34))
    # chipped slate revealing terrazzo beneath
    for x, y, dx, dy in ((10, 46, 9, -5), (116, 44, -8, -4), (12, 82, 7, 6)):
        pen.polygon([(x, y), (x + dx, y), (x, y + dy)], fill=terra, outline=ink)
    im = wash_rect(im, (6, 112, 121, 121), dust, 28)
    pen = ImageDraw.Draw(im)
    scratches(pen, rng, (72, 84, 94), 5, (8, 8, 120, 120))
    chips(pen, rng, plum_d, 3, (8, 8, 120, 120))
    wall_frame(im, ink, terra, slate)
    return im


def wall_pav_04(seed):
    sid = 'after_hours_pavilion'
    plum, plum_d, plum_l = C(sid, 'plum'), C(sid, 'plum_dark'), C(sid, 'plum_light')
    slate, terra = C(sid, 'slate'), C(sid, 'terrazzo')
    brass, brass_l = C(sid, 'brass'), C(sid, 'brass_light')
    cream, ink, dust = C(sid, 'cream'), C(sid, 'ink'), C(sid, 'dust')
    im = material(128, 128, slate, seed, cell=64, amount=8, tilt=5)
    pen = ImageDraw.Draw(im)
    shadow(pen, (10, 20, 118, 108), ink, 3)
    pen.rounded_rectangle((10, 20, 118, 108), radius=6, fill=brass, outline=plum_d, width=2)
    pen.line((12, 22, 116, 22), fill=brass_l)
    pen.line((12, 22, 12, 106), fill=brass_l)
    pen.line((12, 106, 116, 106), fill=(80, 58, 32))
    pen.line((116, 22, 116, 106), fill=(80, 58, 32))
    # ticket slot and protruding blank ticket
    recess(pen, (24, 32, 78, 42), (44, 34, 46), ink, brass, 2)
    bevel(pen, (30, 38, 46, 44), cream, (255, 250, 234), terra, 1)
    pen.line((32, 41, 43, 41), fill=(150, 132, 100))
    # call buttons
    for idx, (x, y) in enumerate(((26, 66), (42, 66), (58, 66))):
        pen.ellipse((x - 6, y - 6, x + 6, y + 6), fill=brass, outline=plum_d)
        pen.ellipse((x - 4, y - 4, x + 4, y + 4),
                    fill=cream if idx == 2 else plum_d, outline=(74, 52, 30))
        if idx == 2:
            pen.ellipse((x - 2, y - 2, x + 2, y + 2), fill=brass_l)
    # vent slots
    for x in (82, 90, 98):
        recess(pen, (x, 28, x + 5, 58), (46, 36, 46), ink, brass, 1)
        pen.line((x + 1, 31, x + 1, 55), fill=plum)
    # bell dome
    pen.pieslice((87, 68, 109, 90), 180, 360, fill=brass_l, outline=plum_d)
    pen.rectangle((88, 79, 108, 84), fill=brass, outline=plum_d)
    pen.line((90, 82, 106, 82), fill=ink)
    pen.ellipse((96, 83, 100, 87), fill=plum_d, outline=ink)
    bolt(pen, 98, 70, 2, brass_l, ink)
    # blank label plate
    recess(pen, (24, 84, 66, 96), (48, 38, 48), ink, brass, 1)
    pen.line((28, 88, 54, 88), fill=brass_l)
    pen.line((28, 92, 44, 92), fill=brass_l)
    for x, y in ((14, 24), (114, 24), (14, 104), (114, 104)):
        bolt(pen, x, y, 2, brass_l, ink)
    im = wash_ellipse(im, (16, 46, 40, 58), plum_d, 28)
    im = wash_ellipse(im, (60, 70, 84, 88), plum_d, 24)
    pen = ImageDraw.Draw(im)
    rng = random.Random(seed + 204)
    scratches(pen, rng, (222, 190, 128), 6, (14, 24, 114, 104))
    chips(pen, rng, (110, 86, 52), 3, (14, 24, 114, 104))
    im = wash_rect(im, (12, 100, 116, 107), dust, 18)
    pen = ImageDraw.Draw(im)
    wall_frame(im, ink, brass_l, plum_d)
    return im


def wall_pav_05(seed):
    sid = 'after_hours_pavilion'
    plum, plum_d, plum_l = C(sid, 'plum'), C(sid, 'plum_dark'), C(sid, 'plum_light')
    slate, terra, terra_d = C(sid, 'slate'), C(sid, 'terrazzo'), C(sid, 'terrazzo_dark')
    brass, brass_l = C(sid, 'brass'), C(sid, 'brass_light')
    cream, ink, dust = C(sid, 'cream'), C(sid, 'ink'), C(sid, 'dust')
    im = material(128, 128, plum, seed, cell=64, amount=8, tilt=5)
    pen = ImageDraw.Draw(im)
    shadow(pen, (8, 14, 120, 114), ink, 3)
    recess(pen, (8, 14, 120, 114), (56, 43, 54), ink, plum_l, 2)
    # rolled shutter barrel
    bevel(pen, (10, 16, 118, 30), (76, 60, 72), plum_l, ink, 2)
    for y in (20, 25):
        pen.line((12, y, 116, y), fill=(104, 82, 98))
    # scissor gate: X cells, all inside the opening
    for row in range(3):
        for col in range(5):
            x0 = 14 + col * 20
            y0 = 30 + row * 20
            pen.line((x0, y0, x0 + 20, y0 + 20), fill=(148, 132, 104), width=2)
            pen.line((x0, y0 + 20, x0 + 20, y0), fill=(148, 132, 104), width=2)
            bolt(pen, x0, y0, 1, brass_l, ink)
    for x in (14, 114):
        bevel(pen, (x - 4, 30, x + 4, 92), (92, 78, 58), brass_l, (58, 44, 30), 1)
    bevel(pen, (60, 30, 68, 92), (92, 78, 58), brass_l, (58, 44, 30), 1)
    pen.rectangle((58, 56, 70, 62), fill=brass, outline=ink)
    pen.line((60, 58, 68, 58), fill=brass_l)
    # counter lip
    shadow(pen, (8, 92, 120, 100), ink, 2)
    bevel(pen, (8, 92, 120, 99), brass, brass_l, (82, 58, 32), 2)
    # small contradictory plaque above the gate
    bevel(pen, (34, 4, 94, 16), cream, (255, 250, 236), terra, 1)
    pen.polygon([(40, 10), (44, 6), (44, 8), (52, 8), (52, 12), (44, 12),
                 (44, 14)], fill=plum_d)
    pen.polygon([(88, 10), (84, 6), (84, 8), (76, 8), (76, 12), (84, 12),
                 (84, 14)], fill=plum_d)
    # fallen paper scrap
    pen.polygon([(30, 108), (44, 104), (48, 111), (34, 114)], fill=cream,
                outline=terra_d)
    im = wash_rect(im, (10, 100, 118, 112), dust, 24)
    pen = ImageDraw.Draw(im)
    rng = random.Random(seed + 205)
    for _ in range(5):
        x, y = rng.randrange(16, 112), rng.randrange(32, 92)
        pen.line((x, y, x + rng.randrange(3, 8), y + rng.choice((-1, 0, 1))),
                 fill=(116, 94, 112))
    scratches(pen, rng, (122, 100, 76), 4, (12, 18, 116, 110))
    wall_frame(im, ink, brass_l, plum_d)
    return im


def wall_pav_06(seed):
    sid = 'after_hours_pavilion'
    plum, plum_d, plum_l = C(sid, 'plum'), C(sid, 'plum_dark'), C(sid, 'plum_light')
    slate, terra, terra_d = C(sid, 'slate'), C(sid, 'terrazzo'), C(sid, 'terrazzo_dark')
    brass, brass_l = C(sid, 'brass'), C(sid, 'brass_light')
    cream, ink, dust = C(sid, 'cream'), C(sid, 'ink'), C(sid, 'dust')
    im = material(128, 128, terra, seed, cell=64, amount=6, tilt=4)
    rng = random.Random(seed + 206)
    im_draw = ImageDraw.Draw(im)
    for _ in range(38):
        x, y = rng.randrange(6, 122), rng.randrange(6, 122)
        s = rng.randrange(1, 4)
        col = rng.choice((terra_d, plum, slate, dust))
        if rng.random() < 0.5:
            im_draw.rectangle((x, y, x + s, y + s), fill=col)
        else:
            im_draw.polygon([(x, y), (x + s + 1, y), (x, y + s + 1)], fill=col)
    pen = ImageDraw.Draw(im)
    shadow(pen, (6, 38, 121, 94), ink, 2)
    bevel(pen, (6, 38, 121, 94), plum, plum_l, plum_d, 2)
    pen.line((6, 40, 121, 40), fill=brass_l)
    pen.line((6, 92, 121, 92), fill=brass)
    # split arrow
    pen.rectangle((14, 62, 42, 67), fill=cream)
    pen.polygon([(14, 64), (22, 57), (22, 72)], fill=cream, outline=plum_d)
    pen.polygon([(42, 64), (34, 57), (34, 72)], fill=cream, outline=plum_d)
    pen.rectangle((25, 52, 30, 63), fill=cream)
    pen.polygon([(27, 46), (21, 53), (33, 53)], fill=cream, outline=plum_d)
    # stair and contradictory arrows
    for k, (x, y) in enumerate(((52, 70), (58, 64), (64, 58), (70, 52))):
        pen.rectangle((x, y, x + 7, 80), fill=cream, outline=plum_d)
    pen.rectangle((55, 44, 58, 52), fill=cream)
    pen.polygon([(56, 42), (52, 48), (60, 48)], fill=cream, outline=plum_d)
    pen.rectangle((73, 42, 76, 50), fill=cream)
    pen.polygon([(74, 54), (70, 48), (78, 48)], fill=cream, outline=plum_d)
    # loop that points into itself
    pen.arc((88, 50, 114, 76), 30, 330, fill=cream, width=4)
    pen.polygon([(110, 53), (116, 62), (106, 61)], fill=cream, outline=plum_d)
    pen.rectangle((94, 61, 108, 65), fill=cream, outline=plum_d)
    # plaques
    for x in (14, 40, 66, 92):
        bevel(pen, (x, 100, x + 20, 110), brass, brass_l, (80, 58, 32), 1)
        pen.line((x + 4, 104, x + 15, 104), fill=plum_d)
        pen.line((x + 4, 107, x + 11, 107), fill=plum_d)
    for x in (24, 64, 104):
        bolt(pen, x, 28, 2, brass_l, ink)
    im = wash_rect(im, (8, 84, 120, 94), dust, 22)
    pen = ImageDraw.Draw(im)
    scratches(pen, rng, (188, 180, 164), 4, (8, 8, 120, 120))
    wall_frame(im, ink, cream, slate)
    return im


def wall_pav_07(seed):
    sid = 'after_hours_pavilion'
    plum, plum_d, plum_l = C(sid, 'plum'), C(sid, 'plum_dark'), C(sid, 'plum_light')
    slate, terra, terra_d = C(sid, 'slate'), C(sid, 'terrazzo'), C(sid, 'terrazzo_dark')
    brass, brass_l = C(sid, 'brass'), C(sid, 'brass_light')
    cream, ink, dust = C(sid, 'cream'), C(sid, 'ink'), C(sid, 'dust')
    im = material(128, 128, plum, seed, cell=64, amount=8, tilt=5)
    pen = ImageDraw.Draw(im)
    shadow(pen, (7, 7, 121, 121), ink, 2)
    bevel(pen, (8, 8, 120, 120), brass, brass_l, (84, 60, 34), 3)
    bevel(pen, (12, 12, 116, 116), terra, cream, terra_d, 2)
    # directory board
    bevel(pen, (14, 14, 114, 74), terra, cream, terra_d, 2)
    # route map with a line that leaves the map and enters the slot column
    cx, cy = 42, 43
    pen.ellipse((cx - 19, cy - 19, cx + 19, cy + 19), outline=brass, width=2)
    pen.ellipse((cx - 17, cy - 17, cx + 17, cy + 17), outline=terra_d)
    route = [(cx - 12, cy + 6), (cx - 4, cy - 10), (cx + 8, cy - 2),
             (cx - 2, cy + 10), (cx + 14, cy + 4), (78, cy + 4), (84, cy - 2)]
    pen.line(route, fill=plum, width=2, joint='curve')
    for x, y in route[::2]:
        pen.ellipse((x - 2, y - 2, x + 2, y + 2), fill=brass, outline=plum_d)
    pen.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=brass_l, outline=plum_d)
    pen.polygon([(84, cy - 2), (78, cy - 6), (78, cy + 2)], fill=plum_d)
    # slot columns
    for col in (0, 1):
        x0 = 80 + col * 16
        for row in range(4):
            y0 = 20 + row * 12
            bevel(pen, (x0, y0, x0 + 12, y0 + 8), brass, brass_l, (82, 58, 32), 1)
            recess(pen, (x0 + 2, y0 + 2, x0 + 10, y0 + 6), plum_d, ink, brass, 1)
    # counter lip
    shadow(pen, (12, 74, 116, 80), ink, 2)
    bevel(pen, (12, 74, 116, 80), brass, brass_l, (82, 58, 32), 2)
    # ticket recess and service grille
    recess(pen, (14, 82, 112, 112), (54, 42, 52), ink, brass, 2)
    bevel(pen, (22, 94, 68, 102), brass, brass_l, (82, 58, 32), 1)
    recess(pen, (26, 96, 64, 100), plum_d, ink, brass, 1)
    bevel(pen, (32, 99, 48, 104), cream, (255, 250, 236), terra, 1)
    for x in (78, 88, 98):
        pen.rectangle((x, 88, x + 4, 108), fill=(66, 52, 62), outline=ink)
        pen.line((x + 1, 90, x + 1, 106), fill=brass)
    bevel(pen, (22, 104, 54, 110), brass, brass_l, (82, 58, 32), 1)
    pen.line((26, 107, 50, 107), fill=plum_d)
    im = wash_rect(im, (14, 104, 112, 114), dust, 22)
    pen = ImageDraw.Draw(im)
    rng = random.Random(seed + 207)
    scratches(pen, rng, (214, 184, 128), 5, (14, 14, 114, 112))
    chips(pen, rng, (108, 84, 52), 3, (14, 14, 114, 112))
    wall_frame(im, ink, brass_l, plum_d)
    return im


def wall_pav_08(seed):
    sid = 'after_hours_pavilion'
    plum, plum_d, plum_l = C(sid, 'plum'), C(sid, 'plum_dark'), C(sid, 'plum_light')
    slate, terra, terra_d = C(sid, 'slate'), C(sid, 'terrazzo'), C(sid, 'terrazzo_dark')
    brass, brass_l = C(sid, 'brass'), C(sid, 'brass_light')
    cream, ink, dust = C(sid, 'cream'), C(sid, 'ink'), C(sid, 'dust')
    im = material(128, 128, plum, seed, cell=64, amount=8, tilt=5)
    pen = ImageDraw.Draw(im)
    shadow(pen, (7, 7, 121, 121), ink, 2)
    bevel(pen, (8, 8, 120, 120), brass, brass_l, (84, 60, 34), 3)
    bevel(pen, (12, 12, 116, 116), terra, cream, terra_d, 2)
    # left half: real directory face
    bevel(pen, (16, 16, 60, 74), terra, cream, terra_d, 2)
    cx, cy = 38, 42
    pen.ellipse((cx - 13, cy - 13, cx + 13, cy + 13), outline=brass, width=2)
    pen.line((cx - 9, cy + 4, cx - 2, cy - 8, cx + 7, cy), fill=plum, width=2,
             joint='curve')
    pen.line((cx + 7, cy, cx + 11, cy + 5, 56, cy + 5), fill=plum, width=2,
             joint='curve')
    pen.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill=brass_l, outline=plum_d)
    for row in range(3):
        y0 = 22 + row * 12
        bevel(pen, (44, y0, 56, y0 + 8), brass, brass_l, (82, 58, 32), 1)
        recess(pen, (46, y0 + 2, 54, y0 + 6), plum_d, ink, brass, 1)
    recess(pen, (16, 82, 60, 112), (54, 42, 52), ink, brass, 2)
    bevel(pen, (22, 94, 54, 102), brass, brass_l, (82, 58, 32), 1)
    recess(pen, (26, 96, 50, 100), plum_d, ink, brass, 1)
    # right half: the same face inlaid solid, with no opening or depth
    bevel(pen, (68, 16, 112, 112), terra, cream, terra_d, 2)
    pen.rectangle((68, 16, 112, 112), outline=terra_d)
    # ghost directory board
    pen.rectangle((72, 20, 108, 74), outline=terra_d)
    pen.ellipse((78, 30, 102, 54), outline=terra_d)
    pen.ellipse((82, 34, 98, 50), outline=brass)
    pen.line((82, 48, 90, 34, 100, 44), fill=terra_d, width=2, joint='curve')
    pen.line((100, 44, 108, 40), fill=terra_d, width=2)
    for row in range(3):
        y0 = 26 + row * 12
        pen.rectangle((94, y0, 104, y0 + 7), outline=terra_d)
        pen.rectangle((96, y0 + 2, 102, y0 + 5), fill=terra_d)
    # ghost ticket recess and inlaid blank ticket stub
    pen.rectangle((72, 82, 108, 108), outline=terra_d)
    pen.rectangle((78, 94, 98, 99), outline=terra_d)
    pen.rectangle((82, 97, 94, 101), fill=terra, outline=terra_d)
    # discontinuous route line across the seam (impossible split)
    pen.line((56, 36, 60, 36), fill=plum, width=2)
    pen.line((68, 50, 74, 50), fill=plum, width=2)
    pen.polygon([(74, 50), (70, 47), (70, 53)], fill=plum)
    # brass seam
    bevel(pen, (62, 10, 66, 118), brass, brass_l, (82, 58, 32), 1)
    bolt(pen, 64, 16, 1, brass_l, ink)
    bolt(pen, 64, 112, 1, brass_l, ink)
    im = wash_rect(im, (14, 104, 112, 114), dust, 20)
    pen = ImageDraw.Draw(im)
    rng = random.Random(seed + 208)
    scratches(pen, rng, (210, 182, 130), 4, (14, 14, 114, 112))
    chips(pen, rng, (108, 84, 52), 3, (14, 14, 114, 112))
    wall_frame(im, ink, brass_l, plum_d)
    return im


PAVILION_WALLS = [wall_pav_01, wall_pav_02, wall_pav_03, wall_pav_04,
                  wall_pav_05, wall_pav_06, wall_pav_07, wall_pav_08]


# -- flats -------------------------------------------------------------------
def flat_drowned_01(seed):
    sid = 'drowned_records'
    ink, chalk, bone, paper = C(sid, 'ink'), C(sid, 'chalk'), C(sid, 'bone'), C(sid, 'paper')
    silt, petrol, slate = C(sid, 'silt'), C(sid, 'petrol'), C(sid, 'slate')
    copper, copper_l = C(sid, 'copper'), C(sid, 'copper_light')
    im = material(64, 64, slate, seed, cell=32, amount=13, tilt=8)
    for row in range(4):
        for col in range(4):
            box = (col * 16, row * 16, col * 16 + 15, row * 16 + 15)
            tone = (row * 4 + col) % 3
            im = wash_rect(im, box, chalk if tone == 0 else (petrol if tone == 1 else silt), 10)
    pen = ImageDraw.Draw(im)
    for x in (15, 31, 47):
        pen.line((x, 2, x, 61), fill=ink)
        pen.line((x + 1, 2, x + 1, 61), fill=(112, 128, 132))
    for y in (15, 31, 47):
        pen.line((2, y, 61, y), fill=ink)
        pen.line((2, y + 1, 61, y + 1), fill=(112, 128, 132))
    rng = random.Random(seed + 301)
    for _ in range(5):
        x, y = rng.randrange(3, 57), rng.randrange(3, 57)
        im = wash_ellipse(im, (x, y, x + rng.randrange(3, 9), y + rng.randrange(2, 6)),
                          silt, 42)
    pen = ImageDraw.Draw(im)
    for _ in range(3):
        x, y = rng.randrange(4, 50), rng.randrange(4, 50)
        pen.polygon([(x, y), (x + 6, y + 1), (x + 5, y + 4), (x + 1, y + 3)],
                    fill=paper, outline=(118, 106, 84))
    for x, y in ((8, 40), (56, 24)):
        pen.ellipse((x - 3, y - 3, x + 3, y + 3), fill=copper, outline=ink)
        pen.point((x - 1, y - 1), fill=copper_l)
    scratches(pen, rng, (124, 140, 142), 6, (3, 3, 60, 60))
    flat_border(im, ink)
    return im


def flat_drowned_02(seed):
    sid = 'drowned_records'
    ink, chalk = C(sid, 'ink'), C(sid, 'chalk')
    silt, petrol = C(sid, 'silt'), C(sid, 'petrol')
    copper, copper_l = C(sid, 'copper'), C(sid, 'copper_light')
    im = material(64, 64, petrol, seed, cell=32, amount=10, tilt=5)
    im = wash_ellipse(im, (6, 6, 58, 58), (56, 72, 76), 70)
    pen = ImageDraw.Draw(im)
    cx = cy = 32
    pen.ellipse((cx - 25, cy - 25, cx + 25, cy + 25), fill=(38, 52, 56),
                outline=ink, width=2)
    pen.ellipse((cx - 22, cy - 22, cx + 22, cy + 22), outline=copper, width=3)
    pen.ellipse((cx - 18, cy - 18, cx + 18, cy + 18), fill=(24, 34, 38), outline=ink)
    for k in range(8):
        ang = math.radians(k * 45)
        x0 = cx + math.cos(ang) * 7
        y0 = cy + math.sin(ang) * 7
        x1 = cx + math.cos(ang) * 17
        y1 = cy + math.sin(ang) * 17
        pen.line((x0, y0, x1, y1), fill=(88, 104, 108), width=3)
        pen.line((x0, y0, x1, y1), fill=(50, 64, 68), width=1)
    pen.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=copper, outline=ink)
    pen.line((cx - 3, cy, cx + 3, cy), fill=copper_l)
    for k in range(4):
        ang = math.radians(45 + k * 90)
        bolt(pen, round(cx + math.cos(ang) * 21), round(cy + math.sin(ang) * 21),
             1, copper_l, ink)
    rng = random.Random(seed + 302)
    for _ in range(7):
        ang = rng.random() * math.tau
        r = rng.randrange(20, 30)
        x, y = round(cx + math.cos(ang) * r), round(cy + math.sin(ang) * r)
        im = wash_ellipse(im, (x - 3, y - 2, x + 3, y + 2), silt, 55)
    pen = ImageDraw.Draw(im)
    for _ in range(5):
        x, y = rng.randrange(4, 58), rng.randrange(4, 58)
        pen.line((x, y, x + rng.randrange(2, 6), y), fill=(42, 56, 60))
    scratches(pen, rng, (96, 112, 114), 4, (4, 4, 60, 60))
    flat_border(im, ink)
    return im


def flat_drowned_03(seed):
    sid = 'drowned_records'
    ink, chalk, bone = C(sid, 'ink'), C(sid, 'chalk'), C(sid, 'bone')
    silt, slate = C(sid, 'silt'), C(sid, 'slate')
    copper, copper_l = C(sid, 'copper'), C(sid, 'copper_light')
    im = material(64, 64, (188, 184, 168), seed, cell=32, amount=6, tilt=4)
    pen = ImageDraw.Draw(im)
    for x in (31, 63):
        pen.line((x, 2, x, 61), fill=slate)
        pen.line((max(1, x - 1), 2, max(1, x - 1), 61), fill=chalk)
    for y in (31, 63):
        pen.line((2, y, 61, y), fill=slate)
        pen.line((2, max(1, y - 1), 61, max(1, y - 1)), fill=chalk)
    for px in (15, 47):
        for py in (15, 47):
            for k in range(4):
                pen.point((px + k * 3, py), fill=(158, 156, 142))
                pen.point((px, py + k * 3), fill=(158, 156, 142))
    for x, y in ((16, 16), (48, 48)):
        pen.ellipse((x - 2, y - 2, x + 2, y + 2), fill=copper, outline=ink)
        pen.point((x, y), fill=copper_l)
    rng = random.Random(seed + 303)
    for _ in range(4):
        x, y = rng.randrange(4, 56), rng.randrange(4, 56)
        im = wash_ellipse(im, (x, y, x + rng.randrange(4, 10), y + rng.randrange(3, 8)),
                          silt, 22)
    pen = ImageDraw.Draw(im)
    for _ in range(4):
        x, y = rng.randrange(4, 58), rng.randrange(4, 58)
        pen.point((x, y), fill=(176, 172, 156))
    flat_border(im, slate)
    return im


def flat_drowned_04(seed):
    sid = 'drowned_records'
    ink, chalk, bone = C(sid, 'ink'), C(sid, 'chalk'), C(sid, 'bone')
    silt, slate = C(sid, 'silt'), C(sid, 'slate')
    copper, copper_l = C(sid, 'copper'), C(sid, 'copper_light')
    im = material(64, 64, (172, 170, 158), seed, cell=32, amount=6, tilt=3)
    pen = ImageDraw.Draw(im)
    for y in (31, 63):
        pen.line((2, y, 61, y), fill=slate)
        pen.line((2, max(1, y - 1), 61, max(1, y - 1)), fill=chalk)
    for x in (31, 63):
        pen.line((x, 2, x, 61), fill=slate)
    for y in (10, 40):
        shadow(pen, (6, y, 58, y + 13), ink, 2)
        recess(pen, (6, y, 58, y + 13), (60, 70, 72), ink, copper_l, 1)
        bevel(pen, (8, y + 2, 56, y + 11), (234, 226, 202), (255, 250, 232),
              (196, 186, 160), 1)
        pen.line((12, y + 6, 52, y + 6), fill=(255, 252, 238))
        for x in (12, 50):
            pen.line((x, y - 1, x, y + 14), fill=copper)
    rng = random.Random(seed + 304)
    for _ in range(3):
        x, y = rng.randrange(4, 56), rng.randrange(4, 56)
        im = wash_ellipse(im, (x, y, x + rng.randrange(4, 10), y + rng.randrange(3, 8)),
                          silt, 20)
    pen = ImageDraw.Draw(im)
    for _ in range(4):
        x, y = rng.randrange(4, 58), rng.randrange(4, 58)
        pen.point((x, y), fill=copper_l)
    flat_border(im, slate)
    return im


def flat_switch_01(seed):
    sid = 'switchyard_chapel'
    ink, iron = (24, 23, 22), C(sid, 'iron')
    rust, rust_l = C(sid, 'rust'), C(sid, 'rust_light')
    oxide, bone = C(sid, 'oxide'), C(sid, 'bone')
    im = material(64, 64, (70, 68, 64), seed, cell=32, amount=8, tilt=7)
    for box, col in (((2, 2, 30, 30), rust_l), ((33, 2, 61, 30), oxide),
                     ((2, 33, 30, 61), oxide), ((33, 33, 61, 61), rust_l)):
        im = wash_rect(im, box, col, 22)
    pen = ImageDraw.Draw(im)
    for x in (31, 32):
        pen.line((2, x, 61, x), fill=(28, 27, 26) if x == 31 else (96, 90, 80))
    for y in (31, 32):
        pen.line((2, y, 61, y), fill=(28, 27, 26) if y == 31 else (96, 90, 80))
    rng = random.Random(seed + 401)
    for bx, by in ((6, 6), (26, 6), (38, 6), (58, 6), (6, 26), (26, 26),
                   (38, 26), (58, 26), (6, 38), (26, 38), (38, 38), (58, 38),
                   (6, 58), (26, 58), (38, 58), (58, 58)):
        bolt(pen, bx, by, 1, (88, 84, 76), (26, 25, 24))
    for py in range(6, 28, 7):
        for px in range(6, 28, 7):
            pen.polygon([(px + 3, py), (px + 6, py + 3), (px + 3, py + 6),
                         (px, py + 3)], fill=rust_l)
            pen.line((px + 1, py + 3, px + 3, py + 1), fill=bone)
        for px in range(37, 59, 7):
            pen.polygon([(px + 3, py + 32), (px + 6, py + 35), (px + 3, py + 38),
                         (px, py + 35)], fill=rust)
            pen.line((px + 1, py + 35, px + 3, py + 33), fill=(136, 128, 112))
    for _ in range(5):
        x, y = rng.randrange(4, 56), rng.randrange(4, 56)
        im = wash_ellipse(im, (x, y, x + rng.randrange(3, 8), y + rng.randrange(2, 5)),
                          oxide, 45)
    pen = ImageDraw.Draw(im)
    scratches(pen, rng, (150, 140, 120), 4, (4, 4, 60, 60))
    flat_border(im, (24, 23, 22))
    return im


def flat_switch_02(seed):
    sid = 'switchyard_chapel'
    ink = (24, 23, 22)
    rust, rust_l = C(sid, 'rust'), C(sid, 'rust_light')
    oxide, bone = C(sid, 'oxide'), C(sid, 'bone')
    cable = C(sid, 'cable')
    im = material(64, 64, (48, 46, 42), seed, cell=32, amount=7, tilt=4)
    pen = ImageDraw.Draw(im)
    for x in (4, 20, 44, 60):
        pen.line((x, 2, x, 61), fill=(34, 32, 30))
        pen.line((x + 1, 2, x + 1, 61), fill=(92, 86, 76))
    # trench
    pen.rectangle((22, 2, 42, 61), fill=(28, 27, 26))
    bevel(pen, (22, 2, 25, 61), rust, rust_l, oxide, 1)
    bevel(pen, (39, 2, 42, 61), rust, rust_l, oxide, 1)
    for k, x in enumerate((28, 32, 36)):
        pen.line((x, 2, x, 61), fill=cable, width=3)
        pen.line((x - 1, 2, x - 1, 61), fill=(rust if k == 1 else (70, 66, 58)), width=1)
        pen.line((x + 1, 2, x + 1, 61), fill=(110, 96, 76), width=1)
    for y in (8, 24, 40, 56):
        pen.rectangle((22, y, 42, y + 2), fill=(62, 58, 52), outline=ink)
        bolt(pen, 23, y + 1, 1, rust_l, ink)
        bolt(pen, 41, y + 1, 1, rust_l, ink)
    for y in range(8, 30, 8):
        for x in range(7, 20, 6):
            pen.polygon([(x + 3, y), (x + 6, y + 3), (x + 3, y + 6), (x, y + 3)],
                        fill=(74, 70, 64))
        for x in range(47, 60, 6):
            pen.polygon([(x + 3, y + 28), (x + 6, y + 31), (x + 3, y + 34),
                         (x, y + 31)], fill=(74, 70, 64))
    rng = random.Random(seed + 402)
    for _ in range(5):
        x, y = rng.randrange(4, 58), rng.randrange(4, 58)
        im = wash_ellipse(im, (x, y, x + rng.randrange(3, 7), y + rng.randrange(2, 5)),
                          oxide, 38)
    pen = ImageDraw.Draw(im)
    scratches(pen, rng, (120, 108, 88), 4, (4, 4, 60, 60))
    flat_border(im, ink)
    return im


def flat_switch_03(seed):
    sid = 'switchyard_chapel'
    ink = (24, 23, 22)
    ivory, bone = C(sid, 'ivory'), C(sid, 'bone')
    rust, oxide = C(sid, 'rust'), C(sid, 'oxide')
    im = material(64, 64, (176, 172, 158), seed, cell=32, amount=5, tilt=3)
    pen = ImageDraw.Draw(im)
    for y in range(2, 62, 8):
        pen.line((2, y, 61, y), fill=(206, 202, 188))
        pen.line((2, y + 1, 61, y + 1), fill=(146, 142, 128))
        pen.line((2, y + 2, 61, y + 2), fill=(164, 160, 146))
        pen.line((2, y + 3, 61, y + 3), fill=(130, 126, 114))
        pen.line((2, y + 4, 61, y + 4), fill=(152, 148, 134))
    for x in (8, 24, 40, 56):
        for y in (6, 22, 38, 54):
            bolt(pen, x, y, 1, (118, 112, 98), (54, 50, 44))
    rng = random.Random(seed + 403)
    for _ in range(4):
        x, y = rng.randrange(6, 58), rng.randrange(4, 58)
        pen.line((x, y, x + rng.randrange(0, 2), y + rng.randrange(4, 12)),
                 fill=rust)
    for _ in range(3):
        x, y = rng.randrange(4, 58), rng.randrange(4, 58)
        im = wash_ellipse(im, (x, y, x + rng.randrange(4, 9), y + rng.randrange(3, 6)),
                          oxide, 22)
    pen = ImageDraw.Draw(im)
    scratches(pen, rng, (140, 134, 118), 3, (4, 4, 60, 60))
    flat_border(im, (64, 60, 54))
    return im


def flat_switch_04(seed):
    sid = 'switchyard_chapel'
    ink = (24, 23, 22)
    ivory, bone = C(sid, 'ivory'), C(sid, 'bone')
    rust, oxide = C(sid, 'rust'), C(sid, 'oxide')
    amber, amber_l = C(sid, 'amber'), C(sid, 'amber_light')
    im = material(64, 64, (168, 165, 152), seed, cell=32, amount=5, tilt=3)
    pen = ImageDraw.Draw(im)
    for y in range(2, 62, 8):
        pen.line((2, y, 61, y), fill=(198, 194, 180))
        pen.line((2, y + 1, 61, y + 1), fill=(142, 138, 126))
        pen.line((2, y + 2, 61, y + 2), fill=(158, 154, 140))
        pen.line((2, y + 3, 61, y + 3), fill=(126, 122, 110))
        pen.line((2, y + 4, 61, y + 4), fill=(148, 144, 130))
    for cx, cy in ((20, 20), (48, 48)):
        pen.ellipse((cx - 12, cy - 12, cx + 12, cy + 12), fill=(58, 54, 48),
                    outline=ink, width=2)
        pen.ellipse((cx - 9, cy - 9, cx + 9, cy + 9), fill=amber, outline=(80, 52, 28))
        pen.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), fill=(240, 214, 160))
        pen.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill=(255, 244, 214))
        for dx, dy in ((-11, 0), (11, 0), (0, -11), (0, 11)):
            pen.line((cx + dx, cy + dy, cx, cy), fill=(40, 38, 34), width=2)
        bolt(pen, cx, cy, 2, rust, oxide)
        for k in range(4):
            ang = math.radians(45 + k * 90)
            bolt(pen, round(cx + math.cos(ang) * 11), round(cy + math.sin(ang) * 11),
                 1, (108, 98, 82), ink)
    rng = random.Random(seed + 404)
    for _ in range(4):
        x, y = rng.randrange(6, 58), rng.randrange(6, 58)
        pen.line((x, y, x + rng.randrange(0, 2), y + rng.randrange(3, 9)), fill=rust)
    scratches(pen, rng, (138, 132, 116), 3, (4, 4, 60, 60))
    flat_border(im, (64, 60, 54))
    return im


def flat_pav_01(seed):
    sid = 'after_hours_pavilion'
    plum, plum_d = C(sid, 'plum'), C(sid, 'plum_dark')
    slate, terra, terra_d = C(sid, 'slate'), C(sid, 'terrazzo'), C(sid, 'terrazzo_dark')
    brass, brass_l = C(sid, 'brass'), C(sid, 'brass_light')
    ink = C(sid, 'ink')
    im = material(64, 64, terra, seed, cell=32, amount=5, tilt=4)
    rng = random.Random(seed + 501)
    pen = ImageDraw.Draw(im)
    for _ in range(46):
        x, y = rng.randrange(4, 58), rng.randrange(4, 58)
        s = rng.randrange(1, 4)
        col = rng.choice((terra_d, plum, slate, brass, terra_d))
        if rng.random() < 0.5:
            pen.rectangle((x, y, x + s, y + s), fill=col)
        else:
            pen.polygon([(x, y), (x + s + 1, y), (x, y + s + 1)], fill=col)
    for x in (31, 32):
        pen.line((2, x, 61, x), fill=brass if x == 31 else brass_l)
    for y in (31, 32):
        pen.line((2, y, 61, y), fill=brass if y == 31 else brass_l)
    # inlaid geometric square, deliberately offset across a brass joint
    pen.rectangle((20, 20, 44, 44), outline=brass)
    pen.rectangle((23, 23, 41, 41), outline=terra_d)
    pen.polygon([(32, 25), (39, 32), (32, 39), (25, 32)], outline=plum)
    pen.polygon([(32, 27), (37, 32), (32, 37), (27, 32)], fill=plum)
    for x, y in ((8, 8), (56, 8), (8, 56), (56, 56)):
        bolt(pen, x, y, 2, brass_l, ink)
    for _ in range(5):
        x, y = rng.randrange(4, 58), rng.randrange(4, 58)
        im = wash_ellipse(im, (x, y, x + rng.randrange(3, 7), y + rng.randrange(2, 5)),
                          plum, 14)
    pen = ImageDraw.Draw(im)
    scratches(pen, rng, (240, 234, 218), 4, (4, 4, 60, 60))
    flat_border(im, brass)
    return im


def flat_pav_02(seed):
    sid = 'after_hours_pavilion'
    plum, plum_d, plum_l = C(sid, 'plum'), C(sid, 'plum_dark'), C(sid, 'plum_light')
    slate, terra = C(sid, 'slate'), C(sid, 'terrazzo')
    brass, brass_l = C(sid, 'brass'), C(sid, 'brass_light')
    ink = C(sid, 'ink')
    im = material(64, 64, plum, seed, cell=32, amount=13, tilt=6)
    pen = ImageDraw.Draw(im)
    # woven carpet marks
    rng = random.Random(seed + 502)
    for _ in range(80):
        x, y = rng.randrange(2, 62), rng.randrange(2, 62)
        c = rng.choice((plum_l, plum_d, (116, 96, 112)))
        pen.point((x, y), fill=c)
        if rng.random() < 0.4:
            pen.point((x + 1, y), fill=c)
    # brass queue line, an L with a worn arrow
    pen.line((40, 2, 40, 40), fill=(70, 52, 30), width=4)
    pen.line((40, 40, 61, 40), fill=(70, 52, 30), width=4)
    pen.line((40, 3, 40, 39), fill=brass, width=2)
    pen.line((40, 40, 60, 40), fill=brass, width=2)
    pen.polygon([(61, 40), (55, 36), (55, 44)], fill=brass_l, outline=ink)
    pen.line((40, 40, 40, 61), fill=(70, 52, 30), width=4)
    pen.line((40, 40, 40, 60), fill=brass, width=2)
    # worn mat
    pen.rectangle((8, 47, 32, 60), fill=plum_d, outline=ink)
    pen.rectangle((10, 49, 30, 58), outline=(88, 68, 50))
    for x in range(12, 30, 4):
        pen.line((x, 50, x, 57), fill=(80, 62, 76))
    for _ in range(4):
        x, y = rng.randrange(4, 58), rng.randrange(4, 58)
        im = wash_ellipse(im, (x, y, x + rng.randrange(2, 6), y + rng.randrange(2, 4)),
                          plum_l, 16)
    pen = ImageDraw.Draw(im)
    scratches(pen, rng, (92, 72, 88), 5, (4, 4, 60, 60))
    flat_border(im, ink)
    return im


def flat_pav_03(seed):
    sid = 'after_hours_pavilion'
    plum, plum_d = C(sid, 'plum'), C(sid, 'plum_dark')
    slate, terra, terra_d = C(sid, 'slate'), C(sid, 'terrazzo'), C(sid, 'terrazzo_dark')
    brass, brass_l = C(sid, 'brass'), C(sid, 'brass_light')
    cream, ink, dust = C(sid, 'cream'), C(sid, 'ink'), C(sid, 'dust')
    im = material(64, 64, (204, 199, 186), seed, cell=32, amount=5, tilt=3)
    pen = ImageDraw.Draw(im)
    for x in (31, 32):
        pen.line((2, x, 61, x), fill=slate if x == 31 else cream)
    for y in (31, 32):
        pen.line((2, y, 61, y), fill=slate if y == 31 else cream)
    rng = random.Random(seed + 503)
    for _ in range(26):
        x, y = rng.randrange(4, 60), rng.randrange(4, 60)
        pen.point((x, y), fill=(186, 182, 168))
    for x, y in ((16, 16), (48, 48)):
        pen.ellipse((x - 2, y - 2, x + 2, y + 2), fill=brass, outline=ink)
        pen.point((x, y), fill=brass_l)
    for _ in range(3):
        x, y = rng.randrange(4, 56), rng.randrange(4, 56)
        im = wash_ellipse(im, (x, y, x + rng.randrange(4, 9), y + rng.randrange(3, 6)),
                          dust, 18)
    pen = ImageDraw.Draw(im)
    scratches(pen, rng, (222, 218, 204), 3, (4, 4, 60, 60))
    flat_border(im, slate)
    return im


def flat_pav_04(seed):
    sid = 'after_hours_pavilion'
    plum, plum_d = C(sid, 'plum'), C(sid, 'plum_dark')
    slate, terra, terra_d = C(sid, 'slate'), C(sid, 'terrazzo'), C(sid, 'terrazzo_dark')
    brass, brass_l = C(sid, 'brass'), C(sid, 'brass_light')
    cream, ink, dust = C(sid, 'cream'), C(sid, 'ink'), C(sid, 'dust')
    im = material(64, 64, (196, 192, 180), seed, cell=32, amount=5, tilt=3)
    pen = ImageDraw.Draw(im)
    for x in (31, 32):
        pen.line((2, x, 61, x), fill=slate if x == 31 else cream)
    for y in (31, 32):
        pen.line((2, y, 61, y), fill=slate if y == 31 else cream)
    for y in (12, 40):
        for x in (10, 26, 42):
            shadow(pen, (x, y, x + 10, y + 8), ink, 1)
            recess(pen, (x, y, x + 10, y + 8), (58, 56, 50), ink, brass_l, 1)
            bevel(pen, (x + 1, y + 1, x + 9, y + 7), (240, 233, 210),
                  (255, 252, 238), (206, 198, 174), 1)
            pen.line((x + 2, y + 4, x + 8, y + 4), fill=(255, 253, 240))
            bevel(pen, (x + 3, y - 1, x + 7, y), brass, brass_l, (88, 64, 36), 1)
    rng = random.Random(seed + 504)
    for _ in range(3):
        x, y = rng.randrange(4, 56), rng.randrange(4, 56)
        im = wash_ellipse(im, (x, y, x + rng.randrange(3, 7), y + rng.randrange(2, 5)),
                          dust, 16)
    pen = ImageDraw.Draw(im)
    scratches(pen, rng, (228, 222, 206), 3, (4, 4, 60, 60))
    flat_border(im, slate)
    return im


DROWNED_FLATS = [flat_drowned_01, flat_drowned_02, flat_drowned_03, flat_drowned_04]
SWITCHYARD_FLATS = [flat_switch_01, flat_switch_02, flat_switch_03, flat_switch_04]
PAVILION_FLATS = [flat_pav_01, flat_pav_02, flat_pav_03, flat_pav_04]


# -- props -------------------------------------------------------------------
def prop_drowned_lamp(seed):
    sid = 'drowned_records'
    ink, chalk, bone, paper = C(sid, 'ink'), C(sid, 'chalk'), C(sid, 'bone'), C(sid, 'paper')
    silt, petrol, slate = C(sid, 'silt'), C(sid, 'petrol'), C(sid, 'slate')
    copper, copper_l = C(sid, 'copper'), C(sid, 'copper_light')
    glass = C(sid, 'glass')
    im = Image.new('RGBA', (96, 128), (0, 0, 0, 0))
    pen = ImageDraw.Draw(im)
    # pallet and feet
    bevel(pen, (22, 114, 74, 121), (66, 58, 48), (112, 98, 78), (40, 34, 28), 1)
    pen.polygon([(18, 119), (30, 119), (28, 123), (20, 123)], fill=(54, 48, 40), outline=ink)
    pen.polygon([(66, 119), (78, 119), (76, 123), (68, 123)], fill=(54, 48, 40), outline=ink)
    # paper-wrapped plinth
    bevel(pen, (28, 104, 68, 116), bone, chalk, (130, 118, 96), 1)
    bevel(pen, (31, 104, 34, 116), copper, copper_l, (92, 56, 32), 1)
    bevel(pen, (62, 104, 65, 116), copper, copper_l, (92, 56, 32), 1)
    bevel(pen, (38, 108, 58, 114), paper, chalk, (128, 116, 94), 1)
    pen.line((41, 111, 55, 111), fill=(96, 84, 66))
    # stem
    bevel(pen, (44, 82, 52, 108), copper, copper_l, (88, 52, 30), 2)
    bevel(pen, (40, 102, 56, 106), copper, copper_l, (88, 52, 30), 1)
    # lantern hood and body
    pen.polygon([(28, 34), (68, 34), (64, 42), (32, 42)], fill=copper, outline=ink)
    pen.line((30, 35, 66, 35), fill=copper_l)
    bevel(pen, (32, 42, 64, 74), slate, (126, 146, 150), (38, 52, 58), 2)
    pen.rectangle((36, 46, 60, 70), fill=glass, outline=ink)
    for y in (50, 56, 62):
        pen.line((37, y, 59, y), fill=(122, 136, 128))
    for x in (40, 48, 56):
        pen.line((x, 44, x, 72), fill=(52, 66, 72), width=2)
    pen.line((36, 57, 60, 57), fill=(52, 66, 72), width=2)
    bevel(pen, (30, 74, 66, 81), copper, copper_l, (88, 52, 30), 2)
    pen.arc((42, 24, 54, 36), 180, 360, fill=copper, width=3)
    # gauge on the stem
    pen.ellipse((54, 84, 68, 98), fill=copper, outline=ink)
    pen.ellipse((57, 87, 65, 95), fill=bone, outline=ink)
    pen.line((61, 93, 64, 89), fill=petrol)
    pen.point((61, 93), fill=copper)
    # chipped paper and silt
    im = wash_poly(im, [(24, 112), (40, 110), (58, 113), (74, 111), (74, 116), (24, 116)],
                   silt, 45)
    pen = ImageDraw.Draw(im)
    rng = random.Random(seed + 601)
    scratches(pen, rng, (132, 144, 140), 4, (30, 42, 66, 102))
    chips(pen, rng, (128, 116, 94), 3, (28, 104, 68, 116))
    return im


def prop_drowned_stack(seed):
    sid = 'drowned_records'
    ink, chalk, bone, paper = C(sid, 'ink'), C(sid, 'chalk'), C(sid, 'bone'), C(sid, 'paper')
    silt, petrol = C(sid, 'silt'), C(sid, 'petrol')
    copper, copper_l = C(sid, 'copper'), C(sid, 'copper_light')
    im = Image.new('RGBA', (96, 128), (0, 0, 0, 0))
    pen = ImageDraw.Draw(im)
    # pallet
    bevel(pen, (18, 114, 78, 121), (66, 58, 48), (112, 98, 78), (40, 34, 28), 1)
    pen.rectangle((22, 121, 74, 123), fill=(48, 42, 34), outline=ink)
    # paper bales
    for box, offset in (((20, 86, 76, 112), 0), ((24, 64, 72, 90), 1), ((28, 50, 68, 68), 0)):
        x0, y0, x1, y1 = box
        bevel(pen, box, paper, chalk, (128, 116, 94), 1)
        for k in range(3):
            y = y0 + 5 + k * 6
            pen.line((x0 + 3, y, x1 - 3, y), fill=(110, 96, 74))
            pen.line((x0 + 3, y + 1, x1 - 3, y + 1), fill=(210, 200, 174))
        for x in (x0 + 8, x1 - 11):
            bevel(pen, (x, y0, x + 3, y1), copper, copper_l, (92, 56, 32), 1)
            bolt(pen, x + 1, y0 + 4, 1, copper_l, ink)
    pen.polygon([(20, 90), (28, 86), (36, 92), (46, 87), (58, 92), (68, 87),
                 (76, 91), (76, 96), (20, 96)], fill=bone, outline=(128, 116, 94))
    # ceramic pressure seal drum
    pen.ellipse((32, 24, 64, 38), fill=bone, outline=ink)
    pen.rectangle((30, 31, 66, 50), fill=bone, outline=ink)
    pen.ellipse((32, 42, 64, 52), fill=(176, 166, 142), outline=ink)
    for y in (34, 44):
        bevel(pen, (28, y, 68, y + 4), copper, copper_l, (92, 56, 32), 1)
        for x in (31, 65):
            bolt(pen, x, y + 1, 1, copper_l, ink)
    pen.ellipse((44, 36, 56, 48), fill=bone, outline=ink)
    pen.ellipse((46, 38, 54, 46), fill=(226, 218, 198), outline=ink)
    pen.line((50, 45, 53, 41), fill=petrol)
    pen.point((50, 45), fill=copper)
    # lever and pipe
    pen.line((62, 34, 80, 22), fill=copper, width=4)
    pen.line((62, 34, 80, 22), fill=copper_l, width=1)
    pen.ellipse((76, 18, 84, 26), fill=(72, 64, 52), outline=ink)
    bevel(pen, (62, 49, 68, 66), copper, copper_l, (88, 52, 30), 1)
    pen.ellipse((60, 60, 70, 70), outline=copper, width=2)
    im = wash_poly(im, [(18, 112), (38, 109), (58, 113), (78, 110), (78, 116), (18, 116)],
                   silt, 40)
    pen = ImageDraw.Draw(im)
    rng = random.Random(seed + 602)
    scratches(pen, rng, (134, 122, 98), 4, (22, 50, 76, 112))
    chips(pen, rng, (108, 94, 72), 3, (20, 50, 76, 112))
    return im


def prop_drowned_lectern(seed):
    sid = 'drowned_records'
    ink, chalk, bone, paper = C(sid, 'ink'), C(sid, 'chalk'), C(sid, 'bone'), C(sid, 'paper')
    silt, petrol, slate = C(sid, 'silt'), C(sid, 'petrol'), C(sid, 'slate')
    copper, copper_l = C(sid, 'copper'), C(sid, 'copper_light')
    im = Image.new('RGBA', (96, 128), (0, 0, 0, 0))
    pen = ImageDraw.Draw(im)
    # feet and legs
    bevel(pen, (24, 96, 34, 123), (68, 80, 60), (124, 110, 86), (42, 36, 30), 2)
    bevel(pen, (62, 96, 72, 123), (68, 80, 60), (124, 110, 86), (42, 36, 30), 2)
    pen.rectangle((20, 119, 38, 123), fill=(48, 42, 34), outline=ink)
    pen.rectangle((58, 119, 76, 123), fill=(48, 42, 34), outline=ink)
    pen.rectangle((32, 112, 64, 117), fill=(68, 58, 46), outline=ink)
    pen.rectangle((28, 100, 68, 104), fill=(58, 50, 42), outline=ink)
    pen.rectangle((20, 116, 76, 121), fill=(58, 50, 42), outline=ink)
    # lectern board
    bevel(pen, (18, 78, 78, 100), (70, 82, 86), (118, 132, 134), (38, 50, 54), 2)
    pen.line((20, 80, 76, 80), fill=copper_l)
    # tide register wheel
    cx, cy, r = 48, 54, 27
    pen.ellipse((cx - r, cy - r, cx + r, cy + r), fill=bone, outline=ink, width=2)
    pen.ellipse((cx - r + 3, cy - r + 3, cx + r - 3, cy + r - 3), outline=copper, width=4)
    for rr in (20, 13):
        pen.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=slate)
    for k in range(12):
        ang = math.radians(k * 30 + 15)
        x0, y0 = cx + math.cos(ang) * 13, cy + math.sin(ang) * 13
        x1, y1 = cx + math.cos(ang) * 22, cy + math.sin(ang) * 22
        pen.line((x0, y0, x1, y1), fill=slate)
    for k in range(12):
        ang = math.radians(k * 30)
        x0, y0 = cx + math.cos(ang) * 23, cy + math.sin(ang) * 23
        x1, y1 = cx + math.cos(ang) * 26, cy + math.sin(ang) * 26
        pen.line((x0, y0, x1, y1), fill=copper_l)
    pen.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), fill=copper, outline=ink)
    pen.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill=ink)
    pen.polygon([(cx, cy - 5), (cx - 3, cy - 20), (cx + 3, cy - 20)], fill=copper_l,
                outline=ink)
    # hanging paper slip
    pen.polygon([(38, 80), (58, 80), (54, 95), (42, 91)], fill=paper, outline=(126, 114, 92))
    pen.line((43, 85, 53, 85), fill=(96, 84, 66))
    pen.line((43, 89, 50, 89), fill=(112, 100, 80))
    bolt(pen, 48, 81, 1, copper_l, ink)
    # ledger stack
    bevel(pen, (22, 104, 74, 116), paper, chalk, (126, 114, 92), 1)
    for y in (107, 110, 113):
        pen.line((25, y, 71, y), fill=(110, 96, 74))
    for x in (28, 68):
        bevel(pen, (x, 104, x + 3, 116), copper, copper_l, (92, 56, 32), 1)
    im = wash_poly(im, [(20, 112), (40, 109), (60, 113), (76, 110), (76, 118), (20, 118)],
                   silt, 38)
    pen = ImageDraw.Draw(im)
    rng = random.Random(seed + 603)
    scratches(pen, rng, (146, 134, 110), 4, (22, 30, 76, 116))
    chips(pen, rng, (110, 96, 74), 3, (22, 78, 76, 116))
    return im


def prop_switch_lamp(seed):
    sid = 'switchyard_chapel'
    ivory, porcelain = C(sid, 'ivory'), C(sid, 'porcelain')
    bone, rust, rust_l = C(sid, 'bone'), C(sid, 'rust'), C(sid, 'rust_light')
    iron, charcoal, oxide = C(sid, 'iron'), C(sid, 'charcoal'), C(sid, 'oxide')
    amber, amber_l = C(sid, 'amber'), C(sid, 'amber_light')
    im = Image.new('RGBA', (96, 128), (0, 0, 0, 0))
    pen = ImageDraw.Draw(im)
    # base
    bevel(pen, (26, 116, 70, 123), iron, (88, 82, 74), (24, 22, 21), 1)
    pen.polygon([(22, 119), (32, 119), (30, 123), (24, 123)], fill=(52, 48, 42),
                outline=(24, 23, 22))
    pen.polygon([(64, 119), (74, 119), (72, 123), (66, 123)], fill=(52, 48, 42), outline=(24, 23, 22))
    bevel(pen, (30, 108, 66, 116), rust, rust_l, oxide, 1)
    for x in (34, 62):
        bolt(pen, x, 112, 1, rust_l, oxide)
    # petticoat pedestal
    for k, (w, y) in enumerate(((34, 94), (30, 100), (26, 106), (22, 112))):
        pen.ellipse((48 - w // 2, y, 48 + w // 2, y + 9), fill=ivory, outline=oxide)
        pen.line((48 - w // 2 + 3, y + 2, 48 + w // 2 - 3, y + 2), fill=porcelain)
        pen.line((48, y + 3, 48, y + 8), fill=bone)
    pen.rectangle((44, 64, 52, 98), fill=iron, outline=(24, 22, 21))
    # lamp cage
    pen.polygon([(30, 28), (66, 28), (62, 36), (34, 36)], fill=rust, outline=oxide)
    pen.rectangle((34, 36, 62, 66), fill=charcoal, outline=iron)
    pen.rectangle((38, 40, 58, 62), fill=amber, outline=oxide)
    pen.rectangle((41, 43, 55, 59), fill=amber_l)
    for x in (38, 46, 54, 58):
        pen.line((x, 36, x, 66), fill=iron, width=2)
    for y in (40, 52, 62):
        pen.line((34, y, 62, y), fill=iron, width=2)
    pen.arc((42, 18, 54, 30), 180, 360, fill=iron, width=3)
    # small brass tag on base
    bevel(pen, (38, 117, 58, 122), (116, 92, 54), (154, 124, 76), (76, 56, 32), 1)
    pen.line((42, 119, 54, 119), fill=(60, 44, 28))
    rng = random.Random(seed + 604)
    scratches(pen, rng, (96, 88, 78), 4, (32, 32, 64, 116))
    return im


def prop_switch_shrine(seed):
    sid = 'switchyard_chapel'
    ivory, porcelain = C(sid, 'ivory'), C(sid, 'porcelain')
    bone, rust, rust_l = C(sid, 'bone'), C(sid, 'rust'), C(sid, 'rust_light')
    iron, charcoal, oxide = C(sid, 'iron'), C(sid, 'charcoal'), C(sid, 'oxide')
    amber, amber_l = C(sid, 'amber'), C(sid, 'amber_light')
    cable = C(sid, 'cable')
    im = Image.new('RGBA', (96, 128), (0, 0, 0, 0))
    pen = ImageDraw.Draw(im)
    # legs and feet
    bevel(pen, (22, 90, 28, 123), iron, (88, 82, 74), (24, 22, 21), 1)
    bevel(pen, (68, 90, 74, 123), iron, (88, 82, 74), (24, 22, 21), 1)
    pen.rectangle((18, 119, 32, 123), fill=charcoal, outline=(24, 23, 22))
    pen.rectangle((64, 119, 78, 123), fill=charcoal, outline=(24, 23, 22))
    for y in (34, 62, 90):
        bevel(pen, (22, y, 74, y + 4), rust, rust_l, oxide, 1)
        bolt(pen, 25, y + 2, 1, rust_l, oxide)
        bolt(pen, 71, y + 2, 1, rust_l, oxide)
    # stacked relay spools
    for y in (40, 58, 76):
        pen.ellipse((36, y - 3, 60, y + 5), fill=bone, outline=oxide)
        pen.rectangle((36, y + 1, 60, y + 15), fill=ivory, outline=oxide)
        pen.ellipse((36, y + 11, 60, y + 19), fill=bone, outline=oxide)
        for x in (36, 60):
            pen.rectangle((x - 2, y - 2, x + 2, y + 18), fill=rust, outline=oxide)
        for yy in (y + 5, y + 10):
            pen.line((38, yy, 58, yy), fill=bone)
        bolt(pen, 48, y + 8, 2, amber, oxide)
        pen.point((48, y + 7), fill=amber_l)
    # sagging cable braids
    left = cable_path([(30, 38), (18, 84)], 12, 22) + cable_path([(18, 84), (30, 94)], 5, 10)
    right = cable_path([(66, 38), (78, 84)], 12, 22) + cable_path([(78, 84), (66, 94)], 5, 10)
    front = cable_path([(30, 92), (66, 92)], 9, 24)
    for path in (left, right, front):
        braid(pen, path, cable, rust, bone, 4)
    # solid lower shelf and base, so the rack does not imply a passage
    bevel(pen, (24, 104, 72, 111), (58, 50, 44), (104, 94, 80), (24, 22, 21), 1)
    bevel(pen, (20, 114, 76, 121), (52, 46, 42), (96, 86, 74), (24, 22, 21), 1)
    # blank brass plate
    bevel(pen, (36, 105, 60, 112), (112, 88, 52), (154, 124, 76), (76, 56, 32), 1)
    pen.line((40, 107, 56, 107), fill=(58, 42, 26))
    pen.line((40, 110, 51, 110), fill=(58, 42, 26))
    rng = random.Random(seed + 605)
    scratches(pen, rng, (94, 86, 74), 4, (24, 34, 72, 116))
    return im


def prop_switch_annunciator(seed):
    sid = 'switchyard_chapel'
    ivory, porcelain = C(sid, 'ivory'), C(sid, 'porcelain')
    bone, rust, rust_l = C(sid, 'bone'), C(sid, 'rust'), C(sid, 'rust_light')
    iron, charcoal, oxide = C(sid, 'iron'), C(sid, 'charcoal'), C(sid, 'oxide')
    amber, amber_l = C(sid, 'amber'), C(sid, 'amber_light')
    im = Image.new('RGBA', (96, 128), (0, 0, 0, 0))
    pen = ImageDraw.Draw(im)
    # narrow legs and feet
    bevel(pen, (28, 96, 34, 123), iron, (88, 82, 74), (24, 22, 21), 1)
    bevel(pen, (62, 96, 68, 123), iron, (88, 82, 74), (24, 22, 21), 1)
    pen.rectangle((24, 119, 38, 123), fill=charcoal, outline=(24, 23, 22))
    pen.rectangle((58, 119, 72, 123), fill=charcoal, outline=(24, 23, 22))
    # portrait board, deliberately unlike the wide pavilion kiosk
    shadow(pen, (22, 24, 74, 104), (20, 19, 18), 2)
    bevel(pen, (22, 24, 74, 104), rust, rust_l, oxide, 3)
    bevel(pen, (26, 28, 70, 100), charcoal, iron, (18, 17, 16), 2)
    rng = random.Random(seed + 606)
    for col in range(2):
        for row in range(5):
            x = 30 + col * 20
            y = 32 + row * 12
            bevel(pen, (x, y, x + 16, y + 8), (62, 56, 46), (106, 96, 76), (28, 26, 22), 1)
            lit = (col + row * 2) % 3 != 1
            pen.rectangle((x + 3, y + 2, x + 13, y + 6),
                          fill=amber if lit else (40, 36, 30), outline=oxide)
            if lit:
                pen.point((x + 5, y + 3), fill=amber_l)
                pen.line((x + 8, y + 4, x + 11, y + 4), fill=amber_l)
    # conduit and clamps down the right edge
    bevel(pen, (66, 30, 70, 100), (58, 52, 46), (104, 94, 82), (24, 22, 21), 1)
    for y in (40, 64, 88):
        pen.rectangle((65, y, 71, y + 3), fill=iron, outline=(20, 19, 18))
    # porcelain horns and a slack cable between them
    for cx in (34, 62):
        insulator_stack(pen, cx, 4, 24, 14, 4, ivory, porcelain, bone, oxide)
        pen.rectangle((cx - 5, 21, cx + 5, 26), fill=rust, outline=oxide)
    braid(pen, cable_path([(34, 7), (62, 7)], 9, 26),
          C(sid, 'cable'), rust, bone, 4)
    # solid base between the legs
    bevel(pen, (28, 100, 68, 106), (58, 50, 44), (104, 94, 80), (24, 22, 21), 1)
    bevel(pen, (26, 104, 70, 119), (58, 50, 44), (104, 94, 80), (24, 22, 21), 1)
    # blank nameplate, bars only
    bevel(pen, (32, 90, 64, 98), (112, 88, 52), (154, 124, 76), (76, 56, 32), 1)
    pen.line((36, 93, 60, 93), fill=(58, 42, 26))
    pen.line((36, 96, 50, 96), fill=(58, 42, 26))
    for x, y in ((25, 27), (71, 27), (25, 101), (71, 101)):
        bolt(pen, x, y, 2, rust_l, oxide)
    scratches(pen, rng, (168, 142, 100), 4, (24, 26, 72, 102))
    return im

def prop_pav_bollard(seed):
    sid = 'after_hours_pavilion'
    plum, plum_d, plum_l = C(sid, 'plum'), C(sid, 'plum_dark'), C(sid, 'plum_light')
    slate, terra, terra_d = C(sid, 'slate'), C(sid, 'terrazzo'), C(sid, 'terrazzo_dark')
    brass, brass_l = C(sid, 'brass'), C(sid, 'brass_light')
    cream, ink, dust = C(sid, 'cream'), C(sid, 'ink'), C(sid, 'dust')
    im = Image.new('RGBA', (96, 128), (0, 0, 0, 0))
    pen = ImageDraw.Draw(im)
    # terrazzo plinth
    bevel(pen, (26, 112, 70, 123), terra, cream, terra_d, 2)
    pen.line((28, 115, 68, 115), fill=brass)
    pen.line((28, 121, 68, 121), fill=brass)
    # stem and push plate
    bevel(pen, (44, 82, 52, 116), brass, brass_l, (82, 58, 32), 2)
    bevel(pen, (38, 90, 58, 100), brass, brass_l, (82, 58, 32), 1)
    pen.ellipse((45, 92, 51, 98), fill=cream, outline=ink)
    pen.line((42, 96, 54, 96), fill=(110, 84, 52))
    # folded shade
    pen.polygon([(36, 54), (48, 56), (48, 86), (26, 88)], fill=plum_l, outline=ink)
    pen.polygon([(48, 56), (60, 54), (70, 88), (48, 86)], fill=plum_d, outline=ink)
    for x, y in ((36, 54), (42, 55), (48, 56), (54, 55), (60, 54)):
        pen.line((x, y, 24 + (x - 36) * 3 // 2, 88), fill=plum)
    pen.line((48, 56, 48, 86), fill=(168, 146, 166))
    bevel(pen, (28, 84, 68, 88), cream, (255, 250, 236), terra_d, 1)
    bevel(pen, (42, 46, 54, 56), brass, brass_l, (82, 58, 32), 1)
    pen.ellipse((45, 42, 51, 48), fill=brass_l, outline=ink)
    im = wash_rect(im, (26, 116, 70, 122), dust, 20)
    pen = ImageDraw.Draw(im)
    rng = random.Random(seed + 607)
    scratches(pen, rng, (226, 218, 200), 3, (28, 58, 68, 120))
    return im


def prop_pav_queue(seed):
    sid = 'after_hours_pavilion'
    plum, plum_d, plum_l = C(sid, 'plum'), C(sid, 'plum_dark'), C(sid, 'plum_light')
    slate, terra, terra_d = C(sid, 'slate'), C(sid, 'terrazzo'), C(sid, 'terrazzo_dark')
    brass, brass_l = C(sid, 'brass'), C(sid, 'brass_light')
    cream, ink, dust = C(sid, 'cream'), C(sid, 'ink'), C(sid, 'dust')
    im = Image.new('RGBA', (96, 128), (0, 0, 0, 0))
    pen = ImageDraw.Draw(im)
    # heavy base
    bevel(pen, (28, 112, 68, 123), terra, cream, terra_d, 2)
    pen.line((30, 115, 66, 115), fill=brass)
    pen.rectangle((32, 118, 64, 121), fill=slate, outline=ink)
    # post and cap
    bevel(pen, (44, 54, 52, 116), brass, brass_l, (82, 58, 32), 2)
    pen.polygon([(38, 48), (58, 48), (54, 56), (42, 56)], fill=plum, outline=ink)
    pen.line((40, 50, 56, 50), fill=plum_l)
    # belt reel
    pen.ellipse((38, 64, 58, 84), fill=brass, outline=ink)
    pen.ellipse((41, 67, 55, 81), fill=plum_d, outline=(82, 58, 32))
    pen.ellipse((45, 71, 51, 77), fill=brass_l, outline=ink)
    # sagging belt with a brass clip
    path = cable_path([(54, 70), (80, 88)], 10, 20) + cable_path([(80, 88), (72, 108)], 6, 14)
    pen.line(path, fill=(64, 46, 34), width=9, joint='curve')
    pen.line(path, fill=plum, width=7, joint='curve')
    pen.line([(x, y - 3) for x, y in path], fill=brass, width=1, joint='curve')
    pen.line([(x, y + 3) for x, y in path], fill=(82, 58, 32), width=1, joint='curve')
    pen.polygon([(68, 104), (76, 104), (74, 112), (70, 112)], fill=brass_l, outline=ink)
    # hanging blank tag with contradictory split arrow
    pen.polygon([(62, 88), (80, 86), (82, 102), (64, 104)], fill=cream, outline=terra_d)
    pen.line((67, 96, 77, 95), fill=plum_d)
    pen.polygon([(67, 96), (71, 93), (71, 99)], fill=plum_d)
    pen.polygon([(77, 95), (73, 92), (73, 98)], fill=plum_d)
    bolt(pen, 71, 86, 1, brass_l, ink)
    im = wash_rect(im, (28, 116, 68, 122), dust, 18)
    pen = ImageDraw.Draw(im)
    rng = random.Random(seed + 608)
    scratches(pen, rng, (218, 196, 148), 3, (30, 52, 78, 120))
    return im


def prop_pav_kiosk(seed):
    sid = 'after_hours_pavilion'
    plum, plum_d, plum_l = C(sid, 'plum'), C(sid, 'plum_dark'), C(sid, 'plum_light')
    slate, terra, terra_d = C(sid, 'slate'), C(sid, 'terrazzo'), C(sid, 'terrazzo_dark')
    brass, brass_l = C(sid, 'brass'), C(sid, 'brass_light')
    cream, ink, dust = C(sid, 'cream'), C(sid, 'ink'), C(sid, 'dust')
    im = Image.new('RGBA', (96, 128), (0, 0, 0, 0))
    pen = ImageDraw.Draw(im)
    # legs and feet
    bevel(pen, (20, 98, 26, 123), (68, 60, 52), (122, 110, 88), (38, 32, 28), 1)
    bevel(pen, (70, 98, 76, 123), (68, 60, 52), (122, 110, 88), (38, 32, 28), 1)
    pen.rectangle((16, 119, 30, 123), fill=plum_d, outline=ink)
    pen.rectangle((66, 119, 80, 123), fill=plum_d, outline=ink)
    # cabinet
    shadow(pen, (8, 22, 88, 100), (24, 20, 26), 2)
    bevel(pen, (8, 22, 88, 100), brass, brass_l, (82, 58, 32), 3)
    bevel(pen, (12, 26, 84, 96), terra, cream, terra_d, 2)
    # brass seam
    bevel(pen, (46, 24, 50, 98), brass, brass_l, (82, 58, 32), 1)
    # left face: real directory
    bevel(pen, (14, 30, 44, 72), terra, cream, terra_d, 1)
    pen.ellipse((18, 36, 42, 60), outline=brass, width=2)
    pen.ellipse((21, 39, 39, 57), outline=terra_d)
    pen.line((23, 50, 30, 39, 38, 46), fill=plum, width=2, joint='curve')
    pen.line((38, 46, 41, 52), fill=plum, width=2)
    pen.ellipse((28, 47, 32, 51), fill=brass_l, outline=plum_d)
    for row in range(2):
        y = 34 + row * 12
        bevel(pen, (36, y, 44, y + 7), brass, brass_l, (82, 58, 32), 1)
    # left lower ticket slot and real counter
    recess(pen, (14, 78, 44, 92), (54, 42, 52), ink, brass, 1)
    bevel(pen, (18, 82, 36, 88), brass, brass_l, (82, 58, 32), 1)
    recess(pen, (21, 84, 33, 87), plum_d, ink, brass, 1)
    bevel(pen, (38, 84, 42, 90), cream, (255, 250, 236), terra, 1)
    # counter lip
    bevel(pen, (10, 72, 86, 78), brass, brass_l, (82, 58, 32), 2)
    # right face: impossible solid inlay of the same kiosk
    pen.rectangle((52, 30, 84, 96), fill=terra, outline=terra_d)
    pen.rectangle((56, 34, 82, 70), outline=terra_d)
    pen.ellipse((60, 38, 80, 58), outline=terra_d)
    pen.ellipse((63, 41, 77, 55), outline=brass)
    pen.line((64, 52, 70, 42, 78, 48), fill=terra_d, width=2, joint='curve')
    for row in range(2):
        y = 38 + row * 12
        pen.rectangle((72, y, 80, y + 7), outline=terra_d)
        pen.rectangle((74, y + 2, 78, y + 5), fill=terra_d)
    pen.rectangle((56, 78, 82, 90), outline=terra_d)
    pen.rectangle((60, 82, 74, 86), outline=terra_d)
    pen.rectangle((62, 84, 72, 87), fill=terra, outline=terra_d)
    # projecting canopy over the real face and a round clock on the solid side
    pen.polygon([(4, 18), (54, 14), (54, 20), (4, 24)], fill=brass, outline=(82, 58, 32))
    pen.line((6, 19, 52, 16), fill=brass_l)
    pen.line((8, 23, 22, 22), fill=(82, 58, 32))
    bevel(pen, (72, 18, 76, 26), brass, brass_l, (82, 58, 32), 1)
    pen.ellipse((69, 5, 83, 19), fill=brass, outline=(82, 58, 32))
    pen.ellipse((71, 7, 81, 17), fill=cream, outline=terra_d)
    for k in range(8):
        ang = math.radians(k * 45)
        pen.line((77 + math.cos(ang) * 3, 12 + math.sin(ang) * 3,
                  77 + math.cos(ang) * 5, 12 + math.sin(ang) * 5), fill=plum_d)
    pen.line((77, 12, 77, 8), fill=plum_d)
    pen.line((77, 12, 80, 13), fill=plum_d)
    # solid plinth under the cabinet
    bevel(pen, (18, 100, 78, 106), (68, 60, 52), (122, 110, 88), (38, 32, 28), 1)
    bevel(pen, (26, 106, 70, 119), (86, 72, 82), (124, 106, 120), (54, 42, 52), 1)
    bevel(pen, (34, 111, 62, 116), brass, brass_l, (82, 58, 32), 1)
    im = wash_rect(im, (12, 92, 84, 98), dust, 20)
    pen = ImageDraw.Draw(im)
    rng = random.Random(seed + 609)
    scratches(pen, rng, (222, 198, 150), 4, (12, 26, 84, 96))
    return im


DROWNED_PROPS = {'service_lamp': prop_drowned_lamp, 'cable_shrine': prop_drowned_stack,
                 'directory_sign': prop_drowned_lectern}
SWITCHYARD_PROPS = {'service_lamp': prop_switch_lamp, 'cable_shrine': prop_switch_shrine,
                    'directory_sign': prop_switch_annunciator}
PAVILION_PROPS = {'service_lamp': prop_pav_bollard, 'cable_shrine': prop_pav_queue,
                  'directory_sign': prop_pav_kiosk}


SET_META = [
    {
        'id': 'drowned_records',
        'name': 'DROWNED RECORDS',
        'description': ('A flood-marked paper archive and pump bureaucracy: chalk-bone '
                        'filing walls, petrol waterlines, silted ceramic panels and copper '
                        'shelf trim. Filing drawers, tide gauges, pressure seals and layered '
                        'paper strata surround a circular flood register bolted through a '
                        'filing facade. Old water is suggested by stains, not live physics.'),
        'landmark': {
            'name': 'The Flood Register',
            'description': ('A circular tide-register wheel embedded in a wall of filing '
                            'drawers. Its copper ring is bolted through the cabinet face; '
                            'the scale carries two zero marks and the pointer sweeps into a '
                            'drawer bank. The paired panels are a filing facade (07) and the '
                            'register plate (08).'),
            'walls': [7, 8],
        },
        'props': {
            'service_lamp': {
                'display_name': 'Silt-Gauge Inspection Lamp',
                'description': ('A caged copper inspection lantern on a paper-wrapped plinth '
                                'with a small silt gauge. Small freestanding floor fixture.'),
            },
            'cable_shrine': {
                'display_name': 'Pressure-Seal Paper Stack',
                'description': ('A pallet of compressed paper bales under ceramic pressure '
                                'seals, copper straps, a hand lever and a blank record plate. '
                                'Freestanding archive utility object.'),
            },
            'directory_sign': {
                'display_name': 'Flood Register Lectern',
                'description': ('A two-legged lectern carrying the portable tide register '
                                'wheel, a hanging blank slip and a stack of ledgers. Landmark '
                                'directory object with a solid base.'),
            },
        },
        'gameplay_notes': ('Cosmetic material set only; no mechanics, collision, light or '
                           'sound changes are claimed. Mid-dark petrol, slate and copper '
                           'surfaces keep bright binding-ring colours legible. Suggested as '
                           'a whole-run or whole-tier identity, never mixed per room.'),
    },
    {
        'id': 'switchyard_chapel',
        'name': 'SWITCHYARD CHAPEL',
        'description': ('An ossified power exchange and ceramic relay forest: ivory '
                        'porcelain brick, rust-red iron, charcoal cable braids and warm amber '
                        'indicators. Chunky fluting, stacked relay niches and sagging bundled '
                        'cable give clear silhouettes around a silent radial conductor fan. '
                        'No religious symbol is copied from an existing game.'),
        'landmark': {
            'name': 'The Silent Conductor',
            'description': ('A nine-fin porcelain insulator fan around a dead charcoal hub. '
                            'Two cable braids descend from the hub; one terminates in a blank '
                            'porcelain cap. The paired panels are the fan (07) and a braided '
                            'cable gallery (08). No live power, bloom or motion is depicted.'),
            'walls': [7, 8],
        },
        'props': {
            'service_lamp': {
                'display_name': 'Porcelain Pilot Lamp',
                'description': ('A squat porcelain petticoat pedestal carrying a caged amber '
                                'pilot lamp under a rust hood. Small static fixture.'),
            },
            'cable_shrine': {
                'display_name': 'Ossified Relay Shrine',
                'description': ('A freestanding iron rack of three ceramic relay spools '
                                'wrapped by sagging cable braids, with one amber pilot. '
                                'Utility sculpture, not an altar or a passage.'),
            },
            'directory_sign': {
                'display_name': 'Annunciator Directory',
                'description': ('A two-legged iron annunciator board with twelve amber relay '
                                'windows, twin porcelain horns, conduit and a blank nameplate. '
                                'Directory object; no text is drawn.'),
            },
        },
        'gameplay_notes': ('Cosmetic material set only; no electrical, combat or traversal '
                           'mechanics are claimed. Rust-red and charcoal fields are broken by '
                           'ivory porcelain and small amber indicators, leaving bright binding '
                           'rings distinct. Suggested as a whole-run or whole-tier identity.'),
    },
    {
        'id': 'after_hours_pavilion',
        'name': 'AFTER HOURS PAVILION',
        'description': ('A deserted transit and convention concourse: dusty plum plaster, '
                        'worn brass, pale geometric terrazzo and shuttered service windows. '
                        'Deeply folded baffles, unclaimed queue apparatus and deliberately '
                        'contradictory abstract pictogram wayfinding lead to an impossible '
                        'split-faced ticket and directory kiosk.'),
        'landmark': {
            'name': 'The Split-Faced Night Kiosk',
            'description': ('A two-panel kiosk facade. Panel 07 is a real directory face with '
                            'a route map, blank slot columns and a ticket recess. Panel 08 is '
                            'the same architecture inlaid solid in terrazzo with no opening; '
                            'its route line leaves the map and re-enters at the wrong height.'),
            'walls': [7, 8],
        },
        'props': {
            'service_lamp': {
                'display_name': 'Queue-Call Bollard',
                'description': ('A terrazzo-based brass bollard with a folded plum shade, a '
                                'cream underside and a call button plate. Small static fixture.'),
            },
            'cable_shrine': {
                'display_name': 'Unclaimed Queue Apparatus',
                'description': ('A single brass stanchion with a heavy base, a retractable '
                                'belt sagging in a loose decorative loop, and a blank '
                                'split-arrow tag. Freestanding queue hardware.'),
            },
            'directory_sign': {
                'display_name': 'Split-Faced Ticket Kiosk',
                'description': ('A two-legged kiosk whose left face has a working directory '
                                'and ticket slot while its right face is the same '
                                'architecture inlaid solid in terrazzo, including a pale '
                                'inlaid ticket stub. No door or opening is drawn.'),
            },
        },
        'gameplay_notes': ('Cosmetic material set only; no transit, queue or door mechanics '
                           'are claimed. Plum and slate fields with pale terrazzo and brass '
                           'keep bright binding-ring colours readable. Suggested as a '
                           'whole-run or whole-tier identity; the split-faced kiosk is a '
                           'deliberate impossible detail, not a hidden route.'),
    },
]

WALL_BUILDERS = {
    'drowned_records': DROWNED_WALLS,
    'switchyard_chapel': SWITCHYARD_WALLS,
    'after_hours_pavilion': PAVILION_WALLS,
}
FLAT_BUILDERS = {
    'drowned_records': DROWNED_FLATS,
    'switchyard_chapel': SWITCHYARD_FLATS,
    'after_hours_pavilion': PAVILION_FLATS,
}
PROP_BUILDERS = {
    'drowned_records': DROWNED_PROPS,
    'switchyard_chapel': SWITCHYARD_PROPS,
    'after_hours_pavilion': PAVILION_PROPS,
}


def environments_document(seed):
    sets = []
    for meta in SET_META:
        entry = {
            'id': meta['id'],
            'name': meta['name'],
            'description': meta['description'],
            'palette': dict(PALETTES[meta['id']]),
            'landmark': dict(meta['landmark']),
            'props': {slot: dict(meta['props'][slot]) for slot in PROP_SLOTS},
            'gameplay_notes': meta['gameplay_notes'],
            'wall_roles': list(WALL_ROLES),
            'flat_roles': list(FLAT_ROLES),
            'seam_behavior': {
                'walls_01_08': 'seamless both axes; exact opposite-edge equality',
                'flats_01_04': 'seamless both axes; exact opposite-edge equality',
                'props': 'RGBA cut-out, transparent margin, bottom anchored, not tiled',
            },
        }
        sets.append(entry)
    return {
        'format': FORMAT,
        'source_seed': int(seed),
        'license': 'GPL-2.0-or-later',
        'title': 'Null Run environment kits: Drowned Records, Switchyard Chapel, After Hours Pavilion',
        'paths': {
            'wall': 'art/{set_id}/walls/{index:02d}.png',
            'flat': 'art/{set_id}/flats/{index:02d}.png',
            'prop': 'art/{set_id}/props/{slot}.png',
            'kit_sheet': 'sheets/{set_id}-kit.png',
            'tiling_sheet': 'sheets/{set_id}-tiling.png',
        },
        'seam_behavior': {
            'walls': ('All eight wall tiles are RGB 128x128 and seamless on both axes. '
                      'Opposite edge rows and columns are exactly equal. Tiles 07 and 08 '
                      'are landmark accent panels: each wraps independently, and the pair '
                      'is an authored adjacent motif rather than a continuous split image.'),
            'flats': ('All four flats are RGB 64x64 and seamless on both axes. Opposite '
                      'edge rows and columns are exactly equal.'),
            'props': ('All props are RGBA 96x128 cut-outs with at least three transparent '
                      'pixels on every edge and feet/bases at the bottom. They are not '
                      'tiled and have no opaque rectangular backdrop.'),
        },
        'selection': {
            'notes': ('Suggestions only. Codex owns seeded selection and native '
                      'integration. Use one kit as a whole-run or whole-tier identity; do '
                      'not mix kits per room. Keep walls 07 and 08 together.'),
            'suggested_cycle': ['drowned_records', 'switchyard_chapel', 'after_hours_pavilion'],
            'suggested_seed_use': ('Derive the set from the run seed as a separate choice '
                                   'from map layout, so the same layout can be replayed '
                                   'with a different kit.'),
        },
        'floor_variation': {
            'notes': ('Metadata only; Codex implements any variation. Flats 01-04 are a '
                      'complete floor/ceiling set and should not be mixed with another kit.'),
            'rules': [
                'flats/01 is the primary floor.',
                'flats/02 is the utility or service floor for plant rooms, trenches and back-of-house.',
                'flats/03 is the ordinary ceiling.',
                'flats/04 is the lit or fixture ceiling; it is never a floor.',
                'Vary floors by room function, not by random per-tile substitution.',
            ],
        },
        'sets': sets,
    }


# -- sheets ------------------------------------------------------------------
def get_font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow
        return ImageFont.load_default()


SHEET_BG = (22, 24, 28)
SHEET_PANEL = (32, 34, 40)
SHEET_TEXT = (226, 222, 210)
SHEET_MUTED = (166, 164, 154)
SHEET_ACCENT = (214, 184, 120)


def scaled(im, factor):
    return im.resize((im.width * factor, im.height * factor), Image.Resampling.NEAREST)


def paste_scaled(sheet, im, x, y, factor):
    sheet.paste(scaled(im, factor), (x, y))


def centered(draw, x, y, text, font, fill=SHEET_TEXT):
    draw.text((x, y), text, font=font, fill=fill, anchor='mm')


def left_text(draw, x, y, text, font, fill=SHEET_TEXT):
    draw.text((x, y), text, font=font, fill=fill, anchor='la')


def wrap_text(text, width_chars):
    words, lines, line = text.split(), [], ''
    for word in words:
        if len(line) + len(word) + (1 if line else 0) > width_chars:
            lines.append(line)
            line = word
        else:
            line = word if not line else line + ' ' + word
    if line:
        lines.append(line)
    return lines


def checkerboard(w, h, cell=32):
    im = Image.new('RGB', (w, h), (52, 48, 56))
    d = ImageDraw.Draw(im)
    for y in range(0, h, cell):
        for x in range(0, w, cell):
            if (x // cell + y // cell) % 2:
                d.rectangle((x, y, min(w - 1, x + cell - 1), min(h - 1, y + cell - 1)),
                            fill=(68, 62, 72))
    return im


def compose_kit_sheet(set_id, walls, flats, props, meta, seed):
    width, height = 1180, 1530
    sheet = Image.new('RGB', (width, height), SHEET_BG)
    d = ImageDraw.Draw(sheet)
    f_title, f_sub, f_head = get_font(30), get_font(15), get_font(17)
    f_label, f_small = get_font(14), get_font(12)

    left_text(d, 40, 24, meta['name'], f_title, SHEET_TEXT)
    left_text(d, 40, 64, 'NULL RUN environment kit  |  ' + set_id + f'  |  seed {seed}',
              f_sub, SHEET_ACCENT)
    for i, line in enumerate(wrap_text(meta['description'], 122)[:3]):
        left_text(d, 40, 86 + i * 18, line, f_sub, SHEET_MUTED)

    # walls
    left_text(d, 40, 160, 'WALLS 01-08  -  128x128 RGB, shown at 2x nearest', f_head, SHEET_ACCENT)
    x0, y0 = 40, 188
    for i, wall in enumerate(walls):
        col, row = i % 4, i // 4
        x = x0 + col * 272
        y = y0 + row * 300
        sheet.paste(scaled(wall, 2), (x, y))
        d.rectangle((x - 1, y - 1, x + 255, y + 255), outline=(70, 74, 84))
        centered(d, x + 128, y + 272, f'{i + 1:02d}  {WALL_ROLES[i]}', f_label, SHEET_TEXT)

    # flats
    left_text(d, 40, 790, 'FLATS 01-04  -  64x64 RGB, shown at 3x nearest', f_head, SHEET_ACCENT)
    x0, y0 = 40, 818
    for i, flat in enumerate(flats):
        x = x0 + i * 208
        y = y0
        sheet.paste(scaled(flat, 3), (x, y))
        d.rectangle((x - 1, y - 1, x + 191, y + 191), outline=(70, 74, 84))
        centered(d, x + 96, y + 208, f'{i + 1:02d}  {FLAT_ROLES[i]}', f_label, SHEET_TEXT)

    # props over checkerboard
    left_text(d, 40, 1052, 'PROPS  -  96x128 RGBA, shown at 2x over mid-dark checkerboard',
              f_head, SHEET_ACCENT)
    x0, y0 = 40, 1080
    for i, slot in enumerate(PROP_SLOTS):
        x = x0 + i * 236
        board = checkerboard(208, 272)
        board.paste(scaled(props[slot], 2), (8, 8), scaled(props[slot], 2))
        sheet.paste(board, (x, y0))
        d.rectangle((x - 1, y0 - 1, x + 207, y0 + 271), outline=(70, 74, 84))
        centered(d, x + 104, y0 + 292, slot, f_label, SHEET_ACCENT)
        centered(d, x + 104, y0 + 310, meta['props'][slot]['display_name'], f_small, SHEET_TEXT)

    # palette
    left_text(d, 40, 1420, 'PALETTE  -  named hex values published in environments.json',
              f_head, SHEET_ACCENT)
    items = list(PALETTES[set_id].items())
    for i, (name, value) in enumerate(items):
        col, row = i % 5, i // 5
        x = 40 + col * 224
        y = 1448 + row * 24
        d.rectangle((x, y, x + 34, y + 16), fill=hx(value), outline=(10, 10, 12))
        left_text(d, x + 42, y + 2, f'{name} {value}', f_small, SHEET_MUTED)
    left_text(d, 40, 1510,
              'Static art. Nearest-neighbour preview. No filtering hides seams. '
              'This sheet is not native-renderer acceptance.', f_small, SHEET_MUTED)
    return sheet


def tiled2x2(tile):
    w, h = tile.size
    out = Image.new(tile.mode, (w * 2, h * 2))
    for y in range(2):
        for x in range(2):
            out.paste(tile, (x * w, y * h))
    return out


def compose_tiling_sheet(set_id, walls, flats, meta, seed):
    width, height = 1180, 2860
    sheet = Image.new('RGB', (width, height), SHEET_BG)
    d = ImageDraw.Draw(sheet)
    f_title, f_head, f_label, f_small = get_font(30), get_font(17), get_font(14), get_font(12)
    left_text(d, 40, 24, meta['name'] + ' - tiling proofs', f_title)
    left_text(d, 40, 64, f'seed {seed}  |  2x2 repeats, nearest-neighbour. No blur, no seam filtering. '
                         'Each base tile must wrap exactly on both axes.', f_small, SHEET_MUTED)

    left_text(d, 40, 104, 'BASE WALLS 01-06 - 2x2 at 2x (512x512 each)', f_head, SHEET_ACCENT)
    for i in range(6):
        col, row = i % 2, i // 2
        x = 64 + col * 540
        y = 170 + row * 572
        left_text(d, x, y - 22, f'WALL {i + 1:02d} - {WALL_ROLES[i]}', f_label, SHEET_TEXT)
        sheet.paste(scaled(tiled2x2(walls[i]), 2), (x, y))
        d.rectangle((x - 1, y - 1, x + 511, y + 511), outline=(70, 74, 84))

    left_text(d, 40, 1840, 'LANDMARK PAIR 07 | 08 - 2x2 arrangement at 2x (512x512)', f_head,
              SHEET_ACCENT)
    px, py = 64, 1880
    lhs = scaled(walls[6], 2)
    rhs = scaled(walls[7], 2)
    pair = Image.new('RGB', (512, 512))
    for yy in range(2):
        for xx in range(2):
            pair.paste(lhs if xx == 0 else rhs, (xx * 256, yy * 256))
    sheet.paste(pair, (px, py))
    d.rectangle((px - 1, py - 1, px + 511, py + 511), outline=(70, 74, 84))
    notes = [
        '07 and 08 each wrap independently on both axes.',
        'The pair is an authored adjacent motif, not a continuous split image.',
        'Tile boundaries are visible in this proof; no filtering is applied.',
        'No filtering is applied between tiles.',
    ]
    for i, line in enumerate(notes):
        left_text(d, 630, py + 40 + i * 24, line, f_small, SHEET_MUTED)

    left_text(d, 40, 2440, 'FLATS 01-04 - 2x2 at 2x (256x256 each)', f_head, SHEET_ACCENT)
    for i in range(4):
        x = 42 + i * 280
        y = 2480
        left_text(d, x, y - 22, f'FLAT {i + 1:02d} - {FLAT_ROLES[i]}', f_label, SHEET_TEXT)
        sheet.paste(scaled(tiled2x2(flats[i]), 2), (x, y))
        d.rectangle((x - 1, y - 1, x + 255, y + 255), outline=(70, 74, 84))

    left_text(d, 40, 2790,
              'Checks assert exact opposite-edge equality for walls 01-08 and flats 01-04. '
              'This sheet is a visual seam proof, not native-renderer acceptance.', f_small,
              SHEET_MUTED)
    return sheet


# -- assembly ----------------------------------------------------------------
def build_set(set_id, seed, set_index):
    walls = [fn(asset_seed(seed, set_index, 0, i))
             for i, fn in enumerate(WALL_BUILDERS[set_id])]
    flats = [fn(asset_seed(seed, set_index, 1, i))
             for i, fn in enumerate(FLAT_BUILDERS[set_id])]
    props = {slot: PROP_BUILDERS[set_id][slot](asset_seed(seed, set_index, 2, i))
             for i, slot in enumerate(PROP_SLOTS)}
    return walls, flats, props


def _save(im, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, format='PNG', compress_level=9)


def write_kit(out, seed=DEFAULT_SEED):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for set_index, meta in enumerate(SET_META):
        set_id = meta['id']
        walls, flats, props = build_set(set_id, seed, set_index)
        for i, wall in enumerate(walls, 1):
            _save(wall.convert('RGB'), out / 'art' / set_id / 'walls' / f'{i:02d}.png')
        for i, flat in enumerate(flats, 1):
            _save(flat.convert('RGB'), out / 'art' / set_id / 'flats' / f'{i:02d}.png')
        for slot in PROP_SLOTS:
            _save(props[slot].convert('RGBA'), out / 'art' / set_id / 'props' / f'{slot}.png')
        _save(compose_kit_sheet(set_id, walls, flats, props, meta, seed),
              out / 'sheets' / f'{set_id}-kit.png')
        _save(compose_tiling_sheet(set_id, walls, flats, meta, seed),
              out / 'sheets' / f'{set_id}-tiling.png')
    doc = environments_document(seed)
    (out / 'environments.json').write_text(json.dumps(doc, indent=2) + '\n', encoding='utf-8')
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description='Generate three Null Run environment kits.')
    parser.add_argument('--out', required=True, help='output directory')
    parser.add_argument('--seed', type=int, default=DEFAULT_SEED,
                        help=f'integer seed (default {DEFAULT_SEED})')
    args = parser.parse_args(argv)
    out = write_kit(args.out, args.seed)
    print(f'wrote 3 kits (45 art PNGs + 6 sheets) and environments.json to {out}')


if __name__ == '__main__':
    main()
