# SPDX-License-Identifier: GPL-2.0-or-later
"""Deterministic 64-bit PRNG (splitmix64) and content-addressed hashing.

No wall-clock, no secrets module, no global state: every value the composer and
director draw is a pure function of explicit seed material, so identical
(seed, profile, cue timeline) input always produces identical output bytes.
"""
M32 = 0xFFFFFFFF
M64 = 0xFFFFFFFFFFFFFFFF


def hash_int(*values, salt=0):
    """Content-addressed 64-bit hash of strings and integers, order-sensitive."""
    h = 0x9E3779B97F4A7C15 ^ salt
    for v in values:
        if isinstance(v, str):
            v = int.from_bytes(v.encode('utf-8', 'replace'), 'little')
        h ^= (int(v) * 0xC2B2AE3D27D4EB4F) & M64
        h = ((h << 13) | (h >> 51)) & M64
    h ^= h >> 30
    h = (h * 0xBF58476D1CE4E5B9) & M64
    h ^= h >> 27
    h = (h * 0x94D049BB133111EB) & M64
    return (h ^ (h >> 31)) & M64


def splitmix64(x):
    x = (x + 0x9E3779B97F4A7C15) & M64
    x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & M64
    x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & M64
    return x ^ (x >> 31)


class Rng:
    """Splitmix64 stream. State is a plain integer, so it can be stored and replayed."""
    def __init__(self, seed):
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError('Seed must be an integer')
        self.state = seed & M64
        self._seed = seed & M64

    def next(self):
        self.state = (self.state + 0x9E3779B97F4A7C15) & M64
        return splitmix64(self.state)

    def randint(self, lo, hi):
        """lo..hi inclusive."""
        if hi < lo:
            raise ValueError('Empty range')
        return lo + self.next() % (hi - lo + 1)

    def chance(self, percent):
        return self.next() % 100 < percent

    def pick(self, items):
        return items[self.next() % len(items)]

    def shuffle(self, items):
        items = list(items)
        for i in range(len(items) - 1, 0, -1):
            j = self.next() % (i + 1)
            items[i], items[j] = items[j], items[i]
        return items
