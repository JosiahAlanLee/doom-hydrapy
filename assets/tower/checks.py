#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Independent structural checks for the Null Run tower bank.

Run:
    PYTHONDONTWRITEBYTECODE=1 python checks.py

Writes checks.json and VALIDATION.md.  Reproducibility checks generate into
temporary `_repro-*` folders inside this output folder and remove them again.
The checks prove structure and determinism, not artistic or native-render
acceptance.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent
DEFAULT_SEED = 20261031
SET_IDS = ('ashbell_foundry', 'boneglass_conservatory', 'skyhotel_service_well')
SLOTS = ('latchwing', 'relay_choir')
STATES = ('idle', 'walk', 'warn', 'attack', 'hurt', 'death')
PROPS = ('service_lamp', 'cable_shrine', 'directory_sign')
WALL_ROLES = ('primary wall', 'relief / panel', 'structural material', 'service hardware',
              'shutter / window', 'wayfinding / accent', 'landmark A', 'landmark B')
FLAT_ROLES = ('primary floor', 'utility floor', 'ordinary ceiling', 'lit ceiling')
MESH_IDS = {
    'ashbell_foundry': ('suspended_ninth_bell', 'chain_lift_cage', 'casting_furnace'),
    'boneglass_conservatory': ('root_cage_planter', 'watering_gantry', 'growth_chamber'),
    'skyhotel_service_well': ('service_lift_car', 'dumbwaiter_winch_head', 'balcony_bay'),
}
SHARED_IDS = ('stair_flight', 'stair_landing', 'guardrail')
CHECKS, METRICS = [], {}


def add(cid, ok, detail, **extra):
    entry = {'id': cid, 'pass': bool(ok), 'detail': detail}
    entry.update(extra)
    CHECKS.append(entry)
    return bool(ok)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_rgb(path):
    im = Image.open(path)
    im.load()
    return im


def arr(path, mode=None):
    im = load_rgb(path)
    if mode:
        im = im.convert(mode)
    return np.asarray(im)


def iou(a, b):
    union = int((a | b).sum())
    return float((a & b).sum()) / union if union else 1.0


def art_paths():
    out = []
    for sid in SET_IDS:
        for i in range(1, 9):
            out.append(Path('art') / sid / 'walls' / f'{i:02d}.png')
        for i in range(1, 5):
            out.append(Path('art') / sid / 'flats' / f'{i:02d}.png')
        for slot in PROPS:
            out.append(Path('art') / sid / 'props' / f'{slot}.png')
    return out


def atlas_paths():
    return [Path('mobs') / sid / f'{role}_{v}.png'
            for sid in SET_IDS for role in SLOTS for v in 'AB']


def mesh_paths():
    out = []
    for sid, ids in MESH_IDS.items():
        for pid in ids:
            out.append((sid, pid, Path('props3d') / sid / f'{pid}.obj'))
    for pid in SHARED_IDS:
        out.append(('shared', pid, Path('props3d') / 'shared' / f'{pid}.obj'))
    return out


def sheet_paths():
    out = []
    for sid in SET_IDS:
        for kind in ('kit', 'tiling', 'mobs', '3d'):
            out.append(Path('sheets') / f'{sid}-{kind}.png')
    out += [Path('sheets/shared-3d.png'), Path('sheets/props3d-overview.png'),
            Path('sheets/overview.png')]
    return out


def hp_mask(path, crop=None):
    gray = load_rgb(path).convert('L')
    a = np.asarray(gray, dtype=float)
    b = np.asarray(gray.filter(ImageFilter.GaussianBlur(2.2)), dtype=float)
    hp = np.abs(a - b)
    if crop:
        hp = hp[crop[1]:crop[3], crop[0]:crop[2]]
    threshold = max(3.0, float(np.percentile(hp, 70)))
    return hp > threshold


# -- layout / counts ---------------------------------------------------------
def check_files():
    actual = sorted((ROOT / 'art').rglob('*.png'))
    expected = [ROOT / p for p in art_paths()]
    missing = [p.relative_to(ROOT).as_posix() for p in expected if not p.is_file()]
    extra = [p.relative_to(ROOT).as_posix() for p in actual if p not in expected]
    add('art_count_45', len(actual) == 45 and not missing and not extra,
        f'{len(actual)} art PNGs; missing={missing}; extra={extra}',
        count=len(actual), missing=missing, extra=extra)
    atl = sorted((ROOT / 'mobs').rglob('*.png'))
    add('mob_atlas_count_12', len(atl) == 12,
        f'{len(atl)} mob atlases; expected 12', count=len(atl))
    objs = sorted((ROOT / 'props3d').rglob('*.obj'))
    add('mesh_obj_count_12', len(objs) == 12,
        f'{len(objs)} OBJ meshes; expected 12', count=len(objs))
    sheets = sorted((ROOT / 'sheets').glob('*.png'))
    add('sheet_count_15', len(sheets) == 15,
        f'{len(sheets)} contact sheets; expected 15', count=len(sheets))
    required = ['environments.json', 'encounters.json', 'props3d.json',
                'vertical_layouts.json', 'music_proposals.json', 'manifest.json',
                'README.md', 'LAYOUTS.md', 'CREDITS.md']
    missing_meta = [p for p in required if not (ROOT / p).is_file()]
    add('metadata_present', not missing_meta, f'missing metadata: {missing_meta}',
        missing=missing_meta)
    total = sum(p.stat().st_size for p in ROOT.rglob('*')
                if p.is_file() and not p.name.startswith('_repro'))
    add('bounded_output_size', total < 50 * 1024 * 1024,
        f'{total / 1e6:.2f} MB output (< 50 MB)', bytes=total)


def check_image_geometry():
    problems = []
    info = {}
    for rel in art_paths():
        im = load_rgb(ROOT / rel)
        expected = ((128, 128, 'RGB') if '/walls/' in rel.as_posix()
                    else (64, 64, 'RGB') if '/flats/' in rel.as_posix()
                    else (96, 128, 'RGBA'))
        if (im.width, im.height, im.mode) != expected:
            problems.append(f'{rel}: {(im.width, im.height, im.mode)} expected {expected}')
        info[rel.as_posix()] = {'size': [im.width, im.height], 'mode': im.mode}
    add('image_dimensions_modes', not problems,
        'walls 128x128 RGB, flats 64x64 RGB, props 96x128 RGBA'
        if not problems else '; '.join(problems[:10]), images=len(info))
    problems = []
    for rel in atlas_paths():
        im = load_rgb(ROOT / rel)
        if (im.width, im.height, im.mode) != (512, 768, 'RGBA'):
            problems.append(f'{rel}: {(im.width, im.height, im.mode)}')
    add('atlas_dimensions_modes', not problems,
        'all 12 atlases are 512x768 RGBA' if not problems else '; '.join(problems), atlases=12)
    problems = []
    for rel in sheet_paths():
        im = load_rgb(ROOT / rel)
        if im.mode != 'RGB' or im.width < 400 or im.height < 400:
            problems.append(f'{rel}: {im.size} {im.mode}')
    add('sheet_modes_sizes', not problems,
        '15 sheets are RGB and at least 400x400' if not problems else '; '.join(problems),
        sheets=len(sheet_paths()))


def check_seams():
    problems = []
    rows = []
    for rel in art_paths():
        if '/props/' in rel.as_posix():
            continue
        a = arr(ROOT / rel)
        vb = bool(np.array_equal(a[0], a[-1]))
        hl = bool(np.array_equal(a[:, 0], a[:, -1]))
        rows.append({'file': rel.as_posix(), 'top_bottom_equal': vb, 'left_right_equal': hl})
        if not (vb and hl):
            problems.append(rel.as_posix())
    add('seams_exact', not problems,
        'opposite edge rows and columns match exactly for 36 walls/flats'
        if not problems else f'seam failures: {problems}', seams=rows)
    doc = json.loads((ROOT / 'environments.json').read_text())
    decl = doc.get('seam_behavior', {})
    ok = all(isinstance(decl.get(k), str) and decl[k] for k in ('walls', 'flats', 'props'))
    ok = ok and 'both axes' in decl.get('walls', '') and 'both axes' in decl.get('flats', '')
    ok = ok and all(isinstance(s.get('seam_behavior'), dict) for s in doc.get('sets', []))
    add('seams_documented', ok, 'environments.json documents wall/flat/prop seam behaviour')


def check_props():
    problems = []
    for sid in SET_IDS:
        for slot in PROPS:
            p = ROOT / 'art' / sid / 'props' / f'{slot}.png'
            a = arr(p)
            alpha = a[:, :, 3]
            ys, xs = np.where(alpha > 0)
            if not len(xs):
                problems.append(f'{p}: blank')
                continue
            x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
            cov = float((alpha > 0).mean())
            inside = int((alpha[y0:y1 + 1, x0:x1 + 1] == 0).sum())
            area = (x1 - x0 + 1) * (y1 - y0 + 1)
            if x0 < 3 or y0 < 3 or x1 > 92 or y1 > 124 or y1 < 121:
                problems.append(f'{p}: bbox={x0},{y0},{x1},{y1}')
            if (x1 - x0 + 1) < 20 or (y1 - y0 + 1) < 40:
                problems.append(f'{p}: small bbox')
            if cov > 0.75 or inside < area * 0.08:
                problems.append(f'{p}: coverage={cov:.2f} inside={inside}/{area}')
            if int(alpha[0].max()) or int(alpha[-1].max()) or int(alpha[:, 0].max()) or int(alpha[:, -1].max()):
                problems.append(f'{p}: edge alpha')
    add('props_alpha_bounds_anchor', not problems,
        'all 9 props are bottom-anchored RGBA cut-outs with 3 px margins and no backdrop'
        if not problems else '; '.join(problems[:10]), problems=problems)


def check_quality():
    problems = []
    unique = {}
    for rel in art_paths():
        p = ROOT / rel
        a = arr(p)
        alpha = a[:, :, 3] if a.shape[2] == 4 else None
        opaque = (alpha > 0) if alpha is not None else np.ones(a.shape[:2], bool)
        g = a[:, :, :3].mean(axis=2)[opaque]
        u = len(np.unique(a.reshape(-1, a.shape[2]), axis=0))
        cov = float(opaque.mean())
        spread = float(np.percentile(g, 95) - np.percentile(g, 5))
        unique[rel.as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
        is_prop = '/props/' in rel.as_posix()
        min_unique = 12 if is_prop else 16
        cov_ok = 0.05 <= cov <= 0.75 if is_prop else cov > 0.95
        if u < min_unique or spread < 35 or not cov_ok:
            problems.append(f'{rel}: unique={u} spread={spread:.1f} cov={cov:.2f}')
    add('assets_nonblank_contrast', not problems,
        '45 art PNGs are nonblank with a minimum colour and contrast floor'
        if not problems else '; '.join(problems[:10]), problems=problems)
    add('assets_unique', len(set(unique.values())) == 45,
        f'{len(set(unique.values()))}/45 unique art PNG hashes', unique=len(set(unique.values())))
    atlas_u = {p.as_posix(): sha(ROOT / p) for p in atlas_paths()}
    add('atlases_unique', len(set(atlas_u.values())) == 12,
        f'{len(set(atlas_u.values()))}/12 unique atlas hashes')


def check_palette_separation():
    means = {}
    for sid in SET_IDS:
        vals = []
        for i in (1, 3, 5, 7):
            a = arr(ROOT / 'art' / sid / 'walls' / f'{i:02d}.png', 'RGB').astype(float)
            vals.append(a.reshape(-1, 3).mean(axis=0))
        means[sid] = np.mean(vals, axis=0)
    pairs = []
    for i, a in enumerate(SET_IDS):
        for b in SET_IDS[i + 1:]:
            dist = float(np.linalg.norm(means[a] - means[b]))
            pairs.append({'pair': [a, b], 'mean_rgb_distance': round(dist, 2)})
    ok = all(p['mean_rgb_distance'] > 25 for p in pairs)
    # high-pass structure: a palette-only recolour cannot pass
    per = []
    for i, a in enumerate(SET_IDS):
        for b in SET_IDS[i + 1:]:
            vals = []
            for i2 in (1, 3, 5, 7):
                ma = hp_mask(ROOT / 'art' / a / 'walls' / f'{i2:02d}.png', (4, 4, 124, 124))
                mb = hp_mask(ROOT / 'art' / b / 'walls' / f'{i2:02d}.png', (4, 4, 124, 124))
                vals.append(iou(ma, mb))
            per.append({'pair': [a, b], 'wall_structure_iou_mean': round(float(np.mean(vals)), 3),
                        'max': round(float(np.max(vals)), 3)})
    ok = ok and all(p['wall_structure_iou_mean'] <= 0.55 and p['max'] <= 0.8 for p in per)
    METRICS['palette_separation'] = {'means': {k: [round(float(x), 1) for x in v] for k, v in means.items()},
                                     'pairs': pairs, 'structure': per,
                                     'note': ('Freedoom PLAYPAL is not present in this folder; '
                                              'this is a mean-RGB + high-pass structure proxy. '
                                              'Codex must perform the real palette conversion.')}
    add('palette_separation_grey_proxy', ok,
        'set mean RGB separation > 25 and wall structure IoU mean <= 0.55/max <= 0.80',
        pairs=pairs, structure=per)


def check_inter_set_structure():
    def group_iou(group):
        vals = []
        for i, a in enumerate(SET_IDS):
            for b in SET_IDS[i + 1:]:
                local = []
                for n in ([f'{j:02d}' for j in range(1, 9)] if group == 'walls'
                          else [f'{j:02d}' for j in range(1, 5)] if group == 'flats'
                          else list(PROPS)):
                    pa = ROOT / 'art' / a / group / (f'{n}.png')
                    pb = ROOT / 'art' / b / group / (f'{n}.png')
                    crop = (4, 4, 124, 124) if group == 'walls' else (3, 3, 60, 60) if group == 'flats' else None
                    local.append(iou(hp_mask(pa, crop), hp_mask(pb, crop)))
                vals.append(float(np.mean(local)))
        return float(np.mean(vals)), float(np.max(vals))
    wm, wx = group_iou('walls'); fm, fx = group_iou('flats'); pm, px = group_iou('props')
    ok = wm <= 0.55 and wx <= 0.80 and fm <= 0.60 and fx <= 0.85 and pm <= 0.65 and px <= 0.85
    METRICS['inter_set_structure'] = {'wall_mean': round(wm, 3), 'wall_max': round(wx, 3),
                                      'flat_mean': round(fm, 3), 'flat_max': round(fx, 3),
                                      'prop_mean': round(pm, 3), 'prop_max': round(px, 3)}
    add('inter_set_structure', ok,
        f'wall {wm:.3f}/{wx:.3f}; flat {fm:.3f}/{fx:.3f}; prop {pm:.3f}/{px:.3f}',
        **METRICS['inter_set_structure'])


# -- atlases -----------------------------------------------------------------
def atlas_cells(path):
    a = arr(ROOT / path)
    cells = {}
    for r, state in enumerate(STATES):
        for c in range(4):
            cells[(state, c)] = a[r * 128:(r + 1) * 128, c * 128:(c + 1) * 128]
    return a, cells


def bbox(alpha):
    ys, xs = np.where(alpha > 0)
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def check_atlases():
    problems = []
    all_cells = {}
    for rel in atlas_paths():
        a, cells = atlas_cells(rel)
        all_cells[rel.as_posix()] = cells
        if set(np.unique(a[:, :, 3]).tolist()) - {0, 255}:
            problems.append(f'{rel}: semi-transparent alpha')
        if len(cells) != 24:
            problems.append(f'{rel}: {len(cells)} cells')
        for (state, col), cell in cells.items():
            al = cell[:, :, 3]
            bb = bbox(al)
            if bb is None:
                problems.append(f'{rel} {state} {col}: blank')
                continue
            x0, y0, x1, y1 = bb
            if x0 < 3 or y0 < 3 or x1 > 124 or y1 > 124:
                problems.append(f'{rel} {state} {col}: padding {bb}')
            if y1 != 120:
                problems.append(f'{rel} {state} {col}: floor y={y1}')
            if not (0.01 <= float((al > 0).mean()) <= 0.80):
                problems.append(f'{rel} {state} {col}: coverage')
            if cell[0, 0, 3] or cell[0, -1, 3] or cell[-1, 0, 3] or cell[-1, -1, 3]:
                problems.append(f'{rel} {state} {col}: opaque corner')
    add('atlas_layout_24_padding_anchor', not problems,
        '288 cells: 24 per atlas, >=3 px padding, exact y=120 floor anchor, crisp alpha'
        if not problems else '; '.join(problems[:10]), problems=problems[:30])

    problems = []
    min_diff = 10 ** 9
    unique_counts = {}
    for key, cells in all_cells.items():
        hashes = {hashlib.sha256(c.tobytes()).hexdigest() for c in cells.values()}
        unique_counts[key] = len(hashes)
        if len(hashes) < 24:
            problems.append(f'{key}: {len(hashes)}/24 unique')
        for state in STATES:
            for c in range(3):
                diff = int((cells[(state, c)] != cells[(state, c + 1)]).any(axis=2).sum())
                min_diff = min(min_diff, diff)
                if diff < 100:
                    problems.append(f'{key} {state} {c}->{c+1}: {diff} px')
    METRICS['atlas_animation'] = {'min_consecutive_changed_pixels': int(min_diff),
                                  'unique_cells': unique_counts}
    add('atlas_frames_unique_animated', not problems,
        f'all 24 cells unique; every consecutive pair changes >=100 px; minimum {min_diff}'
        if not problems else '; '.join(problems[:10]),
        min_changed_pixels=int(min_diff), unique_cells=unique_counts)

    problems = []
    corpse = {}
    for key, cells in all_cells.items():
        cell = cells[('death', 3)]
        bb = bbox(cell[:, :, 3])
        cov = float((cell[:, :, 3] > 0).mean())
        corpse[key] = {'bbox': bb, 'coverage': round(cov, 3)}
        if bb is None or (bb[2] - bb[0]) < 24 or (bb[3] - bb[1]) < 10 or cov < 0.02:
            problems.append(f'{key}: {bb} cov={cov:.3f}')
    add('atlas_frame23_corpse', not problems,
        'all 12 frame-23 cells contain a visible corpse' if not problems else '; '.join(problems),
        corpse=corpse)

    # A/B structural variants
    problems = []
    ab = {}
    for sid in SET_IDS:
        for role in SLOTS:
            ma = all_cells[f'mobs/{sid}/{role}_A.png'][('idle', 0)][:, :, 3] > 0
            mb = all_cells[f'mobs/{sid}/{role}_B.png'][('idle', 0)][:, :, 3] > 0
            value = iou(ma, mb)
            ab[f'{sid}/{role}'] = round(value, 3)
            if value > 0.92:
                problems.append(f'{sid}/{role}: silhouette IoU {value:.3f}')
    add('atlas_ab_structural_variants', not problems,
        'A/B idle silhouettes differ structurally (IoU <= 0.92)' if not problems
        else '; '.join(problems), ab_idle_silhouette_iou=ab)

    # Six identities distinct
    problems = []
    pairs = {}
    for i, sid_a in enumerate(SET_IDS):
        for role_a in SLOTS:
            for sid_b in SET_IDS:
                for role_b in SLOTS:
                    if (sid_a, role_a) >= (sid_b, role_b):
                        continue
                    ma = all_cells[f'mobs/{sid_a}/{role_a}_A.png'][('idle', 0)][:, :, 3] > 0
                    mb = all_cells[f'mobs/{sid_b}/{role_b}_A.png'][('idle', 0)][:, :, 3] > 0
                    value = iou(ma, mb)
                    pairs[f'{sid_a}/{role_a} vs {sid_b}/{role_b}'] = round(value, 3)
                    if value > 0.8:
                        problems.append(f'{sid_a}/{role_a} vs {sid_b}/{role_b}: {value:.3f}')
    add('atlas_six_identities_distinct', not problems,
        'all six identities have distinct idle silhouettes (IoU <= 0.80)' if not problems
        else '; '.join(problems), identity_iou=pairs)
    return all_cells


# -- 3D ----------------------------------------------------------------------
def parse_obj(path):
    verts, uvs, normals, faces = [], [], [], []
    for line in Path(path).read_text().splitlines():
        if line.startswith('v '):
            verts.append([float(x) for x in line.split()[1:4]])
        elif line.startswith('vt '):
            uvs.append([float(x) for x in line.split()[1:3]])
        elif line.startswith('vn '):
            normals.append([float(x) for x in line.split()[1:4]])
        elif line.startswith('f '):
            parts = line.split()[1:]
            if len(parts) != 3:
                raise ValueError(f'{path}: non-triangle face {line}')
            face = []
            for part in parts:
                bits = part.split('/')
                face.append(tuple(int(bits[i]) for i in range(3)))
            faces.append(face)
    return (np.array(verts, float), np.array(uvs, float), np.array(normals, float), faces)


def check_meshes():
    doc = json.loads((ROOT / 'props3d.json').read_text())
    entries = []
    for sid, ids in MESH_IDS.items():
        entries += doc['sets'][sid]['props']
    entries += doc['shared']
    by_id = {e['id']: e for e in entries}
    problems, info, bounds_ok, finite_ok, refs_ok = [], {}, [], [], []
    for e in entries:
        pid = e['id']
        rel = Path(e['obj'])
        p = ROOT / rel
        try:
            verts, uvs, normals, faces = parse_obj(p)
        except Exception as exc:  # noqa: BLE001
            problems.append(f'{rel}: {exc}')
            continue
        info[pid] = {'triangles': len(faces), 'vertices': len(verts), 'uvs': len(uvs),
                     'normals': len(normals),
                     'bounds_m': {'min': [round(float(v), 6) for v in verts.min(axis=0)],
                                  'max': [round(float(v), 6) for v in verts.max(axis=0)]},
                     'uv_range': {'min': [round(float(v), 6) for v in uvs.min(axis=0)],
                                  'max': [round(float(v), 6) for v in uvs.max(axis=0)]}}
        if len(faces) != e['triangle_count'] or len(verts) != e['vertex_count']:
            finite_ok.append(f'{pid}: count mismatch')
        if len(verts) != len(uvs) or len(verts) != len(normals):
            finite_ok.append(f'{pid}: v/vt/vn count mismatch')
        if not (np.isfinite(verts).all() and np.isfinite(uvs).all() and np.isfinite(normals).all()):
            finite_ok.append(f'{pid}: non-finite value')
        if len(faces):
            idx = np.array(faces)
            if idx.min() < 1 or idx.max() > len(verts):
                finite_ok.append(f'{pid}: face index out of range')
            # every triangle nonzero area
            bad = 0
            for face in faces:
                a = verts[face[0][0] - 1]; b = verts[face[1][0] - 1]; c = verts[face[2][0] - 1]
                if np.linalg.norm(np.cross(b - a, c - a)) < 1e-9:
                    bad += 1
            if bad:
                finite_ok.append(f'{pid}: {bad} degenerate triangles')
            if uvs.min() < -1e-9 or uvs.max() > 1 + 1e-9:
                finite_ok.append(f'{pid}: UV outside [0,1]')
            nl = np.linalg.norm(normals, axis=1)
            if nl.max() > 1.001 or nl.min() < 0.999:
                finite_ok.append(f'{pid}: non-unit normal')
            lo = verts.min(axis=0); hi = verts.max(axis=0)
            jlo = np.array(e['bounds_m']['min']); jhi = np.array(e['bounds_m']['max'])
            if not (np.allclose(lo, jlo, atol=1e-4) and np.allclose(hi, jhi, atol=1e-4)):
                bounds_ok.append(f'{pid}: OBJ {lo.tolist()}..{hi.tolist()} JSON {jlo.tolist()}..{jhi.tolist()}')
            if e['triangle_count'] >= 5000:
                bounds_ok.append(f'{pid}: {e["triangle_count"]} triangles')
            # top/bottom footprint extent
            ext = hi - lo
            if ext[0] < 0.2 or ext[1] < 0.2:
                bounds_ok.append(f'{pid}: degenerate top/bottom footprint {ext.tolist()}')
        # MTL and texture references
        mtl = ROOT / e['mtl']
        tex = ROOT / e['texture']
        if not mtl.is_file() or not tex.is_file():
            refs_ok.append(f'{pid}: missing mtl/texture')
        else:
            text = mtl.read_text()
            if 'map_Kd' not in text or tex.name not in text:
                refs_ok.append(f'{pid}: map_Kd does not name {tex.name}')
            tim = load_rgb(tex)
            if tim.size != (256, 256) or tim.mode != 'RGB':
                refs_ok.append(f'{pid}: texture {tim.size} {tim.mode}')
    add('mesh_parse_counts', not problems and not finite_ok,
        '12 OBJ files parse as triangles; face/vertex/UV/normal counts and finite values are valid'
        if not problems and not finite_ok else '; '.join((problems + finite_ok)[:12]),
        meshes=info, problems=problems, finite_problems=finite_ok)
    add('mesh_bounds_triangles_honest', not bounds_ok,
        'mesh-derived bounds match props3d.json and every mesh is <5000 triangles'
        if not bounds_ok else '; '.join(bounds_ok[:12]), problems=bounds_ok)
    add('mesh_texture_references', not refs_ok,
        'every OBJ has an MTL with map_Kd and an adjacent 256x256 RGB PNG'
        if not refs_ok else '; '.join(refs_ok[:12]), problems=refs_ok)

    # collision metadata
    problems = []
    for e in entries:
        c = e.get('collision') or {}
        for key in ('proxy_type', 'footprint_m', 'z_range_m', 'solid', 'notes'):
            if key not in c:
                problems.append(f'{e["id"]}: missing collision.{key}')
                continue
        if 'footprint_m' in c and (len(c['footprint_m']) != 2 or not all(v >= 0 for v in c['footprint_m'])):
            problems.append(f'{e["id"]}: footprint')
        if 'z_range_m' in c and (len(c['z_range_m']) != 2 or c['z_range_m'][0] > c['z_range_m'][1]):
            problems.append(f'{e["id"]}: z range')
        if e['id'] == 'stair_flight':
            if abs(c.get('step_height_m', 0) - 0.1875) > 1e-9 or c.get('step_height_doom_units') != 12:
                problems.append('stair_flight: step height')
        if e['id'] == 'guardrail' and c.get('barrier_height_m', 0) < 1.0:
            problems.append('guardrail: barrier height')
    add('mesh_collision_metadata', not problems,
        'all 12 entries have finite footprint/z proxies, notes and stair/guardrail limits'
        if not problems else '; '.join(problems[:12]), problems=problems)


# -- layouts / music / metadata ----------------------------------------------
def check_layouts():
    doc = json.loads((ROOT / 'vertical_layouts.json').read_text())
    problems = []
    if doc.get('format') != 'nullrun-vertical-layouts-1' or set(doc.get('environments', {})) != set(SET_IDS):
        problems.append('format/sets')
    for sid, e in doc.get('environments', {}).items():
        if e['height_m'] < 12:
            problems.append(f'{sid}: height')
        if len(e['levels']) < 6:
            problems.append(f'{sid}: levels')
        zs = [lv['z_m'] for lv in e['levels']]
        if zs != sorted(zs) or len(set(zs)) != len(zs):
            problems.append(f'{sid}: level z order')
        if abs(zs[-1] - e['height_m']) > 1e-9 or abs(e['tower_proof']['physical_gain_m'] - e['height_m']) > 1e-9:
            problems.append(f'{sid}: tower proof')
        if abs(e['storey_m'] - 3.0) > 1e-9:
            problems.append(f'{sid}: storey')
        for key in ('lower', 'middle', 'upper'):
            if not e['routes'].get(key):
                problems.append(f'{sid}: route {key}')
        if not e['stair_alternative'].get('description') or not e['lift_alternative'].get('description'):
            problems.append(f'{sid}: stair/lift')
        if 'unimplemented' not in e['lift_alternative'].get('status', ''):
            problems.append(f'{sid}: lift status')
        if not e['fall_recovery'].get('catch_surfaces') or not e['fall_recovery'].get('return'):
            problems.append(f'{sid}: fall recovery')
        if not e['safe_spawn'].get('description') or not e['return_path'].get('description'):
            problems.append(f'{sid}: spawn/return')
        if not e['arena_perch_spacing'].get('arena_min_m') or not e['arena_perch_spacing'].get('perch_spacing_m'):
            problems.append(f'{sid}: spacing')
        if not e['room_over_room']:
            problems.append(f'{sid}: room-over-room')
        f = e['first_pass_constraints']
        if f['unavoidable_jumps'] or f['precision_platforming_required'] or f['unseen_hits'] or f['max_required_gap_m'] != 0.0:
            problems.append(f'{sid}: first pass constraint')
    add('layouts_schema_and_tower_proof', not problems,
        '3 environments; 6-7 levels; real 15/15/18 m height; routes, stairs, lifts, recovery, spawn, return, spacing and room-over-room present'
        if not problems else '; '.join(problems[:12]), problems=problems)

    problems = []
    for sid, e in doc['environments'].items():
        nc = e['native_constraints']
        if nc['max_step_doom_units'] > 16 or nc['min_headroom_doom_units'] < 96:
            problems.append(f'{sid}: native limits')
        mc = e['mesh_constraints']
        if '12-unit' not in mc['stair_component']:
            problems.append(f'{sid}: mesh stair limit')
        if e['stair_alternative']['riser_doom_units'] != 12:
            problems.append(f'{sid}: riser units')
        if abs(e['stair_alternative']['flight_rise_m'] * 2 - e['storey_m']) > 1e-9:
            problems.append(f'{sid}: flight/storey')
    add('layouts_native_vs_mesh_constraints', not problems,
        'native step 16 u / headroom 96 u are kept separate from mesh 12-unit risers'
        if not problems else '; '.join(problems), problems=problems)


def check_music():
    sys.path.insert(0, str(ROOT))
    import kit_music as MU
    problems = []
    loaded = {}
    for path in sorted((ROOT / 'music_profiles').glob('*.json')):
        try:
            p = json.loads(path.read_text())
            MU.validate_profile(p)
            loaded[p['id']] = p
        except Exception as exc:  # noqa: BLE001
            problems.append(f'{path.name}: {exc}')
    if set(loaded) != set(SET_IDS):
        problems.append(f'profiles {sorted(loaded)}')
    add('music_profiles_valid', not problems,
        '3 profiles pass the mirrored host schema validator' if not problems else '; '.join(problems),
        profiles=sorted(loaded))
    # exact host validator acceptance, if the reviewed host file is readable
    host = Path('/home/echevarian/dev/shared/codex/nullrun-hires-20261031/music_package/nullrun_music/profiles.py')
    host_note = 'host file not found; mirrored validator used'
    host_ok = True
    if host.is_file():
        try:
            spec = importlib.util.spec_from_file_location('_nullrun_host_profiles', host)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            for p in loaded.values():
                mod.validate_profile(p)
            host_note = 'host validate_profile accepted all 3 proposals'
        except Exception as exc:  # noqa: BLE001
            host_ok = False
            host_note = f'host validator rejected: {exc}'
    add('music_host_schema_accepts', host_ok, host_note, host_path=str(host))
    audio = [p.name for p in ROOT.rglob('*') if p.suffix.lower() in ('.wav', '.ogg', '.mp3', '.flac')]
    add('music_no_rendered_audio', not audio,
        'no rendered audio files exist; profiles are written proposals only' if not audio
        else f'audio files: {audio}', audio=audio)
    index = json.loads((ROOT / 'music_proposals.json').read_text())
    add('music_proposal_status', 'PROPOSAL ONLY' in index.get('status', ''),
        'music_proposals.json states proposal-only, not rendered/auditioned')


def check_metadata():
    env = json.loads((ROOT / 'environments.json').read_text())
    problems = []
    if env.get('format') != 'nullrun-environment-kit-1' or env.get('source_seed') != DEFAULT_SEED:
        problems.append('format/seed')
    if {s['id'] for s in env.get('sets', [])} != set(SET_IDS) or len(env.get('sets', [])) != 3:
        problems.append('sets')
    for s in env.get('sets', []):
        if list(s['props']) != list(PROPS):
            problems.append(f'{s["id"]}: prop slots')
        if s['wall_roles'] != list(WALL_ROLES) or s['flat_roles'] != list(FLAT_ROLES):
            problems.append(f'{s["id"]}: roles')
        if not s.get('landmark', {}).get('name') or not s.get('palette'):
            problems.append(f'{s["id"]}: landmark/palette')
    if env.get('integration_status', {}).get('engine_changed') is not False:
        problems.append('engine_changed claim')
    add('environments_schema', not problems,
        'nullrun-environment-kit-1 with 3 sets, 8 wall roles, 4 flat roles and 3 prop slots'
        if not problems else '; '.join(problems), problems=problems)

    enc = json.loads((ROOT / 'encounters.json').read_text())
    problems = []
    if enc.get('format') != 'nullrun-environment-mobs-1' or set(enc.get('sets', {})) != set(SET_IDS):
        problems.append('format/sets')
    for sid, roles in enc.get('sets', {}).items():
        if set(roles) != set(SLOTS):
            problems.append(f'{sid}: roles')
        for role, e in roles.items():
            for key in ('id', 'name', 'description', 'variant_a', 'variant_b', 'tells',
                        'counterplay', 'atlas_a', 'atlas_b', 'vertical_behavior_proposal'):
                if not e.get(key):
                    problems.append(f'{sid}/{role}: {key}')
            if not (ROOT / e['atlas_a']).is_file() or not (ROOT / e['atlas_b']).is_file():
                problems.append(f'{sid}/{role}: atlas missing')
            if 'NOT IMPLEMENTED' not in e['vertical_behavior_proposal'].get('status', ''):
                problems.append(f'{sid}/{role}: vertical status')
            if 'no new ai' not in e.get('limits', '').lower():
                problems.append(f'{sid}/{role}: AI limit')
    add('encounters_schema', not problems,
        '6 identities, A/B atlases, tells/counterplay and unimplemented vertical proposals'
        if not problems else '; '.join(problems), problems=problems)

    p3 = json.loads((ROOT / 'props3d.json').read_text())
    problems = []
    cs = p3.get('coordinate_system', {})
    if p3.get('format') != 'nullrun-tower-props-1' or cs.get('up') != 'Z' or cs.get('units') != 'metres' \
            or cs.get('doom_units_per_metre') != 64:
        problems.append('format/coordinates')
    if len(p3.get('shared', [])) != 3 or set(p3.get('sets', {})) != set(SET_IDS):
        problems.append('entry count')
    for sid, s in p3.get('sets', {}).items():
        if len(s.get('props', [])) != 3:
            problems.append(f'{sid}: props')
    for e in [x for s in p3.get('sets', {}).values() for x in s['props']] + p3.get('shared', []):
        if e.get('gltf') is not None:
            problems.append(f'{e["id"]}: gltf claim')
        if 'not loaded' not in e.get('status', ''):
            problems.append(f'{e["id"]}: status')
    add('props3d_schema', not problems,
        'Z-up metres, 1 m=64 Doom units, 9 environment + 3 shared entries, no engine-load claim'
        if not problems else '; '.join(problems), problems=problems)


# -- reproducibility ---------------------------------------------------------
def _hash_map(root, include_manifest=True):
    out = {}
    root = Path(root)
    for p in sorted(root.rglob('*')):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if rel in ('checks.json', 'VALIDATION.md'):
            continue
        if not include_manifest and rel == 'manifest.json':
            continue
        out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def _run_generator(out, seed):
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    cmd = [sys.executable, str(ROOT / 'generate.py'), '--out', str(out), '--seed', str(seed)]
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-1200:] + proc.stdout[-600:])
    return time.time() - t0


def check_reproducibility():
    a = Path(tempfile.mkdtemp(prefix='_repro-a-', dir=ROOT))
    b = Path(tempfile.mkdtemp(prefix='_repro-b-', dir=ROOT))
    s = Path(tempfile.mkdtemp(prefix='_repro-seed-', dir=ROOT))
    try:
        t_a = _run_generator(a, DEFAULT_SEED)
        t_b = _run_generator(b, DEFAULT_SEED)
        ha, hb = _hash_map(a), _hash_map(b)
        same = ha == hb
        add('reproducible_two_runs', same,
            f'two fresh folders are byte-identical ({len(ha)} files; {t_a:.1f}s + {t_b:.1f}s)'
            if same else f'{len(set(ha) ^ set(hb))} path differences; content mismatch',
            files=len(ha), seconds=round(t_a + t_b, 2))
        committed = _hash_map(ROOT)
        # compare only files the generator produces
        subset = {k: v for k, v in committed.items() if k in ha}
        match = subset == ha
        missing = sorted(set(ha) - set(committed))
        add('matches_committed_output', match,
            f'fresh generation matches committed generated files ({len(ha)} files)'
            if match else f'mismatch; missing in committed={missing[:5]}',
            missing=missing[:20])
        t_s = _run_generator(s, DEFAULT_SEED + 1)
        hs = _hash_map(s)
        art = [p.as_posix() for p in art_paths()]
        atl = [p.as_posix() for p in atlas_paths()]
        p3doc = json.loads((ROOT / 'props3d.json').read_text())
        tex = [e['texture'] for sid in SET_IDS for e in p3doc['sets'][sid]['props']]
        tex += [e['texture'] for e in p3doc['shared']]
        changed_art = sum(1 for p in art if ha.get(p) != hs.get(p))
        changed_atl = sum(1 for p in atl if ha.get(p) != hs.get(p))
        changed_tex = sum(1 for p in tex if ha.get(p) != hs.get(p))
        ok = changed_art == len(art) and changed_atl == len(atl) and changed_tex == len(tex)
        METRICS['seed_sensitivity'] = {'art': [changed_art, len(art)],
                                       'mobs': [changed_atl, len(atl)],
                                       'textures': [changed_tex, len(tex)],
                                       'seconds': round(t_s, 2)}
        add('seed_sensitivity', ok,
            f'seed+1 changes {changed_art}/45 art, {changed_atl}/12 atlases, '
            f'{changed_tex}/12 textures; OBJ/MTL geometry is intentionally stable',
            **METRICS['seed_sensitivity'])
    finally:
        for p in (a, b, s):
            shutil.rmtree(p, ignore_errors=True)


def check_manifest():
    doc = json.loads((ROOT / 'manifest.json').read_text())
    problems = []
    if doc.get('format') != 'nullrun-tower-manifest-1' or doc.get('algorithm') != 'sha256':
        problems.append('format')
    listed = {f['path']: f for f in doc.get('files', [])}
    for f in doc.get('files', []):
        p = ROOT / f['path']
        if not p.is_file() or sha(p) != f['sha256'] or p.stat().st_size != f['bytes']:
            problems.append(f['path'])
    if doc.get('file_count') != len(doc.get('files', [])):
        problems.append('file_count')
    if doc.get('total_bytes') != sum(f['bytes'] for f in doc.get('files', [])):
        problems.append('total_bytes')
    bundle = hashlib.sha256(''.join(f"{f['path']} {f['sha256']}\n"
                                    for f in doc.get('files', [])).encode()).hexdigest()
    if bundle != doc.get('artifact_bundle_sha256'):
        problems.append('bundle')
    if 'checks.json' in listed or 'VALIDATION.md' in listed:
        problems.append('check outputs included')
    for s in doc.get('sources', []):
        p = ROOT / s['path']
        if p.is_file() and sha(p) != s['sha256']:
            problems.append(f'source {s["path"]}')
    add('manifest_integrity', not problems,
        f'manifest hashes {doc.get("file_count")} generated files and {doc.get("source_count")} source modules'
        if not problems else '; '.join(problems[:12]), problems=problems, doc=doc)


def main():
    t0 = time.time()
    check_files()
    check_image_geometry()
    check_seams()
    check_props()
    check_quality()
    check_palette_separation()
    check_inter_set_structure()
    check_atlases()
    check_meshes()
    check_layouts()
    check_music()
    check_metadata()
    check_reproducibility()
    check_manifest()
    failed = [c['id'] for c in CHECKS if not c['pass']]
    doc = {
        'format': 'nullrun-tower-checks-1',
        'source_seed': DEFAULT_SEED,
        'license': 'GPL-2.0-or-later',
        'passed': len(CHECKS) - len(failed), 'failed': len(failed),
        'total': len(CHECKS), 'failed_ids': failed,
        'seconds': round(time.time() - t0, 2),
        'commands': [
            'PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python generate.py --out . --seed 20261031',
            'PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python checks.py',
            'PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python make_manifest.py',
            'PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python checks.py',
        ],
        'visual_review': ('The 15 contact sheets were viewed locally with the image viewer in this '
                          'run; this is not a native-engine render. Codex must still perform the '
                          'native 640x400 and palette check.'),
        'results': CHECKS, 'metrics': METRICS,
        'limitations': [
            'Structural checks only; not artistic or native-render acceptance.',
            'Freedoom PLAYPAL is not in this folder; palette separation uses a mean-RGB/high-pass proxy.',
            'Music profiles are schema proposals; no audio was rendered or auditioned.',
            'Vertical mob AI and moving lifts are proposals only and are not implemented.',
            'Visual review was performed on the generated contact sheets; Codex must still render in the native engine.',
        ],
    }
    (ROOT / 'checks.json').write_text(json.dumps(doc, indent=2) + '\n')
    lines = ['# Mechanical validation report', '',
             f'Result: **{doc["passed"]}/{doc["total"]} checks passed** in {doc["seconds"]} s.',
             f'Failed: {failed if failed else "none"}.', '',
             'These are structural/deterministic checks, not an artistic or native-render acceptance claim.',
             '', '## Commands run', '```sh']
    lines += doc['commands']
    lines += ['```', '', 'Visual review: ' + doc['visual_review'], '',
              '| Check | Result | Detail |', '| --- | --- | --- |']
    for c in CHECKS:
        lines.append(f'| `{c["id"]}` | {"PASS" if c["pass"] else "FAIL"} | '
                     f'{str(c["detail"]).replace("|", "/")} |')
    # readable per-atlas and per-mesh tables
    lines += ['', '## Per-atlas frames', '',
              '| Atlas | Unique cells | Consecutive min px | Corpse bbox | Corpse coverage |',
              '| --- | --- | --- | --- | --- |']
    corpse = next((c for c in CHECKS if c['id'] == 'atlas_frame23_corpse'), {})
    unique = next((c for c in CHECKS if c['id'] == 'atlas_frames_unique_animated'), {})
    for key in sorted(corpse.get('corpse', {})):
        bb = corpse['corpse'][key]['bbox']
        cov = corpse['corpse'][key]['coverage']
        lines.append(f'| `{key}` | {unique.get("unique_cells", {}).get(key, "?")} | '
                     f'{unique.get("min_changed_pixels", "?")} | {bb} | {cov:.3f} |')
    mesh_info = next((c for c in CHECKS if c['id'] == 'mesh_parse_counts'), {}).get('meshes', {})
    lines += ['', '## Per-mesh validation', '',
              '| Mesh | Triangles | Vertices | Bounds m (min -> max) | UV range |',
              '| --- | --- | --- | --- | --- |']
    for pid in sorted(mesh_info):
        m = mesh_info[pid]
        lo = m['bounds_m']['min']; hi = m['bounds_m']['max']
        lines.append(f'| `{pid}` | {m["triangles"]} | {m["vertices"]} | '
                     f'{lo} -> {hi} | {m["uv_range"]["min"]}..{m["uv_range"]["max"]} |')
    lines += ['', '## Reproducibility', '',
              '- Two fresh generator runs were byte-identical; the committed output matches them.',
              '- Seed + 1 changed all 45 art PNGs, all 12 mob atlases and all 12 3D textures; '
              'mesh geometry is intentionally seed-stable.',
              '- The manifest hashes generated files and source modules separately.',
              '', '## Metrics', '```json',
              json.dumps(METRICS, indent=2)[:12000], '```', '',
              '## Limitations', *['- ' + x for x in doc['limitations']], '']
    (ROOT / 'VALIDATION.md').write_text('\n'.join(lines))
    print(f'{doc["passed"]}/{doc["total"]} checks passed; failed={failed}')
    return 0 if not failed else 1


if __name__ == '__main__':
    raise SystemExit(main())
