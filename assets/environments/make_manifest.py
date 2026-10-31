#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Write manifest.json for the Null Run environment kit.

Every original source, metadata file and generated PNG is hashed, except this
manifest itself and the mutable check output checks.json.  Run after art.py,
checks.py and the documentation are final:

    PYTHONDONTWRITEBYTECODE=1 python make_manifest.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
DEFAULT_SEED = 20261031
WALL_ROLES = ('primary wall', 'relief / panel', 'structural material',
              'service hardware', 'shutter / window', 'wayfinding / accent',
              'landmark A', 'landmark B')
FLAT_ROLES = ('primary floor', 'utility floor', 'ordinary ceiling', 'lit ceiling')
PROP_SLOTS = ('service_lamp', 'cable_shrine', 'directory_sign')
SET_IDS = ('drowned_records', 'switchyard_chapel', 'after_hours_pavilion')
EXCLUDED = ['manifest.json', 'checks.json', '_scratch/**', '.check-tmp-*/**',
            '__pycache__/**', '*.pyc']


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def collect_files():
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


def asset_info(rel, image):
    text = rel.as_posix()
    info = {'width': image.width, 'height': image.height, 'mode': image.mode}
    parts = rel.parts
    if len(parts) >= 4 and parts[0] == 'art':
        set_id, kind = parts[1], parts[2]
        info['set'] = set_id
        info['kind'] = kind[:-1] if kind.endswith('s') else kind
        if kind == 'walls':
            info['role'] = WALL_ROLES[int(rel.stem) - 1]
            info['seam'] = 'both_axes_exact'
        elif kind == 'flats':
            info['role'] = FLAT_ROLES[int(rel.stem) - 1]
            info['seam'] = 'both_axes_exact'
        elif kind == 'props':
            info['role'] = rel.stem
            info['seam'] = 'not_applicable'
            info['alpha'] = 'transparent_margin_bottom_anchored'
        else:
            info['seam'] = 'not_applicable'
    elif len(parts) >= 2 and parts[0] == 'sheets':
        info['kind'] = 'sheet'
        info['role'] = rel.stem
        info['seam'] = 'not_applicable'
    else:
        info['kind'] = 'image'
        info['seam'] = 'not_applicable'
    info['bytes'] = rel.stat().st_size
    return info


def main():
    files = collect_files()
    hashes = {}
    sizes = {}
    assets = {}
    for rel in files:
        path = ROOT / rel
        hashes[rel.as_posix()] = sha256(path)
        sizes[rel.as_posix()] = path.stat().st_size
        if rel.suffix.lower() == '.png':
            with Image.open(path) as image:
                image.load()
                assets[rel.as_posix()] = asset_info(rel, image)

    art_count = sum(1 for rel in files if rel.parts[:1] == ('art',) and rel.suffix == '.png')
    sheet_count = sum(1 for rel in files if rel.parts[:1] == ('sheets',) and rel.suffix == '.png')
    manifest = {
        'format': 'nullrun-environment-kit-manifest-1',
        'title': 'Null Run environment kits: Drowned Records, Switchyard Chapel, After Hours Pavilion',
        'license': 'GPL-2.0-or-later',
        'source_seed': DEFAULT_SEED,
        'excluded': EXCLUDED,
        'seam_requirements': {
            'walls_01_06': {
                'size': [128, 128], 'mode': 'RGB', 'seam': 'both_axes_exact',
                'requirement': 'Opposite edge rows and opposite edge columns must match exactly; checked by checks.py.',
            },
            'landmark_walls_07_08': {
                'size': [128, 128], 'mode': 'RGB', 'seam': 'both_axes_exact',
                'requirement': ('Each landmark panel wraps independently on both axes; the pair is an '
                                'authored adjacent motif, not a continuous split image.'),
            },
            'flats_01_04': {
                'size': [64, 64], 'mode': 'RGB', 'seam': 'both_axes_exact',
                'requirement': 'Opposite edge rows and opposite edge columns must match exactly.',
            },
            'props': {
                'size': [96, 128], 'mode': 'RGBA', 'seam': 'not_applicable',
                'requirement': ('Transparent padding on every edge (>=3 px), feet/bases bottom '
                                'anchored with >=3 px bottom margin, no opaque rectangular backdrop.'),
            },
        },
        'files': hashes,
        'sizes': sizes,
        'assets': assets,
        'totals': {
            'files': len(files),
            'art_pngs': art_count,
            'sheet_pngs': sheet_count,
            'bytes': sum(sizes.values()),
            'art_bytes': sum(v for k, v in sizes.items() if k.startswith('art/')),
            'sheet_bytes': sum(v for k, v in sizes.items() if k.startswith('sheets/')),
        },
        'generation_commands': [
            'PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python art.py --out .',
            'PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python checks.py',
            'PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python make_manifest.py',
        ],
        'notes': [
            'Hashes cover original source, metadata, art and contact/tiling sheets.',
            'manifest.json and the mutable checks.json are excluded from the hash list.',
            'No game pixel, texture, font or logo is sampled in the generated art.',
            'The checks are structural; native renderer and visual acceptance are not claimed here.',
        ],
    }
    (ROOT / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n',
                                        encoding='utf-8')
    print(f'wrote manifest.json: {len(files)} files, {art_count} art PNGs, '
          f'{sheet_count} sheets, {sum(sizes.values())} bytes')


if __name__ == '__main__':
    main()
