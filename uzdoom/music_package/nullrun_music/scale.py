# SPDX-License-Identifier: GPL-2.0-or-later
"""MIDI numbers, HydraPy tracker note spellings, scales and chord spellings.

HydraPy spells C4 as C-4 (MIDI 60) and accepts sharps only, C0-G9.
"""
NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

INTERVALS = {
    # Named interval sets in semitones, for profile grammars.
    'minor': (0, 2, 3, 5, 7, 8, 10),
    'natural_minor': (0, 2, 3, 5, 7, 8, 10),
    'harmonic_minor': (0, 2, 3, 5, 7, 8, 11),
    'phrygian': (0, 1, 3, 5, 7, 8, 10),
    'dorian': (0, 2, 3, 5, 7, 9, 10),
    'minor_pentatonic': (0, 3, 5, 7, 10),
    'locrian': (0, 1, 3, 5, 6, 8, 10),
    'lydian_dominant': (0, 2, 4, 6, 7, 9, 10),
}

# Triads by scale degree (offsets into the scale). 'm' minor, 'M' major, 'd' diminished.
TRIADS = {0: 'm', 1: 'd', 2: 'M', 3: 'm', 4: 'm', 5: 'M', 6: 'M'}
CHORD_INTERVALS = {'m': (0, 3, 7), 'M': (0, 4, 7), 'd': (0, 3, 6)}
KEYS = {0: 'C', 2: 'D', 5: 'F', 7: 'G'}  # tracker3 restricts to C/D/F/G minor


def midi_to_name(midi):
    if not isinstance(midi, int) or not 0 <= midi <= 127:
        raise ValueError('MIDI must be 0-127')
    name = NAMES[midi % 12]
    octave = midi // 12 - 1
    # HydraPy spells naturals C-4 but sharps C#4 (one separator char).
    return f'{name}{octave}' if '#' in name else f'{name}-{octave}'


def name_to_midi(name):
    if not isinstance(name, str) or len(name) < 2:
        raise ValueError('Bad note name')
    letter, accidental = name[0], name[1] if name[1] in '#-' else ''
    octave = name[2:] if accidental else name[1:]
    base = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}[letter]
    midi = 12 * (int(octave) + 1) + base + (accidental == '#')
    if not 0 <= midi <= 127:
        raise ValueError('MIDI must be 0-127')
    return midi


class Scale:
    """A scale rooted at a key, expressed as ascending pitch classes plus octave stretch."""
    def __init__(self, key, intervals):
        if key not in KEYS:
            raise ValueError('Key must be C, D, F or G minor (tracker3)')
        self.key = key
        self.intervals = tuple(intervals)
        self.size = len(intervals)

    def degree(self, deg, octave):
        """Absolute MIDI pitch of scale degree `deg` (may be negative/large) at octave."""
        span, step = divmod(deg, self.size)
        return self.key + 12 * (octave + span) + self.intervals[step]

    def chord(self, degree, octave, kind=None):
        """Chord tones of the triad on scale degree `degree`."""
        intervals = CHORD_INTERVALS[kind or TRIADS[degree % self.size]]
        return [self.degree(degree + i, octave) for i in intervals]

    def in_scale(self, midi):
        return (midi - self.key) % 12 in set(self.intervals)


def clamp_midi(midi, lo=0, hi=127):
    """Move by octaves until in range."""
    while midi < lo:
        midi += 12
    while midi > hi:
        midi -= 12
    return midi
