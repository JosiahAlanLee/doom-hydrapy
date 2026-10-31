#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Threshold: one original 120-second six-lane Gorgon score.

144 BPM, 4/4, rate 1, 16 rows per bar, 72 bars, 9 chained 8-bar patterns,
loop off. Three 40-second acts: foyer/landmark, works descent, return/escape.
D minor with Phrygian b2 colour. Gesture A is a syncopated 3-3-2 drive; gesture
B is a half-time cable-stomp. No earlier melody or rhythm is quoted.

Run: ~/miniconda3/envs/hydrapy/bin/python score.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCORELIB = Path('/home/echevarian/dev/shared/claude/demos')
RUNTIME = Path('/home/echevarian/dev/shared/codex/nullrun-fullstack-20261031/runtime')
sys.path[:0] = [str(SCORELIB), str(RUNTIME)]

from scorelib import Score, hit                                  # noqa: E402

BPM, SEED = 144, 0x7A11E5
BAR, BARS = 16, 8
PATTERNS, ACTS = 9, ('threshold-foyer', 'works-descent', 'return-escape')
LANES = ['kick', 'snare', 'hat', 'riff/lead', 'bass', 'ambient/counterline']
NAMES = ['C-', 'C#', 'D-', 'D#', 'E-', 'F-', 'F#', 'G-', 'G#', 'A-', 'A#', 'B-']
# D natural minor with Eb (b2) as the Phrygian colour; no other accidentals.
SCALE = (0, 2, 3, 5, 7, 8, 10)
ROOTS = {
    'I': [0, 0, 5, 5, 3, 3, 0, 0],       # Dm Dm Bb Bb Gm Gm Dm Dm
    'II': [0, 0, 5, 5, 3, 3, 4, 4],      # Dm Dm Bb Bb Gm Gm Am Am
    'III': [0, 0, 5, 5, 2, 2, 0, 0],     # Dm Dm Bb Bb F F Dm Dm
    'END': [0, 0, 5, 5, 2, 2, 0, 0],
}
EV = {}


def spell(m):
    return f'{NAMES[m % 12]}{m // 12 - 1}'


def deg(d, base=62):
    o, i = divmod(d, 7)
    return base + 12 * o + SCALE[i]


def bass_note(d, base=38):
    m = deg(d, base)
    while m > 53:
        m -= 12
    while m < 29:
        m += 12
    return m


def lead_note(d, base=62):
    m = deg(d, base)
    while m > 81:
        m -= 12
    while m < 57:
        m += 12
    return m


def put(pat, lane, bar, row, pitch, vel, ln=1):
    r = bar * BAR + row
    if not (0 <= pat < PATTERNS and 0 <= bar < BARS and 0 <= row < BAR):
        raise ValueError((pat, lane, bar, row))
    if isinstance(pitch, int):
        if not 21 <= pitch <= 108:
            raise ValueError('pitch out of range')
    key = (pat, lane, r)
    if key in EV:
        raise ValueError(f'duplicate cell {key}')
    EV[key] = (pitch, int(vel), float(max(0.25, ln)))


# -- gesture helpers ---------------------------------------------------------
def kick_A(pat, vel=112):
    for bar in range(BARS):
        for row in (0, 3, 6, 8, 11, 14):
            put(pat, 0, bar, row, 36, vel if row in (0, 8) else vel - 14)


def kick_B(pat, vel=106):
    for bar in range(BARS):
        for row in ((0, 6, 10) if bar % 4 != 3 else (0, 6, 10, 14)):
            put(pat, 0, bar, row, 36, vel if row == 0 else vel - 12)


def snare_A(pat, vel=98):
    for bar in range(BARS):
        put(pat, 1, bar, 4, 38, vel)
        put(pat, 1, bar, 12, 38, vel - 4)
        if bar % 4 == 3:
            put(pat, 1, bar, 15, 38, vel - 30)


def snare_B(pat, vel=104):
    for bar in range(BARS):
        put(pat, 1, bar, 8, 38, vel)
        if bar % 2 == 1:
            put(pat, 1, bar, 15, 38, 48)


def hats8(pat, vel=44, bar_from=0, bar_to=BARS):
    for bar in range(bar_from, bar_to):
        for j, row in enumerate((0, 2, 4, 6, 8, 10, 12, 14)):
            put(pat, 2, bar, row, 42, vel + (8 if j % 2 else 0))


def hats16(pat, vel=40):
    for bar in range(BARS):
        for row in range(16):
            put(pat, 2, bar, row, 42, vel + (10 if row % 4 == 2 else 0)
                - (6 if row % 2 else 0))


def bass_bar(pat, bar, root, offsets=(0, 0, 4, 0, 7, 0), rows=(0, 3, 6, 8, 11, 14),
             base=38, lens=(2, 1, 2, 1, 2, 2), vel=104):
    for j, row in enumerate(rows):
        put(pat, 4, bar, row, bass_note(root + offsets[j % len(offsets)], base),
            vel - (j % 2) * 8, lens[j % len(lens)])


def bass_chug(pat, bar, root, base=38, vel=108):
    rows = (0, 1, 2, 4, 6, 7, 8, 10, 12, 13, 14)
    offs = (0, 0, 7, 0, 4, 0, 7, 0, 0, 7, 0)
    for j, row in enumerate(rows):
        put(pat, 4, bar, row, bass_note(root + offs[j], base), vel - (j % 3) * 6, 1)


def bass_long(pat, bar, root, base=38, vel=100):
    for row, off, ln in ((0, 0, 5), (8, 4, 4), (14, 7, 2)):
        put(pat, 4, bar, row, bass_note(root + off, base), vel - (0 if row == 0 else 10), ln)


def lead_motif(pat, bar, root, base=62, vel=100, answer=False):
    if not answer:
        cell = ((0, 0, 2), (2, 2, 1), (3, 1, 2), (6, 0, 1),
                (8, -1, 2), (10, 0, 1), (11, 2, 1), (14, 4, 2))
    else:
        cell = ((0, 3, 2), (3, 2, 1), (6, 1, 1), (8, 0, 3),
                (12, -1, 2), (14, 0, 1))
    for row, off, ln in cell:
        midi = lead_note(root + off, base)
        put(pat, 3, bar, row, midi, vel - (3 if row % 4 else 0), ln)


def lead_ng(pat, bar, root, base=64, vel=104):
    """Angular short gesture; Eb (b2) and the fifth carry the tension."""
    cell = ((0, 0, 1), (3, 1, 1), (6, 4, 1), (10, 0, 1), (13, 1, 2), (15, 4, 1))
    for row, off, ln in cell:
        put(pat, 3, bar, row, lead_note(root + off, base), vel - (row % 3) * 4, ln)


def counter(pat, bar, row, pitch, vel=66, ln=6):
    put(pat, 5, bar, row, pitch, vel, ln)


# -- nine patterns -----------------------------------------------------------
def p0():
    for bar in range(8):
        root = ROOTS['I'][bar]
        if bar < 2:
            for row in (0, 8):
                put(0, 0, bar, row, 36, 96)
            put(0, 4, bar, 0, bass_note(root, 38), 82, 8)
        elif bar < 4:
            for row in (0, 3, 8, 11):
                put(0, 0, bar, row, 36, 100 if row == 0 else 86)
            for row, off, ln in ((0, 0, 4), (8, 4, 4), (14, 0, 2)):
                put(0, 4, bar, row, bass_note(root + off, 38), 88, ln)
        else:
            for row in (0, 3, 6, 8, 11, 14):
                put(0, 0, bar, row, 36, 106 if row in (0, 8) else 90)
            bass_bar(0, bar, root, vel=96)
            put(0, 1, bar, 4, 38, 88)
            put(0, 1, bar, 12, 38, 84)
        for row in (2, 6, 10, 14):
            put(0, 2, bar, row, 42, 38)
    for bar, row, pitch, ln, vel in ((0, 0, 62, 6, 78), (0, 8, 63, 4, 70),
                                     (1, 4, 65, 4, 76), (1, 12, 62, 4, 72),
                                     (2, 6, 63, 4, 74), (3, 0, 60, 4, 72),
                                     (3, 8, 62, 2, 80), (3, 11, 57, 2, 70),
                                     (3, 14, 62, 2, 76)):
        put(0, 3, bar, row, pitch, vel, ln)
    for bar in range(4, 8):
        lead_motif(0, bar, ROOTS['I'][bar], base=62, vel=92, answer=bar % 2 == 1)
    counter(0, 4, 6, 69, 58, 8)
    counter(0, 6, 10, 77, 62, 6)


def p1():
    kick_A(1)
    snare_A(1)
    hats8(1)
    for bar in range(8):
        root = ROOTS['I'][bar]
        bass_bar(1, bar, root, vel=106)
        lead_motif(1, bar, root, base=62, vel=100, answer=bar % 2 == 1)
    counter(1, 1, 10, 74, 62, 6)
    counter(1, 3, 6, 72, 58, 8)
    counter(1, 5, 12, 69, 60, 4)
    counter(1, 7, 2, 77, 64, 6)


def p2():
    kick_A(2, vel=116)
    snare_A(2, vel=104)
    for bar in range(8):
        for row in (4, 5, 6, 7, 12, 13, 14, 15):
            put(2, 2, bar, row, 42, 46 if row % 2 else 38)
        for row in (0, 2, 8, 10):
            put(2, 2, bar, row, 42, 48)
    for bar in range(8):
        root = ROOTS['I'][bar]
        rows = (0, 1, 2, 4, 6, 8, 9, 10, 12, 14, 15)
        offs = (0, 0, 4, 0, 7, 0, 4, 0, 7, 0, 4)
        for j, row in enumerate(rows):
            put(2, 4, bar, row, bass_note(root + offs[j], 38), 106 - (j % 3) * 6, 1)
    for bar, line in enumerate((
        (0, 62), (3, 65), (6, 67), (10, 69),
        (0, 70), (3, 69), (6, 67), (10, 65),
        (0, 63), (3, 62), (6, 60), (10, 62),
        (0, 60), (3, 62), (6, 63), (10, 62))):
        put(2, 3, bar // 4, line[0], line[1], 106, 2)
    for bar in range(4, 8):
        lead_motif(2, bar, ROOTS['I'][bar], base=62, vel=108, answer=bar % 2 == 1)
    counter(2, 2, 12, 69, 60, 8)
    counter(2, 5, 6, 74, 66, 8)
    counter(2, 7, 14, 75, 56, 2)


def p3():
    kick_B(3)
    snare_B(3)
    for bar in range(8):
        for j, row in enumerate((0, 4, 8, 12)):
            put(3, 2, bar, row, 42, 34 + (6 if j % 2 else 0))
        if bar == 7:
            for row in (13, 14, 15):
                put(3, 2, bar, row, 42, 48)
    for bar in range(8):
        bass_long(3, bar, ROOTS['II'][bar], vel=104)
    slow = ((0, 0, 6, 86), (1, 1, 6, 82), (2, 2, 8, 92), (3, 0, 4, 84),
            (4, 3, 6, 88), (5, 4, 8, 94), (6, 5, 4, 86), (7, 4, 8, 90))
    for bar, off, ln, vel in slow:
        put(3, 3, bar, 0, deg(off, 62), vel, ln)
    put(3, 3, 3, 6, 63, 74, 2)
    put(3, 3, 6, 10, 63, 80, 2)
    counter(3, 1, 12, 74, 52, 4)
    counter(3, 3, 8, 77, 58, 6)
    counter(3, 5, 12, 72, 54, 4)
    counter(3, 7, 8, 75, 60, 6)


def p4():
    for bar in range(8):
        for row in (0, 2, 4, 7, 8, 10, 12, 15):
            put(4, 0, bar, row, 36, 112 if row in (0, 8) else 96)
        put(4, 1, bar, 4, 38, 104)
        put(4, 1, bar, 12, 38, 100)
        if bar % 2:
            put(4, 1, bar, 15, 38, 62)
    hats16(4, 42)
    for bar in range(8):
        bass_chug(4, bar, ROOTS['II'][bar], vel=110)
        lead_ng(4, bar, ROOTS['II'][bar], base=74, vel=108)
    counter(4, 1, 4, 77, 64, 4)
    counter(4, 3, 12, 75, 60, 4)
    counter(4, 5, 4, 79, 66, 4)
    counter(4, 7, 12, 74, 56, 4)


def p5():
    for bar in range(8):
        for row in (0, 3, 4, 6, 8, 11, 12, 14):
            put(5, 0, bar, row, 36, 118 if row in (0, 8) else 100)
        put(5, 1, bar, 4, 38, 110)
        put(5, 1, bar, 12, 38, 106)
        if bar % 4 == 3:
            for row in (14, 15):
                put(5, 1, bar, row, 38, 82)
    hats16(5, 46)
    for bar in range(8):
        bass_chug(5, bar, ROOTS['II'][bar], vel=114)
    peak = ((0, 0, 2), (3, 3, 1), (6, 1, 2), (8, 4, 1), (10, 5, 1),
            (11, 4, 1), (14, 7, 2))
    for bar in range(8):
        for row, off, ln in peak:
            midi = lead_note(ROOTS['II'][bar] + off, 74)
            if midi > 81:
                midi -= 12
            put(5, 3, bar, row, midi, 116 - (row % 4) * 3, ln)
    counter(5, 0, 14, 82, 68, 2)
    counter(5, 2, 10, 77, 60, 6)
    counter(5, 4, 6, 82, 66, 6)
    counter(5, 6, 14, 79, 62, 2)
    counter(5, 7, 10, 75, 58, 6)


def p6():
    kick_A(6, vel=110)
    snare_A(6, vel=96)
    hats8(6, vel=46)
    for bar in range(8):
        root = ROOTS['III'][bar]
        bass_bar(6, bar, root, vel=108)
        lead_motif(6, bar, root, base=74, vel=102, answer=bar % 2 == 1)
    counter(6, 1, 10, 86, 64, 6)
    counter(6, 3, 6, 84, 60, 8)
    counter(6, 5, 12, 81, 62, 4)
    counter(6, 7, 2, 89, 66, 6)


def p7():
    for bar in range(4):
        for row in (0, 6, 10):
            put(7, 0, bar, row, 36, 108 if row == 0 else 92)
        put(7, 1, bar, 8, 38, 100)
        for row in (0, 4, 8, 12):
            put(7, 2, bar, row, 42, 36)
        bass_long(7, bar, ROOTS['III'][bar], vel=102)
    for bar in range(4, 8):
        for row in (0, 3, 6, 8, 11, 14):
            put(7, 0, bar, row, 36, 110 if row in (0, 8) else 92)
        put(7, 1, bar, 4, 38, 100)
        put(7, 1, bar, 12, 38, 96)
        for row in (0, 2, 4, 6, 8, 10, 12, 14):
            put(7, 2, bar, row, 42, 44)
        bass_bar(7, bar, ROOTS['III'][bar], vel=106)
    for bar, off, ln, vel in ((0, 0, 6, 92), (1, 1, 6, 86), (2, 2, 8, 96),
                              (3, 0, 4, 88)):
        put(7, 3, bar, 0, deg(off, 62), vel, ln)
    for bar in range(4, 8):
        lead_motif(7, bar, ROOTS['III'][bar], base=74, vel=108, answer=bar % 2 == 1)
    counter(7, 2, 12, 81, 60, 4)
    counter(7, 5, 6, 86, 66, 4)
    counter(7, 6, 12, 84, 62, 4)


def p8():
    for bar in range(6):
        for row in (0, 3, 6, 8, 11, 14):
            put(8, 0, bar, row, 36, 120 if row in (0, 8) else 102)
        put(8, 1, bar, 4, 38, 110)
        put(8, 1, bar, 12, 38, 106)
        if bar == 5:
            for row in (14, 15):
                put(8, 1, bar, row, 38, 84)
        for row in (0, 2, 4, 6, 8, 10, 12, 14):
            put(8, 2, bar, row, 42, 48)
        bass_chug(8, bar, ROOTS['END'][bar], vel=116)
        lead_motif(8, bar, ROOTS['END'][bar], base=74, vel=112, answer=bar % 2 == 1)
    # bar 6: breakdown, and bar 7: one final D that can loop back to pattern 0
    for row in (0, 8):
        put(8, 0, 6, row, 36, 104)
    put(8, 1, 6, 12, 38, 96)
    for row in (0, 4):
        put(8, 2, 6, row, 42, 38)
    put(8, 4, 6, 0, deg(0, 38), 108, 8)
    put(8, 3, 6, 0, 62, 90, 8)
    counter(8, 1, 6, 74, 58, 4)
    counter(8, 3, 12, 77, 62, 4)
    counter(8, 5, 2, 81, 64, 4)
    put(8, 5, 6, 10, 74, 54, 4)
    put(8, 0, 7, 0, 36, 112)
    put(8, 2, 7, 0, 42, 44)
    put(8, 1, 7, 8, 38, 72)
    put(8, 4, 7, 0, deg(0, 38), 104, 8)
    put(8, 3, 7, 0, 62, 96, 6)
    put(8, 5, 7, 8, 77, 58, 4)


def build():
    global EV
    EV = {}
    s = Score(bpm=BPM, key=2, seed=SEED, names=LANES, loop=False)
    pats = [s.pattern(index, rate=1, bar=BAR, bars=BARS,
                      name=f'{ACTS[index // 3]}-{index % 3 + 1}') for index in range(PATTERNS)]
    for fn in (p0, p1, p2, p3, p4, p5, p6, p7, p8):
        fn()
    for pat in range(PATTERNS):
        for lane in range(6):
            events = sorted((r, v) for (p, l, r), v in EV.items() if p == pat and l == lane)
            cells = {}
            for i, (r, (pitch, vel, ln)) in enumerate(events):
                limit = (events[i + 1][0] - r) if i + 1 < len(events) else (BAR * BARS - r)
                cells[r] = hit(spell(pitch) if isinstance(pitch, int) else pitch, vel,
                               len=max(0.25, min(ln, limit)))
            pats[pat].lane(lane, cells=cells, length=BAR * BARS)
    for act, name in enumerate(ACTS):
        pats[act * 3].p['scenes'] = [{'r': 0, 'name': name, 'fade': 0}]
    for lane, machine in enumerate((16, 17, 22, 0, 0, 0)):
        s.sound(lane, machine)
    s.chain(*range(PATTERNS), loop=False)
    return s


if __name__ == '__main__':
    output = ROOT / 'score.json'
    output.write_text(build().json() + '\n')
    print(output)
