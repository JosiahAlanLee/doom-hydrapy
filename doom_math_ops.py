# SPDX-License-Identifier: GPL-2.0-or-later
"""doom_math_ops.py — Custom Shader & Mathematical Operators for `doom-hydrapy`.

Designed as a drop-in companion to `ascii_op.py` and `legible_ops.py` in
https://github.com/JosiahAlanLee/doom-hydrapy.

Registers four texture operators on `Chain` with both GLSL ES 1.00 hardware shaders
and vectorized NumPy CPU fallbacks:
1. `.doomMeltShear(melt=0.35, shear=0.14, columns=160.0, phase=0.0)`
   Combines Doom's classic 1993 160-column pseudorandom screen-wipe melt (`f_wipe.c`)
   with Family 376 (`openai/math/lean/docs/376.md`) incompressible alternating
   solenoidal shear (det DF == 1) across BSP wall spans.
2. `.doomPoincareCathedral(zoom=1.15, twist=0.0, hud_ring=1.0, sectors=6.0)`
   Conformal Mobius + Poincare hyperbolic disk projection of the 3D Doom viewport
   (top 84% of the 640x400 frame), while wrapping Doom's 32-pixel status bar
   (bottom 16%: mugshot, ammo, health, armor) into a circular polar cockpit bezel
   around the outer rim of the disk.
3. `.doomSobelVectorScope(edge_gain=2.4, hazard_glow=1.4, phosphor=0.65, scan=200.0)`
   Extracts 3x3 Sobel gradients on the 640x400 framebuffer to separate architectural
   BSP wall/plane edges (rendered in Tektronix cyan-green vector phosphor) from
   muzzle flashes, imp fireballs, and red damage screens (rendered as high-bloom
   crimson-amber vector phasors).
4. `.doomAnaglyphRelief(parallax=0.018, light_depth=0.65, horizon=0.56, mode=0.0)`
   Reconstructs a pseudo-depth field z_hat(x, y) from Doom's diminished-lighting law
   (wall/flat luminance decay with distance) fused with floor/ceiling perspective plane
   geometry |y - horizon|, synthesizing either a Red-Cyan 3D stereoscopic anaglyph
   (`mode < 0.5`) or a normal-mapped bas-relief copper/emerald shader (`mode >= 0.5`).
"""
from __future__ import annotations

import math
import numpy as np

try:
    from hydrapy import Input, Op, add_op as register
except ImportError:
    from hydrapy.core import Op, register
    from hydrapy.ops import F as _F

    def Input(name: str, kind: str = "float", default: float = 0.0):
        return _F(name, default, scalar=True)


def _sample_clamped(tex: np.ndarray, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    h, w = tex.shape[:2]
    xi = np.clip((np.mod(u, 1.0) * w).astype(np.int32), 0, w - 1)
    yi = np.clip((np.mod(v, 1.0) * h).astype(np.int32), 0, h - 1)
    return tex[yi, xi]


# =============================================================================
# 1. doomMeltShear — Classic 160-Column `f_wipe.c` Melt + Family 376 Solenoidal Shear
# =============================================================================

def _np_doom_melt_shear(tex, st, melt, shear, columns, phase, env):
    u = st[..., 0].copy()
    v = st[..., 1].copy()
    cols = max(float(columns), 8.0)
    col_id = np.floor(u * cols)
    # Deterministic hash matching M_Random column stagger in Doom's f_wipe.c
    col_hash = np.mod(np.sin(col_id * 12.9898 + 78.233) * 43758.5453, 1.0)
    melt_wave = 0.5 + 0.5 * np.sin(float(phase) + col_id * 0.15)
    dy_melt = float(melt) * (0.25 + 0.75 * col_hash) * melt_wave

    # Family 376 alternating solenoidal shear (area-preserving det J = 1 on (u, v))
    u1 = np.mod(u + float(shear) * np.sin(6.2831853 * 4.0 * v + float(phase)), 1.0)
    v1 = np.mod(v + dy_melt + float(shear) * 0.65 * np.cos(6.2831853 * 6.0 * u1 - float(phase)), 1.0)

    rgba = _sample_clamped(tex, u1, v1).copy()
    # Highlight sheared column boundaries with subtle ember glow proportional to local displacement
    seam = np.exp(-((np.mod(u1 * cols, 1.0) - 0.5) / 0.12) ** 2) * abs(float(melt))
    rgba[..., 0] = np.clip(rgba[..., 0] + 0.35 * seam * col_hash, 0.0, 1.0)
    rgba[..., 1] = np.clip(rgba[..., 1] + 0.12 * seam * col_hash, 0.0, 1.0)
    rgba[..., 3] = 1.0
    return rgba.astype(np.float32)


register(Op(
    "doomMeltShear",
    "texture",
    [
        Input("melt", "float", 0.28),
        Input("shear", "float", 0.12),
        Input("columns", "float", 160.0),
        Input("phase", "float", 0.0),
    ],
    np=_np_doom_melt_shear,
    glsl="""
  float cols = max(columns, 8.0);
  float col_id = floor(_st.x * cols);
  float col_hash = fract(sin(col_id * 12.9898 + 78.233) * 43758.5453);
  float melt_wave = 0.5 + 0.5 * sin(phase + col_id * 0.15);
  float dy_melt = melt * (0.25 + 0.75 * col_hash) * melt_wave;
  float u1 = fract(_st.x + shear * sin(25.13274 * _st.y + phase));
  float v1 = fract(_st.y + dy_melt + shear * 0.65 * cos(37.69911 * u1 - phase));
  vec4 c = texture2D(_tex, vec2(u1, v1));
  float seam = exp(-pow((fract(u1 * cols) - 0.5) / 0.12, 2.0)) * abs(melt);
  c.rgb = clamp(c.rgb + vec3(0.35, 0.12, 0.02) * seam * col_hash, 0.0, 1.0);
  return vec4(c.rgb, 1.0);
""",
))


# =============================================================================
# 2. doomPoincareCathedral — Non-Euclidean Disk Viewport + Polar Status-Bar Bezel
# =============================================================================

def _np_doom_poincare_cathedral(tex, st, zoom, twist, hud_ring, sectors, env):
    asp = env.res[0] / env.res[1]
    px = (st[..., 0] - 0.5) * 2.0 * asp
    py = (st[..., 1] - 0.5) * 2.0
    r = np.sqrt(px * px + py * py)
    ang = np.arctan2(py, px) + float(twist)

    # Dihedral sector symmetry modulation inside the Poincare disk
    sec = max(float(sectors), 1.0)
    folded_ang = np.arccos(np.clip(np.cos(ang * sec * 0.5), -1.0, 1.0)) / (sec * 0.5)
    blend_ang = 0.65 * ang + 0.35 * folded_ang

    # Hyperbolic Poincare radial map: tanh-compressed geodesic radius
    r_hyp = np.tanh(r * max(float(zoom), 0.2))
    u_vp = np.mod(0.5 + 0.48 * r_hyp * np.cos(blend_ang), 1.0)
    # Map into the 84% 3D viewport of Doom (rows 0..84% in top-down array)
    v_vp = np.clip(0.82 * (0.5 + 0.48 * r_hyp * np.sin(blend_ang)), 0.005, 0.835)
    vp_col = _sample_clamped(tex, u_vp, v_vp)

    # Polar HUD ring: wrap Doom's 32-pixel bottom status bar (rows 84%..100%) around r in [0.78, 0.96]
    u_hud = np.mod((ang / (2.0 * math.pi)) + 0.5, 1.0)
    v_hud = 0.84 + np.clip((r - 0.78) / 0.18, 0.0, 1.0) * 0.155
    hud_col = _sample_clamped(tex, u_hud, v_hud)

    in_hud = ((r >= 0.78) & (r <= 0.96)).astype(np.float32) * float(np.clip(hud_ring, 0.0, 1.0))
    in_disk = (r <= 0.96).astype(np.float32)
    rim_glow = np.exp(-((r - 0.78) / 0.018) ** 2) + np.exp(-((r - 0.96) / 0.018) ** 2)

    out_rgb = vp_col[..., :3] * (1.0 - in_hud[..., None]) + hud_col[..., :3] * in_hud[..., None]
    out_rgb = out_rgb * in_disk[..., None] + np.array([0.85, 0.52, 0.16], dtype=np.float32) * (rim_glow[..., None] * 0.55)
    out_rgb = np.clip(out_rgb, 0.0, 1.0)
    return np.concatenate([out_rgb, np.ones_like(r[..., None], dtype=np.float32)], axis=-1)


register(Op(
    "doomPoincareCathedral",
    "texture",
    [
        Input("zoom", "float", 1.15),
        Input("twist", "float", 0.0),
        Input("hud_ring", "float", 1.0),
        Input("sectors", "float", 6.0),
    ],
    np=_np_doom_poincare_cathedral,
    glsl="""
  float asp = resolution.x / resolution.y;
  vec2 p = vec2((_st.x - 0.5) * 2.0 * asp, (_st.y - 0.5) * 2.0);
  float r = length(p);
  float ang = atan(p.y, p.x) + twist;
  float sec = max(sectors, 1.0);
  float fang = acos(clamp(cos(ang * sec * 0.5), -1.0, 1.0)) / (sec * 0.5);
  float bang = 0.65 * ang + 0.35 * fang;
  float e2r = exp(2.0 * clamp(r * max(zoom, 0.2), 0.0, 8.0));
  float r_hyp = (e2r - 1.0) / (e2r + 1.0);
  float u_vp = fract(0.5 + 0.48 * r_hyp * cos(bang));
  float v_vp = clamp(0.16 + 0.82 * (0.5 + 0.48 * r_hyp * sin(bang)), 0.16, 0.995);
  vec3 vp_col = texture2D(_tex, vec2(u_vp, v_vp)).rgb;
  float u_hud = fract(ang / 6.2831853 + 0.5);
  float v_hud = clamp((0.96 - r) / 0.18, 0.0, 1.0) * 0.16;
  vec3 hud_col = texture2D(_tex, vec2(u_hud, v_hud)).rgb;
  float in_hud = step(0.78, r) * step(r, 0.96) * clamp(hud_ring, 0.0, 1.0);
  float in_disk = step(r, 0.96);
  float rim = exp(-pow((r - 0.78) / 0.018, 2.0)) + exp(-pow((r - 0.96) / 0.018, 2.0));
  vec3 rgb = mix(vp_col, hud_col, in_hud) * in_disk + vec3(0.85, 0.52, 0.16) * rim * 0.55;
  return vec4(clamp(rgb, 0.0, 1.0), 1.0);
""",
))


# =============================================================================
# 3. doomSobelVectorScope — Tektronix XY Vector-CRT & Muzzle/Hazard Phasor Bloom
# =============================================================================

def _np_doom_sobel_vector_scope(tex, st, edge_gain, hazard_glow, phosphor, scan, env):
    c0 = env.sample(tex, st)[..., :3]
    cx1 = env.sample_offset(tex, st, (1.0, 0.0))[..., :3]
    cx0 = env.sample_offset(tex, st, (-1.0, 0.0))[..., :3]
    cy1 = env.sample_offset(tex, st, (0.0, 1.0))[..., :3]
    cy0 = env.sample_offset(tex, st, (0.0, -1.0))[..., :3]

    w_luma = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    lx1, lx0 = cx1 @ w_luma, cx0 @ w_luma
    ly1, ly0 = cy1 @ w_luma, cy0 @ w_luma
    l0 = c0 @ w_luma

    gx = lx1 - lx0
    gy = ly1 - ly0
    grad = np.clip(np.sqrt(gx * gx + gy * gy) * float(edge_gain) * 2.2, 0.0, 1.0)

    # Separate vertical BSP wall spans (|gx| > |gy|) from floor/ceiling horizons
    wall_ness = np.abs(gx) / (np.abs(gx) + np.abs(gy) + 1e-5)

    # Isolate Doom PLAYPAL hazard/muzzle/fireball reds & ambers: R - max(G, B)
    red_excess = np.clip(c0[..., 0] - np.maximum(c0[..., 1], c0[..., 2]) * 0.85, 0.0, 1.0)
    muzzle = np.clip((l0 - 0.62) * 2.5, 0.0, 1.0) * np.clip(c0[..., 0] - c0[..., 2], 0.0, 1.0)
    hazard = np.clip((red_excess * 1.8 + muzzle * 1.5) * float(hazard_glow), 0.0, 1.0)

    scanline = 0.82 + 0.18 * np.sin(st[..., 1] * float(scan) * 6.2831853)
    ph = float(np.clip(phosphor, 0.0, 1.0))

    # Tektronix P31 cyan-green vector trace + crimson/gold hazard bloom
    vec_r = grad * (0.12 + 0.25 * (1.0 - wall_ness)) + hazard * 0.98 + c0[..., 0] * (1.0 - ph) * 0.35
    vec_g = grad * (0.85 + 0.15 * wall_ness) + hazard * 0.36 + c0[..., 1] * (1.0 - ph) * 0.35
    vec_b = grad * (0.45 + 0.50 * wall_ness) + hazard * 0.14 + c0[..., 2] * (1.0 - ph) * 0.35

    out_rgb = np.clip(np.stack([vec_r, vec_g, vec_b], axis=-1) * scanline[..., None], 0.0, 1.0)
    return np.concatenate([out_rgb, np.ones_like(grad[..., None], dtype=np.float32)], axis=-1)


register(Op(
    "doomSobelVectorScope",
    "texture",
    [
        Input("edge_gain", "float", 2.4),
        Input("hazard_glow", "float", 1.4),
        Input("phosphor", "float", 0.65),
        Input("scan", "float", 200.0),
    ],
    np=_np_doom_sobel_vector_scope,
    glsl="""
  vec2 px = 1.0 / resolution;
  vec3 c0 = texture2D(_tex, _st).rgb;
  vec3 cx1 = texture2D(_tex, _st + vec2(px.x, 0.0)).rgb;
  vec3 cx0 = texture2D(_tex, _st - vec2(px.x, 0.0)).rgb;
  vec3 cy1 = texture2D(_tex, _st + vec2(0.0, px.y)).rgb;
  vec3 cy0 = texture2D(_tex, _st - vec2(0.0, px.y)).rgb;
  vec3 wl = vec3(0.2126, 0.7152, 0.0722);
  float gx = dot(cx1 - cx0, wl);
  float gy = dot(cy1 - cy0, wl);
  float l0 = dot(c0, wl);
  float grad = clamp(sqrt(gx * gx + gy * gy) * edge_gain * 2.2, 0.0, 1.0);
  float wall_ness = abs(gx) / (abs(gx) + abs(gy) + 0.0001);
  float red_ex = clamp(c0.r - max(c0.g, c0.b) * 0.85, 0.0, 1.0);
  float muzzle = clamp((l0 - 0.62) * 2.5, 0.0, 1.0) * clamp(c0.r - c0.b, 0.0, 1.0);
  float haz = clamp((red_ex * 1.8 + muzzle * 1.5) * hazard_glow, 0.0, 1.0);
  float scanline = 0.82 + 0.18 * sin(_st.y * scan * 6.2831853);
  float ph = clamp(phosphor, 0.0, 1.0);
  vec3 rgb = vec3(
    grad * (0.12 + 0.25 * (1.0 - wall_ness)) + haz * 0.98,
    grad * (0.85 + 0.15 * wall_ness) + haz * 0.36,
    grad * (0.45 + 0.50 * wall_ness) + haz * 0.14
  ) + c0 * (1.0 - ph) * 0.35;
  return vec4(clamp(rgb * scanline, 0.0, 1.0), 1.0);
""",
))


# =============================================================================
# 4. doomAnaglyphRelief — Diminished-Lighting Depth Reconstruction & 3D Parallax
# =============================================================================

def _np_doom_anaglyph_relief(tex, st, parallax, light_depth, horizon, mode, env):
    c0 = env.sample(tex, st)[..., :3]
    w_luma = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    luma = c0 @ w_luma

    # Reconstruct normalized closeness (1 = near, 0 = far horizon) from:
    # 1) Doom's diminished lighting (brighter = closer to player / light source)
    # 2) Floor/ceiling perspective plane geometry |y - horizon| (larger |y - horizon| = closer)
    plane_prox = np.clip(np.abs(st[..., 1] - float(horizon)) * 2.2, 0.0, 1.0)
    ld = float(np.clip(light_depth, 0.0, 1.0))
    closeness = ld * luma + (1.0 - ld) * plane_prox
    disp = (closeness - 0.45) * float(parallax)

    u_left = np.clip(st[..., 0] - disp, 0.0, 1.0)
    u_right = np.clip(st[..., 0] + disp, 0.0, 1.0)
    v_cur = st[..., 1]

    left_rgb = _sample_clamped(tex, u_left, v_cur)[..., :3]
    right_rgb = _sample_clamped(tex, u_right, v_cur)[..., :3]

    if float(mode) < 0.5:
        # Duboscq / optimist Red-Cyan 3D anaglyph preserving luminance detail
        r_ch = 0.70 * left_rgb[..., 0] + 0.30 * left_rgb[..., 1]
        g_ch = right_rgb[..., 1]
        b_ch = right_rgb[..., 2]
        out_rgb = np.stack([r_ch, g_ch, b_ch], axis=-1)
    else:
        # Shaded normal-map metallic relief
        cx1 = env.sample_offset(tex, st, (1.0, 0.0))[..., :3] @ w_luma
        cy1 = env.sample_offset(tex, st, (0.0, 1.0))[..., :3] @ w_luma
        nx = -(cx1 - luma) * 6.0
        ny = -(cy1 - luma) * 6.0
        nz = np.ones_like(nx)
        norm = np.sqrt(nx * nx + ny * ny + nz * nz)
        lam = np.clip((nx * 0.45 + ny * 0.55 + nz * 0.70) / norm, 0.0, 1.0)
        out_rgb = c0 * (0.35 + 0.95 * lam[..., None]) + np.array([0.18, 0.82, 0.68], dtype=np.float32) * ((lam ** 4)[..., None] * 0.45)

    out_rgb = np.clip(out_rgb, 0.0, 1.0)
    return np.concatenate([out_rgb, np.ones_like(luma[..., None], dtype=np.float32)], axis=-1)


register(Op(
    "doomAnaglyphRelief",
    "texture",
    [
        Input("parallax", "float", 0.018),
        Input("light_depth", "float", 0.65),
        Input("horizon", "float", 0.56),
        Input("mode", "float", 0.0),
    ],
    np=_np_doom_anaglyph_relief,
    glsl="""
  vec3 c0 = texture2D(_tex, _st).rgb;
  vec3 wl = vec3(0.2126, 0.7152, 0.0722);
  float luma = dot(c0, wl);
  float plane_prox = clamp(abs(_st.y - horizon) * 2.2, 0.0, 1.0);
  float ld = clamp(light_depth, 0.0, 1.0);
  float closeness = mix(plane_prox, luma, ld);
  float disp = (closeness - 0.45) * parallax;
  vec3 left_c = texture2D(_tex, clamp(_st + vec2(-disp, 0.0), 0.0, 1.0)).rgb;
  vec3 right_c = texture2D(_tex, clamp(_st + vec2(disp, 0.0), 0.0, 1.0)).rgb;
  if (mode < 0.5) {
    vec3 anaglyph = vec3(0.70 * left_c.r + 0.30 * left_c.g, right_c.g, right_c.b);
    return vec4(clamp(anaglyph, 0.0, 1.0), 1.0);
  }
  vec2 px = 1.0 / resolution;
  float lx1 = dot(texture2D(_tex, _st + vec2(px.x, 0.0)).rgb, wl);
  float ly1 = dot(texture2D(_tex, _st + vec2(0.0, px.y)).rgb, wl);
  vec3 n = normalize(vec3(-(lx1 - luma) * 6.0, -(ly1 - luma) * 6.0, 1.0));
  float lam = clamp(dot(n, normalize(vec3(0.45, 0.55, 0.70))), 0.0, 1.0);
  vec3 relief = c0 * (0.35 + 0.95 * lam) + vec3(0.18, 0.82, 0.68) * pow(lam, 4.0) * 0.45;
  return vec4(clamp(relief, 0.0, 1.0), 1.0);
""",
))