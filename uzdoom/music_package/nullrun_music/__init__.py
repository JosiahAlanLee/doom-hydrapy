# SPDX-License-Identifier: GPL-2.0-or-later
"""nullrun_music: a seeded algorithmic composer and adaptive director for NULL RUN.

Original algorithmic composition engine and cue-responsive director, designed to
attach to HydraPy Studio's hydrapy-tracker-3 evaluator and Gorgon. This package is
offline/CPU-only: it never opens audio hardware, game sockets or Rack.

Modules:
    rng        deterministic 64-bit PRNG and content-addressed hashing
    scale      MIDI <-> HydraPy note names, scales and chord spellings
    events     cues, note events, control events, receipts, the JSONL schedule
    profiles   the three NULL RUN theme profiles
    composer   motif grammar, loop sections, sting and cadence material
    director   state machine, priorities, cooldowns, boundaries
    engine     offline and incremental realization of a cue timeline
    snapshot_rules  proposed cue derivation from real game state (documented as proposed)
    export_tracker  hydrapy-tracker-3 pattern-bank export via the frozen validator
    adapter    dry-run live host adapter and its contract
    synth      offline reference renderer (48 kHz stereo PCM16 WAV)
    cli        command line entry point
"""
from .rng import Rng, hash_int, M32
from .events import (TICKS, ROW, BAR, EIGHTH, Cue, NoteEvent, ControlEvent, Receipt,
                     CUE_TYPES, read_jsonl, write_jsonl, Schedule)
from .profiles import PROFILES, load_profile, PROFILE_NAMES

__version__ = '1.0.0'
