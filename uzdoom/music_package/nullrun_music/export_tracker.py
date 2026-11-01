# SPDX-License-Identifier: GPL-2.0-or-later
"""hydrapy-tracker-3 exports, validated by the frozen tracker3 validator.

Two export families:

* Section documents -- the pattern bank. One looping document per
  (profile, section): what a live host loads with `tracker_score` when the
  director enters a section. Sting slots ride in lane 5 as FILL cells, so a
  `tracker_transport` FILL pulse triggers the fallback sting path.
* The story stitch -- one non-looping document whose chain plays a fixed
  timeline exactly (the static/dynamic boundary: a stitch covers a known
  timeline; live adaptation is host work, see INTEGRATION.md).

Pattern indices are stable and documented in exports/pattern_index.json.
"""
import copy
import json

from .events import BAR, ROW
from .scale import midi_to_name
from .composer import compose_sting, finalize_bar

try:  # frozen HydraPy on PYTHONPATH (required only for validation)
    from hydrapy.tracker_v3 import FORMAT, empty_pattern, validate
    from hydrapy.tracker_v3 import evaluate as tracker_evaluate
except ImportError:  # pragma: no cover
    FORMAT = 'hydrapy-tracker-3'
    empty_pattern = validate = tracker_evaluate = None

PATTERN_COUNT = 128

SECTION_INDEX = {
    # stable pattern slot per section kind (exports/pattern_index.json)
    'exploration': 0, 'threat': 1, 'combat': 2, 'quiet': 3,
    'boss_sealed': 4, 'boss_exposed': 5, 'boss_one_down': 6,
    'victory': 7, 'death': 8, 'bridge': 9,
}
STING_ROTATION = ('enemy', 'damage', 'secret', 'boss')


def _document(profile, loop, pattern, chain, seed):
    doc = {
        'format': FORMAT, 'bpm': profile['tempo'], 'key': profile['key'],
        'sound': False, 'loop': loop, 'pattern': pattern, 'chain': chain,
        'seed': seed & 0xFFFFFFFF, 'mutes': [False] * 6, 'scene': 0,
        'modes': {'program': 'o0', 'aux': 'o1'},
        'bindings': {'z': 'Dolly Z', 'roll': 'Roll', 'feedback': 'Feedback'},
        'lanes': [{'name': n} for n in profile['lanes']['names']],
        'sounds': [{'machine': None, 'params': {}} for _ in range(6)],
        'patterns': [None] * PATTERN_COUNT,
    }
    for i in range(PATTERN_COUNT):
        if doc['patterns'][i] is None:
            doc['patterns'][i] = empty_pattern(i) if empty_pattern else None
    return doc


def _empty_bar_pattern():
    """A silent bar: the stitch's chain has no gaps, so silence is a bar too."""
    lanes = [{'len': 16, 'cells': [None] * 16, 'transforms': []} for _ in range(6)]
    return {'name': 'story-empty', 'rate': 1, 'bar': 16, 'bars': 1,
            'lanes': lanes, 'keys': {'z': [], 'roll': [], 'feedback': []},
            'easing': {'z': 'smooth', 'roll': 'smooth', 'feedback': 'smooth'},
            'scenes': []}


def _bar_pattern(profile, section, bar_idx, name, sting_slots=False):
    """One bar of a Section as a tracker3 pattern (16 rows, rate 1)."""
    rows = 16
    lanes = []
    cells = finalize_bar(section, bar_idx)
    for lane in range(6):
        out = [None] * rows
        for row, midi, vel, gate in cells[lane]:
            if row >= rows:
                continue
            out[row] = {'note': midi_to_name(midi), 'vel': int(vel), 'len': float(gate)}
        if sting_slots and lane == 5:
            sting = profile['stings'][STING_ROTATION[bar_idx % len(STING_ROTATION)]]
            out[0] = {'note': midi_to_name(sting['notes'][0]), 'vel': int(sting['vel']),
                      'len': float(min(sting['gate'], 4)), 'cond': {'kind': 'fill'}}
        lanes.append({'len': rows, 'cells': out, 'transforms': []})
    pattern = {'name': name[:40], 'rate': 1, 'bar': 16, 'bars': 1,
               'lanes': lanes, 'keys': {'z': [], 'roll': [], 'feedback': []},
               'easing': {'z': 'smooth', 'roll': 'smooth', 'feedback': 'smooth'},
               'scenes': []}
    return pattern


def _bars_pattern(profile, section, name):
    """A whole Section as one pattern (16 rows per bar, at most 8 bars)."""
    bars = len(section.lanes[0])
    rows = 16 * bars
    lanes = []
    cells_by_lane = [finalize_bar(section, bar) for bar in range(bars)]
    for lane in range(6):
        out = [None] * rows
        for bar in range(bars):
            for row, midi, vel, gate in cells_by_lane[bar][lane]:
                out[bar * 16 + row] = {'note': midi_to_name(midi), 'vel': int(vel),
                                       'len': float(min(gate, 16))}
        lanes.append({'len': rows, 'cells': out, 'transforms': []})
    return {'name': name[:40], 'rate': 1, 'bar': 16, 'bars': bars,
            'lanes': lanes, 'keys': {'z': [], 'roll': [], 'feedback': []},
            'easing': {'z': 'smooth', 'roll': 'smooth', 'feedback': 'smooth'},
            'scenes': []}


def section_document(profile, section, seed, sting_slots=True):
    """One looping document for a loop section (validated)."""
    index = SECTION_INDEX[section.state]
    doc = _document(profile, True, index, [index], seed)
    doc['patterns'][index] = _bars_pattern(profile, section,
                                           f'{profile["id"][:12]}-{section.state}')
    return validate(doc) if validate else doc


def transition_document(profile, section, seed):
    """One non-looping document for a through-composed section (validated)."""
    index = SECTION_INDEX[section.state]
    bars = len(section.lanes[0])
    # Reuse one pattern per bar: chain walks them in order (the tracker3
    # timeline cycles its chain; hosts stop the transport at the section end).
    doc = _document(profile, False, index, [index] * bars, seed)
    for bar in range(bars):
        slot = index if bar == 0 else min(PATTERN_COUNT - 1, 16 + (index * 8) + bar)
        doc['patterns'][slot] = _bar_pattern(profile, section, bar,
                                             f'{profile["id"][:10]}-{section.state}{bar}')
    doc['chain'] = [index] + [min(PATTERN_COUNT - 1, 16 + (index * 8) + bar)
                              for bar in range(1, bars)]
    return validate(doc) if validate else doc


def story_stitch(profiles, schedule, seed, name='story'):
    """One static document playing the canonical schedule exactly.

    Bars become patterns (deduplicated by content); stings ride as plain cells
    at their exact rows; ducked notes keep their lower... (ducking is applied
    by velocity: the canonical schedule marks ducked notes, the stitch lowers
    them 40%, documented approximation). Raises RuntimeError past 128 distinct
    bars -- a static stitch's documented limit.
    """
    # Reconstruct bar content per section from the schedule's control events.
    from .composer import compose_section, compose_transition
    profile_by_env = {p['id']: p for p in profiles.values()}
    # Walk bars from each control event to the next, materializing bar patterns.
    # The walk is continuous across control ticks (a mid-bar duck window must
    # not split a bar in two), and bars advance with the section's own grid.
    ticks = sorted({c.tick for c in schedule.controls} | {0, schedule.meta['end_tick']})
    pattern_by_content = {}
    chain = []
    stings = {}
    for note in schedule.notes:
        if ':sting:' in note.origin:
            stings.setdefault(note.tick, []).append(note)
    active = None
    next_bar = 0
    for i in range(len(ticks) - 1):
        start, end = ticks[i], ticks[i + 1]
        for control in schedule.controls:
            if control.tick == start:
                if control.kind == 'section':
                    env = control.payload.get('env') or schedule.profile
                    profile = profile_by_env[env]
                    content = (compose_section(profile, schedule.seed, control.payload['state'],
                                               control.payload['floor'], env)
                               if control.payload['state'] in ('exploration', 'threat',
                                                               'combat', 'quiet', 'boss_sealed',
                                                               'boss_exposed', 'boss_one_down')
                               else compose_transition(profile, schedule.seed,
                                                       control.payload['state'],
                                                       control.payload['floor']))
                    active = (profile, content, control.payload['state'], control.tick)
                    next_bar = max(next_bar, control.tick)
                elif control.kind == 'transition':
                    env = control.payload.get('env') or schedule.profile
                    profile = profile_by_env[env]
                    content = compose_transition(profile, schedule.seed,
                                                 control.payload['kind'],
                                                 control.payload.get('floor', 0))
                    active = (profile, content, control.payload['kind'], control.tick)
                    next_bar = max(next_bar, control.tick)
                elif control.kind in ('all_off', 'silence'):
                    active = None
        if active is None:
            # Silence is a bar too: the chain's tick mapping stays aligned
            # with the canonical schedule across all-off windows.
            while next_bar + BAR <= end:
                key = json.dumps(_empty_bar_pattern(), sort_keys=True)
                if key not in pattern_by_content:
                    if len(pattern_by_content) >= PATTERN_COUNT - 2:
                        raise RuntimeError('Story stitch exceeds 128 distinct bars')
                    pattern_by_content[key] = len(pattern_by_content)
                chain.append(pattern_by_content[key])
                next_bar += BAR
            continue
        profile, content, state, section_start = active
        bar_len = len(content.lanes[0])
        while next_bar + BAR <= end:
            bar_idx = int((next_bar - section_start) // BAR)
            if not content.loop and bar_idx >= bar_len:
                break
            key = json.dumps(_bar_pattern(profile, content, bar_idx % bar_len, '', sting_slots=False),
                             sort_keys=True)
            if key not in pattern_by_content:
                if len(pattern_by_content) >= PATTERN_COUNT - 2:
                    raise RuntimeError('Story stitch exceeds 128 distinct bars')
                pattern_by_content[key] = len(pattern_by_content)
            chain.append(pattern_by_content[key])
            next_bar += BAR
    if len(chain) > 256:
        raise RuntimeError('Story stitch exceeds the 256-entry chain')
    env0 = schedule.profile
    profile = profile_by_env[env0]
    doc = _document(profile, False, 0, chain, seed)
    # Fill in the deduplicated bar patterns; index 0 must be a real pattern.
    items = sorted(pattern_by_content.items(), key=lambda kv: kv[1])
    for key, idx in items:
        pattern = json.loads(key)
        pattern['name'] = f'story-{idx + 1:02d}'
        if pattern['name'] in {p['name'] for p in doc['patterns'] if p}:
            pattern['name'] = f'story-{idx + 1:02d}x'
        doc['patterns'][idx] = pattern
    # Sting chords at their rows: tracker3 gives one cell per row per lane, so
    # a chord's tones spread by one row (15.6 ms at 96 BPM), a documented
    # approximation of the canonical simultaneous stab.
    for tick, notes in stings.items():
        entry = None
        offset = 0
        for e, slot in enumerate(chain):
            w = ROW * 16 // 1
            if offset <= tick < offset + w:
                entry, row = e, (tick - offset) // ROW
                break
            offset += w
        if entry is None:
            continue
        lane_cells = doc['patterns'][chain[entry]]['lanes'][5]['cells']
        for i, note in enumerate(sorted(notes, key=lambda n: n.midi)):
            cell_row = min(15, row + i)
            lane_cells[cell_row] = {'note': midi_to_name(note.midi), 'vel': note.vel,
                                    'len': min(4.0, max(0.25, note.gate / ROW))}
    return validate(doc) if validate else doc


def export_all(profiles, seed, out_folder, sections=None, env='drowned_records', floor=0):
    """Write section + transition documents for every profile; returns paths."""
    from .composer import compose_section, compose_transition
    out_folder.mkdir(parents=True, exist_ok=True)
    written = []
    index_map = {}
    for pid, profile in profiles.items():
        for state in ('exploration', 'threat', 'combat', 'quiet',
                      'boss_sealed', 'boss_exposed', 'boss_one_down'):
            content = compose_section(profile, seed, state, floor, env)
            doc = section_document(profile, content, seed)
            path = out_folder / f'{pid}__{state}.json'
            path.write_text(json.dumps(doc, indent=1) + '\n')
            written.append(path)
            index_map[f'{pid}:{state}'] = SECTION_INDEX[state]
        for kind in ('victory', 'death', 'bridge'):
            content = compose_transition(profile, seed, kind, floor)
            doc = transition_document(profile, content, seed)
            path = out_folder / f'{pid}__{kind}.json'
            path.write_text(json.dumps(doc, indent=1) + '\n')
            written.append(path)
            index_map[f'{pid}:{kind}'] = SECTION_INDEX[kind]
    (out_folder / 'pattern_index.json').write_text(
        json.dumps({'section_pattern_slots': SECTION_INDEX,
                    'documents': {str(p): str(p.relative_to(out_folder)) for p in written},
                    'note': 'loop documents use loop=true and pattern=slot; '
                            'transition documents chain their bars'}, indent=2) + '\n')
    return written, index_map
