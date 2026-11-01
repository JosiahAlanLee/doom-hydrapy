#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Recompute manifest.json from the files currently in this folder."""
from __future__ import annotations

import argparse
from pathlib import Path

import generate as G


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default=str(Path(__file__).resolve().parent))
    parser.add_argument('--seed', type=int, default=G.DEFAULT_SEED)
    args = parser.parse_args(argv)
    root = Path(args.root)
    data = G.build_manifest(root)
    data['source_seed'] = int(args.seed)
    data['seeds'] = {k: int(args.seed) for k in ('art', 'mobs', 'props3d', 'layouts', 'music')}
    data['seeds']['derivation'] = 'sha256-based asset_seed(seed, set, kind, index); no Python hash()'
    (root / 'manifest.json').write_text(__import__('json').dumps(data, indent=2) + '\n')
    print(f'{data["file_count"]} files, {data["total_bytes"]} bytes, bundle {data["artifact_bundle_sha256"]}')


if __name__ == '__main__':
    raise SystemExit(main())
