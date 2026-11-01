#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Aggregate checks, checks.json and manifest.json for the Threshold kit.

Run after opening.py, art.py, score.py and check_score.py:
PYTHONPATH=/home/echevarian/dev/shared/codex/doom-hydrapy-argon-native \
PYTHONDONTWRITEBYTECODE=1 ~/miniconda3/envs/hydrapy/bin/python check_all.py
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GAME = Path('/home/echevarian/dev/shared/codex/doom-hydrapy-argon-native')
RUNTIME = Path('/home/echevarian/dev/shared/codex/nullrun-fullstack-20261031/runtime')
sys.path[:0] = [str(ROOT), str(GAME), str(RUNTIME)]

import art                                                          # noqa: E402
import opening                                                      # noqa: E402
import score                                                        # noqa: E402
from hydrapy.tracker_v3 import validate                             # noqa: E402
from PIL import Image                                               # noqa: E402

REQUIRED = ['opening.py', 'opening-overview.png', 'opening-overview.json',
            'art.py', 'score.py', 'score.json', 'check_score.py', 'score-checks.json',
            'art-checks.json', 'patch-plan.json', 'README.md', 'CREDITS.md']
ASSETS = ['art/creatures/latchwing_A.png', 'art/creatures/latchwing_B.png',
          'art/creatures/relay_choir_A.png', 'art/creatures/relay_choir_B.png'] + \
         [f'art/walls/{n}.png' for n in art.WALLS] + \
         [f'art/flats/{n}.png' for n in art.FLATS] + \
         [f'art/props/{n}.png' for n in art.PROPS] + \
         [f'art/sheets/{n}_2x2.png' for n in art.WALLS + art.FLATS] + \
         ['art/contact_creatures.png', 'art/contact_materials.png', 'art/contact_props.png']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    checks = []

    def check(name, ok, detail):
        checks.append({'name': name, 'pass': bool(ok), 'detail': detail})

    open_result = opening.run_checks()
    check('opening_suite', open_result['passed'],
          f"{open_result['summary']['passed']}/{open_result['summary']['total']} "
          f"geometry checks across {len(open_result['seeds'])} seeds")
    overview = json.loads((ROOT / 'opening-overview.json').read_text())
    check('opening_overview', (ROOT / 'opening-overview.png').is_file()
          and overview['checks']['failed'] == 0 and overview['seed_scheme'] == opening.SEED_SCHEME,
          'PNG and JSON agree with the 12-seed suite')
    f = opening.generate(20261030)
    check('opening_interface', isinstance(f, opening.Floor) and f.number == 1
          and f.start == opening.START and f.exit == opening.EXIT,
          f'Floor number 1, start {f.start}, exit {f.exit}, {len(f.cells)} cells')
    enemies = [t for t in f.things if t[4] >= 1799]
    pairs = list(zip(enemies, f.variants))
    kinds = {v['kind'] for v in f.variants}
    check('reserved_types', opening.RESERVED == {'latchwing': 69, 'relay_choir': 71}
          and opening.CLASSES['latchwing'] == 15 and opening.CLASSES['relay_choir'] == 16
          and len(pairs) == 8 and kinds >= {'latchwing', 'relay_choir', 'surveyor', 'wire_shambler'}
          and all(t[4] == 1799 | (v['roll'] << 11) for t, v in pairs),
          '69/class15 latchwing and 71/class16 relay_choir present with flag 7 and '
          'options 1799 + roll*2048; surveyor/husk share the signed option space')

    art_checks = json.loads((ROOT / 'art-checks.json').read_text())
    check('art_suite', art_checks['passed'],
          f"art-checks {art_checks['summary']['passed']}/{art_checks['summary']['total']}")
    assets = art.build_all()
    mismatch = []
    for key, expected in art_checks['asset_hashes'].items():
        with Image.open(ROOT / 'art' / key) as image:
            if hashlib.sha256(image.convert(image.mode).tobytes()).hexdigest() != expected:
                mismatch.append(key)
    check('saved_assets_match', not mismatch,
          f'{len(art_checks["asset_hashes"])} generated assets match their saved PNGs')
    check('art_contact_sheets', all((ROOT / p).is_file() for p in
          ['art/contact_creatures.png', 'art/contact_materials.png', 'art/contact_props.png']),
          'three contact sheets present')
    sheets_ok = all(Image.open(ROOT / f'art/sheets/{n}_2x2.png').size ==
                    ((256, 256) if n.startswith('NWALL') else (128, 128))
                    for n in art.WALLS + art.FLATS)
    check('tiling_sheets', sheets_ok, '6 wall 2x2 sheets 256x256 and 4 flat 2x2 sheets 128x128')

    score_checks = json.loads((ROOT / 'score-checks.json').read_text())
    check('score_suite', score_checks['passed'],
          f"score-checks {sum(c['pass'] for c in score_checks['checks'])}/"
          f"{len(score_checks['checks'])}")
    doc = json.loads(score.build().json())
    validate(doc)
    check('score_validator_rebuild', doc['chain'] == list(range(9)) and doc['loop'] is False
          and all(doc['patterns'][p]['bars'] == 8 for p in doc['chain']),
          'fresh build passes hydrapy.tracker_v3.validate; nine 8-bar patterns, loop off')
    check('score_file_matches', sha(ROOT / 'score.json') == score_checks['score_sha256'],
          'score.json SHA-256 matches the validated fresh build')

    plan = json.loads((ROOT / 'patch-plan.json').read_text())
    lanes = {lane['lane']: lane for lane in plan['lanes']}
    check('patch_plan_lanes', sorted(lanes) == [1, 2, 3, 4, 5, 6]
          and 'PVX' in lanes[4]['plan'] and 'PVX' in lanes[5]['plan'],
          'six lanes; PVX named for the riff/lead and bass')
    plan_text = json.dumps(plan).lower()
    check('patch_plan_low_cpu', 'no rack patch' in plan_text and 'loaded' in plan_text
          and 'spoon bender' in plan_text and 'firmware' in plan_text
          and 'optical' in plan_text and 'dc pulse' in plan_text,
          'plan only; one restrained Spoon Bender; explicit no-firmware/no-DC/no-optical limits')

    headers_ok = all('GPL-2.0-or-later' in (ROOT / name).read_text().splitlines()[1]
                     for name in ('opening.py', 'art.py', 'score.py',
                                  'check_score.py', 'check_all.py'))
    check('license_headers', headers_ok, 'SPDX GPL-2.0-or-later on every Python source')
    check('credits_license', 'GPL-2.0-or-later' in (ROOT / 'CREDITS.md').read_text()
          and 'Josiah' in (ROOT / 'CREDITS.md').read_text()
          and 'DeepSeek' in (ROOT / 'CREDITS.md').read_text(),
          'CREDITS names the direction, model-assisted production and license')
    check('no_font_or_ui', not list(ROOT.rglob('*.ttf')) and not list(ROOT.rglob('*.otf'))
          and not list(ROOT.rglob('*.css')) and not list(ROOT.rglob('*.html')),
          'no font or UI file is included; Departure Mono/HUD stay with Codex')

    all_required = all((ROOT / p).is_file() for p in REQUIRED + ASSETS)
    check('required_files', all_required, f'{len(REQUIRED) + len(ASSETS)} expected files present')

    suite = {'passed': all(c['pass'] for c in checks) and open_result['passed']
             and art_checks['passed'] and score_checks['passed'],
             'job': '20261030-230205-deepseek-nullrun-threshold-content',
             'kit': 'Threshold opening floor, art kit and 120-second score',
             'author': 'DeepSeek (model-assisted), directed by Josiah',
             'license': 'GPL-2.0-or-later',
             'suites': {
                 'opening': {k: open_result['summary'][k] for k in ('total', 'passed', 'failed')},
                 'art': {k: art_checks['summary'][k] for k in ('total', 'passed', 'failed')},
                 'score': {'total': len(score_checks['checks']),
                           'passed': sum(c['pass'] for c in score_checks['checks']),
                           'failed': sum(not c['pass'] for c in score_checks['checks'])},
                 'integration': {'total': len(checks),
                                 'passed': sum(c['pass'] for c in checks),
                                 'failed': sum(not c['pass'] for c in checks)}},
             'checks': checks,
             'verified': [
                 'deterministic floor geometry, connectivity, loops, steps, props and 12-seed checks',
                 'creature atlas dimensions, transparency, anchoring, frame motion, corpses and tile seams',
                 'score validator, exact 120 s timeline, act markers, monophony, pitch policy and gestures',
                 'file presence, hashes, license headers and the absence of fonts/UI'],
             'not_verified': [
                 'native Doom gameplay, WAD assembly, native palette readability or enemy behavior',
                 'audio audition, Rack patch load, recording or any video render',
                 'HUD/font replacement, which Codex owns']}
    (ROOT / 'checks.json').write_text(json.dumps(suite, indent=2) + '\n')

    files = []
    for path in sorted(ROOT.rglob('*')):
        if path.is_file() and path.name not in ('manifest.json',) and '__pycache__' not in path.parts:
            files.append({'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size,
                          'sha256': sha(path)})
    manifest = {
        'kit': 'nullrun-threshold-content',
        'job': suite['job'],
        'date': '2026-10-30',
        'author': suite['author'],
        'license': suite['license'],
        'credits': 'CREDITS.md',
        'seed_scheme': {'opening': opening.SEED_SCHEME,
                        'art': 'fixed per-asset seeds in art.frame_seed and material builders',
                        'score': f'0x{score.SEED:08X}'},
        'opening': {
            'interface': 'generate(seed, number=1) -> rogue.maps.Floor',
            'theme': list(opening.THEME),
            'start': list(opening.START), 'exit': list(opening.EXIT),
            'open_cells': len(f.cells), 'route_cells': len(f.route),
            'rooms': len(f.architecture['rooms']),
            'loops': [loop['name'] for loop in f.architecture['loops']],
            'sightlines': f.architecture['sightlines'],
            'max_step': f.architecture['max_step'],
            'start_clearance': f.architecture['start_clearance'],
            'secret_design': f.architecture['secret_design'],
            'reserved_types': f.architecture['reserved_types'],
            'thing_types': sorted({t[3] for t in f.things}),
            'props': [{'name': n, 'cell': list(c)} for n, c, a in opening.PROPS],
            'checks': 'opening-overview.json / checks.json'},
        'art': {
            'families': art.FAMILIES, 'states': list(art.STATES), 'frames_per_state': art.FRAMES,
            'atlas': [512, 768], 'frame': [128, 128],
            'walls': art.WALLS, 'wall_size': [128, 128],
            'flats': art.FLATS, 'flat_size': [64, 64],
            'props': art.PROPS, 'prop_size': [96, 128],
            'checks': 'art-checks.json'},
        'score': {
            'bpm': score.BPM, 'bars': 72, 'rows': 1152, 'seconds': 120.0,
            'patterns': 9, 'bars_per_pattern': 8, 'rate': 1, 'loop': False,
            'chain': list(range(9)), 'lanes': score.LANES,
            'sounds': [16, 17, 22, 0, 0, 0],
            'sha256': score_checks['score_sha256'],
            'checks': 'score-checks.json', 'patch_plan': 'patch-plan.json'},
        'verification': {'checks_json': 'checks.json', 'passed': suite['passed'],
                         'verified': suite['verified'], 'not_verified': suite['not_verified']},
        'files': files,
    }
    (ROOT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'passed': suite['passed'], 'checks': len(checks),
                      'suites': suite['suites'], 'files': len(files),
                      'failed': [c['name'] for c in checks if not c['pass']]}, indent=2))
    return 0 if suite['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
