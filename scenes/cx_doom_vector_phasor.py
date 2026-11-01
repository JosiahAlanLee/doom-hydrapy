# SPDX-License-Identifier: GPL-2.0-or-later
"""cx_doom_vector_phasor.py — Tektronix XY Vector-CRT & Muzzle/Fireball Chroma Isolation.

Drop-in scene for `scenes/` in https://github.com/JosiahAlanLee/doom-hydrapy.
Extracts 3x3 Sobel gradients on the 640x400 framebuffer to render BSP wall and
sector boundaries as Tektronix P31 cyan-green vector traces while isolating Doom
PLAYPAL reds/ambers (fireballs, barrel explosions, shotgun flashes, damage tint)
into high-bloom crimson vector bursts.
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

SCENE = dict(
    name="cx-doom-vector-scope",
    author="Argon & Codex; engine by id Software/doomgeneric; game data by Freedoom",
    algorithms=["Doom engine", "Sobel BSP edge detector", "PLAYPAL hazard chroma isolation"],
    palette="Tektronix P31 phosphor & crimson hazard bloom",
    keys="Demo advances 35 tics per second of renderer time",
    notes="GPL plugin, engine runs in child process",
)


def build(ctx):
    kick = ctx.hit(1, 0.25)
    snare = ctx.hit(2, 0.25)
    return (
        source()
        .doomSobelVectorScope(
            edge_gain=2.2 + 0.9 * snare,
            hazard_glow=1.3 + 0.8 * kick,
            phosphor=0.72,
            scan=200.0,
        )
        .blend(ctx.prev.scale(1.003), 0.22)
        .contrast(1.16)
    )