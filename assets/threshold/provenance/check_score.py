#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Validate the Threshold score and write score-checks.json.

Run: ~/miniconda3/envs/hydrapy/bin/python check_score.py
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import score                                                        # noqa: E402
from hydrapy.studio_tracker import note_midi                       # noqa: E402
from hydrapy.tracker_v3 import timeline, validate                  # noqa: E402


def main():
    raw = score.build().json()
    again = score.build().json()
    doc = json.loads(raw)
    validate(doc)
    tl = timeline(doc)
    checks = []

    def check(name, ok, detail):
        checks.append({'name': name, 'pass': bool(ok), 'detail': detail})

    rows_per_pattern = score.BAR * score.BARS
    total_rows = rows_per_pattern * len(doc['chain'])
    total_ticks = total_rows * 480
    seconds = total_ticks / 1920 * 60 / score.BPM
    row_seconds = 60 / score.BPM / 4
    check('hydrapy.tracker_v3.validate', True, 'score accepted by the supplied validator')
    check('timeline', total_rows == 1152 and abs(seconds - 120.0) < 1e-12
          and tl.cycle == total_ticks and len(tl.starts) == 10,
          f'{total_rows} rows, {total_ticks} ticks, {seconds:.6f} s; timeline cycle {tl.cycle}')
    geo = all(doc['patterns'][p] is not None and doc['patterns'][p]['rate'] == 1
              and doc['patterns'][p]['bar'] == 16 and doc['patterns'][p]['bars'] == 8
              for p in doc['chain'])
    check('pattern_geometry', geo and doc['chain'] == list(range(9)) and doc['loop'] is False,
          'nine 8-bar patterns, rate 1, 16 rows/bar, unlooped chain 0-8')
    starts = {p: i * rows_per_pattern for i, p in enumerate(doc['chain'])}
    scenes = []
    for p in doc['chain']:
        for e in doc['patterns'][p]['scenes']:
            scenes.append((e['name'], starts[p] + e['r'], e['fade']))
    check('acts_exact', scenes == [(score.ACTS[0], 0, 0), (score.ACTS[1], 384, 0),
                                   (score.ACTS[2], 768, 0)],
          'three 24-bar / 40.000 s acts at 0/40/80 s, fade 0')
    sounds = [s['machine'] for s in doc['sounds']]
    check('sounds', sounds == [16, 17, 22, 0, 0, 0] and all(
        not s['params'] for s in doc['sounds']), 'defaults 16/17/22/0/0/0, no sound parameters')

    events = []
    for p in doc['chain']:
        for lane in range(6):
            for r, c in enumerate(doc['patterns'][p]['lanes'][lane]['cells']):
                if c is not None:
                    events.append((p, lane, r, c))
    locks = [c for p, lane, r, c in events if 'locks' in c or 'cond' in c]
    check('no_conditionals_or_locks', not locks,
          'no probability, fill, machine or parameter locks; every note is explicit')

    mono, overlaps = {}, []
    for lane in range(6):
        lane_events = sorted((starts[p] + r, c.get('len', 1.0), p, r)
                             for p, l, r, c in events if l == lane)
        mono[lane] = len(lane_events)
        for (a, la, pa, ra), (b, lb, pb, rb) in zip(lane_events, lane_events[1:]):
            if a + la > b + 1e-9:
                overlaps.append((lane, pa, ra, a, la, b))
        if lane_events:
            last = lane_events[-1]
            if last[0] + last[1] > total_rows + 1e-9:
                overlaps.append((lane, last[2], last[3], last[0], last[1], total_rows))
    check('monophonic_lanes', not overlaps and all(n > 0 for n in mono.values()),
          f'lane events {mono}; no overlapping gates, including chained pattern ends')

    pitch = {}
    allowed = {0, 2, 3, 4, 5, 7, 9, 10}
    for lane, name in ((3, 'lead'), (4, 'bass'), (5, 'counterline')):
        notes = [note_midi(c['note']) for p, l, r, c in events if l == lane]
        pitch[name] = {'min': min(notes), 'max': max(notes),
                       'pitch_classes': sorted({n % 12 for n in notes}),
                       'count': len(notes)}
    check('pitch_register', 57 <= pitch['lead']['min'] and pitch['lead']['max'] <= 81
          and 29 <= pitch['bass']['min'] and pitch['bass']['max'] <= 53,
          f"lead {pitch['lead']['min']}..{pitch['lead']['max']}, "
          f"bass {pitch['bass']['min']}..{pitch['bass']['max']}")
    check('d_minor_phrygian', all(set(v['pitch_classes']) <= allowed for v in pitch.values())
          and 3 in pitch['lead']['pitch_classes'] and 10 in pitch['lead']['pitch_classes'],
          'written pitch classes stay in D minor plus Eb; lead uses b2 and b6')

    kick_bars = {}
    for p, l, r, c in events:
        if l == 0:
            kick_bars.setdefault((p, r // 16), set()).add(r % 16)
    gesture_a = sum(1 for rows in kick_bars.values() if rows == {0, 3, 6, 8, 11, 14})
    gesture_b = sum(1 for rows in kick_bars.values()
                    if rows == {0, 6, 10} or rows == {0, 6, 10, 14})
    check('two_rhythmic_gestures', gesture_a >= 16 and gesture_b >= 8,
          f'gesture A (0,3,6,8,11,14) in {gesture_a} bars; gesture B (0,6,10 half-time) in {gesture_b}')

    vels = [c['vel'] for p, l, r, c in events]
    lens = [c.get('len', 1.0) for p, l, r, c in events]
    check('dynamics', min(vels) <= 52 and max(vels) >= 116 and len(set(vels)) >= 6,
          f'velocity {min(vels)}..{max(vels)}, {len(set(vels))} levels; lengths '
          f'{min(lens):.2f}..{max(lens):.1f}')

    lane_gaps, rest_frac = {}, {}
    for lane in range(6):
        onsets = sorted(starts[p] + r for p, l, r, c in events if l == lane)
        gaps = [onsets[0]] + [b - a for a, b in zip(onsets, onsets[1:])] + [total_rows - onsets[-1]]
        lane_gaps[lane] = max(gaps)
        rest_frac[lane] = 1 - len(set(onsets)) / total_rows
    check('rests', all(v >= 0.20 for v in rest_frac.values())
          and lane_gaps[3] <= 48 and lane_gaps[4] <= 48 and lane_gaps[5] <= 80,
          'empty-row share per lane ' + '/'.join(f'{rest_frac[k]:.2f}' for k in range(6))
          + f'; melodic max gaps {lane_gaps[3]}/{lane_gaps[4]}, sparse lane 6 {lane_gaps[5]} rows')
    all_onsets = sorted(starts[p] + r for p, l, r, c in events)
    global_gap = max([all_onsets[0]] + [b - a for a, b in zip(all_onsets, all_onsets[1:])]
                     + [total_rows - all_onsets[-1]])
    check('no_extended_silence', global_gap <= 32,
          f'max all-lane onset gap {global_gap} rows = {global_gap * row_seconds:.3f} s')

    final = doc['patterns'][8]
    final_notes = [(r, c['note'], c['vel'], c.get('len', 1.0))
                   for lane in range(6) for r, c in enumerate(final['lanes'][lane]['cells']) if c]
    last_row = max(r for r, n, v, ln in final_notes)
    bass_end = [c['note'] for r, c in enumerate(final['lanes'][4]['cells']) if c and r >= 112]
    lead_end = [c['note'] for r, c in enumerate(final['lanes'][3]['cells']) if c and r >= 112]
    check('loopable_finite_end', last_row <= 120 and 'D-2' in bass_end and 'D-4' in lead_end
          and len(final_notes) >= 6,
          f'last onset pattern row {last_row}; final bar starts on bass D-2 and lead D-4; '
          f'{len(final_notes)} events in the 8-bar pattern')

    counts = [sum(1 for p, l, r, c in events if p // 3 == act) for act in range(3)]
    lane_counts = {score.LANES[k]: sum(1 for p, l, r, c in events if l == k) for k in range(6)}
    check('three_developed_acts', min(counts) >= 250 and counts[2] != counts[0]
          and counts[2] < counts[1],
          f'act event counts {counts}; return is substantial but not a copy of act 1')

    disk = (ROOT / 'score.json').read_text() if (ROOT / 'score.json').exists() else ''
    data = disk.encode()
    check('score_file_matches', disk == raw + '\n',
          'score.json equals a fresh build plus its trailing newline')
    check('deterministic', raw == again,
          'two builds are byte-identical, sha256 ' + hashlib.sha256(data).hexdigest())

    result = {
        'score': 'score.json', 'checker': 'check_score.py',
        'score_sha256': hashlib.sha256(data).hexdigest(), 'score_bytes': len(data),
        'passed': all(c['pass'] for c in checks), 'checks': checks,
        'timeline': {'bpm': score.BPM, 'key': score.key if hasattr(score, 'key') else 2,
                     'bars': 72, 'rows': total_rows, 'ticks': total_ticks,
                     'seconds': seconds, 'row_seconds': row_seconds,
                     'loop': doc['loop'], 'patterns': len(doc['chain'])},
        'acts': [{'name': score.ACTS[i], 'start_bar': i * 24, 'bars': 24,
                  'start_seconds': i * 40.0, 'patterns': list(range(i * 3, i * 3 + 3)),
                  'events': counts[i]} for i in range(3)],
        'lanes': {score.LANES[k]: {'events': lane_counts[score.LANES[k]],
                                   'max_onset_gap_rows': lane_gaps[k],
                                   'rest_fraction': round(rest_frac[k], 4)} for k in range(6)},
        'pitch': pitch,
        'gestures': {'A_syncopated_bars': gesture_a, 'B_half_time_bars': gesture_b},
        'velocity': {'min': min(vels), 'max': max(vels), 'levels': len(set(vels))},
        'silence': {'max_gap_rows': global_gap,
                    'max_gap_seconds': round(global_gap * row_seconds, 6),
                    'tail_rows': total_rows - all_onsets[-1]},
        'determinism': {'two_builds_identical': raw == again,
                        'sha256': hashlib.sha256(data).hexdigest()},
    }
    (ROOT / 'score-checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': result['passed'], 'timeline': result['timeline'],
                      'acts': result['acts'], 'gestures': result['gestures'],
                      'lanes': result['lanes'], 'failed': [c['name'] for c in checks if not c['pass']]},
                     indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
