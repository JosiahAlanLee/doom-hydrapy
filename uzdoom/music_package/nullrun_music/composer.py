# SPDX-License-Identifier: GPL-2.0-or-later
"""Seeded motif-grammar composer.

Every draw is content-addressed: Rng(hash_int(seed, profile, state, floor, bar)),
so the same (profile, seed, state, floor) composes the same material regardless
of evaluation order, and the same cue timeline always yields the same score.

Content model
-------------
* A Motif is a contour: steps of (row offset, scale-degree offset, velocity,
  gate rows). The source motif of a floor is carried across states by named
  transforms (prime/anticipation/diminution/rest/retrograde/register), so
  exploration, combat and boss music share recognizable material without
  re-rolling it.
* A Section is `bars` bars of six monophonic lanes; every note stays inside its
  bar (gate clipped), so loops wrap without stuck notes or overlaps.
* Lanes 0-1 percussion, 2 bass, 3 lead/counterline, 4 pad/drone, 5 reserved
  for stings (explicitly budgeted).
"""
from .rng import Rng, hash_int
from .scale import Scale, INTERVALS, clamp_midi
from .events import BAR

LANES = 6
PERC_LOW, PERC_HIGH, BASS, LEAD, PAD, STING = range(6)
STATE_RHYTHMS = ('exploration', 'threat', 'combat', 'quiet',
                 'boss_sealed', 'boss_exposed', 'boss_one_down')
TRANSFORMS = {
    # state -> (contour op, gate op, register shift, density)
    'exploration':  ('prime', 'as-is', 0, 1.0),
    'threat':       ('anticipation', 'as-is', 0, 0.8),
    'combat':       ('invert-odd', 'halve', 0, 1.4),
    'quiet':        ('drop', 'as-is', -12, 0.5),
    'boss_sealed':  ('retrograde', 'double', -12, 1.0),
    'boss_exposed': ('invert-odd', 'halve', 12, 1.6),
    'boss_one_down':('drop', 'as-is', -12, 0.7),
}


class Motif:
    def __init__(self, steps):
        self.steps = list(steps)  # (row, degree, vel, gate)

    def contour(self):
        return [s[1] for s in self.steps]


class Section:
    """One composition: bars of (row, midi, vel, gate, ghost) per lane."""
    def __init__(self, state, bars, loop, profile_id):
        self.state, self.bars, self.loop, self.profile_id = state, bars, loop, profile_id
        self.lanes = [[[] for _ in range(bars)] for _ in range(LANES)]
        self.sting_slots = []   # (bar, row) where the live document's FILL slots sit

    def add(self, lane, bar, row, midi, vel, gate, ghost=False):
        self.lanes[lane][bar].append((row, midi, vel, gate, ghost))

    def note_count(self):
        return sum(len(l) for lane in self.lanes for l in lane)


def _bar_rng(seed, profile, state, floor, bar):
    return Rng(hash_int(seed, profile['id'], state, floor, bar))


def _rows(stepstring, vel_base, vel_accent, rng, drop_last=False):
    """Parse a 16-character step string to (row, velocity) pairs."""
    out = []
    for row, ch in enumerate(stepstring):
        if ch == 'X':
            out.append((row, vel_accent))
        elif ch == 'x':
            out.append((row, vel_base))
    if drop_last and out:
        out.pop()
    return out


def _source_motif(profile, seed, floor):
    """The floor's source contour: what every state of the floor varies."""
    rng = Rng(hash_int(seed, profile['id'], 'source-motif', floor))
    pulses = profile['motif']['pulses']
    span_lo, span_hi = profile['motif']['spans']
    steps, row, degree = [], 0, 0
    for _ in range(max(4, round(16 * profile['motif']['density']))):
        pulse = rng.pick(pulses)
        gate = rng.randint(1, 3)
        steps.append([row, degree, 0, gate])
        degree = max(-12, min(12, degree + rng.pick(pulse)))
        row = min(16, row + rng.randint(span_lo, span_hi))
        if row >= 16:
            break
    return Motif(steps)


def _transform(motif, kind, state, rng):
    steps = [[r, d, v, g] for r, d, v, g in motif.steps]
    if kind == 'prime':
        pass
    elif kind == 'anticipation':
        steps = [[max(0, r - 1), d, v, 1] for r, d, v, g in steps]
        steps.insert(0, [0, 0, 0, 1])
    elif kind == 'invert-odd':
        for i in range(1, len(steps), 2):
            steps[i][1] = -steps[i][1]
        steps = [[r // 2, d, v, max(1, g // 2)] for r, d, v, g in steps]
    elif kind == 'drop':
        steps = steps[::2][:4]
    elif kind == 'retrograde':
        steps.reverse()
        steps = [[r, d, v, min(6, g * 2)] for r, d, v, g in steps]
    else:
        raise ValueError(kind)
    for s in steps:
        if state == 'quiet' and rng.chance(25):
            s[3] = 0  # a swallowed step becomes a rest of the same length
    return Motif([s for s in steps if s[3] > 0])


def _lead_notes(profile, scale, chord_root_deg, motif, rhythm, bar_rng, state):
    """Place the bar's motif steps onto the profile's lead register."""
    rows = sorted(rhythm['motif_rows'])
    if not rows or not motif.steps:
        return []
    lo, hi = profile['register']['lead']
    out, placed = [], 0
    for row in rows:
        if placed >= len(motif.steps):
            break
        _, degree, _, gate = motif.steps[placed]
        midi = clamp_midi(scale.degree(chord_root_deg + degree, 3), lo, hi)
        vel = 74 + bar_rng.randint(0, 20)
        gate = max(1, min(gate if gate else 2, 16 - row))
        out.append((row, midi, vel, gate))
        placed += 1
    return out


def _pad_notes(profile, scale, chord_deg, rows, bar_rng, tense=False):
    """One held tone per row: the pad is a single drone voice (the tracker3
    cell model is one note per row per lane, so chords belong to stings)."""
    lo, hi = profile['register']['pad']
    midi = clamp_midi(scale.degree(chord_deg, 3), lo, hi)
    if tense:  # threat/boss pedal: flatten toward the scale's uneasy interval
        midi = clamp_midi(scale.degree(chord_deg, 3) - 1, lo, hi)
    return [(row, midi, 58 + bar_rng.randint(0, 8), min(16, 14)) for row in rows]


def compose_section(profile, seed, state, floor, env=''):
    """Compose one loop section: `bars` bars of six lanes, wrapped cleanly."""
    rhythm_name = state if state in STATE_RHYTHMS else 'exploration'
    rhythm = profile['rhythms'][rhythm_name]
    bars = profile['bars_per_loop']
    scale = Scale(profile['key'], INTERVALS[profile['scale']])
    harmony = profile['harmony']
    source = _source_motif(profile, seed, floor)
    contour_op, gate_op, register_shift, _ = TRANSFORMS[rhythm_name]
    section = Section(state, bars, True, profile['id'])
    ghost_prob = profile['ghost_prob']

    for bar in range(bars):
        rng = _bar_rng(seed, profile, state, floor, bar)
        chord_deg = harmony[bar % len(harmony)]
        drop_last = (profile['id'] == 'after_hours_pavilion' and bar == bars - 1)

        # Lane 0/1: percussion from the state's step strings.
        for lane, key, midi, vel_base, vel_acc in (
                (PERC_LOW, 'perc_low', profile['register']['perc_low'], 96, 110),
                (PERC_HIGH, 'perc_high', profile['register']['perc_high'], 70, 88)):
            for row, vel in _rows(rhythm[key], vel_base, vel_acc, rng, drop_last and lane == PERC_LOW):
                if lane == PERC_HIGH and rng.chance(ghost_prob):
                    continue  # a ghosted tick: the cell is simply absent this bar
                section.add(lane, bar, row, midi, vel, 1)

        # Lane 2: bass on chord roots.
        bass_rows = _rows(rhythm['bass'], 88, 98, rng)
        bass_midi = clamp_midi(scale.degree(chord_deg, 1), *profile['register']['bass'])
        for row, vel in bass_rows:
            gate = 16 - row if row == 0 and profile['id'] == 'drowned_records' else min(6, 16 - row)
            section.add(BASS, bar, row, bass_midi, vel, gate)

        # Lane 3: the floor's motif, varied per state and per bar.
        motif = _transform(source, contour_op, state, rng)
        for row, midi, vel, gate in _lead_notes(profile, scale, chord_deg, motif, rhythm, rng, state):
            midi = clamp_midi(midi + register_shift, *profile['register']['lead'])
            if state in ('exploration', 'quiet') and rng.chance(ghost_prob // 2):
                continue  # a swallowed phrase step: rest, not repetition
            section.add(LEAD, bar, row, midi, vel, gate)

        # Lane 4: pad, tense for threat/boss pressure.
        tense = state in ('threat', 'boss_sealed', 'boss_one_down')
        for row, midi, vel, gate in _pad_notes(profile, scale, chord_deg, rhythm['pad_rows'], rng, tense):
            section.add(PAD, bar, row, midi, vel, gate)

        # Lane 5: the sting voice. Empty in loop sections; the live-contract
        # FILL slots are exported by export_tracker from section.sting_slots.
        section.sting_slots.append((bar, 0))

    return section


def compose_fill_bar(profile, seed, state, floor, bar_index):
    """One denser bar used as the outgoing fill before a section switch."""
    rhythm = dict(profile['rhythms']['combat'])
    bars = profile['bars_per_loop']
    scale = Scale(profile['key'], INTERVALS[profile['scale']])
    chord_deg = profile['harmony'][bar_index % len(profile['harmony'])]
    rng = _bar_rng(seed, profile, state, floor, bar_index)
    section = Section('fill', 1, False, profile['id'])
    for lane, key, midi, vb, va in (
            (PERC_LOW, 'perc_low', profile['register']['perc_low'], 96, 116),
            (PERC_HIGH, 'perc_high', profile['register']['perc_high'], 74, 96)):
        for row, vel in _rows(rhythm[key], vb, va, rng):
            section.add(lane, 0, row, midi, vel, 1)
    source = _source_motif(profile, seed, floor)
    motif = _transform(source, 'invert-odd', 'combat', rng)
    for row, midi, vel, gate in _lead_notes(profile, scale, chord_deg, motif, rhythm, rng, 'combat'):
        section.add(LEAD, 0, row, midi, vel, gate)
    bass_midi = clamp_midi(scale.degree(chord_deg, 1), *profile['register']['bass'])
    for row, vel in _rows(rhythm['bass'], 92, 102, rng):
        section.add(BASS, 0, row, bass_midi, vel, min(3, 16 - row))
    return section


def compose_transition(profile, seed, kind, floor):
    """Through-composed one-shot sections: victory cadence, death, floor bridge."""
    spec = profile['transition'][kind]  # kind: 'victory', 'death', 'bridge'
    scale = Scale(profile['key'], INTERVALS[profile['scale']])
    source = _source_motif(profile, seed, floor)
    section = Section(kind, spec['bars'], False, profile['id'])
    for bar in range(spec['bars']):
        rng = _bar_rng(seed, profile, kind, floor, bar)
        chord_deg = spec['degrees'][min(bar, len(spec['degrees']) - 1)]
        lead_rows = [0, 4, 8, 12][: max(2, spec['bars'] - bar)]
        if kind == 'victory':
            motif = _transform(source, 'retrograde', 'boss_sealed', rng)
            register = 4
        elif kind == 'death':
            motif = _transform(_transform(source, 'drop', 'quiet', rng), 'retrograde', 'boss_sealed', rng)
            register = 2
        else:
            motif = _transform(source, 'anticipation', 'threat', rng)
            register = 3
        for i, row in enumerate(lead_rows):
            if i >= len(motif.steps):
                break
            _, degree, _, gate = motif.steps[i]
            midi = clamp_midi(scale.degree(chord_deg + degree, register), *profile['register']['lead'])
            section.add(LEAD, bar, row, midi, 84 + rng.randint(0, 16), max(1, min(gate, 16 - row)))
        bass_midi = clamp_midi(scale.degree(chord_deg, 1), *profile['register']['bass'])
        for row in ([0, 8, 12] if kind == 'death' else [0, 8]):
            section.add(BASS, bar, row, bass_midi, 92, min(8, 16 - row))
        if bar == spec['bars'] - 1:
            # Final bar of a one-shot: cadence tone, held, ends the section.
            for i, tone in enumerate(scale.chord(chord_deg, 3)):
                midi = clamp_midi(tone, *profile['register']['pad'])
                section.add(PAD, bar, 4 + i * 2, midi, 84, 12)  # spread over rows
        else:
            for row, midi, vel, gate in _pad_notes(profile, scale, chord_deg, [0], rng, kind == 'death'):
                section.add(PAD, bar, row, midi, vel, gate)
        if kind == 'death':
            for row, vel in _rows('X...............', 96, 108, rng):
                section.add(PERC_LOW, bar, row, profile['register']['perc_low'], vel, 1)
    return section


def compose_sting(profile, seed, sting_kind, cue_id):
    """A short response on the reserved sting lane, from the profile's vocab."""
    spec = profile['stings'].get(sting_kind) or profile['stings']['enemy']
    rng = Rng(hash_int(seed, profile['id'], 'sting', sting_kind, cue_id))
    notes = []
    for midi in spec['notes']:
        notes.append({'lane': STING, 'midi': midi, 'vel': min(127, spec['vel'] + rng.randint(-6, 6)),
                      'gate': spec['gate']})
    return notes


def composer_selfcheck(profile):
    """Structural guarantees the composer promises (called by the tests)."""
    assert len(profile['harmony']) == profile['bars_per_loop']
    for state in STATE_RHYTHMS:
        rhythm = profile['rhythms'][state]
        assert len(rhythm['perc_low']) == 16 and len(rhythm['perc_high']) == 16 and len(rhythm['bass']) == 16
        assert all(0 <= r < 16 for r in rhythm['motif_rows'] + rhythm['pad_rows'])
    return True


def finalize_bar(section, bar_idx):
    """The bar's playable cells, per lane: sorted by row, gates clipped to the
    next hit and to the bar end. The single source of truth for both the
    canonical engine and the tracker3 exports, so the two never disagree."""
    out = [[] for _ in range(LANES)]
    for lane in range(LANES):
        cells = sorted(section.lanes[lane][bar_idx])
        for i, (row, midi, vel, gate, *_rest) in enumerate(cells):
            end_row = 16
            if i + 1 < len(cells):
                end_row = min(end_row, cells[i + 1][0])
            gate = max(1, min(gate, end_row - row))
            out[lane].append((row, midi, vel, gate))
    return out
