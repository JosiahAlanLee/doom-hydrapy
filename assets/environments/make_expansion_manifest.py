#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Write expansion-manifest.json for the mob and score expansion.

Hashes the stable expansion sources, mob atlases/sheets, score note data,
patch plans and documentation.  The original 45-art manifest/check receipt are
referenced, not rewritten.  Mutable check receipts are recorded separately.

    PYTHONDONTWRITEBYTECODE=1 python make_expansion_manifest.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
SET_IDS = ('drowned_records', 'switchyard_chapel', 'after_hours_pavilion')
SLOTS = ('latchwing', 'relay_choir')
STATES = ('idle', 'walk', 'warning', 'attack', 'hurt', 'death')
EXCLUDED = [
    'expansion-manifest.json', 'expansion-checks.json', 'mob-checks.json',
    'music/*/checks.json', 'manifest.json', 'checks.json', '_scratch/**',
    '.mob-check-*/**', '.check-tmp-*/**', '__pycache__/**', '*.pyc',
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stable_files():
    files = [
        Path('mob_art.py'), Path('mob_checks.py'), Path('make_expansion_manifest.py'),
        Path('encounters.json'), Path('EXPANSION.md'),
        Path('music/common.py'), Path('music/check_music.py'),
        Path('music/catalogue.json'),
    ]
    files += sorted(Path('mobs').glob('*/*.png'))
    files += [Path('sheets') / f'{sid}-mobs.png' for sid in SET_IDS]
    files += [Path('sheets/drowned-records-creepy.png')]
    for sid in SET_IDS:
        for name in ('score.py', 'score.json', 'patch-plan.json', 'README.md'):
            files.append(Path('music') / sid / name)
    files = [p for p in files if (ROOT / p).is_file()]
    return sorted(set(files), key=lambda p: p.as_posix())


def asset_info(rel):
    with Image.open(ROOT / rel) as image:
        image.load()
        info = {'width': image.width, 'height': image.height, 'mode': image.mode}
    if rel.parts[0] == 'mobs':
        info.update(frames=24, cell='128x128', columns=4, rows=6,
                    states=list(STATES), layout='idle, walk, warning, attack, hurt, death',
                    anchor='bottom y=120; >=3 px transparent padding')
    else:
        info.update(kind='sheet', layout='checkerboard contact/detail')
    info['bytes'] = (ROOT / rel).stat().st_size
    return info


def receipt(path):
    if not (ROOT / path).is_file():
        return None
    return {'sha256': sha(ROOT / path), 'bytes': (ROOT / path).stat().st_size,
            'mutable_check_output': True}


def main():
    files = stable_files()
    hashes = {p.as_posix(): sha(p) for p in files}
    sizes = {p.as_posix(): int((ROOT / p).stat().st_size) for p in files}
    assets = {p.as_posix(): asset_info(p) for p in files if p.suffix == '.png'}

    scores = {}
    catalogue = json.loads((ROOT / 'music/catalogue.json').read_text(encoding='utf-8'))
    for sid in SET_IDS:
        entry = catalogue['sets'][sid]
        score_path = ROOT / entry['score']
        scores[sid] = {
            'score': entry['score'], 'bpm': entry['bpm'], 'seconds': entry['seconds'],
            'bars': entry['bars'], 'patterns': entry['patterns'], 'key': entry['key'],
            'sha256': sha(ROOT / score_path),
            'checks': entry['checks'], 'patch_plan': entry['patch_plan'],
        }

    original_manifest = ROOT / 'manifest.json'
    original_checks = ROOT / 'checks.json'
    original = {
        'manifest': 'manifest.json',
        'manifest_sha256': sha(original_manifest) if original_manifest.is_file() else None,
        'checks': 'checks.json',
        'checks_sha256': sha(original_checks) if original_checks.is_file() else None,
        'art_pngs': len(list((ROOT / 'art').rglob('*.png'))),
        'art_bundle_sha256': (json.loads(original_checks.read_text(encoding='utf-8')).get('art_bundle_sha256')
                              if original_checks.is_file() else None),
        'note': ('The original 45-art manifest/check receipt are preserved as the '
                 'record for the completed environment kit; they are not rewritten by this expansion.'),
    }
    receipts = {
        'mob-checks.json': receipt('mob-checks.json'),
        'expansion-checks.json': None,
    }
    for sid in SET_IDS:
        receipts[f'music/{sid}/checks.json'] = receipt(f'music/{sid}/checks.json')

    atlas_count = sum(1 for p in files if p.parts[0] == 'mobs')
    sheet_count = sum(1 for p in files if p.parts[0] == 'sheets')
    manifest = {
        'format': 'nullrun-environment-expansion-manifest-1',
        'title': ('Null Run environment expansion: six signature mobs and three '
                  'environment-keyed 120-second scores'),
        'license': 'GPL-2.0-or-later',
        'source_seed': 20261031,
        'credits': 'EXPANSION.md and the original CREDITS.md',
        'excluded': EXCLUDED,
        'totals': {
            'stable_files': len(files),
            'atlases': atlas_count,
            'frames': atlas_count * 24,
            'mob_sheets': sheet_count,
            'scores': len(scores),
            'bytes': sum(sizes.values()),
        },
        'layout': {
            'atlas': '512x768 RGBA, 4 columns x 6 rows, 128x128 cells, 24 cells',
            'mob_states': list(STATES),
            'props': 'no new actor IDs; six identities on two existing behavior families',
            'scores': 'hydrapy-tracker-3, 4/4, 16 rows/bar, rate 1, loop=False, exactly 120.000 s',
        },
        'files': hashes,
        'sizes': sizes,
        'assets': assets,
        'scores': scores,
        'check_receipts': receipts,
        'original_kit': original,
        'generation_commands': [
            'PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python mob_art.py --out .',
            'PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python mob_checks.py',
            'PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python music/drowned_records/score.py',
            'PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python music/switchyard_chapel/score.py',
            'PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python music/after_hours_pavilion/score.py',
            'PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python music/check_music.py',
            'PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python expansion_checks.py',
            'PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python make_expansion_manifest.py',
        ],
        'notes': [
            'Stable expansion sources, generated art, written scores and patch plans are hashed.',
            'mob-checks.json, music/*/checks.json and expansion-checks.json are mutable receipts and are not in the stable set.',
            'The original 45-art manifest/checks are referenced in original_kit and were not rewritten.',
            'No audio was rendered or auditioned; native frame mapping, Rack mapping and audio acceptance are Codex work.',
        ],
    }
    (ROOT / 'expansion-manifest.json').write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(f'wrote expansion-manifest.json: {len(files)} stable files, '
          f'{atlas_count} atlases, {atlas_count * 24} frames, {len(scores)} scores')


if __name__ == '__main__':
    main()
