#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Switchyard Chapel: original 128 BPM, 64-bar, eight-pattern score.

Eight 8-bar patterns, one finite chain, 120.000 seconds at 4/4.  Driving
syncopated electro/FM machinery, a strong irregular bass figure, call/response
lead phrases, a sparse breakdown and a developed return.  No existing music is
quoted or transcribed.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from common import Builder, degree_note, score_seconds, write_score   # noqa: E402

BPM = 128
KEY = 2                     # D minor
SEED = 0xC0A1E
PATTERNS = 8
BARS = 64
NAMES = ('gate-open', 'relay-drive', 'arc-response', 'breakdown',
         'build', 'peak', 'return', 'close')
ROOTS = (0, 0, 5, 5, 3, 4, 0, 0)   # Dm Dm Bb Bb Gm Am Dm Dm


def bass_note(degree, base=38):
    return degree_note(KEY, degree, base, 29, 53)


def lead_note(degree, base=70):
    return degree_note(KEY, degree, base, 57, 84)


def counter_note(degree, base=77):
    return degree_note(KEY, degree, base, 65, 91)


def kick(b, pattern, variant=0, vel=104):
    patterns = (
        (0, 3, 6, 8, 11, 14),
        (0, 2, 5, 8, 10, 13),
        (0, 3, 6, 8, 11, 14, 15),
        (0, 6, 8, 14),
    )
    rows = patterns[variant % len(patterns)]
    for bar in range(8):
        for row in rows:
            b.put(pattern, 0, bar, row, 36, vel - (10 if row not in (0, 8) else 0))


def snare(b, pattern, backbeat=True, ghost=False, vel=98):
    for bar in range(8):
        if backbeat:
            b.put(pattern, 1, bar, 4, 38, vel)
            b.put(pattern, 1, bar, 12, 38, vel - 4)
        if ghost and bar % 2 == 1:
            b.put(pattern, 1, bar, 15, 38, 56)


def hats(b, pattern, sixteenth=False, vel=44, bars=range(8)):
    for bar in bars:
        rows = range(16) if sixteenth else (0, 2, 4, 6, 8, 10, 12, 14)
        for row in rows:
            b.put(pattern, 2, bar, row, 84, vel + (8 if row % 4 == 2 else 0)
                  - (5 if row % 2 else 0))


def bass_figure(b, pattern, variant=0, vel=102):
    figures = (
        ((0, 0), (3, 0), (6, 7), (8, 0), (11, 4), (14, 7)),
        ((0, 0), (2, 7), (5, 0), (8, 4), (10, 7), (13, 0)),
        ((0, 0), (3, 4), (6, 7), (8, 0), (11, 4), (14, 0)),
    )
    for bar, root in enumerate(ROOTS):
        figure = figures[variant % len(figures)]
        for j, (row, offset) in enumerate(figure):
            b.put(pattern, 4, bar, row, bass_note(root + offset), vel - (j % 3) * 6,
                  1 if row % 2 else 2)


def lead_call(b, pattern, bar, response=False, vel=100):
    if not response:
        cell = ((0, 0, 2), (2, 2, 1), (5, 4, 2), (8, 3, 1),
                (10, 2, 2), (13, 0, 2))
    else:
        cell = ((0, 4, 2), (3, 3, 1), (6, 2, 1), (8, 0, 3),
                (12, 1, 2), (14, 0, 2))
    for row, degree, length in cell:
        b.put(pattern, 3, bar, row, lead_note(degree), vel - (row % 4) * 3, length)


def counter(b, pattern, entries):
    for bar, row, degree, vel, length in entries:
        b.put(pattern, 5, bar, row, counter_note(degree), vel, length)


def build():
    b = Builder(BPM, KEY, SEED, NAMES)

    # p0 - gate open: syncopated machinery, call phrase
    kick(b, 0, 0, 108)
    snare(b, 0, vel=100)
    hats(b, 0, vel=42)
    bass_figure(b, 0, 0, 104)
    for bar in (0, 2):
        lead_call(b, 0, bar, False, 102)
    counter(b, 0, ((1, 10, 5, 64, 4), (5, 6, 2, 60, 6), (7, 14, 6, 68, 2)))

    # p1 - relay drive: answer phrase, stronger bass
    kick(b, 1, 1, 112)
    snare(b, 1, ghost=True, vel=102)
    hats(b, 1, sixteenth=True, vel=45)
    bass_figure(b, 1, 1, 108)
    for bar in (4, 6):
        lead_call(b, 1, bar, True, 104)
    counter(b, 1, ((0, 14, 4, 68, 2), (3, 6, 5, 64, 4), (7, 10, 2, 72, 4)))

    # p2 - arc response: irregular kick and a second call
    kick(b, 2, 2, 114)
    snare(b, 2, ghost=True, vel=104)
    hats(b, 2, sixteenth=True, vel=44)
    bass_figure(b, 2, 2, 110)
    for bar in (1, 3, 5):
        lead_call(b, 2, bar, bar % 2 == 0, 104)
    counter(b, 2, ((2, 12, 2, 76, 4), (6, 8, 4, 72, 6)))

    # p3 - breakdown: sparse, long bass, no backbeat
    kick(b, 3, 3, 92)
    hats(b, 3, False, 32, bars=(1, 3, 5, 7))
    for bar, root in enumerate(ROOTS):
        b.put(3, 4, bar, 0, bass_note(root), 88, 10)
        b.put(3, 4, bar, 10, bass_note(root + 4), 78, 4)
    for bar in (0, 4):
        lead_call(b, 3, bar, True, 84)
    counter(b, 3, ((1, 6, 5, 64, 8), (4, 10, 2, 69, 6), (7, 6, 0, 62, 8)))

    # p4 - build: return of the drive, call phrase
    kick(b, 4, 0, 104)
    snare(b, 4, vel=96)
    hats(b, 4, False, 42)
    bass_figure(b, 4, 0, 104)
    for bar in (0, 2, 4):
        lead_call(b, 4, bar, False, 100)
    counter(b, 4, ((3, 12, 5, 68, 4), (6, 6, 2, 72, 4)))

    # p5 - peak: full but phrased, response
    kick(b, 5, 1, 116)
    snare(b, 5, ghost=True, vel=108)
    hats(b, 5, sixteenth=True, vel=46)
    bass_figure(b, 5, 1, 112)
    for bar in (1, 3, 5, 7):
        lead_call(b, 5, bar, bar % 2 == 0, 106)
    counter(b, 5, ((0, 14, 4, 72, 2), (2, 6, 5, 68, 4), (4, 10, 2, 76, 4),
                   (6, 6, 6, 69, 6)))

    # p6 - return: restate the first gesture with a longer answer
    kick(b, 6, 0, 108)
    snare(b, 6, vel=100)
    hats(b, 6, False, 42)
    bass_figure(b, 6, 0, 106)
    for bar in (0, 2, 4, 6):
        lead_call(b, 6, bar, bar % 2 == 1, 102)
    counter(b, 6, ((1, 10, 5, 68, 6), (5, 6, 2, 64, 4), (7, 14, 6, 72, 2)))

    # p7 - close: full but finite, ending on a low D and a held answer
    kick(b, 7, 2, 110)
    snare(b, 7, ghost=True, vel=102)
    hats(b, 7, sixteenth=True, vel=42)
    bass_figure(b, 7, 2, 108)
    for bar in (0, 2, 4, 6):
        lead_call(b, 7, bar, bar % 2 == 1, 104)
    b.put(7, 3, 7, 0, lead_note(0), 94, 8)
    counter(b, 7, ((1, 12, 5, 68, 4), (5, 8, 2, 72, 4), (7, 8, 6, 69, 4)))
    return b.finish()


if __name__ == '__main__':
    doc = build()
    write_score(ROOT / 'score.json', doc)
    print(f'{ROOT / "score.json"}: {BPM} BPM, {BARS} bars, {PATTERNS} patterns, '
          f'{score_seconds(doc):.6f} s')
