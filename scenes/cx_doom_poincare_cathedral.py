# SPDX-License-Identifier: GPL-2.0-or-later
"""cx_doom_poincare_cathedral.py — Non-Euclidean Poincare Disk Viewport & Polar HUD Bezel.

Drop-in scene for `scenes/` in https://github.com/JosiahAlanLee/doom-hydrapy.
Maps the top 84% 3D raycast viewport of Doom into a dihedral-folded Poincare
hyperbolic disk while wrapping Doom's 32-pixel bottom status bar (Doomguy face,
ammo, health, armor) around the outer polar ring r in [0.78, 0.96].
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
    name="cx-doom-poincare",
    author="Argon & Codex; engine by id Software/doomgeneric; game data by Freedoom",
    algorithms=["Doom engine", "Poincare hyperbolic disk", "polar HUD status-bar bezel"],
    palette="Freedoom cathedral brass & crimson",
    keys="Demo advances 35 tics per second of renderer time",
    notes="GPL plugin, engine runs in child process",
)


def build(ctx):
    kick = ctx.hit(1, 0.30)
    zoom_mod = 1.05 + 0.25 * kick + 0.12 * Fn1("sin", ctx.beat * 0.25)
    twist_mod = ctx.time * 0.18 + 0.08 * Fn1("cos", ctx.beat * 0.5)

    return (
        source()
        .doomPoincareCathedral(
            zoom=zoom_mod,
            twist=twist_mod,
            hud_ring=1.0,
            sectors=6.0,
        )
        .contrast(1.14)
        .saturate(1.18)
    )