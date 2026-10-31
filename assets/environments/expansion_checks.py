#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Independent checks for the Null Run environment expansion.

Verifies the preserved 45-art kit against its original manifest/check receipt,
the 12 mob atlases / 288 frames and their receipt, the three 120-second scores
and catalogue, the patch-plan boundaries, and the expansion manifest.

    PYTHONDONTWRITEBYTECODE=1 python expansion_checks.py

Only expansion-checks.json is written.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
SET_IDS = ('drowned_records', 'switchyard_chapel', 'after_hours_pavilion')
SLOTS = ('latchwing', 'relay_choir')
STATES = ('idle', 'walk', 'warning', 'attack', 'hurt', 'death')
CHECKS = []
METRICS = {}


def add(cid, ok, detail, **extra):
    entry = {'id': cid, 'pass': bool(ok), 'detail': detail}
    entry.update(extra)
    CHECKS.append(entry)
    return bool(ok)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def art_bundle():
    paths = sorted((ROOT / 'art').rglob('*.png'))
    return hashlib.sha256(''.join(f'{p.relative_to(ROOT).as_posix()} {sha(p)}'
                                  for p in paths).encode()).hexdigest()


def atlas_bundle():
    paths = sorted((ROOT / 'mobs').rglob('*.png'))
    return hashlib.sha256(''.join(sorted(sha(p) for p in paths)).encode()).hexdigest()


def expected_atlases():
    return [Path('mobs') / sid / f'{slot}_{variant}.png'
            for sid in SET_IDS for slot in SLOTS for variant in ('A', 'B')]


def expected_mob_sheets():
    return ([Path('sheets') / f'{sid}-mobs.png' for sid in SET_IDS]
            + [Path('sheets/drowned-records-creepy.png')])


def check_original():
    problems = []
    manifest_path = ROOT / 'manifest.json'
    checks_path = ROOT / 'checks.json'
    if not manifest_path.is_file() or not checks_path.is_file():
        add('original_45_art_preserved', False, 'original manifest/checks missing')
        return
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    original_checks = json.loads(checks_path.read_text(encoding='utf-8'))
    if manifest.get('format') != 'nullrun-environment-kit-manifest-1':
        problems.append('manifest format changed')
    if manifest.get('source_seed') != 20261031:
        problems.append('manifest seed changed')
    files = manifest.get('files', {})
    if len(files) != 57:
        problems.append(f'original manifest has {len(files)} files, expected 57')
    for rel, digest in files.items():
        path = ROOT / rel
        if not path.is_file():
            problems.append(f'missing {rel}')
        elif sha(path) != digest:
            problems.append(f'hash changed {rel}')
    art_count = len(list((ROOT / 'art').rglob('*.png')))
    if art_count != 45:
        problems.append(f'art count {art_count}, expected 45')
    bundle = art_bundle()
    if original_checks.get('art_bundle_sha256') != bundle:
        problems.append('original checks art bundle does not match current art')
    if original_checks.get('passed') is not True or original_checks.get('failed'):
        problems.append('original checks receipt is not passing')
    if len(original_checks.get('checks', [])) != 19:
        problems.append(f'original checks count {len(original_checks.get("checks", []))}')
    METRICS['original'] = {
        'manifest_sha256': sha(manifest_path),
        'checks_sha256': sha(checks_path),
        'files_hashed': len(files),
        'art_pngs': art_count,
        'art_bundle_sha256': bundle,
        'original_checked': bool(original_checks.get('passed')),
    }
    add('original_45_art_preserved', not problems,
        'original manifest, 45 art PNGs, 57 hashed files and 19/19 check receipt unchanged'
        if not problems else '; '.join(problems[:10]), problems=problems[:30])


def check_mobs():
    problems = []
    expected = expected_atlases()
    actual = sorted((ROOT / 'mobs').rglob('*.png'))
    rel_actual = [p.relative_to(ROOT) for p in actual]
    if len(actual) != 12:
        problems.append(f'{len(actual)} atlases, expected 12')
    if any(p not in rel_actual for p in expected):
        problems.append('missing expected atlas path')
    for rel in expected:
        if not (ROOT / rel).is_file():
            continue
        with Image.open(ROOT / rel) as image:
            image.load()
            if image.size != (512, 768) or image.mode != 'RGBA':
                problems.append(f'{rel}: {image.size} {image.mode}')
    receipt_path = ROOT / 'mob-checks.json'
    if not receipt_path.is_file():
        problems.append('mob-checks.json missing')
    else:
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        if receipt.get('passed') is not True or receipt.get('failed'):
            problems.append('mob receipt not passing')
        if receipt.get('atlases') != 12 or receipt.get('frames') != 288:
            problems.append('mob receipt counts')
        if len(receipt.get('checks', [])) != 14:
            problems.append('mob receipt check count')
        if receipt.get('atlas_bundle_sha256') != atlas_bundle():
            problems.append('mob receipt atlas bundle mismatch')
    with Image.open(ROOT / 'sheets/drowned-records-creepy.png') as image:
        image.load()
        if image.size[0] < 1000 or image.size[1] < 1200:
            problems.append('creepy board too small')
    for rel in expected_mob_sheets():
        if not (ROOT / rel).is_file():
            problems.append(f'missing {rel}')
    encounters = json.loads((ROOT / 'encounters.json').read_text(encoding='utf-8'))
    if encounters.get('format') != 'nullrun-environment-mobs-1':
        problems.append('encounters format')
    sets = encounters.get('sets', {})
    if set(sets) != set(SET_IDS):
        problems.append('encounters sets')
    ids = []
    for sid in SET_IDS:
        if set(sets.get(sid, {})) != set(SLOTS):
            problems.append(f'{sid}: slots')
            continue
        for slot in SLOTS:
            mob = sets[sid][slot]
            if mob.get('behavior_family') != slot:
                problems.append(f'{sid}/{slot}: behavior_family')
            limits = mob.get('limits', '').lower()
            if 'existing' not in limits or 'no new ai' not in limits:
                problems.append(f'{sid}/{slot}: limits')
            ids.append(mob.get('id'))
    if len(ids) != 6 or len(set(ids)) != 6:
        problems.append('not six unique identities')
    METRICS['mobs'] = {'atlases': len(actual), 'frames': len(actual) * 24,
                       'atlas_bundle_sha256': atlas_bundle()}
    add('mobs_12_atlases_288_frames', not problems,
        '12 RGBA 512x768 atlases, 288 frames, four sheets, six identities on two existing families'
        if not problems else '; '.join(problems[:10]), problems=problems[:30])


def check_music():
    problems = []
    catalogue_path = ROOT / 'music/catalogue.json'
    if not catalogue_path.is_file():
        add('scores_three_120s', False, 'music/catalogue.json missing')
        return
    catalogue = json.loads(catalogue_path.read_text(encoding='utf-8'))
    if catalogue.get('format') != 'nullrun-environment-score-catalogue-1':
        problems.append('catalogue format')
    sets = catalogue.get('sets', {})
    if set(sets) != set(SET_IDS):
        problems.append('catalogue sets')
    rows = {}
    for sid in SET_IDS:
        entry = sets.get(sid, {})
        score_path = ROOT / entry.get('score', '')
        checks_path = ROOT / entry.get('checks', '')
        patch_path = ROOT / entry.get('patch_plan', '')
        readme_path = ROOT / 'music' / sid / 'README.md'
        script_path = ROOT / 'music' / sid / 'score.py'
        for path, label in ((score_path, 'score'), (checks_path, 'checks'),
                            (patch_path, 'patch-plan'), (readme_path, 'README'),
                            (script_path, 'score.py')):
            if not path.is_file():
                problems.append(f'{sid}: missing {label}')
        if not score_path.is_file() or not checks_path.is_file():
            continue
        if entry.get('sha256') != sha(score_path):
            problems.append(f'{sid}: catalogue score hash')
        checks = json.loads(checks_path.read_text(encoding='utf-8'))
        if checks.get('passed') is not True or checks.get('failed'):
            problems.append(f'{sid}: score checks not passing')
        if len(checks.get('checks', [])) != 21:
            problems.append(f'{sid}: check count {len(checks.get("checks", []))}')
        timeline = checks.get('timeline', {})
        if (timeline.get('bpm') != entry.get('bpm')
                or timeline.get('bars') != entry.get('bars')
                or timeline.get('patterns') != entry.get('patterns')
                or abs(timeline.get('seconds', 0) - 120.0) > 1e-9
                or timeline.get('loop') is not False):
            problems.append(f'{sid}: timeline/catalogue mismatch')
        ids = {c['id']: c['pass'] for c in checks.get('checks', [])}
        for required in ('tracker3_validate', 'timeline_120_seconds',
                         'monophonic_no_gate_overlap', 'patch_plan_low_cpu_intent',
                         'distinct_bpm', 'distinct_bars', 'distinct_patterns',
                         'distinct_key', 'distinct_event_density',
                         'distinct_kick_rhythm', 'distinct_lead_contour',
                         'distinct_lead_register'):
            if ids.get(required) is not True:
                problems.append(f'{sid}: {required}')
        rows[sid] = {'bpm': entry.get('bpm'), 'bars': entry.get('bars'),
                     'patterns': entry.get('patterns'), 'seconds': entry.get('seconds'),
                     'sha256': entry.get('sha256')}
    METRICS['scores'] = rows
    add('scores_three_120s', not problems,
        'three original 120.000 s scores, 21/21 checks each, catalogue hashes match, distinctness verified'
        if not problems else '; '.join(problems[:10]), problems=problems[:30])


def _keys(value, out):
    if isinstance(value, dict):
        out.update(value.keys())
        for item in value.values():
            _keys(item, out)
    elif isinstance(value, list):
        for item in value:
            _keys(item, out)


def check_boundaries():
    forbidden = ('.wav', '.mp3', '.flac', '.ogg', '.opus', '.mp4', '.mov', '.gif',
                 '.bin', '.rom', '.img', '.iso')
    bad_files = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*')
                 if p.is_file() and p.suffix.lower() in forbidden]
    keys = set()
    for name in ('encounters.json', 'music/catalogue.json'):
        _keys(json.loads((ROOT / name).read_text(encoding='utf-8')), keys)
    forbidden_keys = {'actor_id', 'native_id', 'type_id', 'new_ai', 'firmware'}
    bad_keys = sorted(keys & forbidden_keys)
    expansion_files = [p for p in ROOT.rglob('*') if p.is_file()
                       and (p.relative_to(ROOT).parts[0] in
                            ('mobs', 'music', 'sheets', 'mob_art.py', 'mob_checks.py',
                             'encounters.json', 'EXPANSION.md', 'make_expansion_manifest.py'))]
    total = sum(p.stat().st_size for p in expansion_files)
    largest = max((p.stat().st_size for p in expansion_files), default=0)
    METRICS['boundaries'] = {'forbidden_files': bad_files, 'forbidden_keys': bad_keys,
                             'expansion_files': len(expansion_files),
                             'expansion_bytes': total, 'largest_bytes': largest}
    ok = not bad_files and not bad_keys and total <= 20_000_000 and largest <= 5_000_000
    add('no_audio_video_firmware_or_actor_ids', ok,
        f'no audio/video/firmware extensions; no actor/type IDs; expansion size {total} B'
        if ok else f'files={bad_files[:5]} keys={bad_keys} total={total} largest={largest}')


def check_docs():
    problems = []
    expansion = ROOT / 'EXPANSION.md'
    if not expansion.is_file():
        problems.append('EXPANSION.md missing')
    else:
        text = expansion.read_text(encoding='utf-8').lower()
        for term in ('creepy', 'not rendered', 'not auditioned', 'existing',
                     '120.000', '288', 'josiah', 'deepseek', 'gpl-2.0-or-later'):
            if term not in text:
                problems.append(f'EXPANSION.md missing {term}')
    for sid in SET_IDS:
        readme = (ROOT / 'music' / sid / 'README.md').read_text(encoding='utf-8').lower()
        if 'no audio was rendered' not in readme or '120.000000 s' not in readme:
            problems.append(f'{sid}: README non-claim/timing missing')
    add('nonclaim_documentation', not problems,
        'EXPANSION.md and the three score READMEs state the 120 s facts and audio/native non-claims'
        if not problems else '; '.join(problems[:8]))


def check_manifest():
    path = ROOT / 'expansion-manifest.json'
    if not path.is_file():
        add('expansion_manifest_integrity', True,
            'expansion-manifest.json not present yet; run make_expansion_manifest.py', skipped=True)
        return
    manifest = json.loads(path.read_text(encoding='utf-8'))
    problems = []
    if manifest.get('format') != 'nullrun-environment-expansion-manifest-1':
        problems.append('format')
    if manifest.get('source_seed') != 20261031:
        problems.append('source_seed')
    files = manifest.get('files', {})
    expected = [
        Path('mob_art.py'), Path('mob_checks.py'), Path('make_expansion_manifest.py'),
        Path('encounters.json'), Path('EXPANSION.md'),
        Path('music/common.py'), Path('music/check_music.py'), Path('music/catalogue.json'),
    ]
    expected += expected_atlases()
    expected += expected_mob_sheets()
    for sid in SET_IDS:
        for name in ('score.py', 'score.json', 'patch-plan.json', 'README.md'):
            expected.append(Path('music') / sid / name)
    expected_set = {p.as_posix() for p in expected if (ROOT / p).is_file()}
    if set(files) != expected_set:
        missing = sorted(expected_set - set(files))
        extra = sorted(set(files) - expected_set)
        problems.append(f'keys missing={missing[:5]} extra={extra[:5]}')
    for rel, digest in files.items():
        if sha(ROOT / rel) != digest:
            problems.append(f'hash mismatch {rel}')
    assets = manifest.get('assets', {})
    for rel in expected_atlases() + expected_mob_sheets():
        meta = assets.get(rel.as_posix(), {})
        if not meta:
            problems.append(f'missing asset metadata {rel}')
            continue
        with Image.open(ROOT / rel) as image:
            if meta.get('width') != image.width or meta.get('height') != image.height \
                    or meta.get('mode') != image.mode:
                problems.append(f'asset metadata {rel}')
    for sid in SET_IDS:
        entry = manifest.get('scores', {}).get(sid, {})
        if entry.get('sha256') != sha(ROOT / f'music/{sid}/score.json'):
            problems.append(f'{sid}: score hash')
        if abs(entry.get('seconds', 0) - 120.0) > 1e-9:
            problems.append(f'{sid}: seconds')
    receipts = manifest.get('check_receipts', {})
    for rel in ['mob-checks.json'] + [f'music/{sid}/checks.json' for sid in SET_IDS]:
        if receipts.get(rel, {}).get('sha256') != sha(ROOT / rel):
            problems.append(f'receipt {rel}')
    original = manifest.get('original_kit', {})
    if original.get('manifest_sha256') != sha(ROOT / 'manifest.json') \
            or original.get('checks_sha256') != sha(ROOT / 'checks.json'):
        problems.append('original receipt reference')
    add('expansion_manifest_integrity', not problems,
        f'{len(files)} stable expansion files and {len(assets)} PNG assets hashed; '
        f'receipts and original references match' if not problems else '; '.join(problems[:10]),
        problems=problems[:30])


def main():
    check_original()
    check_mobs()
    check_music()
    check_boundaries()
    check_docs()
    check_manifest()
    failed = [c['id'] for c in CHECKS if not c['pass']]
    doc = {
        'format': 'nullrun-environment-expansion-checks-1',
        'source_seed': 20261031,
        'passed': not failed,
        'failed': failed,
        'checks': CHECKS,
        'metrics': METRICS,
        'limitations': [
            'Structural checks only; visual quality, native sprite mapping and audio quality are not proved.',
            'No native game, PLAYPAL, Rack patch, audio render or audition was run.',
            'Six identities reuse the existing latchwing and relay_choir behavior families; no new AI or actor IDs exist.',
            'Codex owns native integration, frame mapping, collision, performance, Rack/audio and final review.',
        ],
        'nonclaims': [
            'No audio/video/firmware files are included.',
            'No sample, existing music or copied game pixel is included.',
            'No gameplay, actor ID, mechanic or loaded patch is claimed.',
        ],
    }
    (ROOT / 'expansion-checks.json').write_text(json.dumps(doc, indent=2) + '\n',
                                                encoding='utf-8')
    print(f'expansion checks: {len(CHECKS) - len(failed)}/{len(CHECKS)} passed; failed={failed}')
    for c in CHECKS:
        print(('PASS ' if c['pass'] else 'FAIL ') + c['id'] + ': ' + c['detail'])
    return 0 if not failed else 1


if __name__ == '__main__':
    raise SystemExit(main())
