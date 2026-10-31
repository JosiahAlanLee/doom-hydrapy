#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""After Hours Pavilion: original 112 BPM, 56-bar, seven-pattern score.

Seven 8-bar patterns, one finite chain, 120.000 seconds at 4/4.  Off-kilter
broken lounge: displaced bell/reed phrases, gentle mechanical bass, missing
expected beats and a deliberately quiet middle.  No existing music is quoted.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from common import Builder, degree_note, score_seconds, write_score   # noqa: E402

BPM = 112
KEY = 7                     # G minor
SEED = 0xA57E2
PATTERNS = 7
BARS = 56
NAMES = ('concourse', 'queue-drift', 'quiet-a', 'quiet-b',
         'return', 'late', 'close')
ROOTS = (0, 0, 5, 3, 4, 0, 6, 0)   # Gm Gm Eb Bb C Gm F Gm


def bass_note(degree, base=43):
    return degree_note(KEY, degree, base, 31, 55)


def lead_note(degree, base=67):
    return degree_note(KEY, degree, base, 55, 86)


def counter_note(degree, base=74):
    return degree_note(KEY, degree, base, 67, 93)


def off_kick(b, pattern, variant=0, vel=78):
    figures = (
        (2, 6, 10, 14),
        (1, 5, 9, 13),
        (0, 3, 7, 11),
        (2, 7, 12),
        (4, 9, 14),
    )
    rows = figures[variant % len(figures)]
    for bar in range(8):
        if variant == 5 and bar % 4 == 2:
            continue
        for row in rows:
            b.put(pattern, 0, bar, row, 36, vel - (6 if row % 4 else 0))


def soft_snare(b, pattern, rows=(7, 15), vel=64):
    for bar in range(8):
        for row in rows:
            b.put(pattern, 1, bar, row, 38, vel - (4 if row > 12 else 0))


def sparse_hats(b, pattern, rows=(0, 4, 8, 12), vel=30, bars=range(8)):
    for bar in bars:
        for row in rows:
            b.put(pattern, 2, bar, row, 84, vel + (4 if row == 4 else 0))


def gentle_bass(b, pattern, long_notes=False, vel=68):
    for bar, root in enumerate(ROOTS):
        if long_notes:
            b.put(pattern, 4, bar, 0, bass_note(root), vel, 8)
            b.put(pattern, 4, bar, 10, bass_note(root + 4), vel - 6, 4)
        else:
            b.put(pattern, 4, bar, 2, bass_note(root), vel, 2)
            b.put(pattern, 4, bar, 7, bass_note(root + 4), vel - 4, 2)
            b.put(pattern, 4, bar, 11, bass_note(root), vel - 6, 2)


def bell_phrase(b, pattern, bar, answer=False, vel=82):
    if not answer:
        cell = ((1, 4, 2), (5, 2, 2), (9, 0, 3), (13, 3, 2))
    else:
        cell = ((2, 0, 3), (6, 3, 1), (10, 4, 2), (14, 2, 2))
    for row, degree, length in cell:
        b.put(pattern, 3, bar, row, lead_note(degree), vel - (row % 4) * 2, length)


def counter(b, pattern, entries):
    for bar, row, degree, vel, length in entries:
        b.put(pattern, 5, bar, row, counter_note(degree), vel, length)


def build():
    b = Builder(BPM, KEY, SEED, NAMES)

    # p0 - concourse: missing downbeat, displaced phrase
    off_kick(b, 0, 0, 82)
    soft_snare(b, 0, (7, 15), 66)
    sparse_hats(b, 0, (2, 6, 10, 14), 30)
    gentle_bass(b, 0, False, 70)
    for bar in (0, 2):
        bell_phrase(b, 0, bar, False, 84)
    counter(b, 0, ((1, 12, 4, 52, 6), (5, 8, 2, 48, 8), (7, 14, 6, 56, 2)))

    # p1 - queue drift: answer phrase, displaced accents
    off_kick(b, 1, 1, 86)
    soft_snare(b, 1, (5, 13), 68)
    sparse_hats(b, 1, (0, 4, 8, 12), 32, bars=(0, 1, 2, 3, 5, 6, 7))
    gentle_bass(b, 1, False, 72)
    for bar in (4, 6):
        bell_phrase(b, 1, bar, True, 86)
    counter(b, 1, ((0, 6, 5, 56, 4), (2, 10, 2, 52, 6), (6, 12, 4, 60, 4)))

    # p2 - quiet middle A: nearly empty, long bass and one long displaced note
    off_kick(b, 2, 3, 64)
    gentle_bass(b, 2, True, 58)
    bell_phrase(b, 2, 1, False, 64)
    bell_phrase(b, 2, 5, True, 60)
    counter(b, 2, ((0, 14, 5, 42, 8), (4, 8, 2, 40, 10)))

    # p3 - quiet middle B: no hats, no backbeat, missing beats
    off_kick(b, 3, 4, 60)
    gentle_bass(b, 3, True, 56)
    bell_phrase(b, 3, 3, True, 58)
    counter(b, 3, ((1, 6, 4, 40, 10), (5, 12, 0, 38, 8)))

    # p4 - return: the phrase re-enters over a fuller but still broken pulse
    off_kick(b, 4, 0, 88)
    soft_snare(b, 4, (7, 15), 70)
    sparse_hats(b, 4, (2, 6, 10, 14), 34)
    gentle_bass(b, 4, False, 74)
    for bar in (0, 2, 4):
        bell_phrase(b, 4, bar, False, 88)
    counter(b, 4, ((1, 10, 5, 54, 6), (3, 6, 2, 50, 8), (6, 12, 6, 58, 4)))

    # p5 - late: answer, slightly harder bass, still no straight four
    off_kick(b, 5, 2, 90)
    soft_snare(b, 5, (5, 13), 72)
    sparse_hats(b, 5, (0, 4, 8, 12), 34, bars=(1, 2, 3, 5, 6, 7))
    gentle_bass(b, 5, False, 76)
    for bar in (1, 3, 5, 7):
        bell_phrase(b, 5, bar, bar % 2 == 1, 88)
    counter(b, 5, ((0, 14, 4, 56, 2), (4, 8, 5, 52, 6), (7, 10, 2, 60, 4)))

    # p6 - close: sparse resolve on G, with an unanswered displaced note
    off_kick(b, 6, 3, 58)
    soft_snare(b, 6, (12,), 52)
    gentle_bass(b, 6, True, 56)
    bell_phrase(b, 6, 2, True, 62)
    b.put(6, 3, 7, 6, lead_note(0), 54, 4)
    counter(b, 6, ((0, 14, 5, 40, 8), (4, 8, 0, 38, 10)))
    return b.finish()


if __name__ == '__main__':
    doc = build()
    write_score(ROOT / 'score.json', doc)
    print(f'{ROOT / "score.json"}: {BPM} BPM, {BARS} bars, {PATTERNS} patterns, '
          f'{score_seconds(doc):.6f} s')
