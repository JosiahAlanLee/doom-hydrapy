# SPDX-License-Identifier: GPL-2.0-or-later
"""Original low-poly 3D prop and architecture kit for the tower bank.

Z-up, metres.  Documented conversion: 1 m = 64 Doom units.  Every mesh is
exported as UV-mapped OBJ+MTL with a procedural texture beside it.  A JSON
manifest records honest bounds, triangle counts and simple collision proxies.
The contact sheets are software orthographic previews, not engine renders.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import kit_common as K

UNITS_PER_M = 64
TEX_SIZE = 256


# -- mesh builder ------------------------------------------------------------
class MeshBuilder:
    def __init__(self, name):
        self.name = name
        self.verts = []
        self.uvs = []
        self.normals = []
        self.faces = []          # (i0,i1,i2, material)
        self.materials = {}      # name -> {'hex':..., 'patch': (u0,v0,u1,v1), 'style':...}
        self.triangles = 0

    def material(self, name, hex_color, style='metal'):
        idx = len(self.materials)
        x = 0.03 + 0.47 * (idx % 2)
        y = 0.03 + 0.47 * (idx // 2)
        self.materials[name] = {'hex': hex_color, 'patch': (x, y, x + 0.44, y + 0.44),
                                'style': style}
        return name

    def _uv(self, material, u, v):
        u0, v0, u1, v1 = self.materials[material]['patch']
        u = min(0.999, max(0.001, u))
        v = min(0.999, max(0.001, v))
        return (u0 + u * (u1 - u0), v0 + v * (v1 - v0))

    def add_tri(self, a, b, c, uva, uvb, uvc, material, outward=None):
        a = tuple(float(v) for v in a)
        b = tuple(float(v) for v in b)
        c = tuple(float(v) for v in c)
        ab = np.array(b) - np.array(a)
        ac = np.array(c) - np.array(a)
        n = np.cross(ab, ac)
        ln = float(np.linalg.norm(n))
        if ln < 1e-9:
            return False
        n = n / ln
        if outward is not None and float(np.dot(n, np.array(outward, dtype=float))) < 0:
            b, c = c, b
            uvb, uvc = uvc, uvb
            n = -n
        base = len(self.verts)
        for p in (a, b, c):
            self.verts.append(p)
        for uv in (uva, uvb, uvc):
            self.uvs.append(self._uv(material, uv[0], uv[1]))
        for _ in range(3):
            self.normals.append(tuple(float(x) for x in n))
        self.faces.append((base, base + 1, base + 2, material))
        self.triangles += 1
        return True

    def add_quad(self, a, b, c, d, uvs, material, outward=None):
        ok1 = self.add_tri(a, b, c, uvs[0], uvs[1], uvs[2], material, outward)
        ok2 = self.add_tri(a, c, d, uvs[0], uvs[2], uvs[3], material, outward)
        return ok1 or ok2

    def add_box(self, x0, y0, z0, x1, y1, z1, material, uv_scale=1.0):
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        z0, z1 = sorted((z0, z1))
        p = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        u = [(0, 0), (uv_scale, 0), (uv_scale, uv_scale), (0, uv_scale)]
        self.add_quad(p[0], p[3], p[2], p[1], u, material, (0, 0, -1))
        self.add_quad(p[4], p[5], p[6], p[7], u, material, (0, 0, 1))
        self.add_quad(p[0], p[1], p[5], p[4], u, material, (0, -1, 0))
        self.add_quad(p[3], p[7], p[6], p[2], u, material, (0, 1, 0))
        self.add_quad(p[0], p[4], p[7], p[3], u, material, (-1, 0, 0))
        self.add_quad(p[1], p[2], p[6], p[5], u, material, (1, 0, 0))

    def add_beam(self, p0, p1, width, depth, material):
        p0 = np.array(p0, dtype=float)
        p1 = np.array(p1, dtype=float)
        d = p1 - p0
        ln = float(np.linalg.norm(d))
        if ln < 1e-9:
            return
        d /= ln
        up = np.array((0.0, 0.0, 1.0)) if abs(d[2]) < 0.9 else np.array((0.0, 1.0, 0.0))
        side = np.cross(up, d)
        side /= np.linalg.norm(side)
        up2 = np.cross(d, side)
        hw, hd = width / 2.0, depth / 2.0
        corners = []
        for w in (0.0, ln):
            for u, v in ((-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)):
                corners.append(tuple(p0 + side * u + up2 * v + d * w))
        # local box order, mapped to (side, up2, axis)
        p = corners
        u = [(0, 0), (1, 0), (1, 1), (0, 1)]
        self.add_quad(p[0], p[3], p[2], p[1], u, material, tuple(-d))
        self.add_quad(p[4], p[5], p[6], p[7], u, material, tuple(d))
        self.add_quad(p[0], p[1], p[5], p[4], u, material, tuple(-up2))
        self.add_quad(p[3], p[7], p[6], p[2], u, material, tuple(up2))
        self.add_quad(p[0], p[4], p[7], p[3], u, material, tuple(-side))
        self.add_quad(p[1], p[2], p[6], p[5], u, material, tuple(side))

    def add_cylinder(self, cx, cy, z0, z1, r0, r1, seg, material, caps=True):
        z0, z1 = sorted((z0, z1))
        rings = []
        for z, r in ((z0, r0), (z1, r1)):
            ring = []
            for i in range(seg):
                a = math.tau * i / seg
                ring.append((cx + math.cos(a) * r, cy + math.sin(a) * r, z))
            rings.append(ring)
        for i in range(seg):
            j = (i + 1) % seg
            u0, u1 = i / seg, (i + 1) / seg
            mid = math.tau * (i + 0.5) / seg
            out = (math.cos(mid), math.sin(mid), 0)
            self.add_quad(rings[0][i], rings[0][j], rings[1][j], rings[1][i],
                          [(u0, 0), (u1, 0), (u1, 1), (u0, 1)], material, out)
        if caps:
            if r0 > 1e-9:
                for i in range(seg):
                    j = (i + 1) % seg
                    self.add_tri((cx, cy, z0), rings[0][j], rings[0][i],
                                 (0.5, 0.5), (j / seg, 0), (i / seg, 0), material, (0, 0, -1))
            if r1 > 1e-9:
                for i in range(seg):
                    j = (i + 1) % seg
                    self.add_tri((cx, cy, z1), rings[1][i], rings[1][j],
                                 (0.5, 0.5), (i / seg, 1), (j / seg, 1), material, (0, 0, 1))

    def add_lathe(self, cx, cy, z0, profile, seg, material, cap_bottom=True, cap_top=False):
        """profile: list of (radius, dz) from bottom to top; z0 is the bottom."""
        rings = []
        for r, dz in profile:
            ring = []
            for i in range(seg):
                a = math.tau * i / seg
                ring.append((cx + math.cos(a) * r, cy + math.sin(a) * r, z0 + dz))
            rings.append(ring)
        for k in range(len(rings) - 1):
            for i in range(seg):
                j = (i + 1) % seg
                u0, u1 = i / seg, (i + 1) / seg
                v0, v1 = k / max(1, len(rings) - 1), (k + 1) / max(1, len(rings) - 1)
                mid = math.tau * (i + 0.5) / seg
                out = (math.cos(mid), math.sin(mid), 0)
                r0, r1 = profile[k][0], profile[k + 1][0]
                if r0 < 1e-9 and r1 < 1e-9:
                    continue
                if r0 < 1e-9:
                    self.add_tri((cx, cy, z0 + profile[k][1]), rings[k + 1][j], rings[k + 1][i],
                                 (0.5, v0), (u1, v1), (u0, v1), material, out)
                elif r1 < 1e-9:
                    self.add_tri(rings[k][i], rings[k][j], (cx, cy, z0 + profile[k + 1][1]),
                                 (u0, v0), (u1, v0), (0.5, v1), material, out)
                else:
                    self.add_quad(rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i],
                                  [(u0, v0), (u1, v0), (u1, v1), (u0, v1)], material, out)
        if cap_bottom and profile[0][0] > 1e-9:
            for i in range(seg):
                j = (i + 1) % seg
                self.add_tri((cx, cy, z0), rings[0][j], rings[0][i],
                             (0.5, 0.5), (j / seg, 0), (i / seg, 0), material, (0, 0, -1))
        if cap_top and profile[-1][0] > 1e-9:
            for i in range(seg):
                j = (i + 1) % seg
                self.add_tri((cx, cy, z0 + profile[-1][1]), rings[-1][i], rings[-1][j],
                             (0.5, 0.5), (i / seg, 1), (j / seg, 1), material, (0, 0, 1))

    def add_torus(self, cx, cy, cz, major, minor, seg_major, seg_minor, material, axis='y'):
        """Torus in the XZ plane (axis y) or YZ plane (axis x), useful for chain links."""
        rings = []
        for i in range(seg_major):
            a = math.tau * i / seg_major
            if axis == 'y':
                centre = np.array((cx + math.cos(a) * major, cy, cz + math.sin(a) * major))
                radial = np.array((math.cos(a), 0.0, math.sin(a)))
                axial = np.array((0.0, 1.0, 0.0))
            else:
                centre = np.array((cx, cy + math.cos(a) * major, cz + math.sin(a) * major))
                radial = np.array((0.0, math.cos(a), math.sin(a)))
                axial = np.array((1.0, 0.0, 0.0))
            ring = []
            for j in range(seg_minor):
                b = math.tau * j / seg_minor
                p = centre + radial * (math.cos(b) * minor) + axial * (math.sin(b) * minor)
                ring.append(tuple(p))
            rings.append(ring)
        for i in range(seg_major):
            j = (i + 1) % seg_major
            for k in range(seg_minor):
                l = (k + 1) % seg_minor
                a = rings[i][k]
                b = rings[i][l]
                c = rings[j][l]
                d = rings[j][k]
                mid = (np.array(a) + np.array(c)) / 2.0
                if axis == 'y':
                    centre = np.array((cx + math.cos(math.tau * (i + 0.5) / seg_major) * major, cy,
                                       cz + math.sin(math.tau * (i + 0.5) / seg_major) * major))
                else:
                    centre = np.array((cx, cy + math.cos(math.tau * (i + 0.5) / seg_major) * major,
                                       cz + math.sin(math.tau * (i + 0.5) / seg_major) * major))
                out = mid - centre
                self.add_quad(a, b, c, d, [(i / seg_major, k / seg_minor),
                                           (i / seg_major, (k + 1) / seg_minor),
                                           ((i + 1) / seg_major, (k + 1) / seg_minor),
                                           ((i + 1) / seg_major, k / seg_minor)],
                              material, tuple(out))

    def bounds(self):
        arr = np.array(self.verts, dtype=float)
        lo = arr.min(axis=0)
        hi = arr.max(axis=0)
        return [round(float(v), 6) for v in lo], [round(float(v), 6) for v in hi]

    def write_obj(self, folder, texture_name):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        obj = folder / f'{self.name}.obj'
        mtl = folder / f'{self.name}.mtl'
        lines = [f'# {self.name}: original Null Run tower kit; Z-up, metres',
                 f'# triangle count {self.triangles}; 1 m = {UNITS_PER_M} Doom units',
                 f'mtllib {self.name}.mtl', f'o {self.name}']
        for v in self.verts:
            lines.append(f'v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}')
        for uv in self.uvs:
            lines.append(f'vt {uv[0]:.6f} {uv[1]:.6f}')
        for n in self.normals:
            lines.append(f'vn {n[0]:.6f} {n[1]:.6f} {n[2]:.6f}')
        for mat in self.materials:
            lines.append(f'usemtl {mat}')
            for i0, i1, i2, m in self.faces:
                if m != mat:
                    continue
                a, b, c = i0 + 1, i1 + 1, i2 + 1
                lines.append(f'f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}')
        obj.write_text('\n'.join(lines) + '\n')
        mlines = ['# original Null Run tower kit materials', f'# texture {texture_name}']
        for name, info in self.materials.items():
            col = K.hx(info['hex'])
            kd = tuple(c / 255.0 for c in col)
            mlines.extend([f'newmtl {name}', 'Ka 0.08 0.08 0.08',
                           f'Kd {kd[0]:.4f} {kd[1]:.4f} {kd[2]:.4f}',
                           'Ks 0.18 0.18 0.18', 'Ns 24.0', 'd 1.0', 'illum 2',
                           f'map_Kd {texture_name}', ''])
        mtl.write_text('\n'.join(mlines))
        return obj, mtl

    def uv_ranges(self):
        arr = np.array(self.uvs, dtype=float)
        return ([round(float(v), 6) for v in arr.min(axis=0)],
                [round(float(v), 6) for v in arr.max(axis=0)])


# -- procedural textures -----------------------------------------------------
def build_texture(mb, seed):
    img = Image.new('RGB', (TEX_SIZE, TEX_SIZE), (46, 46, 48))
    arr = np.array(img, dtype=np.float64)
    rng = np.random.default_rng(seed)
    for name, info in mb.materials.items():
        u0, v0, u1, v1 = info['patch']
        # Standard OBJ/image convention: V=0 is the bottom of the image.
        x0, x1 = int(u0 * TEX_SIZE), int(u1 * TEX_SIZE)
        y0, y1 = int((1.0 - v1) * TEX_SIZE), int((1.0 - v0) * TEX_SIZE)
        h, w = y1 - y0, x1 - x0
        base = np.array(K.hx(info['hex']), dtype=np.float64)
        yy, xx = np.mgrid[0:h, 0:w]
        field = (np.sin(xx / 9.0 + yy / 17.0) * 0.5 + np.sin(xx / 4.0 - yy / 7.0) * 0.25
                 + rng.normal(0, 0.35, (h, w)))
        style = info['style']
        if style == 'metal':
            field += (xx % 9 < 3) * 0.5
        elif style == 'brick':
            field += ((yy // 12) % 2) * 0.35 + ((xx + (yy // 12) * 10) % 24 < 2) * -0.8
        elif style == 'cloth':
            field = np.sin(xx / 4.0) * 0.55 + np.sin(yy / 6.0) * 0.25 + rng.normal(0, 0.2, (h, w))
        elif style == 'glow':
            field = 1.2 - (((xx - w / 2) ** 2 + (yy - h / 2) ** 2) ** 0.5) / (w * 0.8)
        elif style == 'glass':
            field = np.sin(xx / 13.0) * 0.4 + np.sin(yy / 23.0) * 0.3
        sub = base[None, None, :] * (0.82 + 0.20 * field[:, :, None])
        arr[y0:y1, x0:x1, :] = np.clip(sub, 0, 255)
        # patch border
        arr[y0:y0 + 1, x0:x1, :] = 22
        arr[y1 - 1:y1, x0:x1, :] = 22
        arr[y0:y1, x0:x0 + 1, :] = 22
        arr[y0:y1, x1 - 1:x1, :] = 22
    return Image.fromarray(arr.astype(np.uint8), 'RGB')


# -- prop constructors -------------------------------------------------------
def mat_set(mb, colors, styles=None):
    styles = styles or ['metal'] * len(colors)
    names = []
    for i, (key, hexv) in enumerate(colors):
        names.append(mb.material(key, hexv, styles[i]))
    return names


def _bell_profile(height, rmax):
    # (radius, dz) from the flared lip to the crown; the waist is deliberately narrow
    return [
        (rmax * 0.92, 0.00), (rmax * 1.00, 0.035 * height),
        (rmax * 0.97, 0.09 * height), (rmax * 0.76, 0.16 * height),
        (rmax * 0.60, 0.28 * height), (rmax * 0.52, 0.42 * height),
        (rmax * 0.57, 0.56 * height), (rmax * 0.66, 0.70 * height),
        (rmax * 0.72, 0.82 * height), (rmax * 0.64, 0.90 * height),
        (rmax * 0.46, 0.96 * height), (rmax * 0.22, 1.00 * height),
        (rmax * 0.10, 1.01 * height),
    ]


def build_suspended_bell(seed):
    sid = 'ashbell_foundry'
    mb = MeshBuilder('ashbell_suspended_ninth_bell')
    bronze, verd, iron, glow = mat_set(mb, [
        ('bronze', K.PALETTES[sid]['bronze']), ('patina', K.PALETTES[sid]['verdigris']),
        ('iron', K.PALETTES[sid]['iron_light']), ('ember', K.PALETTES[sid]['furnace'])],
        ['metal', 'brick', 'metal', 'glow'])
    # bell hanging at 1.55 m, crown 2.95 m
    mb.add_lathe(0, 0, 1.55, _bell_profile(1.40, 0.62), 20, bronze, cap_bottom=True)
    # lip ring
    for i in range(20):
        a = math.tau * i / 20
        mb.add_beam((math.cos(a) * 0.58, math.sin(a) * 0.58, 1.57),
                    (math.cos(a) * 0.64, math.sin(a) * 0.64, 1.60), 0.035, 0.035, verd)
    # crown loop and chain
    mb.add_torus(0, 0, 3.06, 0.13, 0.035, 14, 6, iron, axis='x')
    for i in range(5):
        z = 3.16 + i * 0.17
        mb.add_torus(0, 0, z, 0.075, 0.022, 10, 5, iron, axis='y' if i % 2 else 'x')
    mb.add_beam((0, 0, 3.10), (0, 0, 3.95), 0.07, 0.07, iron)
    # clapper and inner mouth
    mb.add_cylinder(0, 0, 1.58, 2.10, 0.055, 0.09, 10, iron)
    mb.add_lathe(0, 0, 1.56, [(0.30, 0.0), (0.42, 0.05), (0.30, 0.10)], 14, glow, cap_top=False)
    # a small counterweight chain beside the bell
    for i in range(3):
        mb.add_torus(0.82, 0, 2.3 - i * 0.20, 0.06, 0.018, 9, 5, iron, axis='x')
    mb.add_box(0.76, -0.08, 1.55, 0.90, 0.08, 1.73, iron)
    return mb


def build_lift_cage(seed):
    sid = 'ashbell_foundry'
    mb = MeshBuilder('ashbell_chain_lift_cage')
    iron, bronze, rail, glow = mat_set(mb, [
        ('iron', K.PALETTES[sid]['iron']), ('bronze', K.PALETTES[sid]['bronze']),
        ('verdigris', K.PALETTES[sid]['verdigris']), ('lamp', K.PALETTES[sid]['furnace'])],
        ['metal', 'metal', 'brick', 'glow'])
    # cage floor and roof
    mb.add_box(-0.8, -0.8, 0.02, 0.8, 0.8, 0.10, rail)
    mb.add_box(-0.8, -0.8, 2.10, 0.8, 0.8, 2.18, rail)
    # corner posts and bars
    for x in (-0.8, 0.8):
        for y in (-0.8, 0.8):
            mb.add_box(x - 0.04, y - 0.04, 0.10, x + 0.04, y + 0.04, 2.10, iron)
    for i in range(1, 6):
        x = -0.8 + i * 1.6 / 6
        for y in (-0.8, 0.8):
            mb.add_box(x - 0.02, y - 0.02, 0.10, x + 0.02, y + 0.02, 2.10, bronze)
    for i in range(1, 6):
        y = -0.8 + i * 1.6 / 6
        for x in (-0.8, 0.8):
            mb.add_box(x - 0.02, y - 0.02, 0.10, x + 0.02, y + 0.02, 2.10, bronze)
    # diagonal braces on the open back
    mb.add_beam((-0.78, 0.8, 0.12), (0.78, 0.8, 2.08), 0.035, 0.035, bronze)
    mb.add_beam((0.78, 0.8, 0.12), (-0.78, 0.8, 2.08), 0.035, 0.035, bronze)
    # roof lamp
    mb.add_box(-0.12, -0.12, 2.02, 0.12, 0.12, 2.10, glow)
    # overhead chain and guide rails
    for x in (-0.68, 0.68):
        mb.add_box(x - 0.04, -0.04, 0.0, x + 0.04, 0.04, 4.0, iron)
    for i in range(7):
        z = 2.25 + i * 0.24
        mb.add_torus(0, 0, z, 0.09, 0.025, 10, 5, iron, axis='y' if i % 2 else 'x')
    # counterweight
    mb.add_box(0.92, -0.16, 0.8, 1.12, 0.16, 1.7, iron)
    mb.add_beam((0.68, 0, 3.8), (1.02, 0, 1.7), 0.04, 0.04, iron)
    return mb


def build_furnace(seed):
    sid = 'ashbell_foundry'
    mb = MeshBuilder('ashbell_casting_furnace')
    soot, brick, bronze, glow = mat_set(mb, [
        ('soot', K.PALETTES[sid]['soot']), ('brick', K.PALETTES[sid]['firebrick']),
        ('bronze', K.PALETTES[sid]['bronze']), ('glow', K.PALETTES[sid]['furnace'])],
        ['metal', 'brick', 'metal', 'glow'])
    # body and chimney
    mb.add_box(-1.1, -0.6, 0.0, 1.1, 0.6, 2.35, soot)
    mb.add_box(-0.4, -0.35, 2.35, 0.4, 0.35, 3.55, soot)
    mb.add_box(-0.52, -0.42, 3.55, 0.52, 0.42, 3.7, bronze)
    mb.add_box(-1.2, -0.7, 0.0, 1.2, 0.7, 0.18, brick)
    # arched mouth made from jambs and radial blocks
    mb.add_box(-0.62, -0.62, 0.3, -0.46, -0.52, 1.55, bronze)
    mb.add_box(0.46, -0.62, 0.3, 0.62, -0.52, 1.55, bronze)
    for i in range(9):
        a = math.pi * (i + 0.5) / 9
        x = math.cos(a) * 0.54
        z = 1.55 + math.sin(a) * 0.54
        mb.add_beam((x - 0.06, -0.58, z - 0.03), (x + 0.06, -0.58, z + 0.03),
                    0.10, 0.10, bronze)
    # recessed glowing mouth
    mb.add_box(-0.46, -0.64, 0.3, 0.46, -0.56, 1.55, glow)
    for i in range(4):
        mb.add_box(-0.38, -0.67, 0.45 + i * 0.25, 0.38, -0.635, 0.52 + i * 0.25, soot)
    # ladle spout and crucible lip
    mb.add_beam((0.72, 0, 1.85), (1.45, 0, 1.55), 0.16, 0.16, soot)
    mb.add_lathe(1.48, 0, 1.46, [(0.18, 0.0), (0.28, 0.08), (0.18, 0.18)], 12, bronze, cap_top=False)
    mb.add_lathe(1.48, 0, 1.53, [(0.10, 0.0), (0.18, 0.03), (0.10, 0.06)], 10, glow)
    # rivets and side tools
    for x in (-0.95, -0.65, 0.65, 0.95):
        for z in (0.4, 1.0, 1.8):
            mb.add_cylinder(x, -0.63, z, z + 0.05, 0.045, 0.045, 8, bronze)
    return mb


def build_root_cage(seed):
    sid = 'boneglass_conservatory'
    mb = MeshBuilder('boneglass_root_cage_planter')
    root, bone, peat, glow = mat_set(mb, [
        ('root', K.PALETTES[sid]['root']), ('bone', K.PALETTES[sid]['bone']),
        ('peat', K.PALETTES[sid]['peat']), ('glow', K.PALETTES[sid]['glow'])],
        ['brick', 'metal', 'metal', 'glow'])
    # planter and trunk
    mb.add_lathe(0, 0, 0.0, [(0.55, 0.0), (0.62, 0.10), (0.58, 0.55)], 16, root, cap_top=True)
    mb.add_cylinder(0, 0, 0.55, 1.3, 0.17, 0.13, 12, bone)
    # root cage: vertical curved ribs and woven rings
    for i in range(8):
        a = math.tau * i / 8
        pts = []
        for k in range(6):
            t = k / 5
            r = 0.55 + 0.25 * math.sin(math.pi * t) - 0.12 * t
            z = 1.0 + t * 1.9
            pts.append((math.cos(a) * r, math.sin(a) * r, z))
        for p0, p1 in zip(pts, pts[1:]):
            mb.add_beam(p0, p1, 0.055, 0.055, root)
    for k in range(5):
        z = 1.10 + k * 0.42
        r = 0.58 + 0.22 * math.sin(math.pi * (z - 1.0) / 1.9)
        for i in range(16):
            a = math.tau * i / 16
            b = math.tau * (i + 1) / 16
            mb.add_beam((math.cos(a) * r, math.sin(a) * r, z),
                        (math.cos(b) * r, math.sin(b) * r, z), 0.045, 0.045, root)
    # hanging cords and a pale growth inside
    for i in range(5):
        a = math.tau * i / 5
        mb.add_beam((math.cos(a) * 0.5, math.sin(a) * 0.5, 2.9),
                    (math.cos(a) * 0.62, math.sin(a) * 0.62, 3.45), 0.035, 0.035, root)
    mb.add_cylinder(0, 0, 1.25, 1.75, 0.07, 0.11, 8, glow)
    # dark peat mound at the base
    mb.add_lathe(0, 0, 0.0, [(0.62, 0.0), (0.48, 0.12), (0.25, 0.20)], 14, peat)
    return mb


def build_watering_gantry(seed):
    sid = 'boneglass_conservatory'
    mb = MeshBuilder('boneglass_watering_gantry')
    verd, bone, brass, glow = mat_set(mb, [
        ('verdigris', K.PALETTES[sid]['wet']), ('bone', K.PALETTES[sid]['bone']),
        ('brass', K.PALETTES[sid]['root_light']), ('water', K.PALETTES[sid]['glow'])],
        ['metal', 'brick', 'metal', 'glow'])
    # arch posts and top beam
    for x in (-1.3, 1.3):
        mb.add_box(x - 0.07, -0.07, 0.0, x + 0.07, 0.07, 2.4, verd)
        mb.add_box(x - 0.22, -0.22, 0.0, x + 0.22, 0.22, 0.12, brass)
    mb.add_box(-1.4, -0.09, 2.35, 1.4, 0.09, 2.52, verd)
    mb.add_box(-1.45, -0.12, 2.52, 1.45, 0.12, 2.58, brass)
    # cross pipe and nozzles
    mb.add_cylinder(0, 0, 2.05, 2.30, 0.06, 0.06, 10, verd)
    for x in (-0.85, 0.0, 0.85):
        mb.add_cylinder(x, 0, 1.85, 2.08, 0.045, 0.045, 8, verd)
        mb.add_lathe(x, 0, 1.72, [(0.13, 0.0), (0.17, 0.08), (0.12, 0.14)], 10, brass, cap_top=False)
        for k in range(4):
            a = math.tau * k / 4
            mb.add_beam((x + math.cos(a) * 0.04, math.sin(a) * 0.04, 1.70),
                        (x + math.cos(a) * 0.08, math.sin(a) * 0.08, 1.62), 0.02, 0.02, glow)
    # tap wheel and pressure bulb at one post
    mb.add_torus(-1.3, 0.16, 1.05, 0.18, 0.025, 12, 5, brass, axis='y')
    mb.add_cylinder(-1.3, 0.16, 1.0, 1.10, 0.035, 0.035, 8, brass)
    mb.add_lathe(1.3, 0.15, 1.55, [(0.08, 0.0), (0.12, 0.08), (0.08, 0.16)], 10, bone)
    # hanging hose loop
    for k in range(8):
        a = math.pi * k / 7
        x = -0.55 + math.cos(a) * 0.35
        z = 1.9 - math.sin(a) * 0.9
        if k < 7:
            a2 = math.pi * (k + 1) / 7
            x2 = -0.55 + math.cos(a2) * 0.35
            z2 = 1.9 - math.sin(a2) * 0.9
            mb.add_beam((x, 0.18, z), (x2, 0.18, z2), 0.045, 0.045, verd)
    return mb


def build_growth_chamber(seed):
    sid = 'boneglass_conservatory'
    mb = MeshBuilder('boneglass_growth_chamber')
    bone, peat, verd, glow = mat_set(mb, [
        ('bone', K.PALETTES[sid]['bone']), ('peat', K.PALETTES[sid]['peat']),
        ('verdigris', K.PALETTES[sid]['wet']), ('glow', K.PALETTES[sid]['glow'])],
        ['brick', 'metal', 'metal', 'glow'])
    # cabinet shell
    mb.add_box(-0.7, -0.4, 0.0, 0.7, 0.4, 2.15, bone)
    mb.add_box(-0.62, -0.44, 0.12, 0.62, 0.30, 2.03, peat)
    # glass front and frame
    mb.add_box(-0.62, -0.48, 0.12, 0.62, -0.44, 2.03, verd)
    for x in (-0.62, 0.0, 0.62):
        mb.add_box(x - 0.03, -0.50, 0.10, x + 0.03, -0.42, 2.05, bone)
    for z in (0.10, 1.05, 2.03):
        mb.add_box(-0.64, -0.50, z - 0.03, 0.64, -0.42, z + 0.03, bone)
    # soil bed and pale sprouts
    mb.add_box(-0.52, -0.32, 0.62, 0.52, 0.22, 0.78, peat)
    for x, z in ((-0.30, 1.15), (0.0, 1.42), (0.30, 1.28)):
        mb.add_cylinder(x, -0.05, 0.78, z, 0.025, 0.02, 6, bone)
        mb.add_lathe(x, -0.05, z, [(0.03, 0.0), (0.11, 0.08), (0.05, 0.18)], 8, glow)
    # latch and top vent
    mb.add_box(0.52, -0.53, 1.02, 0.62, -0.46, 1.20, verd)
    mb.add_box(-0.2, -0.25, 2.15, 0.2, 0.25, 2.30, verd)
    return mb


def build_service_lift(seed):
    sid = 'skyhotel_service_well'
    mb = MeshBuilder('skyhotel_service_lift_car')
    maroon, brass, night, amber = mat_set(mb, [
        ('maroon', K.PALETTES[sid]['maroon']), ('brass', K.PALETTES[sid]['brass']),
        ('night', K.PALETTES[sid]['night']), ('amber', K.PALETTES[sid]['amber'])],
        ['cloth', 'metal', 'metal', 'glow'])
    # car shell, floor and roof
    mb.add_box(-1.0, -1.0, 0.0, 1.0, 1.0, 0.12, brass)
    mb.add_box(-1.0, -1.0, 2.28, 1.0, 1.0, 2.42, brass)
    mb.add_box(-1.0, -1.0, 0.12, 1.0, -0.94, 2.28, maroon)
    mb.add_box(-1.0, 0.94, 0.12, 1.0, 1.0, 2.28, maroon)
    mb.add_box(-1.0, -0.94, 0.12, -0.94, 0.94, 2.28, maroon)
    # open front, one door panel ajar
    mb.add_box(0.62, -0.94, 0.12, 0.94, -0.86, 2.28, brass)
    mb.add_box(0.62, -0.86, 0.12, 0.86, -0.82, 2.28, amber)
    # interior amber light and ceiling panel
    mb.add_box(-0.12, -0.12, 2.20, 0.12, 0.12, 2.28, amber)
    # indicator panel above the door
    mb.add_box(-0.32, -0.97, 2.42, 0.32, -0.90, 2.62, night)
    for i in range(3):
        mb.add_box(-0.22 + i * 0.15, -0.99, 2.47, -0.18 + i * 0.15, -0.96, 2.57, amber)
    # call plate
    mb.add_box(0.72, -0.98, 1.10, 0.86, -0.92, 1.45, night)
    mb.add_cylinder(0.79, -0.99, 1.20, 1.24, 0.025, 0.025, 8, amber)
    return mb


def build_dumbwaiter(seed):
    sid = 'skyhotel_service_well'
    mb = MeshBuilder('skyhotel_dumbwaiter_winch_head')
    iron, brass, maroon, amber = mat_set(mb, [
        ('iron', K.PALETTES[sid]['blue']), ('brass', K.PALETTES[sid]['brass']),
        ('maroon', K.PALETTES[sid]['maroon']), ('amber', K.PALETTES[sid]['amber'])],
        ['metal', 'metal', 'cloth', 'glow'])
    # low body and rails
    mb.add_box(-0.7, -0.32, 0.0, 0.7, 0.32, 1.15, iron)
    mb.add_box(-0.75, -0.36, 1.15, 0.75, 0.36, 1.24, brass)
    for x in (-0.62, 0.62):
        mb.add_box(x - 0.035, 0.32, 0.0, x + 0.035, 0.40, 2.25, brass)
    # big spoked wheel in the XZ plane
    mb.add_torus(0, 0.28, 1.02, 0.34, 0.045, 18, 6, brass, axis='y')
    for k in range(6):
        a = math.tau * k / 6
        mb.add_beam((0, 0.28, 1.02),
                    (math.cos(a) * 0.30, 0.28, 1.02 + math.sin(a) * 0.30),
                    0.035, 0.035, brass)
    mb.add_cylinder(0, 0.28, 0.98, 1.06, 0.07, 0.07, 10, iron)
    # cable spool
    mb.add_cylinder(0.52, 0.02, 0.8, 1.1, 0.15, 0.15, 12, brass)
    # hanging suitcase
    mb.add_beam((0.54, 0.30, 1.15), (0.54, 0.30, 1.55), 0.03, 0.03, brass)
    mb.add_beam((0.40, 0.30, 1.55), (0.68, 0.30, 1.55), 0.035, 0.035, brass)
    mb.add_box(0.38, 0.16, 1.20, 0.70, 0.48, 1.58, maroon)
    mb.add_box(0.46, 0.12, 1.56, 0.62, 0.16, 1.60, brass)
    # call plate on the side
    mb.add_box(-0.72, 0.32, 1.30, -0.50, 0.38, 1.70, brass)
    for k in range(3):
        mb.add_cylinder(-0.61, 0.39, 1.38 + k * 0.10, 1.42 + k * 0.10, 0.025, 0.025, 8, amber)
    return mb


def build_balcony_bay(seed):
    sid = 'skyhotel_service_well'
    mb = MeshBuilder('skyhotel_balcony_bay')
    iron, brass, maroon, amber = mat_set(mb, [
        ('concrete', K.PALETTES[sid]['blue']), ('brass', K.PALETTES[sid]['brass']),
        ('maroon', K.PALETTES[sid]['maroon']), ('amber', K.PALETTES[sid]['amber'])],
        ['metal', 'metal', 'cloth', 'glow'])
    # floor slab and back wall
    mb.add_box(-1.5, -0.6, 0.0, 1.5, 0.6, 0.16, iron)
    mb.add_box(-1.5, 0.42, 0.16, 1.5, 0.6, 3.0, iron)
    mb.add_box(-1.5, -0.6, 2.9, 1.5, 0.6, 3.0, brass)
    # side walls / room reveal
    for x in (-1.5, 1.44):
        mb.add_box(x, -0.6, 0.16, x + 0.06, 0.42, 2.9, iron)
    # guardrail: posts and rails along the front edge
    for x in (-1.45, -0.72, 0.0, 0.72, 1.45):
        mb.add_box(x - 0.035, -0.60, 0.16, x + 0.035, -0.54, 1.25, brass)
    for z in (0.68, 1.22):
        mb.add_box(-1.48, -0.62, z - 0.035, 1.48, -0.56, z + 0.035, brass)
    # recessed door / window
    mb.add_box(-0.62, 0.36, 0.30, 0.62, 0.44, 2.55, maroon)
    mb.add_box(-0.54, 0.30, 0.42, 0.54, 0.38, 2.42, amber)
    for x in (-0.62, 0.0, 0.62):
        mb.add_box(x - 0.03, 0.29, 0.30, x + 0.03, 0.38, 2.55, brass)
    # number plaque and rain hood
    mb.add_box(-0.20, 0.27, 2.52, 0.20, 0.34, 2.72, brass)
    mb.add_box(-0.16, 0.26, 2.56, -0.02, 0.29, 2.66, amber)
    mb.add_box(0.02, 0.26, 2.56, 0.16, 0.29, 2.66, amber)
    mb.add_box(-0.82, 0.20, 2.55, 0.82, 0.30, 2.62, brass)
    return mb


def build_shared_stair(seed):
    mb = MeshBuilder('shared_stair_flight')
    stone, steel, paint = mat_set(mb, [
        ('stone', '#8E8B84'), ('steel', '#4A4D52'), ('paint', '#C9B26A')],
        ['brick', 'metal', 'metal'])
    steps = 8
    riser = 0.1875
    tread = 0.28
    width = 1.6
    for i in range(steps):
        z0 = i * riser
        z1 = (i + 1) * riser
        y0 = i * tread
        y1 = (i + 1) * tread
        mb.add_box(-width / 2, y0, 0.0, width / 2, y1, z1, stone)
        mb.add_box(-width / 2, y0, z1 - 0.012, width / 2, y1 - 0.02, z1, paint)
    # side stringers, kept inside the stair volume (no below-floor overhang)
    for x in (-width / 2 - 0.05, width / 2 + 0.05):
        mb.add_beam((x, 0.02, 0.10), (x, steps * tread, steps * riser - 0.08),
                    0.09, 0.09, steel)
    # a small landing lip at the top
    mb.add_box(-width / 2, steps * tread, steps * riser - 0.12,
               width / 2, steps * tread + 0.20, steps * riser, steel)
    return mb


def build_shared_landing(seed):
    mb = MeshBuilder('shared_stair_landing')
    steel, stone, paint = mat_set(mb, [
        ('steel', '#4A4D52'), ('stone', '#8E8B84'), ('paint', '#C9B26A')],
        ['metal', 'brick', 'metal'])
    size = 1.8
    top = 1.5
    mb.add_box(-size / 2, -size / 2, top - 0.14, size / 2, size / 2, top, steel)
    mb.add_box(-size / 2 + 0.06, -size / 2 + 0.06, top, size / 2 - 0.06, size / 2 - 0.06, top + 0.01, paint)
    for x in (-size / 2 + 0.12, size / 2 - 0.12):
        for y in (-size / 2 + 0.12, size / 2 - 0.12):
            mb.add_box(x - 0.055, y - 0.055, 0.0, x + 0.055, y + 0.055, top - 0.14, steel)
    # edge curb
    for x0, y0, x1, y1 in ((-size/2, -size/2, size/2, -size/2+0.06),
                           (-size/2, size/2-0.06, size/2, size/2)):
        mb.add_box(x0, y0, top, x1, y1, top + 0.05, paint)
    return mb


def build_shared_guardrail(seed):
    mb = MeshBuilder('shared_guardrail')
    steel, paint = mat_set(mb, [('steel', '#4A4D52'), ('paint', '#C9B26A')],
                           ['metal', 'metal'])
    length = 2.0
    # posts
    for x in (0.05, length / 2, length - 0.05):
        mb.add_box(x - 0.035, -0.04, 0.0, x + 0.035, 0.04, 1.1, steel)
        mb.add_box(x - 0.10, -0.10, 0.0, x + 0.10, 0.10, 0.05, steel)
    # top and mid rails
    mb.add_box(0.0, -0.035, 1.05, length, 0.035, 1.12, paint)
    mb.add_box(0.0, -0.025, 0.58, length, 0.025, 0.64, steel)
    # a lower kick plate
    mb.add_box(0.0, -0.02, 0.15, length, 0.02, 0.22, steel)
    return mb


BUILDERS = {
    'ashbell_foundry': {
        'suspended_ninth_bell': build_suspended_bell,
        'chain_lift_cage': build_lift_cage,
        'casting_furnace': build_furnace,
    },
    'boneglass_conservatory': {
        'root_cage_planter': build_root_cage,
        'watering_gantry': build_watering_gantry,
        'growth_chamber': build_growth_chamber,
    },
    'skyhotel_service_well': {
        'service_lift_car': build_service_lift,
        'dumbwaiter_winch_head': build_dumbwaiter,
        'balcony_bay': build_balcony_bay,
    },
}
SHARED = {
    'stair_flight': build_shared_stair,
    'stair_landing': build_shared_landing,
    'guardrail': build_shared_guardrail,
}


# -- metadata ----------------------------------------------------------------
PROP_META = {
    'ashbell_foundry': {
        'suspended_ninth_bell': {
            'name': 'Suspended Ninth Bell',
            'role': 'landmark / vertical void',
            'description': ('A cracked cast bell hanging on an eight-link chain with a '
                            'side counterweight and a glowing clapper. The player can '
                            'walk beneath it and read its profile from above and below.'),
            'collision': {
                'proxy_type': 'overhead_cylinder', 'footprint_m': [1.55, 1.40],
                'z_range_m': [1.55, 3.95], 'solid': True, 'ground_clearance_m': 1.55,
                'walkable_surfaces': [],
                'notes': ('No ground blocker: the bell, clapper and chain are overhead. '
                          '1.53 m = 98 Doom units, just above the native 96-unit headroom floor.'),
            },
        },
        'chain_lift_cage': {
            'name': 'Chain Lift Cage',
            'role': 'lift landmark / open shaft',
            'description': ('A barred service cage with a roof lamp, guide rails, overhead '
                            'chain and a counterweight. The mesh is static: it proposes a '
                            'vertical landmark and collision shell, not a moving lift.'),
            'collision': {
                'proxy_type': 'box_shell', 'footprint_m': [2.24, 1.68],
                'z_range_m': [0.0, 4.00], 'solid': True,
                'walkable_surfaces': [{'z_m': 0.10, 'area_m': [1.52, 1.52],
                                       'note': 'cage floor; use only if Codex adds lift motion'}],
                'notes': ('Barred shell; no doorway is cut in this pass. The dark +Y face '
                          'is the least obstructed side and is the intended doorway location. '
                          'Do not treat this mesh as a working lift.'),
            },
        },
        'casting_furnace': {
            'name': 'Casting Furnace Chest',
            'role': 'solid industrial prop',
            'description': ('A black furnace with a firebrick plinth, arched glowing mouth, '
                            'chimney and a ladle spout. A solid mass with a readable chimney '
                            'silhouette from above.'),
            'collision': {
                'proxy_type': 'box', 'footprint_m': [2.96, 1.40],
                'z_range_m': [0.0, 3.70], 'solid': True,
                'walkable_surfaces': [],
                'notes': 'Solid blocker. The mouth is a recessed texture panel, not a passage.',
            },
        },
    },
    'boneglass_conservatory': {
        'root_cage_planter': {
            'name': 'Root Cage Planter',
            'role': 'landmark / hanging cage',
            'description': ('A root-woven teardrop cage around a black void, hung from five '
                            'cords above a peat planter with one pale growth inside. Readable '
                            'as an open cage from above and as a hanging pod from below.'),
            'collision': {
                'proxy_type': 'mixed', 'footprint_m': [1.65, 1.65],
                'z_range_m': [0.0, 3.46], 'solid': True,
                'walkable_surfaces': [],
                'notes': ('The planter is a 1.1 m solid base; the cage is overhead from '
                          '1.0 m to 2.9 m with an empty centre. Do not use the cage as a '
                          'passage or a lift.'),
            },
        },
        'watering_gantry': {
            'name': 'Watering Gantry',
            'role': 'arch / overhead route',
            'description': ('A verdigris pipe arch with three watering roses, a tap wheel, '
                            'a pressure bulb and a hanging hose loop. The clear opening is '
                            '2.0 m wide and 2.0 m high.'),
            'collision': {
                'proxy_type': 'posts_plus_beam', 'footprint_m': [3.04, 0.49],
                'z_range_m': [0.0, 2.58], 'solid': True,
                'walkable_surfaces': [{'z_m': 0.0, 'area_m': [2.0, 0.4],
                                       'note': 'walk through under the beam; overhead clearance 2.03 m'}],
                'notes': ('Only the two 0.44 m posts and the top beam block movement. '
                          '2.03 m = 130 Doom units clear under the beam.'),
            },
        },
        'growth_chamber': {
            'name': 'Growth Chamber Cabinet',
            'role': 'solid laboratory prop',
            'description': ('A bone-framed cabinet with a dark soil bed and three pale '
                            'sprouts behind a wet glass panel. The glass is opaque geometry '
                            'in this kit; no transparency or growth animation is claimed.'),
            'collision': {
                'proxy_type': 'box', 'footprint_m': [1.40, 0.93],
                'z_range_m': [0.0, 2.31], 'solid': True,
                'walkable_surfaces': [],
                'notes': 'Solid blocker. Use as a cover object, not as a window.',
            },
        },
    },
    'skyhotel_service_well': {
        'service_lift_car': {
            'name': 'Service Lift Car',
            'role': 'lift landmark',
            'description': ('A brass and maroon service car with an open side, one ajar '
                            'door panel, amber interior light and a three-tick indicator. '
                            'Static geometry only.'),
            'collision': {
                'proxy_type': 'box_shell', 'footprint_m': [2.00, 2.02],
                'z_range_m': [0.0, 2.62], 'solid': True,
                'walkable_surfaces': [{'z_m': 0.12, 'area_m': [1.88, 1.88],
                                       'note': 'car floor; codex must add motion and door state'}],
                'notes': ('Shell with a partial front opening on -Y. This is not a moving '
                          'lift and has no floor-call logic.'),
            },
        },
        'dumbwaiter_winch_head': {
            'name': 'Dumbwaiter Winch Head',
            'role': 'service machine prop',
            'description': ('A low luggage winch with a large spoked wheel, cable spool, '
                            'hanging suitcase and three-button call plate. The wheel gives '
                            'a strong circular silhouette from the front and a compact '
                            'rectangular mass from above.'),
            'collision': {
                'proxy_type': 'box', 'footprint_m': [1.50, 0.84],
                'z_range_m': [0.0, 2.25], 'solid': True,
                'walkable_surfaces': [],
                'notes': 'Solid blocker; the wheel and case overhang the 0.8 m body depth.',
            },
        },
        'balcony_bay': {
            'name': 'Staggered Balcony Bay',
            'role': 'room-over-room module',
            'description': ('A 3.0 m room bay with a walkable floor, brass guardrail, '
                            'recessed maroon door, amber transom and a rain hood. The module '
                            'is designed to stack offset above and below another copy.'),
            'collision': {
                'proxy_type': 'mixed', 'footprint_m': [3.00, 1.22],
                'z_range_m': [0.0, 3.00], 'solid': True,
                'walkable_surfaces': [{'z_m': 0.16, 'area_m': [3.0, 1.2],
                                       'note': 'balcony floor; rear 0.18 m is wall'}],
                'barrier': {'height_m': 1.1, 'edge': '-Y', 'climbable': False},
                'notes': ('Floor at 0.16 m (10 Doom units) above the nominal level; '
                          'guardrail top at 1.26 m. Stack with a 3.0 m storey pitch.'),
            },
        },
    },
}
SHARED_META = {
    'stair_flight': {
        'name': 'Straight Stair Flight',
        'role': 'shared circulation',
        'description': ('Eight stone/steel steps, 1.5 m total rise, 2.24 m run and 1.6 m '
                        'clear width, with side stringers and a painted nosing.'),
        'collision': {
            'proxy_type': 'steps', 'footprint_m': [1.82, 2.50],
            'z_range_m': [0.0, 1.66], 'solid': True, 'climbable': True,
            'step_height_m': 0.1875, 'step_height_doom_units': 12,
            'walkable_surfaces': [{'z_m': 1.5, 'area_m': [1.6, 0.2], 'note': 'top lip only'}],
            'notes': ('12-unit risers are below the native 16-unit step limit. Two flights '
                      'plus a landing make one 3.0 m storey. No jump is required.'),
        },
    },
    'stair_landing': {
        'name': 'Stair Landing',
        'role': 'shared circulation',
        'description': ('A 1.8 m square steel landing at 1.5 m with four support posts and a '
                        'painted edge curb, sized to join two stair flights.'),
        'collision': {
            'proxy_type': 'platform', 'footprint_m': [1.80, 1.80],
            'z_range_m': [0.0, 1.55], 'solid': True, 'climbable': True,
            'walkable_surfaces': [{'z_m': 1.5, 'area_m': [1.68, 1.68],
                                   'note': 'landing deck; guardrail is a separate component'}],
            'notes': ('Posts occupy four corners; the deck is walkable. Add the guardrail '
                      'component on open edges.'),
        },
    },
    'guardrail': {
        'name': 'Guardrail Module',
        'role': 'shared safety component',
        'description': ('A 2.0 m steel rail with three posts, top and mid rails and a kick '
                        'plate, 1.1 m high.'),
        'collision': {
            'proxy_type': 'barrier', 'footprint_m': [2.10, 0.20],
            'z_range_m': [0.0, 1.12], 'solid': True, 'climbable': False,
            'barrier_height_m': 1.1,
            'walkable_surfaces': [],
            'notes': ('Use as a blocking line; 1.1 m = 70 Doom units. Do not place it in a '
                      'required route without a 1.6 m opening.'),
        },
    },
}


def export_mesh(mb, folder, seed):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    tex_name = f'{mb.name}.png'
    tex = build_texture(mb, seed)
    tex.save(folder / tex_name, optimize=False)
    obj, mtl = mb.write_obj(folder, tex_name)
    lo, hi = mb.bounds()
    uv_lo, uv_hi = mb.uv_ranges()
    return {
        'obj': obj, 'mtl': mtl, 'texture': folder / tex_name,
        'bounds_m': {'min': lo, 'max': hi,
                     'size': [round(hi[i] - lo[i], 6) for i in range(3)]},
        'triangle_count': mb.triangles,
        'vertex_count': len(mb.verts),
        'uv_range': {'min': uv_lo, 'max': uv_hi},
        'texture_size': [TEX_SIZE, TEX_SIZE],
        'materials': {name: {'hex': info['hex'], 'patch': [round(v, 4) for v in info['patch']],
                             'style': info['style']}
                      for name, info in mb.materials.items()},
    }


# -- software contact-sheet render ------------------------------------------
def _font(size=16, bold=False):
    names = ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold
             else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
    for path in names:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _sample(tex_arr, uv):
    h, w = tex_arr.shape[:2]
    x = min(w - 1, max(0, int(uv[0] * w)))
    y = min(h - 1, max(0, int((1.0 - uv[1]) * h)))
    return tex_arr[y, x]


def render_mesh(mb, texture, view, size=(420, 360)):
    verts = np.array(mb.verts, dtype=float)
    if view == 'front':
        sx, sy, depth = verts[:, 0], verts[:, 2], verts[:, 1]
        keep = np.array([n[1] < -0.05 for n in mb.normals])
        light = np.array((0.2, -1.0, 0.55)); light /= np.linalg.norm(light)
    elif view == 'top':
        sx, sy, depth = verts[:, 0], verts[:, 1], -verts[:, 2]
        keep = np.array([n[2] > 0.05 for n in mb.normals])
        light = np.array((0.4, 0.3, 1.0)); light /= np.linalg.norm(light)
    else:
        sx, sy, depth = verts[:, 0], -verts[:, 1], verts[:, 2]
        keep = np.array([n[2] < -0.05 for n in mb.normals])
        light = np.array((0.4, 0.3, -1.0)); light /= np.linalg.norm(light)
    tri_keep = keep[np.arange(len(mb.faces)) * 3]
    if not tri_keep.any():
        tri_keep = np.ones(len(mb.faces), dtype=bool)
    x0, x1 = float(sx.min()), float(sx.max())
    y0, y1 = float(sy.min()), float(sy.max())
    pad = 24
    scale = min((size[0] - 2 * pad) / max(1e-6, x1 - x0),
                (size[1] - 2 * pad) / max(1e-6, y1 - y0))
    img = Image.new('RGB', size, (26, 29, 33))
    pen = ImageDraw.Draw(img)
    # ground tick for orientation
    if view in ('front', 'bottom'):
        gy = size[1] - 18
        pen.line((20, gy, size[0] - 20, gy), fill=(48, 54, 60))
    tex_arr = np.array(texture)
    order = []
    for ti, (i0, i1, i2, mat) in enumerate(mb.faces):
        if not tri_keep[ti]:
            continue
        d = (depth[i0] + depth[i1] + depth[i2]) / 3.0
        order.append((d, ti))
    order.sort(reverse=True)
    for d, ti in order:
        i0, i1, i2, mat = mb.faces[ti]
        pts = []
        for idx in (i0, i1, i2):
            px = pad + (sx[idx] - x0) * scale
            py = size[1] - pad - (sy[idx] - y0) * scale
            pts.append((px, py))
        n = np.array(mb.normals[i0])
        lam = max(0.0, float(np.dot(n, light)))
        shade = 0.42 + 0.58 * lam
        uv = tuple((np.array(mb.uvs[i0]) + np.array(mb.uvs[i1]) + np.array(mb.uvs[i2])) / 3.0)
        col = _sample(tex_arr, uv)
        fill = tuple(int(min(255, c * shade)) for c in col)
        pen.polygon(pts, fill=fill, outline=(14, 16, 18))
    return img


def compose_3d_sheet(out_path, entries, title, seed):
    view_w, view_h = 380, 300
    cols = 3
    rows = len(entries)
    sheet = Image.new('RGB', (cols * view_w + 40, rows * (view_h + 52) + 54), (24, 27, 31))
    pen = ImageDraw.Draw(sheet)
    pen.text((20, 14), title, font=_font(20, True), fill=(236, 232, 220))
    small = _font(13)
    for r, entry in enumerate(entries):
        mb, texture = entry['mesh'], entry['texture_img']
        y0 = 48 + r * (view_h + 52)
        for c, view in enumerate(('front', 'top', 'bottom')):
            im = render_mesh(mb, texture, view, (view_w - 8, view_h - 8))
            x = 12 + c * view_w
            sheet.paste(im, (x, y0))
            pen.text((x + 4, y0 + view_h - 18), f'{view} view', font=small, fill=(190, 200, 200))
        pen.text((12, y0 + view_h - 2), f"{entry['id']}  |  {mb.triangles} tris  |  "
                 f"bounds {entry['meta']['bounds_m']['size']} m", font=_font(14, True),
                 fill=(238, 220, 150))
    sheet.save(out_path)
    return sheet


def build_all(out_root, seed=K.DEFAULT_SEED):
    out_root = Path(out_root)
    props_root = out_root / 'props3d'
    sheets_root = out_root / 'sheets'
    sheets_root.mkdir(parents=True, exist_ok=True)
    doc = {
        'format': 'nullrun-tower-props-1',
        'source_seed': int(seed),
        'license': K.LICENSE,
        'title': 'Null Run tower 3D prop and circulation kit',
        'coordinate_system': {
            'up': 'Z', 'units': 'metres', 'doom_units_per_metre': UNITS_PER_M,
            'handedness': 'right-handed', 'obj_units': 'metres',
            'conversion_note': ('1 m = 64 Doom units. The native map grid uses 128-unit '
                                'tiles, i.e. 2 m at this conversion; mesh assets and layout '
                                'tables use the requested 64 u/m convention.'),
        },
        'texture_note': ('Each OBJ has an adjacent 256x256 RGB PNG and an MTL that references '
                         'it with map_Kd. Materials map to four inset patches in that PNG; '
                         'UVs stay inside [0,1]. The textures are original procedural art.'),
        'gltf_note': ('OBJ+MTL is the delivered interchange format. A glTF exporter was not '
                      'added, per the brief not to spend the job on a new export framework.'),
        'render_note': ('Contact sheets are software orthographic previews (flat-shaded '
                        'triangles, painter-sorted). They are not engine renders and do not '
                        'claim lighting, collision or gameplay behaviour.'),
        'shared': [], 'sets': {},
    }
    sheet_entries = []
    env_sheets = {}
    for env_index, sid in enumerate(K.SET_IDS):
        env_entries = []
        env_sheet_entries = []
        for prop_index, (pid, builder) in enumerate(BUILDERS[sid].items()):
            mb = builder(K.asset_seed(seed, env_index, 40 + prop_index, 0))
            meta = dict(PROP_META[sid][pid])
            folder = props_root / sid
            exported = export_mesh(mb, folder, K.asset_seed(seed, env_index, 41 + prop_index, 0))
            if mb.triangles >= 5000:
                raise ValueError(f'{pid}: {mb.triangles} triangles exceeds 5000')
            entry = {
                'id': pid, 'name': meta['name'], 'role': meta['role'],
                'description': meta['description'],
                'obj': exported['obj'].relative_to(out_root).as_posix(),
                'mtl': exported['mtl'].relative_to(out_root).as_posix(),
                'texture': exported['texture'].relative_to(out_root).as_posix(),
                'bounds_m': exported['bounds_m'],
                'bounds_doom_units': {
                    'min': [round(v * UNITS_PER_M, 3) for v in exported['bounds_m']['min']],
                    'max': [round(v * UNITS_PER_M, 3) for v in exported['bounds_m']['max']],
                    'size': [round(v * UNITS_PER_M, 3) for v in exported['bounds_m']['size']],
                },
                'triangle_count': exported['triangle_count'],
                'vertex_count': exported['vertex_count'],
                'materials': exported['materials'],
                'uv_range': exported['uv_range'],
                'texture_size': exported['texture_size'],
                'collision': meta['collision'],
                'readability': {
                    'from_above': 'primary mass and footprint are separable in the top preview',
                    'from_below': 'overhead silhouette and chain/leg gaps are separable in the bottom preview',
                },
                'gltf': None,
                'status': 'original source proposal; not loaded into an engine',
            }
            env_entries.append(entry)
            env_sheet_entries.append({'id': pid, 'mesh': mb,
                                      'texture_img': Image.open(exported['texture']),
                                      'meta': entry})
        doc['sets'][sid] = {'name': K.SETS[sid]['name'], 'props': env_entries}
        compose_3d_sheet(sheets_root / f'{sid}-3d.png', env_sheet_entries,
                         f'{K.SETS[sid]["name"]} - 3D props (front / top / bottom)', seed)
        sheet_entries.extend(env_sheet_entries)
        env_sheets[sid] = env_sheet_entries
    shared_entries = []
    for i, (pid, builder) in enumerate(SHARED.items()):
        mb = builder(K.asset_seed(seed, 90, 50 + i, 0))
        meta = dict(SHARED_META[pid])
        folder = props_root / 'shared'
        exported = export_mesh(mb, folder, K.asset_seed(seed, 90, 51 + i, 0))
        if mb.triangles >= 5000:
            raise ValueError(f'{pid}: {mb.triangles} triangles exceeds 5000')
        entry = {
            'id': pid, 'name': meta['name'], 'role': meta['role'],
            'description': meta['description'],
            'obj': exported['obj'].relative_to(out_root).as_posix(),
            'mtl': exported['mtl'].relative_to(out_root).as_posix(),
            'texture': exported['texture'].relative_to(out_root).as_posix(),
            'bounds_m': exported['bounds_m'],
            'bounds_doom_units': {
                'min': [round(v * UNITS_PER_M, 3) for v in exported['bounds_m']['min']],
                'max': [round(v * UNITS_PER_M, 3) for v in exported['bounds_m']['max']],
                'size': [round(v * UNITS_PER_M, 3) for v in exported['bounds_m']['size']],
            },
            'triangle_count': exported['triangle_count'], 'vertex_count': exported['vertex_count'],
            'materials': exported['materials'], 'uv_range': exported['uv_range'],
            'texture_size': exported['texture_size'], 'collision': meta['collision'],
            'readability': {
                'from_above': 'steps, deck or rail line remain distinct in the top preview',
                'from_below': 'support posts and undersides remain distinct in the bottom preview',
            },
            'gltf': None, 'status': 'original source proposal; not loaded into an engine',
        }
        doc['shared'].append(entry)
        shared_entries.append({'id': pid, 'mesh': mb,
                               'texture_img': Image.open(exported['texture']),
                               'meta': entry})
    compose_3d_sheet(sheets_root / 'shared-3d.png', shared_entries,
                     'Shared stair / landing / guardrail (front / top / bottom)', seed)
    # a compact overview of one front view per environment prop
    view_w, view_h = 300, 240
    sheet = Image.new('RGB', (3 * view_w + 40, 3 * (view_h + 36) + 50), (24, 27, 31))
    pen = ImageDraw.Draw(sheet)
    pen.text((18, 12), '3D prop overview - one front view per environment', font=_font(19, True),
             fill=(238, 232, 218))
    for r, sid in enumerate(K.SET_IDS):
        for c, entry in enumerate(env_sheets[sid]):
            im = render_mesh(entry['mesh'], entry['texture_img'], 'front', (view_w - 8, view_h - 8))
            x = 12 + c * view_w; y = 46 + r * (view_h + 36)
            sheet.paste(im, (x, y))
            pen.text((x + 4, y + view_h - 18), entry['id'], font=_font(12),
                     fill=(210, 214, 208))
    sheet.save(sheets_root / 'props3d-overview.png')
    return doc
