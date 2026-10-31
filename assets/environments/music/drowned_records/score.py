#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Drowned Records: original 96 BPM, 48-bar, six-pattern score.

Six 8-bar patterns, one finite chain, 120.000 seconds at 4/4.  Sparse broken
pulses, long low bass, a restrained five-note motif and uneasy near-intervals
in the lead/counterline.  No existing music is quoted or transcribed.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from common import Builder, degree_note, score_seconds, write_score   # noqa: E402

BPM = 96
KEY = 5                     # F minor
SEED = 0x5EEDD0
PATTERNS = 6
BARS = 48
NAMES = ('archive-intro', 'first-pressure', 'waterline-rising',
         'drawer-open', 'ink-pressure', 'register-close')
ROOTS = (0, 0, 5, 5, 3, 4, 0, 0)   # Fm Fm Db Db Bb C Fm Fm


def bass_note(degree, base=41):
    return degree_note(KEY, degree, base, 29, 53)


def lead_note(degree, base=65):
    return degree_note(KEY, degree, base, 53, 84)


def counter_note(degree, base=72):
    return degree_note(KEY, degree, base, 65, 91)


def motif(b, pattern, bar, kind='call', vel=82):
    """The restrained five-note cell; the answer closes downward."""
    if kind == 'call':
        notes = ((0, 0, 3), (3, 1, 2), (6, 4, 2), (10, 3, 3), (14, 0, 2))
    else:
        notes = ((0, 3, 2), (4, 4, 2), (7, 1, 3), (11, 0, 2), (14, 0, 4))
    for row, degree, length in notes:
        b.put(pattern, 3, bar, row, lead_note(degree), vel - (row % 3) * 3, length)


def broken_pulse(b, pattern, level=1):
    for bar in range(8):
        if level <= 1:
            rows = (0, 8) if bar % 2 == 0 else (3, 11)
            vel = 86 if bar % 4 == 0 else 74
        elif level == 2:
            rows = (0, 3, 8, 11) if bar % 2 == 0 else (0, 6, 8, 14)
            vel = 92 if bar % 4 == 0 else 78
        else:
            rows = (0, 3, 6, 8, 11, 14) if bar % 2 == 0 else (0, 6, 8, 14)
            vel = 96 if bar % 4 == 0 else 80
        b.fill(pattern, 0, bar, rows, 36, vel)
        if bar % 2 == 1:
            b.put(pattern, 1, bar, 12, 38, 54 if level == 1 else 62)
        if bar % 4 == 3:
            b.put(pattern, 1, bar, 15, 38, 46)


def bass_line(b, pattern, long_notes=False, vel=82):
    for bar, root in enumerate(ROOTS):
        if long_notes:
            b.put(pattern, 4, bar, 0, bass_note(root), vel, 9)
            b.put(pattern, 4, bar, 10, bass_note(root + 4), vel - 10, 4)
        else:
            b.put(pattern, 4, bar, 0, bass_note(root), vel, 4)
            b.put(pattern, 4, bar, 8, bass_note(root + 4), vel - 8, 3)
            if bar % 4 == 2:
                b.put(pattern, 4, bar, 14, bass_note(root + 6), vel - 14, 2)


def drips(b, pattern, bars=(0, 2, 4, 6), vel=38):
    for bar in bars:
        for row in (2, 10):
            b.put(pattern, 2, bar, row, 84, vel + (row % 3))
    b.put(pattern, 2, 7, 6, 86, 34)


def build():
    b = Builder(BPM, KEY, SEED, NAMES)

    # p0 - archive intro: sparse, long bass, the motif appears once
    broken_pulse(b, 0, level=1)
    bass_line(b, 0, long_notes=True, vel=78)
    drips(b, 0, bars=(0, 2, 4, 6), vel=34)
    motif(b, 0, 2, 'call', vel=76)
    motif(b, 0, 6, 'answer', vel=72)
    b.put(0, 5, 1, 6, counter_note(5), 44, 10)
    b.put(0, 5, 4, 10, counter_note(2), 42, 8)

    # p1 - first pressure: a little more pulse, still spacious
    broken_pulse(b, 1, level=2)
    bass_line(b, 1, long_notes=False, vel=84)
    drips(b, 1, bars=(0, 1, 3, 5, 7), vel=38)
    for bar in range(0, 6, 2):
        motif(b, 1, bar, 'call' if bar < 4 else 'answer', vel=80)
    b.put(1, 5, 2, 12, counter_note(6), 48, 4)
    b.put(1, 5, 5, 8, counter_note(5), 46, 6)
    b.put(1, 5, 7, 14, 66, 40, 2)          # Gb4, the b2 warning

    # p2 - waterline rising: more broken kick, near-interval lead
    broken_pulse(b, 2, level=3)
    bass_line(b, 2, long_notes=False, vel=86)
    drips(b, 2, bars=(0, 2, 4, 5, 7), vel=40)
    motif(b, 2, 1, 'call', vel=84)
    motif(b, 2, 3, 'answer', vel=80)
    motif(b, 2, 5, 'call', vel=82)
    b.put(2, 5, 1, 14, counter_note(1), 52, 2)
    b.put(2, 5, 3, 6, counter_note(4), 50, 6)
    b.put(2, 5, 6, 10, 78, 46, 4)          # F#5, the tritone edge

    # p3 - drawer open: sparser, low, long bass and a displaced answer
    broken_pulse(b, 3, level=1)
    bass_line(b, 3, long_notes=True, vel=88)
    drips(b, 3, bars=(0, 2, 5, 7), vel=36)
    motif(b, 3, 1, 'answer', vel=78)
    motif(b, 3, 5, 'call', vel=74)
    b.put(3, 5, 2, 8, counter_note(2), 46, 8)
    b.put(3, 5, 6, 12, counter_note(5), 50, 4)

    # p4 - ink pressure: the motif returns developed over the broken pulse
    broken_pulse(b, 4, level=2)
    bass_line(b, 4, long_notes=False, vel=90)
    drips(b, 4, bars=(0, 1, 3, 4, 6, 7), vel=42)
    motif(b, 4, 0, 'call', vel=86)
    motif(b, 4, 2, 'answer', vel=82)
    motif(b, 4, 4, 'call', vel=88)
    motif(b, 4, 6, 'answer', vel=84)
    b.put(4, 5, 3, 6, counter_note(6), 52, 6)
    b.put(4, 5, 5, 10, counter_note(2), 48, 6)
    b.put(4, 5, 7, 14, 66, 42, 2)

    # p5 - register close: thin, low, a final statement and long rest
    broken_pulse(b, 5, level=1)
    bass_line(b, 5, long_notes=True, vel=76)
    drips(b, 5, bars=(0, 3, 6), vel=32)
    motif(b, 5, 2, 'answer', vel=78)
    for row, degree in ((0, 0), (4, 3), (8, 0)):
        b.put(5, 3, 7, row, lead_note(degree), 66 - row // 4, 2)
    b.put(5, 5, 0, 10, counter_note(5), 40, 8)
    b.put(5, 5, 4, 6, counter_note(0), 38, 10)
    return b.finish()


if __name__ == '__main__':
    doc = build()
    write_score(ROOT / 'score.json', doc)
    print(f'{ROOT / "score.json"}: {BPM} BPM, {BARS} bars, {PATTERNS} patterns, '
          f'{score_seconds(doc):.6f} s')
