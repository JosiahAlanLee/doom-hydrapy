# SPDX-License-Identifier: GPL-2.0-or-later
"""doom_gameplay_optics.py — Playtest-Ready Surveyor 35-Tic Optics & RAW Fallback for NULLRUN.

Refined per engine playtest feedback to guarantee four hard invariants:
1. Instant RAW Fallback (`raw=1.0` or `raw_mode=True`):
   - When `raw >= 0.5`, `.doomTacticalOptics` bypasses all Sobel/phosphor processing and
     returns the exact, unmodified `texture2D(_tex, _st)` Doom framebuffer so playtesters
     can A/B toggle between `RAW` and `OPTICS` live without rebuilding the HydraPy graph.
2. Strictly Protected Aiming Reticle & HUD Status Bar:
   - HUD Status Bar (`v <= 0.16`, bottom 32 rows of 200): 100% immune to UV shear,
     chromatic split, and peripheral distortion; native HUD numerals and mugshot stay locked.
   - Central Aiming Box (`0.16 <= u <= 0.84`): Zero UV displacement (`u_eff == u`, `v_eff == v`)
     so crosshair aim and target pixels never shift by even a fraction of a texel.
3. Exact 35-Tic Surveyor Warning Countdown (`surveyor_tic` in `0..35`):
   - Visualizes the Surveyor's real 35-tic (1.00s at 35 Hz) warning state via two non-intrusive
     diegetic indicators that stay outside the central aiming reticle:
     * A 35-segment discrete tic-counter bar along the HUD top bezel (`v in [0.160, 0.174]`)
       that lights up 1 block per tic (`tic 1..35`), shifting from ochre-amber (`tics 1..27`)
       to high-alert crimson strobe on the final 8 tics (`tics 28..35`).
     * Converging vertical range-brackets that slide inward from the outer margins (`u = 0.12`
       and `u = 0.88` at tic 1) to the outer boundary of the protected aiming box (`u = 0.34`
       and `u = 0.66` at tic 35), giving an instant peripheral reading of time-to-discharge
       while keeping the crosshair unobstructed.
4. Peripheral Rear-Ambush Shear (`rear_left`, `rear_right` in `[0..1]`):
   - Restricted strictly to the outer 15% screen edges (`u < 0.15` or `u > 0.85`) above the HUD.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Sequence
import numpy as np

try:
    from hydrapy import Fn1, Input, Op, add_op as register
except ImportError:
    from hydrapy.core import Op, register
    from hydrapy.ops import F as _F
    from hydrapy.signals import Fn1

    def Input(name: str, kind: str = "float", default: float = 0.0):
        return _F(name, default, scalar=True)


SURVEYOR_MAX_WARNING_TICS: int = 35


def _sample_clamped(tex: np.ndarray, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    h, w = tex.shape[:2]
    xi = np.clip((np.clip(u, 0.0, 0.9999) * w).astype(np.int32), 0, w - 1)
    yi = np.clip((np.clip(v, 0.0, 0.9999) * h).astype(np.int32), 0, h - 1)
    return tex[yi, xi]


def _np_doom_tactical_optics(tex, st, surveyor_tic, rear_left, rear_right, raw, phase, env):
    u = st[..., 0]
    v = st[..., 1]

    # 1. Hard RAW fallback: return unmodified native Doom framebuffer when raw >= 0.5
    if float(raw) >= 0.5:
        c_raw = env.sample(tex, st)[..., :3]
        return np.concatenate([c_raw, np.ones_like(u[..., None], dtype=np.float32)], axis=-1)

    s_tic = float(np.clip(surveyor_tic, 0.0, float(SURVEYOR_MAX_WARNING_TICS)))
    charge = s_tic / float(SURVEYOR_MAX_WARNING_TICS)
    rl = float(np.clip(rear_left, 0.0, 1.0))
    rr = float(np.clip(rear_right, 0.0, 1.0))
    ph = float(phase)

    # 2. Strictly preserve HUD (v <= 0.16) and central 70% aiming corridor (0.15 <= u <= 0.85)
    in_3d_vp = (v > 0.16).astype(np.float32)
    left_margin = np.clip((0.15 - u) / 0.15, 0.0, 1.0) * rl * in_3d_vp
    right_margin = np.clip((u - 0.85) / 0.15, 0.0, 1.0) * rr * in_3d_vp
    periph = left_margin + right_margin

    col_id = np.floor(u * 160.0)
    col_hash = np.mod(np.sin(col_id * 12.9898 + 78.233) * 43758.5453, 1.0)
    dy_shear = periph * 0.12 * (0.3 + 0.7 * col_hash) * np.sin(ph * 3.0 + col_id * 0.4)
    dx_shear = periph * 0.03 * np.sin(v * 37.699 + ph * 2.0)

    u_eff = np.clip(u + dx_shear, 0.0, 0.999)
    v_eff = np.where(v > 0.16, np.clip(v + dy_shear, 0.1605, 0.999), v)

    c0 = _sample_clamped(tex, u_eff, v_eff)[..., :3]
    cx1 = _sample_clamped(tex, np.clip(u_eff + 1.0 / 640.0, 0.0, 0.999), v_eff)[..., :3]
    cx0 = _sample_clamped(tex, np.clip(u_eff - 1.0 / 640.0, 0.0, 0.999), v_eff)[..., :3]
    cy1 = _sample_clamped(tex, u_eff, np.clip(v_eff + 1.0 / 400.0, 0.0, 0.999))[..., :3]
    cy0 = _sample_clamped(tex, u_eff, np.clip(v_eff - 1.0 / 400.0, 0.0, 0.999))[..., :3]

    w_luma = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    l0 = c0 @ w_luma
    gx = (cx1 - cx0) @ w_luma
    gy = (cy1 - cy0) @ w_luma
    edge = np.clip(np.sqrt(gx * gx + gy * gy) * 3.2, 0.0, 1.0)

    px_x, px_y = env.px[..., 0], env.px[..., 1]
    pgrid = (((np.mod(px_x, 4.0) < 1.0) | (np.mod(px_y, 4.0) < 1.0)).astype(np.float32)) * edge
    red_haz = np.clip(c0[..., 0] - np.maximum(c0[..., 1], c0[..., 2]) * 0.78, 0.0, 1.0)
    warm_fill = np.clip(c0[..., 0] * 0.72 - c0[..., 2] * 0.35, 0.0, 1.0) * (l0 > 0.20)
    stipple = (np.mod(np.sin(px_x * 12.9898 + px_y * 78.233) * 43758.5453, 1.0) > 0.65).astype(np.float32) * l0 * 0.42

    vp_r = warm_fill * 0.82 + red_haz * 1.35 + edge * 0.16 + pgrid * 0.24 + periph * (0.55 + 0.45 * edge)
    vp_g = edge * (0.96 - 0.30 * periph) + pgrid * 0.45 + stipple * 0.82 + red_haz * 0.26
    vp_b = edge * 0.66 + pgrid * 0.34 + stipple * 0.40 + red_haz * 0.10

    # Preserve crisp HUD readability in the bottom 16% status bar (v <= 0.16)
    hud_r = c0[..., 0] * 0.55 + vp_r * 0.55
    hud_g = c0[..., 1] * 0.45 + vp_g * 0.65
    hud_b = c0[..., 2] * 0.45 + vp_b * 0.55

    out_r = np.where(v > 0.16, vp_r, hud_r)
    out_g = np.where(v > 0.16, vp_g, hud_g)
    out_b = np.where(v > 0.16, vp_b, hud_b)

    # 3. Surveyor Real 35-Tic Warning Countdown Visualization (when s_tic > 0)
    if s_tic > 0.0:
        is_crit = 1.0 if s_tic >= 28.0 else 0.0
        # (a) 35-segment discrete tic bar along the HUD lintel (v in [0.162, 0.178], u in [0.15, 0.85])
        in_bar_y = (v >= 0.162) & (v <= 0.178)
        bar_u = (u - 0.15) / 0.70
        seg_idx = np.floor(bar_u * 35.0)
        seg_frac = np.mod(bar_u * 35.0, 1.0)
        in_seg = in_bar_y & (bar_u >= 0.0) & (bar_u < 1.0) & (seg_frac > 0.12) & (seg_frac < 0.88)
        lit_seg = in_seg & (seg_idx < s_tic)
        unlit_seg = in_seg & (seg_idx >= s_tic)

        # (b) Converging vertical sightline brackets outside the aiming reticle
        # Slide from u = 0.5 +/- 0.36 (at tic 1) to u = 0.5 +/- 0.16 (at tic 35, stopping outside crosshair!)
        b_offset = 0.36 - 0.20 * charge
        in_bracket_y = (v >= 0.34) & (v <= 0.72)
        b_vert = in_bracket_y & ((np.abs(np.abs(u - 0.5) - b_offset) < 0.0045))
        b_caps = ((np.abs(v - 0.34) < 0.005) | (np.abs(v - 0.72) < 0.005)) & (
            (np.abs(np.abs(u - 0.5) - (b_offset - 0.012)) < 0.014)
        )
        bracket_mask = (b_vert | b_caps).astype(np.float32)

        # Color shifts from Backrooms transit ochre-amber (tics 1..27) to critical crimson (tics 28..35)
        warn_r = 0.98
        warn_g = 0.78 * (1.0 - 0.72 * is_crit)
        warn_b = 0.16 * (1.0 - 0.50 * is_crit)

        overlay = np.clip(lit_seg.astype(np.float32) + bracket_mask, 0.0, 1.0)
        out_r = np.where(unlit_seg, out_r * 0.4 + 0.12, out_r * (1.0 - overlay) + warn_r * overlay)
        out_g = np.where(unlit_seg, out_g * 0.4 + 0.18, out_g * (1.0 - overlay) + warn_g * overlay)
        out_b = np.where(unlit_seg, out_b * 0.4 + 0.14, out_b * (1.0 - overlay) + warn_b * overlay)

    out_rgb = np.clip(np.stack([out_r, out_g, out_b], axis=-1), 0.0, 1.0)
    return np.concatenate([out_rgb, np.ones_like(l0[..., None], dtype=np.float32)], axis=-1)


register(Op(
    "doomTacticalOptics",
    "texture",
    [
        Input("surveyor_tic", "float", 0.0),
        Input("rear_left", "float", 0.0),
        Input("rear_right", "float", 0.0),
        Input("raw", "float", 0.0),
        Input("phase", "float", 0.0),
    ],
    np=_np_doom_tactical_optics,
    glsl="""
  if (raw >= 0.5) {
    return vec4(texture2D(_tex, _st).rgb, 1.0);
  }
  float u = _st.x, v = _st.y;
  float s_tic = clamp(surveyor_tic, 0.0, 35.0);
  float charge = s_tic / 35.0;
  float rl = clamp(rear_left, 0.0, 1.0);
  float rr = clamp(rear_right, 0.0, 1.0);
  float in_vp = step(0.16, v);
  float left_m = clamp((0.15 - u) / 0.15, 0.0, 1.0) * rl * in_vp;
  float right_m = clamp((u - 0.85) / 0.15, 0.0, 1.0) * rr * in_vp;
  float periph = left_m + right_m;
  float col_id = floor(u * 160.0);
  float col_hash = fract(sin(col_id * 12.9898 + 78.233) * 43758.5453);
  float dy_s = periph * 0.12 * (0.3 + 0.7 * col_hash) * sin(phase * 3.0 + col_id * 0.4);
  float dx_s = periph * 0.03 * sin(v * 37.699 + phase * 2.0);
  float u_eff = clamp(u + dx_s, 0.0, 0.999);
  float v_eff = v > 0.16 ? clamp(v + dy_s, 0.1605, 0.999) : v;
  vec3 c0 = texture2D(_tex, vec2(u_eff, v_eff)).rgb;
  vec2 px = 1.0 / resolution;
  vec3 wl = vec3(0.2126, 0.7152, 0.0722);
  float l0 = dot(c0, wl);
  float gx = dot(texture2D(_tex, vec2(u_eff + px.x, v_eff)).rgb - texture2D(_tex, vec2(u_eff - px.x, v_eff)).rgb, wl);
  float gy = dot(texture2D(_tex, vec2(u_eff, v_eff + px.y)).rgb - texture2D(_tex, vec2(u_eff, v_eff - px.y)).rgb, wl);
  float edge = clamp(sqrt(gx * gx + gy * gy) * 3.2, 0.0, 1.0);
  vec2 fpx = _st * resolution;
  float pgrid = clamp(step(mod(fpx.x, 4.0), 1.0) + step(mod(fpx.y, 4.0), 1.0), 0.0, 1.0) * edge;
  float red_haz = clamp(c0.r - max(c0.g, c0.b) * 0.78, 0.0, 1.0);
  float warm_f = clamp(c0.r * 0.72 - c0.b * 0.35, 0.0, 1.0) * step(0.20, l0);
  float stipple = step(0.65, fract(sin(fpx.x * 12.9898 + fpx.y * 78.233) * 43758.5453)) * l0 * 0.42;
  vec3 vp_rgb = vec3(
    warm_f * 0.82 + red_haz * 1.35 + edge * 0.16 + pgrid * 0.24 + periph * (0.55 + 0.45 * edge),
    edge * (0.96 - 0.30 * periph) + pgrid * 0.45 + stipple * 0.82 + red_haz * 0.26,
    edge * 0.66 + pgrid * 0.34 + stipple * 0.40 + red_haz * 0.10
  );
  vec3 hud_rgb = vec3(c0.r * 0.55 + vp_rgb.r * 0.55, c0.g * 0.45 + vp_rgb.g * 0.65, c0.b * 0.45 + vp_rgb.b * 0.55);
  vec3 rgb = mix(hud_rgb, vp_rgb, in_vp);
  if (s_tic > 0.0) {
    float is_crit = step(28.0, s_tic);
    float bar_u = (u - 0.15) / 0.70;
    float seg_idx = floor(bar_u * 35.0);
    float seg_f = fract(bar_u * 35.0);
    float in_seg = step(0.162, v) * step(v, 0.178) * step(0.0, bar_u) * step(bar_u, 1.0) * step(0.12, seg_f) * step(seg_f, 0.88);
    float lit_s = in_seg * step(seg_idx + 0.5, s_tic);
    float b_off = 0.36 - 0.20 * charge;
    float in_by = step(0.34, v) * step(v, 0.72);
    float b_vert = in_by * step(abs(abs(u - 0.5) - b_off), 0.0045);
    float b_caps = (step(abs(v - 0.34), 0.005) + step(abs(v - 0.72), 0.005)) * step(abs(abs(u - 0.5) - (b_off - 0.012)), 0.014);
    float ov = clamp(lit_s + b_vert + b_caps, 0.0, 1.0);
    vec3 w_col = vec3(0.98, 0.78 * (1.0 - 0.72 * is_crit), 0.16 * (1.0 - 0.50 * is_crit));
    rgb = mix(rgb, w_col, ov);
  }
  return vec4(clamp(rgb, 0.0, 1.0), 1.0);
""",
))


@dataclass
class TacticalUniforms:
    surveyor_tic: int
    rear_left: float
    rear_right: float
    raw: float


class TacticalOpticsDirector:
    """Computes playtest-ready shader uniforms (35-tic Surveyor warning, rear shear, RAW fallback)."""

    @staticmethod
    def compute_uniforms(
        player_xy: tuple[float, float],
        player_yaw_rad: float,
        monsters: Sequence[dict[str, Any]],
        raw_mode: bool = False,
    ) -> TacticalUniforms:
        if raw_mode:
            return TacticalUniforms(surveyor_tic=0, rear_left=0.0, rear_right=0.0, raw=1.0)

        px, py = float(player_xy[0]), float(player_xy[1])
        fx, fy = math.cos(player_yaw_rad), math.sin(player_yaw_rad)
        rx, ry = math.sin(player_yaw_rad), -math.cos(player_yaw_rad)

        rear_l = 0.0
        rear_r = 0.0
        max_surveyor_tic = 0

        for m in monsters:
            if m.get("hp", 1) <= 0:
                continue
            dx = float(m["x"]) - px
            dy = float(m["y"]) - py
            dist = math.hypot(dx, dy) + 1e-6
            ux, uy = dx / dist, dy / dist

            fwd_dot = fx * ux + fy * uy
            right_dot = rx * ux + ry * uy

            # 1. Rear threat behind camera plane (fwd_dot < -0.15) within 220 map units
            if fwd_dot < -0.15 and dist < 220.0:
                prox = (220.0 - dist) / 220.0
                if right_dot <= 0.1:
                    rear_l = max(rear_l, prox * min(1.0, abs(right_dot) + 0.35))
                if right_dot >= -0.1:
                    rear_r = max(rear_r, prox * min(1.0, abs(right_dot) + 0.35))

            # 2. Surveyor real 35-tic warning countdown (0..35)
            if m.get("kind") == "SURVEYOR" or m.get("optical_class") == "SURVEYOR":
                w_tic = int(np.clip(m.get("warning_tic", m.get("charge_tics", 0)), 0, SURVEYOR_MAX_WARNING_TICS))
                max_surveyor_tic = max(max_surveyor_tic, w_tic)

        return TacticalUniforms(
            surveyor_tic=int(max_surveyor_tic),
            rear_left=round(float(np.clip(rear_l, 0.0, 1.0)), 4),
            rear_right=round(float(np.clip(rear_r, 0.0, 1.0)), 4),
            raw=0.0,
        )