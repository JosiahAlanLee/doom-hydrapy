#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""
Argon monster art study renderer (derived work).

Derived from "Nullrun Monsters.py" (SPDX-License-Identifier: GPL-2.0-or-later),
supplied by the user. Original concepts and attribution: NULLRUN monster
bestiary / procedural monster generator, GPL-2.0-or-later. This file is an
independent art-study renderer for those four concepts; the original file is
left untouched at shared/codex/argon-monster-render-20261031/input/argon-original.py.

This renderer is self-contained: NumPy + Pillow only. It never reads input
files, calls a shell, evaluates strings or touches the network. All output is
deterministic from (seed, kind, variant, state, frame).

CLI:
  python monster_renderer.py --kind SURVEYOR --variant A --state idle --frame 0 \
      --seed 20261030 --size 128 --out frame.png
  python monster_renderer.py --all --outdir frames --seed 20261030
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys

import numpy as np
from PIL import Image

SIZE = 128
SS = 2                      # supersampling factor
H = SIZE * SS
STATES = ("idle", "walk", "warning", "attack", "hurt", "death")
KINDS = ("SURVEYOR", "WIRE_SHAMBLER", "THRESHOLD_MIMIC", "VORE_SPINDLE")
VARIANTS = {
    "SURVEYOR": ("TRIPOD", "GIMBAL"),
    "WIRE_SHAMBLER": ("BALLAST HUSK", "CABLE TOWER"),
    "THRESHOLD_MIMIC": ("LINTEL DOOR", "FALSE EXIT"),
    "VORE_SPINDLE": ("PENDULUM", "CEILING LURKER"),
}
DEFAULT_SEED = 20261030

# Fixed palette: worn industrial ochre / stone / bone / rust / cable, with
# restrained warm and green hazard accents. Rendered RGB is mapped to this
# palette so each variant keeps a stable, countable colour set.
PALETTE = np.array([
    [0x12, 0x10, 0x0d], [0x1b, 0x18, 0x13], [0x26, 0x21, 0x1a], [0x33, 0x2c, 0x22],
    [0x45, 0x39, 0x2b], [0x5a, 0x3b, 0x26], [0x74, 0x47, 0x2a],
    [0x86, 0x63, 0x2a], [0xa8, 0x7c, 0x33], [0xc3, 0x99, 0x47], [0xdc, 0xb8, 0x62],
    [0x5b, 0x59, 0x4f], [0x74, 0x71, 0x65], [0x90, 0x8c, 0x7e], [0xaa, 0xa5, 0x96],
    [0xc8, 0xbc, 0x9b], [0xe0, 0xd5, 0xb4],
    [0x3c, 0x5a, 0x20], [0x6d, 0x98, 0x32], [0xa2, 0xc7, 0x54],
    [0xd6, 0x88, 0x2a], [0xf2, 0xc0, 0x58], [0xe9, 0xef, 0xc4],
    [0x8a, 0x29, 0x1d], [0xbf, 0x43, 0x29], [0xf6, 0xf1, 0xd9],
    [0x25, 0x0f, 0x0a],
], dtype=np.float32) / 255.0
INK, COAL, SOOT, CHAR = PALETTE[0], PALETTE[1], PALETTE[2], PALETTE[3]
DIRT, RUST, RUST_HI = PALETTE[4], PALETTE[5], PALETTE[6]
OCHRE_D, OCHRE, OCHRE_L, OCHRE_HI = PALETTE[7], PALETTE[8], PALETTE[9], PALETTE[10]
STONE_D, STONE, STONE_L, STONE_HI = PALETTE[11], PALETTE[12], PALETTE[13], PALETTE[14]
BONE_D, BONE = PALETTE[15], PALETTE[16]
GREEN_D, GREEN, GREEN_HI = PALETTE[17], PALETTE[18], PALETTE[19]
AMBER, AMBER_HI, FLUOR = PALETTE[20], PALETTE[21], PALETTE[22]
RED, RED_HI, WHITE, MAW = PALETTE[23], PALETTE[24], PALETTE[25], PALETTE[26]

_YY, _XX = np.mgrid[0:H, 0:H]
X = (_XX.astype(np.float32) + 0.5) / SS
Y = (_YY.astype(np.float32) + 0.5) / SS

_hashes: dict[int, np.ndarray] = {}
def tex_field(seed: int, salt: int = 0) -> np.ndarray:
    """Deterministic 0..1 grain field; depends only on seed and salt."""
    key = (int(seed) * 32 + int(salt)) & 0xffffffff
    got = _hashes.get(key)
    if got is not None:
        return got
    xs = _XX.astype(np.uint32)
    ys = _YY.astype(np.uint32)
    n = xs * np.uint32(374761393) + ys * np.uint32(668265263) + np.uint32(key * 2654435761 & 0xffffffff)
    n ^= n >> np.uint32(13)
    n *= np.uint32(1274126177)
    n ^= n >> np.uint32(16)
    got = (n & np.uint32(0xffff)).astype(np.float32) / 65535.0
    if len(_hashes) > 200:
        _hashes.clear()
    _hashes[key] = got
    return got


def _shift(a: np.ndarray, dy: int, dx: int) -> np.ndarray:
    out = np.zeros_like(a)
    h, w = a.shape[:2]
    y0, y1 = max(0, dy), h + min(0, dy)
    x0, x1 = max(0, dx), w + min(0, dx)
    out[y0:y1, x0:x1] = a[max(0, -dy):h - max(0, dy), max(0, -dx):w - max(0, dx)]
    return out


def dilate(m: np.ndarray, px: int = 2) -> np.ndarray:
    out = m
    for dy, dx in ((px, 0), (-px, 0), (0, px), (0, -px),
                   (px, px), (px, -px), (-px, px), (-px, -px)):
        out = np.maximum(out, _shift(m, dy, dx))
    return out


def capsule(p0, p1, r: float, soft: float = 0.75) -> np.ndarray:
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    den = dx * dx + dy * dy + 1e-9
    t = np.clip(((X - p0[0]) * dx + (Y - p0[1]) * dy) / den, 0.0, 1.0)
    d = np.sqrt((X - (p0[0] + t * dx)) ** 2 + (Y - (p0[1] + t * dy)) ** 2)
    return np.clip((r + soft * 0.5 - d) / soft, 0.0, 1.0)


def ellipse(c, r, ry=None, ang: float = 0.0, soft: float = 0.75) -> np.ndarray:
    ry = r if ry is None else ry
    ca, sa = math.cos(ang), math.sin(ang)
    dx, dy = X - c[0], Y - c[1]
    u = ca * dx + sa * dy
    v = -sa * dx + ca * dy
    q = np.sqrt((u / max(r, 0.3)) ** 2 + (v / max(ry, 0.3)) ** 2)
    d = (q - 1.0) * min(r, ry)
    return np.clip(0.5 - d / soft, 0.0, 1.0)


def rect(x0, y0, x1, y1, rad: float = 1.0, soft: float = 0.75) -> np.ndarray:
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    hx, hy = (x1 - x0) * 0.5, (y1 - y0) * 0.5
    qx = np.abs(X - cx) - (hx - rad)
    qy = np.abs(Y - cy) - (hy - rad)
    d = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2) + np.minimum(np.maximum(qx, qy), 0) - rad
    return np.clip(0.5 - d / soft, 0.0, 1.0)


def poly(points, soft: float = 0.8) -> np.ndarray:
    pts = np.asarray(points, dtype=np.float32)
    inside = np.ones((H, H), dtype=bool)
    dmin = np.full((H, H), 1e9, dtype=np.float32)
    area = 0.0
    for i in range(len(pts)):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % len(pts)]
        area += ax * by - bx * ay
    sign = 1.0 if area >= 0 else -1.0
    for i in range(len(pts)):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % len(pts)]
        ex, ey = bx - ax, by - ay
        cross = ex * (Y - ay) - ey * (X - ax)
        inside &= (cross * sign) >= 0
        den = ex * ex + ey * ey + 1e-9
        t = np.clip(((X - ax) * ex + (Y - ay) * ey) / den, 0.0, 1.0)
        d = np.sqrt((X - (ax + t * ex)) ** 2 + (Y - (ay + t * ey)) ** 2)
        dmin = np.minimum(dmin, d)
    cov = np.where(inside, np.clip(0.5 + dmin / soft, 0.0, 1.0),
                   np.clip(0.5 - dmin / soft, 0.0, 1.0))
    return cov.astype(np.float32)


def rotp(p, pivot, deg: float):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    x, y = p[0] - pivot[0], p[1] - pivot[1]
    return (pivot[0] + ca * x - sa * y, pivot[1] + sa * x + ca * y)


def lerp(a, b, t):
    return a + (b - a) * t


def lp(p0, p1, t):
    return (lerp(p0[0], p1[0], t), lerp(p0[1], p1[1], t))


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def h01(*vals) -> float:
    """Stable scalar hash for seeded decorative jitter (not per-pixel)."""
    x = 0.0
    for i, v in enumerate(vals):
        x += (float(v) + 0.12345) * (12.9898 + i * 7.233)
    return (math.sin(x) * 43758.5453) % 1.0

class Sprite:
    """Supersampled straight-alpha canvas with palette-locked finish."""

    def __init__(self, seed: int):
        self.seed = int(seed)
        self.rgb = np.zeros((H, H, 3), dtype=np.float32)
        self.a = np.zeros((H, H), dtype=np.float32)
        self.salt = 0

    def _col(self, color):
        col = np.asarray(color, dtype=np.float32)
        if col.ndim == 1:
            return col[None, None, :]
        return col

    def blend(self, mask, color, opacity: float = 1.0):
        m = np.clip(mask * opacity, 0.0, 1.0)
        if m.max() <= 0:
            return
        col = self._col(color)
        self.rgb = self.rgb * (1 - m[..., None]) + col * m[..., None]
        self.a = self.a + m * (1 - self.a)

    def add(self, mask, color, gain: float = 1.0):
        m = np.clip(mask * gain, 0.0, 1.0)
        if m.max() <= 0:
            return
        col = self._col(color)
        self.rgb = np.clip(self.rgb + col * m[..., None], 0.0, 1.5)
        self.a = np.maximum(self.a, m)

    def part(self, mask, color, under: float = 1.4, tex: float = 0.10,
             opacity: float = 1.0, rim: bool = True, salt: int = 0,
             shade: float = 0.10):
        """Outline + base material plane + sparse wear + top rim light."""
        if under > 0:
            self.blend(dilate(mask, max(1, int(round(under * SS)))), INK, 0.92)
        ys, xs = np.nonzero(mask > 0.35)
        h = tex_field(self.seed, (salt + 7 * self.salt) & 255)
        factor = 1.0 + (h - 0.5) * tex
        if len(ys):
            y0, y1 = ys.min(), ys.max()
            if y1 > y0:
                v = np.clip((Y - (y0 + 0.5) / SS) / max(1e-3, (y1 - y0) / SS), 0, 1)
                factor = factor + shade * (0.55 - v)
        factor = np.clip(factor, 0.55, 1.45)
        col = self._col(color) * factor[..., None]
        self.blend(mask, col, opacity)
        if rim:
            top = np.clip(mask - _shift(mask, -max(2, SS), 0), 0, 1) * mask
            self.blend(top, np.clip(np.asarray(color) * 1.32, 0, 1), 0.55 * opacity)
            bot = np.clip(mask - _shift(mask, max(2, SS), 0), 0, 1) * mask
            self.blend(bot, INK, 0.30 * opacity)
        # sparse chips / pits, stable across frames
        chip = (h > 0.985) & (mask > 0.6)
        if chip.any():
            self.blend(chip.astype(np.float32), np.clip(np.asarray(color) * 1.5 + 0.03, 0, 1), 0.5 * opacity)
        pit = (h < 0.008) & (mask > 0.6)
        if pit.any():
            self.blend(pit.astype(np.float32), INK, 0.42 * opacity)

    def finish(self) -> Image.Image:
        a = self.a.reshape(SIZE, SS, SIZE, SS).mean(axis=(1, 3))
        pm = (self.rgb * self.a[..., None]).reshape(SIZE, SS, SIZE, SS, 3).mean(axis=(1, 3))
        rgb = pm / np.maximum(a[..., None], 1e-5)
        flat = rgb.reshape(-1, 3)
        d = ((flat[:, None, :] - PALETTE[None, :, :]) ** 2).sum(axis=-1)
        idx = d.argmin(axis=1)
        rgb = PALETTE[idx].reshape(rgb.shape)
        alpha = np.where(a >= 0.45, 255, 0).astype(np.uint8)
        out = np.zeros((SIZE, SIZE, 4), dtype=np.uint8)
        out[..., :3] = np.clip(rgb * 255.0 + 0.5, 0, 255).astype(np.uint8)
        out[..., 3] = alpha
        out[alpha == 0, :3] = 0
        return Image.fromarray(out, mode="RGBA")


# ---- reusable drawing vocabulary -------------------------------------------

def shadow(c: Sprite, center, rx, strength=0.30):
    c.blend(ellipse(center, rx, max(2.2, rx * 0.16), soft=1.2), INK, strength)


def rivet(c: Sprite, p, col=OCHRE_HI, r=0.9, salt=11):
    c.part(ellipse(p, r, r, soft=0.55), col, under=0.7, tex=0.06, rim=False, salt=salt)


def rivets(c: Sprite, p0, p1, n, col=OCHRE_HI, r=0.75, salt=12):
    for i in range(n):
        p = lp(p0, p1, (i + 0.5) / n)
        rivet(c, p, col, r, salt + i)


def limb(c: Sprite, pts, r, color, salt=0, collars=(), collar_col=STONE_D, taper=0.0):
    for i, (p0, p1) in enumerate(zip(pts, pts[1:])):
        rr = r * (1.0 - taper * i / max(1, len(pts) - 1))
        c.part(capsule(p0, p1, rr, soft=0.7), color, under=1.35, salt=salt + i)
    for i in collars:
        if 0 <= i < len(pts):
            c.part(ellipse(pts[i], r + 0.9, r + 0.9, soft=0.6), collar_col,
                   under=0.9, salt=salt + 20 + i, rim=False)


def cable(c: Sprite, pts, r=0.7, strands=3, spread=1.1, col=COAL, hi=STONE_D, salt=0, collars=True):
    for s in range(strands):
        off = (s - (strands - 1) / 2.0) * spread
        pp = [(p[0] + off * 0.55, p[1] - off) for p in pts]
        limb(c, pp, r, col, salt=salt + s * 3, taper=0.12)
    hp = [(p[0] - spread * 0.45, p[1] - spread * 0.35) for p in pts]
    limb(c, hp, max(0.38, r * 0.38), hi, salt=salt + 9, taper=0.2)
    if collars:
        for i in range(1, len(pts) - 1):
            c.part(ellipse(pts[i], r + spread * 0.9, r + spread * 0.9, soft=0.55),
                   DIRT, under=0.5, rim=False, salt=salt + 31 + i)


def arc(c: Sprite, pts, width=1.1, col=AMBER_HI, glow=0.55, salt=0):
    for p0, p1 in zip(pts, pts[1:]):
        c.add(capsule(p0, p1, width * 3.2, soft=1.8), col, 0.10 * glow)
        c.add(capsule(p0, p1, width * 1.7, soft=1.0), col, 0.34 * glow)
        c.part(capsule(p0, p1, width * 0.62, soft=0.55), WHITE, under=0.5, tex=0.02, rim=False)


def sparks(c: Sprite, at, n, spread, salt=0, col=AMBER_HI, f=0):
    for i in range(n):
        u = h01(salt, i, 1)
        v = h01(salt, i, 2)
        ang = u * math.tau
        dist = spread * (0.25 + 0.75 * v)
        p = (min(123.0, max(4.0, at[0] + math.cos(ang) * dist)),
             min(124.0, max(4.0, at[1] + math.sin(ang) * dist * 0.8)))
        c.add(ellipse(p, 0.7 + 0.7 * h01(salt, i, 3), 0.7), col, 0.9)
        if i % 3 == 0:
            q = (p[0] + math.cos(ang) * 2.2, p[1] + math.sin(ang) * 1.8)
            c.add(capsule(p, q, 0.35, 0.5), col, 0.55)


def dust(c: Sprite, at, n, spread, salt=0):
    for i in range(n):
        p = (min(123.0, max(4.0, at[0] + (h01(salt, i, 4) - 0.5) * spread)),
             min(124.0, max(4.0, at[1] + (h01(salt, i, 5) - 0.5) * spread * 0.7)))
        c.blend(ellipse(p, 0.7 + 0.8 * h01(salt, i, 6), 0.7), STONE, 0.55)


def teeth_v(c: Sprite, x, y0, y1, side, n, depth, col=BONE, salt=0, gap=0.0):
    step = (y1 - y0) / n
    for i in range(n):
        yy = y0 + step * (i + 0.5)
        tipx = x + side * (gap + depth * (0.55 + 0.45 * h01(salt, i, 7)))
        base0 = (x, yy - step * 0.34)
        base1 = (x, yy + step * 0.34)
        c.part(poly([base0, base1, (tipx, yy)], soft=0.55), col,
               under=0.8, tex=0.08, salt=salt + i, rim=False)


def teeth_h(c: Sprite, y, x0, x1, side, n, depth, col=BONE, salt=0, gap=0.0):
    step = (x1 - x0) / n
    for i in range(n):
        xx = x0 + step * (i + 0.5)
        tipy = y + side * (gap + depth * (0.55 + 0.45 * h01(salt, i, 8)))
        c.part(poly([(xx - step * 0.32, y), (xx + step * 0.32, y), (xx, tipy)], soft=0.55),
               col, under=0.8, tex=0.08, salt=salt + i, rim=False)


def ring(c: Sprite, p, r, th, col=AMBER, opacity=0.9, salt=0):
    m = np.clip(ellipse(p, r + th, r + th, soft=0.7) - ellipse(p, r - th, r - th, soft=0.7), 0, 1)
    c.blend(m, col, opacity)


def prism(c: Sprite, p, size, col_dark=COAL, col_side=GREEN, col_hi=AMBER_HI, ang=0.0, glow=1.0):
    """Octahedral spore / survey prism: four readable facets."""
    x, y = p
    s = size
    top = (x, y - s)
    bot = (x, y + s)
    left = (x - s * 0.78, y)
    right = (x + s * 0.78, y)
    c.part(poly([top, right, bot, left], soft=0.6), col_dark, under=0.8, tex=0.05, salt=3)
    c.part(poly([top, (x + 1.0, y), left], soft=0.55), np.clip(col_side * 1.1, 0, 1), under=0.4, tex=0.05, salt=4, rim=False)
    c.part(poly([(x, y - s * 0.9), right, (x, y + 0.5)], soft=0.55), np.clip(col_hi * 0.9, 0, 1), under=0.4, tex=0.05, salt=5, rim=False)
    c.add(ellipse((x + s * 0.1, y - s * 0.25), s * 0.3, s * 0.3), WHITE, 0.18 * glow)
    c.part(ellipse((x + s * 0.1, y - s * 0.25), s * 0.28, s * 0.28, soft=0.5), FLUOR,
           under=0.35, tex=0.02, rim=False)
    ring(c, p, s * 0.75, max(0.5, s * 0.08), col_hi, 0.30 * glow)


def eye(c: Sprite, p, r, charge=0.0, col=AMBER, dead=False, salt=0):
    if dead:
        c.part(ellipse(p, r, r, soft=0.6), MAW, under=0.8, tex=0.05, salt=salt, rim=False)
        c.add(ellipse((p[0], p[1] + r * 0.3), r * 0.5, r * 0.22), RED, 0.25)
        return
    c.part(ellipse(p, r + 1.4, r + 1.4, soft=0.6), COAL, under=0.8, tex=0.04, salt=salt, rim=False)
    c.add(ellipse(p, r * 2.5, r * 2.5), col, 0.10 + 0.16 * charge)
    c.part(ellipse(p, r, r, soft=0.55), np.clip(col * (0.8 + 0.35 * charge), 0, 1),
           under=0.6, tex=0.05, salt=salt + 1, rim=False)
    c.part(ellipse(p, r * 0.52, r * 0.52, soft=0.5), WHITE, under=0.3, tex=0.02, salt=salt + 2, rim=False)
    # three closing iris blades
    for i in range(3):
        a = math.radians(20 + i * 120 + 8 * charge + 40 * charge)
        p0 = (p[0] + math.cos(a) * r * 0.92, p[1] + math.sin(a) * r * 0.92)
        p1 = (p[0] + math.cos(a + 0.5) * r * (0.35 - 0.15 * charge),
              p[1] + math.sin(a + 0.5) * r * (0.35 - 0.15 * charge))
        c.part(capsule(p0, p1, 0.55, 0.5), SOOT, under=0.4, tex=0.02, rim=False, salt=salt + 5 + i)
    if charge > 0.25:
        ring(c, p, r + 2.6 + 1.1 * charge, 0.55, col, 0.4 + 0.4 * charge)


def beam(c: Sprite, p0, p1, width=1.2, gain=1.0, salt=0):
    ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    c.blend(capsule(p0, p1, width * 3.4, soft=1.4), np.clip(AMBER * 0.9, 0, 1), 0.30 * gain)
    c.blend(capsule(p0, p1, width * 1.9, soft=0.9), AMBER_HI, 0.55 * gain)
    c.add(capsule(p0, p1, width * 0.75, soft=0.5), WHITE, 0.85 * gain)
    for t in (0.25, 0.55, 0.8):
        q = lp(p0, p1, t)
        c.add(ellipse((q[0] + math.cos(ang) * 3, q[1] + math.sin(ang) * 3), 1.1, 1.1), AMBER_HI, 0.55)
    sparks(c, p1, 4, width * 2.4, salt=salt, f=2)

# ---- motion curves ---------------------------------------------------------

def motion(state: str, f: int, seed: int) -> dict:
    ph = math.tau * f / 4.0
    j = h01(seed, f, 3) - 0.5
    m = dict(bob=0.0, sway=0.0, lean=0.0, crouch=0.0, jaw=0.0, charge=0.0,
             fire=0.0, hurt=0.0, death=0.0, flash=0.0, step=0.0, f=f)
    if state == "idle":
        m["bob"] = 1.1 * math.sin(ph + seed % 7) + 0.4 * j
        m["sway"] = 0.7 * math.sin(ph * 0.5 + seed % 5)
    elif state == "walk":
        # asymmetric four-phase cycle: all four source frames differ
        m["bob"] = 1.9 * abs(math.sin(ph)) + 0.5 * math.cos(ph)
        m["sway"] = 2.4 * math.sin(ph) + 0.8 * math.cos(ph)
        m["step"] = math.sin(ph) - 0.4 * math.cos(ph)
        m["lean"] = 2.0
    elif state == "warning":
        m["charge"] = (0.18, 0.45, 0.72, 0.95)[f]
        m["crouch"] = (0.8, 1.8, 2.8, 3.8)[f]
        m["lean"] = -1.5 - 2.5 * f / 3
        m["sway"] = 0.6 * math.sin(f * 2.1 + seed % 9)
    elif state == "attack":
        m["fire"] = (0.25, 1.0, 0.7, 0.18)[f]
        m["lean"] = (-4.0, 8.0, 6.0, 2.0)[f]
        m["sway"] = (-1.0, 3.0, 2.0, 1.0)[f]
        m["jaw"] = (0.35, 1.0, 0.8, 0.3)[f]
        m["charge"] = (0.8, 1.0, 0.6, 0.2)[f]
        m["crouch"] = (1.0, 0.0, 0.0, 0.5)[f]
    elif state == "hurt":
        m["hurt"] = (1.0, 0.75, 0.5, 0.25)[f]
        m["lean"] = (-10.0, -7.0, -4.0, -2.0)[f]
        m["sway"] = (-4.0, -3.0, -2.0, -1.0)[f]
        m["jaw"] = (0.8, 0.55, 0.35, 0.2)[f]
        m["flash"] = 1.0 if f == 0 else 0.0
    elif state == "death":
        m["death"] = (0.22, 0.52, 0.80, 1.0)[f]
        m["lean"] = (6.0, 20.0, 45.0, 78.0)[f]
        m["crouch"] = (2.0, 8.0, 16.0, 0.0)[f]
    return m


def flash(c: Sprite, m):
    if m["flash"]:
        # Tint the solid mass only; never lift the faint contact shadow or dust
        # into the alpha cutout (that used to touch the bottom margin).
        c.blend((c.a > 0.62).astype(np.float32), FLUOR, 0.20)


# ---- SURVEYOR --------------------------------------------------------------

def _surveyor_head(c, hc, charge, fire, lean, salt, dead=False):
    rx, ry = 14.5, 10.5
    oct_pts = []
    for i in range(8):
        a = math.pi / 8 + i * math.pi / 4
        oct_pts.append((hc[0] + math.cos(a) * rx, hc[1] + math.sin(a) * ry))
    c.part(poly(oct_pts, soft=0.7), STONE_D, under=1.8, tex=0.10, salt=salt)
    inner = [(hc[0] + (p[0] - hc[0]) * 0.84, hc[1] + (p[1] - hc[1]) * 0.82) for p in oct_pts]
    c.part(poly(inner, soft=0.65), OCHRE_D, under=0.9, tex=0.12, salt=salt + 1)
    # top cap + sight vane
    c.part(rect(hc[0] - 8, hc[1] - ry - 2.0, hc[0] + 8, hc[1] - ry + 1.0, 1.2),
           OCHRE_L, under=0.9, salt=salt + 2)
    c.part(poly([(hc[0] - 7, hc[1] - ry + 1), (hc[0] - 3, hc[1] - ry - 5),
                 (hc[0] + 1, hc[1] - ry + 1)], soft=0.5), STONE_L, under=0.7, salt=salt + 3)
    # panel line and rivets
    c.part(capsule((hc[0] - 10, hc[1] + 4.5), (hc[0] + 7, hc[1] + 4.5), 0.42), CHAR,
           under=0.3, rim=False, salt=salt + 4)
    rivet(c, (hc[0] - 11, hc[1] - 3), OCHRE_HI, 0.8, salt + 5)
    rivet(c, (hc[0] + 3, hc[1] - 5), OCHRE_HI, 0.8, salt + 6)
    # emitter hood on right
    c.part(ellipse((hc[0] + 10.5, hc[1] + 1.0), 4.6, 5.4, soft=0.6), STONE_D,
           under=1.0, salt=salt + 7)
    eye(c, (hc[0] + 2.4, hc[1] + 1.2), 5.6, charge=charge, dead=dead, salt=salt + 8)
    c.part(ellipse((hc[0] + 10.8, hc[1] + 1.0), 2.5, 3.0, soft=0.5), MAW,
           under=0.5, rim=False, salt=salt + 9)
    c.add(ellipse((hc[0] + 10.8, hc[1] + 1.0), 2.0, 2.4), AMBER, 0.18 + 0.25 * charge)
    # hazard tag
    c.part(rect(hc[0] - 12.5, hc[1] + 6.0, hc[0] - 7.5, hc[1] + 8.2, 0.4),
           GREEN_D, under=0.5, rim=False, salt=salt + 10)
    if charge > 0.5:
        sparks(c, (hc[0] + 2, hc[1] - 1), 3, 6.0, salt=salt + 11)


def draw_surveyor_a(c: Sprite, state, f, seed):
    m = motion(state, f, seed)
    s = seed % 97
    if state == "death":
        draw_surveyor_a_death(c, f, seed)
        return
    hip = (64 + m["sway"], 61 + m["bob"] + 0.8 * m["crouch"])
    shadow(c, (64, 123.2), 28 + 1.5 * m["crouch"], 0.30)
    # rear leg
    limb(c, [hip, (60, 88), (61, 114), (61, 120)], 2.6, OCHRE_D, salt=10, taper=0.15)
    c.part(ellipse((61, 121.3), 4.2, 1.9, soft=0.6), STONE_D, under=0.8, salt=11, rim=False)
    # front legs
    lift_l = max(0.0, m["step"]) * 4
    lift_r = max(0.0, -m["step"]) * 4
    knee_l = (39 + m["sway"] * 0.2, 88 + 0.5 * m["crouch"])
    knee_r = (90 + m["sway"] * 0.2, 88 + 0.5 * m["crouch"])
    foot_l = (27 + m["sway"] * 0.15 - 2 * m["step"], 121 - lift_l)
    foot_r = (101 + m["sway"] * 0.15 - 2 * m["step"], 121 - lift_r)
    limb(c, [(58 + m["sway"], hip[1] + 1), knee_l, foot_l], 3.1, OCHRE, salt=12,
         collars=(1,), collar_col=STONE_D, taper=0.10)
    limb(c, [(70 + m["sway"], hip[1] + 1), knee_r, foot_r], 3.1, OCHRE, salt=13,
         collars=(1,), collar_col=STONE_D, taper=0.10)
    for fp in (foot_l, foot_r):
        c.part(ellipse((fp[0], fp[1] + 0.8), 4.4, 2.0, soft=0.6), STONE_D,
               under=0.9, salt=14, rim=False)
    # crossbars
    c.part(capsule((36, 84), (92, 84), 1.25, 0.6), STONE_D, under=0.9, salt=15)
    c.part(capsule((47, 96), (81, 96), 0.95, 0.55), RUST, under=0.7, salt=16)
    # plumb line and bob
    c.part(capsule((64 + m["sway"], 68), (64 + m["sway"] * 0.6, 100), 0.55, 0.6),
           SOOT, under=0.5, rim=False, salt=17)
    bob = (64 + m["sway"] * 0.6, 102)
    c.part(poly([(bob[0] - 2.2, bob[1] - 3.6), (bob[0] + 2.2, bob[1] - 3.6),
                 (bob[0] + 3.3, bob[1] + 0.6), (bob[0] + 1.6, bob[1] + 3.8),
                 (bob[0] - 1.6, bob[1] + 3.8), (bob[0] - 3.3, bob[1] + 0.6)], soft=0.55),
           OCHRE_L, under=1.0, salt=18)
    # column + counterweight
    c.part(capsule((64 + m["sway"], 40), (hip[0], hip[1] + 2), 3.3, 0.7), OCHRE_D,
           under=1.4, salt=19)
    c.part(rect(hip[0] - 6.5, hip[1] + 1, hip[0] + 6.5, hip[1] + 10, 1.8),
           RUST, under=1.0, salt=20)
    rivets(c, (hip[0] - 4.5, hip[1] + 3.5), (hip[0] + 4.5, hip[1] + 3.5), 3, STONE_L, 0.7, salt=21)
    c.part(rect(hip[0] - 5, hip[1] + 11, hip[0] + 5, hip[1] + 13.5, 0.6),
           GREEN_D, under=0.6, rim=False, salt=22)
    # yoke
    c.part(rect(46, 40, 82, 47, 2.0), STONE_L, under=1.4, salt=23)
    rivets(c, (49, 43.5), (79, 43.5), 5, RUST_HI, 0.8, salt=24)
    c.part(capsule((50, 39.5), (54, 36.5), 1.0, 0.5), STONE_D, under=0.6, salt=25)
    c.part(capsule((78, 39.5), (74, 36.5), 1.0, 0.5), STONE_D, under=0.6, salt=26)
    # hazard ticks on legs
    for p in (knee_l, knee_r):
        c.part(rect(p[0] - 1.1, p[1] + 3.2, p[0] + 1.1, p[1] + 6.0, 0.3),
               GREEN, under=0.4, rim=False, salt=27)
    hc = (64 + m["sway"] + 0.32 * m["lean"], 26.5 + m["bob"] + 0.5 * m["crouch"] + 0.12 * abs(m["lean"]))
    _surveyor_head(c, hc, m["charge"], m["fire"], m["lean"], 30 + s)
    # charge / fire cues
    if m["charge"] > 0.1 and m["fire"] < 0.8:
        ring(c, (hc[0] + 2.4, hc[1] + 1.2), 9.0 + 1.4 * m["charge"], 0.55, AMBER, 0.30 + 0.5 * m["charge"])
        for i in range(3):
            a = math.radians(-60 + i * 60 + 25 * m["charge"])
            p0 = (hc[0] + 2.4 + math.cos(a) * 11.5, hc[1] + 1.2 + math.sin(a) * 8.0)
            p1 = (hc[0] + 2.4 + math.cos(a) * 14.0, hc[1] + 1.2 + math.sin(a) * 10.0)
            c.add(capsule(p0, p1, 0.7, 0.5), AMBER_HI, 0.5 + 0.5 * m["charge"])
        if m["charge"] > 0.7:
            dust(c, (64, 110), 4, 26, salt=40 + f)
    if m["fire"] > 0.15:
        gain = 0.35 + 0.65 * m["fire"]
        p0 = (hc[0] + 12, hc[1] + 1)
        p1 = (118.0, hc[1] + 1 + 2.0 * math.sin(f * 1.7))
        if state == "attack" and f in (1, 2):
            beam(c, p0, p1, 1.3, gain, salt=50 + f)
        else:
            c.add(ellipse((hc[0] + 12, hc[1] + 1), 3.4, 3.4), AMBER_HI, 0.5)
            sparks(c, (hc[0] + 12, hc[1] + 1), 4, 7, salt=51 + f)
    if m["hurt"] > 0.2:
        sparks(c, (hip[0] + 4, hip[1] - 2), 4, 10, salt=60 + f)
        c.part(capsule((42, 83), (50, 86), 0.5, 0.5), COAL, under=0.3, rim=False, salt=61)
    flash(c, m)


def draw_surveyor_a_death(c: Sprite, f, seed):
    k = (0.22, 0.52, 0.80, 1.0)[f]
    shadow(c, (68, 122.5), 30 + 10 * k, 0.32)
    hip = lp((64, 61), (66, 112), ease(k))
    head = lp((64, 26.5), (92, 103), ease(k))
    # legs buckle and splay
    limb(c, [(60, hip[1]), (52, lerp(88, 114, k)), (22, 121)], 3.0, OCHRE_D,
         salt=70, taper=0.15)
    limb(c, [(68, hip[1]), (82, lerp(88, 116, k)), (108, 120)], 3.0, OCHRE_D,
         salt=71, taper=0.15)
    limb(c, [(64, hip[1]), (46, lerp(96, 117, k)), (48, 120)], 2.2, OCHRE_D,
         salt=72, taper=0.2)
    for fp in ((22, 121), (108, 120), (48, 120)):
        c.part(ellipse((fp[0], fp[1] + 1), 4.2, 1.9, soft=0.6), STONE_D,
               under=0.8, salt=73, rim=False)
    # toppling column and counterweight
    base = lp((64, 40), (76, 104), ease(k))
    c.part(capsule(base, (hip[0], hip[1] + 1), 3.2, 0.7), OCHRE_D, under=1.3, salt=74)
    cw = lp((64, 70), (80, 114), ease(k))
    c.part(rect(cw[0] - 6, cw[1] - 4, cw[0] + 6, cw[1] + 5, 1.5), RUST,
           under=1.0, salt=75)
    c.part(rect(cw[0] - 4.5, cw[1] + 6, cw[0] + 4.5, cw[1] + 8, 0.5), GREEN_D,
           under=0.5, rim=False, salt=76)
    # fallen crossbars
    c.part(capsule(lp((36, 84), (22, 119), k), lp((92, 84), (70, 118), k), 1.2, 0.6),
           STONE_D, under=0.8, salt=77)
    c.part(capsule(lp((47, 96), (38, 120), k), lp((81, 96), (94, 119), k), 0.9, 0.55),
           RUST, under=0.6, salt=78)
    # plumb line snapped, bob on the floor
    c.part(capsule((64, 68), (66, lerp(100, 112, k)), 0.5, 0.6), SOOT,
           under=0.4, rim=False, salt=79)
    bob = lp((64, 102), (76, 119), k)
    c.part(poly([(bob[0] - 2.2, bob[1] - 3.2), (bob[0] + 2.2, bob[1] - 3.2),
                 (bob[0] + 3.2, bob[1] + 0.5), (bob[0] + 1.5, bob[1] + 3.2),
                 (bob[0] - 1.5, bob[1] + 3.2), (bob[0] - 3.2, bob[1] + 0.5)], soft=0.55),
           OCHRE_L, under=0.9, salt=80)
    # housing lies on its side
    ang = 68 * ease(k)
    rx, ry = 14.5, 10.5
    pts = []
    for i in range(8):
        a = math.pi / 8 + i * math.pi / 4
        q = (math.cos(a) * rx, math.sin(a) * ry)
        pts.append(rotp((head[0] + q[0], head[1] + q[1]), head, ang))
    c.part(poly(pts, soft=0.7), STONE_D, under=1.6, tex=0.10, salt=81)
    c.part(ellipse((head[0], head[1]), 10.5, 6.5, ang=math.radians(ang), soft=0.6),
           OCHRE_D, under=0.9, salt=82)
    # dead lens, dim ember
    lens = rotp((head[0] + 4, head[1] + 1), head, ang)
    c.part(ellipse(lens, 5.2, 4.0, ang=math.radians(ang), soft=0.6), MAW,
           under=0.8, rim=False, salt=83)
    c.add(ellipse((lens[0], lens[1] + 0.5), 1.6, 1.0), RED, 0.25)
    c.part(ellipse((head[0] + 10.5, head[1] + 1), 3.0, 2.4, ang=math.radians(ang), soft=0.5),
           COAL, under=0.5, rim=False, salt=84)
    # rubble and dust
    for i in range(5):
        p = (30 + 15 * h01(seed, i, 11), 116 + 4 * h01(seed, i, 12))
        c.part(poly([(p[0] - 2, p[1] + 2), (p[0] - 1, p[1] - 2), (p[0] + 2.5, p[1] - 1),
                     (p[0] + 2, p[1] + 2)], soft=0.5), STONE_D, under=0.5,
               tex=0.03, salt=85 + i, rim=False)
    if f >= 2:
        dust(c, (70, 112), 5, 24, salt=90 + f)
    if f == 3:
        c.part(capsule((78, 116), (90, 119), 0.45, 0.5), GREEN_D, under=0.3,
               rim=False, salt=95)

def draw_surveyor_b(c: Sprite, state, f, seed):
    m = motion(state, f, seed)
    if state == "death":
        draw_surveyor_b_death(c, f, seed)
        return
    s = seed % 89
    body = (64 + m["sway"] * 0.7, 72 + m["bob"] + 1.1 * m["crouch"])
    shadow(c, (64, 123.2), 34, 0.32)
    # four outrigger legs: rear pair darker
    lift = m["step"] * 2.2
    limb(c, [(52, 79), (46, 101), (42 - lift, 121)], 3.0, OCHRE_D, salt=10, taper=0.15)
    limb(c, [(76, 79), (82, 101), (86 + lift, 121)], 3.0, OCHRE_D, salt=11, taper=0.15)
    limb(c, [(45, 81), (27, 100), (23 + lift, 121)], 3.4, OCHRE, salt=12,
         collars=(1,), collar_col=STONE_D, taper=0.12)
    limb(c, [(83, 81), (101, 100), (105 - lift, 121)], 3.4, OCHRE, salt=13,
         collars=(1,), collar_col=STONE_D, taper=0.12)
    for fp in ((42, 121), (86, 121), (23, 121), (105, 121)):
        c.part(ellipse((fp[0], fp[1] + 1), 4.1, 1.9, soft=0.6), STONE_D,
               under=0.8, salt=14, rim=False)
    # body deck
    c.part(rect(41, 63, 87, 84, 4.0), STONE_D, under=1.6, salt=15)
    c.part(rect(45, 66, 83, 78, 2.2), OCHRE_D, under=0.9, salt=16)
    c.part(rect(47, 80, 81, 85, 1.2), RUST, under=0.8, salt=17)
    rivets(c, (47, 69), (81, 69), 5, OCHRE_HI, 0.75, salt=18)
    c.part(rect(48, 73, 59, 76.5, 0.5), GREEN_D, under=0.4, rim=False, salt=19)
    c.part(rect(67, 73, 78, 76.5, 0.5), GREEN_D, under=0.4, rim=False, salt=20)
    # A-frame struts and twin prism drums
    c.part(capsule((49, 66), (44, 48), 1.6, 0.6), STONE_L, under=0.9, salt=21)
    c.part(capsule((79, 66), (84, 48), 1.6, 0.6), STONE_L, under=0.9, salt=22)
    for side, dx in ((-1, 0), (1, 1)):
        cx = 44 if dx == 0 else 84
        cy = 46 + m["bob"] * 0.4
        c.part(ellipse((cx, cy), 11.5, 10.0, soft=0.7), COAL, under=1.6, salt=23 + dx * 10)
        c.part(ellipse((cx, cy), 9.8, 8.4, soft=0.7), OCHRE_D, under=0.9, salt=24 + dx * 10)
        c.part(ellipse((cx, cy), 9.8, 2.0, soft=0.5), STONE_D, under=0.5, rim=False, salt=25 + dx * 10)
        # drum lens rotates with charge
        lx = cx + 1.0
        ly = cy + 0.4
        eye(c, (lx, ly), 4.0, charge=m["charge"], salt=26 + dx * 10)
        c.part(rect(cx - 7, cy + 7.0, cx + 7, cy + 9.3, 0.5), GREEN_D,
               under=0.5, rim=False, salt=27 + dx * 10)
    # central mast and crown
    mast_top = 35 + 2.0 * m["crouch"]
    c.part(capsule((64, 66), (64 + m["sway"] * 0.2, mast_top), 2.4, 0.6), STONE_L,
           under=1.0, salt=40)
    c.part(capsule((57, 39), (71, 39), 0.9, 0.5), STONE_D, under=0.6, salt=41)
    prism(c, (64 + m["sway"] * 0.2, mast_top - 4.5), 5.0, col_side=OCHRE, col_hi=GREEN_HI,
          glow=0.5 + m["charge"])
    # counterweight chain and ballast
    c.part(capsule((64, 85), (64, 92), 0.6, 0.5), SOOT, under=0.4, rim=False, salt=42)
    cw = (64 + m["sway"] * 0.5, 96)
    c.part(ellipse(cw, 7.0, 8.4, soft=0.65), RUST, under=1.2, salt=43)
    c.part(rect(cw[0] - 5.5, cw[1] - 1.5, cw[0] + 5.5, cw[1] + 1.2, 0.4),
           GREEN_D, under=0.4, rim=False, salt=44)
    rivets(c, (cw[0] - 4.5, cw[1] - 4), (cw[0] + 4.5, cw[1] - 4), 3, OCHRE_HI, 0.7, salt=45)
    if m["charge"] > 0.1 and m["fire"] < 0.8:
        for dx in (44, 84):
            ring(c, (dx, 46.4), 6.0 + 1.2 * m["charge"], 0.5, AMBER, 0.25 + 0.5 * m["charge"])
        ring(c, (64, mast_top - 4.5), 6.5, 0.5, GREEN_HI, 0.5 * m["charge"])
        if m["charge"] > 0.65:
            sparks(c, (64, 39), 4, 10, salt=46 + f)
    if state == "attack" and f in (1, 2):
        gate = (104.0, 52.0)
        beam(c, (45, 47), gate, 0.9, 0.8, salt=47 + f)
        beam(c, (83, 47), gate, 0.9, 0.8, salt=48 + f)
        beam(c, gate, (118.0, 53.0), 1.5, 0.95, salt=49 + f)
        sparks(c, gate, 5, 12, salt=50 + f)
    elif m["fire"] > 0.1:
        for dx in (44, 84):
            c.add(ellipse((dx + 1, 46.4), 3.0, 3.0), AMBER_HI, 0.45)
    if m["hurt"] > 0.15:
        sparks(c, (84, 43), 5, 12, salt=60 + f)
        c.part(capsule((82, 41), (88, 47), 0.5, 0.5), COAL, under=0.3, rim=False, salt=61)
    flash(c, m)


def draw_surveyor_b_death(c: Sprite, f, seed):
    k = (0.22, 0.52, 0.80, 1.0)[f]
    shadow(c, (64, 122.5), 38 + 8 * k, 0.34)
    bodyy = lerp(72, 104, ease(k))
    # folded legs
    limb(c, [(48, bodyy + 8), (36, lerp(101, 116, k)), (26, 121)], 3.2, OCHRE_D, salt=70)
    limb(c, [(80, bodyy + 8), (94, lerp(101, 116, k)), (104, 121)], 3.2, OCHRE_D, salt=71)
    limb(c, [(56, bodyy + 8), (52, lerp(103, 118, k)), (48, 121)], 2.6, OCHRE_D, salt=72)
    limb(c, [(74, bodyy + 8), (74, lerp(103, 118, k)), (80, 121)], 2.6, OCHRE_D, salt=73)
    # collapsed deck
    c.part(rect(42, bodyy - 8, 86, bodyy + 9, 4.0), STONE_D, under=1.4, salt=74)
    c.part(rect(48, bodyy - 4, 80, bodyy + 6, 2.0), OCHRE_D, under=0.9, salt=75)
    c.part(rect(46, bodyy + 7, 84, bodyy + 11, 1.0), RUST, under=0.7, salt=76)
    # fallen drums
    for cx, cy in ((lerp(44, 30, k), lerp(46, 115, k)), (lerp(84, 98, k), lerp(46, 113, k))):
        c.part(ellipse((cx, cy), 11.0, 8.0, ang=math.radians(25), soft=0.7), COAL,
               under=1.4, salt=77)
        c.part(ellipse((cx, cy), 9.0, 6.2, ang=math.radians(25), soft=0.65), OCHRE_D,
               under=0.8, salt=78)
        c.part(ellipse((cx + 2, cy + 1), 3.4, 3.0, soft=0.5), MAW, under=0.5,
               rim=False, salt=79)
        c.add(ellipse((cx + 2, cy + 1), 1.3, 1.1), RED, 0.22)
    # snapped mast lying across
    mast = lp((64, 35), (88, 113), ease(k))
    c.part(capsule((64, bodyy), mast, 2.0, 0.6), STONE_L, under=0.9, salt=80)
    prism(c, (mast[0] + 3, mast[1] - 1), 3.6, col_side=STONE, col_hi=GREEN_D, glow=0.15)
    # counterweight half buried
    cw = lp((64, 96), (58, 118), ease(k))
    c.part(ellipse(cw, 7.0, 7.0, soft=0.65), RUST, under=1.0, salt=81)
    c.part(ellipse((cw[0] - 1, cw[1] - 2), 3.5, 1.5, soft=0.5), DIRT, under=0.4,
           rim=False, salt=82)
    for i in range(6):
        p = (30 + 20 * h01(seed, i, 21), 115 + 5 * h01(seed, i, 22))
        c.part(poly([(p[0] - 2, p[1] + 2), (p[0] - 1, p[1] - 2.5), (p[0] + 2.5, p[1] - 1),
                     (p[0] + 2, p[1] + 2)], soft=0.5), STONE_D, under=0.5,
               tex=0.03, salt=83 + i, rim=False)
    if f >= 2:
        dust(c, (64, 114), 6, 28, salt=90 + f)
    if f == 3:
        c.part(rect(44, 118, 54, 119, 0.3), GREEN_D, under=0.3, rim=False, salt=96)


# ---- WIRE_SHAMBLER ---------------------------------------------------------

def draw_shambler_a(c: Sprite, state, f, seed):
    m = motion(state, f, seed)
    if state == "death":
        draw_shambler_a_death(c, f, seed)
        return
    s = seed % 83
    hipy = 76 + m["bob"] + 0.8 * m["crouch"]
    sway = m["sway"] * 0.7
    shadow(c, (64, 123.2), 30, 0.34)
    # bowed legs
    lift = m["step"] * 2.0
    limb(c, [(52 + sway, hipy), (44, 99), (42 - lift, 121)], 4.0, COAL, salt=10, taper=0.12)
    limb(c, [(76 + sway, hipy), (84, 99), (88 + lift, 121)], 4.0, COAL, salt=11, taper=0.12)
    limb(c, [(45, 101), (42, 110), (40, 120)], 2.4, RUST, salt=12, taper=0.2)
    limb(c, [(85, 101), (88, 110), (90, 120)], 2.4, RUST, salt=13, taper=0.2)
    for fp in ((42, 121), (88, 121)):
        c.part(ellipse((fp[0], fp[1] + 1), 5.2, 2.2, soft=0.6), STONE_D,
               under=0.8, salt=14, rim=False)
    # torso masses
    c.part(ellipse((62 + sway, 60 + 0.4 * m["bob"]), 25, 16, soft=0.8), COAL,
           under=1.6, salt=15)
    c.part(ellipse((65 + sway, 42 + 0.3 * m["bob"]), 27, 13.5, soft=0.8), STONE_D,
           under=1.5, salt=16)
    c.part(ellipse((62 + sway, 58), 18, 10, soft=0.7), DIRT, under=0.8, salt=17)
    # exposed ribs / boiler plate
    c.part(rect(46, 54, 63, 66, 2.5), RUST, under=1.0, salt=18)
    rivets(c, (49, 57), (60, 57), 3, OCHRE_HI, 0.7, salt=19)
    for i in range(3):
        c.part(capsule((50 + i * 9, 46), (45 + i * 10, 53), 0.8, 0.55), BONE_D,
               under=0.5, salt=20 + i)
    # cable spine
    cable(c, [(72 + sway, 34), (68, 48), (62, 64), (58, 76)], r=0.7, strands=3,
          spread=1.3, salt=25)
    # right rebar arm
    c.part(ellipse((98 + sway, 44), 8.0, 6.0, soft=0.7), STONE_D, under=1.2, salt=30)
    arm_r = [(100 + sway, 47), (111 + 1.5 * m["lean"], 70), (100, 105)]
    limb(c, arm_r, 1.8, RUST_HI, salt=31, taper=0.1)
    for i in range(2):
        p0 = lp(arm_r[0], arm_r[1], 0.35 + i * 0.3)
        c.part(capsule((p0[0] - 3, p0[1]), (p0[0] + 3, p0[1] + 1), 0.5, 0.5), STONE,
               under=0.4, rim=False, salt=32 + i)
    for k2 in range(3):
        a = math.radians(-60 + k2 * 55)
        p0 = (100, 106)
        p1 = (p0[0] + math.cos(a) * 8, p0[1] + math.sin(a) * 5 + 4)
        c.part(capsule(p0, p1, 1.0, 0.5), RUST, under=0.6, salt=35 + k2)
    # left cable arm, long drag
    cable(c, [(28 + sway, 47), (18, 72), (27, 104), (26, 114)], r=1.0, strands=3,
          spread=1.5, salt=38)
    for k2 in range(3):
        p0 = (26, 115)
        p1 = (16 + k2 * 9, 120)
        c.part(capsule(p0, p1, 0.8, 0.55), COAL, under=0.5, salt=41 + k2)
    # head with vertical warning maw
    hc = (73 + sway + 0.25 * m["lean"], 44 + 0.4 * m["crouch"])
    c.part(ellipse(hc, 10.5, 11.0, soft=0.75), STONE_D, under=1.4, salt=44)
    c.part(ellipse(hc, 8.5, 9.0, soft=0.7), COAL, under=0.8, salt=45)
    jaw = 0.4 + 5.5 * m["jaw"] + 1.5 * m["charge"]
    gap = min(7.0, jaw)
    c.part(rect(hc[0] - gap / 2, hc[1] - 8, hc[0] + gap / 2, hc[1] + 8, 1.0), MAW,
           under=0.6, rim=False, salt=46)
    if m["jaw"] > 0.15 or state == "warning":
        c.add(ellipse((hc[0], hc[1] + 1), 4 + 4 * m["jaw"], 5), AMBER, 0.15 + 0.3 * m["jaw"])
    teeth_v(c, hc[0] - gap / 2 - 0.3, hc[1] - 6.5, hc[1] + 6.5, 1, 5,
            3.0 + 2.0 * m["jaw"], BONE_D, salt=47)
    teeth_v(c, hc[0] + gap / 2 + 0.3, hc[1] - 6.5, hc[1] + 6.5, -1, 5,
            3.0 + 2.0 * m["jaw"], BONE_D, salt=48)
    c.part(ellipse((hc[0] - 6.5, hc[1] - 4), 1.7, 1.7, soft=0.55), GREEN_HI,
           under=0.6, rim=False, salt=49)
    c.add(ellipse((hc[0] - 6.5, hc[1] - 4), 3.0, 3.0), GREEN, 0.2 + 0.5 * m["charge"])
    # shoulder spikes and hazard plate
    for i, p in enumerate(((88 + sway, 36), (94 + sway, 38))):
        c.part(poly([(p[0] - 2, p[1] + 2), (p[0], p[1] - 6), (p[0] + 2, p[1] + 2)], soft=0.5),
               STONE_L, under=0.7, salt=50 + i)
    c.part(rect(54, 68, 64, 73, 0.7), GREEN_D, under=0.5, rim=False, salt=52)
    c.add(ellipse((97, 38), 2.2, 2.2), AMBER_HI, 0.25 + 0.5 * m["charge"])
    if m["charge"] > 0.35 and state in ("warning", "attack"):
        pts = [(hc[0] - 2, hc[1] - 10), (hc[0] - 12, hc[1] - 18), (hc[0] + 2, hc[1] - 22),
               (hc[0] + 15, hc[1] - 16), (hc[0] + 25, hc[1] - 24)]
        arc(c, pts, 0.9, AMBER_HI, 0.5 + 0.5 * m["charge"], salt=53 + f)
    if state == "attack" and f in (1, 2):
        bolt = [(hc[0] + 5, hc[1] + 1), (88, 52), (100, 44), (108, 58), (117, 52)]
        arc(c, bolt, 1.7, AMBER_HI, 1.0, salt=60 + f)
        sparks(c, (117, 52), 6, 9, salt=61 + f)
    if m["hurt"] > 0.15:
        sparks(c, (88, 50), 5, 12, salt=70 + f)
    flash(c, m)

def draw_shambler_a_death(c: Sprite, f, seed):
    k = (0.22, 0.52, 0.80, 1.0)[f]
    shadow(c, (64, 122.5), 36 + 8 * k, 0.34)
    humpy = lerp(42, 98, ease(k))
    # crumpled torso heap
    c.part(ellipse((64, lerp(60, 108, ease(k))), 27, lerp(16, 12, k), soft=0.8), COAL,
           under=1.5, salt=70)
    c.part(ellipse((58, humpy), 22, lerp(13.5, 10, k), soft=0.8), STONE_D,
           under=1.3, salt=71)
    c.part(ellipse((60, lerp(58, 108, ease(k))), 17, 9, soft=0.7), DIRT,
           under=0.8, salt=72)
    c.part(rect(46, lerp(54, 103, k), 61, lerp(66, 113, k), 2.2), RUST,
           under=0.9, salt=73)
    # folded legs
    limb(c, [(52, lerp(76, 108, k)), (38, 118), (46, 120)], 3.6, COAL, salt=74)
    limb(c, [(76, lerp(76, 108, k)), (88, 118), (82, 120)], 3.6, COAL, salt=75)
    # slack arms
    cable(c, [(30, lerp(47, 104, k)), (18, 116), (26, 120)], r=0.95, strands=3,
          spread=1.3, salt=76, collars=False)
    limb(c, [(98, lerp(47, 102, k)), (110, 112), (104, 120)], 1.7, RUST_HI, salt=77)
    for i in range(3):
        c.part(capsule((102, 117), (98 + i * 6, 121), 0.8, 0.5), RUST, under=0.5, salt=78 + i)
    # head fallen forward, maw open and dark
    hc = lp((76, 44), (84, 110), ease(k))
    c.part(ellipse(hc, 10.0, 9.5, ang=math.radians(25 * k), soft=0.7), STONE_D,
           under=1.1, salt=81)
    c.part(ellipse(hc, 8.0, 7.0, soft=0.65), COAL, under=0.7, salt=82)
    c.part(rect(hc[0] - 3.6, hc[1] - 5, hc[0] + 3.6, hc[1] + 6, 1.2), MAW,
           under=0.6, rim=False, salt=83)
    c.add(ellipse((hc[0], hc[1] + 2), 2.2, 2.6), RED, 0.18)
    teeth_v(c, hc[0] - 3.7, hc[1] - 5, hc[1] + 5, 1, 4, 2.0, BONE_D, salt=84)
    teeth_v(c, hc[0] + 3.7, hc[1] - 5, hc[1] + 5, -1, 4, 2.0, BONE_D, salt=85)
    # unspooled cables and loose teeth
    for i in range(3):
        p0 = (36 + i * 10, 116)
        c.part(capsule(p0, (p0[0] - 6 + i * 3, 121), 0.55, 0.5), COAL,
               under=0.4, rim=False, salt=86 + i)
    for i in range(4):
        p = (46 + 9 * i + 2 * h01(seed, i, 31), 119 + 2 * h01(seed, i, 32))
        c.part(poly([(p[0] - 1, p[1] + 1.5), (p[0], p[1] - 2), (p[0] + 1.5, p[1] + 1.5)],
                    soft=0.4), BONE, under=0.3, tex=0.02, rim=False, salt=90 + i)
    if f >= 2:
        dust(c, (60, 114), 7, 30, salt=95 + f)
    if f == 3:
        c.part(rect(50, 116, 62, 118, 0.4), GREEN_D, under=0.3, rim=False, salt=99)


def draw_shambler_b(c: Sprite, state, f, seed):
    m = motion(state, f, seed)
    if state == "death":
        draw_shambler_b_death(c, f, seed)
        return
    sway = m["sway"] * 0.6
    hipy = 76 + m["bob"] + 0.7 * m["crouch"]
    shadow(c, (64, 123.2), 23, 0.32)
    lift = m["step"] * 2.4
    # digitigrade legs
    limb(c, [(58 + sway, hipy), (48, 96), (53, 111), (47 - lift, 121)], 3.3, STONE_D,
         salt=10, collars=(1,), taper=0.12)
    limb(c, [(70 + sway, hipy), (80, 96), (75, 111), (81 + lift, 121)], 3.3, STONE_D,
         salt=11, collars=(1,), taper=0.12)
    for fp in ((47, 121), (81, 121)):
        c.part(ellipse((fp[0], fp[1] + 1), 4.0, 2.0, soft=0.6), RUST, under=0.8,
               salt=12, rim=False)
    # narrow stacked torso
    for i, (cy, rx, ry) in enumerate(((68, 10, 8), (58, 9, 8), (48, 11, 8))):
        c.part(ellipse((64 + sway, cy + 0.3 * m["bob"]), rx, ry, soft=0.7), COAL,
               under=1.2, salt=15 + i)
        c.part(ellipse((64 + sway, cy - 1 + 0.3 * m["bob"]), rx - 1.5, ry - 1.6, soft=0.6),
               STONE_D, under=0.6, salt=18 + i)
    c.part(rect(54, 60, 74, 73, 2.0), RUST, under=1.0, salt=21)
    c.part(rect(56, 64, 66, 67, 0.5), GREEN_D, under=0.4, rim=False, salt=22)
    rivets(c, (57, 70), (71, 70), 3, OCHRE_HI, 0.7, salt=23)
    for i in range(4):
        y = 50 + i * 7
        side = -1 if i % 2 == 0 else 1
        c.part(capsule((64 + side * 2, y), (64 + side * 17, y - 3), 0.8, 0.55),
               BONE_D, under=0.5, salt=24 + i)
    # hanging ballast sac and chains
    c.part(capsule((52 + sway, 47), (61, 78), 0.7, 0.55), SOOT, under=0.4, salt=28)
    c.part(capsule((76 + sway, 47), (67, 78), 0.7, 0.55), SOOT, under=0.4, salt=29)
    sacx = 64 + sway + 4.0 * (m["charge"] + m["fire"] * 0.5) * (1 if f % 2 else -1) * 0.5
    c.part(ellipse((sacx, 88), 10.0, 11.5, soft=0.7), RUST, under=1.4, salt=30)
    c.part(ellipse((sacx - 1, 87), 7.5, 8.5, soft=0.6), RUST_HI, under=0.7, salt=31)
    c.part(rect(sacx - 7, 90, sacx + 7, 92.5, 0.6), GREEN_D, under=0.4, rim=False, salt=32)
    c.part(ellipse((sacx, 97), 4.0, 3.0, soft=0.5), DIRT, under=0.4, rim=False, salt=33)
    # arms with hooks
    cable(c, [(50 + sway, 46), (36, 63), (31, 85), (28, 95)], r=0.85, strands=3,
          spread=1.2, salt=35)
    cable(c, [(78 + sway, 46), (92, 63), (97, 85), (100, 95)], r=0.85, strands=3,
          spread=1.2, salt=38)
    for hand, sgn in ((28, -1), (100, 1)):
        for i in range(3):
            c.part(capsule((hand, 94), (hand + sgn * (2 + i * 2), 104 + i * 2), 0.7, 0.5),
                   STONE_L, under=0.5, salt=41 + i)
    # head, horizontal split jaw
    hc = (64 + sway + 0.3 * m["lean"], 32 + 0.3 * m["crouch"])
    c.part(ellipse(hc, 8.5, 8.0, soft=0.7), STONE_D, under=1.2, salt=45)
    c.part(ellipse(hc, 6.8, 6.2, soft=0.6), COAL, under=0.6, salt=46)
    jaw = min(6.5, 0.4 + 5.5 * m["jaw"] + 1.3 * m["charge"])
    c.part(rect(hc[0] - 7, hc[1] - jaw / 2, hc[0] + 7, hc[1] + jaw / 2, 1.0), MAW,
           under=0.6, rim=False, salt=47)
    teeth_h(c, hc[1] - jaw / 2 - 0.2, hc[0] - 6, hc[0] + 6, 1, 4, 2.0 + 1.5 * m["jaw"],
            BONE_D, salt=48)
    teeth_h(c, hc[1] + jaw / 2 + 0.2, hc[0] - 6, hc[0] + 6, -1, 4, 2.0 + 1.5 * m["jaw"],
            BONE_D, salt=49)
    if jaw > 1.2:
        c.add(ellipse((hc[0], hc[1]), 4.5, 3.0), AMBER, 0.2 + 0.25 * m["jaw"])
    for ex in (-4, 4):
        c.part(ellipse((hc[0] + ex, hc[1] - 4), 1.3, 1.3, soft=0.5), GREEN_HI,
               under=0.5, rim=False, salt=50 + ex)
        c.add(ellipse((hc[0] + ex, hc[1] - 4), 2.4, 2.4), GREEN, 0.2 + 0.45 * m["charge"])
    for i in range(3):
        c.part(capsule((hc[0] - 5 + i * 5, hc[1] - 8), (hc[0] - 7 + i * 7, hc[1] - 15),
                       0.65, 0.5), STONE_L, under=0.6, salt=52 + i)
    if m["charge"] > 0.3 and state in ("warning", "attack"):
        pts = [(hc[0] - 3, hc[1] - 10), (hc[0] - 12, hc[1] - 17), (hc[0], hc[1] - 21),
               (hc[0] + 12, hc[1] - 15), (hc[0] + 21, hc[1] - 22)]
        arc(c, pts, 0.8, GREEN_HI, 0.4 + 0.6 * m["charge"], salt=55 + f)
    if state == "attack" and f in (1, 2):
        bolt = [(hc[0] + 5, hc[1] - 1), (86, 44), (96, 36), (106, 48), (117, 42)]
        arc(c, bolt, 1.5, AMBER_HI, 1.0, salt=60 + f)
        sparks(c, (117, 42), 5, 8, salt=61 + f)
        c.add(ellipse((hc[0] + 4, hc[1]), 4, 4), AMBER_HI, 0.6)
    if m["hurt"] > 0.2:
        sparks(c, (sacx, 86), 4, 9, salt=65 + f)
        c.part(capsule((sacx - 6, 84), (sacx + 5, 90), 0.6, 0.5), INK,
               under=0.3, rim=False, salt=66)
    flash(c, m)


def draw_shambler_b_death(c: Sprite, f, seed):
    k = (0.22, 0.52, 0.80, 1.0)[f]
    shadow(c, (64, 122.5), 28 + 10 * k, 0.34)
    topy = lerp(48, 100, ease(k))
    for i in range(3):
        c.part(ellipse((64, topy + i * 5), 10 + i * 1.5, 7, soft=0.7), COAL,
               under=1.0, salt=70 + i)
        c.part(ellipse((64, topy + i * 5 - 1), 8.5, 5.5, soft=0.6), STONE_D,
               under=0.5, salt=73 + i)
    # burst ballast rolled clear
    sac = lp((64, 88), (88, 116), ease(k))
    c.part(ellipse(sac, 9.0, 8.0, soft=0.7), RUST, under=1.2, salt=76)
    c.part(ellipse((sac[0] - 2, sac[1] - 2), 5.0, 3.0, soft=0.55), DIRT,
           under=0.4, rim=False, salt=77)
    c.part(capsule(sac, (78, 118), 0.7, 0.5), SOOT, under=0.4, rim=False, salt=78)
    # limbs folded
    cable(c, [(50, topy + 8), (34, 114), (26, 120)], r=0.8, strands=3, spread=1.0,
          salt=79, collars=False)
    cable(c, [(78, topy + 8), (96, 114), (104, 120)], r=0.8, strands=3, spread=1.0,
          salt=82, collars=False)
    for i in range(3):
        c.part(capsule((44 + i * 5, 112), (40 + i * 5, 121), 1.8, 0.6), STONE_D,
               under=0.6, salt=85 + i)
    # head low, jaw slack
    hc = lp((64, 32), (56, 112), ease(k))
    c.part(ellipse(hc, 8.0, 7.5, soft=0.7), STONE_D, under=1.0, salt=88)
    c.part(ellipse(hc, 6.3, 5.8, soft=0.6), COAL, under=0.6, salt=89)
    c.part(rect(hc[0] - 6, hc[1] - 2.2, hc[0] + 6, hc[1] + 2.2, 1.0), MAW,
           under=0.5, rim=False, salt=90)
    c.add(ellipse((hc[0], hc[1]), 2.5, 1.5), RED, 0.16)
    teeth_h(c, hc[1] - 2.5, hc[0] - 5, hc[0] + 5, 1, 4, 1.6, BONE_D, salt=91)
    teeth_h(c, hc[1] + 2.5, hc[0] - 5, hc[0] + 5, -1, 4, 1.6, BONE_D, salt=92)
    for i in range(4):
        p = (44 + 11 * i, 118 + 2 * h01(seed, i, 41))
        c.part(poly([(p[0] - 1.4, p[1] + 1.8), (p[0], p[1] - 2), (p[0] + 1.4, p[1] + 1.8)],
                    soft=0.4), BONE, under=0.3, tex=0.02, rim=False, salt=93 + i)
    if f >= 2:
        dust(c, (58, 116), 6, 26, salt=97 + f)

# ---- THRESHOLD_MIMIC -------------------------------------------------------

def _mimic_sign(c, p, w, h, on, salt):
    c.part(rect(p[0] - w / 2 - 1.2, p[1] - h / 2 - 1.2, p[0] + w / 2 + 1.2,
                p[1] + h / 2 + 1.2, 1.2), COAL, under=0.8, salt=salt)
    c.part(rect(p[0] - w / 2, p[1] - h / 2, p[0] + w / 2, p[1] + h / 2, 1.0),
           GREEN_D if on else DIRT, under=0.5, rim=False, salt=salt + 1)
    if on:
        c.add(rect(p[0] - w / 2, p[1] - h / 2, p[0] + w / 2, p[1] + h / 2, 1.0),
               GREEN, 0.22)
        c.part(rect(p[0] - 2.2, p[1] - 1.0, p[0] + 2.2, p[1] + 1.4, 0.3), INK,
               under=0.3, rim=False, salt=salt + 2)


def draw_mimic_a(c: Sprite, state, f, seed):
    if state == "death":
        draw_mimic_a_death(c, f, seed)
        return
    m = motion("idle" if state == "walk" else state, f, seed)
    s = seed % 79
    gap = 0.0
    if state == "attack":
        gap = (2.0, 13.5, 9.0, 2.5)[f]
    elif state == "warning":
        gap = (0.6, 1.3, 2.2, 3.1)[f]
    elif state == "hurt":
        gap = 1.6
    shadow(c, (64, 123.0), 46, 0.26)
    # recess backing
    c.part(rect(24, 17, 104, 116, 1.0), COAL, under=1.4, salt=10)
    # outer stone frame
    c.part(rect(17, 9, 111, 18, 2.0), STONE_D, under=1.5, salt=11)
    c.part(rect(17, 18, 24, 116, 1.5), STONE_D, under=1.4, salt=12)
    c.part(rect(104, 18, 111, 116, 1.5), STONE_D, under=1.4, salt=13)
    c.part(rect(17, 112, 111, 122, 2.0), STONE, under=1.4, salt=14)
    c.part(rect(22, 113, 106, 118, 1.0), STONE_L, under=0.8, salt=15)
    c.part(rect(20, 14, 108, 17, 0.7), OCHRE_D, under=0.5, salt=16)
    rivets(c, (22, 13.5), (106, 13.5), 6, OCHRE_HI, 0.75, salt=17)
    # lintel hazard plate and exit sign
    c.part(rect(26, 19, 40, 22, 0.5), GREEN_D, under=0.4, rim=False, salt=18)
    sign_on = state != "hurt" and not (state == "warning" and f == 2)
    _mimic_sign(c, (64, 12.4), 18, 4.4, sign_on, salt=19)
    # leaves (worn painted steel panels, recessed)
    li = 63.5 - gap / 2
    ri = 64.5 + gap / 2
    for x0, x1, sgn in ((27, li, -1), (ri, 101, 1)):
        w = x1 - x0
        c.part(rect(x0, 21, x1, 113, 1.3), OCHRE_D, under=1.2, salt=20 + sgn)
        c.part(rect(x0 + 2, 25, x1 - 2, 58, 1.0), np.clip(OCHRE_D * 0.86, 0, 1),
               under=0.5, tex=0.10, salt=22 + sgn, rim=False)
        c.part(rect(x0 + 2, 64, x1 - 2, 108, 1.0), np.clip(OCHRE_D * 0.80, 0, 1),
               under=0.5, tex=0.10, salt=24 + sgn, rim=False)
        c.part(rect(x0 + 1, 21, x1 - 1, 24, 0.4), STONE_L, under=0.4, rim=False,
               salt=26 + sgn)
        c.part(rect(x0 + 1, 109, x1 - 1, 112, 0.5), DIRT, under=0.4, rim=False,
               salt=27 + sgn)
        # hinge plates on outer edge
        for hy in (45, 90):
            c.part(rect(x0 if sgn < 0 else x1 - 3, hy - 4, x0 + 3 if sgn < 0 else x1, hy + 4, 0.8),
                   RUST, under=0.6, salt=28 + sgn)
        c.part(capsule((x0 + 2, 61.5), (x1 - 2, 61.5), 0.45, 0.5), CHAR,
               under=0.3, rim=False, salt=30 + sgn)
    # handles and crimson seam
    c.part(ellipse((li - 4.5, 70), 1.5, 2.8, soft=0.5), RUST_HI, under=0.6, salt=33)
    c.part(capsule((li + 0.8, 21), (li + 0.8, 113), 0.42, 0.5), INK,
           under=0.3, rim=False, salt=34)
    c.part(capsule((ri - 0.8, 21), (ri - 0.8, 113), 0.42, 0.5), INK,
           under=0.3, rim=False, salt=35)
    # teeth appear in the split when it opens
    if gap > 1.2:
        open_amt = min(1.0, (gap - 1.2) / 10)
        c.part(poly([(64 - gap / 2, 22), (64 + gap / 2, 22), (64 + gap * 0.3, 112),
                     (64 - gap * 0.3, 112)], soft=0.6), MAW, under=0.7, rim=False, salt=36)
        c.add(ellipse((64, 92), gap * 0.6, 14), AMBER, 0.20 + 0.30 * open_amt)
        teeth_v(c, 64 - gap / 2 + 0.5, 25, 66, 1, 7, 2.5 + 3.5 * open_amt, BONE, salt=37)
        teeth_v(c, 64 + gap / 2 - 0.5, 69, 110, -1, 7, 2.5 + 3.5 * open_amt, BONE, salt=38)
        c.part(ellipse((64, 66), gap * 0.28, 2.0, soft=0.5), RED_HI, under=0.4,
               rim=False, salt=39)
    # faint crimson floor seam and seam leakage
    seam_on = state in ("warning", "attack") or (state == "hurt" and f < 2)
    c.part(rect(30, 113.4, 98, 114.4, 0.3), RED if seam_on else DIRT,
           under=0.3, rim=False, salt=40)
    if seam_on:
        c.add(rect(30, 113.2, 98, 114.6, 0.3), RED, 0.35)
        c.add(capsule((64, 22), (64, 112), 1.2, 0.5), RED, 0.10 + 0.18 * min(1, gap / 8))
    if state == "idle":
        # held idle: only a faint seam breath and settling dust, no locomotion
        pulse = 0.035 + 0.035 * math.sin(math.tau * f / 4.0 + seed % 5)
        c.add(capsule((64, 23), (64, 112), 0.7, 0.5), RED, pulse)
        if f >= 1:
            dust(c, (64, 110), 1 + (f % 2), 46, salt=300 + f)
        if f == 3:
            c.add(rect(56, 10.5, 72, 14.2, 0.5), GREEN, 0.12)
    # warning cracks and dust
    if state == "warning":
        c.part(capsule((48, 15), (58, 22), 0.5, 0.5), INK, under=0.3, rim=False, salt=41)
        c.part(capsule((78, 18), (84, 25), 0.4, 0.5), INK, under=0.3, rim=False, salt=42)
        if f >= 2:
            dust(c, (64, 111), 5, 40, salt=43 + f)
    if state == "attack":
        c.part(capsule((22, 20), (30, 27), 0.7, 0.5), INK, under=0.3, rim=False, salt=45)
        c.part(capsule((101, 105), (108, 98), 0.6, 0.5), INK, under=0.3, rim=False, salt=46)
        dust(c, (64, 114), 6, 44, salt=47 + f)
    if state == "hurt":
        c.part(capsule((80, 30), (96, 50), 0.6, 0.5), INK, under=0.3, rim=False, salt=50)
        c.part(poly([(84, 78), (90, 74), (92, 81), (86, 86)], soft=0.5), STONE_D,
               under=0.5, salt=51)
        sparks(c, (36, 74), 4, 9, salt=52 + f)
    flash(c, m)


def draw_mimic_a_death(c: Sprite, f, seed):
    k = (0.22, 0.52, 0.80, 1.0)[f]
    shadow(c, (64, 122.5), 48, 0.30)
    top = lerp(9, 92, ease(k))
    # falling lintel + jambs
    c.part(rect(18 + 6 * k, top, 110 - 6 * k, top + lerp(9, 6, k), 1.6), STONE_D,
           under=1.2, salt=60)
    c.part(rect(18, top + 5, 25, lerp(116, 108, k), 1.2), STONE_D, under=1.0, salt=61)
    c.part(rect(103, top + 5, 110, lerp(116, 106, k), 1.2), STONE_D, under=1.0, salt=62)
    # leaves fallen flat / leaning
    for i, (x0, x1) in enumerate(((22, 62), (66, 106))):
        y0 = lerp(22 + i * 2, 106 + i * 4, ease(k))
        y1 = lerp(112, 121, ease(k))
        c.part(rect(x0, y0, x1, y1, 1.4), OCHRE_D, under=1.1, salt=63 + i)
        c.part(rect(x0 + 3, y0 + 4, x1 - 3, (y0 + y1) / 2 - 2, 0.8),
               np.clip(OCHRE_D * 0.85, 0, 1), under=0.4, rim=False, salt=65 + i)
    # dark split remains visible
    c.part(rect(61, lerp(24, 106, ease(k)), 67, lerp(112, 121, ease(k)), 0.8), MAW,
           under=0.5, rim=False, salt=67)
    c.add(ellipse((64, 116), 8, 2.5), RED, 0.16)
    # sign fallen and rubble
    _mimic_sign(c, (86, 117.5), 14, 4.0, False, salt=68)
    for i in range(6):
        p = (26 + 14 * i + 3 * h01(seed, i, 51), 117 + 4 * h01(seed, i, 52))
        c.part(poly([(p[0] - 2.4, p[1] + 2), (p[0] - 1, p[1] - 2.5), (p[0] + 2.5, p[1] - 1),
                     (p[0] + 2, p[1] + 2)], soft=0.5), STONE_D, under=0.5,
               tex=0.03, salt=70 + i, rim=False)
    if f >= 2:
        dust(c, (64, 116), 7, 48, salt=76 + f)
    if f == 3:
        c.part(capsule((70, 118), (84, 120), 0.4, 0.5), GREEN_D, under=0.3,
               rim=False, salt=79)


def draw_mimic_b(c: Sprite, state, f, seed):
    if state == "death":
        draw_mimic_b_death(c, f, seed)
        return
    m = motion("idle" if state == "walk" else state, f, seed)
    s = seed % 71
    gap = 0.0
    if state == "attack":
        gap = (2.0, 13.0, 8.0, 2.5)[f]
    elif state == "warning":
        gap = (0.5, 1.1, 1.9, 2.8)[f]
    elif state == "hurt":
        gap = 1.4
    shadow(c, (64, 123.0), 30, 0.26)
    c.part(rect(44, 15, 84, 116, 1.0), COAL, under=1.3, salt=110)
    # tall narrow steel/stone frame
    c.part(rect(37, 7, 91, 16, 1.8), STONE_D, under=1.4, salt=111)
    c.part(rect(37, 16, 45, 116, 1.2), STONE_D, under=1.2, salt=112)
    c.part(rect(83, 16, 91, 116, 1.2), STONE_D, under=1.2, salt=113)
    c.part(rect(37, 112, 91, 122, 1.8), STONE, under=1.2, salt=114)
    c.part(rect(42, 114, 86, 118, 0.8), STONE_L, under=0.7, salt=115)
    rivets(c, (41, 11), (87, 11), 5, OCHRE_HI, 0.7, salt=116)
    _mimic_sign(c, (64, 11), 17, 4.6, state != "hurt", salt=117)
    # horizontal split leaves
    li = 63.5 - gap / 2
    ri = 64.5 + gap / 2
    c.part(rect(45, 17, 83, li, 1.2), OCHRE_D, under=1.1, salt=118)
    c.part(rect(45, ri, 83, 112, 1.2), OCHRE_D, under=1.1, salt=119)
    for y0, y1, sd in ((20, li - 2, 0), (ri + 2, 108, 1)):
        c.part(rect(48, y0, 80, y1, 0.8), np.clip(OCHRE_D * 0.82, 0, 1),
               under=0.4, tex=0.10, rim=False, salt=120 + sd)
    # push bar
    barsnap = state in ("attack", "hurt")
    if not barsnap:
        c.part(capsule((47, 61), (81, 61), 1.4, 0.6), RUST, under=0.9, salt=122)
        for x in (51, 77):
            c.part(rect(x - 1.1, 59, x + 1.1, 65, 0.5), RUST_HI, under=0.5, salt=123)
    else:
        c.part(capsule((47, 61), (62, 58), 1.4, 0.6), RUST, under=0.9, salt=124)
        c.part(capsule((66, 65), (81, 61), 1.4, 0.6), RUST, under=0.9, salt=125)
    c.part(rect(47, 72, 60, 75, 0.5), GREEN_D, under=0.4, rim=False, salt=126)
    c.part(rect(68, 72, 81, 75, 0.5), GREEN_D, under=0.4, rim=False, salt=127)
    # horizontal bite maw
    if gap > 1.0:
        open_amt = min(1.0, (gap - 1.0) / 9)
        c.part(rect(45, 64 - gap / 2, 83, 64 + gap / 2, 1.0), MAW,
               under=0.6, rim=False, salt=128)
        c.add(ellipse((64, 64), 18, gap * 0.45), AMBER, 0.18 + 0.32 * open_amt)
        teeth_h(c, 64 - gap / 2 + 0.5, 48, 80, 1, 7, 2.4 + 3.4 * open_amt, BONE,
                salt=129)
        teeth_h(c, 64 + gap / 2 - 0.5, 48, 80, -1, 7, 2.4 + 3.4 * open_amt, BONE,
                salt=130)
        c.part(ellipse((64, 64), 3.0, gap * 0.20, soft=0.5), RED_HI,
               under=0.4, rim=False, salt=131)
    c.part(rect(48, 113.4, 80, 114.5, 0.3), RED if state in ("warning", "attack") else DIRT,
           under=0.3, rim=False, salt=132)
    if state in ("warning", "attack"):
        c.add(rect(48, 113.2, 80, 114.7, 0.3), RED, 0.3)
        c.add(capsule((64, 18), (64, 112), 1.0, 0.5), RED, 0.10 + 0.15 * min(1, gap / 8))
    if state == "idle":
        pulse = 0.03 + 0.03 * math.sin(math.tau * f / 4.0 + seed % 7)
        c.add(capsule((64, 19), (64, 112), 0.6, 0.5), RED, pulse)
        if f >= 1:
            dust(c, (64, 110), 1 + (f % 2), 30, salt=302 + f)
        if f == 3:
            c.add(rect(56, 8.8, 72, 13.2, 0.5), GREEN, 0.10)
    if state == "warning":
        if f >= 2:
            dust(c, (64, 111), 4, 26, salt=133 + f)
        c.part(capsule((84, 22), (80, 31), 0.5, 0.5), INK, under=0.3, rim=False,
               salt=136)
    if state == "attack":
        c.part(capsule((44, 20), (48, 28), 0.6, 0.5), INK, under=0.3, rim=False,
               salt=137)
        dust(c, (64, 113), 5, 30, salt=138 + f)
    if state == "hurt":
        c.part(capsule((70, 24), (78, 40), 0.5, 0.5), INK, under=0.3, rim=False,
               salt=140)
        sparks(c, (64, 60), 4, 10, salt=141 + f)
    flash(c, m)


def draw_mimic_b_death(c: Sprite, f, seed):
    k = (0.22, 0.52, 0.80, 1.0)[f]
    shadow(c, (64, 122.5), 38, 0.30)
    top = lerp(7, 94, ease(k))
    # frame falls sideways and folds
    c.part(rect(38 + 20 * k, top, 90 - 20 * k, top + lerp(9, 5, k), 1.4), STONE_D,
           under=1.1, salt=160)
    c.part(rect(38 + 14 * k, top + 5, 44 + 14 * k, lerp(116, 108, k), 1.0), STONE_D,
           under=0.9, salt=161)
    c.part(rect(84 - 14 * k, top + 5, 90 - 14 * k, lerp(116, 106, k), 1.0), STONE_D,
           under=0.9, salt=162)
    # two leaves lying flat, split horizontal remains
    c.part(rect(24 + 8 * k, lerp(17, 103, ease(k)), 88, lerp(62, 112, ease(k)), 1.0),
           OCHRE_D, under=1.0, salt=163)
    c.part(rect(28, lerp(68, 113, ease(k)), 100 - 8 * k, lerp(112, 121, ease(k)), 1.0),
           OCHRE_D, under=1.0, salt=164)
    c.part(rect(48, lerp(61, 108, ease(k)), 80, lerp(66, 113, ease(k)), 0.9), MAW,
           under=0.5, rim=False, salt=165)
    c.add(ellipse((66, 116), 10, 2.2), RED, 0.13)
    c.part(capsule((42, 106), (56, 96), 1.2, 0.6), RUST, under=0.7, salt=166)
    _mimic_sign(c, (84, 119), 13, 3.6, False, salt=167)
    for i in range(5):
        p = (30 + 16 * i + 2 * h01(seed, i, 61), 117 + 4 * h01(seed, i, 62))
        c.part(poly([(p[0] - 2.2, p[1] + 2), (p[0] - 1, p[1] - 2.5), (p[0] + 2.5, p[1] - 1),
                     (p[0] + 2, p[1] + 2)], soft=0.5), STONE_D, under=0.5,
               tex=0.03, salt=168 + i, rim=False)
    if f >= 2:
        dust(c, (64, 116), 6, 34, salt=174 + f)

# ---- VORE_SPINDLE ----------------------------------------------------------

def _ceiling_plate(c, x0, x1, y=0.0, broken=False, salt=0):
    c.part(rect(x0, y, x1, y + 6.5, 1.2), STONE_D, under=1.3, salt=salt)
    c.part(rect(x0 + 3, y + 1.0, x1 - 3, y + 4.0, 0.6), STONE, under=0.6, salt=salt + 1)
    rivets(c, (x0 + 5, y + 3.1), (x1 - 5, y + 3.1), max(3, int((x1 - x0) / 10)),
           OCHRE_HI, 0.65, salt=salt + 2)
    for i in range(3):
        c.part(poly([(x0 + 4 + i * 7, y + 6.4), (x0 + 7 + i * 7, y + 10 + 2 * h01(salt, i, 1)),
                     (x0 + 11 + i * 7, y + 6.4)], soft=0.4), STONE_D, under=0.4,
               tex=0.03, salt=salt + 3 + i, rim=False)
    # bad fluorescent stub
    c.part(rect(x0 + 8, y + 4.6, x1 - 8, y + 6.2, 0.5), FLUOR, under=0.4,
           tex=0.05, rim=False, salt=salt + 7)
    c.add(rect(x0 + 8, y + 4.6, x1 - 8, y + 6.2, 0.5), GREEN, 0.12)


def _spindle_spore(c, p, size, glow=1.0, salt=0):
    prism(c, p, size, col_side=GREEN, col_hi=AMBER_HI, glow=glow)
    c.add(ellipse(p, size * 1.5, size * 1.5), GREEN, 0.10 * glow)
    if glow > 0.5:
        ring(c, p, size * 1.2, 0.4, GREEN_HI, 0.35 * glow)


def draw_spindle_a(c: Sprite, state, f, seed):
    if state == "death":
        draw_spindle_a_death(c, f, seed)
        return
    m = motion(state, f, seed)
    s = seed % 73
    sway = m["sway"] * 0.9
    hub = (64 + sway, 20 + 0.3 * m["bob"])
    _ceiling_plate(c, 43, 85, salt=s)
    # heavy suspension cables to hub
    for p0 in ((52 + sway * 0.3, 5), (64, 6), (76 + sway * 0.3, 5)):
        c.part(capsule(p0, hub, 0.95, 0.6), SOOT, under=0.5, rim=False, salt=10)
        c.part(capsule((p0[0] + 0.6, p0[1] + 1), (hub[0] + 0.6, hub[1] - 1), 0.32, 0.5),
               STONE_D, under=0.3, rim=False, salt=10)
    c.part(ellipse(hub, 4.6, 3.2, soft=0.6), STONE_D, under=0.9, salt=11)
    # inverted chitin torso: a heavy hanging mass, not a wire icon
    torso = (64 + sway, 38 + 0.4 * m["bob"] - 1.5 * m["crouch"] + 2.0 * m["charge"])
    c.part(ellipse(torso, 17.5, 17.0, soft=0.8), COAL, under=1.7, salt=12)
    c.part(ellipse((torso[0], torso[1] - 1), 14.5, 14.0, soft=0.7), STONE_D,
           under=0.9, salt=13)
    for i in range(3):
        c.part(ellipse((torso[0], torso[1] - 8 + i * 7), 13.5 - i, 2.6, soft=0.55),
               DIRT, under=0.4, tex=0.04, rim=False, salt=14 + i)
    c.part(ellipse((torso[0], torso[1] + 11), 11.0, 6.0, soft=0.6), BONE_D,
           under=0.8, salt=17)
    # three heavy scythe limbs with joint collars and barbs
    lift = 2.0 * m["charge"]
    ll = [(torso[0] - 12, torso[1] - 2), (27 + sway * 0.5, 49 - lift),
          (17 + sway * 0.4, 73 - lift), (31, 97)]
    rr = [(torso[0] + 12, torso[1] - 2), (101 + sway * 0.5, 49 - lift),
          (111 + sway * 0.4, 73 - lift), (97, 97)]
    limb(c, ll, 3.4, COAL, salt=20, collars=(1, 2), collar_col=STONE_D, taper=0.40)
    limb(c, rr, 3.4, COAL, salt=23, collars=(1, 2), collar_col=STONE_D, taper=0.40)
    limb(c, [(torso[0], torso[1] + 8), (64 + sway, 72), (53, 95)], 2.7, SOOT,
         salt=26, collars=(1,), taper=0.4)
    for pts in (ll, rr):
        c.part(capsule(np.add(pts[-1], (-1, -5)), np.add(pts[-1], (-7, 5)), 1.0, 0.55),
               GREEN_D, under=0.6, salt=29)
        c.part(capsule(np.add(pts[-1], (0, -6)), np.add(pts[-1], (2, -1)), 1.4, 0.55),
               BONE_D, under=0.5, salt=29)
        c.part(poly([pts[2], (pts[2][0] + 6, pts[2][1] - 5), (pts[2][0] + 4, pts[2][1] + 3)],
                    soft=0.45), STONE_L, under=0.6, salt=30)
        c.part(poly([pts[1], (pts[1][0] - 5, pts[1][1] - 2), (pts[1][0] - 1, pts[1][1] + 5)],
                    soft=0.4), BONE_D, under=0.5, salt=31)
    # spore chamber and spore
    ch = (64 + sway, 62 + 2.0 * m["charge"] + 1.0 * m["fire"])
    launched = state == "attack"
    if launched:
        spore_pos = ((64 + sway, 62), (88, 56), (103, 74), (91, 90))[f]
        spore_glow = (0.4, 1.0, 0.9, 0.5)[f]
    else:
        spore_pos = ch
        spore_glow = 0.6 + 0.8 * m["charge"]
    # petals / cradle open with charge
    petal = 0.25 + 0.75 * m["charge"]
    for i in range(4):
        a = math.radians(-90 + i * 90 + 12 * m["charge"])
        p0 = (ch[0] + math.cos(a) * 4.5, ch[1] + math.sin(a) * 4.5)
        p1 = (ch[0] + math.cos(a) * (13 + 5 * petal), ch[1] + math.sin(a) * (13 + 5 * petal))
        c.part(capsule(p0, p1, 1.8, 0.55), BONE_D, under=0.7, salt=33 + i)
    c.part(ellipse(ch, 8.0, 8.0, soft=0.6), MAW, under=0.9, salt=37)
    if not launched or f == 0:
        _spindle_spore(c, spore_pos, 6.8, spore_glow, salt=38)
    else:
        # empty glowing chamber + flying spore with homing trail
        c.add(ellipse(ch, 4.4, 4.4), GREEN_HI, 0.35)
        ring(c, ch, 5.0, 0.5, GREEN_HI, 0.4)
        _spindle_spore(c, spore_pos, 6.2, spore_glow, salt=39)
        trail_start = ((64 + sway, 62), (78, 56), (92, 64), (86, 82))[f]
        for i in range(3):
            q = lp(trail_start, spore_pos, i / 3.0)
            c.add(ellipse(q, 1.2 - 0.2 * i, 1.2 - 0.2 * i), GREEN_HI, 0.35)
    # ceiling fluorescent flicker
    if state == "warning":
        if f == 2:
            c.add(rect(54, 4.6, 74, 6.2, 0.5), FLUOR, 0.3)
        elif f == 3:
            sparks(c, (72, 6), 3, 8, salt=40 + f)
        if f >= 2:
            dust(c, (64, 42), 5, 30, salt=41 + f)
    if state == "attack" and f >= 1:
        sparks(c, spore_pos, 4, 8, salt=44 + f)
    if state == "hurt":
        sparks(c, (torso[0], torso[1] - 2), 5, 12, salt=46 + f)
        c.part(capsule((torso[0] - 6, torso[1] + 2), (torso[0] + 5, torso[1] + 7), 0.6, 0.5),
               INK, under=0.3, rim=False, salt=47)
    flash(c, m)


def draw_spindle_a_death(c: Sprite, f, seed):
    k = (0.22, 0.52, 0.80, 1.0)[f]
    shadow(c, (64, 122.0), 30 + 6 * k, 0.30)
    _ceiling_plate(c, 46, 82, salt=seed + 5)
    # snapped cables hanging from plate
    for x, ln in ((56, 12), (70, 8)):
        c.part(capsule((x, 5), (x + 2, 5 + ln * (0.5 + 0.5 * k)), 0.5, 0.5), SOOT,
               under=0.4, rim=False, salt=60)
    # body falls and lies on its back
    body = lp((64, 37), (64, 110), ease(k))
    c.part(ellipse(body, lerp(13.5, 19, k), lerp(14.5, 8.5, k), soft=0.8), COAL,
           under=1.4, salt=61)
    c.part(ellipse((body[0], body[1] - 1), lerp(11, 16, k), lerp(12, 7, k), soft=0.7),
           STONE_D, under=0.8, salt=62)
    for i in range(3):
        c.part(ellipse((body[0] - 4 + i * 5, body[1] - 3), 3.4, 1.6, soft=0.5),
               DIRT, under=0.4, rim=False, salt=63 + i)
    # splayed limbs
    for sgn in (-1, 1):
        pts = [(body[0] + sgn * 10, body[1] - 2), (body[0] + sgn * lerp(30, 34, k), lerp(60, 114, k)),
               (body[0] + sgn * lerp(44, 40, k), lerp(80, 120, k))]
        limb(c, pts, 2.3, SOOT, salt=66 + sgn, taper=0.4)
    limb(c, [(body[0], body[1] + 4), (body[0] + 8, 114), (body[0] - 4, 120)], 2.0,
         SOOT, salt=68, taper=0.4)
    # cracked chamber, dead spore on floor
    chamber = lp((64, 57), (80, 117), ease(k))
    c.part(ellipse(chamber, 6.0, 5.0, soft=0.6), BONE_D, under=0.7, salt=70)
    c.part(ellipse((chamber[0] + 2, chamber[1]), 4.0, 3.5, soft=0.55), MAW,
           under=0.4, rim=False, salt=71)
    c.add(ellipse((chamber[0] + 2, chamber[1]), 1.8, 1.5), RED, 0.20)
    for i in range(4):
        p = (40 + 12 * i, 118 + 3 * h01(seed, i, 71))
        c.part(poly([(p[0] - 2, p[1] + 1.5), (p[0] - 0.5, p[1] - 2), (p[0] + 2.5, p[1] + 0.5)],
                    soft=0.4), BONE_D, under=0.3, tex=0.02, rim=False, salt=72 + i)
    if f >= 2:
        dust(c, (64, 112), 6, 30, salt=78 + f)


def draw_spindle_b(c: Sprite, state, f, seed):
    if state == "death":
        draw_spindle_b_death(c, f, seed)
        return
    m = motion(state, f, seed)
    s = seed % 67
    sway = m["sway"] * 0.8
    hub = (64 + sway, 22 + 0.2 * m["bob"])
    _ceiling_plate(c, 26, 102, salt=s)
    # two broken fluorescent stubs on the plate
    for x0, x1 in ((34, 48), (78, 92)):
        c.part(rect(x0, 4.4, x1, 6.4, 0.4), FLUOR, under=0.4, tex=0.05, rim=False,
               salt=90 + x0)
        c.add(rect(x0, 4.4, x1, 6.4, 0.4), GREEN, 0.10)
    for p0 in ((48, 6), (64, 7), (80, 6)):
        c.part(capsule(p0, hub, 0.65, 0.55), SOOT, under=0.4, rim=False, salt=10)
    # heavy squat abdomen
    body = (64 + sway, 43 + 0.4 * m["bob"] - 2.0 * m["crouch"] + 2.0 * m["charge"])
    c.part(ellipse(body, 20, 14, soft=0.8), COAL, under=1.6, salt=11)
    c.part(ellipse((body[0], body[1] - 1), 17, 11, soft=0.7), STONE_D, under=0.9, salt=12)
    for i in range(3):
        c.part(ellipse((body[0] - 6 + i * 6, body[1] + 4), 3.0, 2.0, soft=0.5),
               DIRT, under=0.4, rim=False, salt=13 + i)
    c.part(ellipse((body[0], body[1] - 7), 12, 5, soft=0.6), RUST, under=0.6, salt=16)
    # four short gripping limbs
    limbs = []
    for i, sgn in enumerate((-1, 1)):
        limbs.append([(body[0] + sgn * 13, body[1] - 5), (body[0] + sgn * 31, 48 - 2 * m["charge"]),
                      (body[0] + sgn * 38, 68 - 3 * m["charge"])])
        limb(c, limbs[-1], 3.4, SOOT, salt=20 + i, collars=(1,), collar_col=STONE_D,
             taper=0.35)
    for i, sgn in enumerate((-1, 1)):
        pts = [(body[0] + sgn * 8, body[1] + 6), (body[0] + sgn * 22, 64 - 2 * m["charge"]),
               (body[0] + sgn * 18, 82 - 3 * m["charge"])]
        limb(c, pts, 2.6, SOOT, salt=23 + i, collars=(1,), taper=0.4)
    # twin spore pods in bone cradle
    cradle = (64 + sway, 61 + 2 * m["charge"])
    c.part(ellipse(cradle, 14, 8, soft=0.7), BONE_D, under=1.0, salt=26)
    podA = (58 + sway, 58 + 2 * m["charge"])
    podB = (76 + sway, 63 + 1.5 * m["charge"])
    for pod, size, glow in ((podA, 7.2, 0.5 + m["charge"]), (podB, 4.8, 0.4 + 0.5 * m["charge"])):
        c.part(ellipse(pod, size, size, soft=0.65), MAW, under=0.8, salt=28)
        c.part(ellipse((pod[0] - 1, pod[1] - 1), size * 0.65, size * 0.65, soft=0.55),
               BONE_D, under=0.4, rim=False, salt=29)
    _spindle_spore(c, podA, 4.8, 0.5 + m["charge"], salt=30)
    _spindle_spore(c, podB, 3.0, 0.4 + 0.4 * m["charge"], salt=31)
    if state == "attack":
        spore_pos = (podA, (84, 62), (101, 77), (89, 90))[f]
        glow = (0.5, 1.0, 0.9, 0.5)[f]
        if f > 0:
            _spindle_spore(c, spore_pos, 4.8, glow, salt=33)
            c.add(ellipse(podA, 3.6, 3.6), GREEN_HI, 0.3)
            ring(c, podA, 4.0, 0.4, GREEN_HI, 0.4)
            for i in range(3):
                q = lp(podA, spore_pos, i / 3.0)
                c.add(ellipse(q, 1.0, 1.0), GREEN_HI, 0.3)
            sparks(c, spore_pos, 3, 7, salt=34 + f)
    if state == "warning":
        ring(c, podA, 6.5, 0.5, GREEN_HI, 0.5 * m["charge"])
        ring(c, podB, 4.5, 0.4, GREEN_HI, 0.4 * m["charge"])
        if f == 2:
            c.add(rect(34, 4.4, 48, 6.4, 0.4), FLUOR, 0.35)
        if f >= 2:
            dust(c, (64, 45), 6, 34, salt=36 + f)
        for i in range(4):
            c.add(ellipse((body[0] - 8 + i * 5, 50), 0.8, 0.8), GREEN, 0.5)
    if state == "hurt":
        sparks(c, (body[0] + 7, body[1] + 2), 5, 11, salt=40 + f)
        c.part(capsule((podB[0] - 4, podB[1] - 3), (podB[0] + 4, podB[1] + 3), 0.6, 0.5),
               INK, under=0.3, rim=False, salt=41)
    flash(c, m)


def draw_spindle_b_death(c: Sprite, f, seed):
    k = (0.22, 0.52, 0.80, 1.0)[f]
    shadow(c, (64, 122.0), 34 + 8 * k, 0.32)
    _ceiling_plate(c, 26, 102, salt=seed + 9)
    for x, ln in ((46, 11), (82, 9)):
        c.part(capsule((x, 5), (x + 3, 5 + ln * (0.5 + 0.5 * k)), 0.5, 0.5), SOOT,
               under=0.4, rim=False, salt=170)
    body = lp((64, 43), (64, 110), ease(k))
    c.part(ellipse(body, lerp(20, 24, k), lerp(14, 8.5, k), soft=0.8), COAL,
           under=1.5, salt=171)
    c.part(ellipse((body[0], body[1] - 1), lerp(17, 20, k), lerp(11, 7, k), soft=0.7),
           STONE_D, under=0.8, salt=172)
    c.part(ellipse((body[0], body[1] - 5), lerp(12, 14, k), 3.5, soft=0.6), RUST,
           under=0.5, salt=173)
    # crumpled limbs
    for sgn in (-1, 1):
        pts = [(body[0] + sgn * 14, body[1] - 4), (body[0] + sgn * 30, lerp(54, 114, k)),
               (body[0] + sgn * 37, lerp(72, 120, k))]
        limb(c, pts, 3.0, SOOT, salt=174 + sgn, taper=0.4)
        pts2 = [(body[0] + sgn * 9, body[1] + 5), (body[0] + sgn * 23, lerp(68, 116, k)),
                (body[0] + sgn * 28, lerp(84, 121, k))]
        limb(c, pts2, 2.4, SOOT, salt=176 + sgn, taper=0.4)
    # burst pods on the floor
    for pod, size in (((48, 118), 6.0), ((84, 117), 4.2)):
        c.part(ellipse(pod, size, size * 0.8, soft=0.6), BONE_D, under=0.7, salt=180)
        c.part(ellipse((pod[0], pod[1]), size * 0.6, size * 0.45, soft=0.55), MAW,
               under=0.4, rim=False, salt=181)
        c.add(ellipse((pod[0], pod[1]), 1.3, 1.0), RED, 0.15)
    for i in range(5):
        p = (44 + 10 * i, 119 + 2 * h01(seed, i, 81))
        c.part(poly([(p[0] - 2, p[1] + 1.5), (p[0] - 0.5, p[1] - 2), (p[0] + 2.5, p[1] + 0.5)],
                    soft=0.4), BONE_D, under=0.3, tex=0.02, rim=False, salt=182 + i)
    if f >= 2:
        dust(c, (64, 112), 6, 34, salt=188 + f)

# ---- public API + CLI ------------------------------------------------------

DRAW = {
    ("SURVEYOR", 0): draw_surveyor_a, ("SURVEYOR", 1): draw_surveyor_b,
    ("WIRE_SHAMBLER", 0): draw_shambler_a, ("WIRE_SHAMBLER", 1): draw_shambler_b,
    ("THRESHOLD_MIMIC", 0): draw_mimic_a, ("THRESHOLD_MIMIC", 1): draw_mimic_b,
    ("VORE_SPINDLE", 0): draw_spindle_a, ("VORE_SPINDLE", 1): draw_spindle_b,
}


def variant_index(variant) -> int:
    if isinstance(variant, str):
        v = variant.strip().upper()
        if v in ("0", "A", "0A", "TRIPOD", "BALLAST", "BALLAST HUSK", "LINTEL", "LINTEL DOOR", "PENDULUM"):
            return 0
        if v in ("1", "B", "1B", "GIMBAL", "CABLE TOWER", "FALSE EXIT", "CEILING LURKER"):
            return 1
        raise ValueError(f"unknown variant {variant!r}; use A/0 or B/1")
    if isinstance(variant, (int, np.integer)) and int(variant) in (0, 1):
        return int(variant)
    raise ValueError("variant must be A/B or 0/1")


def validate(kind, variant, state, frame, seed, size=SIZE):
    if not isinstance(kind, str) or kind.upper() not in KINDS:
        raise ValueError(f"unknown kind {kind!r}; expected one of {KINDS}")
    kind = kind.upper()
    vi = variant_index(variant)
    if not isinstance(state, str) or state.lower() not in STATES:
        raise ValueError(f"unknown state {state!r}; expected one of {STATES}")
    state = state.lower()
    if not isinstance(frame, (int, np.integer)) or not (0 <= int(frame) < 4):
        raise ValueError("frame must be an integer 0..3")
    if not isinstance(seed, (int, np.integer)) or int(seed) < 0:
        raise ValueError("seed must be a non-negative integer")
    if int(size) != SIZE:
        raise ValueError(f"invalid size {size!r}; this renderer emits exactly {SIZE}x{SIZE}")
    return kind, vi, state, int(frame), int(seed)


def render_frame(kind: str, variant=0, state: str = "idle", frame: int = 0,
                 seed: int = DEFAULT_SEED, size: int = SIZE) -> Image.Image:
    """Render one deterministic 128x128 RGBA frame. No I/O, no shell, no eval."""
    kind, vi, state, frame, seed = validate(kind, variant, state, frame, seed, size)
    draw = DRAW[(kind, vi)]
    c = Sprite(seed)
    # A stationary door mimic must not fake locomotion: walk frames are one held
    # pose, so normalise the frame index for drawing (all four are identical).
    draw_frame = 0 if (kind == "THRESHOLD_MIMIC" and state == "walk") else frame
    draw(c, state, draw_frame, seed)
    return c.finish()


def frame_meta(kind, variant, state, frame, seed):
    return dict(kind=kind, variant="AB"[int(variant)], variant_name=VARIANTS[kind][int(variant)],
                state=state, frame=int(frame), seed=int(seed))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Argon monster art-study renderer (GPL-2.0-or-later)")
    ap.add_argument("--kind", choices=KINDS, help="archetype")
    ap.add_argument("--variant", default="A", help="A/0 or B/1")
    ap.add_argument("--state", default="idle", help=" / ".join(STATES))
    ap.add_argument("--frame", type=int, default=0)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--size", type=int, default=SIZE)
    ap.add_argument("--out", help="write one PNG here")
    ap.add_argument("--all", action="store_true", help="render the full 192-frame batch")
    ap.add_argument("--outdir", default="frames", help="destination for --all")
    args = ap.parse_args(argv)
    try:
        if args.all:
            os.makedirs(args.outdir, exist_ok=True)
            n = 0
            for kind in KINDS:
                for vi in (0, 1):
                    for state in STATES:
                        for f in range(4):
                            img = render_frame(kind, vi, state, f, args.seed)
                            path = os.path.join(args.outdir, f"{kind}_{'AB'[vi]}_{state}_{f}.png")
                            img.save(path)
                            n += 1
            print(f"wrote {n} frames to {args.outdir}")
            return 0
        img = render_frame(args.kind or "SURVEYOR", args.variant, args.state, args.frame,
                           args.seed, args.size)
        if args.out:
            os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
            img.save(args.out)
            print(args.out)
        else:
            img.show()
        return 0
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
