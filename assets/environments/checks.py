#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Independent checks for the three Null Run environment kits.

These checks are structural and deterministic.  They do not replace visual
review or native-renderer acceptance.  Run:

    PYTHONDONTWRITEBYTECODE=1 python checks.py

The only file written is checks.json.  Reproducibility generations use
temporary directories inside this kit folder and remove them again.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent
DEFAULT_SEED = 20261031
KIT_FORMAT = 'nullrun-environment-kit-1'
CHECK_FORMAT = 'nullrun-environment-kit-checks-1'
SET_IDS = ('drowned_records', 'switchyard_chapel', 'after_hours_pavilion')
WALL_ROLES = ('primary wall', 'relief / panel', 'structural material',
              'service hardware', 'shutter / window', 'wayfinding / accent',
              'landmark A', 'landmark B')
FLAT_ROLES = ('primary floor', 'utility floor', 'ordinary ceiling', 'lit ceiling')
PROP_SLOTS = ('service_lamp', 'cable_shrine', 'directory_sign')
HEX_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')

CHECKS = []
METRICS = {}


def add(check_id, ok, detail, **extra):
    entry = {'id': check_id, 'pass': bool(ok), 'detail': detail}
    entry.update(extra)
    CHECKS.append(entry)
    return bool(ok)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_image(path):
    image = Image.open(path)
    image.load()
    return image


def rgb(path):
    return np.asarray(load_image(path).convert('RGB'), dtype=np.uint8)


def lum(path):
    return np.asarray(load_image(path).convert('L'), dtype=float)


def expected_art_paths():
    paths = []
    for sid in SET_IDS:
        for i in range(1, 9):
            paths.append(Path('art') / sid / 'walls' / f'{i:02d}.png')
        for i in range(1, 5):
            paths.append(Path('art') / sid / 'flats' / f'{i:02d}.png')
        for slot in PROP_SLOTS:
            paths.append(Path('art') / sid / 'props' / f'{slot}.png')
    return paths


def expected_sheet_paths():
    return [Path('sheets') / f'{sid}-{kind}.png' for sid in SET_IDS
            for kind in ('kit', 'tiling')]


def collect_project_files():
    """Source, metadata and generated files eligible for the manifest."""
    files = []
    for path in ROOT.rglob('*'):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        parts = rel.parts
        if any(part.startswith('.check-tmp-') or part == '__pycache__'
               or part.startswith('_scratch') for part in parts):
            continue
        if rel.as_posix() in ('manifest.json', 'checks.json'):
            continue
        if path.suffix.lower() not in ('.py', '.json', '.md', '.png'):
            continue
        files.append(rel)
    return sorted(files, key=lambda p: p.as_posix())


def hp_mask(path, crop):
    gray = load_image(path).convert('L')
    a = np.asarray(gray.crop(crop), dtype=float)
    b = np.asarray(gray.filter(ImageFilter.GaussianBlur(2.2)).crop(crop), dtype=float)
    hp = np.abs(a - b)
    threshold = max(3.0, float(np.percentile(hp, 70)))
    return hp > threshold


def iou(a, b):
    union = int((a | b).sum())
    return float((a & b).sum()) / union if union else 1.0


# -- checks ------------------------------------------------------------------
def check_layout():
    art_files = sorted((ROOT / 'art').rglob('*.png'))
    expected = expected_art_paths()
    actual = [p.relative_to(ROOT) for p in art_files]
    missing = [p.as_posix() for p in expected if p not in actual]
    extra = [p.as_posix() for p in actual if p not in expected]
    add('art_count_45', len(art_files) == 45 and not missing and not extra,
        f'{len(art_files)} art PNGs; missing={missing}; extra={extra}',
        count=len(art_files), missing=missing, extra=extra)

    sheets = sorted((ROOT / 'sheets').glob('*.png'))
    sheet_expected = expected_sheet_paths()
    sheet_actual = [p.relative_to(ROOT) for p in sheets]
    sheet_missing = [p.as_posix() for p in sheet_expected if p not in sheet_actual]
    sheet_extra = [p.as_posix() for p in sheet_actual if p not in sheet_expected]
    add('sheet_count_6', len(sheets) == 6 and not sheet_missing and not sheet_extra,
        f'{len(sheets)} sheet PNGs; missing={sheet_missing}; extra={sheet_extra}',
        count=len(sheets))
    add('environments_json_present', (ROOT / 'environments.json').is_file(),
        'environments.json exists' if (ROOT / 'environments.json').is_file()
        else 'environments.json missing')


def check_modes():
    problems = []
    for rel in expected_art_paths():
        im = load_image(ROOT / rel)
        want = (96, 128, 'RGBA') if 'props' in rel.parts else (
            (64, 64, 'RGB') if 'flats' in rel.parts else (128, 128, 'RGB'))
        got = (im.width, im.height, im.mode)
        if got != want:
            problems.append(f'{rel}: {got} != {want}')
    add('dimensions_and_modes', not problems,
        'all 45 art files have the expected size and mode' if not problems
        else '; '.join(problems[:8]), problems=problems[:20])


def check_nonblank_distinct():
    hashes = {}
    problems = []
    for rel in expected_art_paths():
        hashes.setdefault(sha256(ROOT / rel), []).append(rel.as_posix())
    dupes = [v for v in hashes.values() if len(v) > 1]
    add('unique_assets', not dupes, f'{len(hashes)} unique SHA256 values for 45 files',
        duplicates=dupes)

    weak = []
    for sid in SET_IDS:
        for kind in ('walls', 'flats'):
            for i in range(1, 9 if kind == 'walls' else 5):
                p = ROOT / 'art' / sid / kind / f'{i:02d}.png'
                a = rgb(p)
                g = np.asarray(load_image(p).convert('L'), dtype=float)
                unique = len(np.unique(a.reshape(-1, 3), axis=0))
                spread = float(np.percentile(g, 95) - np.percentile(g, 5))
                if unique < 12 or g.std() < 5 or spread < 25:
                    weak.append(f'{p.relative_to(ROOT)} unique={unique} std={g.std():.1f} spread={spread:.1f}')
        for slot in PROP_SLOTS:
            p = ROOT / 'art' / sid / 'props' / f'{slot}.png'
            a = np.asarray(load_image(p), dtype=np.uint8)
            alpha = a[:, :, 3]
            opaque = alpha > 0
            g = np.asarray(load_image(p).convert('L'), dtype=float)[opaque]
            unique = len(np.unique(a.reshape(-1, 4), axis=0))
            coverage = float(opaque.mean())
            spread = float(np.percentile(g, 95) - np.percentile(g, 5))
            if unique < 16 or spread < 35 or not (0.05 <= coverage <= 0.75):
                weak.append(f'{p.relative_to(ROOT)} unique={unique} spread={spread:.1f} coverage={coverage:.2f}')
    add('nonblank_contrast', not weak,
        'all assets are nonblank and meet the documented contrast floor' if not weak
        else '; '.join(weak[:8]), weak=weak)


def check_prop_alpha():
    problems = []
    for sid in SET_IDS:
        for slot in PROP_SLOTS:
            p = ROOT / 'art' / sid / 'props' / f'{slot}.png'
            a = np.asarray(load_image(p), dtype=np.uint8)
            alpha = a[:, :, 3]
            ys, xs = np.where(alpha > 0)
            if not len(xs):
                problems.append(f'{p.relative_to(ROOT)}: no opaque pixels')
                continue
            x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
            coverage = float((alpha > 0).mean())
            bbox_area = (x1 - x0 + 1) * (y1 - y0 + 1)
            inside_transparent = int((alpha[y0:y1 + 1, x0:x1 + 1] == 0).sum())
            corners = [int(alpha[0, 0]), int(alpha[0, -1]), int(alpha[-1, 0]), int(alpha[-1, -1])]
            if (x0 < 3 or y0 < 3 or x1 > 92 or y1 > 124 or y1 < 121
                    or (x1 - x0 + 1) < 20 or (y1 - y0 + 1) < 40):
                problems.append(f'{p.relative_to(ROOT)}: bbox={x0},{y0},{x1},{y1}')
            if any(corners) or coverage > 0.75:
                problems.append(f'{p.relative_to(ROOT)}: corners={corners} coverage={coverage:.2f}')
            if inside_transparent < bbox_area * 0.08:
                problems.append(f'{p.relative_to(ROOT)}: opaque rectangular backdrop suspected')
            if int(alpha[0].max()) or int(alpha[-1].max()) or int(alpha[:, 0].max()) or int(alpha[:, -1].max()):
                problems.append(f'{p.relative_to(ROOT)}: edge pixel is not transparent')
    add('prop_alpha_padding_anchor', not problems,
        'all props are transparent cut-outs with >=3 px margins and bottom-anchored bases'
        if not problems else '; '.join(problems[:8]), problems=problems[:20])


def check_seams():
    problems = []
    seam_rows = []
    for rel in expected_art_paths():
        if 'props' in rel.parts:
            continue
        a = rgb(ROOT / rel)
        vertical = bool(np.array_equal(a[0, :, :], a[-1, :, :]))
        horizontal = bool(np.array_equal(a[:, 0, :], a[:, -1, :]))
        seam_rows.append({'file': rel.as_posix(), 'top_bottom_equal': vertical,
                          'left_right_equal': horizontal})
        if not (vertical and horizontal):
            problems.append(rel.as_posix())
    add('seam_exact_edges', not problems,
        'opposite edge rows and columns match exactly for all 36 wall/flat images'
        if not problems else f'seam failures: {problems}', seams=seam_rows)

    doc = json.loads((ROOT / 'environments.json').read_text(encoding='utf-8'))
    declaration = doc.get('seam_behavior', {})
    ok = all(isinstance(declaration.get(k), str) and declaration.get(k)
             for k in ('walls', 'flats', 'props'))
    ok = ok and 'both axes' in declaration.get('walls', '') and 'both axes' in declaration.get('flats', '')
    ok = ok and all(isinstance(s.get('seam_behavior'), dict) for s in doc.get('sets', []))
    add('seam_behavior_documented', ok,
        'environments.json declares wall, flat and prop seam behaviour per set')


def check_floor_ceiling():
    rows = {}
    problems = []
    for sid in SET_IDS:
        means = [float(lum(ROOT / 'art' / sid / 'flats' / f'{i:02d}.png').mean())
                 for i in range(1, 5)]
        floor_mean = (means[0] + means[1]) / 2
        ceiling_mean = (means[2] + means[3]) / 2
        a4 = lum(ROOT / 'art' / sid / 'flats' / '04.png')
        bright = float((a4 >= 210).mean())
        rows[sid] = {'floor_mean': round(floor_mean, 2),
                     'ceiling_mean': round(ceiling_mean, 2),
                     'difference': round(ceiling_mean - floor_mean, 2),
                     'flat04_bright_fraction': round(bright, 4)}
        if ceiling_mean - floor_mean < 12:
            problems.append(f'{sid}: ceiling-floor luminance difference {ceiling_mean - floor_mean:.1f}')
        if bright < 0.02 or float(a4.max()) < 200:
            problems.append(f'{sid}: flat 04 fixture is too dim (bright={bright:.3f})')
    METRICS['floor_ceiling'] = rows
    add('floor_ceiling_distinction', not problems,
        'each set has darker floors than ceilings and a lit ceiling with static fixture pixels'
        if not problems else '; '.join(problems), rows=rows)


def check_wall_hierarchy():
    rows = {}
    problems = []
    for sid in SET_IDS:
        means = [float(lum(ROOT / 'art' / sid / 'walls' / f'{i:02d}.png').mean())
                 for i in range(1, 7)]
        rows[sid] = {'min': round(min(means), 1), 'max': round(max(means), 1),
                     'range': round(max(means) - min(means), 1),
                     'means': [round(v, 1) for v in means]}
        if min(means) > 115 or max(means) < 145 or max(means) - min(means) < 35:
            problems.append(f'{sid}: min={min(means):.1f} max={max(means):.1f}')
    METRICS['wall_hierarchy'] = rows
    add('wall_bright_dark_hierarchy', not problems,
        'each base wall set includes dark and bright material roles'
        if not problems else '; '.join(problems), rows=rows)


def check_inter_set():
    wall_masks = {sid: [hp_mask(ROOT / 'art' / sid / 'walls' / f'{i:02d}.png',
                                (4, 4, 124, 124)) for i in range(1, 9)]
                  for sid in SET_IDS}
    flat_masks = {sid: [hp_mask(ROOT / 'art' / sid / 'flats' / f'{i:02d}.png',
                                (3, 3, 61, 61)) for i in range(1, 5)]
                  for sid in SET_IDS}
    wall_rows = {}
    flat_rows = {}
    wall_values = []
    flat_values = []
    for a, b in itertools.combinations(SET_IDS, 2):
        wv = [iou(wall_masks[a][i], wall_masks[b][i]) for i in range(8)]
        fv = [iou(flat_masks[a][i], flat_masks[b][i]) for i in range(4)]
        wall_rows[f'{a}__{b}'] = [round(v, 3) for v in wv]
        flat_rows[f'{a}__{b}'] = [round(v, 3) for v in fv]
        wall_values.extend(wv)
        flat_values.extend(fv)
    prop_rows = {}
    prop_values = []
    for slot in PROP_SLOTS:
        prop_rows[slot] = {}
        for a, b in itertools.combinations(SET_IDS, 2):
            ma = np.asarray(load_image(ROOT / 'art' / a / 'props' / f'{slot}.png'))[:, :, 3] > 0
            mb = np.asarray(load_image(ROOT / 'art' / b / 'props' / f'{slot}.png'))[:, :, 3] > 0
            v = iou(ma, mb)
            prop_rows[slot][f'{a}__{b}'] = round(v, 3)
            prop_values.append(v)
    wall_mean = float(np.mean(wall_values))
    wall_max = float(np.max(wall_values))
    flat_mean = float(np.mean(flat_values))
    flat_max = float(np.max(flat_values))
    prop_mean = float(np.mean(prop_values))
    prop_max = float(np.max(prop_values))
    METRICS['inter_set_structure'] = {
        'wall_same_index_iou': wall_rows, 'wall_mean': round(wall_mean, 3),
        'wall_max': round(wall_max, 3),
        'flat_same_index_iou': flat_rows, 'flat_mean': round(flat_mean, 3),
        'flat_max': round(flat_max, 3),
        'prop_alpha_iou': prop_rows, 'prop_mean': round(prop_mean, 3),
        'prop_max': round(prop_max, 3),
        'method': ('high-pass geometric masks exclude the shared 3-4 px edge frame; '
                   'a pure recolor or identical silhouette would score near 1.0'),
    }
    ok = (wall_mean <= 0.55 and wall_max <= 0.80 and flat_mean <= 0.60
          and flat_max <= 0.85 and prop_mean <= 0.65 and prop_max <= 0.85)
    add('inter_set_difference_beyond_recolor', ok,
        f'wall mean/max={wall_mean:.3f}/{wall_max:.3f}; '
        f'flat mean/max={flat_mean:.3f}/{flat_max:.3f}; '
        f'prop mean/max={prop_mean:.3f}/{prop_max:.3f}', metrics=METRICS['inter_set_structure'])

    display = []
    doc = json.loads((ROOT / 'environments.json').read_text(encoding='utf-8'))
    for slot in PROP_SLOTS:
        names = [s['props'][slot]['display_name'] for s in doc['sets']]
        display.append(len(set(names)) == 3)
    add('distinct_prop_fiction', all(display),
        'all three sets give each native prop slot a different display_name')


def check_metadata():
    doc = json.loads((ROOT / 'environments.json').read_text(encoding='utf-8'))
    problems = []
    if doc.get('format') != KIT_FORMAT:
        problems.append('format')
    if doc.get('source_seed') != DEFAULT_SEED:
        problems.append(f'source_seed={doc.get("source_seed")}')
    if doc.get('license') != 'GPL-2.0-or-later':
        problems.append('license')
    sets = doc.get('sets')
    if not isinstance(sets, list) or len(sets) != 3:
        problems.append('sets length')
        sets = []
    ids = [s.get('id') for s in sets]
    if set(ids) != set(SET_IDS):
        problems.append(f'ids={ids}')
    names = [s.get('name') for s in sets]
    if len(set(names)) != 3:
        problems.append('set names not distinct')
    for s in sets:
        sid = s.get('id')
        if not isinstance(s.get('palette'), dict) or len(s['palette']) < 8:
            problems.append(f'{sid}: palette')
        else:
            for name, value in s['palette'].items():
                if not isinstance(value, str) or not HEX_RE.match(value):
                    problems.append(f'{sid}: palette {name}={value}')
        landmark = s.get('landmark', {})
        if not landmark.get('name') or not landmark.get('description'):
            problems.append(f'{sid}: landmark text')
        if landmark.get('walls') != [7, 8]:
            problems.append(f'{sid}: landmark walls={landmark.get("walls")}')
        if not set(s.get('props', {})) == set(PROP_SLOTS):
            problems.append(f'{sid}: prop keys')
        else:
            for slot in PROP_SLOTS:
                if not s['props'][slot].get('display_name') or not s['props'][slot].get('description'):
                    problems.append(f'{sid}: prop {slot} text')
        notes = s.get('gameplay_notes', '').lower()
        if 'cosmetic' not in notes or 'no ' not in notes:
            problems.append(f'{sid}: gameplay notes lack cosmetic/no-mechanics wording')
        if not isinstance(s.get('seam_behavior'), dict):
            problems.append(f'{sid}: seam behaviour')
    if not isinstance(doc.get('selection', {}).get('notes'), str):
        problems.append('selection notes')
    if not isinstance(doc.get('floor_variation', {}).get('notes'), str):
        problems.append('floor variation notes')
    paths = doc.get('paths', {})
    for key, value in (('wall', 'art/{set_id}/walls/{index:02d}.png'),
                       ('flat', 'art/{set_id}/flats/{index:02d}.png'),
                       ('prop', 'art/{set_id}/props/{slot}.png')):
        if paths.get(key) != value:
            problems.append(f'paths.{key}')
    add('environments_schema', not problems,
        'format, seed, three sets, palettes, landmarks, props and metadata paths are valid'
        if not problems else '; '.join(problems[:10]), problems=problems[:30])


def check_sheets():
    problems = []
    rows = {}
    for rel in expected_sheet_paths():
        p = ROOT / rel
        im = load_image(p)
        rows[rel.as_posix()] = [im.width, im.height, im.mode]
        if im.mode != 'RGB':
            problems.append(f'{rel}: mode {im.mode}')
        if 'kit' in rel.name and (im.width < 1000 or im.height < 1200):
            problems.append(f'{rel}: too small {im.size}')
        if 'tiling' in rel.name and (im.width < 1000 or im.height < 2000):
            problems.append(f'{rel}: too small {im.size}')
        if np.asarray(im.convert('L'), dtype=float).std() < 4:
            problems.append(f'{rel}: blank')
    add('sheets_present_and_sized', not problems,
        f'{len(rows)} readable contact/tiling sheets at the documented dimensions'
        if not problems else '; '.join(problems), sheets=rows)


def check_size():
    art_files = expected_art_paths()
    art_sizes = [int((ROOT / p).stat().st_size) for p in art_files]
    sheet_sizes = [int((ROOT / p).stat().st_size) for p in expected_sheet_paths()]
    all_png = art_sizes + sheet_sizes
    kit_bytes = sum(int(p.stat().st_size) for p in ROOT.rglob('*')
                    if p.is_file() and not any(part.startswith('.check-tmp-') or
                                               part == '__pycache__' or part.startswith('_scratch')
                                               for part in p.relative_to(ROOT).parts))
    METRICS['sizes'] = {
        'art_total_bytes': sum(art_sizes), 'art_max_bytes': max(art_sizes),
        'sheet_total_bytes': sum(sheet_sizes), 'kit_total_bytes': kit_bytes,
        'png_total_bytes': sum(all_png),
    }
    ok = (sum(art_sizes) <= 4_000_000 and max(art_sizes) <= 250_000
          and sum(sheet_sizes) <= 8_000_000 and kit_bytes <= 12_000_000)
    add('bounded_output_size', ok,
        f'art={sum(art_sizes)} B (max {max(art_sizes)}); sheets={sum(sheet_sizes)} B; '
        f'kit={kit_bytes} B', sizes=METRICS['sizes'])


def _run_generator(out, seed):
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    cmd = [sys.executable, str(ROOT / 'art.py'), '--out', str(out), '--seed', str(seed)]
    start = time.perf_counter()
    result = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
    elapsed = time.perf_counter() - start
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    return elapsed


def _generated_files(root):
    return sorted((p.relative_to(root) for p in Path(root).rglob('*') if p.is_file()),
                  key=lambda p: p.as_posix())


def check_reproducibility():
    try:
        with tempfile.TemporaryDirectory(dir=ROOT, prefix='.check-tmp-a-') as ta, \
                tempfile.TemporaryDirectory(dir=ROOT, prefix='.check-tmp-b-') as tb:
            elapsed_a = _run_generator(ta, DEFAULT_SEED)
            elapsed_b = _run_generator(tb, DEFAULT_SEED)
            files_a = _generated_files(ta)
            files_b = _generated_files(tb)
            problems = []
            if files_a != files_b:
                problems.append('generated file lists differ')
            diff_ab = [p.as_posix() for p in files_a
                       if sha256(Path(ta) / p) != sha256(Path(tb) / p)]
            if diff_ab:
                problems.append(f'two fresh folders differ: {diff_ab[:5]}')
            committed = []
            for p in files_a:
                target = ROOT / p
                if target.is_file() and sha256(target) != sha256(Path(ta) / p):
                    committed.append(p.as_posix())
            if committed:
                problems.append(f'committed output differs from regeneration: {committed[:5]}')
            pngs = [p for p in files_a if p.suffix == '.png']
            METRICS['reproducibility'] = {
                'files_compared': len(files_a), 'pngs_compared': len(pngs),
                'fresh_folder_differences': diff_ab,
                'committed_differences': committed,
                'generation_seconds_first': round(elapsed_a, 3),
                'generation_seconds_second': round(elapsed_b, 3),
            }
            add('reproducible_same_seed', not problems,
                f'{len(files_a)} files (45 art PNGs) identical in two fresh folders and '
                f'match the committed output; generation {elapsed_a:.2f}s'
                if not problems else '; '.join(problems),
                metrics=METRICS['reproducibility'])
    except Exception as exc:  # noqa: BLE001 - report the failure honestly
        add('reproducible_same_seed', False, f'reproducibility run failed: {exc}')


def check_seed_sensitivity():
    try:
        with tempfile.TemporaryDirectory(dir=ROOT, prefix='.check-tmp-c-') as tc:
            _run_generator(tc, DEFAULT_SEED + 1)
            source = [p for p in expected_art_paths()]
            diff = [p.as_posix() for p in source
                    if sha256(ROOT / p) != sha256(Path(tc) / p)]
            doc = json.loads((Path(tc) / 'environments.json').read_text(encoding='utf-8'))
            ok = len(diff) >= 40 and doc.get('source_seed') == DEFAULT_SEED + 1
            add('seed_affects_assets', ok,
                f'{len(diff)}/45 art PNGs change at seed {DEFAULT_SEED + 1}; '
                f'environments source_seed={doc.get("source_seed")}')
    except Exception as exc:  # noqa: BLE001
        add('seed_affects_assets', False, f'seed run failed: {exc}')


def check_manifest():
    path = ROOT / 'manifest.json'
    if not path.is_file():
        add('manifest_integrity', True, 'manifest.json not present yet; run make_manifest.py',
            skipped=True)
        return
    manifest = json.loads(path.read_text(encoding='utf-8'))
    problems = []
    if manifest.get('format') != 'nullrun-environment-kit-manifest-1':
        problems.append('manifest format')
    if manifest.get('source_seed') != DEFAULT_SEED:
        problems.append('manifest seed')
    files = manifest.get('files', {})
    expected = collect_project_files()
    expected_set = {p.as_posix() for p in expected}
    if set(files) != expected_set:
        missing = sorted(expected_set - set(files))
        extra = sorted(set(files) - expected_set)
        problems.append(f'manifest keys missing={missing[:5]} extra={extra[:5]}')
    for rel in expected:
        if rel.as_posix() in files and files[rel.as_posix()] != sha256(ROOT / rel):
            problems.append(f'hash mismatch {rel}')
    if 'manifest.json' in files or 'checks.json' in files:
        problems.append('manifest hashes itself or mutable checks.json')
    assets = manifest.get('assets', {})
    for rel in expected_art_paths():
        meta = assets.get(rel.as_posix(), {})
        im = load_image(ROOT / rel)
        want_seam = 'not_applicable' if 'props' in rel.parts else 'both_axes_exact'
        if (meta.get('width') != im.width or meta.get('height') != im.height
                or meta.get('mode') != im.mode or meta.get('seam') != want_seam):
            problems.append(f'asset metadata {rel}')
    if not isinstance(manifest.get('seam_requirements'), dict):
        problems.append('seam_requirements')
    add('manifest_integrity', not problems,
        f'{len(files)} files hashed and matching; {len(assets)} art entries carry '
        f'dimensions, mode and seam metadata' if not problems else '; '.join(problems[:10]),
        problems=problems[:20])


def main():
    started = time.perf_counter()
    check_layout()
    check_modes()
    check_nonblank_distinct()
    check_prop_alpha()
    check_seams()
    check_floor_ceiling()
    check_wall_hierarchy()
    check_inter_set()
    check_metadata()
    check_sheets()
    check_size()
    check_reproducibility()
    check_seed_sensitivity()
    check_manifest()

    failed = [c['id'] for c in CHECKS if not c['pass']]
    art_paths = expected_art_paths()
    bundle = hashlib.sha256(''.join(f'{p.as_posix()} {sha256(ROOT / p)}'
                                    for p in sorted(art_paths)).encode()).hexdigest()
    doc = {
        'format': CHECK_FORMAT,
        'source_seed': DEFAULT_SEED,
        'art_pngs': len(art_paths),
        'sheet_pngs': len(expected_sheet_paths()),
        'art_bundle_sha256': bundle,
        'passed': not failed,
        'failed': failed,
        'checks': CHECKS,
        'metrics': METRICS,
        'notes': [
            'These are structural and geometric checks. They do not prove visual quality.',
            'Visual acceptance is not claimed; Codex owns native integration and visual review.',
            'Structure metrics exclude the shared edge frame so they measure actual forms, not the kit frame.',
            'Assets have not been palette-quantised to the Doom PLAYPAL or rendered in the native game.',
            'The reproducibility check runs art.py twice in fresh folders inside this kit and removes them.',
        ],
        'visual_acceptance': 'not claimed; native renderer and human visual review are separate',
        'elapsed_seconds': round(time.perf_counter() - started, 3),
    }
    (ROOT / 'checks.json').write_text(json.dumps(doc, indent=2) + '\n', encoding='utf-8')
    print(f'checks: {len(CHECKS) - len(failed)}/{len(CHECKS)} passed; failed={failed}')
    print(f'art bundle sha256: {bundle}')
    for c in CHECKS:
        print(('PASS ' if c['pass'] else 'FAIL ') + c['id'] + ': ' + c['detail'])
    return 0 if not failed else 1


if __name__ == '__main__':
    raise SystemExit(main())
