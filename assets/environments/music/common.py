#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Small shared builder for the three original 120-second tracker-3 scores.

The real reader is hydrapy.tracker_v3.validate; this module only assembles
monophonic lanes and never reimplements or weakens that validator.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCORELIB = Path('/home/echevarian/dev/shared/claude/demos')
RUNTIME = Path('/home/echevarian/dev/shared/codex/nullrun-fullstack-20261031/runtime')
sys.path[:0] = [str(SCORELIB), str(RUNTIME)]

from scorelib import Score, hit                                  # noqa: E402
from hydrapy.tracker_v3 import TICKS, timeline, validate         # noqa: E402
from hydrapy.studio_tracker import note_midi                      # noqa: E402

BAR = 16
BARS = 8
ROWS = BAR * BARS
LANE_NAMES = ('kick', 'snare', 'hat/texture', 'lead', 'bass',
              'counterline/atmosphere')
MACHINES = (16, 17, 22, 0, 0, 0)
NOTE_NAMES = ('C-', 'C#', 'D-', 'D#', 'E-', 'F-', 'F#', 'G-', 'G#', 'A-', 'A#', 'B-')
SCALES = {
    0: (0, 2, 3, 5, 7, 8, 10),   # C minor
    2: (0, 2, 3, 5, 7, 8, 10),   # D minor
    5: (0, 2, 3, 5, 7, 8, 10),   # F minor
    7: (0, 2, 3, 5, 7, 8, 10),   # G minor
}
ROOT_MIDI = {0: 60, 2: 62, 5: 65, 7: 67}


def spell(midi):
    midi = int(midi)
    if not 24 <= midi <= 96:
        raise ValueError(f'MIDI {midi} outside 24..96')
    return f'{NOTE_NAMES[midi % 12]}{midi // 12 - 1}'


def degree_note(key, degree, base, low=24, high=96):
    scale = SCALES[key]
    octave, index = divmod(int(degree), 7)
    midi = int(base) + 12 * octave + scale[index]
    while midi < low:
        midi += 12
    while midi > high:
        midi -= 12
    if not low <= midi <= high:
        raise ValueError(f'degree {degree} left register {low}..{high}')
    return midi


class Builder:
    def __init__(self, bpm, key, seed, pattern_names):
        if len(pattern_names) > 16:
            raise ValueError('bounded score: at most 16 patterns')
        self.bpm = int(bpm)
        self.key = int(key)
        self.names = list(pattern_names)
        self.score = Score(bpm=bpm, key=key, seed=seed, names=LANE_NAMES, loop=False)
        self.patterns = [self.score.pattern(index, rate=1, bar=BAR, bars=BARS,
                                            name=name)
                         for index, name in enumerate(self.names)]
        self.events = {}

    def put(self, pattern, lane, bar, row, midi, vel=100, length=1.0):
        if not 0 <= pattern < len(self.patterns):
            raise ValueError(f'pattern {pattern}')
        if not 0 <= lane < 6:
            raise ValueError(f'lane {lane}')
        if not 0 <= bar < BARS or not 0 <= row < BAR:
            raise ValueError(f'{pattern}/{lane}/{bar}/{row}')
        midi = int(midi)
        if not 24 <= midi <= 96:
            raise ValueError(f'MIDI {midi} outside 24..96')
        key = (pattern, lane, bar * BAR + row)
        if key in self.events:
            raise ValueError(f'duplicate cell {key}')
        self.events[key] = (spell(midi), int(vel), float(max(0.25, min(16.0, length))))

    def fill(self, pattern, lane, bar, rows, midi, vel=100, length=1.0):
        for row in rows:
            self.put(pattern, lane, bar, row, midi, vel, length)

    def finish(self):
        for pattern in range(len(self.patterns)):
            for lane in range(6):
                events = sorted((row, value)
                                for (p, l, row), value in self.events.items()
                                if p == pattern and l == lane)
                cells = {}
                for index, (row, (note, vel, length)) in enumerate(events):
                    limit = (events[index + 1][0] - row) if index + 1 < len(events) else (ROWS - row)
                    cells[row] = hit(note, vel, len=max(0.25, min(length, limit, 16.0)))
                self.patterns[pattern].lane(lane, cells=cells, length=ROWS)
        self.score.chain(*range(len(self.patterns)), loop=False)
        for lane, machine in enumerate(MACHINES):
            self.score.sound(lane, machine=machine)
        return validate(self.score.doc)


def score_seconds(doc):
    tl = timeline(doc)
    return tl.cycle / TICKS * 60 / doc['bpm']


def write_score(path, doc):
    path.write_text(json.dumps(doc, indent=2) + '\n', encoding='utf-8')
    return path


def lane_events(doc):
    """(absolute_row, lane, cell) for every onset in the finite unlooped chain."""
    starts = {}
    row = 0
    for pattern in doc['chain']:
        starts[pattern] = row
        row += ROWS
    events = []
    for pattern in doc['chain']:
        for lane, data in enumerate(doc['patterns'][pattern]['lanes']):
            for offset, cell in enumerate(data['cells']):
                if cell is not None:
                    events.append((starts[pattern] + offset, lane, cell))
    return sorted(events), row
