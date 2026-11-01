# SPDX-License-Identifier: GPL-2.0-or-later
"""cx_doom_anaglyph_relief.py — Diminished-Lighting Depth Reconstruction & 3D Parallax Relief.

Drop-in scene for `scenes/` in https://github.com/JosiahAlanLee/doom-hydrapy.
Exploits Doom's software sector diminished-lighting law (brightness drop with distance)
and floor/ceiling perspective plane geometry |y - horizon| to reconstruct a live
per-pixel pseudo-depth field, driving stereoscopic Red-Cyan 3D parallax and
normal-mapped metallic relief.
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
    name="cx-doom-depth-relief",
    author="Argon & Codex; engine by id Software/doomgeneric; game data by Freedoom",
    algorithms=["Doom engine", "diminished-lighting depth estimation", "stereoscopic parallax & relief"],
    palette="Red-cyan stereoscopic anaglyph / normal-mapped relief",
    keys="Demo advances 35 tics per second of renderer time",
    notes="GPL plugin, engine runs in child process",
)


def build(ctx):
    kick = ctx.hit(1, 0.25)
    parallax_amt = 0.014 + 0.016 * kick + 0.005 * Fn1("sin", ctx.beat * 0.5)
    return (
        source()
        .doomAnaglyphRelief(
            parallax=parallax_amt,
            light_depth=0.65,
            horizon=0.56,
            mode=0.0,
        )
        .contrast(1.12)
        .saturate(1.15)
    )