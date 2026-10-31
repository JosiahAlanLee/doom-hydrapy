# SPDX-License-Identifier: GPL-2.0-or-later
"""Deterministic bitmap art for the three tower environment kits.

Walls 128x128 RGB, flats 64x64 RGB, props 96x128 RGBA.  Everything is drawn
from geometric primitives and periodic fields with Pillow/NumPy.  No game
pixel, font, logo or texture is sampled.  Opposite edges are forced equal so
every wall and flat tiles exactly on both axes.
"""
from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import kit_common as K

WALL = 128
FLAT = 64
PROP_W, PROP_H = 96, 128
FLOOR_Y = 120


# -- deterministic texture helpers ------------------------------------------
def _field(w, h, seed, octaves=5, base_freq=2):
    """Periodic value field: integer-frequency sinusoids + wrapped fine grain."""
    rng = random.Random(seed)
    yy, xx = np.mgrid[0:h, 0:w]
    field = np.zeros((h, w), dtype=np.float64)
    for octave in range(octaves):
        kx = rng.randint(1, base_freq + octave * 2)
        ky = rng.randint(1, base_freq + octave * 2)
        phase = rng.uniform(0, math.tau)
        amp = 1.0 / (1.0 + octave * 0.85)
        field += amp * np.sin(math.tau * (kx * xx / w + ky * yy / h) + phase)
    nprng = np.random.default_rng(seed ^ 0x9E3779B9)
    fine = nprng.normal(0.0, 1.0, (h, w))
    fine = (fine + np.roll(fine, 1, 0) + np.roll(fine, -1, 0)
            + np.roll(fine, 1, 1) + np.roll(fine, -1, 1)) / 5.0
    field += fine * 0.55
    field -= field.mean()
    std = field.std()
    if std > 1e-9:
        field /= std
    return field


def textured(w, h, base, seed, tint=(10, 8, 6), octaves=5, gain=1.0, clip=True):
    field = _field(w, h, seed, octaves=octaves) * gain
    arr = np.array(base, dtype=np.float64)[None, None, :] + field[:, :, None] * np.array(tint)[None, None, :]
    if clip:
        arr = np.clip(arr, 0, 255)
    return Image.fromarray(arr.astype(np.uint8), 'RGB')


def tinted(w, h, base, seed, light, dark, gain=1.0):
    """Periodic two-tone material: positive field toward light, negative to dark."""
    f = _field(w, h, seed) * gain
    arr = np.array(base, dtype=np.float64)[None, None, :].repeat(h, 0).repeat(w, 1)
    pos = np.clip(f, 0, None)[:, :, None]
    neg = np.clip(-f, 0, None)[:, :, None]
    arr = arr * (1 - 0.28 * pos) + np.array(light, dtype=np.float64)[None, None, :] * (0.28 * pos)
    arr = arr * (1 - 0.24 * neg) + np.array(dark, dtype=np.float64)[None, None, :] * (0.24 * neg)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), 'RGB')


def wash_rect(im, box, color, alpha):
    layer = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rectangle(box, fill=tuple(color) + (int(alpha),))
    return Image.alpha_composite(im.convert('RGBA'), layer).convert('RGB')


def wash_poly(im, points, color, alpha):
    layer = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).polygon(points, fill=tuple(color) + (int(alpha),))
    return Image.alpha_composite(im.convert('RGBA'), layer).convert('RGB')


def wash_ellipse(im, box, color, alpha):
    layer = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse(box, fill=tuple(color) + (int(alpha),))
    return Image.alpha_composite(im.convert('RGBA'), layer).convert('RGB')


def bevel_rect(pen, box, fill, light, dark, depth=1):
    x0, y0, x1, y1 = box
    pen.rectangle(box, fill=fill)
    pen.line((x0, y0, x1, y0), fill=light, width=depth)
    pen.line((x0, y0, x0, y1), fill=light, width=depth)
    pen.line((x0, y1, x1, y1), fill=dark, width=depth)
    pen.line((x1, y0, x1, y1), fill=dark, width=depth)


def recess(pen, box, fill, dark, light, depth=1):
    x0, y0, x1, y1 = box
    pen.rectangle(box, fill=fill)
    pen.line((x0, y0, x1, y0), fill=dark, width=depth)
    pen.line((x0, y0, x0, y1), fill=dark, width=depth)
    pen.line((x0, y1, x1, y1), fill=light, width=depth)
    pen.line((x1, y0, x1, y1), fill=light, width=depth)


def bolt(pen, x, y, r, face, edge, shine=None):
    pen.ellipse((x - r, y - r, x + r, y + r), fill=face, outline=edge)
    if shine and r >= 1:
        pen.point((x - 1, y - 1), fill=shine)


def wall_frame(im, outer, inner, dark):
    pen = ImageDraw.Draw(im)
    x0, y0, x1, y1 = 0, 0, WALL - 1, WALL - 1
    pen.rectangle((x0, y0, x1, y1), outline=outer, width=2)
    pen.rectangle((2, 2, x1 - 2, y1 - 2), outline=dark, width=1)
    pen.line((3, 3, x1 - 3, 3), fill=inner, width=1)
    pen.line((3, 3, 3, y1 - 3), fill=inner, width=1)
    return im


def flat_frame(im, color, light=None):
    pen = ImageDraw.Draw(im)
    pen.rectangle((0, 0, FLAT - 1, FLAT - 1), outline=color, width=1)
    if light:
        pen.line((1, 1, FLAT - 2, 1), fill=light, width=1)
        pen.line((1, 1, 1, FLAT - 2), fill=light, width=1)
    return im


def scratches(pen, rng, color, count, box, length=(3, 12)):
    x0, y0, x1, y1 = box
    for _ in range(count):
        x = rng.randint(x0, max(x0, x1 - 2))
        y = rng.randint(y0, max(y0, y1 - 2))
        dx = rng.randint(*length)
        dy = rng.choice((-1, 0, 0, 1))
        pen.line((x, y, min(x1, x + dx), max(y0, min(y1, y + dy))), fill=color, width=1)


def chips(pen, rng, color, count, box, size=3):
    x0, y0, x1, y1 = box
    for _ in range(count):
        x = rng.randint(x0, x1 - size)
        y = rng.randint(y0, y1 - size)
        w = rng.randint(1, size)
        h = rng.randint(1, size)
        pen.polygon([(x, y), (x + w, y + 1), (x + w - 1, y + h), (x, y + h - 1)], fill=color)


def seam_fix(im):
    """Force exact opposite-edge equality; corners stay consistent."""
    a = np.array(im.convert('RGB'), dtype=np.uint8)
    a[:, -1, :] = a[:, 0, :]
    a[-1, :, :] = a[0, :, :]
    a[-1, -1, :] = a[0, 0, :]
    return Image.fromarray(a, 'RGB')


def bell_shape(pen, cx, top, width, height, body, light, dark, lip=None):
    """A readable cast-bell silhouette: crown, curved shoulder, waist, flared lip."""
    hw = width / 2.0
    profile = [
        (0.26, 0.00), (0.40, 0.07), (0.46, 0.15), (0.39, 0.23),
        (0.60, 0.34), (0.80, 0.45), (0.88, 0.54), (0.80, 0.62),
        (0.72, 0.68), (0.82, 0.78), (0.96, 0.88), (1.00, 0.95),
        (1.00, 0.99),
    ]
    left = [(cx - hw * f, top + height * y) for f, y in profile]
    right = [(cx + hw * f, top + height * y) for f, y in reversed(profile)]
    pts = left + right
    # crown loop sits above the shell
    pen.ellipse((cx - width * 0.09, top - height * 0.085,
                 cx + width * 0.09, top + height * 0.055),
                outline=dark, width=2)
    pen.ellipse((cx - width * 0.055, top - height * 0.065,
                 cx + width * 0.055, top + height * 0.035),
                fill=body, outline=light)
    pen.polygon(pts, fill=body, outline=dark)
    # shoulder highlight and waist shadow
    pen.line([left[3], left[5]], fill=light, width=2)
    pen.line([left[2], left[4]], fill=light, width=1)
    pen.line([right[3], right[6]], fill=dark, width=2)
    # bottom rim: an ellipse gives the mouth real thickness
    lip_y = top + height * 0.99
    pen.ellipse((cx - hw, lip_y - height * 0.045,
                 cx + hw, lip_y + height * 0.045),
                fill=dark if lip is None else lip, outline=dark)
    pen.ellipse((cx - hw * 0.82, lip_y - height * 0.028,
                 cx + hw * 0.82, lip_y + height * 0.028),
                fill=(18, 17, 16))
    # crown band
    pen.line((left[0][0], left[0][1] + 2, right[0][0], right[0][1] + 2), fill=dark, width=1)


# -- Ashbell Foundry walls ---------------------------------------------------
def wall_foundry_01(seed):
    sid = 'ashbell_foundry'
    soot, iron, iron_l = K.C(sid, 'soot'), K.C(sid, 'iron'), K.C(sid, 'iron_light')
    verd, verd_l = K.C(sid, 'verdigris'), K.C(sid, 'verdigris_light')
    bronze, bone = K.C(sid, 'bronze'), K.C(sid, 'bone')
    im = tinted(WALL, WALL, iron, seed, iron_l, soot, gain=0.9)
    for band in (0, 32, 64, 96):
        im = wash_rect(im, (4, band + 3, 123, band + 30), (30, 32, 36), 44)
        im = wash_rect(im, (4, band + 26, 123, band + 31), soot, 120)
    pen = ImageDraw.Draw(im)
    for band in (0, 32, 64, 96):
        pen.line((4, band + 3, 123, band + 3), fill=iron_l)
        pen.line((4, band + 30, 123, band + 30), fill=soot)
        for x in (18, 60, 102):
            for y in (band + 14, band + 23):
                bolt(pen, x, y, 2, bronze, soot, bone)
    rng = random.Random(seed + 11)
    # verdigris bleeding down from the plate seams
    for x, wdt in ((24, 5), (52, 3), (88, 7), (112, 3)):
        length = rng.randint(10, 22)
        im = wash_poly(im, [(x - wdt, 33), (x + wdt, 33), (x + wdt - 1, 33 + length),
                            (x - wdt + 1, 33 + length)], verd, 108)
    pen = ImageDraw.Draw(im)
    for x, wdt in ((24, 4), (52, 2), (88, 5), (112, 2)):
        pen.line((x, 33, x, 44), fill=verd_l)
    # chain scar and a hanging stub
    pen.line((44, 0, 44, 10), fill=soot, width=3)
    pen.ellipse((40, 8, 48, 16), outline=verd, width=2)
    pen.line((44, 15, 44, 22), fill=soot, width=2)
    scratches(pen, rng, (108, 104, 96), 13, (6, 6, 122, 120))
    chips(pen, rng, verd, 8, (8, 8, 120, 120), 3)
    chips(pen, rng, soot, 10, (8, 8, 120, 120), 4)
    wall_frame(im, soot, verd_l, soot)
    return seam_fix(im)


def wall_foundry_02(seed):
    sid = 'ashbell_foundry'
    soot, iron_l = K.C(sid, 'soot'), K.C(sid, 'iron_light')
    brick, bdark = K.C(sid, 'firebrick'), K.C(sid, 'brick_dark')
    bronze, bronze_l = K.C(sid, 'bronze'), K.C(sid, 'bronze_light')
    verd, verd_l = K.C(sid, 'verdigris'), K.C(sid, 'verdigris_light')
    ash, bone = K.C(sid, 'ash'), K.C(sid, 'bone')
    im = tinted(WALL, WALL, brick, seed, (208, 166, 140), bdark, gain=0.7)
    pen = ImageDraw.Draw(im)
    # staggered pale firebrick courses
    for row in range(8):
        y = row * 16
        offset = 0 if row % 2 == 0 else 16
        for col in range(-1, 9):
            x = col * 32 + offset
            fill = brick if (row + col) % 3 else (176, 116, 92)
            pen.rectangle((x + 1, y + 1, x + 31, y + 15), outline=bdark)
            pen.rectangle((x + 2, y + 2, x + 30, y + 14), fill=fill)
            pen.line((x + 3, y + 2, x + 29, y + 2), fill=(198, 150, 126))
    # soot cap
    im = wash_rect(im, (0, 0, 127, 10), soot, 190)
    # central arched niche
    im = wash_rect(im, (23, 40, 105, 118), soot, 240)
    pen = ImageDraw.Draw(im)
    pen.pieslice((23, 26, 105, 70), 180, 360, fill=soot, outline=soot)
    pen.arc((23, 26, 105, 70), 180, 360, fill=bronze, width=4)
    pen.line((23, 48, 23, 118), fill=bronze, width=4)
    pen.line((105, 48, 105, 118), fill=bronze, width=4)
    pen.line((27, 52, 27, 114), fill=(66, 40, 24), width=1)
    pen.line((101, 52, 101, 114), fill=bronze_l, width=1)
    # interior depth
    pen.rectangle((28, 52, 100, 114), fill=(18, 18, 20))
    for y in range(58, 112, 9):
        pen.line((31, y, 97, y), fill=(34, 30, 28))
    # small hanging relief bell inside
    pen.line((64, 54, 64, 66), fill=bronze, width=2)
    bell_shape(pen, 64, 64, 32, 40, bronze, bronze_l, verd, lip=verd_l)
    # nothing in the mouth
    pen.ellipse((56, 101, 72, 106), fill=(9, 9, 10))
    # niche keystone and bolts
    pen.polygon([(58, 30), (70, 30), (74, 40), (54, 40)], fill=iron_l, outline=soot)
    bolt(pen, 64, 35, 2, bronze, soot, bone)
    for y in (58, 90, 112):
        bolt(pen, 23, y, 2, verd, soot, verd_l)
        bolt(pen, 105, y, 2, verd, soot, verd_l)
    # soot streaks above and below
    rng = random.Random(seed + 21)
    for x in (30, 38, 88, 96):
        im = wash_poly(im, [(x, 26), (x + 3, 26), (x + 1, 22), (x + 4, 22),
                            (x + 2, 16)], soot, 110)
    pen = ImageDraw.Draw(im)
    scratches(pen, rng, ash, 9, (6, 6, 122, 120))
    chips(pen, rng, bdark, 7, (6, 6, 122, 120), 4)
    wall_frame(im, soot, bronze_l, soot)
    return seam_fix(im)


def wall_foundry_03(seed):
    sid = 'ashbell_foundry'
    soot, iron, iron_l = K.C(sid, 'soot'), K.C(sid, 'iron'), K.C(sid, 'iron_light')
    bronze, bronze_l = K.C(sid, 'bronze'), K.C(sid, 'bronze_light')
    verd, verd_l = K.C(sid, 'verdigris'), K.C(sid, 'verdigris_light')
    ash = K.C(sid, 'ash')
    im = tinted(WALL, WALL, soot, seed, (54, 50, 46), (10, 10, 12), gain=1.0)
    # diagonal braces behind the column
    pen = ImageDraw.Draw(im)
    pen.line((-4, 2, 44, 34), fill=(40, 39, 38), width=9)
    pen.line((132, 2, 84, 34), fill=(40, 39, 38), width=9)
    pen.line((-4, 126, 44, 94), fill=(40, 39, 38), width=9)
    pen.line((132, 126, 84, 94), fill=(40, 39, 38), width=9)
    pen.line((0, 0, 40, 30), fill=iron_l, width=1)
    pen.line((127, 0, 88, 30), fill=iron_l, width=1)
    # central riveted I-beam
    pen.rectangle((38, 0, 90, 127), fill=iron)
    pen.rectangle((34, 0, 44, 127), fill=iron_l)
    pen.rectangle((84, 0, 94, 127), fill=(26, 27, 30))
    pen.rectangle((44, 0, 84, 127), fill=(38, 39, 42))
    pen.line((44, 0, 44, 127), fill=soot)
    pen.line((84, 0, 84, 127), fill=iron_l)
    for y in range(6, 127, 12):
        bolt(pen, 39, y, 2, bronze, soot, bronze_l)
        bolt(pen, 89, y, 2, bronze, soot, bronze_l)
        pen.line((50, y + 4, 78, y + 4), fill=(44, 44, 46))
    # verdigris on the web and a chain hanging beside it
    im = wash_rect(im, (50, 36, 78, 86), verd, 34)
    pen = ImageDraw.Draw(im)
    for x in (54, 62, 72):
        pen.line((x, 40, x - 1, 74), fill=verd, width=1)
    for y in (28, 40, 52):
        pen.ellipse((98, y, 106, y + 10), outline=bronze, width=2)
    pen.line((102, 38, 102, 52), fill=soot, width=1)
    # flanges and base plates
    pen.rectangle((30, 0, 98, 6), fill=iron_l, outline=soot)
    pen.rectangle((30, 120, 98, 127), fill=iron_l, outline=soot)
    rng = random.Random(seed + 31)
    scratches(pen, rng, ash, 11, (6, 6, 122, 120))
    chips(pen, rng, bronze, 7, (8, 8, 120, 120), 3)
    wall_frame(im, soot, verd_l, soot)
    return seam_fix(im)


def wall_foundry_04(seed):
    sid = 'ashbell_foundry'
    soot, iron, iron_l = K.C(sid, 'soot'), K.C(sid, 'iron'), K.C(sid, 'iron_light')
    bronze, bronze_l = K.C(sid, 'bronze'), K.C(sid, 'bronze_light')
    verd, verd_l = K.C(sid, 'verdigris'), K.C(sid, 'verdigris_light')
    bone, ash = K.C(sid, 'bone'), K.C(sid, 'ash')
    im = tinted(WALL, WALL, iron, seed, (58, 56, 52), (14, 15, 18), gain=0.8)
    # main pipe run and service plate
    im = wash_rect(im, (6, 26, 122, 94), (24, 25, 28), 120)
    pen = ImageDraw.Draw(im)
    pen.rectangle((6, 36, 122, 52), fill=bronze, outline=soot)
    pen.line((6, 38, 122, 38), fill=bronze_l, width=2)
    pen.line((6, 50, 122, 50), fill=(80, 48, 22), width=2)
    for x in (20, 64, 108):
        pen.rectangle((x - 4, 33, x + 4, 55), fill=iron_l, outline=soot)
        bolt(pen, x, 40, 1, bronze_l, soot)
        bolt(pen, x, 48, 1, bronze_l, soot)
    # vertical drops with flanges
    for x in (30, 98):
        pen.rectangle((x - 4, 52, x + 4, 118), fill=(114, 76, 36), outline=soot)
        pen.line((x - 3, 54, x - 3, 116), fill=bronze_l)
        for y in (62, 78, 94, 110):
            pen.rectangle((x - 7, y, x + 7, y + 4), fill=iron_l, outline=soot)
    # large valve wheel
    cx, cy, r = 62, 74, 20
    pen.ellipse((cx - r, cy - r, cx + r, cy + r), outline=bronze, width=4)
    pen.ellipse((cx - r + 4, cy - r + 4, cx + r - 4, cy + r - 4), outline=(84, 50, 22), width=1)
    for k in range(8):
        a = math.tau * k / 8
        pen.line((cx + math.cos(a) * 4, cy + math.sin(a) * 4,
                  cx + math.cos(a) * 17, cy + math.sin(a) * 17), fill=bronze_l, width=2)
    pen.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill=iron, outline=soot)
    bolt(pen, cx, cy, 2, verd, soot, verd_l)
    # small wheel
    cx2, cy2, r2 = 22, 78, 12
    pen.ellipse((cx2 - r2, cy2 - r2, cx2 + r2, cy2 + r2), outline=verd, width=3)
    for k in range(6):
        a = math.tau * k / 6
        pen.line((cx2, cy2, cx2 + math.cos(a) * 11, cy2 + math.sin(a) * 11), fill=verd_l)
    # pressure dial
    pen.ellipse((94, 64, 116, 86), fill=(216, 205, 182), outline=iron_l, width=2)
    pen.ellipse((97, 67, 113, 83), fill=bone, outline=soot)
    pen.line((105, 75, 111, 70), fill=(150, 40, 30), width=1)
    for k in range(6):
        a = math.radians(20 + k * 24)
        pen.line((105 + math.cos(a) * 5, 75 + math.sin(a) * 5,
                  105 + math.cos(a) * 7, 75 + math.sin(a) * 7), fill=soot)
    # hanging chain pull
    for y in (8, 14, 20):
        pen.ellipse((86, y, 92, y + 7), outline=bronze, width=2)
    pen.line((89, 27, 89, 33), fill=soot, width=1)
    rng = random.Random(seed + 41)
    scratches(pen, rng, ash, 10, (6, 6, 122, 120))
    chips(pen, rng, verd, 6, (8, 8, 120, 120), 3)
    wall_frame(im, soot, bronze_l, soot)
    return seam_fix(im)


def wall_foundry_05(seed):
    sid = 'ashbell_foundry'
    soot, iron, iron_l = K.C(sid, 'soot'), K.C(sid, 'iron'), K.C(sid, 'iron_light')
    bronze, bronze_l = K.C(sid, 'bronze'), K.C(sid, 'bronze_light')
    verd, verd_l = K.C(sid, 'verdigris'), K.C(sid, 'verdigris_light')
    furn, furn_l = K.C(sid, 'furnace'), K.C(sid, 'furnace_light')
    bone = K.C(sid, 'bone')
    im = tinted(WALL, WALL, soot, seed, (54, 50, 46), (10, 10, 12), gain=1.0)
    pen = ImageDraw.Draw(im)
    # heavy riveted surround
    bevel_rect(pen, (8, 8, 120, 120), iron, iron_l, soot, 2)
    for x in range(14, 118, 13):
        bolt(pen, x, 12, 2, bronze, soot, bone)
        bolt(pen, x, 116, 2, bronze, soot, bone)
    for y in range(18, 112, 13):
        bolt(pen, 12, y, 2, bronze, soot, bone)
        bolt(pen, 116, y, 2, bronze, soot, bone)
    # hatch opening
    recess(pen, (20, 22, 108, 112), (20, 20, 22), soot, iron_l, 2)
    # warm interior / louvres
    pen.rectangle((24, 26, 104, 108), fill=(50, 24, 14))
    for i, y in enumerate(range(30, 106, 11)):
        glow = furn_l if 50 < y < 88 else furn
        im = wash_rect(im, (26, y, 102, y + 7), glow, 150 if 46 < y < 92 else 90)
    pen = ImageDraw.Draw(im)
    for i, y in enumerate(range(29, 108, 11)):
        pts = [(24, y), (104, y), (104, y + 5), (24, y + 5)]
        if i == 4:  # one bent louvre
            pts = [(24, y), (104, y + 1), (104, y + 7), (78, y + 9), (24, y + 5)]
        pen.polygon(pts, fill=(34, 33, 34), outline=(12, 12, 13))
        pen.line((28, y + 1, 100, y + 1), fill=(74, 72, 70))
    # central locking bar and handle
    pen.rectangle((60, 22, 68, 112), fill=iron, outline=soot)
    pen.line((62, 24, 62, 110), fill=iron_l)
    pen.rectangle((52, 62, 76, 70), fill=iron_l, outline=soot)
    pen.ellipse((68, 57, 84, 73), outline=bronze, width=3)
    bolt(pen, 76, 65, 2, verd, soot, verd_l)
    # heat cracks around the mouth
    rng = random.Random(seed + 51)
    for x0, y0 in ((20, 30), (108, 44), (18, 94)):
        pen.line((x0, y0, x0 + rng.randint(-5, 5), y0 + rng.randint(8, 18)), fill=soot)
    chips(pen, rng, verd, 8, (8, 8, 120, 120), 3)
    wall_frame(im, soot, verd_l, soot)
    return seam_fix(im)


def wall_foundry_06(seed):
    sid = 'ashbell_foundry'
    soot, iron, iron_l = K.C(sid, 'soot'), K.C(sid, 'iron'), K.C(sid, 'iron_light')
    bronze, bronze_l = K.C(sid, 'bronze'), K.C(sid, 'bronze_light')
    verd, verd_l = K.C(sid, 'verdigris'), K.C(sid, 'verdigris_light')
    bone, ash = K.C(sid, 'bone'), K.C(sid, 'ash')
    im = tinted(WALL, WALL, iron, seed, (54, 52, 48), (12, 13, 16), gain=0.7)
    # worn diagonal hazard band, kept inside the frame
    band = Image.new('RGBA', (WALL, WALL), (0, 0, 0, 0))
    bd = ImageDraw.Draw(band)
    bd.polygon([(4, 86), (124, 66), (124, 94), (4, 114)], fill=soot + (255,))
    im = Image.alpha_composite(im.convert('RGBA'), band).convert('RGB')
    pen = ImageDraw.Draw(im)
    for i in range(-2, 12):
        x = i * 14
        pen.polygon([(x, 112), (x + 14, 86), (x + 21, 86), (x + 7, 112)],
                    fill=bronze if i % 2 else (196, 154, 78))
    pen.line((4, 86, 124, 66), fill=(44, 34, 22))
    pen.line((4, 114, 124, 94), fill=bone)
    # painted bell mark
    bell_shape(pen, 64, 18, 58, 58, verd, verd_l, soot, lip=verd_l)
    pen.line((64, 12, 64, 18), fill=bronze, width=2)
    # arrow pointing up through the bell
    pen.polygon([(64, 80), (52, 92), (60, 92), (60, 100), (68, 100), (68, 92), (76, 92)],
                fill=bronze_l, outline=soot)
    rng = random.Random(seed + 61)
    for _ in range(24):  # stencil wear
        x, y = rng.randint(8, 118), rng.randint(72, 110)
        pen.point((x, y), fill=iron_l)
    scratches(pen, rng, ash, 9, (6, 6, 122, 120))
    chips(pen, rng, soot, 8, (6, 6, 122, 120), 4)
    wall_frame(im, soot, verd_l, soot)
    return seam_fix(im)


def wall_foundry_07(seed):
    sid = 'ashbell_foundry'
    soot, iron, iron_l = K.C(sid, 'soot'), K.C(sid, 'iron'), K.C(sid, 'iron_light')
    bronze, bronze_l = K.C(sid, 'bronze'), K.C(sid, 'bronze_light')
    verd, verd_l = K.C(sid, 'verdigris'), K.C(sid, 'verdigris_light')
    furn, furn_l = K.C(sid, 'furnace'), K.C(sid, 'furnace_light')
    bone = K.C(sid, 'bone')
    im = tinted(WALL, WALL, (24, 25, 27), seed, (58, 52, 46), (8, 9, 11), gain=1.0)
    # furnace halo behind the bell
    for r, a in ((58, 30), (48, 34), (38, 38)):
        im = wash_ellipse(im, (64 - r, 64 - r, 64 + r, 64 + r), furn, a)
    im = wash_ellipse(im, (34, 40, 94, 96), furn_l, 20)
    pen = ImageDraw.Draw(im)
    # chain rising out of frame
    for y in (0, 8, 16, 24):
        pen.ellipse((58, y, 70, y + 10), outline=bronze, width=3)
        pen.line((64, y + 9, 64, y + 12), fill=soot, width=1)
    # crown gimbal
    pen.ellipse((48, 26, 80, 44), outline=iron_l, width=3)
    pen.ellipse((52, 30, 76, 40), outline=bronze, width=2)
    # the ninth bell
    bell_shape(pen, 64, 38, 76, 76, bronze, bronze_l, (58, 36, 18), lip=verd)
    # patina patches
    im = wash_poly(im, [(38, 72), (50, 66), (58, 84), (42, 90)], verd, 90)
    im = wash_poly(im, [(76, 62), (90, 74), (86, 94), (72, 88)], verd, 70)
    pen = ImageDraw.Draw(im)
    # cast seam and a deliberate crack
    pen.line((64, 52, 64, 108), fill=(76, 46, 20), width=1)
    pen.line((64, 82, 56, 94, 62, 100, 54, 108), fill=(28, 20, 14), width=2)
    # roman nine, inlaid
    pen.line((58, 66, 58, 76), fill=verd_l, width=2)
    pen.line((66, 66, 72, 76), fill=verd_l, width=2)
    pen.line((72, 66, 66, 76), fill=verd_l, width=2)
    # clapper glimpsed inside the lip
    pen.ellipse((60, 108, 68, 116), fill=iron, outline=soot)
    # soot and ash on the lower shoulders
    rng = random.Random(seed + 71)
    for _ in range(16):
        x, y = rng.randint(34, 92), rng.randint(50, 106)
        if abs(x - 64) < 34:
            pen.point((x, y), fill=(60, 55, 48))
    bolt(pen, 44, 58, 2, verd, soot, verd_l)
    bolt(pen, 84, 58, 2, verd, soot, verd_l)
    scratches(pen, rng, bone, 6, (8, 8, 120, 120))
    wall_frame(im, soot, bronze_l, soot)
    return seam_fix(im)


def wall_foundry_08(seed):
    sid = 'ashbell_foundry'
    soot, iron, iron_l = K.C(sid, 'soot'), K.C(sid, 'iron'), K.C(sid, 'iron_light')
    bronze, bronze_l = K.C(sid, 'bronze'), K.C(sid, 'bronze_light')
    verd, verd_l = K.C(sid, 'verdigris'), K.C(sid, 'verdigris_light')
    furn, furn_l = K.C(sid, 'furnace'), K.C(sid, 'furnace_light')
    bone = K.C(sid, 'bone')
    im = tinted(WALL, WALL, soot, seed, (44, 42, 40), (8, 9, 11), gain=1.0)
    pen = ImageDraw.Draw(im)
    # shaft recess
    recess(pen, (26, 4, 102, 120), (10, 11, 13), soot, iron_l, 2)
    for y in range(12, 112, 10):
        pen.line((30, y, 98, y), fill=(16, 18, 20))
    # lift chains in the dark
    for x in (38, 90):
        pen.line((x, 8, x, 118), fill=(52, 44, 32), width=1)
    # cage
    pen.rectangle((32, 30, 96, 112), fill=(18, 18, 19), outline=bronze, width=3)
    pen.rectangle((36, 34, 92, 44), fill=iron, outline=soot)
    for x in (40, 52, 64, 76, 88):
        pen.line((x, 42, x, 108), fill=bronze, width=2)
        pen.line((x + 1, 42, x + 1, 108), fill=(124, 82, 36), width=1)
    pen.rectangle((34, 104, 94, 112), fill=iron_l, outline=soot)
    pen.line((36, 46, 92, 104), fill=(92, 60, 28))
    pen.line((92, 46, 36, 104), fill=(92, 60, 28))
    # cage lamp
    pen.rectangle((56, 34, 72, 40), fill=iron, outline=soot)
    pen.ellipse((58, 39, 70, 47), fill=furn, outline=furn_l)
    im = wash_ellipse(im, (50, 44, 78, 60), furn_l, 45)
    pen = ImageDraw.Draw(im)
    # counterweight and chain on the left
    pen.rectangle((10, 42, 24, 84), fill=iron_l, outline=soot)
    for y in (48, 58, 68, 78):
        pen.line((11, y, 23, y), fill=(72, 70, 66))
    pen.line((17, 0, 17, 42), fill=bronze, width=3)
    bolt(pen, 17, 86, 2, verd, soot, verd_l)
    # landing threshold and warning edge
    pen.rectangle((4, 112, 124, 120), fill=iron, outline=soot)
    for x in range(6, 124, 12):
        pen.polygon([(x, 118), (x + 6, 112), (x + 9, 112), (x + 3, 118)], fill=bronze)
    # verdigris and heat wear
    im = wash_rect(im, (32, 30, 96, 44), verd, 26)
    rng = random.Random(seed + 81)
    scratches(pen, rng, bone, 6, (8, 8, 120, 120))
    chips(pen, rng, verd, 7, (8, 8, 120, 120), 3)
    wall_frame(im, soot, bronze_l, soot)
    return seam_fix(im)


FOUNDRY_WALLS = (wall_foundry_01, wall_foundry_02, wall_foundry_03, wall_foundry_04,
                 wall_foundry_05, wall_foundry_06, wall_foundry_07, wall_foundry_08)


def root_branch(pen, x, y, angle, length, width, color, rng, depth=2):
    x2 = x + math.cos(angle) * length
    y2 = y + math.sin(angle) * length
    pen.line((x, y, x2, y2), fill=color, width=max(1, int(width)))
    if depth <= 0:
        return
    for _ in range(rng.randint(1, 2)):
        na = angle + rng.uniform(-0.75, 0.75)
        root_branch(pen, x2, y2, na, length * rng.uniform(0.45, 0.7),
                    max(1, width * 0.55), color, rng, depth - 1)


# -- Boneglass Conservatory walls -------------------------------------------
def wall_conservatory_01(seed):
    sid = 'boneglass_conservatory'
    bone, chalk, pale = K.C(sid, 'bone'), K.C(sid, 'chalk'), K.C(sid, 'pale')
    lichen, moss, peat = K.C(sid, 'lichen'), K.C(sid, 'moss'), K.C(sid, 'peat')
    root, root_l = K.C(sid, 'root'), K.C(sid, 'root_light')
    wet = K.C(sid, 'wet')
    im = tinted(WALL, WALL, bone, seed, pale, chalk, gain=0.55)
    pen = ImageDraw.Draw(im)
    # fluted ceramic nursery tiles
    for x in range(0, WALL, 16):
        pen.line((x + 1, 0, x + 1, 127), fill=chalk)
        pen.line((x + 2, 0, x + 2, 127), fill=(190, 185, 170))
        pen.line((x + 12, 0, x + 12, 127), fill=(206, 201, 187))
        pen.line((x + 13, 0, x + 13, 127), fill=(244, 240, 226))
    for y in (0, 32, 64, 96):
        pen.line((0, y, 127, y), fill=(176, 170, 154))
        pen.line((0, y + 1, 127, y + 1), fill=(238, 233, 219))
        pen.line((0, y + 2, 127, y + 2), fill=(198, 192, 176))
    # damp and moss creeping up from the floor
    im = wash_rect(im, (0, 96, 127, 127), wet, 34)
    im = wash_rect(im, (0, 110, 127, 127), moss, 48)
    pen = ImageDraw.Draw(im)
    rng = random.Random(seed + 101)
    for x in (14, 40, 76, 108):
        root_branch(pen, x, 128, -math.pi / 2 + rng.uniform(-0.3, 0.3),
                    rng.randint(12, 26), 2, root, rng, 2)
    # a few upward root veins from seams
    for x in (30, 94):
        pen.line((x, 64, x + 2, 50, x - 3, 38), fill=(148, 136, 116), width=1)
    # chips and limescale
    for _ in range(18):
        x, y = rng.randint(8, 118), rng.randint(8, 118)
        pen.line((x, y, x + rng.randint(1, 4), y + rng.randint(1, 3)),
                 fill=(246, 242, 229) if rng.random() < 0.5 else (170, 164, 148))
    scratches(pen, rng, (150, 156, 140), 8, (6, 6, 122, 120))
    wall_frame(im, (52, 48, 42), pale, (96, 92, 82))
    return seam_fix(im)


def wall_conservatory_02(seed):
    sid = 'boneglass_conservatory'
    bone, chalk, pale = K.C(sid, 'bone'), K.C(sid, 'chalk'), K.C(sid, 'pale')
    lichen, moss, peat = K.C(sid, 'lichen'), K.C(sid, 'moss'), K.C(sid, 'peat')
    root, root_l = K.C(sid, 'root'), K.C(sid, 'root_light')
    wet, fungus, glow = K.C(sid, 'wet'), K.C(sid, 'fungus'), K.C(sid, 'glow')
    tin = K.C(sid, 'tin')
    im = tinted(WALL, WALL, chalk, seed, pale, (184, 179, 164), gain=0.7)
    pen = ImageDraw.Draw(im)
    # tiled surround
    for x in range(0, WALL, 24):
        pen.line((x, 0, x, 127), fill=(182, 176, 161))
    for y in (16, 48, 80, 112):
        pen.line((0, y, 127, y), fill=(184, 178, 163))
    # recessed growth chamber
    bevel_rect(pen, (16, 16, 112, 116), bone, pale, (150, 145, 132), 2)
    recess(pen, (22, 22, 106, 110), peat, (78, 72, 62), pale, 2)
    # deep soil bed with an organic surface, not a floating blob
    pen.polygon([(24, 110), (24, 94), (34, 88), (44, 92), (54, 86), (66, 90),
                 (78, 84), (90, 90), (104, 86), (104, 110)], fill=(31, 27, 22))
    pen.line((26, 94, 36, 90, 46, 94, 58, 88, 70, 92, 82, 86, 94, 92, 102, 88),
             fill=(58, 49, 38), width=1)
    for x in (30, 48, 72, 96):
        root_branch(pen, x, 108, -math.pi / 2 + random.Random(seed + x).uniform(-0.5, 0.5),
                    8, 1, (74, 62, 46), random.Random(seed + 950 + x), 1)
    sprout_x = (42, 64, 86)
    for i, x in enumerate(sprout_x):
        h = (36, 44, 32)[i]
        top = 84 - h
        pen.line((x, 90, x + (i - 1) * 2, top), fill=(198, 206, 178), width=2)
        pen.ellipse((x - 5, top - 8, x + 5, top + 2), fill=fungus, outline=lichen)
        pen.ellipse((x - 2, top - 5, x + 2, top - 1), fill=glow)
        pen.line((x, top + 2, x - 8, top + 10), fill=lichen, width=1)
        pen.line((x, top + 4, x + 9, top + 12), fill=lichen, width=1)
    # cloudy glass and reflection streaks
    rng = random.Random(seed + 102)
    im = wash_rect(im, (24, 24, 104, 108), (170, 194, 184), 20)
    pen = ImageDraw.Draw(im)
    pen.line((28, 102, 62, 28), fill=(196, 211, 200))
    pen.line((34, 104, 68, 30), fill=(166, 186, 174))
    pen.line((78, 104, 100, 44), fill=(202, 216, 205))
    for _ in range(24):
        x, y = rng.randint(28, 100), rng.randint(28, 100)
        pen.point((x, y), fill=(218, 228, 216))
    # copper-green latch and frame bolts
    pen.rectangle((98, 58, 105, 78), fill=(86, 120, 104), outline=(40, 60, 50))
    pen.line((100, 62, 103, 74), fill=(152, 184, 160))
    bolt(pen, 24, 26, 2, tin, (64, 60, 50))
    bolt(pen, 104, 26, 2, tin, (64, 60, 50))
    bolt(pen, 24, 106, 2, tin, (64, 60, 50))
    rng = random.Random(seed + 102)
    scratches(pen, rng, (232, 228, 212), 8, (6, 6, 122, 120))
    chips(pen, rng, (154, 148, 132), 6, (6, 6, 122, 120), 4)
    wall_frame(im, (56, 52, 44), pale, (104, 98, 86))
    return seam_fix(im)


def wall_conservatory_03(seed):
    sid = 'boneglass_conservatory'
    bone, chalk, pale = K.C(sid, 'bone'), K.C(sid, 'chalk'), K.C(sid, 'pale')
    lichen, moss, peat = K.C(sid, 'lichen'), K.C(sid, 'moss'), K.C(sid, 'peat')
    root, root_l = K.C(sid, 'root'), K.C(sid, 'root_light')
    wet, bruise = K.C(sid, 'wet'), K.C(sid, 'bruise')
    tin = K.C(sid, 'tin')
    im = tinted(WALL, WALL, chalk, seed, (226, 221, 206), (156, 150, 136), gain=0.7)
    pen = ImageDraw.Draw(im)
    # wavy pale tree trunk as a structural column
    left = []
    right = []
    for y in range(0, 128, 4):
        w = 18 + 4 * math.sin(y / 13.0) + (3 if y > 92 else 0)
        left.append((64 - w, y))
        right.append((64 + w + 2 * math.sin(y / 9.0 + 1.2), y))
    pen.polygon(left + list(reversed(right)), fill=bone, outline=(112, 104, 90))
    pen.line(left, fill=pale, width=2)
    pen.line(right, fill=(132, 124, 108), width=2)
    for y in range(8, 124, 9):
        x = 64 + int(8 * math.sin(y / 11.0))
        pen.line((x - 8, y, x + 9, y + 2), fill=(190, 184, 168), width=1)
        pen.line((x - 3, y + 3, x + 12, y + 5), fill=(214, 209, 194), width=1)
    # dark hollow knot
    pen.ellipse((54, 44, 76, 66), fill=peat, outline=(114, 104, 88))
    pen.ellipse((57, 47, 73, 63), fill=(12, 11, 10))
    pen.arc((54, 44, 76, 66), 200, 340, fill=moss, width=2)
    # roots leaving the trunk
    rng = random.Random(seed + 103)
    for i, y in enumerate((16, 32, 88, 108)):
        side = -1 if i % 2 else 1
        root_branch(pen, 64 + side * 16, y, (0 if side > 0 else math.pi) + rng.uniform(-0.5, 0.5),
                    rng.randint(18, 34), 2, root, rng, 2)
    # metal root cage band
    pen.rectangle((38, 72, 92, 82), fill=tin, outline=(52, 56, 52))
    pen.line((38, 74, 92, 74), fill=(160, 170, 160))
    pen.line((38, 80, 92, 80), fill=(54, 58, 54))
    for x in (42, 54, 76, 88):
        bolt(pen, x, 77, 2, (96, 110, 98), (42, 46, 42))
    # moss at the base
    im = wash_rect(im, (0, 106, 127, 127), moss, 54)
    pen = ImageDraw.Draw(im)
    for _ in range(14):
        x, y = rng.randint(8, 118), rng.randint(108, 122)
        pen.ellipse((x, y, x + rng.randint(3, 9), y + rng.randint(2, 5)), fill=lichen)
    chips(pen, rng, (166, 160, 144), 8, (8, 8, 120, 120), 4)
    wall_frame(im, (58, 54, 46), pale, (108, 102, 90))
    return seam_fix(im)


def wall_conservatory_04(seed):
    sid = 'boneglass_conservatory'
    bone, chalk, pale = K.C(sid, 'bone'), K.C(sid, 'chalk'), K.C(sid, 'pale')
    lichen, moss, peat = K.C(sid, 'lichen'), K.C(sid, 'moss'), K.C(sid, 'peat')
    root, root_l = K.C(sid, 'root'), K.C(sid, 'root_light')
    wet, tin = K.C(sid, 'wet'), K.C(sid, 'tin')
    im = tinted(WALL, WALL, bone, seed, (230, 225, 210), (168, 162, 146), gain=0.65)
    pen = ImageDraw.Draw(im)
    # verdigris watering manifold
    pen.rectangle((6, 32, 122, 46), fill=(78, 114, 98), outline=(34, 54, 46))
    pen.line((6, 34, 122, 34), fill=(146, 180, 156))
    pen.line((6, 44, 122, 44), fill=(42, 66, 54))
    for x in (18, 64, 110):
        pen.rectangle((x - 5, 29, x + 5, 49), fill=(92, 124, 104), outline=(38, 58, 48))
        bolt(pen, x, 34, 1, (178, 204, 176), (38, 58, 48))
        bolt(pen, x, 44, 1, (178, 204, 176), (38, 58, 48))
    # three nozzles with roses
    for x in (30, 64, 98):
        pen.rectangle((x - 3, 46, x + 3, 64), fill=(72, 104, 90), outline=(34, 54, 46))
        pen.line((x - 2, 48, x - 2, 62), fill=(146, 180, 156))
        pen.ellipse((x - 9, 62, x + 9, 70), fill=(88, 122, 100), outline=(36, 56, 46))
        for k in range(-2, 3):
            pen.point((x + k * 3, 67), fill=(26, 40, 34))
        for dy in (6, 12, 18):
            pen.line((x, 70 + dy, x, 72 + dy), fill=(96, 140, 124))
    # tap wheel and pressure bulb
    pen.ellipse((10, 60, 34, 84), outline=(74, 108, 92), width=3)
    for k in range(6):
        a = math.tau * k / 6
        pen.line((22, 72, 22 + math.cos(a) * 11, 72 + math.sin(a) * 11), fill=(130, 164, 140))
    pen.ellipse((18, 68, 26, 76), fill=(48, 70, 58), outline=(24, 38, 32))
    pen.ellipse((104, 58, 120, 80), fill=(176, 188, 164), outline=(60, 76, 62))
    pen.line((112, 68, 112, 76), fill=(86, 104, 86))
    # coiled hose at the base
    for r in (18, 15, 12):
        pen.arc((54 - r, 88 - r // 2, 54 + r, 88 + r), 190, 520, fill=(70, 98, 84), width=2)
    # drip stains and damp
    im = wash_rect(im, (20, 66, 80, 127), wet, 26)
    pen = ImageDraw.Draw(im)
    rng = random.Random(seed + 104)
    for x in (30, 64, 98):
        for _ in range(3):
            y = rng.randint(72, 112)
            pen.line((x + rng.randint(-2, 2), y, x + rng.randint(-3, 3), y + rng.randint(4, 12)),
                     fill=(104, 138, 118))
    root_branch(pen, 118, 76, math.pi * 0.8, 18, 2, root, rng, 2)
    for _ in range(10):
        x, y = rng.randint(10, 118), rng.randint(92, 122)
        pen.ellipse((x, y, x + 3, y + 2), fill=lichen)
    scratches(pen, rng, (226, 222, 208), 7, (6, 6, 122, 120))
    wall_frame(im, (58, 54, 46), pale, (110, 104, 92))
    return seam_fix(im)


def wall_conservatory_05(seed):
    sid = 'boneglass_conservatory'
    bone, chalk, pale = K.C(sid, 'bone'), K.C(sid, 'chalk'), K.C(sid, 'pale')
    lichen, moss, peat = K.C(sid, 'lichen'), K.C(sid, 'moss'), K.C(sid, 'peat')
    root, root_l = K.C(sid, 'root'), K.C(sid, 'root_light')
    wet, tin, fungus = K.C(sid, 'wet'), K.C(sid, 'tin'), K.C(sid, 'fungus')
    iron = K.C(sid, 'iron')
    im = tinted(WALL, WALL, chalk, seed, (218, 213, 198), (148, 142, 128), gain=0.8)
    pen = ImageDraw.Draw(im)
    # arched glasshouse window
    pen.pieslice((10, 8, 118, 76), 180, 360, fill=bone, outline=(84, 78, 66))
    pen.rectangle((10, 42, 118, 120), fill=bone, outline=(84, 78, 66))
    pen.pieslice((19, 17, 109, 72), 180, 360, fill=(28, 38, 36), outline=iron)
    pen.rectangle((19, 44, 109, 111), fill=(28, 38, 36), outline=iron)
    # glazing bars
    for x in (41, 64, 87):
        pen.line((x, 34, x, 111), fill=(96, 88, 72), width=2)
    for y in (48, 70, 92):
        pen.line((21, y, 107, y), fill=(96, 88, 72), width=2)
    pen.arc((19, 17, 109, 72), 180, 360, fill=(104, 96, 80), width=2)
    # pale skeletal trees behind the glass
    rng = random.Random(seed + 105)
    for base_x, height in ((34, 62), (74, 54), (94, 40)):
        pen.line((base_x, 108, base_x + 2, 108 - height), fill=(184, 190, 168), width=2)
        for k in range(3):
            y = 108 - height * (0.35 + 0.18 * k)
            root_branch(pen, base_x, y, -math.pi / 2 + rng.uniform(-1.0, 1.0),
                        rng.randint(8, 16), 1, (184, 190, 168), rng, 1)
    # condensation streaks and a crack
    for x in (26, 32, 50, 58, 78, 100):
        pen.line((x, 30, x + rng.randint(-2, 2), rng.randint(84, 109)), fill=(104, 130, 120))
    for _ in range(30):
        x, y = rng.randint(23, 105), rng.randint(22, 106)
        pen.point((x, y), fill=(166, 190, 174))
    pen.line((70, 52, 78, 64, 74, 76, 86, 88), fill=(196, 208, 192))
    pen.line((78, 64, 88, 60), fill=(196, 208, 192))
    # pale sill and a root through the frame
    pen.rectangle((8, 110, 120, 118), fill=bone, outline=(88, 82, 70))
    pen.line((8, 110, 120, 110), fill=pale)
    root_branch(pen, 116, 84, math.pi * 0.9, 22, 2, root, rng, 2)
    # moss on the sill
    im = wash_rect(im, (10, 112, 118, 120), moss, 44)
    pen = ImageDraw.Draw(im)
    for _ in range(12):
        x, y = rng.randint(10, 114), rng.randint(112, 119)
        pen.ellipse((x, y, x + 4, y + 2), fill=lichen)
    wall_frame(im, (54, 50, 42), pale, (104, 98, 86))
    return seam_fix(im)


def wall_conservatory_06(seed):
    sid = 'boneglass_conservatory'
    bone, chalk, pale = K.C(sid, 'bone'), K.C(sid, 'chalk'), K.C(sid, 'pale')
    lichen, moss, peat = K.C(sid, 'lichen'), K.C(sid, 'moss'), K.C(sid, 'peat')
    root, root_l = K.C(sid, 'root'), K.C(sid, 'root_light')
    bruise, tin = K.C(sid, 'bruise'), K.C(sid, 'tin')
    im = tinted(WALL, WALL, bone, seed, pale, (170, 164, 148), gain=0.6)
    pen = ImageDraw.Draw(im)
    # root-knot glyph
    pen.ellipse((14, 30, 48, 64), outline=moss, width=3)
    pen.ellipse((22, 38, 40, 56), outline=(76, 94, 72), width=2)
    for k in range(5):
        a = math.tau * k / 5 - 0.3
        root_branch(pen, 31 + math.cos(a) * 15, 47 + math.sin(a) * 15,
                    a, 18, 2, moss, random.Random(seed + 300 + k), 1)
    # large rough arrow, painted with a dry brush
    pts = [(64, 20), (98, 52), (82, 52), (82, 74), (70, 74), (70, 52), (50, 52)]
    pen.polygon(pts, fill=moss, outline=(42, 54, 40))
    pen.line((64, 23, 94, 51), fill=lichen, width=2)
    pen.line((56, 56, 78, 74), fill=(52, 66, 50), width=1)
    # hanging plant labels on strings
    for i, (x, y, w) in enumerate(((84, 12, 18), (98, 26, 16), (74, 40, 14))):
        pen.line((x + w // 2, 0, x + w // 2, y), fill=(86, 74, 58))
        pen.rectangle((x, y, x + w, y + 10), fill=bone, outline=(112, 102, 84))
        pen.line((x + 2, y + 3, x + w - 3, y + 3), fill=(124, 112, 92))
        pen.line((x + 2, y + 6, x + w - 4, y + 6), fill=(124, 112, 92))
    # painted dots and wear
    rng = random.Random(seed + 106)
    for _ in range(16):
        x, y = rng.randint(10, 118), rng.randint(80, 118)
        pen.ellipse((x, y, x + 2, y + 2), fill=(126, 138, 112))
    for _ in range(22):
        x, y = rng.randint(8, 118), rng.randint(8, 118)
        pen.point((x, y), fill=(238, 233, 218))
    # damp stain and a root at the floor
    im = wash_rect(im, (0, 108, 127, 127), (96, 110, 88), 36)
    pen = ImageDraw.Draw(im)
    root_branch(pen, 8, 122, -0.4, 26, 2, root, rng, 2)
    root_branch(pen, 120, 120, math.pi + 0.3, 20, 1, root_l, rng, 2)
    scratches(pen, rng, (226, 222, 208), 9, (6, 6, 122, 120))
    wall_frame(im, (56, 52, 44), pale, (106, 100, 88))
    return seam_fix(im)


def wall_conservatory_07(seed):
    sid = 'boneglass_conservatory'
    bone, chalk, pale = K.C(sid, 'bone'), K.C(sid, 'chalk'), K.C(sid, 'pale')
    lichen, moss, peat = K.C(sid, 'lichen'), K.C(sid, 'moss'), K.C(sid, 'peat')
    root, root_l = K.C(sid, 'root'), K.C(sid, 'root_light')
    wet, fungus, glow = K.C(sid, 'wet'), K.C(sid, 'fungus'), K.C(sid, 'glow')
    bruise = K.C(sid, 'bruise')
    im = tinted(WALL, WALL, (26, 23, 20), seed, (58, 50, 42), (10, 10, 9), gain=0.9)
    im = wash_ellipse(im, (30, 30, 98, 120), wet, 32)
    pen = ImageDraw.Draw(im)
    rng = random.Random(seed + 107)
    # cords from the canopy above
    for x in (42, 52, 64, 76, 86):
        pen.line((x, 0, x + rng.randint(-3, 3), 30), fill=root_l, width=3)
        pen.line((x + 1, 0, x + rng.randint(-2, 4), 30), fill=bone, width=1)
    # woven root cage: a clear teardrop outline with readable bars
    cage_top, cage_bot = 30, 114
    def half_width(y):
        t = (y - cage_top) / (cage_bot - cage_top)
        return 14 + 18 * math.sin(math.pi * min(1.0, t * 0.92)) - 6 * t
    left = [(64 - half_width(y), y) for y in range(cage_top, cage_bot + 1, 3)]
    right = [(64 + half_width(y), y) for y in range(cage_top, cage_bot + 1, 3)]
    # dark interior
    pen.polygon(left + list(reversed(right)), fill=(7, 7, 7), outline=bone)
    pen.line(left, fill=bone, width=2)
    pen.line(right, fill=root_l, width=2)
    # vertical woven bars
    for i in range(-4, 5):
        pts = []
        for y in range(cage_top + 2, cage_bot, 4):
            f = i / 4.4
            pts.append((64 + f * half_width(y), y))
        pen.line(pts, fill=bone if i % 2 else root_l, width=2 if i % 3 else 1)
    # horizontal woven bands
    for y in (40, 54, 70, 88, 104):
        hw = half_width(y)
        pen.arc((64 - hw, y - 5, 64 + hw, y + 5), 190, 350, fill=root_l, width=2)
        pen.arc((64 - hw + 1, y - 4, 64 + hw - 1, y + 4), 190, 350, fill=bone, width=1)
    # knots where roots cross
    for x, y in ((42, 54), (86, 70), (46, 88), (80, 104), (64, 40)):
        pen.ellipse((x - 3, y - 3, x + 3, y + 3), fill=root, outline=bone)
        pen.point((x, y), fill=peat)
    # top closure and hanging ring
    pen.arc((48, 24, 80, 44), 190, 350, fill=bone, width=2)
    pen.ellipse((60, 22, 68, 30), outline=root_l, width=2)
    # black void inside and one pale growth at the floor
    pen.ellipse((47, 44, 81, 102), fill=(8, 8, 8))
    pen.line((58, 104, 64, 88), fill=fungus, width=2)
    pen.ellipse((60, 84, 68, 92), fill=fungus, outline=lichen)
    im = wash_ellipse(im, (58, 80, 70, 94), glow, 70)
    pen = ImageDraw.Draw(im)
    # hanging tags and a cut root
    pen.line((88, 24, 88, 40), fill=root_l)
    pen.rectangle((82, 40, 94, 50), fill=bone, outline=root)
    pen.line((84, 44, 92, 44), fill=moss)
    # roots crossing the dark outer ground
    for _ in range(7):
        root_branch(pen, rng.randint(6, 120), 124, -math.pi / 2 + rng.uniform(-0.8, 0.8),
                    rng.randint(14, 32), 2, root, rng, 2)
    wall_frame(im, (42, 38, 32), bone, (22, 20, 18))
    return seam_fix(im)


def wall_conservatory_08(seed):
    sid = 'boneglass_conservatory'
    bone, chalk, pale = K.C(sid, 'bone'), K.C(sid, 'chalk'), K.C(sid, 'pale')
    lichen, moss, peat = K.C(sid, 'lichen'), K.C(sid, 'moss'), K.C(sid, 'peat')
    root, root_l = K.C(sid, 'root'), K.C(sid, 'root_light')
    wet, fungus, glow = K.C(sid, 'wet'), K.C(sid, 'fungus'), K.C(sid, 'glow')
    bruise = K.C(sid, 'bruise')
    im = tinted(WALL, WALL, (28, 25, 21), seed, (62, 56, 46), (9, 9, 8), gain=0.9)
    pen = ImageDraw.Draw(im)
    rng = random.Random(seed + 108)
    # descending canopy mass
    top_pts = [(0, 0), (128, 0), (128, 42)]
    for x in range(128, -1, -8):
        y = 42 + int(12 * math.sin(x / 13.0) + 7 * math.sin(x / 5.0 + 1.0))
        top_pts.append((x, y))
    pen.polygon(top_pts, fill=(46, 44, 36))
    # pale leaf/root clusters
    for i in range(46):
        x = rng.randint(2, 124)
        y = rng.randint(2, 48)
        r = rng.randint(2, 6)
        pen.ellipse((x - r, y - r // 2, x + r, y + r // 2),
                    fill=fungus if i % 3 else lichen, outline=moss)
    # hanging pods on long root strands
    for x, y, r in ((22, 64, 7), (48, 52, 5), (70, 78, 8), (96, 58, 6), (112, 88, 5)):
        pen.line((x, 34, x + rng.randint(-3, 3), y - r), fill=root_l, width=2)
        pen.ellipse((x - r, y - r * 1.4, x + r, y + r * 1.2), fill=fungus, outline=lichen)
        pen.ellipse((x - 2, y - r, x + 2, y + 1), fill=glow)
        pen.line((x, y + r, x, y + r + rng.randint(6, 18)), fill=root_l)
    # embedded growth lamps
    for x, y in ((36, 30), (86, 24)):
        pen.rectangle((x - 6, y - 3, x + 6, y + 3), fill=(74, 78, 62), outline=peat)
        im = wash_ellipse(im, (x - 5, y + 1, x + 5, y + 12), glow, 80)
    pen = ImageDraw.Draw(im)
    # long hanging root curtain
    for _ in range(28):
        x = rng.randint(2, 124)
        y = rng.randint(38, 56)
        root_branch(pen, x, y, math.pi / 2 + rng.uniform(-0.3, 0.3),
                    rng.randint(18, 58), 1, (118, 104, 82), rng, 1)
    # black negative space at the bottom
    im = wash_rect(im, (0, 104, 127, 127), (8, 8, 7), 150)
    pen = ImageDraw.Draw(im)
    for _ in range(8):
        root_branch(pen, rng.randint(10, 118), 124, -math.pi / 2, rng.randint(8, 20), 1,
                    root, rng, 1)
    wall_frame(im, (38, 34, 28), fungus, (18, 16, 14))
    return seam_fix(im)


CONSERVATORY_WALLS = (
    wall_conservatory_01, wall_conservatory_02, wall_conservatory_03, wall_conservatory_04,
    wall_conservatory_05, wall_conservatory_06, wall_conservatory_07, wall_conservatory_08,
)


def seven_seg_three(pen, x, y, w, h, color, dark):
    """A small 7-segment '3' for hotel door plaques; no font is used."""
    t = max(1, h // 6)
    segments = [
        (x, y, x + w, y),                       # top
        (x + w, y, x + w, y + h // 2),          # upper right
        (x, y + h // 2, x + w, y + h // 2),     # middle
        (x + w, y + h // 2, x + w, y + h),      # lower right
        (x, y + h, x + w, y + h),               # bottom
    ]
    for x0, y0, x1, y1 in segments:
        pen.line((x0, y0, x1, y1), fill=dark, width=t + 2)
        pen.line((x0, y0, x1, y1), fill=color, width=t)


# -- Skyhotel Service Well walls --------------------------------------------
def wall_skyhotel_01(seed):
    sid = 'skyhotel_service_well'
    night, night_d = K.C(sid, 'night'), K.C(sid, 'night_dark')
    blue, blue_l = K.C(sid, 'blue'), K.C(sid, 'blue_light')
    rain, teal, teal_d = K.C(sid, 'rain'), K.C(sid, 'teal'), K.C(sid, 'teal_dark')
    amber, amber_l = K.C(sid, 'amber'), K.C(sid, 'amber_light')
    brass, linen = K.C(sid, 'brass'), K.C(sid, 'linen')
    im = tinted(WALL, WALL, blue, seed, blue_l, night_d, gain=0.6)
    pen = ImageDraw.Draw(im)
    # vertical hotel wallpaper stripes with a faint damask tick
    for x in range(0, WALL, 16):
        pen.rectangle((x, 0, x + 7, 127), fill=(58, 76, 90))
        pen.line((x + 8, 0, x + 8, 127), fill=(28, 38, 48))
        for y in range(6, 128, 24):
            pen.line((x + 3, y, x + 3, y + 6), fill=(70, 90, 104))
            pen.line((x + 3, y + 3, x + 6, y + 1), fill=(70, 90, 104))
            pen.line((x + 3, y + 3, x, y + 1), fill=(70, 90, 104))
    # brass chair rail
    pen.rectangle((0, 82, 127, 88), fill=brass, outline=(48, 36, 20))
    pen.line((0, 83, 127, 83), fill=(214, 180, 116))
    pen.line((0, 87, 127, 87), fill=(74, 54, 28))
    for x in (12, 44, 76, 108):
        pen.rectangle((x, 80, x + 6, 90), fill=(130, 100, 54), outline=(52, 38, 20))
        bolt(pen, x + 3, 85, 1, amber_l, (52, 38, 20))
    # dark baseboard
    pen.rectangle((0, 112, 127, 127), fill=(24, 32, 40), outline=(12, 18, 24))
    pen.line((0, 112, 127, 112), fill=(66, 82, 94))
    # rain stain from above and scuffs
    im = wash_poly(im, [(28, 0), (42, 0), (38, 26), (48, 46), (44, 70), (52, 82),
                        (46, 82), (38, 58), (42, 34), (32, 16)], night_d, 42)
    pen = ImageDraw.Draw(im)
    rng = random.Random(seed + 201)
    for _ in range(18):
        x, y = rng.randint(4, 122), rng.randint(90, 122)
        pen.line((x, y, x + rng.randint(2, 8), y + rng.randint(-2, 2)), fill=(84, 98, 108))
    for _ in range(12):
        x, y = rng.randint(4, 120), rng.randint(8, 110)
        pen.point((x, y), fill=(120, 138, 150))
    # a small brass service hook
    pen.arc((92, 94, 104, 106), 180, 360, fill=brass, width=2)
    pen.line((98, 94, 98, 90), fill=brass, width=2)
    wall_frame(im, (18, 24, 30), (128, 154, 168), (12, 16, 20))
    return seam_fix(im)


def wall_skyhotel_02(seed):
    sid = 'skyhotel_service_well'
    night, night_d = K.C(sid, 'night'), K.C(sid, 'night_dark')
    blue, blue_l = K.C(sid, 'blue'), K.C(sid, 'blue_light')
    rain, teal, teal_d = K.C(sid, 'rain'), K.C(sid, 'teal'), K.C(sid, 'teal_dark')
    amber, amber_l = K.C(sid, 'amber'), K.C(sid, 'amber_light')
    maroon, maroon_d = K.C(sid, 'maroon'), K.C(sid, 'maroon_dark')
    brass, linen = K.C(sid, 'brass'), K.C(sid, 'linen')
    im = tinted(WALL, WALL, blue, seed, (66, 82, 96), night_d, gain=0.55)
    pen = ImageDraw.Draw(im)
    for x in range(0, WALL, 16):
        pen.line((x, 0, x, 127), fill=(34, 46, 56))
    # door surround
    bevel_rect(pen, (20, 4, 108, 120), (44, 58, 70), blue_l, night_d, 2)
    # maroon door
    pen.rectangle((26, 10, 102, 116), fill=maroon, outline=maroon_d, width=2)
    pen.line((28, 12, 100, 12), fill=(130, 82, 88))
    # recessed panels
    for box, fill in (((34, 20, 94, 54), (92, 48, 54)), ((34, 64, 94, 104), (96, 50, 56))):
        x0, y0, x1, y1 = box
        pen.rectangle(box, fill=fill, outline=maroon_d, width=2)
        pen.line((x0 + 2, y0 + 2, x1 - 2, y0 + 2), fill=(142, 86, 92))
        pen.line((x0 + 2, y0 + 2, x0 + 2, y1 - 2), fill=(132, 80, 86))
    # brass number plaque with two 7-segment 3s
    pen.rectangle((52, 12, 76, 30), fill=brass, outline=(58, 42, 22))
    seven_seg_three(pen, 55, 16, 6, 10, amber_l, (54, 38, 18))
    seven_seg_three(pen, 67, 16, 6, 10, amber_l, (54, 38, 18))
    # peephole and handle
    pen.ellipse((61, 38, 67, 44), fill=(22, 16, 18), outline=brass)
    pen.ellipse((62, 39, 66, 43), fill=(92, 70, 44))
    pen.rectangle((91, 70, 97, 78), fill=brass, outline=(52, 38, 20))
    pen.ellipse((88, 74, 98, 84), outline=brass, width=2)
    # under-door light and threshold
    im = wash_rect(im, (26, 110, 102, 116), amber, 100)
    pen = ImageDraw.Draw(im)
    pen.line((26, 110, 102, 110), fill=amber_l)
    pen.rectangle((18, 114, 110, 120), fill=(40, 50, 58), outline=(18, 24, 30))
    for x in (28, 52, 76, 100):
        bolt(pen, x, 117, 1, (112, 130, 140), (24, 30, 36))
    # card slot and room-service hanger
    pen.rectangle((78, 88, 94, 92), fill=(32, 24, 26), outline=brass)
    pen.line((80, 90, 92, 90), fill=amber)
    # scuffs and rain smear
    rng = random.Random(seed + 202)
    im = wash_poly(im, [(8, 0), (16, 0), (20, 40), (14, 80), (18, 112), (12, 112),
                        (8, 78), (12, 38)], night_d, 38)
    pen = ImageDraw.Draw(im)
    scratches(pen, rng, (132, 146, 154), 8, (6, 6, 122, 120))
    chips(pen, rng, maroon_d, 6, (28, 12, 100, 114), 3)
    wall_frame(im, (16, 22, 28), (126, 150, 162), (10, 14, 18))
    return seam_fix(im)


def wall_skyhotel_03(seed):
    sid = 'skyhotel_service_well'
    night, night_d = K.C(sid, 'night'), K.C(sid, 'night_dark')
    blue, blue_l = K.C(sid, 'blue'), K.C(sid, 'blue_light')
    rain, teal, teal_d = K.C(sid, 'rain'), K.C(sid, 'teal'), K.C(sid, 'teal_dark')
    amber, amber_l = K.C(sid, 'amber'), K.C(sid, 'amber_light')
    brass, linen = K.C(sid, 'brass'), K.C(sid, 'linen')
    im = tinted(WALL, WALL, (64, 76, 86), seed, (104, 116, 126), (36, 44, 52), gain=0.8)
    pen = ImageDraw.Draw(im)
    # concrete formwork lines
    for y in (0, 32, 64, 96):
        pen.line((0, y, 127, y), fill=(44, 52, 60))
        pen.line((0, y + 1, 127, y + 1), fill=(94, 104, 112))
    # central pipe chase
    pen.rectangle((50, 0, 88, 127), fill=(42, 52, 60), outline=(24, 30, 36))
    pen.rectangle((52, 0, 58, 127), fill=teal, outline=(26, 44, 44))
    pen.rectangle((60, 0, 68, 127), fill=(126, 90, 48), outline=(54, 38, 20))
    pen.rectangle((70, 0, 78, 127), fill=blue_l, outline=(38, 50, 60))
    for x in (55, 64, 74):
        pen.line((x, 0, x, 127), fill=(176, 190, 196))
    for y in (24, 56, 88, 118):
        pen.rectangle((50, y, 88, y + 6), fill=(80, 90, 98), outline=(30, 36, 42))
        bolt(pen, 53, y + 3, 1, (150, 162, 168), (30, 36, 42))
        bolt(pen, 85, y + 3, 1, (150, 162, 168), (30, 36, 42))
    # corner guards
    for x0 in (14, 100):
        pen.rectangle((x0, 8, x0 + 14, 120), fill=(76, 86, 94), outline=(32, 38, 44))
        pen.line((x0 + 2, 10, x0 + 2, 118), fill=(126, 138, 146))
        for y in (18, 52, 86, 112):
            pen.ellipse((x0 + 6, y, x0 + 9, y + 3), fill=(32, 36, 40))
    # floor level band and amber tick
    pen.rectangle((0, 104, 127, 112), fill=(34, 42, 48), outline=(20, 26, 32))
    pen.line((0, 104, 127, 104), fill=amber)
    pen.rectangle((100, 106, 118, 110), fill=amber, outline=(66, 46, 20))
    pen.rectangle((104, 107, 114, 109), fill=night_d)
    # cracks and damp
    rng = random.Random(seed + 203)
    for x, y in ((12, 40), (94, 24), (36, 78)):
        pen.line((x, y, x + rng.randint(-4, 6), y + rng.randint(8, 18)), fill=(42, 50, 58))
    im = wash_rect(im, (0, 0, 127, 8), night_d, 80)
    pen = ImageDraw.Draw(im)
    scratches(pen, rng, (134, 146, 154), 10, (6, 6, 122, 120))
    wall_frame(im, (16, 22, 28), (126, 150, 162), (10, 14, 18))
    return seam_fix(im)


def wall_skyhotel_04(seed):
    sid = 'skyhotel_service_well'
    night, night_d = K.C(sid, 'night'), K.C(sid, 'night_dark')
    blue, blue_l = K.C(sid, 'blue'), K.C(sid, 'blue_light')
    rain, teal, teal_d = K.C(sid, 'rain'), K.C(sid, 'teal'), K.C(sid, 'teal_dark')
    amber, amber_l = K.C(sid, 'amber'), K.C(sid, 'amber_light')
    brass, linen = K.C(sid, 'brass'), K.C(sid, 'linen')
    im = tinted(WALL, WALL, night, seed, (58, 70, 82), (12, 18, 24), gain=0.7)
    pen = ImageDraw.Draw(im)
    # twin dumbwaiter rails
    for x in (20, 100):
        pen.rectangle((x, 0, x + 8, 127), fill=brass, outline=(48, 34, 18))
        pen.line((x + 1, 0, x + 1, 127), fill=(208, 176, 116))
        pen.line((x + 7, 0, x + 7, 127), fill=(70, 50, 26))
        for y in range(10, 127, 22):
            pen.rectangle((x - 3, y, x + 11, y + 5), fill=(88, 94, 100), outline=(28, 32, 38))
            pen.ellipse((x, y + 1, x + 8, y + 4), fill=(132, 140, 146))
    # top pulley and cable
    pen.ellipse((46, 10, 82, 46), fill=(58, 70, 80), outline=(20, 26, 32))
    pen.ellipse((50, 14, 78, 42), outline=brass, width=3)
    for k in range(6):
        a = math.tau * k / 6
        pen.line((64, 28, 64 + math.cos(a) * 13, 28 + math.sin(a) * 13), fill=(154, 124, 70))
    pen.ellipse((61, 25, 67, 31), fill=night_d, outline=brass)
    pen.line((64, 46, 64, 76), fill=(190, 164, 112), width=2)
    # call panel
    pen.rectangle((48, 76, 80, 104), fill=(44, 54, 62), outline=(18, 24, 30))
    pen.rectangle((52, 80, 76, 100), fill=(28, 36, 44), outline=brass)
    for i, y in enumerate((84, 90, 96)):
        pen.ellipse((58, y - 2, 66, y + 2), fill=amber if i == 1 else (96, 80, 50), outline=(32, 28, 20))
    pen.line((68, 88, 74, 88), fill=amber_l)
    # hanging cable loop and service scuffs
    pen.arc((86, 56, 106, 76), 90, 300, fill=(176, 150, 104), width=2)
    pen.line((104, 62, 108, 40), fill=(176, 150, 104), width=2)
    rng = random.Random(seed + 204)
    for _ in range(14):
        x, y = rng.randint(10, 118), rng.randint(100, 122)
        pen.line((x, y, x + rng.randint(2, 10), y + rng.randint(-2, 2)), fill=(72, 84, 94))
    im = wash_rect(im, (0, 0, 127, 10), night_d, 110)
    pen = ImageDraw.Draw(im)
    scratches(pen, rng, (128, 144, 154), 7, (6, 6, 122, 120))
    wall_frame(im, (14, 20, 26), (122, 148, 160), (9, 13, 17))
    return seam_fix(im)


def wall_skyhotel_05(seed):
    sid = 'skyhotel_service_well'
    night, night_d = K.C(sid, 'night'), K.C(sid, 'night_dark')
    blue, blue_l = K.C(sid, 'blue'), K.C(sid, 'blue_light')
    rain, teal, teal_d = K.C(sid, 'rain'), K.C(sid, 'teal'), K.C(sid, 'teal_dark')
    amber, amber_l = K.C(sid, 'amber'), K.C(sid, 'amber_light')
    brass, linen = K.C(sid, 'brass'), K.C(sid, 'linen')
    im = tinted(WALL, WALL, blue, seed, (74, 92, 108), night_d, gain=0.6)
    pen = ImageDraw.Draw(im)
    # rectangular rain window
    bevel_rect(pen, (6, 6, 122, 122), (44, 56, 66), (94, 110, 122), (20, 26, 32), 2)
    pen.rectangle((12, 12, 116, 116), fill=(18, 28, 38), outline=(10, 14, 18), width=2)
    # night outside: balcony rail and city lights
    pen.rectangle((12, 12, 116, 74), fill=(22, 34, 46))
    for y in (82, 90, 98):
        pen.line((14, y, 114, y), fill=(94, 114, 126), width=2)
        pen.line((14, y + 1, 114, y + 1), fill=(44, 58, 68))
    for x in (24, 48, 72, 96):
        pen.line((x, 74, x, 106), fill=(94, 114, 126), width=2)
    rng = random.Random(seed + 205)
    for _ in range(18):
        x, y = rng.randint(16, 112), rng.randint(16, 70)
        pen.point((x, y), fill=amber if _ % 4 == 0 else (84, 106, 120))
    # glazing bars
    pen.line((64, 12, 64, 116), fill=(112, 126, 136), width=3)
    pen.line((12, 52, 116, 52), fill=(100, 116, 126), width=3)
    pen.line((12, 80, 116, 80), fill=(76, 90, 100), width=2)
    # rain streaks and beads
    for _ in range(46):
        x = rng.randint(14, 112)
        y0 = rng.randint(14, 90)
        y1 = min(114, y0 + rng.randint(6, 26))
        pen.line((x, y0, x + rng.randint(-2, 2), y1), fill=(82, 108, 122))
    for _ in range(30):
        x, y = rng.randint(14, 112), rng.randint(14, 112)
        pen.ellipse((x, y, x + 2, y + 3), fill=(126, 150, 162))
    # cracked pane
    pen.line((74, 56, 84, 70, 79, 82, 92, 94), fill=(182, 198, 204))
    pen.line((84, 70, 96, 66), fill=(182, 198, 204))
    # amber reflection smear
    im = wash_poly(im, [(16, 94), (30, 88), (42, 100), (34, 116), (16, 116)], amber, 34)
    pen = ImageDraw.Draw(im)
    pen.line((14, 114, 114, 114), fill=(98, 112, 122))
    wall_frame(im, (12, 18, 24), (120, 146, 158), (8, 12, 16))
    return seam_fix(im)


def wall_skyhotel_06(seed):
    sid = 'skyhotel_service_well'
    night, night_d = K.C(sid, 'night'), K.C(sid, 'night_dark')
    blue, blue_l = K.C(sid, 'blue'), K.C(sid, 'blue_light')
    rain, teal, teal_d = K.C(sid, 'rain'), K.C(sid, 'teal'), K.C(sid, 'teal_dark')
    amber, amber_l = K.C(sid, 'amber'), K.C(sid, 'amber_light')
    brass, linen = K.C(sid, 'brass'), K.C(sid, 'linen')
    im = tinted(WALL, WALL, teal_d, seed, (68, 92, 90), (28, 42, 42), gain=0.7)
    pen = ImageDraw.Draw(im)
    for x in range(0, WALL, 16):
        pen.line((x, 0, x, 127), fill=(40, 58, 58))
    # directory panel
    bevel_rect(pen, (12, 16, 116, 104), (34, 50, 50), (84, 106, 102), (18, 28, 28), 2)
    pen.rectangle((18, 22, 110, 98), fill=(22, 34, 36), outline=(10, 18, 20))
    # floor rows: amber ticks and small arrows
    rows = (30, 40, 50, 60, 70, 80)
    for i, y in enumerate(rows):
        length = 42 + (i * 13) % 34
        pen.line((24, y, 24 + length, y), fill=amber if i % 2 == 0 else (168, 124, 62), width=3)
        pen.line((24, y - 2, 24 + length, y - 2), fill=amber_l, width=1)
        if i % 2:
            pen.polygon([(24 + length + 5, y), (24 + length - 3, y - 5),
                         (24 + length - 3, y + 5)], fill=amber)
        for k in range(3):
            pen.line((28 + k * 7, y - 5, 28 + k * 7, y - 3), fill=(222, 178, 100))
    # large right arrow and an upward return arrow
    pen.polygon([(34, 90), (72, 90), (72, 84), (92, 94), (72, 104), (72, 98), (34, 98)],
                fill=amber, outline=(80, 54, 20))
    pen.polygon([(24, 92), (30, 80), (36, 92), (31, 92), (31, 98), (29, 98), (29, 92)],
                fill=amber_l, outline=(80, 54, 20))
    # screws and worn edges
    for x, y in ((16, 20), (112, 20), (16, 100), (112, 100)):
        bolt(pen, x, y, 2, (140, 112, 62), (48, 34, 18))
    rng = random.Random(seed + 206)
    im = wash_poly(im, [(86, 100), (118, 96), (118, 127), (92, 127)], night_d, 60)
    pen = ImageDraw.Draw(im)
    scratches(pen, rng, (146, 156, 154), 12, (6, 6, 122, 120))
    chips(pen, rng, (86, 72, 40), 6, (12, 16, 116, 104), 3)
    wall_frame(im, (12, 18, 24), (118, 144, 154), (8, 12, 16))
    return seam_fix(im)


def wall_skyhotel_07(seed):
    sid = 'skyhotel_service_well'
    night, night_d = K.C(sid, 'night'), K.C(sid, 'night_dark')
    blue, blue_l = K.C(sid, 'blue'), K.C(sid, 'blue_light')
    rain, teal, teal_d = K.C(sid, 'rain'), K.C(sid, 'teal'), K.C(sid, 'teal_dark')
    amber, amber_l = K.C(sid, 'amber'), K.C(sid, 'amber_light')
    maroon, maroon_d = K.C(sid, 'maroon'), K.C(sid, 'maroon_dark')
    brass, linen = K.C(sid, 'brass'), K.C(sid, 'linen')
    im = tinted(WALL, WALL, night, seed, (56, 68, 80), (10, 16, 22), gain=0.7)
    pen = ImageDraw.Draw(im)
    for x in range(0, WALL, 16):
        pen.line((x, 0, x, 127), fill=(22, 32, 40))
    # brass lift surround
    bevel_rect(pen, (16, 4, 112, 122), (58, 70, 78), (132, 104, 58), (16, 22, 28), 2)
    # indicator box, with an impossible extra tick between floors
    pen.rectangle((40, 8, 88, 26), fill=(16, 22, 26), outline=brass)
    for i, x in enumerate((46, 56, 66, 76)):
        h = 6 + i * 2
        pen.line((x, 22 - h, x, 22), fill=amber_l if i != 2 else (78, 58, 30), width=2)
    pen.polygon([(80, 16), (84, 20), (80, 24)], fill=amber)
    # lift doors: one panel ajar on amber light
    pen.rectangle((22, 30, 106, 116), fill=(12, 16, 18), outline=(8, 10, 12))
    pen.rectangle((22, 30, 60, 116), fill=maroon, outline=maroon_d, width=2)
    pen.rectangle((68, 30, 106, 116), fill=(70, 38, 42), outline=maroon_d, width=2)
    for x0 in (22, 68):
        for y in range(34, 116, 12):
            pen.line((x0 + 2, y, x0 + 36, y), fill=(110, 66, 70))
        pen.line((x0 + 4, 30, x0 + 4, 116), fill=(122, 76, 80))
        pen.line((x0 + 34, 30, x0 + 34, 116), fill=(46, 24, 28))
    # amber gap between the panels
    im = wash_rect(im, (60, 30, 68, 116), amber, 210)
    pen = ImageDraw.Draw(im)
    pen.line((60, 30, 60, 116), fill=amber_l, width=2)
    for y in (40, 54, 68, 82, 96, 110):
        pen.line((60, y, 68, y), fill=(120, 74, 28))
    # call plate and floor sill
    pen.rectangle((108, 60, 120, 88), fill=(38, 48, 56), outline=(14, 18, 22))
    pen.ellipse((111, 64, 117, 70), fill=amber, outline=(52, 38, 18))
    pen.ellipse((111, 74, 117, 80), fill=(82, 66, 40), outline=(52, 38, 18))
    pen.rectangle((10, 116, 122, 122), fill=(52, 62, 70), outline=(16, 22, 28))
    for x in range(14, 122, 12):
        pen.line((x, 116, x + 4, 122), fill=(104, 92, 62))
    # amber spill on the floor
    im = wash_ellipse(im, (42, 112, 94, 128), amber, 54)
    pen = ImageDraw.Draw(im)
    rng = random.Random(seed + 207)
    scratches(pen, rng, (122, 140, 150), 8, (6, 6, 122, 120))
    wall_frame(im, (10, 16, 20), (120, 146, 156), (8, 12, 16))
    return seam_fix(im)


def wall_skyhotel_08(seed):
    sid = 'skyhotel_service_well'
    night, night_d = K.C(sid, 'night'), K.C(sid, 'night_dark')
    blue, blue_l = K.C(sid, 'blue'), K.C(sid, 'blue_light')
    rain, teal, teal_d = K.C(sid, 'rain'), K.C(sid, 'teal'), K.C(sid, 'teal_dark')
    amber, amber_l = K.C(sid, 'amber'), K.C(sid, 'amber_light')
    brass, linen = K.C(sid, 'brass'), K.C(sid, 'linen')
    im = tinted(WALL, WALL, (13, 19, 26), seed, (32, 42, 52), (5, 8, 12), gain=0.7)
    pen = ImageDraw.Draw(im)
    rng = random.Random(seed + 208)
    # atrium perspective lines
    for x in (0, 18, 36, 54, 72, 90, 108, 126):
        pen.line((x, 0, x, 127), fill=(20, 28, 36))
    # staggered balcony slabs with lit rooms
    slabs = (
        (0, 18, 74, 8, 'left'), (54, 44, 128, 8, 'right'),
        (0, 70, 82, 8, 'left'), (48, 96, 128, 8, 'right'),
    )
    for i, (x0, y, x1, h, side) in enumerate(slabs):
        pen.rectangle((x0, y, x1, y + h), fill=(54, 64, 72), outline=(24, 32, 40))
        pen.line((x0, y, x1, y), fill=(112, 126, 136))
        # railing
        rx0 = x1 - 34 if side == 'left' else x0
        pen.line((rx0, y - 8, rx0 + 34, y - 8), fill=(112, 132, 142), width=2)
        for k in range(5):
            pen.line((rx0 + k * 8, y - 8, rx0 + k * 8, y), fill=(78, 94, 104))
        # lit room windows behind
        for k in range(3):
            wx = x0 + 8 + k * 20 if side == 'left' else x0 + 18 + k * 20
            if wx + 8 < x1:
                pen.rectangle((wx, y - 18, wx + 8, y - 3),
                              fill=amber if (i + k) % 2 else (86, 66, 40),
                              outline=(32, 28, 22))
        # under-balcony service line
        pen.line((x0 + 4, y + h + 2, x1 - 4, y + h + 2), fill=(44, 54, 62))
    # hanging luggage cage in the void
    pen.line((82, 32, 82, 52), fill=(116, 96, 58), width=2)
    pen.rectangle((74, 52, 90, 70), fill=(22, 28, 32), outline=brass)
    for x in (77, 81, 85, 89):
        pen.line((x, 54, x, 68), fill=brass)
    # rain on the atrium glass and small distant lights
    for _ in range(40):
        x = rng.randint(2, 124)
        pen.line((x, rng.randint(2, 80), x + rng.randint(-2, 2), rng.randint(84, 126)),
                 fill=(24, 40, 50))
    for _ in range(24):
        x, y = rng.randint(4, 122), rng.randint(4, 116)
        pen.point((x, y), fill=amber if _ % 5 == 0 else (60, 86, 100))
    # deep void gradient at the bottom
    im = wash_rect(im, (0, 112, 127, 127), (4, 6, 9), 150)
    pen = ImageDraw.Draw(im)
    wall_frame(im, (8, 12, 16), (92, 118, 130), (6, 9, 12))
    return seam_fix(im)


SKYHOTEL_WALLS = (
    wall_skyhotel_01, wall_skyhotel_02, wall_skyhotel_03, wall_skyhotel_04,
    wall_skyhotel_05, wall_skyhotel_06, wall_skyhotel_07, wall_skyhotel_08,
)


# -- flats -------------------------------------------------------------------
def flat_foundry_01(seed):
    sid = 'ashbell_foundry'
    soot, iron, iron_l = K.C(sid, 'soot'), K.C(sid, 'iron'), K.C(sid, 'iron_light')
    bronze, verd, ash = K.C(sid, 'bronze'), K.C(sid, 'verdigris'), K.C(sid, 'ash')
    im = tinted(FLAT, FLAT, iron, seed, iron_l, soot, gain=0.7)
    pen = ImageDraw.Draw(im)
    for p in (0, 32):
        pen.line((p, 0, p, 63), fill=soot)
        pen.line((p + 1, 0, p + 1, 63), fill=(98, 96, 90))
        pen.line((0, p, 63, p), fill=soot)
        pen.line((0, p + 1, 63, p + 1), fill=(98, 96, 90))
    for x, y in ((16, 16), (48, 16), (16, 48), (48, 48)):
        bolt(pen, x, y, 2, bronze, soot, ash)
        pen.line((x - 6, y + 4, x + 6, y + 4), fill=(52, 50, 46))
    # embedded hoist rails
    for y in (8, 40):
        pen.line((0, y, 63, y), fill=(114, 74, 34))
        pen.line((0, y + 1, 63, y + 1), fill=(28, 28, 30))
    im = wash_ellipse(im, (6, 34, 28, 54), verd, 34)
    pen = ImageDraw.Draw(im)
    rng = random.Random(seed + 301)
    scratches(pen, rng, (128, 124, 116), 10, (2, 2, 61, 61), (2, 7))
    for _ in range(9):
        x, y = rng.randint(3, 58), rng.randint(3, 58)
        pen.point((x, y), fill=(148, 94, 42))
    flat_frame(im, soot, iron_l)
    return seam_fix(im)


def flat_foundry_02(seed):
    sid = 'ashbell_foundry'
    soot, iron = K.C(sid, 'soot'), K.C(sid, 'iron')
    bronze, bronze_l = K.C(sid, 'bronze'), K.C(sid, 'bronze_light')
    verd, ash = K.C(sid, 'verdigris'), K.C(sid, 'ash')
    im = tinted(FLAT, FLAT, (56, 45, 35), seed, (94, 76, 54), (26, 21, 17), gain=1.2)
    pen = ImageDraw.Draw(im)
    # casting sand drag marks and a runner channel
    rng = random.Random(seed + 302)
    for _ in range(6):
        x0, y0 = rng.randint(2, 54), rng.randint(4, 58)
        pts = [(x0, y0)]
        for k in range(4):
            pts.append((pts[-1][0] + rng.randint(3, 9), pts[-1][1] + rng.randint(-3, 3)))
        pen.line(pts, fill=(34, 28, 22), width=2)
    pen.rectangle((0, 26, 63, 34), fill=(38, 31, 24), outline=(22, 18, 14))
    pen.line((0, 27, 63, 27), fill=(74, 60, 44))
    # bronze spill with a bright edge
    pen.ellipse((30, 38, 58, 54), fill=(132, 92, 40), outline=(62, 42, 20))
    pen.ellipse((36, 41, 50, 49), fill=bronze_l)
    pen.ellipse((40, 43, 45, 47), fill=(212, 162, 84))
    pen.line((32, 50, 54, 48), fill=(86, 58, 26))
    # divots and ash
    for _ in range(14):
        x, y = rng.randint(3, 58), rng.randint(3, 58)
        r = rng.randint(1, 3)
        pen.ellipse((x, y, x + r, y + r), fill=(30, 24, 18))
    im = wash_rect(im, (0, 54, 63, 63), ash, 18)
    pen = ImageDraw.Draw(im)
    scratches(pen, rng, (128, 106, 78), 6, (2, 2, 61, 61))
    flat_frame(im, soot, bronze)
    return seam_fix(im)


def flat_foundry_03(seed):
    sid = 'ashbell_foundry'
    soot, iron, iron_l = K.C(sid, 'soot'), K.C(sid, 'iron'), K.C(sid, 'iron_light')
    bronze, verd = K.C(sid, 'bronze'), K.C(sid, 'verdigris')
    im = tinted(FLAT, FLAT, (19, 20, 22), seed, (44, 42, 38), (6, 6, 8), gain=0.8)
    pen = ImageDraw.Draw(im)
    # dark brick vault ribs
    for y in (0, 32):
        pen.rectangle((0, y, 63, y + 6), fill=(42, 38, 34), outline=(10, 10, 11))
        pen.line((0, y + 1, 63, y + 1), fill=(74, 66, 56))
        for x in range(4, 64, 16):
            pen.line((x, y + 2, x, y + 6), fill=(16, 16, 17))
    # short hanging chains and hooks viewed from below
    for x, y in ((16, 18), (48, 18), (32, 50)):
        for k in range(3):
            pen.ellipse((x - 2, y + k * 5, x + 2, y + k * 5 + 3), outline=bronze)
        pen.line((x, y + 15, x, y + 20), fill=soot)
        pen.arc((x - 3, y + 18, x + 3, y + 24), 0, 180, fill=verd, width=1)
    rng = random.Random(seed + 303)
    scratches(pen, rng, (80, 76, 68), 8, (2, 2, 61, 61))
    flat_frame(im, soot, (54, 52, 48))
    return seam_fix(im)


def flat_foundry_04(seed):
    sid = 'ashbell_foundry'
    soot, iron, iron_l = K.C(sid, 'soot'), K.C(sid, 'iron'), K.C(sid, 'iron_light')
    bronze, bronze_l = K.C(sid, 'bronze'), K.C(sid, 'bronze_light')
    furn, furn_l = K.C(sid, 'furnace'), K.C(sid, 'furnace_light')
    im = tinted(FLAT, FLAT, iron, seed, iron_l, soot, gain=0.6)
    pen = ImageDraw.Draw(im)
    # heavy grate frame
    pen.rectangle((4, 4, 59, 59), fill=(40, 24, 14), outline=soot, width=3)
    im = wash_rect(im, (8, 8, 56, 56), furn, 170)
    im = wash_ellipse(im, (16, 16, 48, 48), furn_l, 90)
    pen = ImageDraw.Draw(im)
    # grate bars
    for x in range(8, 60, 8):
        pen.rectangle((x, 6, x + 3, 58), fill=iron, outline=soot)
        pen.line((x, 7, x + 1, 57), fill=iron_l)
    for y in (8, 56):
        pen.rectangle((6, y, 58, y + 3), fill=iron, outline=soot)
    # glow slots and heat dither
    for x in range(12, 56, 8):
        pen.line((x, 14, x, 52), fill=furn_l)
    rng = random.Random(seed + 304)
    for _ in range(20):
        x, y = rng.randint(10, 54), rng.randint(10, 54)
        pen.point((x, y), fill=(255, 206, 122))
    pen.line((8, 8, 56, 56), fill=(44, 28, 16))
    flat_frame(im, soot, bronze_l)
    return seam_fix(im)


def flat_conservatory_01(seed):
    sid = 'boneglass_conservatory'
    bone, chalk, pale = K.C(sid, 'bone'), K.C(sid, 'chalk'), K.C(sid, 'pale')
    lichen, moss = K.C(sid, 'lichen'), K.C(sid, 'moss')
    peat, root = K.C(sid, 'peat'), K.C(sid, 'root')
    im = tinted(FLAT, FLAT, (176, 170, 155), seed, (226, 221, 206), (118, 112, 98), gain=0.9)
    pen = ImageDraw.Draw(im)
    for p in (0, 32):
        pen.line((p, 0, p, 63), fill=(88, 84, 72))
        pen.line((p + 1, 0, p + 1, 63), fill=(214, 209, 194))
        pen.line((0, p, 63, p), fill=(88, 84, 72))
        pen.line((0, p + 1, 63, p + 1), fill=(214, 209, 194))
    rng = random.Random(seed + 401)
    # moss in joints and scattered pale pebbles
    for _ in range(18):
        x = rng.randint(0, 60)
        y = rng.choice((2, 30, 34, 62)) + rng.randint(0, 2)
        pen.ellipse((x, y, x + rng.randint(3, 7), y + 2), fill=moss)
    for _ in range(26):
        x, y = rng.randint(2, 59), rng.randint(2, 59)
        r = rng.randint(1, 3)
        pen.ellipse((x, y, x + r, y + r), fill=pale if _ % 3 else chalk,
                    outline=(142, 136, 122))
    # root veins
    for x, y, a in ((8, 60, -1.4), (40, 62, -1.7), (58, 54, -2.0)):
        root_branch(pen, x, y, a, rng.randint(8, 16), 1, root, rng, 2)
    im = wash_ellipse(im, (4, 36, 26, 58), peat, 18)
    pen = ImageDraw.Draw(im)
    scratches(pen, rng, (232, 228, 214), 9, (2, 2, 61, 61))
    flat_frame(im, (58, 54, 46), pale)
    return seam_fix(im)


def flat_conservatory_02(seed):
    sid = 'boneglass_conservatory'
    bone, chalk = K.C(sid, 'bone'), K.C(sid, 'chalk')
    lichen, moss, peat = K.C(sid, 'lichen'), K.C(sid, 'moss'), K.C(sid, 'peat')
    wet, tin, root = K.C(sid, 'wet'), K.C(sid, 'tin'), K.C(sid, 'root')
    im = tinted(FLAT, FLAT, (54, 66, 62), seed, (92, 106, 98), (24, 30, 28), gain=1.0)
    rng = random.Random(seed + 402)
    pen = ImageDraw.Draw(im)
    # slate drainage grid
    for p in (0, 32):
        pen.line((p, 0, p, 63), fill=(20, 26, 24))
        pen.line((p + 1, 0, p + 1, 63), fill=(82, 96, 88))
        pen.line((0, p, 63, p), fill=(20, 26, 24))
        pen.line((0, p + 1, 63, p + 1), fill=(82, 96, 88))
    # central drain grate
    pen.rectangle((22, 22, 42, 42), fill=(36, 42, 38), outline=(12, 16, 14))
    for x in range(25, 40, 4):
        pen.line((x, 24, x, 40), fill=tin)
    for y in (24, 32, 40):
        pen.line((23, y, 41, y), fill=(18, 22, 20))
    # puddles and algae
    for box in ((6, 44, 28, 60), (36, 6, 56, 18), (44, 46, 60, 58)):
        im = wash_ellipse(im, box, (18, 26, 26), 150)
    pen = ImageDraw.Draw(im)
    for box in ((8, 46, 24, 58), (38, 8, 52, 16), (46, 48, 58, 56)):
        pen.arc(box, 200, 340, fill=(104, 124, 114))
    for _ in range(14):
        x, y = rng.randint(2, 58), rng.randint(2, 58)
        pen.ellipse((x, y, x + rng.randint(2, 5), y + rng.randint(1, 3)), fill=moss)
    root_branch(pen, 58, 62, -1.9, 14, 1, root, rng, 2)
    flat_frame(im, (18, 24, 22), (96, 112, 102))
    return seam_fix(im)


def flat_conservatory_03(seed):
    sid = 'boneglass_conservatory'
    bone, chalk, pale = K.C(sid, 'bone'), K.C(sid, 'chalk'), K.C(sid, 'pale')
    lichen, moss, peat = K.C(sid, 'lichen'), K.C(sid, 'moss'), K.C(sid, 'peat')
    root, tin = K.C(sid, 'root'), K.C(sid, 'tin')
    im = tinted(FLAT, FLAT, (154, 148, 134), seed, (202, 196, 180), (92, 88, 76), gain=0.7)
    pen = ImageDraw.Draw(im)
    for p in (0, 32):
        pen.line((p, 0, p, 63), fill=(74, 70, 60))
        pen.line((p + 1, 0, p + 1, 63), fill=(196, 190, 174))
        pen.line((0, p, 63, p), fill=(74, 70, 60))
        pen.line((0, p + 1, 63, p + 1), fill=(196, 190, 174))
    # water stains and hanging roots
    rng = random.Random(seed + 403)
    for box in ((5, 6, 25, 28), (36, 34, 58, 56)):
        im = wash_ellipse(im, box, (108, 100, 84), 56)
    pen = ImageDraw.Draw(im)
    for _ in range(7):
        x = rng.randint(3, 60)
        root_branch(pen, x, 0, math.pi / 2 + rng.uniform(-0.4, 0.4),
                    rng.randint(4, 13), 1, root, rng, 1)
    # a missing tile corner
    pen.polygon([(46, 0), (64, 0), (64, 18), (56, 14)], fill=(28, 26, 22))
    pen.line((46, 0, 56, 14), fill=(84, 80, 68))
    for x, y in ((16, 16), (48, 48)):
        pen.ellipse((x - 2, y - 2, x + 2, y + 2), fill=tin, outline=(64, 60, 52))
    scratches(pen, rng, (210, 204, 188), 7, (2, 2, 61, 61))
    flat_frame(im, (54, 50, 42), (206, 200, 184))
    return seam_fix(im)


def flat_conservatory_04(seed):
    sid = 'boneglass_conservatory'
    bone, chalk, pale = K.C(sid, 'bone'), K.C(sid, 'chalk'), K.C(sid, 'pale')
    lichen, moss, peat = K.C(sid, 'lichen'), K.C(sid, 'moss'), K.C(sid, 'peat')
    root, fungus, glow = K.C(sid, 'root'), K.C(sid, 'fungus'), K.C(sid, 'glow')
    wet, tin = K.C(sid, 'wet'), K.C(sid, 'tin')
    im = tinted(FLAT, FLAT, (208, 216, 198), seed, (238, 244, 226), (138, 150, 132), gain=0.5)
    pen = ImageDraw.Draw(im)
    # glasshouse roof panes and dark glazing bars
    for p in (0, 16, 32, 48):
        pen.line((p, 0, p, 63), fill=(82, 94, 80))
        pen.line((p + 1, 0, p + 1, 63), fill=(166, 178, 158))
        pen.line((0, p, 63, p), fill=(82, 94, 80))
        pen.line((0, p + 1, 63, p + 1), fill=(166, 178, 158))
    # pane tone variation
    for row in range(4):
        for col in range(4):
            if (row + col) % 3 == 0:
                im = wash_rect(im, (col * 16 + 2, row * 16 + 2, col * 16 + 14, row * 16 + 14),
                               (138, 162, 146), 40)
    pen = ImageDraw.Draw(im)
    # silhouetted vines crossing the glass
    rng = random.Random(seed + 404)
    for base_x, base_y, angle in ((8, 60, -1.2), (46, 62, -1.8), (60, 8, 2.2)):
        root_branch(pen, base_x, base_y, angle, rng.randint(12, 20), 2, (58, 76, 60), rng, 2)
    for x in (24, 40, 56):
        pen.ellipse((x - 3, 26, x + 3, 30), outline=(66, 84, 68))
    # condensation
    for _ in range(18):
        x, y = rng.randint(2, 60), rng.randint(2, 60)
        pen.point((x, y), fill=(244, 248, 232))
    flat_frame(im, (70, 82, 68), (238, 244, 226))
    return seam_fix(im)


def flat_skyhotel_01(seed):
    sid = 'skyhotel_service_well'
    night, night_d = K.C(sid, 'night'), K.C(sid, 'night_dark')
    blue, blue_l = K.C(sid, 'blue'), K.C(sid, 'blue_light')
    rain, teal, teal_d = K.C(sid, 'rain'), K.C(sid, 'teal'), K.C(sid, 'teal_dark')
    amber, amber_l = K.C(sid, 'amber'), K.C(sid, 'amber_light')
    maroon, maroon_d = K.C(sid, 'maroon'), K.C(sid, 'maroon_dark')
    linen, carpet = K.C(sid, 'linen'), K.C(sid, 'carpet')
    im = tinted(FLAT, FLAT, carpet, seed, (78, 94, 90), (34, 44, 42), gain=0.8)
    pen = ImageDraw.Draw(im)
    # chevron hotel carpet, period 16
    for row in range(4):
        y = row * 16
        for col in range(8):
            x = col * 8 + (8 if row % 2 else 0)
            pen.line((x - 4, y + 15, x + 4, y + 1), fill=maroon, width=2)
            pen.line((x - 3, y + 15, x + 5, y + 1), fill=(126, 78, 82))
            pen.line((x + 4, y + 15, x + 12, y + 1), fill=teal_d, width=1)
    for y in (0, 16, 32, 48):
        pen.line((0, y, 63, y), fill=(30, 40, 38))
    im = wash_ellipse(im, (10, 36, 30, 54), night_d, 64)
    im = wash_ellipse(im, (40, 8, 58, 22), (58, 42, 30), 48)
    pen = ImageDraw.Draw(im)
    rng = random.Random(seed + 501)
    for _ in range(8):
        x, y = rng.randint(2, 58), rng.randint(2, 58)
        pen.line((x, y, x + rng.randint(2, 7), y + rng.randint(-2, 2)), fill=(112, 100, 82))
    flat_frame(im, night_d, (92, 110, 104))
    return seam_fix(im)


def flat_skyhotel_02(seed):
    sid = 'skyhotel_service_well'
    night, night_d = K.C(sid, 'night'), K.C(sid, 'night_dark')
    blue, blue_l = K.C(sid, 'blue'), K.C(sid, 'blue_light')
    rain, teal, teal_d = K.C(sid, 'rain'), K.C(sid, 'teal'), K.C(sid, 'teal_dark')
    amber, amber_l = K.C(sid, 'amber'), K.C(sid, 'amber_light')
    brass, linen = K.C(sid, 'brass'), K.C(sid, 'linen')
    im = tinted(FLAT, FLAT, (66, 78, 88), seed, (102, 114, 124), (38, 48, 56), gain=0.8)
    pen = ImageDraw.Draw(im)
    for p in (0, 16, 32, 48):
        pen.line((p, 0, p, 63), fill=(34, 42, 50))
        pen.line((p + 1, 0, p + 1, 63), fill=(104, 114, 122))
        pen.line((0, p, 63, p), fill=(34, 42, 50))
        pen.line((0, p + 1, 63, p + 1), fill=(104, 114, 122))
    # drain
    pen.rectangle((24, 24, 40, 40), fill=(30, 38, 44), outline=(14, 18, 22))
    for x in range(26, 39, 3):
        pen.line((x, 26, x, 38), fill=brass)
    for y in (26, 32, 38):
        pen.line((25, y, 39, y), fill=(16, 20, 24))
    # wet footprints and scuffs
    rng = random.Random(seed + 502)
    for x, y in ((8, 44), (16, 50), (48, 10), (54, 16)):
        pen.ellipse((x, y, x + 4, y + 7), fill=(30, 40, 48))
        pen.ellipse((x + 1, y + 8, x + 3, y + 10), fill=(30, 40, 48))
    for _ in range(13):
        x, y = rng.randint(2, 58), rng.randint(2, 58)
        pen.line((x, y, x + rng.randint(2, 8), y + rng.randint(-1, 1)), fill=(96, 106, 112))
    # small amber caution mark
    pen.polygon([(8, 56), (12, 56), (12, 60), (8, 60)], fill=amber)
    im = wash_ellipse(im, (4, 2, 20, 12), night_d, 44)
    flat_frame(im, (20, 26, 32), (108, 120, 128))
    return seam_fix(im)


def flat_skyhotel_03(seed):
    sid = 'skyhotel_service_well'
    night, night_d = K.C(sid, 'night'), K.C(sid, 'night_dark')
    blue, blue_l = K.C(sid, 'blue'), K.C(sid, 'blue_light')
    rain, teal, teal_d = K.C(sid, 'rain'), K.C(sid, 'teal'), K.C(sid, 'teal_dark')
    amber, amber_l = K.C(sid, 'amber'), K.C(sid, 'amber_light')
    brass, linen = K.C(sid, 'brass'), K.C(sid, 'linen')
    im = tinted(FLAT, FLAT, (150, 148, 136), seed, (190, 188, 174), (86, 86, 78), gain=0.6)
    pen = ImageDraw.Draw(im)
    for p in (0, 32):
        pen.line((p, 0, p, 63), fill=(82, 80, 72))
        pen.line((p + 1, 0, p + 1, 63), fill=(196, 194, 180))
        pen.line((0, p, 63, p), fill=(82, 80, 72))
        pen.line((0, p + 1, 63, p + 1), fill=(196, 194, 180))
    # water stain
    im = wash_ellipse(im, (6, 8, 30, 30), (120, 104, 80), 52)
    pen = ImageDraw.Draw(im)
    pen.arc((8, 10, 28, 28), 200, 340, fill=(104, 88, 66))
    # one missing tile with dark void
    pen.rectangle((36, 36, 60, 60), fill=(32, 34, 34), outline=(88, 86, 78))
    pen.line((36, 36, 60, 36), fill=(206, 204, 190))
    for x in (42, 50):
        pen.line((x, 38, x, 58), fill=(20, 22, 22))
    # sprinkler head
    pen.ellipse((30, 28, 36, 34), fill=(92, 90, 82), outline=(58, 56, 50))
    pen.line((33, 34, 33, 38), fill=(58, 56, 50))
    scratches(pen, rng := random.Random(seed + 503), (208, 206, 192), 6, (2, 2, 61, 61))
    flat_frame(im, (58, 56, 50), (200, 198, 184))
    return seam_fix(im)


def flat_skyhotel_04(seed):
    sid = 'skyhotel_service_well'
    night, night_d = K.C(sid, 'night'), K.C(sid, 'night_dark')
    blue, blue_l = K.C(sid, 'blue'), K.C(sid, 'blue_light')
    rain, teal, teal_d = K.C(sid, 'rain'), K.C(sid, 'teal'), K.C(sid, 'teal_dark')
    amber, amber_l = K.C(sid, 'amber'), K.C(sid, 'amber_light')
    brass, linen = K.C(sid, 'brass'), K.C(sid, 'linen')
    im = tinted(FLAT, FLAT, (76, 68, 56), seed, (120, 104, 82), (36, 32, 26), gain=0.7)
    pen = ImageDraw.Draw(im)
    # coffered hotel ceiling
    for p in (0, 32):
        pen.rectangle((p, 0, p + 4, 63), fill=brass, outline=(44, 34, 20))
        pen.rectangle((0, p, 63, p + 4), fill=brass, outline=(44, 34, 20))
    for x, y in ((16, 16), (48, 16), (16, 48), (48, 48)):
        # warm recessed downlight
        im = wash_ellipse(im, (x - 10, y - 10, x + 10, y + 10), amber, 60)
        pen = ImageDraw.Draw(im)
        pen.ellipse((x - 6, y - 6, x + 6, y + 6), fill=(60, 48, 32), outline=brass, width=2)
        pen.ellipse((x - 4, y - 4, x + 4, y + 4), fill=amber_l)
        pen.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(255, 238, 196))
        pen.arc((x - 7, y - 7, x + 7, y + 7), 200, 340, fill=(44, 34, 20))
    rng = random.Random(seed + 504)
    scratches(pen, rng, (158, 144, 118), 6, (4, 4, 59, 59))
    flat_frame(im, (36, 30, 22), (174, 156, 118))
    return seam_fix(im)


FOUNDRY_FLATS = (flat_foundry_01, flat_foundry_02, flat_foundry_03, flat_foundry_04)
CONSERVATORY_FLATS = (flat_conservatory_01, flat_conservatory_02,
                      flat_conservatory_03, flat_conservatory_04)
SKYHOTEL_FLATS = (flat_skyhotel_01, flat_skyhotel_02, flat_skyhotel_03, flat_skyhotel_04)


# -- props (96x128 RGBA, transparent margin, base y~123) --------------------
def _prop():
    return Image.new('RGBA', (PROP_W, PROP_H), (0, 0, 0, 0))


def _base_shadow(pen, x0=14, x1=82, y=118):
    pen.ellipse((x0, y, x1, min(124, y + 6)), fill=(0, 0, 0, 62))


def prop_foundry_lamp(seed):
    sid = 'ashbell_foundry'
    soot, iron, iron_l = K.C(sid, 'soot'), K.C(sid, 'iron'), K.C(sid, 'iron_light')
    bronze, bronze_l = K.C(sid, 'bronze'), K.C(sid, 'bronze_light')
    verd, verd_l = K.C(sid, 'verdigris'), K.C(sid, 'verdigris_light')
    furn, furn_l = K.C(sid, 'furnace'), K.C(sid, 'furnace_light')
    bone = K.C(sid, 'bone')
    im = _prop()
    pen = ImageDraw.Draw(im)
    _base_shadow(pen, 18, 80, 117)
    # three legs
    pen.line((48, 82, 24, 122), fill=soot, width=5)
    pen.line((49, 82, 24, 122), fill=iron_l, width=1)
    pen.line((48, 82, 70, 122), fill=soot, width=5)
    pen.line((47, 82, 69, 122), fill=iron, width=1)
    pen.line((48, 82, 48, 122), fill=soot, width=5)
    pen.line((49, 82, 49, 122), fill=iron_l, width=1)
    pen.ellipse((20, 119, 30, 124), fill=iron, outline=soot)
    pen.ellipse((66, 119, 76, 124), fill=iron, outline=soot)
    # central hook post
    pen.line((48, 84, 48, 34), fill=iron, width=5)
    pen.line((49, 84, 49, 34), fill=iron_l, width=1)
    pen.arc((48, 24, 72, 48), 90, 300, fill=iron, width=5)
    pen.arc((49, 25, 71, 47), 90, 300, fill=iron_l, width=1)
    pen.line((69, 36, 69, 48), fill=soot, width=3)
    # chain and ladle
    for y in (48, 55, 62):
        pen.ellipse((66, y, 72, y + 7), outline=bronze, width=2)
    pen.line((69, 69, 69, 74), fill=soot, width=2)
    pen.polygon([(52, 72), (86, 72), (80, 86), (58, 86)], fill=bronze, outline=(58, 36, 18))
    pen.ellipse((53, 70, 85, 82), fill=bronze_l, outline=(74, 46, 20))
    pen.ellipse((57, 72, 81, 80), fill=furn, outline=(110, 62, 24))
    pen.ellipse((62, 73, 76, 78), fill=furn_l)
    pen.line((55, 76, 66, 76), fill=(255, 212, 142))
    pen.line((80, 73, 88, 60), fill=bronze, width=3)
    pen.line((88, 60, 70, 48), fill=bronze, width=3)
    # hook attachment and heat wear
    pen.ellipse((65, 44, 74, 53), outline=bronze, width=2)
    pen.line((54, 85, 82, 85), fill=(80, 48, 20))
    for x, y in ((58, 88), (64, 91), (74, 89)):
        pen.ellipse((x, y, x + 4, y + 2), fill=(126, 74, 30))
    # ash tray and grease pot
    pen.ellipse((24, 113, 46, 122), fill=iron, outline=soot)
    pen.ellipse((27, 114, 43, 119), fill=(50, 44, 38))
    pen.rectangle((72, 106, 86, 120), fill=iron, outline=soot)
    pen.ellipse((73, 103, 85, 110), fill=bronze, outline=(58, 36, 18))
    pen.line((74, 108, 84, 108), fill=verd)
    # small verdigris details
    bolt(pen, 48, 88, 2, verd, soot, verd_l)
    bolt(pen, 78, 112, 1, bronze, soot, bone)
    rng = random.Random(seed + 601)
    for _ in range(6):
        x, y = rng.randint(22, 84), rng.randint(96, 121)
        pen.point((x, y), fill=(132, 124, 108))
    pen.line((56 + rng.randint(-2, 2), 78, 66 + rng.randint(-2, 2), 77 + rng.randint(-1, 1)),
             fill=furn_l)
    return im


def prop_foundry_shrine(seed):
    sid = 'ashbell_foundry'
    soot, iron, iron_l = K.C(sid, 'soot'), K.C(sid, 'iron'), K.C(sid, 'iron_light')
    bronze, bronze_l = K.C(sid, 'bronze'), K.C(sid, 'bronze_light')
    verd, verd_l = K.C(sid, 'verdigris'), K.C(sid, 'verdigris_light')
    ash, bone = K.C(sid, 'ash'), K.C(sid, 'bone')
    im = _prop()
    pen = ImageDraw.Draw(im)
    _base_shadow(pen, 12, 86, 117)
    # squat chain drum
    pen.rectangle((14, 82, 78, 121), fill=iron, outline=soot)
    pen.ellipse((14, 76, 78, 94), fill=(58, 58, 60), outline=soot)
    pen.ellipse((18, 79, 74, 91), fill=iron_l, outline=(28, 28, 30))
    for y in (92, 106):
        pen.rectangle((14, y, 78, y + 4), fill=bronze, outline=(58, 38, 18))
        for x in (20, 42, 70):
            bolt(pen, x, y + 2, 1, verd, soot, verd_l)
    # coiled chain mound, deliberately asymmetric
    rng = random.Random(seed + 611)
    for i in range(7):
        cx = 24 + i * 6 + rng.randint(-1, 1)
        cy = 76 - (i % 3) * 2 + rng.randint(-1, 1)
        r = 11 + rng.randint(0, 2)
        pen.arc((cx - r, cy - 8, cx + r, cy + 8), 190, 530, fill=bronze, width=3)
        pen.arc((cx - r + 2, cy - 6, cx + r - 2, cy + 6), 190, 530, fill=bronze_l, width=1)
    for _ in range(4):
        x, y = rng.randint(20, 72), rng.randint(98, 120)
        pen.point((x, y), fill=(122, 112, 94))
    # hanging hook and counterweight
    pen.line((58, 70, 58, 32), fill=iron_l, width=3)
    pen.arc((48, 22, 68, 42), 90, 300, fill=iron_l, width=3)
    pen.line((66, 32, 66, 44), fill=soot, width=2)
    pen.ellipse((64, 42, 72, 50), outline=bronze, width=2)
    pen.rectangle((68, 46, 82, 64), fill=iron_l, outline=soot)
    pen.line((70, 50, 80, 50), fill=(92, 88, 82))
    pen.line((70, 56, 80, 56), fill=(70, 68, 64))
    # grease pot and ladle cup
    pen.rectangle((76, 96, 90, 118), fill=(64, 56, 44), outline=soot)
    pen.ellipse((75, 92, 91, 101), fill=bronze, outline=(58, 38, 18))
    pen.line((78, 97, 88, 97), fill=verd_l)
    pen.line((80, 100, 86, 100), fill=(30, 40, 34))
    pen.ellipse((20, 112, 38, 121), fill=(44, 38, 32), outline=soot)
    # verdigris bleed and ash
    im = Image.fromarray(np.array(im), 'RGBA')
    return im


def prop_foundry_directory(seed):
    sid = 'ashbell_foundry'
    soot, iron, iron_l = K.C(sid, 'soot'), K.C(sid, 'iron'), K.C(sid, 'iron_light')
    bronze, bronze_l = K.C(sid, 'bronze'), K.C(sid, 'bronze_light')
    verd, verd_l = K.C(sid, 'verdigris'), K.C(sid, 'verdigris_light')
    bone, ash = K.C(sid, 'bone'), K.C(sid, 'ash')
    im = _prop()
    pen = ImageDraw.Draw(im)
    _base_shadow(pen, 14, 82, 117)
    # two legs and feet
    for x0, x1 in ((30, 22), (66, 74)):
        pen.line((x0, 72, x1, 122), fill=iron, width=5)
        pen.line((x0 + 1, 72, x1 + 1, 122), fill=iron_l, width=1)
        pen.line((x1 - 6, 121, x1 + 6, 121), fill=soot, width=3)
    # tilted board with cast frame
    board = [(22, 32), (72, 22), (82, 70), (32, 80)]
    pen.polygon(board, fill=soot, outline=(12, 12, 14))
    pen.line((24, 34, 74, 24), fill=bronze, width=2)
    pen.line((74, 24, 82, 68), fill=bronze, width=2)
    pen.line((82, 68, 34, 78), fill=(70, 44, 20), width=2)
    pen.line((34, 78, 24, 34), fill=(70, 44, 20), width=2)
    # three bell plaques on short chains
    for x, y, w, h in ((36, 38, 15, 18), (53, 34, 20, 24), (69, 44, 12, 15)):
        pen.line((x + w // 2, y - 6, x + w // 2, y), fill=bronze)
        pen.ellipse((x + w // 2 - 2, y - 8, x + w // 2 + 2, y - 4), outline=bronze)
        bell_shape(pen, x + w // 2, y, w, h, bronze_l if w > 15 else bronze,
                   (236, 190, 112), (66, 40, 18), lip=verd)
    # direction arrow on the board
    pen.line((40, 66, 62, 62), fill=verd_l, width=3)
    pen.polygon([(66, 61), (58, 57), (60, 67)], fill=verd_l)
    # top chain
    for y in (4, 10, 16):
        pen.ellipse((46, y, 52, y + 6), outline=bronze, width=2)
    pen.line((49, 22, 49, 30), fill=soot, width=1)
    # verdigris and wear
    for x, y in ((30, 50), (76, 30), (58, 74)):
        pen.ellipse((x, y, x + 5, y + 2), fill=verd)
    rng = random.Random(seed + 612)
    for _ in range(8):
        x, y = rng.randint(26, 78), rng.randint(26, 76)
        pen.point((x, y), fill=ash)
    bolt(pen, 27, 36, 2, verd, soot, verd_l)
    bolt(pen, 77, 68, 2, verd, soot, verd_l)
    return im


def prop_conservatory_lamp(seed):
    sid = 'boneglass_conservatory'
    bone, chalk, pale = K.C(sid, 'bone'), K.C(sid, 'chalk'), K.C(sid, 'pale')
    lichen, moss, peat = K.C(sid, 'lichen'), K.C(sid, 'moss'), K.C(sid, 'peat')
    root, root_l = K.C(sid, 'root'), K.C(sid, 'root_light')
    fungus, glow = K.C(sid, 'fungus'), K.C(sid, 'glow')
    copper = K.C(sid, 'root_light')
    im = _prop()
    pen = ImageDraw.Draw(im)
    _base_shadow(pen, 20, 78, 117)
    # mossy ceramic pot
    pen.polygon([(30, 100), (64, 100), (68, 116), (62, 123), (32, 123), (26, 116)],
                fill=(112, 118, 98), outline=(44, 48, 38))
    pen.ellipse((28, 96, 66, 108), fill=(150, 154, 126), outline=(48, 52, 42))
    pen.ellipse((34, 99, 60, 105), fill=peat, outline=(50, 44, 34))
    for x, y in ((32, 112), (44, 118), (58, 110)):
        pen.ellipse((x, y, x + 7, y + 4), fill=moss)
    # curved root stem
    pts = [(48, 100), (44, 88), (40, 74), (44, 60), (54, 50), (64, 44)]
    pen.line(pts, fill=root, width=5)
    pen.line([(x + 1, y) for x, y in pts], fill=root_l, width=1)
    # branches and tendrils
    pen.line((44, 74, 33, 64), fill=root, width=2)
    pen.line((48, 60, 38, 48), fill=root, width=2)
    pen.line((54, 50, 48, 38), fill=root, width=2)
    pen.line((64, 44, 72, 34), fill=root_l, width=2)
    # drooping translucent pod
    pod = [(64, 46), (76, 50), (80, 64), (74, 80), (66, 86), (60, 78), (58, 64), (60, 52)]
    pen.polygon(pod, fill=(226, 234, 202), outline=lichen)
    pen.line((64, 48, 62, 82), fill=(184, 198, 160), width=2)
    pen.ellipse((64, 60, 74, 74), fill=glow, outline=(188, 204, 166))
    pen.ellipse((67, 63, 71, 67), fill=(250, 255, 236))
    pen.line((62, 56, 74, 52), fill=(196, 210, 174))
    pen.line((62, 72, 74, 76), fill=(190, 204, 170))
    # copper tag and leaves
    pen.line((70, 52, 80, 44), fill=root_l, width=2)
    pen.ellipse((80, 40, 86, 46), outline=(150, 112, 66), width=1)
    pen.line((82, 42, 84, 44), fill=(150, 112, 66))
    for x, y, w in ((34, 68, 8), (46, 84, 7), (72, 88, 8)):
        pen.ellipse((x, y, x + w, y + w // 2), fill=(126, 146, 110), outline=moss)
    # hanging tendrils
    for x0, y0, x1, y1 in ((58, 86, 55, 100), (66, 86, 70, 98), (74, 80, 84, 94)):
        pen.line((x0, y0, x1, y1), fill=root_l, width=1)
    # glow spill on the pot
    im = Image.alpha_composite(im, Image.new('RGBA', im.size, (0, 0, 0, 0)))
    overlay = Image.new('RGBA', im.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((58, 88, 86, 104), fill=(226, 242, 198, 46))
    im = Image.alpha_composite(im, overlay)
    pen = ImageDraw.Draw(im)
    rng = random.Random(seed + 620)
    for _ in range(5):
        x, y = rng.randint(28, 88), rng.randint(40, 118)
        pen.ellipse((x, y, x + 2, y + 1), fill=(214, 226, 190))
    pen.line((60 + rng.randint(-2, 2), 60, 58 + rng.randint(-2, 2), 78),
             fill=(186, 202, 164), width=1)
    return im


def prop_conservatory_shrine(seed):
    sid = 'boneglass_conservatory'
    bone, chalk, pale = K.C(sid, 'bone'), K.C(sid, 'chalk'), K.C(sid, 'pale')
    lichen, moss, peat = K.C(sid, 'lichen'), K.C(sid, 'moss'), K.C(sid, 'peat')
    root, root_l = K.C(sid, 'root'), K.C(sid, 'root_light')
    wet, tin = K.C(sid, 'wet'), K.C(sid, 'tin')
    im = _prop()
    pen = ImageDraw.Draw(im)
    _base_shadow(pen, 10, 88, 117)
    # peat mound base
    pen.polygon([(10, 118), (14, 104), (26, 96), (40, 100), (54, 92), (72, 98),
                 (86, 106), (88, 120), (74, 124), (20, 124)],
                fill=(40, 34, 26), outline=(20, 18, 14))
    pen.line((14, 108, 34, 102, 52, 106, 72, 100, 84, 108), fill=(70, 58, 42))
    rng = random.Random(seed + 621)
    for _ in range(12):
        x, y = rng.randint(14, 82), rng.randint(102, 120)
        pen.ellipse((x, y, x + rng.randint(2, 5), y + 2), fill=root)
    # standpipe: vertical + crossbar + tap + rose
    pen.rectangle((44, 54, 54, 104), fill=(78, 112, 96), outline=(34, 54, 44))
    pen.line((46, 56, 46, 102), fill=(152, 184, 158))
    pen.rectangle((18, 58, 80, 68), fill=(82, 116, 98), outline=(34, 54, 44))
    pen.line((20, 60, 78, 60), fill=(156, 186, 160))
    pen.ellipse((14, 52, 34, 72), outline=(66, 96, 82), width=3)
    for k in range(6):
        a = math.tau * k / 6
        pen.line((24, 62, 24 + math.cos(a) * 9, 62 + math.sin(a) * 9), fill=(130, 162, 138))
    pen.ellipse((21, 59, 27, 65), fill=(42, 62, 52), outline=(22, 34, 28))
    # watering rose
    pen.ellipse((72, 62, 90, 76), fill=(92, 126, 104), outline=(34, 54, 44))
    for x, y in ((76, 67), (80, 65), (84, 68), (78, 72), (84, 72)):
        pen.point((x, y), fill=(26, 42, 34))
    for x in (76, 80, 84, 88):
        pen.line((x, 76, x, 78 + (x % 3)), fill=(106, 146, 124))
    # pressure bulb
    pen.ellipse((44, 42, 56, 56), fill=(172, 184, 158), outline=(58, 72, 58))
    pen.line((50, 48, 50, 54), fill=(78, 96, 78))
    pen.ellipse((48, 46, 52, 50), fill=(208, 218, 192))
    # white roots swallowing the pipe
    for _ in range(9):
        x = rng.randint(30, 80)
        y = rng.randint(68, 100)
        root_branch(pen, x, y, rng.uniform(-2.4, -0.6), rng.randint(8, 18), 2,
                    (214, 208, 188), rng, 2)
    # a bucket hanging on the crossbar
    pen.line((66, 68, 66, 78), fill=root_l)
    pen.polygon([(60, 78), (72, 78), (70, 92), (62, 92)], fill=(94, 106, 88), outline=(42, 52, 42))
    pen.ellipse((60, 76, 72, 82), fill=(58, 68, 56), outline=(34, 42, 34))
    # algae and drip
    for _ in range(8):
        x, y = rng.randint(18, 86), rng.randint(74, 96)
        pen.ellipse((x, y, x + 4, y + 2), fill=lichen)
    return im


def prop_conservatory_directory(seed):
    sid = 'boneglass_conservatory'
    bone, chalk, pale = K.C(sid, 'bone'), K.C(sid, 'chalk'), K.C(sid, 'pale')
    lichen, moss, peat = K.C(sid, 'lichen'), K.C(sid, 'moss'), K.C(sid, 'peat')
    root, root_l = K.C(sid, 'root'), K.C(sid, 'root_light')
    fungus, glow = K.C(sid, 'fungus'), K.C(sid, 'glow')
    im = _prop()
    pen = ImageDraw.Draw(im)
    _base_shadow(pen, 12, 84, 117)
    # root-wrapped legs
    for x0, x1 in ((30, 20), (66, 76)):
        pen.line((x0, 74, x1, 123), fill=root, width=4)
        pen.line((x0 + 1, 74, x1 + 1, 123), fill=root_l, width=1)
        for k in range(4):
            y = 84 + k * 10
            x = x0 + (x1 - x0) * (y - 74) / 49
            pen.arc((x - 4, y - 2, x + 4, y + 3), 190, 350, fill=(218, 212, 192), width=1)
    # leaning trellis board
    board = [(24, 32), (74, 24), (80, 76), (30, 84)]
    pen.polygon(board, fill=(196, 190, 172), outline=(92, 84, 68))
    pen.line((26, 35, 72, 28), fill=pale, width=2)
    pen.line((72, 28, 78, 74), fill=(156, 150, 132))
    pen.line((78, 74, 32, 82), fill=(110, 102, 84))
    # slats
    for k in range(3):
        x0 = 30 + k * 4
        pen.line((x0, 40 + k * 9, x0 + 42, 36 + k * 9), fill=(146, 140, 122), width=2)
    # shallow seed tray
    pen.polygon([(32, 82), (76, 76), (78, 88), (34, 94)], fill=peat, outline=(70, 62, 48))
    rng = random.Random(seed + 622)
    for _ in range(12):
        x, y = rng.randint(38, 70), rng.randint(82, 90)
        pen.ellipse((x, y, x + 2, y + 2), fill=(146, 128, 86) if _ % 3 else glow)
    # hanging tags on strings
    for x, y, w in ((34, 36, 16), (50, 30, 14), (64, 42, 12)):
        pen.line((x + w // 2, 30, x + w // 2, y), fill=root_l)
        pen.rectangle((x, y, x + w, y + 9), fill=bone, outline=(104, 96, 80))
        pen.line((x + 2, y + 3, x + w - 2, y + 3), fill=moss)
        pen.line((x + 2, y + 6, x + w - 4, y + 6), fill=(144, 132, 110))
        pen.point((x + w // 2, y + 9), fill=root)
    # root tendril and moss
    root_branch(pen, 75, 76, -0.6, 18, 2, root, rng, 2)
    root_branch(pen, 22, 92, -1.2, 14, 1, root_l, rng, 2)
    for _ in range(8):
        x, y = rng.randint(22, 80), rng.randint(86, 104)
        pen.ellipse((x, y, x + 4, y + 2), fill=lichen)
    return im


def prop_skyhotel_lamp(seed):
    sid = 'skyhotel_service_well'
    night, night_d = K.C(sid, 'night'), K.C(sid, 'night_dark')
    blue, blue_l = K.C(sid, 'blue'), K.C(sid, 'blue_light')
    amber, amber_l = K.C(sid, 'amber'), K.C(sid, 'amber_light')
    brass, linen = K.C(sid, 'brass'), K.C(sid, 'linen')
    maroon = K.C(sid, 'maroon')
    im = _prop()
    pen = ImageDraw.Draw(im)
    _base_shadow(pen, 26, 70, 117)
    # stable base
    pen.ellipse((32, 116, 62, 124), fill=(64, 50, 28), outline=(30, 24, 14))
    pen.ellipse((36, 117, 58, 122), fill=brass, outline=(46, 36, 20))
    # slim post
    pen.rectangle((46, 42, 50, 120), fill=brass, outline=(44, 32, 16))
    pen.line((47, 44, 47, 118), fill=(210, 176, 112))
    pen.line((49, 44, 49, 118), fill=(86, 62, 30))
    # rain hood and warm rectangular shade
    pen.rectangle((22, 22, 74, 30), fill=brass, outline=(40, 30, 16))
    pen.line((24, 24, 72, 24), fill=(218, 184, 120))
    pen.rectangle((26, 30, 70, 50), fill=(58, 44, 26), outline=(30, 24, 14))
    pen.rectangle((29, 32, 67, 48), fill=amber, outline=(86, 60, 24))
    pen.rectangle((32, 34, 64, 40), fill=amber_l, outline=(120, 86, 36))
    pen.line((30, 46, 66, 46), fill=(150, 102, 42))
    # hanging luggage tag
    pen.line((69, 48, 76, 58), fill=(106, 82, 46))
    pen.polygon([(74, 58), (84, 60), (82, 72), (72, 70)], fill=maroon, outline=(38, 22, 26))
    pen.ellipse((77, 62, 80, 65), fill=(24, 16, 18), outline=linen)
    pen.line((76, 67, 83, 68), fill=(176, 142, 96))
    # grime and light spill
    overlay = Image.new('RGBA', im.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((22, 44, 76, 76), fill=(238, 190, 110, 34))
    im = Image.alpha_composite(im, overlay)
    pen = ImageDraw.Draw(im)
    for x, y in ((34, 114), (58, 114), (40, 110)):
        pen.line((x, y, x + 4, y - 1), fill=(122, 94, 54))
    rng = random.Random(seed + 630)
    for _ in range(5):
        x, y = rng.randint(28, 72), rng.randint(96, 120)
        pen.point((x, y), fill=(148, 120, 78))
    pen.line((69, 48, 76 + rng.randint(-2, 2), 58 + rng.randint(-2, 2)),
             fill=(118, 92, 52))
    return im


def prop_skyhotel_shrine(seed):
    sid = 'skyhotel_service_well'
    night, night_d = K.C(sid, 'night'), K.C(sid, 'night_dark')
    blue, blue_l = K.C(sid, 'blue'), K.C(sid, 'blue_light')
    amber, amber_l = K.C(sid, 'amber'), K.C(sid, 'amber_light')
    brass = K.C(sid, 'brass')
    maroon, maroon_d = K.C(sid, 'maroon'), K.C(sid, 'maroon_dark')
    linen = K.C(sid, 'linen')
    im = _prop()
    pen = ImageDraw.Draw(im)
    _base_shadow(pen, 10, 88, 117)
    # low winch body
    pen.rectangle((12, 94, 74, 122), fill=(64, 74, 82), outline=(22, 28, 32))
    pen.rectangle((14, 96, 72, 102), fill=(94, 106, 114), outline=(28, 34, 38))
    for x in (18, 34, 50, 66):
        bolt(pen, x, 108, 1, brass, (30, 26, 16))
    # large spoked wheel
    cx, cy, r = 42, 72, 22
    pen.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(48, 56, 62), outline=brass, width=4)
    pen.ellipse((cx - r + 5, cy - r + 5, cx + r - 5, cy + r - 5), outline=(126, 94, 50), width=2)
    for k in range(6):
        a = math.tau * k / 6
        pen.line((cx, cy, cx + math.cos(a) * 18, cy + math.sin(a) * 18), fill=brass, width=3)
        pen.line((cx, cy, cx + math.cos(a) * 18, cy + math.sin(a) * 18), fill=(206, 172, 110), width=1)
    pen.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=(30, 36, 40), outline=brass)
    # cable spool
    pen.rectangle((70, 90, 88, 118), fill=(52, 60, 66), outline=(20, 24, 28))
    for y in (94, 100, 106, 112):
        pen.arc((68, y, 90, y + 8), 180, 360, fill=(118, 92, 52), width=2)
    # hanging suitcase from a hook
    pen.line((80, 84, 80, 96), fill=(142, 112, 64), width=2)
    pen.rectangle((66, 98, 88, 120), fill=maroon, outline=maroon_d)
    pen.rectangle((72, 96, 82, 100), fill=(36, 26, 28), outline=maroon_d)
    pen.line((68, 106, 86, 106), fill=(124, 72, 78))
    pen.rectangle((70, 110, 84, 112), fill=brass, outline=(46, 34, 18))
    # call plate with three buttons
    pen.rectangle((14, 62, 32, 88), fill=(40, 50, 58), outline=(20, 26, 30))
    pen.rectangle((16, 64, 30, 86), fill=(28, 36, 42), outline=(96, 74, 40))
    for i, y in enumerate((68, 74, 80)):
        pen.ellipse((20, y, 26, y + 4), fill=amber if i == 1 else (92, 76, 48), outline=(34, 26, 16))
    pen.line((27, 68, 29, 68), fill=amber_l)
    # cable loop and scuffs
    pen.arc((30, 52, 58, 80), 190, 350, fill=(148, 120, 72), width=2)
    pen.line((44, 80, 44, 92), fill=(148, 120, 72), width=2)
    for x, y in ((18, 116), (58, 114), (76, 120)):
        pen.line((x, y, x + 6, y - 1), fill=(122, 102, 64))
    rng = random.Random(seed + 631)
    for _ in range(5):
        x, y = rng.randint(12, 72), rng.randint(96, 120)
        pen.line((x, y, x + rng.randint(2, 6), y + rng.randint(-1, 1)),
                 fill=(126, 112, 78))
    pen.arc((30, 54 + rng.randint(-2, 2), 58, 78 + rng.randint(-2, 2)), 190, 350,
            fill=(154, 128, 80), width=2)
    return im


def prop_skyhotel_directory(seed):
    sid = 'skyhotel_service_well'
    night, night_d = K.C(sid, 'night'), K.C(sid, 'night_dark')
    blue, blue_l = K.C(sid, 'blue'), K.C(sid, 'blue_light')
    amber, amber_l = K.C(sid, 'amber'), K.C(sid, 'amber_light')
    brass = K.C(sid, 'brass')
    maroon, maroon_d = K.C(sid, 'maroon'), K.C(sid, 'maroon_dark')
    linen = K.C(sid, 'linen')
    im = _prop()
    pen = ImageDraw.Draw(im)
    _base_shadow(pen, 12, 84, 117)
    # two solid legs
    for x0, x1 in ((28, 20), (68, 76)):
        pen.line((x0, 80, x1, 122), fill=(78, 84, 90), width=4)
        pen.line((x0 + 1, 80, x1 + 1, 122), fill=(136, 142, 146), width=1)
        pen.line((x1 - 6, 121, x1 + 6, 121), fill=(30, 34, 38), width=3)
    # frame and rain hood
    pen.rectangle((22, 22, 78, 86), fill=(48, 58, 66), outline=brass, width=3)
    pen.rectangle((18, 14, 82, 24), fill=brass, outline=(54, 40, 20))
    pen.line((20, 16, 80, 16), fill=(216, 182, 118))
    pen.line((20, 23, 80, 23), fill=(78, 56, 28))
    # stepped shelves
    pen.rectangle((26, 28, 74, 82), fill=(20, 30, 36), outline=(10, 16, 20))
    shelves = ((28, 34, 60), (36, 48, 72), (24, 62, 56))
    for i, (x0, y, x1) in enumerate(shelves):
        pen.rectangle((x0, y, x1, y + 3), fill=brass, outline=(50, 36, 18))
        pen.line((x0, y, x0, y - 6), fill=(122, 132, 138), width=1)
        pen.line((x1, y, x1, y - 6), fill=(122, 132, 138), width=1)
        for k in range(3):
            bx = x0 + 4 + k * 8
            if bx + 4 < x1:
                pen.rectangle((bx, y + 6, bx + 4, y + 14), fill=amber if (i + k) % 2 else (112, 84, 44),
                              outline=(42, 34, 20))
                pen.line((bx + 1, y + 8, bx + 3, y + 8), fill=amber_l)
    # large arrow at the bottom
    pen.polygon([(30, 72), (58, 72), (58, 68), (70, 76), (58, 84), (58, 80), (30, 80)],
                fill=amber, outline=(70, 48, 18))
    # rain streaks and wear
    rng = random.Random(seed + 632)
    for x in (30, 38, 54, 66):
        pen.line((x, 26, x + 1, 56 + (x % 14)), fill=(86, 110, 120))
    for _ in range(6):
        x, y = rng.randint(26, 74), rng.randint(28, 80)
        pen.point((x, y), fill=(164, 180, 186))
    for x, y in ((24, 26), (76, 26), (24, 84), (76, 84)):
        bolt(pen, x, y, 1, (176, 142, 82), (48, 34, 18))
    return im


PROPS = {
    'ashbell_foundry': {
        'service_lamp': prop_foundry_lamp,
        'cable_shrine': prop_foundry_shrine,
        'directory_sign': prop_foundry_directory,
    },
    'boneglass_conservatory': {
        'service_lamp': prop_conservatory_lamp,
        'cable_shrine': prop_conservatory_shrine,
        'directory_sign': prop_conservatory_directory,
    },
    'skyhotel_service_well': {
        'service_lamp': prop_skyhotel_lamp,
        'cable_shrine': prop_skyhotel_shrine,
        'directory_sign': prop_skyhotel_directory,
    },
}
WALLS = {
    'ashbell_foundry': FOUNDRY_WALLS,
    'boneglass_conservatory': CONSERVATORY_WALLS,
    'skyhotel_service_well': SKYHOTEL_WALLS,
}
FLATS = {
    'ashbell_foundry': FOUNDRY_FLATS,
    'boneglass_conservatory': CONSERVATORY_FLATS,
    'skyhotel_service_well': SKYHOTEL_FLATS,
}


# -- output helpers ----------------------------------------------------------
def safe_prop(im):
    """Keep the 3 px transparent margin and guarantee opaque edge pixels are absent."""
    a = np.array(im.convert('RGBA'), dtype=np.uint8)
    a[:, :3, 3] = 0
    a[:, 93:, 3] = 0
    a[:3, :, 3] = 0
    a[125:, :, 3] = 0
    return Image.fromarray(a, 'RGBA')


def _font(size, bold=False):
    path = ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold
            else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _wrap(text, width):
    words = text.split()
    lines = []
    line = ''
    for word in words:
        if len(line) + len(word) + 1 > width:
            lines.append(line)
            line = word
        else:
            line = (line + ' ' + word).strip()
    if line:
        lines.append(line)
    return lines


def compose_kit_sheet(sid, walls, flats, props, meta, seed, out_path):
    W, H = 1200, 1180
    im = Image.new('RGB', (W, H), (20, 22, 26))
    pen = ImageDraw.Draw(im)
    pen.text((24, 16), f'{meta["name"]} - environment kit', font=_font(26, True),
             fill=(240, 234, 220))
    pen.text((24, 50), f'seed {seed}  |  walls 128x128 RGB  |  flats 64x64 RGB  |  '
             'props 96x128 RGBA', font=_font(14), fill=(180, 190, 190))
    # walls 4x2 at 224 px
    for i, tile in enumerate(walls):
        x = 24 + (i % 4) * 286
        y = 88 + (i // 4) * 286
        pen.text((x, y - 15), f'{i+1:02d}  {K.WALL_ROLES[i]}', font=_font(13, True),
                 fill=(228, 206, 150))
        im.paste(tile.resize((224, 224), Image.NEAREST), (x, y))
        pen.rectangle((x - 1, y - 1, x + 224, y + 224), outline=(70, 72, 76))
    # flats, left column
    for i, tile in enumerate(flats):
        x = 24 + i * 156
        y = 690
        pen.text((x, y - 18), f'flat {i+1:02d}', font=_font(12, True), fill=(228, 206, 150))
        pen.text((x, y - 5), K.FLAT_ROLES[i], font=_font(9), fill=(186, 192, 190))
        im.paste(tile.resize((140, 140), Image.NEAREST), (x, y + 8))
        pen.rectangle((x - 1, y + 7, x + 140, y + 148), outline=(70, 72, 76))
    # props, left column, labels underneath in two lines
    for i, slot in enumerate(K.PROP_SLOTS):
        tile = props[slot]
        x = 24 + i * 202
        y = 890
        bg = Image.new('RGBA', (150, 200), (46, 50, 56, 255))
        bg.alpha_composite(tile, (27, 36))
        im.paste(bg.convert('RGB'), (x, y))
        pen.rectangle((x - 1, y - 1, x + 150, y + 200), outline=(70, 72, 76))
        pen.text((x, y + 205), slot, font=_font(11, True), fill=(228, 206, 150))
        name_lines = _wrap(meta['props'][slot]['display_name'], 22)
        for k, line in enumerate(name_lines[:2]):
            pen.text((x, y + 219 + k * 12), line, font=_font(10), fill=(196, 202, 200))
    # right column: landmark, palette, description
    px = 700
    pen.text((px, 650), 'LANDMARK', font=_font(11, True), fill=(150, 160, 158))
    pen.text((px, 666), meta['landmark']['name'], font=_font(21, True), fill=(240, 220, 160))
    y = 698
    for line in _wrap(meta['landmark']['description'], 52)[:5]:
        pen.text((px, y), line, font=_font(12), fill=(196, 202, 200))
        y += 17
    y += 8
    pen.text((px, y), 'PALETTE', font=_font(11, True), fill=(150, 160, 158))
    y += 18
    keys = list(meta.get('palette', {}))
    for i, key in enumerate(keys):
        col = K.hx(meta['palette'][key])
        sx = px + (i % 4) * 124
        sy = y + (i // 4) * 40
        pen.rectangle((sx, sy, sx + 20, sy + 20), fill=col, outline=(12, 12, 14))
        pen.text((sx + 24, sy + 4), key, font=_font(9), fill=(190, 196, 194))
    y += ((len(keys) + 3) // 4) * 40 + 8
    pen.text((px, y), 'SET DESCRIPTION', font=_font(11, True), fill=(150, 160, 158))
    y += 18
    for line in _wrap(meta['description'], 54)[:10]:
        pen.text((px, y), line, font=_font(11), fill=(184, 190, 188))
        y += 15
    im.save(out_path)
    return im


def compose_tiling_sheet(sid, walls, flats, meta, seed, out_path):
    W, H = 1120, 900
    im = Image.new('RGB', (W, H), (20, 22, 26))
    pen = ImageDraw.Draw(im)
    pen.text((24, 14), f'{meta["name"]} - 2x2 seam proofs', font=_font(24, True),
             fill=(240, 234, 220))
    pen.text((24, 46), 'Opposite edge rows and columns are exactly equal; each panel is a '
             '2x2 paste at native size.', font=_font(13), fill=(180, 190, 190))
    for i, tile in enumerate(walls):
        x = 24 + (i % 4) * 272
        y = 84 + (i // 4) * 300
        proof = Image.new('RGB', (256, 256))
        for yy in (0, 128):
            for xx in (0, 128):
                proof.paste(tile, (xx, yy))
        im.paste(proof, (x, y))
        pen.rectangle((x - 1, y - 1, x + 256, y + 256), outline=(70, 72, 76))
        pen.text((x, y + 260), f'wall {i+1:02d} {K.WALL_ROLES[i]}', font=_font(12),
                 fill=(226, 206, 155))
    for i, tile in enumerate(flats):
        x = 24 + i * 136
        y = 720
        proof = Image.new('RGB', (128, 128))
        for yy in (0, 64):
            for xx in (0, 64):
                proof.paste(tile, (xx, yy))
        im.paste(proof, (x, y))
        pen.rectangle((x - 1, y - 1, x + 128, y + 128), outline=(70, 72, 76))
        pen.text((x, y + 132), f'flat {i+1:02d}', font=_font(11), fill=(226, 206, 155))
    # adjacent landmark pair used as a motif, not a continuous split image
    pair = Image.new('RGB', (256, 128))
    pair.paste(walls[6], (0, 0))
    pair.paste(walls[7], (128, 0))
    im.paste(pair, (690, 700))
    pen.rectangle((689, 699, 946, 828), outline=(70, 72, 76))
    pen.text((690, 682), 'walls 07 + 08 adjacent motif', font=_font(12),
             fill=(226, 206, 155))
    im.save(out_path)
    return im
