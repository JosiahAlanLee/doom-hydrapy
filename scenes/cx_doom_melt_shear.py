# SPDX-License-Identifier: GPL-2.0-or-later
"""cx_doom_melt_shear.py — Doom 160-Column Wipe Melt + Family 376 Solenoidal BSP Shear.

Drop-in scene for `scenes/` in https://github.com/JosiahAlanLee/doom-hydrapy.
Pairs Doom's classic 1993 `f_wipe.c` 160-column vertical screen melt with
OpenAI Math Family 376 (`lean/docs/376.md`) incompressible alternating solenoidal
shear (det DF == 1), driven by beat phase and weapon-fire transients.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from common import source
except ImportError:
    from hydrapy import osc

    def source():
        return osc(12.0, 0.1, 0.5)

import doom_math_ops  # noqa: F401
from hydrapy.signals import Fn1

SCENE = dict(
    name="cx-doom-melt-shear",
    author="Argon & Codex; engine by id Software/doomgeneric; game data by Freedoom",
    algorithms=["Doom engine", "f_wipe 160-column melt", "Family 376 solenoidal shear"],
    palette="Freedoom ember-sheared",
    keys="Demo advances 35 tics per second of renderer time",
    notes="GPL plugin, engine runs in child process",
)


def build(ctx):
    kick = ctx.hit(1, 0.25)
    snare = ctx.hit(2, 0.30)
    beat_wave = Fn1("sin", ctx.beat * 0.5)
    melt_amt = 0.08 + 0.18 * kick + 0.06 * beat_wave
    shear_amt = 0.05 + 0.10 * snare

    base = source().doomMeltShear(
        melt=melt_amt,
        shear=shear_amt,
        columns=160.0,
        phase=ctx.beat * 0.85,
    )
    return base.blend(ctx.prev.scale(1.004), 0.18).contrast(1.12).saturate(1.15)