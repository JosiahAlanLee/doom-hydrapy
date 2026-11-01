#!/usr/bin/env python3
"""Null Run original first-person weapon art bank.

CPU-only procedural rasterisation: chunky flat-shaded polygons, painted
noise ramps for industrial materials, one coherent glove/sleeve design.
No external images, no IWAD pixels, no borrowed silhouettes.

Run:  hydrapy/bin/python generate_weapons.py [--out DIR] [--seed N]
"""
import argparse
import hashlib
import json
import math
import os
import random
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageChops, ImageFont

W, H = 640, 400
SS = 3
EDGE = "#08090b"

def hx(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))

MATERIALS = {
    "gunmetal": {"ramp": ["#101216", "#1c2128", "#2c333d", "#414a56", "#5d6875", "#818d9a"], "amp": 0.10, "edge": "#07080a"},
    "steel":    {"ramp": ["#14161a", "#26292f", "#3b4048", "#565d68", "#7a828d", "#a8b0ba"], "amp": 0.08, "edge": "#08090b"},
    "brass":    {"ramp": ["#2a1c0a", "#4f3613", "#7c5722", "#a87c37", "#d0a75c", "#efd79a"], "amp": 0.11, "edge": "#1e1407"},
    "verdigris":{"ramp": ["#102622", "#1c3f36", "#2d5c4c", "#447c66", "#68a286", "#9cc7b0"], "amp": 0.12, "edge": "#08130f"},
    "oxblood":  {"ramp": ["#1a0d0c", "#331513", "#52241e", "#6f3329", "#904739", "#b05f4c"], "amp": 0.10, "edge": "#120a08"},
    "leather":  {"ramp": ["#1a120e", "#2c1e16", "#432d20", "#5b3e2b", "#785440", "#96705a"], "amp": 0.12, "edge": "#120c08"},
    "canvas":   {"ramp": ["#2e2412", "#4a3a1c", "#6b5528", "#8c7036", "#ad904b", "#cdb268"], "amp": 0.13, "edge": "#1c150a"},
    "bone":     {"ramp": ["#4a4234", "#6a6250", "#8e846d", "#b2a78d", "#d3c9ad", "#eee6cf"], "amp": 0.09, "edge": "#2a2218"},
    "chalk":    {"ramp": ["#4e4e46", "#73736a", "#97978c", "#b9b8ab", "#d8d6c6", "#f0eddc"], "amp": 0.07, "edge": "#23231d"},
    "rust":     {"ramp": ["#221009", "#3f1d0e", "#632e15", "#874222", "#a95a30", "#c47a45"], "amp": 0.14, "edge": "#120804"},
    "warning":  {"ramp": ["#351008", "#5c1b0c", "#8a2a12", "#b8401a", "#d9642c", "#f09050"], "amp": 0.11, "edge": "#1a0603"},
    "energy":   {"ramp": ["#07180f", "#0e331d", "#185c31", "#2c9a4c", "#5fd97a", "#c8ffd4"], "amp": 0.13, "edge": "#052510"},
    "void":     {"ramp": ["#080a0c", "#101317", "#191d23", "#242a31", "#323941", "#434b55"], "amp": 0.06, "edge": "#050607"},
    "walnut":   {"ramp": ["#1c1009", "#33200f", "#4f3016", "#6d441f", "#8c5a2b", "#a9723c"], "amp": 0.13, "edge": "#120b06"},
    "paper":    {"ramp": ["#5b584c", "#7d796a", "#a19c88", "#c2bda5", "#ded9c0", "#f4f0d9"], "amp": 0.05, "edge": "#2e2b22"},
}

def ramp_color(ramp, t):
    t = max(0.0, min(1.0, t)) * (len(ramp) - 1)
    i = int(t)
    f = t - i
    a, b = hx(ramp[min(i, len(ramp) - 1)]), hx(ramp[min(i + 1, len(ramp) - 1)])
    return tuple(a[k] + (b[k] - a[k]) * f for k in range(3))

class Paint:
    """Supersampled painter. RGB is drawn over black and unpremultiplied at the
    end, so anti-aliased silhouette edges get clean straight-alpha RGBA."""
    def __init__(self, w, h, ss=SS, seed=7):
        self.w, self.h, self.ss = w, h, ss
        self.W, self.H = w * ss, h * ss
        self.RGB = Image.new("RGB", (self.W, self.H), (0, 0, 0))
        self.A = Image.new("L", (self.W, self.H), 0)
        rng = np.random.RandomState(seed)
        g1 = Image.fromarray((rng.rand(18, 18) * 255).astype(np.uint8)).resize((self.W, self.H), Image.BICUBIC)
        g2 = Image.fromarray((rng.rand(90, 90) * 255).astype(np.uint8)).resize((self.W, self.H), Image.BICUBIC)
        fine = rng.rand(self.H, self.W).astype(np.float32)
        self.noise = (0.5 * (np.asarray(g1, np.float32) / 255.0)
                      + 0.25 * (np.asarray(g2, np.float32) / 255.0)
                      + 0.25 * fine)

    def poly(self, pts, mat, shade=0.6, edge=True, ew=1.0):
        pts = [(float(x), float(y)) for x, y in pts]
        if len(pts) < 3:
            return
        s = self.ss
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        x0 = max(0, int(math.floor(min(xs) * s)) - 2); y0 = max(0, int(math.floor(min(ys) * s)) - 2)
        x1 = min(self.W, int(math.ceil(max(xs) * s)) + 3); y1 = min(self.H, int(math.ceil(max(ys) * s)) + 3)
        if x1 <= x0 or y1 <= y0:
            return
        loc = [(x * s - x0, y * s - y0) for x, y in pts]
        mask = Image.new("L", (x1 - x0, y1 - y0), 0)
        ImageDraw.Draw(mask).polygon(loc, fill=255)
        base = np.array(ramp_color(MATERIALS[mat]["ramp"], shade), np.float32)
        n = self.noise[y0:y1, x0:x1]
        amp = MATERIALS[mat].get("amp", 0.10)
        col = np.clip(base[None, None, :] * (1.0 + (n[..., None] - 0.5) * 2.0 * amp), 0, 255).astype(np.uint8)
        fill = Image.fromarray(col, "RGB")
        crop = self.RGB.crop((x0, y0, x1, y1))
        crop.paste(fill, (0, 0), mask)
        if edge:
            ImageDraw.Draw(crop).line(loc + [loc[0]], fill=hx(MATERIALS[mat].get("edge", EDGE)),
                                      width=max(1, int(round(ew * s))), joint="curve")
        self.RGB.paste(crop, (x0, y0))
        ac = self.A.crop((x0, y0, x1, y1))
        self.A.paste(ImageChops.lighter(ac, mask), (x0, y0))

    def line(self, pts, mat, shade=0.8, width=1.0):
        s = self.ss
        d = ImageDraw.Draw(self.RGB)
        d.line([(x * s, y * s) for x, y in pts], fill=tuple(int(c) for c in ramp_color(MATERIALS[mat]["ramp"], shade)),
               width=max(1, int(round(width * s))), joint="curve")

    def disc(self, cx, cy, r, mat, shade=0.6, n=14, edge=True, ew=1.0):
        pts = [(cx + math.cos(2 * math.pi * i / n) * r, cy + math.sin(2 * math.pi * i / n) * r) for i in range(n)]
        self.poly(pts, mat, shade, edge, ew)

    def finish(self):
        rgb = self.RGB.resize((self.w, self.h), Image.BOX)
        a = self.A.resize((self.w, self.h), Image.BOX)
        arr = np.asarray(rgb, np.float32)
        al = np.asarray(a, np.float32)
        af = al / 255.0
        out = np.zeros((self.h, self.w, 3), np.float32)
        m = af > 0
        out[m] = arr[m] / af[m][:, None]
        out = np.clip(out, 0, 255).astype(np.uint8)
        alpha = al.astype(np.uint8)
        out[alpha == 0] = 0
        return Image.fromarray(np.dstack([out, alpha]), "RGBA")

class Rig:
    def __init__(self, paint, origin, rot, groups=None):
        self.p = paint
        self.ox, self.oy = origin
        self.th = math.radians(rot)
        self.c, self.s = math.cos(self.th), math.sin(self.th)
        self.groups = groups or {}

    def W(self, x, y, group=None):
        gx, gy = self.groups.get(group, (0, 0)) if group else (0, 0)
        x += gx; y += gy
        return (self.ox + x * self.c - y * self.s, self.oy + x * self.s + y * self.c)

    def T(self, pts, group=None):
        return [self.W(x, y, group) for x, y in pts]

    def P(self, pts, mat, shade=0.6, group=None, edge=True, ew=1.0):
        self.p.poly(self.T(pts, group), mat, shade, edge, ew)

    def rect(self, x0, y0, x1, y1, mat, shade=0.6, group=None, off=(3, -4), edge=True):
        ox, oy = off
        self.P([(x0 + ox, y0 + oy), (x1 + ox, y0 + oy), (x1 + ox, y1 + oy), (x0 + ox, y1 + oy)],
               mat, max(0.0, shade - 0.32), group, edge)
        self.P([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], mat, shade, group, edge)
        if off[1] < 0:
            self.p.line(self.T([(x0, y0 + 1), (x1, y0 + 1)], group), mat, min(1.0, shade + 0.25), 0.6)

    def line(self, pts, mat, shade=0.8, width=1.0, group=None):
        self.p.line(self.T(pts, group), mat, shade, width)

    def disc(self, cx, cy, r, mat, shade=0.6, group=None, n=14):
        pts = [(cx + math.cos(2 * math.pi * i / n) * r, cy + math.sin(2 * math.pi * i / n) * r) for i in range(n)]
        self.P(pts, mat, shade, group)

    def rivet(self, x, y, *args, group=None, r=2.0, mat="brass"):
        for a in args:
            if isinstance(a, str):
                group = a
            else:
                r = float(a)
        self.disc(x, y, r, mat, 0.75, group, 8)

def hand(rig, anchor, kind="grip", yaw=0.0, flip=1, group=None, scale=0.82, part="all"):
    """One coherent glove/sleeve design in weapon-local space.
    u runs up the grip, +v to the hand's outer side. Sleeves are drawn early
    (part='sleeve') so they sit behind the weapon; gloves late (part='glove').
    Sleeves deliberately run past the bottom edge: the only crop."""
    ax, ay = anchor
    ca, sa = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))

    def T(u, v):
        x, y = v * flip * scale, -u * scale
        return (ax + x * ca - y * sa, ay + x * sa + y * ca)

    def P(pts, mat, shade, edge=True, ew=1.0):
        rig.P([T(u, v) for u, v in pts], mat, shade, group, edge, ew)

    if part in ("all", "sleeve"):
        sleeve = [(-220, -31), (-220, 39), (-8, 28), (-6, -25)]
        P(sleeve, "canvas", 0.45, True, 1.2)
        P([(-220, -10), (-220, 39), (-66, 35), (-60, 2)], "canvas", 0.33, False)
        for u0, u1 in ((-32, -26), (-21, -15)):
            P([(u0, -29), (u1, -29), (u1, 28), (u0, 28)], "warning", 0.30, False)
        P([(-58, -26), (-52, -26), (-52, 28), (-58, 28)], "canvas", 0.28, False, 0.8)
        P([(-14, -27), (-2, -25), (-2, 26), (-14, 28)], "leather", 0.36, True, 1.2)
        P([(-12, -27), (-7, -27), (-7, 26), (-12, 26)], "oxblood", 0.32, False)
        P([(-11, 12), (-4, 11), (-4, 21), (-11, 22)], "brass", 0.66, True, 0.8)
        rig.rivet(*T(-7.5, 17), group=group, r=1.6)

    if part in ("all", "glove"):
        palm = [(2, -18), (10, -25), (36, -26), (50, -18), (55, -2), (50, 18), (31, 27),
                (11, 22), (1, 7)]
        P(palm, "leather", 0.58, True, 1.3)
        P([(10, -22), (35, -23), (47, -16), (38, -10), (15, -8)], "leather", 0.72, False)
        for v0 in (-12, -1, 10):
            P([(35, v0), (47, v0 + 1), (48, v0 + 8), (36, v0 + 8)], "bone", 0.60, True, 0.8)
            P([(37, v0 + 1), (46, v0 + 2), (46, v0 + 4), (37, v0 + 3)], "bone", 0.82, False)
        for v in (-13, -2, 9, 20):
            rig.line([T(27, v), T(51, v + 2)], "leather", 0.22, 0.7, group)
        thumb = [(4, -20), (17, -29), (33, -30), (41, -24), (34, -14), (16, -13)]
        P(thumb, "leather", 0.50, True, 1.0)
        P([(18, -26), (31, -27), (36, -23), (20, -21)], "leather", 0.64, False)
        rig.line([T(2, -25), T(2, 26)], "leather", 0.25, 0.8, group)

def star_pts(cx, cy, r0, r1, n, rot, rng, jit=0.22):
    pts = []
    for i in range(n * 2):
        a = rot + math.pi * i / n
        r = (r0 if i % 2 == 0 else r1) * (1.0 + (rng.random() * 2 - 1) * jit)
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts

def render_flash(wid, variant, muzzle, angle_deg, seed):
    p = Paint(W, H, SS, seed)
    rng = random.Random(seed)
    cx, cy = muzzle
    kind = FLASH_STYLE[wid]
    if kind in ("star", "hymn"):
        n = 11 if kind == "star" else 14
        r_out = (48 if kind == "star" else 74) * (1.0 if variant == "a" else 0.82)
        outer_mat = "warning" if kind == "star" else "brass"
        mid_mat = "brass" if kind == "star" else "bone"
        core_mat = "chalk"
        # orient the burst down the barrel; ballistic flashes are stretched forward
        ar = math.radians(angle_deg)
        ux, uy = math.sin(ar), -math.cos(ar)
        vx, vy = math.cos(ar), math.sin(ar)
        elong = 1.45 if kind == "star" else 1.12

        def xf(pts, e=elong):
            out = []
            for x, y in pts:
                a, b = x * e, y / e
                out.append((cx + a * ux + b * vx, cy + a * uy + b * vy))
            return out

        star_a = star_pts(0, 0, r_out, r_out * 0.32, n, math.radians(rng.random() * 30), rng, 0.30)
        star_b = star_pts(0, 0, r_out * 0.68, r_out * 0.22, n, math.radians(rng.random() * 30), rng, 0.24)
        p.poly(xf(star_a), outer_mat, 0.46)
        p.poly(xf(star_b), mid_mat, 0.76)
        if kind == "star":
            tip = (cx + ux * r_out * 1.18, cy + uy * r_out * 1.18)
            p.poly([(cx + vx * 13, cy + vy * 13), tip, (cx - vx * 13, cy - vy * 13)], "warning", 0.55, False)
            p.poly([(cx + ux * 6 + vx * 7, cy + uy * 6 + vy * 7),
                    (cx + ux * r_out * 0.72, cy + uy * r_out * 0.72),
                    (cx + ux * 6 - vx * 7, cy + uy * 6 - vy * 7)], "brass", 0.82, False)
            p.disc(cx + ux * 5, cy + uy * 5, r_out * 0.22, core_mat, 0.96, 12)
        else:
            p.disc(cx + ux * 4, cy + uy * 4, r_out * 0.24, core_mat, 0.95, 12)
            # bone mouth-petals attached to the halo, not floating confetti
            for i in range(9):
                a = math.radians(angle_deg + 90) + i * 2 * math.pi / 9 + rng.random() * 0.12
                ca, sa = math.cos(a), math.sin(a)
                r0, r1 = r_out * 0.92, r_out * (1.10 + rng.random() * 0.12)
                w = 0.055
                p.poly([(cx + ca * r0 - sa * 0, cy + sa * r0 + ca * 0),
                        (cx + ca * r1 - sa * 7, cy + sa * r1 + ca * 7),
                        (cx + ca * r1 + sa * 7, cy + sa * r1 - ca * 7),
                        (cx + ca * (r0 + 4) + sa * 3, cy + sa * (r0 + 4) - ca * 3)],
                       "bone", 0.70, False)
    elif kind == "energy":
        r = 60 if variant == "a" else 44
        p.poly(star_pts(cx, cy, r, r * 0.4, 10, math.radians(rng.random() * 30), rng, 0.3), "energy", 0.55)
        p.disc(cx, cy, r * 0.46, "energy", 0.88, 16)
        p.disc(cx, cy, r * 0.2, "chalk", 0.98, 12)
        for stage in (0.72, 1.02):
            rr = r * stage
            for i in range(18):
                a0 = 2 * math.pi * i / 18 + 0.08
                a1 = a0 + 0.09
                p.poly([(cx + math.cos(a0) * rr, cy + math.sin(a0) * rr),
                        (cx + math.cos(a1) * rr, cy + math.sin(a1) * rr),
                        (cx + math.cos(a1) * (rr + 3), cy + math.sin(a1) * (rr + 3)),
                        (cx + math.cos(a0) * (rr + 3), cy + math.sin(a0) * (rr + 3))],
                       "energy", 0.70, False)
        for i in range(7):
            a = rng.random() * 2 * math.pi
            d0, d1 = r * 1.05, r * (1.25 + rng.random() * 0.4)
            p.poly([(cx + math.cos(a) * d0, cy + math.sin(a) * d0),
                    (cx + math.cos(a + 0.03) * d1, cy + math.sin(a + 0.03) * d1),
                    (cx + math.cos(a) * (d1 + 5), cy + math.sin(a) * (d1 + 5))],
                   "energy", 0.85, False)
    elif kind == "spark":
        r = 40 if variant == "a" else 30
        p.disc(cx, cy, r * 0.2, "chalk", 0.95, 10)
        for i in range(12):
            a = rng.random() * 2 * math.pi
            d0, d1 = r * 0.25, r * (0.6 + rng.random() * 0.9)
            w = 0.05 + rng.random() * 0.05
            p.poly([(cx + math.cos(a - w) * d0, cy + math.sin(a - w) * d0),
                    (cx + math.cos(a) * d1, cy + math.sin(a) * d1),
                    (cx + math.cos(a + w) * d0, cy + math.sin(a + w) * d0)],
                   "warning", 0.62, False)
        p.poly(star_pts(cx, cy, r * 0.5, r * 0.16, 8, math.radians(rng.random() * 40), rng, 0.25), "warning", 0.52)
    elif kind == "blast":
        r = 70 if variant == "a" else 54
        p.poly(star_pts(cx, cy, r, r * 0.38, 12, math.radians(rng.random() * 20), rng, 0.3), "warning", 0.50)
        p.poly(star_pts(cx, cy, r * 0.62, r * 0.22, 9, math.radians(rng.random() * 35), rng, 0.2), "brass", 0.72)
        p.disc(cx, cy, r * 0.26, "chalk", 0.95, 12)
        rr = r * 0.86
        for i in range(16):
            a0 = 2 * math.pi * i / 16
            a1 = a0 + 0.12
            p.poly([(cx + math.cos(a0) * rr, cy + math.sin(a0) * rr),
                    (cx + math.cos(a1) * rr, cy + math.sin(a1) * rr),
                    (cx + math.cos(a1) * (rr + 4), cy + math.sin(a1) * (rr + 4)),
                    (cx + math.cos(a0) * (rr + 4), cy + math.sin(a0) * (rr + 4))],
                   "warning", 0.66, False)
    img = p.finish()
    return img

# ---------------------------------------------------------------- weapons ---
FLASH_STYLE = {
    "fathom_hook": "spark",
    "registrar": "star",
    "transit_12": "star",
    "comptroller": "star",
    "plumb_bombard": "blast",
    "aethometer": "energy",
    "hymnodyne": "hymn",
}

def draw_fathom_hook(rig, frame):
    P, R = rig.P, rig.rect
    hand(rig, (16, 12), "grip", yaw=-20, flip=1, part="sleeve")
    # surveyor's steel rule shaft, chalk graduations
    P([(-10, 48), (10, 48), (7, -138), (-5, -138)], "steel", 0.52)
    P([(-6, -138), (6, -138), (4, -158), (-3, -158)], "steel", 0.64)
    for yy in range(-116, 26, 18):
        rig.line([(-10, yy), (-3, yy)], "chalk", 0.72, 0.7)
    rig.line([(-9, -128), (8, -126)], "warning", 0.42, 1.1)
    # ferrules and oxblood grip wrap
    R(-12, -42, 14, -28, "brass", 0.62)
    R(-12, 42, 14, 54, "brass", 0.58)
    R(-11, -26, 13, 38, "oxblood", 0.42)
    for yy in range(-16, 34, 10):
        rig.line([(-11, yy), (13, yy + 1)], "leather", 0.25, 0.6)
    # head block and plumb counterweight
    R(-20, -166, 20, -132, "gunmetal", 0.54)
    P([(-24, -166), (-8, -178), (16, -172), (20, -152), (-2, -138), (-22, -146)], "gunmetal", 0.64)
    rig.disc(24, -150, 10, "brass", 0.64)
    rig.disc(24, -150, 4, "brass", 0.38, n=10)
    rig.line([(24, -150), (24, -166)], "brass", 0.68, 2.0)
    # billhook blade, bright honed edge
    blade = [(-6, -168), (-28, -180), (-50, -176), (-56, -162), (-44, -154), (-24, -156), (-12, -150)]
    P(blade, "steel", 0.70)
    P([(-28, -176), (-48, -172), (-52, -163), (-41, -158), (-26, -162)], "steel", 0.88)
    rig.line([(-50, -175), (-56, -162), (-44, -154)], "chalk", 0.92, 1.1)
    # bone inlay, issue tag
    P([(-14, -160), (-2, -162), (2, -150), (-10, -146)], "bone", 0.62)
    rig.line([(-6, -158), (-4, -150)], "bone", 0.34, 0.6)
    P([(-25, -84), (-15, -88), (-13, -60), (-23, -56)], "paper", 0.56)
    for yy in (-80, -74, -68):
        rig.line([(-22, yy), (-15, yy)], "chalk", 0.30, 0.8)
    hand(rig, (16, 12), "grip", yaw=-20, flip=1, part="glove")
    return (-56, -162)

def draw_registrar(rig, frame):
    P, R = rig.P, rig.rect
    hand(rig, (16, 48), "grip", yaw=-20, flip=1, part="sleeve")
    # frame and oxblood grip
    R(-18, 0, 18, 40, "gunmetal", 0.44)
    P([(-16, 10), (16, 10), (20, 56), (-8, 60)], "oxblood", 0.50)
    P([(-12, 18), (12, 18), (16, 50), (-4, 54)], "oxblood", 0.62)
    for yy in range(24, 50, 8):
        rig.line([(0, yy), (15, yy + 1)], "leather", 0.30, 0.6)
    R(-10, 52, 18, 66, "gunmetal", 0.48, group="mag")
    rig.rivet(12, 59, "mag", 2.1)
    R(-24, -16, 24, 8, "gunmetal", 0.50)
    # trigger guard as three clean bars
    P([(-16, -4), (-10, -4), (-8, 26), (-14, 28)], "gunmetal", 0.42)
    P([(-14, 22), (14, 22), (14, 28), (-14, 28)], "gunmetal", 0.45)
    P([(10, -2), (16, -2), (14, 24), (8, 24)], "gunmetal", 0.42)
    P([(-2, 0), (4, 0), (3, 16), (-3, 18)], "brass", 0.60)
    # slide with ejection port and register plate
    R(-27, -98, 25, -16, "gunmetal", 0.62, group="slide")
    P([(-27, -98), (25, -98), (29, -90), (-29, -86)], "steel", 0.74, group="slide")
    P([(-24, -76), (-6, -74), (-6, -56), (-24, -58)], "void", 0.40, group="slide")
    for yy in range(-46, -22, 5):
        rig.line([(-2, yy), (20, yy + 1)], "void", 0.25, 0.9, group="slide")
    R(-18, -52, 10, -34, "brass", 0.62, group="slide")
    rig.line([(-14, -46), (-8, -46)], "chalk", 0.45, 1.0, group="slide")
    rig.line([(-14, -41), (-4, -41)], "chalk", 0.40, 1.0, group="slide")
    rig.rivet(-15, -38, "slide", 1.4)
    # survey vial and sights
    P([(-26, -88), (-18, -92), (-14, -84), (-22, -80)], "brass", 0.64, group="slide")
    rig.disc(-21, -86, 2.6, "energy", 0.75, group="slide", n=8)
    R(-18, -88, -10, -80, "brass", 0.60, group="slide")
    P([(-2, -112), (2, -112), (2, -102), (-2, -102)], "brass", 0.70, group="slide")
    # muzzle block, bore
    R(-19, -104, 17, -92, "steel", 0.70, group="slide")
    rig.disc(0, -100, 7, "void", 0.30, group="slide", n=12)
    rig.disc(0, -100, 4, "void", 0.12, group="slide", n=12)
    rig.disc(15, 62, 5, "brass", 0.55, n=10)
    rig.disc(15, 62, 2.4, "void", 0.20, n=8)
    hand(rig, (16, 48), "grip", yaw=-20, flip=1, part="glove")
    return (0, -112)

def draw_transit_12(rig, frame):
    P, R = rig.P, rig.rect
    sup = frame.get("support_anchor", (-12, -58))
    hand(rig, sup, "support", yaw=26, flip=-1, scale=0.76, part="sleeve")
    hand(rig, (16, 48), "grip", yaw=-20, flip=1, part="sleeve")
    # walnut stock and butt plate
    P([(28, 14), (46, 14), (60, 100), (36, 114)], "walnut", 0.42)
    P([(37, 106), (60, 98), (64, 110), (40, 118)], "brass", 0.55)
    rig.disc(50, 90, 5, "brass", 0.50, n=10)
    rig.disc(50, 90, 2, "void", 0.20, n=8)
    # wrist
    P([(-14, 8), (16, 8), (20, 52), (-10, 58)], "walnut", 0.50)
    for yy in range(20, 50, 9):
        rig.line([(-6, yy), (16, yy + 1)], "leather", 0.28, 0.6)
    # receiver, side plate with transit badge
    R(-38, -54, 38, 10, "gunmetal", 0.58)
    P([(-28, -54), (28, -54), (24, -44), (-26, -40)], "steel", 0.72)
    P([(-14, -50), (14, -50), (12, -16), (-12, -16)], "brass", 0.55)
    rig.disc(0, -33, 9, "verdigris", 0.55, n=14)
    rig.disc(0, -33, 6, "brass", 0.35, n=14)
    rig.disc(0, -33, 3, "void", 0.20, n=10)
    rig.rivet(-10, -46, 1.8)
    rig.rivet(10, -46, 1.8)
    P([(12, -14), (26, -16), (26, 4), (12, 6)], "void", 0.38)
    # barrel and under tube
    P([(-19, -162), (19, -162), (20, -54), (-20, -54)], "steel", 0.62)
    P([(-19, -162), (-7, -162), (-8, -54), (-20, -54)], "steel", 0.78)
    P([(-11, -146), (11, -146), (11, -58), (-11, -58)], "gunmetal", 0.42)
    R(-19, -120, 19, -112, "brass", 0.58)
    R(-19, -66, 19, -58, "brass", 0.55)
    # wood pump, brass bands, support hand rides it
    R(-29, -80, 29, -42, "walnut", 0.50, group="pump")
    for yy in range(-74, -44, 8):
        rig.line([(-25, yy), (25, yy + 1)], "void", 0.28, 0.9, group="pump")
    R(-27, -88, 27, -78, "brass", 0.60, group="pump")
    # transit sight housing and level vial
    R(-24, -152, 24, -126, "brass", 0.58)
    rig.disc(-20, -139, 7, "energy", 0.50, n=12)
    rig.disc(20, -139, 7, "void", 0.30, n=12)
    P([(-10, -162), (10, -162), (10, -152), (-10, -152)], "energy", 0.36)
    rig.disc(2, -157, 3.2, "chalk", 0.92, n=10)
    rig.rivet(-26, -120, 2.2)
    rig.rivet(26, -120, 2.2)
    # muzzle band and bead
    R(-20, -174, 20, -158, "brass", 0.62)
    rig.disc(0, -166, 8, "void", 0.30, n=12)
    P([(-2, -180), (2, -180), (0, -172)], "brass", 0.75)
    # hands
    hand(rig, sup, "support", yaw=26, flip=-1, scale=0.76, part="glove")
    hand(rig, (16, 48), "grip", yaw=-20, flip=1, part="glove")
    return (0, -176)

def draw_comptroller(rig, frame):
    P, R = rig.P, rig.rect
    sup = frame.get("support_anchor", (-12, -54))
    hand(rig, sup, "support", yaw=26, flip=-1, scale=0.76, part="sleeve")
    hand(rig, (16, 50), "grip", yaw=-20, flip=1, part="sleeve")
    P([(-16, 12), (16, 12), (20, 56), (-10, 62)], "walnut", 0.46)
    for yy in range(24, 54, 10):
        rig.line([(-8, yy), (18, yy + 1)], "leather", 0.28, 0.6)
    R(-44, -64, 44, 12, "gunmetal", 0.58)
    P([(-34, -64), (34, -64), (30, -54), (-32, -50)], "steel", 0.70)
    # typewriter paper slot and curled tape
    R(-22, -78, 22, -64, "brass", 0.55)
    P([(-18, -76), (-4, -78), (2, -58), (-12, -56)], "paper", 0.72)
    for yy in (-72, -66):
        for xx in (-14, -8, -2):
            rig.rivet(xx, yy, 0.8, mat="chalk")
    # carry handle
    P([(-28, -78), (-20, -78), (-18, -94), (-26, -94)], "brass", 0.50)
    P([(20, -78), (28, -78), (26, -94), (18, -94)], "brass", 0.50)
    R(-28, -104, 28, -94, "brass", 0.60)
    # typebar fins on the left
    for i, yy in enumerate(range(-56, -8, 12)):
        P([(-46, yy), (-34, yy - 4), (-30, yy + 6), (-42, yy + 10)], "brass", 0.45 + i * 0.04)
    # feed cassette with tape
    R(26, -58, 50, -18, "brass", 0.55, group="feed")
    P([(28, -54), (48, -54), (44, -30), (26, -30)], "paper", 0.68, group="feed")
    for i in range(4):
        rig.rivet(31 + i * 4, -46, 0.9, mat="chalk", group="feed")
    rig.rivet(45, -24, 2.0, group="feed")
    # barrel, cooling rings, shroud
    P([(-18, -168), (18, -168), (20, -60), (-20, -60)], "gunmetal", 0.58)
    for yy in (-150, -122, -94):
        R(-19, yy, 19, yy + 8, "brass", 0.55)
    R(-22, -182, 22, -166, "steel", 0.66)
    rig.disc(0, -176, 8, "void", 0.30, n=12)
    rig.disc(0, -176, 4, "void", 0.12, n=10)
    # bolt handle
    R(30, -60, 44, -50, "steel", 0.70, group="bolt")
    rig.disc(42, -55, 3, "brass", 0.60, group="bolt")
    # stencil lot marks
    rig.line([(-12, -44), (4, -44)], "chalk", 0.40, 1.0)
    rig.line([(-12, -38), (-4, -38)], "chalk", 0.34, 1.0)
    hand(rig, sup, "support", yaw=26, flip=-1, scale=0.76, part="glove")
    hand(rig, (16, 50), "grip", yaw=-20, flip=1, part="glove")
    return (0, -184)

def draw_plumb_bombard(rig, frame):
    P, R = rig.P, rig.rect
    sup = frame.get("support_anchor", (-16, -46))
    hand(rig, sup, "support", yaw=26, flip=-1, scale=0.76, part="sleeve")
    hand(rig, (16, 52), "grip", yaw=-22, flip=1, part="sleeve")
    P([(-18, 10), (18, 10), (22, 60), (-12, 64)], "oxblood", 0.46)
    for yy in range(22, 56, 10):
        rig.line([(-10, yy), (20, yy + 1)], "leather", 0.26, 0.6)
    R(-43, -30, 43, 18, "gunmetal", 0.55)
    # short wide tube with patina
    P([(-44, -152), (44, -152), (48, -40), (-48, -40)], "gunmetal", 0.60)
    P([(-24, -150), (-7, -152), (-5, -42), (-22, -42)], "steel", 0.70)
    P([(10, -146), (24, -142), (26, -120), (14, -124)], "verdigris", 0.44, False)
    P([(-30, -96), (-18, -92), (-16, -78), (-28, -82)], "verdigris", 0.38, False)
    for yy in (-136, -94, -52):
        R(-44, yy, 44, yy + 12, "brass", 0.60)
    rig.disc(0, -156, 33, "brass", 0.60, n=18)
    rig.disc(0, -156, 23, "void", 0.28, n=18)
    rig.disc(0, -156, 17, "void", 0.14, n=16)
    # theodolite sight bridge + level
    R(-30, -124, 30, -100, "brass", 0.55)
    rig.disc(-24, -112, 8, "void", 0.30, n=12)
    rig.disc(24, -112, 6, "energy", 0.50, n=12)
    P([(-8, -134), (12, -134), (10, -124), (-10, -124)], "energy", 0.40)
    rig.disc(1, -129, 3, "chalk", 0.90, n=10)
    # fore grip, breech plate, side shell rack
    R(-13, -70, 13, -36, "walnut", 0.45)
    R(22, -72, 46, -24, "brass", 0.55, group="breech")
    rig.disc(42, -64, 6, "brass", 0.35, group="breech")
    rig.rivet(28, -34, 2.0, group="breech")
    P([(30, -58), (48, -56), (46, -30), (28, -32)], "brass", 0.62, group="shell")
    P([(32, -54), (46, -53), (45, -36), (31, -37)], "warning", 0.40, group="shell")
    rig.rivet(38, -44, "shell", 2.0)
    rig.line([(-24, -80), (-8, -80)], "chalk", 0.35, 1.0)
    rig.line([(-24, -74), (-12, -74)], "chalk", 0.30, 1.0)
    sup = frame.get("support_anchor", (-16, -46))
    hand(rig, sup, "support", yaw=26, flip=-1, scale=0.76, part="glove")
    hand(rig, (16, 52), "grip", yaw=-22, flip=1, part="glove")
    return (0, -170)

def draw_aethometer(rig, frame):
    P, R = rig.P, rig.rect
    sup = frame.get("support_anchor", (-16, -54))
    hand(rig, sup, "support", yaw=26, flip=-1, scale=0.76, part="sleeve")
    hand(rig, (16, 48), "grip", yaw=-20, flip=1, part="sleeve")
    P([(-15, 10), (17, 10), (20, 56), (-10, 62)], "leather", 0.46)
    for yy in range(22, 54, 9):
        rig.line([(-8, yy), (19, yy + 1)], "leather", 0.24, 0.6)
    R(-30, -18, 28, 12, "gunmetal", 0.55)
    R(-38, -96, 34, -10, "gunmetal", 0.58)
    P([(-24, -92), (16, -92), (10, -12), (-26, -12)], "brass", 0.50)
    # pressure gauge
    rig.disc(-4, -56, 16, "brass", 0.50, n=18)
    rig.disc(-4, -56, 13, "paper", 0.80, n=16)
    rig.line([(-4, -56), (3, -64)], "warning", 0.50, 1.0)
    rig.rivet(-4, -56, 1.6)
    # tapered emitter with brass coils
    P([(-27, -92), (23, -92), (16, -150), (-16, -150)], "brass", 0.55)
    P([(-24, -92), (-14, -92), (-10, -150), (-14, -150)], "brass", 0.70)
    for yy in (-102, -120, -138):
        R(-26, yy, 22, yy + 6, "brass", 0.58)
    # glass condenser segment
    P([(-9, -146), (9, -146), (8, -116), (-8, -116)], "energy", 0.50, group="vent")
    P([(-6, -142), (-1, -142), (-2, -120), (-6, -120)], "chalk", 0.60, group="vent")
    rig.line([(-9, -130), (8, -130)], "energy", 0.75, 0.8, group="vent")
    # muzzle prongs and core
    for sx in (-1, 1):
        for i in range(3):
            x = sx * (10 + i * 5)
            P([(x, -168), (x + 3, -168), (x + sx * 2, -148), (x - sx * 2, -148)], "brass", 0.55)
    rig.disc(0, -160, 9, "energy", 0.70, group="vent")
    rig.disc(0, -160, 4, "chalk", 0.95, group="vent")
    # side condenser and lever
    rig.disc(24, -72, 10, "energy", 0.45)
    rig.disc(24, -72, 6, "brass", 0.35)
    P([(18, -30), (28, -34), (36, -52), (28, -54)], "brass", 0.60, group="lever")
    rig.rivet(28, -40, "lever", 2.0)
    R(-13, -64, 13, -30, "walnut", 0.45)
    sup = frame.get("support_anchor", (-16, -54))
    hand(rig, sup, "support", yaw=26, flip=-1, scale=0.76, part="glove")
    hand(rig, (16, 48), "grip", yaw=-20, flip=1, part="glove")
    return (0, -172)

def draw_hymnodyne(rig, frame):
    P, R = rig.P, rig.rect
    sup = frame.get("support_anchor", (-48, -14))
    hand(rig, sup, "support", yaw=26, flip=-1, scale=0.76, part="sleeve")
    hand(rig, (16, 56), "grip", yaw=-20, flip=1, part="sleeve")
    # censer chain and bob on the left
    for i, yy in enumerate(range(18, 92, 13)):
        rig.disc(-54 + (i % 2) * 3, yy, 4, "brass", 0.45, n=8)
        rig.disc(-54 + (i % 2) * 3, yy, 2, "void", 0.25, n=8)
    rig.disc(-52, 102, 10, "brass", 0.50, n=12)
    rig.disc(-52, 96, 4, "brass", 0.62, n=8)
    # housing and hub
    P([(-54, -24), (54, -24), (48, 18), (-48, 18)], "gunmetal", 0.55)
    P([(-45, -20), (45, -20), (38, 10), (-38, 10)], "brass", 0.50)
    rig.disc(0, -36, 33, "gunmetal", 0.60, n=20)
    rig.disc(0, -36, 24, "brass", 0.50, n=20)
    rig.disc(0, -36, 12, "bone", 0.65, n=16)
    rig.disc(0, -36, 5, "void", 0.30, n=12)
    P([(-42, 4), (-24, 2), (-22, 12), (-40, 14)], "bone", 0.60)
    P([(24, 2), (42, 4), (40, 14), (22, 12)], "bone", 0.60)
    rig.line([(-16, -10), (-8, -10)], "chalk", 0.45, 1.2)
    rig.line([(0, -10), (4, -10)], "chalk", 0.40, 1.2)
    rig.line([(10, -10), (18, -10)], "chalk", 0.45, 1.2)
    # five organ pipes, the ritual bank
    pipes = [(0, -184, 0), (-14, -168, -9), (14, -168, 9), (-26, -152, -17), (26, -152, 17)]
    for px, tipy, lean in pipes:
        base_y = -52
        tipx = px + lean * 0.8
        P([(px - 7, base_y), (px + 7, base_y), (tipx + 6, tipy), (tipx - 6, tipy)], "brass", 0.55, group="cluster")
        P([(px - 7, base_y), (px - 3, base_y), (tipx - 2, tipy), (tipx - 6, tipy)], "brass", 0.72, group="cluster")
        rig.line([(px, base_y - 2), (tipx, tipy + 8)], "void", 0.25, 1.0, group="cluster")
        R(px - 10, -62, px + 10, -52, "brass", 0.62, group="cluster")
        P([(tipx - 6, tipy), (tipx + 6, tipy), (tipx + 10, tipy - 8), (tipx - 10, tipy - 8)], "bone", 0.60, group="cluster")
        rig.line([(tipx, tipy - 1), (tipx, tipy - 7)], "void", 0.30, 0.9, group="cluster")
    # winding crank on the right
    rig.disc(52, -30, 7, "brass", 0.55, group="crank")
    P([(52, -30), (64, -26), (62, -38)], "brass", 0.65, group="crank")
    rig.rivet(63, -30, "crank", 2.2)
    # grip
    P([(-16, 16), (18, 16), (22, 62), (-12, 66)], "oxblood", 0.45)
    for yy in range(28, 58, 10):
        rig.line([(-8, yy), (19, yy + 1)], "leather", 0.26, 0.6)
    sup = frame.get("support_anchor", (-48, -14))
    hand(rig, sup, "support", yaw=26, flip=-1, scale=0.76, part="glove")
    hand(rig, (16, 56), "grip", yaw=-20, flip=1, part="glove")
    return (0, -184)

# ------------------------------------------------------------ frame tables ---
def melee_frames():
    spec = [
        ("idle", "Ready / sway loop", 900, 0, (0, 0), None),
        ("raise_low", "Raise start, weapon low", 90, 14, (18, 120), None),
        ("raise_mid", "Raise mid", 90, 6, (7, 46), None),
        ("windup", "Swing windup", 120, -8, (-6, -8), None),
        ("impact", "Swing impact (spark overlay)", 90, 17, (20, 8), "a"),
        ("follow", "Swing follow-through (spark tail)", 160, 25, (32, 18), "b"),
        ("recover", "Swing recover", 220, 8, (6, 4), None),
        ("guard", "Guard reset", 600, 3, (3, 2), None),
    ]
    out = []
    for i, (state, role, ms, rot, tr, flash) in enumerate(spec):
        out.append({"state": state, "role": role, "duration_ms": ms, "rot": rot, "tr": tr,
                    "groups": {}, "support_off": (0, 0), "flash_variant": flash})
    return out

def std_frames(recoil, settle, reload_a, reload_b, sup_a, sup_b):
    spec = [
        ("idle", "Ready loop; grip anchor pose", 900, 0.0, (0, 0), {}, (0, 0), None),
        ("raise_low", "Raise start, weapon low", 90, 12.0, (16, 118), {}, (0, 0), None),
        ("raise_mid", "Raise mid", 90, 5.0, (6, 46), {}, (0, 0), None),
        ("fire_peak", "Fire peak recoil", 60, -2.2, (-3, -4), recoil, (0, 0), "a"),
        ("fire_settle", "Fire settle, flash tail", 80, -1.0, (-1, -2), settle, (0, 0), "b"),
        ("recover", "Recoil recover", 110, 0.5, (0, 1), {}, (0, 0), None),
        ("reload_a", "Reload/cycle A", 240, 3.0, (4, 28), reload_a, sup_a, None),
        ("reload_b", "Reload/cycle B", 300, 1.5, (2, 12), reload_b, sup_b, None),
    ]
    out = []
    for state, role, ms, rot, tr, groups, sup, flash in spec:
        out.append({"state": state, "role": role, "duration_ms": ms, "rot": rot, "tr": tr,
                    "groups": groups, "support_off": sup, "flash_variant": flash})
    return out

WEAPONS = [
    {"id": "fathom_hook", "slot": "melee", "name": "Fathom Hook", "draw": draw_fathom_hook,
     "origin": (340, 390), "rot": 16.0, "muzzle": (-56, -162), "grip_anchor": (16, 12),
     "support_anchor": None, "frames": melee_frames(),
     "desc": "Surveyor's rule shaft, brass plumb counterweight, honed billhook; oxblood wrap; bone inlay.",
     "groups": []},
    {"id": "registrar", "slot": "sidearm", "name": "Registrar", "draw": draw_registrar,
     "origin": (372, 362), "rot": -14.0, "muzzle": (0, -112), "grip_anchor": (16, 48),
     "support_anchor": None,
     "frames": std_frames({"slide": (0, 9)}, {"slide": (0, 4)},
                          {"mag": (10, 34), "slide": (0, 6)}, {"mag": (3, 12)}, (0, 0), (0, 0)),
     "desc": "Rivet sidearm: gunmetal slide, brass register plate, vial sight, oxblood grip.",
     "groups": ["slide", "mag"]},
    {"id": "transit_12", "slot": "scattergun", "name": "Transit-12", "draw": draw_transit_12,
     "origin": (372, 366), "rot": -30.0, "muzzle": (0, -176), "grip_anchor": (16, 48),
     "support_anchor": (-36, -30),
     "frames": std_frames({"pump": (0, 3)}, {"pump": (0, 1)},
                          {"pump": (0, 26)}, {"pump": (0, 9)}, (0, 26), (0, 9)),
     "desc": "Pump scattergun built from a surveyor's level: walnut pump, octagonal barrel, brass level vial.",
     "groups": ["pump"]},
    {"id": "comptroller", "slot": "repeater", "name": "Comptroller", "draw": draw_comptroller,
     "origin": (380, 372), "rot": -28.0, "muzzle": (0, -184), "grip_anchor": (16, 50),
     "support_anchor": (-36, -30),
     "frames": std_frames({"bolt": (0, 7), "feed": (0, 2)}, {"bolt": (0, 3)},
                          {"feed": (0, 30), "bolt": (0, 5)}, {"feed": (0, 10), "bolt": (0, 1)},
                          (0, 0), (0, 0)),
     "desc": "Adding-machine repeater: paper feed, typebar fins, cooling rings, brass carry handle.",
     "groups": ["feed", "bolt"]},
    {"id": "plumb_bombard", "slot": "launcher", "name": "Plumb Bombard", "draw": draw_plumb_bombard,
     "origin": (375, 376), "rot": -24.0, "muzzle": (0, -170), "grip_anchor": (16, 52),
     "support_anchor": (-38, -24),
     "frames": std_frames({}, {},
                          {"breech": (0, 18), "shell": (0, 48)}, {"breech": (0, 6), "shell": (0, 14)},
                          (0, 0), (0, 0)),
     "desc": "Breech mortar / theodolite hybrid: wide brass-ringed tube, spirit level, side shell rack.",
     "groups": ["breech", "shell"]},
    {"id": "aethometer", "slot": "projector", "name": "Aethometer", "draw": draw_aethometer,
     "origin": (370, 374), "rot": -24.0, "muzzle": (0, -172), "grip_anchor": (16, 48),
     "support_anchor": (-38, -34),
     "frames": std_frames({"vent": (0, 2)}, {},
                          {"vent": (0, 22), "lever": (0, 10)}, {"vent": (0, 8), "lever": (0, 3)},
                          (0, 0), (0, 0)),
     "desc": "Aether projector: brass coils, glass condenser, pressure gauge, forbidden green discharge.",
     "groups": ["vent", "lever"]},
    {"id": "hymnodyne", "slot": "heavy", "name": "Hymnodyne", "draw": draw_hymnodyne,
     "origin": (372, 384), "rot": -14.0, "muzzle": (0, -184), "grip_anchor": (16, 56),
     "support_anchor": (-48, -14),
     "frames": std_frames({"cluster": (3, 0), "crank": (2, 0)}, {"cluster": (1, 0)},
                          {"cluster": (6, 0), "crank": (5, 4)}, {"cluster": (-3, 0), "crank": (1, 2)},
                          (0, 0), (0, 0)),
     "desc": "Heavy ritual instrument: five organ pipes on a brass hub, bone mouths, censer chain, winding crank.",
     "groups": ["cluster", "crank"]},
]

# ------------------------------------------------------------------- icons ---
def icon_paint(wid, seed):
    p = Paint(96, 64, 4, seed)
    def P(pts, mat, shade=0.6, edge=True):
        p.poly(pts, mat, shade, edge, 0.8)
    def R(x0, y0, x1, y1, mat, shade=0.6, edge=True):
        P([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], mat, shade, edge)
    def D(cx, cy, r, mat, shade=0.6, n=14):
        p.disc(cx, cy, r, mat, shade, n, True, 0.8)
    if wid == "fathom_hook":
        P([(26, 54), (33, 51), (54, 20), (49, 16)], "steel", 0.55)
        P([(35, 43), (42, 40), (49, 28), (42, 31)], "oxblood", 0.52)
        P([(44, 17), (52, 11), (60, 15), (58, 23), (50, 25)], "gunmetal", 0.62)
        P([(46, 15), (34, 8), (28, 11), (31, 18), (39, 20), (46, 19)], "steel", 0.74)
        p.line([(34, 10), (29, 12), (31, 17)], "chalk", 0.9, 0.8)
        D(60, 20, 4, "brass", 0.66)
        D(60, 20, 1.6, "brass", 0.35, 8)
        p.line([(26, 49), (31, 47)], "chalk", 0.65, 0.7)
        p.line([(30, 44), (35, 42)], "warning", 0.5, 0.8)
    elif wid == "registrar":
        R(16, 25, 22, 33, "steel", 0.72)
        D(17, 29, 2.4, "void", 0.25, 10)
        R(22, 23, 62, 32, "gunmetal", 0.64)
        P([(22, 23), (62, 23), (64, 26), (22, 27)], "steel", 0.76)
        R(36, 26, 56, 31, "brass", 0.62)
        P([(54, 32), (64, 32), (70, 50), (60, 52)], "oxblood", 0.52)
        P([(22, 32), (28, 32), (27, 39), (21, 39)], "gunmetal", 0.4)
        R(36, 32, 52, 34, "gunmetal", 0.45)
        P([(28, 18), (33, 16), (35, 21), (30, 23)], "brass", 0.62)
        D(31, 19, 1.8, "energy", 0.8, 8)
        R(16, 34, 20, 44, "brass", 0.55)
    elif wid == "transit_12":
        P([(12, 27), (54, 25), (54, 32), (12, 33)], "steel", 0.64)
        P([(12, 27), (54, 25), (54, 28), (12, 30)], "steel", 0.78)
        R(50, 22, 68, 38, "gunmetal", 0.6)
        P([(66, 26), (86, 33), (86, 41), (66, 38)], "walnut", 0.46)
        P([(84, 32), (88, 33), (88, 41), (84, 40)], "brass", 0.55)
        P([(26, 33), (42, 32), (42, 41), (26, 42)], "walnut", 0.52)
        P([(24, 33), (26, 32), (26, 42), (24, 41)], "brass", 0.6)
        R(48, 17, 64, 22, "brass", 0.6)
        D(56, 19, 2.2, "energy", 0.75, 10)
        D(12, 30, 2.6, "void", 0.25, 10)
        P([(46, 22), (50, 22), (50, 26), (46, 26)], "brass", 0.6)
        p.line([(14, 32), (22, 32)], "chalk", 0.4, 0.7)
    elif wid == "comptroller":
        P([(10, 27), (30, 26), (30, 35), (10, 36)], "gunmetal", 0.6)
        R(28, 20, 62, 40, "gunmetal", 0.6)
        P([(28, 20), (62, 20), (60, 24), (28, 24)], "steel", 0.72)
        R(32, 18, 54, 22, "brass", 0.55)
        P([(36, 18), (42, 17), (44, 23), (38, 24)], "paper", 0.7)
        P([(30, 12), (34, 12), (34, 18), (30, 18)], "brass", 0.5)
        P([(52, 12), (56, 12), (56, 18), (52, 18)], "brass", 0.5)
        R(30, 9, 56, 13, "brass", 0.6)
        R(60, 24, 72, 38, "brass", 0.55)
        P([(62, 26), (70, 26), (68, 36), (60, 36)], "paper", 0.66)
        P([(46, 40), (58, 40), (62, 56), (50, 57)], "walnut", 0.48)
        P([(26, 28), (30, 27), (32, 34), (28, 35)], "brass", 0.46)
        P([(26, 35), (30, 34), (32, 41), (28, 42)], "brass", 0.46)
        D(12, 31, 2.2, "void", 0.3, 10)
    elif wid == "plumb_bombard":
        # fat breech mortar, muzzle up-left, side shell and fore-grip
        P([(16, 46), (22, 43), (40, 12), (32, 8)], "gunmetal", 0.60)
        P([(16, 46), (22, 43), (27, 31), (22, 34)], "steel", 0.72)
        P([(19, 14), (28, 5), (41, 11), (33, 20)], "brass", 0.62)
        D(29, 12, 5, "void", 0.30, 14)
        D(29, 12, 2.2, "void", 0.14, 10)
        for yy, xx in ((36, 24), (26, 28), (16, 33)):
            P([(xx - 8, yy + 1), (xx + 8, yy - 1), (xx + 9, yy + 4), (xx - 7, yy + 6)], "brass", 0.60)
        R(31, 25, 45, 34, "brass", 0.55)
        D(34, 29, 3.4, "energy", 0.62, 10)
        P([(34, 34), (44, 33), (50, 48), (38, 52)], "walnut", 0.46)
        P([(24, 36), (32, 35), (34, 46), (26, 47)], "walnut", 0.50)
        P([(36, 36), (48, 36), (48, 44), (36, 44)], "brass", 0.54)
        P([(38, 38), (46, 38), (46, 42), (38, 42)], "warning", 0.42)
        p.line([(20, 40), (28, 36)], "chalk", 0.35, 0.7)
    elif wid == "aethometer":
        # emitter up-left, brass coils, glass core, gauge, grip
        P([(12, 24), (20, 22), (20, 34), (12, 33)], "brass", 0.60)
        D(18, 28, 3.4, "energy", 0.80, 12)
        P([(20, 20), (56, 18), (58, 38), (20, 39)], "gunmetal", 0.60)
        P([(24, 21), (34, 20), (34, 38), (24, 38)], "brass", 0.50)
        P([(26, 22), (32, 22), (32, 36), (26, 36)], "energy", 0.55)
        p.line([(26, 23), (32, 23)], "chalk", 0.75, 0.8)
        for xx in (38, 44, 50):
            P([(xx, 19), (xx + 3, 19), (xx + 3, 39), (xx, 39)], "brass", 0.55)
        D(54, 28, 5, "brass", 0.50)
        D(54, 28, 3.6, "paper", 0.75, 12)
        p.line([(54, 28), (56, 25)], "warning", 0.55, 0.7)
        P([(52, 38), (64, 38), (68, 54), (58, 55)], "leather", 0.48)
        D(60, 34, 4, "energy", 0.45, 10)
        P([(58, 31), (62, 30), (63, 35), (59, 36)], "brass", 0.55)
    elif wid == "aethometer":
        P([(12, 26), (20, 24), (20, 35), (12, 34)], "brass", 0.6)
        D(18, 29, 3.2, "energy", 0.8, 12)
        P([(20, 21), (56, 19), (58, 38), (20, 39)], "gunmetal", 0.6)
        P([(24, 22), (34, 21), (34, 38), (24, 38)], "brass", 0.5)
        P([(26, 23), (32, 23), (32, 36), (26, 36)], "energy", 0.55)
        p.line([(26, 24), (32, 24)], "chalk", 0.75, 0.8)
        for xx in (38, 44, 50):
            P([(xx, 20), (xx + 3, 20), (xx + 3, 39), (xx, 39)], "brass", 0.55)
        D(54, 28, 5, "brass", 0.5)
        D(54, 28, 3.6, "paper", 0.75, 12)
        p.line([(54, 28), (56, 25)], "warning", 0.55, 0.7)
        P([(52, 39), (64, 39), (68, 54), (58, 55)], "leather", 0.48)
        D(24, 44, 4, "energy", 0.45, 10)
    elif wid == "hymnodyne":
        R(36, 38, 60, 50, "gunmetal", 0.55)
        D(48, 36, 10, "brass", 0.55, 16)
        D(48, 36, 6, "bone", 0.65, 12)
        D(48, 36, 2.4, "void", 0.3, 10)
        pipes = [(48, 8, 0), (37, 10, -5), (59, 10, 5), (29, 16, -8), (67, 16, 8)]
        for tipx, tipy, lean in pipes:
            bx = 48 + lean * 0.6
            P([(bx - 4, 30), (bx + 4, 30), (tipx + 3, tipy), (tipx - 3, tipy)], "brass", 0.58)
            p.line([(bx, 30), (tipx, tipy + 3)], "void", 0.28, 0.7)
            P([(tipx - 3, tipy), (tipx + 3, tipy), (tipx + 5, tipy - 2), (tipx - 5, tipy - 2)], "bone", 0.62)
        D(22, 34, 3, "brass", 0.5, 8)
        D(22, 40, 3, "brass", 0.5, 8)
        D(24, 46, 4, "brass", 0.52, 10)
        P([(54, 46), (64, 46), (68, 60), (58, 61)], "oxblood", 0.46)
        P([(62, 32), (72, 30), (70, 40)], "brass", 0.62)
    return p.finish()

# --------------------------------------------------------------- assembly ---
def seed_for(text):
    return int(hashlib.sha256(("nullrun-weapons-v1:" + text).encode()).hexdigest()[:8], 16) % 100000

def alpha_bbox(img):
    bb = img.getchannel("A").getbbox()
    if bb is None:
        return None
    return [bb[0], bb[1], bb[2] - 1, bb[3] - 1]

def checker_bg(w, h, size=12):
    img = Image.new("RGB", (w, h), (25, 27, 31))
    d = ImageDraw.Draw(img)
    for y in range(0, h, size):
        for x in range(0, w, size):
            if ((x // size) + (y // size)) % 2 == 0:
                d.rectangle([x, y, x + size - 1, y + size - 1], fill=(34, 37, 42))
    return img

def paste_checker(cell_w, cell_h, img, label=None, title=False, font=None):
    bg = checker_bg(cell_w, cell_h)
    im = img.resize((cell_w, cell_h), Image.LANCZOS)
    bg.paste(im, (0, 0), im)
    return bg

def make_slot_sheet(w, bodies, out_path):
    cw, ch = 320, 200
    cols, rows = 4, 2
    margin, header, labelh = 10, 42, 22
    sw = cols * cw + (cols + 1) * margin
    sh = header + rows * (ch + labelh + margin) + margin
    sheet = Image.new("RGB", (sw, sh), (18, 20, 23))
    d = ImageDraw.Draw(sheet)
    f_title = ImageFont.load_default(size=20)
    f_lbl = ImageFont.load_default(size=13)
    d.text((margin, 10), f"{w['name']}  [{w['slot']}]  -  idle / raise / fire / cycle", font=f_title, fill=(226, 222, 208))
    for i, fr in enumerate(w["frames"]):
        r, c = divmod(i, cols)
        x = margin + c * (cw + margin)
        y = header + r * (ch + labelh + margin)
        cell = paste_checker(cw, ch, bodies[i])
        cd = ImageDraw.Draw(cell)
        # y=240 body line and central x band, downscaled 50%
        cd.line([(0, 120), (cw, 120)], fill=(70, 96, 104), width=1)
        cd.line([(110, 0), (110, 95)], fill=(52, 62, 70), width=1)
        cd.line([(210, 0), (210, 95)], fill=(52, 62, 70), width=1)
        sheet.paste(cell, (x, y))
        st = fr["state"]
        d.text((x, y + ch + 3), f"{i:02d} {st}  {fr['duration_ms']}ms", font=f_lbl, fill=(196, 192, 178))
    sheet.save(out_path)
    return sheet

def make_flash_sheet(flash_items, out_path):
    cw, ch = 240, 150
    cols = 4
    rows = (len(flash_items) + cols - 1) // cols
    margin, header, labelh = 10, 42, 20
    sw = cols * cw + (cols + 1) * margin
    sh = header + rows * (ch + labelh + margin) + margin
    sheet = Image.new("RGB", (sw, sh), (18, 20, 23))
    d = ImageDraw.Draw(sheet)
    f_title = ImageFont.load_default(size=20)
    f_lbl = ImageFont.load_default(size=13)
    d.text((margin, 10), "Muzzle / discharge overlays (separate RGBA, 640x400)", font=f_title, fill=(226, 222, 208))
    for i, (label, img) in enumerate(flash_items):
        r, c = divmod(i, cols)
        x = margin + c * (cw + margin)
        y = header + r * (ch + labelh + margin)
        sheet.paste(paste_checker(cw, ch, img), (x, y))
        d.text((x, y + ch + 3), label, font=f_lbl, fill=(196, 192, 178))
    sheet.save(out_path)
    return sheet

def make_icon_sheet(items, out_path):
    cw, ch = 288, 192
    cols = 4
    rows = (len(items) + cols - 1) // cols
    margin, header, labelh = 10, 42, 22
    sw = cols * cw + (cols + 1) * margin
    sh = header + rows * (ch + labelh + margin) + margin
    sheet = Image.new("RGB", (sw, sh), (18, 20, 23))
    d = ImageDraw.Draw(sheet)
    f_title = ImageFont.load_default(size=20)
    f_lbl = ImageFont.load_default(size=13)
    d.text((margin, 10), "Pickup icons, original 96x64 RGBA (shown at 3x)", font=f_title, fill=(226, 222, 208))
    for i, (label, img) in enumerate(items):
        r, c = divmod(i, cols)
        x = margin + c * (cw + margin)
        y = header + r * (ch + labelh + margin)
        bg = checker_bg(cw, ch, 16)
        big = img.resize((cw, ch), Image.NEAREST)
        bg.paste(big, (0, 0), big)
        sheet.paste(bg, (x, y))
        d.text((x, y + ch + 3), label, font=f_lbl, fill=(196, 192, 178))
    sheet.save(out_path)
    return sheet

def make_master_sheet(items, out_path):
    cw, ch = 320, 200
    cols = 4
    rows = (len(items) + cols - 1) // cols
    margin, header, labelh = 10, 44, 22
    sw = cols * cw + (cols + 1) * margin
    sh = header + rows * (ch + labelh + margin) + margin
    sheet = Image.new("RGB", (sw, sh), (18, 20, 23))
    d = ImageDraw.Draw(sheet)
    f_title = ImageFont.load_default(size=20)
    f_lbl = ImageFont.load_default(size=13)
    d.text((margin, 10), "Null Run - original weapon bank v1 - idle frames (50%)", font=f_title, fill=(226, 222, 208))
    for i, (label, img) in enumerate(items):
        r, c = divmod(i, cols)
        x = margin + c * (cw + margin)
        y = header + r * (ch + labelh + margin)
        cell = paste_checker(cw, ch, img)
        ImageDraw.Draw(cell).line([(0, 120), (cw, 120)], fill=(70, 96, 104), width=1)
        sheet.paste(cell, (x, y))
        d.text((x, y + ch + 3), label, font=f_lbl, fill=(196, 192, 178))
    sheet.save(out_path)
    return sheet


def make_fire_sheet(items, out_path):
    cw, ch = 320, 200
    cols = 4
    rows = (len(items) + cols - 1) // cols
    margin, header, labelh = 10, 44, 22
    sw = cols * cw + (cols + 1) * margin
    sh = header + rows * (ch + labelh + margin) + margin
    sheet = Image.new("RGB", (sw, sh), (18, 20, 23))
    d = ImageDraw.Draw(sheet)
    f_title = ImageFont.load_default(size=20)
    f_lbl = ImageFont.load_default(size=13)
    d.text((margin, 10), "Fire/impact frames with their aligned flash overlays (50%)", font=f_title, fill=(226, 222, 208))
    for i, (label, img) in enumerate(items):
        r, c = divmod(i, cols)
        x = margin + c * (cw + margin)
        y = header + r * (ch + labelh + margin)
        bg = checker_bg(640, 400, 16)
        bg = bg.convert("RGBA")
        bg.alpha_composite(img)
        sheet.paste(bg.convert("RGB").resize((cw, ch), Image.LANCZOS), (x, y))
        d.text((x, y + ch + 3), label, font=f_lbl, fill=(196, 192, 178))
    sheet.save(out_path)
    return sheet

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent))
    ap.add_argument("--seed", type=int, default=20261031)
    args = ap.parse_args()
    out = Path(args.out)
    (out / "frames").mkdir(parents=True, exist_ok=True)
    (out / "flashes").mkdir(parents=True, exist_ok=True)
    (out / "icons").mkdir(parents=True, exist_ok=True)
    (out / "sheets").mkdir(parents=True, exist_ok=True)

    manifest = {
        "pack": "nullrun-original-weapons-v1",
        "generator": "generate_weapons.py (pure CPU, Pillow/NumPy, no external art)",
        "seed": args.seed,
        "canvas": {"width": W, "height": H, "mode": "RGBA", "origin": "top-left, inclusive pixel coordinates"},
        "safe_view": {
            "aim_clear_rect": [220, 40, 420, 180],
            "body_frames_max_y": 189,
            "above_y_240_x_band": [250, 440],
            "bottom_crop_y": H,
            "notes": "Body frames keep the central aiming rectangle empty; muzzle/pipe tips may enter y>=190 only inside x 250..440. Forearms are deliberately cropped by the bottom edge, never by the sides."
        },
        "frame_conventions": {
            "suggested_native_sprite": "640x400 RGBA at 1:1, bottom weapon layer",
            "suggested_native_pickup": "96x64 RGBA at 1:1, integer scaling only",
            "native_frame": "Use each 640x400 RGBA frame as a full-screen bottom-layer sprite at (0,0).",
            "anchor": "Frames are pre-anchored to the 640x400 viewport; no per-frame origin shifts needed.",
            "flash": "Overlay flash PNGs at (0,0) on the same viewport; they are already aligned to the matching body frame.",
            "timings": "duration_ms is the dwell time for that single image; raise order is raise_low -> raise_mid -> idle.",
            "warning": "Mapping labels below are descriptive only. No engine API, ZScript function or runtime test is claimed."
        },
        "slots": [],
    }
    geometry = {"pack": manifest["pack"], "weapons": []}
    bodies_store = {}
    flashes_store = {}
    icons_store = {}
    meta_by_id = {w["id"]: w for w in WEAPONS}

    for w in WEAPONS:
        wid = w["id"]
        wpath = out / "frames" / w["slot"]
        wpath.mkdir(parents=True, exist_ok=True)
        frames_meta = []
        bodies = []
        seed = (args.seed + seed_for(wid)) % (2**31 - 1)
        for idx, fr in enumerate(w["frames"]):
            f = dict(fr)
            if w["support_anchor"] is not None:
                f["support_anchor"] = (w["support_anchor"][0] + fr["support_off"][0],
                                       w["support_anchor"][1] + fr["support_off"][1])
            p = Paint(W, H, SS, seed)
            rig = Rig(p, (w["origin"][0] + fr["tr"][0], w["origin"][1] + fr["tr"][1]),
                      w["rot"] + fr["rot"], fr["groups"])
            w["draw"](rig, f)
            img = p.finish()
            name = f"{wid}_{idx:02d}_{fr['state']}.png"
            rel = f"frames/{w['slot']}/{name}"
            img.save(out / rel)
            bb = alpha_bbox(img)
            alpha_px = int((np.asarray(img.getchannel('A')) > 0).sum())
            mz = rig.W(w["muzzle"][0], w["muzzle"][1])
            fr_meta = {
                "index": idx,
                "file": rel,
                "state": fr["state"],
                "role": fr["role"],
                "duration_ms": fr["duration_ms"],
                "generation_pose": {
                    "base_rotation_deg": w["rot"],
                    "frame_rotation_deg": fr["rot"],
                    "total_rotation_deg": round(w["rot"] + fr["rot"], 3),
                    "translate_px": list(fr["tr"]),
                    "part_offsets_px": {k: list(v) for k, v in fr["groups"].items()},
                    "support_offset_px": list(fr["support_off"]),
                },
                "content_bbox": bb,
                "alpha_pixels": alpha_px,
                "muzzle_world": [round(mz[0], 1), round(mz[1], 1)],
                "flash": None,
            }
            if fr["flash_variant"]:
                flash_rel = f"flashes/{wid}_flash_{fr['flash_variant']}.png"
                fr_meta["flash"] = flash_rel
            frames_meta.append(fr_meta)
            bodies.append(img)
        bodies_store[wid] = bodies
        # flashes, generated from the fire poses so they line up with those frames
        flash_meta = []
        for variant in ("a", "b"):
            matches = [fm for fm in frames_meta if fm["flash"] and fm["flash"].endswith(f"_{variant}.png")]
            if not matches:
                continue
            fm = matches[0]
            fsrc = w["frames"][fm["index"]]
            rig = Rig(None, (w["origin"][0] + fsrc["tr"][0], w["origin"][1] + fsrc["tr"][1]),
                       w["rot"] + fsrc["rot"], fsrc["groups"])
            mz = rig.W(w["muzzle"][0], w["muzzle"][1])
            angle = w["rot"] + fsrc["rot"]
            seed_f = (args.seed + seed_for(wid + ":" + variant)) % (2**31 - 1)
            fimg = render_flash(wid, variant, mz, angle, seed_f)
            rel = f"flashes/{wid}_flash_{variant}.png"
            fimg.save(out / rel)
            flash_meta.append({
                "file": rel,
                "variant": variant,
                "for_frame_index": fm["index"],
                "for_state": fm["state"],
                "muzzle_world": [round(mz[0], 1), round(mz[1], 1)],
                "duration_ms": fm["duration_ms"],
                "content_bbox": alpha_bbox(fimg),
                "alpha_pixels": int((np.asarray(fimg.getchannel('A')) > 0).sum()),
                "blend_hint": "alpha-over; optional additive blend if the engine supports it",
                "style": FLASH_STYLE[wid],
            })
            flashes_store[f"{wid}:{variant}"] = fimg
        # icon
        iseed = (args.seed + seed_for(wid + ":icon")) % (2**31 - 1)
        iimg = icon_paint(wid, iseed)
        irel = f"icons/{wid}_icon_96x64.png"
        iimg.save(out / irel)
        icons_store[wid] = iimg
        icon_meta = {
            "file": irel,
            "canvas": [96, 64],
            "content_bbox": alpha_bbox(iimg),
            "alpha_pixels": int((np.asarray(iimg.getchannel('A')) > 0).sum()),
            "suggested_native_size": [96, 64],
            "notes": "Side-profile pickup sprite; weapon only, no hands; transparent margin on all sides."
        }
        slot_meta = {
            "slot": w["slot"],
            "id": wid,
            "name": w["name"],
            "description": w["desc"],
            "origin": list(w["origin"]),
            "base_rotation_deg": w["rot"],
            "grip_anchor_local": list(w["grip_anchor"]),
            "support_anchor_local": list(w["support_anchor"]) if w["support_anchor"] else None,
            "muzzle_local": list(w["muzzle"]),
            "animated_groups": w["groups"],
            "frames": frames_meta,
            "flashes": flash_meta,
            "icon": icon_meta,
            "suggested_mapping": {
                "ready": "idle",
                "raise": ["raise_low", "raise_mid", "idle"],
                "fire": ["fire_peak", "fire_settle", "recover"],
                "cycle_or_reload": ["reload_a", "reload_b", "idle"],
                "melee_attack": ["windup", "impact", "follow", "recover"] if wid == "fathom_hook" else None,
                "note": "Descriptive labels for a proposed integration; not tied to or tested against any engine."
            }
        }
        manifest["slots"].append(slot_meta)
        geometry["weapons"].append({
            "id": wid, "slot": w["slot"], "name": w["name"], "description": w["desc"],
            "origin": list(w["origin"]), "base_rotation_deg": w["rot"],
            "grip_anchor_local": list(w["grip_anchor"]),
            "support_anchor_local": list(w["support_anchor"]) if w["support_anchor"] else None,
            "muzzle_local": list(w["muzzle"]),
            "animated_groups": w["groups"],
            "frame_states": [{"state": f["state"], "rot": f["rot"], "tr": list(f["tr"]),
                              "groups": {k: list(v) for k, v in f["groups"].items()},
                              "support_off": list(f["support_off"]), "duration_ms": f["duration_ms"]}
                             for f in w["frames"]],
            "construction": "procedurally painted extruded polygons in generate_weapons.py; local coords, y up-negative, grip pivot at (0,0)",
        })

    # sheets
    for w in WEAPONS:
        make_slot_sheet(w, bodies_store[w["id"]], out / "sheets" / f"{w['slot']}_sheet.png")
    flash_items = []
    for w in WEAPONS:
        for variant in ("a", "b"):
            key = f"{w['id']}:{variant}"
            if key in flashes_store:
                flash_items.append((f"{w['name']} / flash {variant.upper()}", flashes_store[key]))
    make_flash_sheet(flash_items, out / "sheets" / "flashes_sheet.png")
    icon_items = [(f"{w['name']} [{w['slot']}]", icons_store[w["id"]]) for w in WEAPONS]
    make_icon_sheet(icon_items, out / "sheets" / "icons_sheet.png")
    master_items = [(f"{w['name']} [{w['slot']}]", bodies_store[w["id"]][0]) for w in WEAPONS]
    make_master_sheet(master_items, out / "sheets" / "master_sheet.png")

    # composite preview: body frame plus its separate flash overlay, exactly as
    # the proposed integration would stack them at (0,0)
    fire_items = []
    for w in WEAPONS:
        wid = w["id"]
        for variant in ("a", "b"):
            if f"{wid}:{variant}" not in flashes_store:
                continue
            fm = next(x for x in manifest["slots"][[q["id"] for q in WEAPONS].index(wid)]["frames"]
                      if x["flash"] and x["flash"].endswith(f"_{variant}.png"))
            comp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            comp.alpha_composite(bodies_store[wid][fm["index"]])
            comp.alpha_composite(flashes_store[f"{wid}:{variant}"])
            fire_items.append((f"{w['name']} / {fm['state']} + flash {variant.upper()}", comp))
    make_fire_sheet(fire_items, out / "sheets" / "fire_composite_sheet.png")

    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out / "materials.json").write_text(json.dumps({
        "pack": manifest["pack"],
        "notes": "Palette ramps are indexed dark->light; shade values in geometry pick a position; per-pixel deterministic noise is applied at paint time.",
        "materials": MATERIALS
    }, indent=2) + "\n")
    (out / "geometry.json").write_text(json.dumps(geometry, indent=2) + "\n")

    # README / provenance / integration notes
    lines = [
        "# Null Run - original weapon and hand art bank v1",
        "",
        "Seven functional slots, original industrial-occult instruments and one coherent glove/sleeve design.",
        "Generated on CPU from `generate_weapons.py`; no IWAD pixels, no Freedoom/Doom recolours, no external images.",
        "",
        "## Contents",
        "",
        "- `frames/<slot>/` - 8 RGBA body frames per slot, 640x400, bottom-half view sprite.",
        "- `flashes/` - 14 separate RGBA discharge overlays (2 per slot), pre-aligned to fire frames.",
        "- `icons/` - 7 original 96x64 pickup icons.",
        "- `sheets/` - per-slot contact sheets, flash sheet, icon sheet, master sheet and",
        "  a fire-composite preview that stacks each body fire frame with its overlay.",
        "- `manifest.json` - roles, timings, poses, offsets, bboxes, muzzle points, safe region.",
        "- `materials.json`, `geometry.json` - palette and construction source data.",
        "- `PROVENANCE.md`, `INTEGRATION.md`, `validation_report.json`, `SHA256SUMS`.",
        "- `SHA256SUMS` covers every artefact except itself and `validation_report.json`",
        "  (the report is written after the sums and records the validation run).",
        "",
        "## Regenerate",
        "",
        "```",
        "/home/echevarian/miniconda3/envs/hydrapy/bin/python generate_weapons.py --out .",
        "/home/echevarian/miniconda3/envs/hydrapy/bin/python validate.py",
        "```",
        "",
        "## Slots",
        "",
        "| slot | name | frames | notes |",
        "|---|---|---|---|",
    ]
    for w in WEAPONS:
        lines.append(f"| {w['slot']} | {w['name']} | 8 | {w['desc']} |")
    lines += [
        "",
        "## Frame timing (all slots)",
        "",
        "| state | ms | role |",
        "|---|---|---|",
        "| idle | 900 | ready loop |",
        "| raise_low / raise_mid | 90 + 90 | raise; play low then mid, then idle |",
        "| fire_peak / fire_settle | 60 + 80 | recoil, overlay flash A then B |",
        "| recover | 110 | return to idle |",
        "| reload_a / reload_b | 240 + 300 | cycle, pump, feed or breech depending on slot |",
        "",
        "Melee substitutes windup (120), impact (90, spark A), follow (160, spark B), recover (220), guard (600).",
        "Per-slot roles and exact timings are in `manifest.json`.",
        "",
        "## Safe view",
        "",
        "Body frames leave x 220..420, y 40..180 empty; muzzle/pipe tips only enter y>=190 inside x 250..440.",
        "Idle bodies sit broadly below y=240. Flashes are allowed above that, as overlays.",
        "",
        "## Limits",
        "",
        "- Painted noise is sampled in screen space, so its grain is fixed in the frame rather than stuck to each surface.",
        "- Poses are baked 2D approximations of a 3D view; part animation uses small translations, not true articulation.",
        "- Contact sheets are for review; the individual frames are the deliverable.",
        "- No engine integration or ZScript API testing was done. See INTEGRATION.md.",
    ]
    (out / "README.md").write_text("\n".join(lines) + "\n")
    (out / "PROVENANCE.md").write_text(
        "# Provenance and licence\n\n"
        "All images in this pack were produced procedurally by `generate_weapons.py` on this machine on 2026-11-01, "
        "using only Python, Pillow and NumPy. No photographs, scans, Freedoom or Doom/IWAD sprite pixels, external "
        "textures or third-party models were used. The game frames contain no text or embedded fonts; only the review "
        "contact sheets use Pillow's bundled default label font. Names, silhouettes, material language and the "
        "glove/sleeve design are original to this pack.\n\n"
        "The Quake-era chunky polygon/painted-texture look is a broad stylistic target, not a copy of any specific "
        "weapon, logo, pose or asset. No weapon in the pack is intended to read as a real firearm or a recognisable "
        "franchise design.\n\n"
        "Released CC0-1.0 to the extent possible, for Josiah's Null Run project. Josiah may relicense the pack. "
        "The generator and manifests may be reused and modified freely.\n"
    )
    (out / "INTEGRATION.md").write_text(
        "# Proposed integration notes (not tested in an engine)\n\n"
        "This is art replacement only: no balance, damage, ammo, sound or engine-behaviour changes are proposed or "
        "tested. Nothing below claims a working ZScript/ACS/engine API; treat it as a layout description.\n\n"
        "## Body frames\n\n"
        "Each `frames/<slot>/<id>_<index>_<state>.png` is a 640x400 RGBA image already anchored to the viewport. "
        "Draw it at screen (0,0) on the bottom weapon layer. The central aiming rect (220,40)-(420,180) is empty. "
        "Forearms reach the bottom edge deliberately; other edges are untouched.\n\n"
        "Suggested sequence, using the manifest state names:\n\n"
        "- Ready: loop `idle` at 900 ms (or hold).\n"
        "- Raise: `raise_low` 90 ms, `raise_mid` 90 ms, then `idle`.\n"
        "- Fire: `fire_peak` 60 ms + flash A, `fire_settle` 80 ms + flash B, `recover` 110 ms, `idle`.\n"
        "- Cycle/reload: `reload_a` 240 ms, `reload_b` 300 ms, `idle`. Melee: `windup`, `impact` + spark A, "
        "`follow` + spark B, `recover`, `guard`.\n\n"
        "If the engine needs explicit offsets/pivots, use the manifest's `origin`, `content_bbox` and per-frame "
        "`generation_pose`; the baked frames need none. Muzzle points are recorded for flash or light spawning.\n\n"
        "## Flashes\n\n"
        "Flash PNGs are separate 640x400 RGBA overlays generated from the matching fire frame's pose. Composite at "
        "(0,0) over the body layer with normal alpha, or additively if the renderer supports it. The manifest records "
        "`muzzle_world`, `for_frame_index` and `duration_ms`. Flash alpha is already anti-aliased and has no opaque "
        "background.\n\n"
        "## Icons\n\n"
        "`icons/<id>_icon_96x64.png` is a side-profile pickup sprite with a transparent margin. Native size is 96x64; "
        "scale by an integer factor for larger HUD use.\n\n"
        "## What is not provided\n\n"
        "No DECORATE/ZScript/ACS, no wad/pk3 packaging, no palette conversion, no HUD layout, no audio. The frames "
        "are true-colour RGBA; conversion to a limited palette is a game-side decision.\n"
    )

    # preliminary sums (validate.py rewrites this after adding itself/report exclusions)
    sums = []
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name not in ("SHA256SUMS", "validation_report.json"):
            if "__pycache__" in path.parts:
                continue
            h = hashlib.sha256(path.read_bytes()).hexdigest()
            sums.append(f"{h}  {path.relative_to(out).as_posix()}")
    (out / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    nf = sum(len(w["frames"]) for w in WEAPONS)
    print(f"wrote {nf} frames, {sum(2 for _ in WEAPONS)} flashes, {len(WEAPONS)} icons to {out}")

if __name__ == "__main__":
    main()
