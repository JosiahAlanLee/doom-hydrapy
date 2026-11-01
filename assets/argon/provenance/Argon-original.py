# SPDX-License-Identifier: GPL-2.0-or-later
"""nullrun_monsters.py — Procedural Monster Bestiary & 35-Tic AI State Machines for NULLRUN.

Designed for the "MyHouse.wad + Quake + Backrooms" aesthetic in NULLRUN (`doom-hydrapy`),
specifically engineered to interlock with:
  - The Hollow (frustum-freeze ambusher: moves only when outside player FOV)
  - The Stone ReDead (close-range root grapple: pins player position until F-bar fills or hurt)
  - Non-Euclidean Corridor Swapping (silent preserve-angle sector/hallway permutations)

Defines 4 procedural enemy archetypes with 64x64 Doom-palette sprite generators
and deterministic 35-tic behavioral state machines:
1. `SURVEYOR` ("The Transit"):
   - Backrooms yellow-ochre laser transit tripod + rotating brass prism oculus.
   - Projects a sightline beam down long corridors. Crossing its beam without crouching
     or staggering it triggers a silent corridor swap behind the player and fires a
     delayed Quake-style rail arc.
2. `WIRE_SHAMBLER` ("The Ballast Husk"):
   - Quake Shambler + Kane Pixels Backrooms wire-bacteria silhouette: hunched asymmetric
     rebar/cable frame with a jagged lightning-arc jaw.
   - 28-tic (0.8s) telegraph charge-up before firing a hitscan arc. Forces the player
     to duck behind a pillar to break line-of-sight—which simultaneously breaks FOV
     on The Hollow and lets The Hollow sprint forward!
3. `THRESHOLD_MIMIC` ("The False Exit"):
   - MyHouse.wad hostile architecture: masquerades as a recessed exit door / office
     lintel with a faint 1px crimson floor seam until approached within 192 units,
     then splits vertically into concrete teeth and flips the player's camera 180 deg
     on bite so retreating sends them deeper into the swapped maze.
4. `VORE_SPINDLE` ("The Drop-Tile Lurker"):
   - Quake Vore (Shalrath) homage: hangs inverted from a missing fluorescent drop-ceiling
     tile and launches a slow, shootable homing polyhedron that steers around corners,
     preventing players from camping in one room.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any
import numpy as np


@dataclass
class MonsterSpec:
    id_name: str
    display_name: str
    subtitle: str
    banner_title: str
    banner_hint: str
    hp: int
    speed_units_per_tic: float
    radius: float
    height: float
    telegraph_tics: int
    triggers_corridor_swap: bool


MONSTER_SPECS: dict[str, MonsterSpec] = {
    "SURVEYOR": MonsterSpec(
        id_name="MT_SURVEYOR",
        display_name="THE SURVEYOR",
        subtitle="BACKROOMS TRANSIT / SIGHTLINE ARCHITECT",
        banner_title="THE SURVEYOR / SIGHTLINE LOCKED",
        banner_hint="Crossing its laser plumb-line re-indexes the floorplan. Stagger it before advancing.",
        hp=90,
        speed_units_per_tic=4.0,
        radius=20.0,
        height=62.0,
        telegraph_tics=21,
        triggers_corridor_swap=True,
    ),
    "WIRE_SHAMBLER": MonsterSpec(
        id_name="MT_WIRE_SHAMBLER",
        display_name="THE BALLAST HUSK",
        subtitle="QUAKE SHAMBLER / FLUORESCENT ARC BRUTE",
        banner_title="THE BALLAST HUSK / ARC CHARGING",
        banner_hint="Break line-of-sight behind a pillar before the 28-tic arc discharges. Watch your back.",
        hp=220,
        speed_units_per_tic=7.5,
        radius=28.0,
        height=64.0,
        telegraph_tics=28,
        triggers_corridor_swap=False,
    ),
    "THRESHOLD_MIMIC": MonsterSpec(
        id_name="MT_THRESHOLD",
        display_name="THE THRESHOLD",
        subtitle="MYHOUSE HOSTILE DOORFRAME / COMPASS THIEF",
        banner_title="THE THRESHOLD / FALSE LINTEL",
        banner_hint="Check the vertical seam before pressing F. Its bite inverts your compass bearing 180 deg.",
        hp=140,
        speed_units_per_tic=0.0,
        radius=32.0,
        height=64.0,
        telegraph_tics=10,
        triggers_corridor_swap=True,
    ),
    "VORE_SPINDLE": MonsterSpec(
        id_name="MT_VORE_SPINDLE",
        display_name="THE DROP-TILE SPINDLE",
        subtitle="CEILING PENDULUM / HOMING POLYHEDRON",
        banner_title="THE SPINDLE / HOMING SPORE IN FLIGHT",
        banner_hint="Its spore steers around corners. Shoot the spore out of the air or lead it into a pillar.",
        hp=110,
        speed_units_per_tic=5.5,
        radius=22.0,
        height=56.0,
        telegraph_tics=35,
        triggers_corridor_swap=False,
    ),
}


def _draw_segment(mask: np.ndarray, x0: float, y0: float, x1: float, y1: float, radius: float) -> np.ndarray:
    h, w = mask.shape
    yy, xx = np.mgrid[0:h, 0:w]
    dx, dy = x1 - x0, y1 - y0
    denom = dx * dx + dy * dy + 1e-9
    t = np.clip(((xx - x0) * dx + (yy - y0) * dy) / denom, 0.0, 1.0)
    dist = np.sqrt((xx - (x0 + t * dx)) ** 2 + (yy - (y0 + t * dy)) ** 2)
    return np.maximum(mask, (dist <= radius).astype(np.float32))


def generate_monster_sprite(kind: str, size: int = 64, state: str = "awake") -> np.ndarray:
    """Synthesize a crisp 64x64 RGBA uint8 Doom-style pixel-art sprite for `kind`."""
    s = int(size)
    rgba = np.zeros((s, s, 4), dtype=np.float32)
    yy, xx = np.mgrid[0:s, 0:s]
    nx = (xx - s * 0.5) / (s * 0.5)
    ny = (yy - s * 0.5) / (s * 0.5)

    if kind == "SURVEYOR":
        # Spindly 3-legged yellow-ochre surveyor transit tripod + brass prism + laser eye
        legs = np.zeros((s, s), dtype=np.float32)
        legs = _draw_segment(legs, s * 0.50, s * 0.34, s * 0.20, s * 0.92, 1.6)
        legs = _draw_segment(legs, s * 0.50, s * 0.34, s * 0.80, s * 0.92, 1.6)
        legs = _draw_segment(legs, s * 0.50, s * 0.34, s * 0.50, s * 0.95, 1.5)
        # Horizontal transit crossbars & plumb-bob ring
        legs = _draw_segment(legs, s * 0.34, s * 0.58, s * 0.66, s * 0.58, 1.2)
        legs = _draw_segment(legs, s * 0.27, s * 0.74, s * 0.73, s * 0.74, 1.1)

        # Octagonal transit head housing (top)
        head_box = (np.abs(nx) < 0.22) & (np.abs(ny + 0.42) < 0.16) & ((np.abs(nx) + np.abs(ny + 0.42)) < 0.31)
        head_rim = head_box & ((np.abs(nx) > 0.17) | (np.abs(ny + 0.42) > 0.11))
        eye_dist = np.sqrt(nx ** 2 + (ny + 0.42) ** 2)
        eye_core = eye_dist <= 0.085
        laser_cross = ((np.abs(ny + 0.42) <= 0.025) & (np.abs(nx) < 0.44)) | ((np.abs(nx) <= 0.02) & (np.abs(ny + 0.42) < 0.32))

        alpha = np.clip(legs + head_box.astype(np.float32) + laser_cross.astype(np.float32), 0.0, 1.0)
        # Backrooms yellow-ochre legs + dark bronze body + crimson/chartreuse laser oculus
        rgba[..., 0] = legs * 0.78 + head_box * 0.32 + head_rim * 0.55 + eye_core * 0.98 + laser_cross * 0.95
        rgba[..., 1] = legs * 0.66 + head_box * 0.28 + head_rim * 0.48 + eye_core * 0.96 + laser_cross * 0.25
        rgba[..., 2] = legs * 0.22 + head_box * 0.18 + head_rim * 0.20 + eye_core * 0.42 + laser_cross * 0.18
        rgba[..., 3] = (alpha > 0.1).astype(np.float32)

    elif kind == "WIRE_SHAMBLER":
        # Hunched Quake Shambler + Backrooms wire-bacteria tangle with overhead lightning arc
        body = np.zeros((s, s), dtype=np.float32)
        # Massive hunched shoulders & gorilla-like grounded arms
        body = _draw_segment(body, s * 0.50, s * 0.36, s * 0.22, s * 0.24, 4.2)
        body = _draw_segment(body, s * 0.22, s * 0.24, s * 0.14, s * 0.78, 3.8)
        body = _draw_segment(body, s * 0.50, s * 0.36, s * 0.78, s * 0.24, 4.2)
        body = _draw_segment(body, s * 0.78, s * 0.24, s * 0.86, s * 0.78, 3.8)
        # Bowed legs & heavy torso
        body = _draw_segment(body, s * 0.42, s * 0.54, s * 0.32, s * 0.92, 3.6)
        body = _draw_segment(body, s * 0.58, s * 0.54, s * 0.68, s * 0.92, 3.6)
        torso = (np.abs(nx) < 0.24) & (ny > -0.26) & (ny < 0.24)
        body = np.maximum(body, torso.astype(np.float32))

        # Jagged rebar ribs & gaping lightning maw in center of chest/head
        ribs = ((np.sin(yy * 0.95) > 0.15) & (body > 0.5)).astype(np.float32)
        maw = (np.abs(nx) < 0.15) & (ny > -0.22) & (ny < -0.02)
        teeth = maw & ((xx % 3 == 0) & ((yy < s * 0.42) | (yy > s * 0.46)))

        # Overhead Shambler lightning arc between raised claws
        arc = np.zeros((s, s), dtype=np.float32)
        arc = _draw_segment(arc, s * 0.16, s * 0.20, s * 0.36, s * 0.10, 1.3)
        arc = _draw_segment(arc, s * 0.36, s * 0.10, s * 0.52, s * 0.16, 1.3)
        arc = _draw_segment(arc, s * 0.52, s * 0.16, s * 0.68, s * 0.09, 1.3)
        arc = _draw_segment(arc, s * 0.68, s * 0.09, s * 0.84, s * 0.20, 1.3)

        alpha = np.clip(body + arc, 0.0, 1.0)
        rgba[..., 0] = body * (0.38 + 0.28 * ribs) * (1.0 - maw) + teeth * 0.92 + arc * 0.35
        rgba[..., 1] = body * (0.24 + 0.18 * ribs) * (1.0 - maw) + teeth * 0.88 + arc * 0.96
        rgba[..., 2] = body * (0.18 + 0.12 * ribs) * (1.0 - maw) + teeth * 0.72 + arc * 1.00
        rgba[..., 3] = (alpha > 0.1).astype(np.float32)

    elif kind == "THRESHOLD_MIMIC":
        # MyHouse.wad Mimic Doorframe split vertically down the center with concrete teeth & void oculus
        outer_frame = (np.abs(nx) < 0.44) & (ny > -0.82) & (ny < 0.92)
        inner_door = (np.abs(nx) < 0.34) & (ny > -0.70) & (ny < 0.90)
        # Split vertical jaws down the center
        gap_width = 0.14 + 0.06 * np.sin(ny * 4.0)
        void_gap = inner_door & (np.abs(nx) < gap_width)
        jaw_teeth = void_gap & (np.abs(nx) > gap_width - 0.055) & ((yy % 5) < 3)

        # Glowing red-amber oculus deep inside the split doorway
        oculus = (np.sqrt(nx ** 2 + (ny + 0.10) ** 2) < 0.095)
        pupil = (np.abs(nx) < 0.025) & (np.abs(ny + 0.10) < 0.075)
        panel_grid = ((xx % 8 == 0) | (yy % 10 == 0)) & inner_door & (~void_gap)

        frame_only = outer_frame & (~inner_door)
        door_leaf = inner_door & (~void_gap)

        rgba[..., 0] = frame_only * 0.46 + door_leaf * (0.54 - 0.16 * panel_grid) + jaw_teeth * 0.88 + oculus * 0.98
        rgba[..., 1] = frame_only * 0.44 + door_leaf * (0.50 - 0.16 * panel_grid) + jaw_teeth * 0.82 + oculus * 0.28
        rgba[..., 2] = frame_only * 0.40 + door_leaf * (0.42 - 0.14 * panel_grid) + jaw_teeth * 0.74 + oculus * 0.16
        # Darken pupil
        rgba[pupil, 0] = 0.15
        rgba[pupil, 1] = 0.98
        rgba[pupil, 2] = 0.72
        rgba[..., 3] = outer_frame.astype(np.float32)

    else:  # VORE_SPINDLE
        # Inverted 3-limbed Quake Vore / ceiling pendulum + glowing homing polyhedron
        cables = np.zeros((s, s), dtype=np.float32)
        cables = _draw_segment(cables, s * 0.50, 0.0, s * 0.50, s * 0.32, 2.0)
        cables = _draw_segment(cables, s * 0.38, 0.0, s * 0.46, s * 0.28, 1.2)
        cables = _draw_segment(cables, s * 0.62, 0.0, s * 0.54, s * 0.28, 1.2)
        # 3 scythe-like chitinous limbs curving down around the central spore
        cables = _draw_segment(cables, s * 0.50, s * 0.28, s * 0.18, s * 0.48, 2.4)
        cables = _draw_segment(cables, s * 0.18, s * 0.48, s * 0.28, s * 0.84, 1.8)
        cables = _draw_segment(cables, s * 0.50, s * 0.28, s * 0.82, s * 0.48, 2.4)
        cables = _draw_segment(cables, s * 0.82, s * 0.48, s * 0.72, s * 0.84, 1.8)
        cables = _draw_segment(cables, s * 0.50, s * 0.28, s * 0.50, s * 0.78, 2.0)

        # Central diamond/octahedral Vore homing spore
        spore_dist = np.abs(nx) * 1.2 + np.abs(ny - 0.12) * 1.1
        spore = spore_dist < 0.22
        spore_rim = spore & (spore_dist > 0.16)

        alpha = np.clip(cables + spore.astype(np.float32), 0.0, 1.0)
        rgba[..., 0] = cables * 0.48 + spore * 0.86 + spore_rim * 0.25
        rgba[..., 1] = cables * 0.56 + spore * 0.22 + spore_rim * 0.75
        rgba[..., 2] = cables * 0.42 + spore * 0.78 + spore_rim * 0.45
        rgba[..., 3] = (alpha > 0.1).astype(np.float32)

    return (np.clip(rgba, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


class NullrunMonsterDirector:
    """Deterministic 35-tic encounter state machine coordinating NULLRUN monsters + corridor swaps."""

    def __init__(self, seed: int = 20261030) -> None:
        self.seed = int(seed)

    def evaluate_encounter_tic(
        self,
        kind: str,
        tic: int,
        player_in_los: bool,
        player_looking_at_monster: bool,
        dist_units: float,
    ) -> dict[str, Any]:
        """Evaluate a single 35-Hz tic for monster `kind` and return action/corridor-swap flags."""
        spec = MONSTER_SPECS[kind]
        phase_in_cycle = tic % (spec.telegraph_tics * 2)
        charging = player_in_los and (phase_in_cycle < spec.telegraph_tics)
        discharging = player_in_los and (phase_in_cycle == spec.telegraph_tics)

        corridor_swap = False
        invert_player_yaw = False
        active_banner = spec.banner_title

        if kind == "SURVEYOR":
            # Crossing the laser beam while in LOS triggers an immediate MyHouse corridor swap
            if discharging and dist_units < 512.0:
                corridor_swap = True
        elif kind == "WIRE_SHAMBLER":
            # 28-tic Shambler lightning charge: only hits if player stays in LOS on tic 28
            if charging:
                active_banner = f"THE BALLAST HUSK / CHARGING ({spec.telegraph_tics - phase_in_cycle} TICS)"
        elif kind == "THRESHOLD_MIMIC":
            # Wakes only inside 192 units; biting the player flips their yaw 180 deg and swaps the hallway
            if dist_units < 192.0 and discharging:
                corridor_swap = True
                invert_player_yaw = True
        elif kind == "VORE_SPINDLE":
            if discharging:
                active_banner = "THE SPINDLE / HOMING POLYHEDRON LAUNCHED"

        return {
            "kind": kind,
            "tic": tic,
            "charging": charging,
            "attack_discharge": discharging,
            "trigger_corridor_swap": corridor_swap,
            "invert_player_yaw_180": invert_player_yaw,
            "should_player_break_los": (kind in ("SURVEYOR", "WIRE_SHAMBLER")) and charging,
            "banner_title": active_banner,
            "banner_hint": spec.banner_hint,
        }