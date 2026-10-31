#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Independent checks for the six Null Run signature mob designs.

The checks are structural: atlas layout, padding, grounding, animation change,
silhouette separation, schema and deterministic regeneration.  They do not
replace visual review or native frame mapping.  Run:

    PYTHONDONTWRITEBYTECODE=1 python mob_checks.py

Only mob-checks.json is written.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
DEFAULT_SEED = 20261031
SET_IDS = ('drowned_records', 'switchyard_chapel', 'after_hours_pavilion')
SLOTS = ('latchwing', 'relay_choir')
STATES = ('idle', 'walk', 'warning', 'attack', 'hurt', 'death')
COLS, ROWS, SIZE = 4, 6, 128
EXPECTED_IDS = {
    'drowned_records': {'latchwing': 'shelf_widow', 'relay_choir': 'redacted_choir'},
    'switchyard_chapel': {'latchwing': 'insulator_widow', 'relay_choir': 'transformer_cantor'},
    'after_hours_pavilion': {'latchwing': 'queue_stalker', 'relay_choir': 'usher_cluster'},
}
CHECKS = []
METRICS = {}


def add(cid, ok, detail, **extra):
    entry = {'id': cid, 'pass': bool(ok), 'detail': detail}
    entry.update(extra)
    CHECKS.append(entry)
    return bool(ok)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def expected_atlas_paths():
    return [Path('mobs') / sid / f'{slot}_{variant}.png'
            for sid in SET_IDS for slot in SLOTS for variant in ('A', 'B')]


def expected_sheet_paths():
    return [Path('sheets') / f'{sid}-mobs.png' for sid in SET_IDS] + [
        Path('sheets') / 'drowned-records-creepy.png']


def cells_from_atlas(path):
    image = Image.open(path)
    image.load()
    if image.size != (COLS * SIZE, ROWS * SIZE) or image.mode != 'RGBA':
        raise ValueError(f'{path}: expected 512x768 RGBA')
    arr = np.asarray(image, dtype=np.uint8)
    cells = {}
    for row, state in enumerate(STATES):
        for col in range(COLS):
            cell = arr[row * SIZE:(row + 1) * SIZE,
                       col * SIZE:(col + 1) * SIZE]
            cells[(state, col)] = cell
    return image, arr, cells


def bbox(alpha):
    ys, xs = np.where(alpha > 0)
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def iou(a, b):
    union = int((a | b).sum())
    return float((a & b).sum()) / union if union else 1.0


def check_layout():
    actual = sorted((ROOT / 'mobs').rglob('*.png'))
    expected = expected_atlas_paths()
    rel_actual = [p.relative_to(ROOT) for p in actual]
    missing = [p.as_posix() for p in expected if p not in rel_actual]
    extra = [p.as_posix() for p in rel_actual if p not in expected]
    add('atlases_12', len(actual) == 12 and not missing and not extra,
        f'{len(actual)} atlases; missing={missing}; extra={extra}')
    sheets = expected_sheet_paths()
    sheet_missing = [p.as_posix() for p in sheets if not (ROOT / p).is_file()]
    add('sheets_4', not sheet_missing,
        f'{len(sheets) - len(sheet_missing)}/4 mob sheets present; missing={sheet_missing}')
    add('encounters_present', (ROOT / 'encounters.json').is_file(),
        'encounters.json exists')


def check_atlas_geometry():
    problems = []
    all_cells = {}
    atlas_info = {}
    for rel in expected_atlas_paths():
        try:
            image, arr, cells = cells_from_atlas(ROOT / rel)
        except Exception as exc:  # noqa: BLE001
            problems.append(str(exc))
            continue
        all_cells[rel.as_posix()] = cells
        atlas_info[rel.as_posix()] = {'width': image.width, 'height': image.height,
                                      'mode': image.mode, 'cells': len(cells)}
        if len(cells) != 24:
            problems.append(f'{rel}: {len(cells)} cells')
        if set(np.unique(arr[:, :, 3]).tolist()) - {0, 255}:
            problems.append(f'{rel}: semi-transparent alpha')
    add('atlas_layout_512x768_rgba_24', not problems,
        '12 atlases x 24 cells = 288 frames; 512x768 RGBA; crisp 0/255 alpha'
        if not problems else '; '.join(problems[:8]), atlases=atlas_info)
    return all_cells


def check_cells(all_cells):
    problems = []
    bboxes = {}
    coverage = {}
    centers = {}
    for key, cells in all_cells.items():
        for (state, col), cell in cells.items():
            alpha = cell[:, :, 3]
            bb = bbox(alpha)
            if bb is None:
                problems.append(f'{key} {state} {col}: blank')
                continue
            x0, y0, x1, y1 = bb
            cov = float((alpha > 0).mean())
            bboxes[(key, state, col)] = bb
            coverage[(key, state, col)] = cov
            centers[(key, state, col)] = (x0 + x1) / 2
            if x0 < 3 or y0 < 3 or x1 > 124 or y1 > 124:
                problems.append(f'{key} {state} {col}: padding {bb}')
            if abs(y1 - 120) > 1:
                problems.append(f'{key} {state} {col}: floor anchor y={y1}')
            if not (0.01 <= cov <= 0.80):
                problems.append(f'{key} {state} {col}: coverage {cov:.2f}')
            if cell[0, 0, 3] or cell[0, -1, 3] or cell[-1, 0, 3] or cell[-1, -1, 3]:
                problems.append(f'{key} {state} {col}: opaque corner')
    add('padding_alpha_grounding', not problems,
        'every frame has >=3 px transparent padding, a y=120 floor anchor and no opaque backdrop'
        if not problems else '; '.join(problems[:10]), problems=problems[:30])

    # stable grounding and horizontal body anchor per atlas
    anchor_problems = []
    for key, cells in all_cells.items():
        bottoms = []
        xs = []
        for (state, col), cell in cells.items():
            bb = bbox(cell[:, :, 3])
            if bb:
                bottoms.append(bb[3])
                xs.append((bb[0] + bb[2]) / 2)
        if not bottoms or max(bottoms) - min(bottoms) > 1:
            anchor_problems.append(f'{key}: foot bottoms {sorted(set(bottoms))}')
        if not xs or max(abs(x - 64) for x in xs) > 12:
            anchor_problems.append(f'{key}: body centre range {min(xs):.1f}..{max(xs):.1f}')
    add('stable_body_feet_anchors', not anchor_problems,
        'foot baseline y=120 throughout and body centres stay within 12 px of x=64'
        if not anchor_problems else '; '.join(anchor_problems[:8]))

    # final death corpse visibility
    corpse = []
    for key, cells in all_cells.items():
        cell = cells[('death', 3)]
        bb = bbox(cell[:, :, 3])
        cov = float((cell[:, :, 3] > 0).mean())
        if bb is None or (bb[2] - bb[0]) < 24 or (bb[3] - bb[1]) < 10 or cov < 0.02:
            corpse.append(f'{key}: corpse bbox={bb} coverage={cov:.3f}')
    add('final_death_corpse_visible', not corpse,
        'all 12 final death frames contain a visible, non-blank corpse'
        if not corpse else '; '.join(corpse), problems=corpse)


def check_animation(all_cells):
    problems = []
    min_diff = 10 ** 9
    unique_rows = {}
    for key, cells in all_cells.items():
        hashes = {hashlib.sha256(cell.tobytes()).hexdigest()
                  for cell in cells.values()}
        unique_rows[key] = len(hashes)
        if len(hashes) < 20:
            problems.append(f'{key}: only {len(hashes)}/24 unique cells')
        for state in STATES:
            state_hashes = {hashlib.sha256(cells[(state, col)].tobytes()).hexdigest()
                            for col in range(COLS)}
            if len(state_hashes) < 2:
                problems.append(f'{key} {state}: all four frames identical')
            for col in range(COLS - 1):
                a = cells[(state, col)]
                b = cells[(state, col + 1)]
                diff = int((a != b).any(axis=2).sum())
                min_diff = min(min_diff, diff)
                if diff < 100:
                    problems.append(f'{key} {state} {col}->{col + 1}: only {diff} changed pixels')
    METRICS['animation'] = {'min_consecutive_changed_pixels': int(min_diff),
                            'unique_cells_per_atlas': unique_rows}
    add('genuine_frame_animation', not problems,
        f'every consecutive frame pair changes >=100 pixels; minimum {min_diff}; '
        f'{min(unique_rows.values())}-{max(unique_rows.values())} unique cells per atlas'
        if not problems else '; '.join(problems[:10]))


def check_silhouettes(all_cells):
    idle = {key: cells[('idle', 0)][:, :, 3] > 0 for key, cells in all_cells.items()}
    ab_rows = []
    ab_problems = []
    for sid in SET_IDS:
        for slot in SLOTS:
            a = idle[f'mobs/{sid}/{slot}_A.png']
            b = idle[f'mobs/{sid}/{slot}_B.png']
            v = iou(a, b)
            ab_rows.append((sid, slot, round(v, 3)))
            if v > 0.90:
                ab_problems.append(f'{sid} {slot}: A/B silhouette IoU {v:.3f}')
    designs = [(sid, slot) for sid in SET_IDS for slot in SLOTS]
    cross_rows = []
    cross_values = []
    for (a_sid, a_slot), (b_sid, b_slot) in itertools.combinations(designs, 2):
        a = idle[f'mobs/{a_sid}/{a_slot}_A.png']
        b = idle[f'mobs/{b_sid}/{b_slot}_A.png']
        v = iou(a, b)
        cross_values.append(v)
        cross_rows.append((a_sid, a_slot, b_sid, b_slot, round(v, 3)))
    max_cross = max(cross_values) if cross_values else 1.0
    METRICS['silhouettes'] = {'a_b_iou': ab_rows, 'cross_design_iou': cross_rows,
                              'cross_design_max': round(max_cross, 3)}
    ok = not ab_problems and max_cross < 0.75
    add('silhouette_differences', ok,
        f'A/B max IoU {max(v for _, _, v in ab_rows):.3f}; '
        f'cross-design max IoU {max_cross:.3f} (idle frame 0)'
        if ok else '; '.join(ab_problems) + f'; cross max {max_cross:.3f}')


def check_encounters():
    doc = json.loads((ROOT / 'encounters.json').read_text(encoding='utf-8'))
    problems = []
    if doc.get('format') != 'nullrun-environment-mobs-1':
        problems.append('format')
    if doc.get('source_seed') != DEFAULT_SEED:
        problems.append(f'source_seed={doc.get("source_seed")}')
    sets = doc.get('sets')
    if not isinstance(sets, dict) or set(sets) != set(SET_IDS):
        problems.append('sets keys')
        sets = {}
    ids = []
    names = []
    for sid in SET_IDS:
        entry = sets.get(sid, {})
        if set(entry) != set(SLOTS):
            problems.append(f'{sid}: slot keys {sorted(entry)}')
            continue
        for slot in SLOTS:
            mob = entry[slot]
            for field in ('id', 'name', 'description', 'behavior_family',
                          'warning_notes', 'limits'):
                if not isinstance(mob.get(field), str) or not mob[field]:
                    problems.append(f'{sid}/{slot}: {field}')
            if mob.get('behavior_family') != slot:
                problems.append(f'{sid}/{slot}: behavior_family={mob.get("behavior_family")}')
            if mob.get('id') != EXPECTED_IDS[sid][slot]:
                problems.append(f'{sid}/{slot}: id={mob.get("id")}')
            if mob.get('name') != mob.get('name', '').upper():
                problems.append(f'{sid}/{slot}: display name not uppercase')
            limits = mob.get('limits', '').lower()
            if 'existing' not in limits or 'no new ai' not in limits:
                problems.append(f'{sid}/{slot}: limits lacks existing/no-new-AI wording')
            if slot not in limits:
                problems.append(f'{sid}/{slot}: limits does not name the behavior family')
            ids.append(mob.get('id'))
            names.append(mob.get('name'))
    if len(ids) != 6 or len(set(ids)) != 6:
        problems.append(f'identities not six unique ids: {ids}')
    if len(names) != 6 or len(set(names)) != 6:
        problems.append(f'identities not six unique names: {names}')
    add('encounters_schema', not problems,
        'three sets x two slots; six unique identities; exact behavior_family names; honest limits'
        if not problems else '; '.join(problems[:10]), problems=problems[:30])


def check_sheets():
    problems = []
    rows = {}
    for rel in expected_sheet_paths():
        path = ROOT / rel
        image = Image.open(path)
        image.load()
        rows[rel.as_posix()] = [image.width, image.height, image.mode]
        if image.mode != 'RGB':
            problems.append(f'{rel}: mode {image.mode}')
        if 'creepy' in rel.name:
            if image.width < 1000 or image.height < 1200:
                problems.append(f'{rel}: small {image.size}')
        elif image.width < 1100 or image.height < 1700:
            problems.append(f'{rel}: small {image.size}')
        if np.asarray(image.convert('L'), dtype=float).std() < 4:
            problems.append(f'{rel}: blank')
    add('mob_sheets_present', not problems,
        'three full-atlas mob sheets and one larger creepy detail board'
        if not problems else '; '.join(problems), sheets=rows)


def check_size():
    atlas_sizes = [int((ROOT / p).stat().st_size) for p in expected_atlas_paths()]
    sheet_sizes = [int((ROOT / p).stat().st_size) for p in expected_sheet_paths()]
    total = sum(atlas_sizes) + sum(sheet_sizes) + int((ROOT / 'encounters.json').stat().st_size)
    METRICS['sizes'] = {'atlas_total_bytes': sum(atlas_sizes),
                        'atlas_max_bytes': max(atlas_sizes),
                        'sheet_total_bytes': sum(sheet_sizes),
                        'mob_total_bytes': total}
    ok = (sum(atlas_sizes) <= 8_000_000 and max(atlas_sizes) <= 600_000
          and sum(sheet_sizes) <= 8_000_000 and total <= 16_000_000)
    add('bounded_mob_output_size', ok,
        f'atlases={sum(atlas_sizes)} B (max {max(atlas_sizes)}); '
        f'sheets={sum(sheet_sizes)} B; total={total} B')


def _run(out, seed):
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    start = time.perf_counter()
    result = subprocess.run([sys.executable, str(ROOT / 'mob_art.py'),
                             '--out', str(out), '--seed', str(seed)],
                            cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    return time.perf_counter() - start


def _files(root):
    return sorted((p.relative_to(root) for p in Path(root).rglob('*') if p.is_file()),
                  key=lambda p: p.as_posix())


def check_reproducibility():
    try:
        with tempfile.TemporaryDirectory(dir=ROOT, prefix='.mob-check-a-') as ta, \
                tempfile.TemporaryDirectory(dir=ROOT, prefix='.mob-check-b-') as tb:
            elapsed_a = _run(ta, DEFAULT_SEED)
            elapsed_b = _run(tb, DEFAULT_SEED)
            fa, fb = _files(ta), _files(tb)
            problems = []
            if fa != fb:
                problems.append('generated file lists differ')
            diff = [p.as_posix() for p in fa if sha(Path(ta) / p) != sha(Path(tb) / p)]
            if diff:
                problems.append(f'two fresh folders differ: {diff[:5]}')
            committed = [p.as_posix() for p in fa
                         if (ROOT / p).is_file() and sha(ROOT / p) != sha(Path(ta) / p)]
            if committed:
                problems.append(f'committed output differs: {committed[:5]}')
            METRICS['reproducibility'] = {
                'files_compared': len(fa),
                'differences_between_fresh_folders': diff,
                'differences_from_committed': committed,
                'generation_seconds_first': round(elapsed_a, 3),
                'generation_seconds_second': round(elapsed_b, 3),
            }
            add('reproducible_same_seed', not problems,
                f'{len(fa)} files (12 atlases, 288 frames) identical in two fresh folders '
                f'and match the committed output; generation {elapsed_a:.2f}s'
                if not problems else '; '.join(problems))
    except Exception as exc:  # noqa: BLE001
        add('reproducible_same_seed', False, f'reproducibility run failed: {exc}')


def check_seed_sensitivity():
    try:
        with tempfile.TemporaryDirectory(dir=ROOT, prefix='.mob-check-c-') as tc:
            _run(tc, DEFAULT_SEED + 1)
            diff = [p.as_posix() for p in expected_atlas_paths()
                    if sha(ROOT / p) != sha(Path(tc) / p)]
            doc = json.loads((Path(tc) / 'encounters.json').read_text(encoding='utf-8'))
            ok = len(diff) >= 10 and doc.get('source_seed') == DEFAULT_SEED + 1
            add('seed_affects_mobs', ok,
                f'{len(diff)}/12 atlases change at seed {DEFAULT_SEED + 1}; '
                f'encounters source_seed={doc.get("source_seed")}')
    except Exception as exc:  # noqa: BLE001
        add('seed_affects_mobs', False, f'seed run failed: {exc}')


def main():
    check_layout()
    all_cells = check_atlas_geometry()
    if all_cells:
        check_cells(all_cells)
        check_animation(all_cells)
        check_silhouettes(all_cells)
    check_encounters()
    check_sheets()
    check_size()
    check_reproducibility()
    check_seed_sensitivity()

    failed = [c['id'] for c in CHECKS if not c['pass']]
    atlas_hashes = [sha(ROOT / p) for p in expected_atlas_paths()]
    bundle = hashlib.sha256(''.join(sorted(atlas_hashes)).encode()).hexdigest()
    doc = {
        'format': 'nullrun-environment-mob-checks-1',
        'source_seed': DEFAULT_SEED,
        'atlases': 12,
        'frames': 288,
        'atlas_bundle_sha256': bundle,
        'passed': not failed,
        'failed': failed,
        'checks': CHECKS,
        'metrics': METRICS,
        'notes': [
            'Structural checks only; warning/attack readability and visual quality are not proved by scores.',
            'The A/B variants differ in silhouette and detail, not merely hue; the checks measure alpha-mask IoU.',
            'Six identities use the existing latchwing and relay_choir behavior families unchanged.',
            'No actor IDs, AI, native frame mapping, gameplay or audio were implemented or tested here.',
            'Codex owns native integration, frame mapping and visual acceptance.',
        ],
    }
    (ROOT / 'mob-checks.json').write_text(json.dumps(doc, indent=2) + '\n', encoding='utf-8')
    print(f'mob checks: {len(CHECKS) - len(failed)}/{len(CHECKS)} passed; failed={failed}')
    print(f'atlas bundle sha256: {bundle}')
    for c in CHECKS:
        print(('PASS ' if c['pass'] else 'FAIL ') + c['id'] + ': ' + c['detail'])
    return 0 if not failed else 1


if __name__ == '__main__':
    raise SystemExit(main())
