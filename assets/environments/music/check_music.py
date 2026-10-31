#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Validate the three environment-keyed scores and write their check receipts.

Uses the supplied hydrapy.tracker_v3.validate and an independent timeline /
gate-overlap calculation.  Also checks the low-CPU patch plans as written
intent.  Writes music/<set>/checks.json and music/catalogue.json only.

    PYTHONDONTWRITEBYTECODE=1 python check_music.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from common import ROWS, lane_events, score_seconds, validate, timeline  # noqa: E402
from hydrapy.studio_tracker import note_midi                               # noqa: E402

SET_IDS = ('drowned_records', 'switchyard_chapel', 'after_hours_pavilion')
EXPECTED = {
    'drowned_records': {
        'bpm': 96, 'bars': 48, 'patterns': 6, 'key': 5,
        'mood': ('Sparse flood-marked archive pressure: broken low pulses, long bass, '
                 'warm reedy PVX and a restrained near-interval motif.'),
    },
    'switchyard_chapel': {
        'bpm': 128, 'bars': 64, 'patterns': 8, 'key': 2,
        'mood': ('Driving syncopated electro/FM machinery: irregular percussion, a strong '
                 'bass figure, call/response lead, a sparse breakdown and a developed return.'),
    },
    'after_hours_pavilion': {
        'bpm': 112, 'bars': 56, 'patterns': 7, 'key': 7,
        'mood': ('Off-kilter broken lounge: displaced bell/reed phrase, gentle mechanical '
                 'bass, missing expected beats and a deliberately quiet middle.'),
    },
}
LANE_NAMES = ('kick', 'snare', 'hat/texture', 'lead', 'bass',
              'counterline/atmosphere')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def add(checks, cid, ok, detail, **extra):
    entry = {'id': cid, 'pass': bool(ok), 'detail': detail}
    entry.update(extra)
    checks.append(entry)
    return bool(ok)


def load_build(set_id):
    path = ROOT / set_id / 'score.py'
    spec = importlib.util.spec_from_file_location(f'score_{set_id}', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def notes_by_lane(events):
    out = {lane: [] for lane in range(6)}
    for row, lane, cell in events:
        out[lane].append((row, note_midi(cell['note']), cell.get('len', 1.0), cell['vel']))
    for lane in out:
        out[lane].sort()
    return out


def overlaps(lanes, total):
    bad = []
    for lane, notes in lanes.items():
        for (row_a, _, len_a, _), (row_b, _, _, _) in zip(notes, notes[1:]):
            if row_a + len_a > row_b + 1e-9:
                bad.append((lane, row_a, len_a, row_b))
        if notes and notes[-1][0] + notes[-1][2] > total + 1e-9:
            bad.append((lane, 'tail', notes[-1][0], notes[-1][2], total))
    return bad


def patch_check(checks, set_id):
    path = ROOT / set_id / 'patch-plan.json'
    problems = []
    if not path.is_file():
        add(checks, 'patch_plan', False, 'patch-plan.json missing')
        return None
    plan = json.loads(path.read_text(encoding='utf-8'))
    status = str(plan.get('status', '')).lower()
    if 'plan only' not in status or 'loaded' not in status or 'auditioned' not in status:
        problems.append('status is not clearly plan-only')
    lanes = plan.get('lanes', [])
    if not isinstance(lanes, list) or len(lanes) != 6:
        problems.append('six lanes required')
    else:
        for i, lane in enumerate(lanes, 1):
            if lane.get('lane') != i or lane.get('name') != LANE_NAMES[i - 1]:
                problems.append(f'lane {i} mismatch')
    voices = plan.get('voices', {})
    if set(voices) != {'PVX_lead', 'PVX_bass', 'percussion', 'space'}:
        problems.append(f'voice keys {sorted(voices)}')
    else:
        if voices['PVX_lead'].get('lanes') != [4, 6]:
            problems.append('PVX_lead must carry lanes 4 and 6')
        if voices['PVX_bass'].get('lanes') != [5]:
            problems.append('PVX_bass must carry lane 5')
        if voices['percussion'].get('lanes') != [1, 2, 3]:
            problems.append('percussion must carry lanes 1-3')
        if voices['space'].get('lanes') != [6]:
            problems.append('space must carry lane 6')
    bridge = str(plan.get('gorgon_bridge', '')).lower()
    for term in ('pitch12', 'gates11', 'velocity3'):
        if term not in bridge:
            problems.append(f'gorgon bridge missing {term}')
    pvx = str(plan.get('pvx_input2', '')).lower()
    if 'external audio' not in pvx or 'not velocity' not in pvx or 'vca' not in pvx:
        problems.append('PVX input2 / VCA note missing')
    limits = ' '.join(str(x).lower() for x in plan.get('limits', []))
    for term in ('no firmware emulation', 'no giant voice banks',
                 'no gpu/audio/image sampling prerequisites', 'no dc pulses'):
        if term not in limits:
            problems.append(f'limit missing {term}')
    if not isinstance(plan.get('revoicing_suggestions'), dict):
        problems.append('revoicing suggestions missing')
    add(checks, 'patch_plan_low_cpu_intent', not problems,
        'six lanes, PVX lead/bass, simple percussion, optional clean Spoon Bender, '
        'PVX input2/VCA and no-firmware/no-bank/no-GPU/no-DC limits documented'
        if not problems else '; '.join(problems), problems=problems[:20])
    return plan


def score_check(set_id):
    checks = []
    spec = EXPECTED[set_id]
    module = load_build(set_id)
    first = module.build()
    second = module.build()
    doc = validate(first)
    events, total_rows = lane_events(doc)
    lanes = notes_by_lane(events)
    tl = timeline(doc)
    seconds = score_seconds(doc)
    score_path = ROOT / set_id / 'score.json'
    raw = score_path.read_text(encoding='utf-8')

    geometry = all(doc['patterns'][p] is not None
                   and doc['patterns'][p]['rate'] == 1
                   and doc['patterns'][p]['bar'] == 16
                   and doc['patterns'][p]['bars'] == 8 for p in doc['chain'])
    add(checks, 'tracker3_validate', True, 'accepted by hydrapy.tracker_v3.validate')
    add(checks, 'timeline_120_seconds',
        abs(seconds - 120.0) < 1e-9 and tl.cycle == total_rows * 480,
        f'{total_rows} rows, {tl.cycle} ticks, {seconds:.6f} s')
    add(checks, 'pattern_geometry',
        geometry and doc['chain'] == list(range(spec['patterns'])) and doc['loop'] is False,
        f'{spec["patterns"]} x 8-bar patterns, rate 1, 16 rows/bar, finite chain 0-{spec["patterns"] - 1}')
    add(checks, 'header',
        doc['bpm'] == spec['bpm'] and doc['key'] == spec['key']
        and len(doc['chain']) == spec['patterns'],
        f'BPM {doc["bpm"]}, key {doc["key"]}, {len(doc["chain"])} patterns, '
        f'{spec["bars"]} bars, loop={doc["loop"]}')
    add(checks, 'six_lane_names',
        [lane['name'] for lane in doc['lanes']] == list(LANE_NAMES),
        'kick / snare / hat-texture / lead / bass / counterline-atmosphere')
    add(checks, 'no_chords_one_cell_per_row',
        all(len({row for row, _, _, _ in notes}) == len(notes) for notes in lanes.values()),
        'each lane has at most one onset per row')
    bad = overlaps(lanes, total_rows)
    add(checks, 'monophonic_no_gate_overlap', not bad,
        'all lane gates are disjoint, including chained pattern boundaries'
        if not bad else f'overlaps {bad[:5]}')
    pitches = [note_midi(cell['note']) for _, _, cell in events]
    add(checks, 'midi_24_96', 24 <= min(pitches) and max(pitches) <= 96,
        f'written range {min(pitches)}..{max(pitches)}')
    vels = [cell['vel'] for _, _, cell in events]
    add(checks, 'dynamics',
        min(vels) <= 60 and max(vels) >= 80 and len(set(vels)) >= 5,
        f'velocity {min(vels)}..{max(vels)}, {len(set(vels))} levels')
    rests = {}
    lane_gaps = {}
    for lane, notes in lanes.items():
        onsets = [row for row, *_ in notes]
        gaps = [onsets[0]] + [b - a for a, b in zip(onsets, onsets[1:])] + [total_rows - onsets[-1]]
        rests[LANE_NAMES[lane]] = round(1 - len(onsets) / total_rows, 4)
        lane_gaps[LANE_NAMES[lane]] = max(gaps)
    all_onsets = sorted(row for row, _, _ in events)
    global_gaps = [all_onsets[0]] + [b - a for a, b in zip(all_onsets, all_onsets[1:])] + [
        total_rows - all_onsets[-1]]
    add(checks, 'rests_and_no_extended_silence',
        all(value >= 0.20 for value in rests.values())
        and max(global_gaps) <= 32 and all(notes for notes in lanes.values()),
        'empty-row share ' + '/'.join(f'{rests[name]:.2f}' for name in LANE_NAMES)
        + f'; max all-lane gap {max(global_gaps)} rows')
    add(checks, 'score_file_matches',
        raw == json.dumps(doc, indent=2) + '\n',
        'score.json equals a fresh build with pretty indentation and trailing newline')
    add(checks, 'deterministic',
        json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
        and sha(score_path) == hashlib.sha256(raw.encode()).hexdigest(),
        'two builds are identical; sha256 ' + sha(score_path))
    patch_check(checks, set_id)

    pitch = {}
    for lane, name in ((3, 'lead'), (4, 'bass'), (5, 'counterline')):
        notes = [midi for _, midi, _, _ in lanes[lane]]
        pitch[name] = {'min': min(notes), 'max': max(notes), 'count': len(notes),
                       'mean': round(sum(notes) / len(notes), 3)}
    counts = {LANE_NAMES[lane]: len(lanes[lane]) for lane in range(6)}
    failed = [c['id'] for c in checks if not c['pass']]
    result = {
        'format': 'nullrun-environment-score-checks-1',
        'set_id': set_id,
        'score': 'score.json',
        'score_sha256': sha(score_path),
        'score_bytes': len(raw.encode()),
        'passed': not failed,
        'failed': failed,
        'checks': checks,
        'timeline': {
            'bpm': doc['bpm'], 'key': doc['key'], 'bars': spec['bars'],
            'patterns': spec['patterns'], 'rows': total_rows,
            'ticks': tl.cycle, 'seconds': seconds, 'loop': doc['loop'],
            'row_seconds': 60 / doc['bpm'] / 4,
        },
        'lanes': {LANE_NAMES[lane]: {'events': counts[LANE_NAMES[lane]],
                                     'rest_fraction': rests[LANE_NAMES[lane]],
                                     'max_onset_gap_rows': lane_gaps[LANE_NAMES[lane]]}
                  for lane in range(6)},
        'pitch': pitch,
        'velocity': {'min': min(vels), 'max': max(vels), 'levels': len(set(vels))},
        'notes': [
            'Validated with the supplied hydrapy.tracker_v3 reader; no reimplementation.',
            'No audio was rendered or auditioned. Patch plans are intent only.',
            'The score is original written note data; no sample or existing music is included.',
            'Codex owns native playback, Rack mapping and audio review.',
        ],
    }
    (ROOT / set_id / 'checks.json').write_text(json.dumps(result, indent=2) + '\n',
                                               encoding='utf-8')
    return result, doc, events, lanes


def distinctness(results, docs, events_by_set, lanes_by_set):
    checks = []
    specs = {sid: results[sid]['timeline'] for sid in SET_IDS}
    for field in ('bpm', 'bars', 'patterns', 'key'):
        values = [specs[sid][field] for sid in SET_IDS]
        add(checks, f'distinct_{field}', len(set(values)) == 3,
            f'{field} values {values}')
    event_counts = [len(events_by_set[sid]) for sid in SET_IDS]
    add(checks, 'distinct_event_density', len(set(event_counts)) == 3,
        f'event counts {event_counts}')

    kick_signatures = {}
    lead_contours = {}
    lead_means = {}
    for sid in SET_IDS:
        doc = docs[sid]
        first_pattern = doc['chain'][0]
        kick_cells = doc['patterns'][first_pattern]['lanes'][0]['cells']
        kick_signatures[sid] = tuple(i for i, cell in enumerate(kick_cells) if cell)
        notes = [midi for _, midi, _, _ in lanes_by_set[sid][3]]
        lead_contours[sid] = tuple(b - a for a, b in zip(notes, notes[1:]))
        lead_means[sid] = sum(notes) / len(notes)
    add(checks, 'distinct_kick_rhythm',
        len(set(kick_signatures.values())) == 3,
        'first-pattern kick row sets differ: ' +
        '; '.join(f'{sid}={len(v)} rows' for sid, v in kick_signatures.items()))
    add(checks, 'distinct_lead_contour',
        len(set(lead_contours.values())) == 3,
        'lead interval sequences differ across all three scores')
    lead_values = [lead_means[sid] for sid in SET_IDS]
    add(checks, 'distinct_lead_register',
        max(lead_values) - min(lead_values) >= 2.0,
        'lead mean MIDI ' + ', '.join(f'{sid}={lead_means[sid]:.2f}' for sid in SET_IDS))
    return checks


def main():
    results = {}
    docs = {}
    events_by_set = {}
    lanes_by_set = {}
    for set_id in SET_IDS:
        result, doc, events, lanes = score_check(set_id)
        results[set_id] = result
        docs[set_id] = doc
        events_by_set[set_id] = events
        lanes_by_set[set_id] = lanes

    distinct_checks = distinctness(results, docs, events_by_set, lanes_by_set)
    for set_id in SET_IDS:
        results[set_id]['checks'].extend(distinct_checks)
        failed = [c['id'] for c in results[set_id]['checks'] if not c['pass']]
        results[set_id]['passed'] = not failed
        results[set_id]['failed'] = failed
        (ROOT / set_id / 'checks.json').write_text(
            json.dumps(results[set_id], indent=2) + '\n', encoding='utf-8')

    catalogue = {
        'format': 'nullrun-environment-score-catalogue-1',
        'source_seed': 20261031,
        'license': 'GPL-2.0-or-later',
        'notes': [
            'Original written note data only; no audio was rendered or auditioned.',
            'Paths are relative to the kit root. BPM and bars give exactly 120.000 s at 4/4.',
            'Codex owns native playback, Rack mapping, revoicing and audio review.',
        ],
        'sets': {},
    }
    for set_id in SET_IDS:
        score_path = ROOT / set_id / 'score.json'
        spec = EXPECTED[set_id]
        catalogue['sets'][set_id] = {
            'score': f'music/{set_id}/score.json',
            'checks': f'music/{set_id}/checks.json',
            'patch_plan': f'music/{set_id}/patch-plan.json',
            'bpm': spec['bpm'],
            'seconds': 120.0,
            'bars': spec['bars'],
            'patterns': spec['patterns'],
            'key': spec['key'],
            'mood': spec['mood'],
            'sha256': sha(score_path),
        }
    (ROOT / 'catalogue.json').write_text(json.dumps(catalogue, indent=2) + '\n',
                                         encoding='utf-8')

    failures = {sid: results[sid]['failed'] for sid in SET_IDS if results[sid]['failed']}
    print(f'music checks: {sum(1 for sid in SET_IDS if not results[sid]["failed"])}/3 scores passed')
    for sid in SET_IDS:
        print(f'{sid}: {len(results[sid]["checks"]) - len(results[sid]["failed"])}/'
              f'{len(results[sid]["checks"])} passed, failed={results[sid]["failed"]}')
    print('catalogue.json written')
    return 0 if not failures else 1


if __name__ == '__main__':
    raise SystemExit(main())
