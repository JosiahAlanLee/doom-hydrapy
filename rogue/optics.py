# SPDX-License-Identifier: GPL-2.0-or-later
"""Argon-derived, opt-in Surveyor optics with native telemetry and exact UI bypass.

No import-time shader registration, device access, mutation or background polling.
Texture coordinates follow HydraPy: the origin is at the bottom-left edge.
"""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
import numpy as np

WARNING_TICS = 35
WARNING_PHASE = 2
MAX_ACTORS = 4096


@dataclass(frozen=True)
class TacticalUniforms:
    surveyor_tic: int = 0
    warning_ticks: int = 0
    raw: float = 1.0

    def shader_inputs(self):
        return {'surveyor_tic': self.surveyor_tic, 'raw': self.raw}


RAW = TacticalUniforms()


class TacticalOpticsDirector:
    @staticmethod
    def compute_uniforms(monsters=(), *, raw_mode=True, paused=False, dead=False, won=False):
        """Read a single native MOBS snapshot, choosing the earliest discharge.

        warning_ticks counts DOWN. The visual segment index counts UP, 1..35.
        Corpses, missiles, legacy aliases, invalid records and other phases
        cannot create a warning. No enemy proximity or wall visibility is inferred.
        """
        if any(type(v) is not bool for v in (raw_mode, paused, dead, won)):
            raise ValueError('View and lifecycle flags must be booleans')
        if raw_mode or paused or dead or won:
            return RAW
        if not isinstance(monsters, Sequence) or isinstance(monsters, (str, bytes)):
            raise ValueError('Expected a native MOBS sequence')
        if len(monsters) > MAX_ACTORS:
            raise ValueError('MOBS snapshot exceeds the optics actor budget')
        remaining = WARNING_TICS + 1
        for mob in monsters:
            if not isinstance(mob, Mapping):
                continue
            if (mob.get('argon_kind') != 'surveyor' or type(mob.get('class')) is not int
                    or mob['class'] != 11
                    or mob.get('missile') is not False
                    or type(mob.get('argon_phase')) is not int
                    or mob['argon_phase'] != WARNING_PHASE):
                continue
            health, ticks = mob.get('health'), mob.get('warning_ticks')
            if type(health) is not int or not 0 < health <= 2147483647:
                continue
            if type(ticks) is not int or not 1 <= ticks <= WARNING_TICS:
                continue
            remaining = min(remaining, ticks)
        if remaining > WARNING_TICS:
            return TacticalUniforms(raw=0.)
        return TacticalUniforms(WARNING_TICS - remaining + 1, remaining, 0.)


class NativeOpticsSampler:
    """Coherent Desktop picture/MOBS sampling, cached by native revision/frame.

    Only the render thread should call sample(). NativeGame owns its RLock.
    RAW incurs no MOBS request. A busy builder or failed telemetry read returns
    RAW, never a warning from a different engine frame. last_error is diagnostic.
    """
    def __init__(self, desktop):
        self.desktop = desktop
        self._render_key = self._render_sample = self._frame_key = None
        self._uniforms = RAW
        self.last_error = None

    def sample(self, t, *, raw_mode=True):
        if type(raw_mode) is not bool:
            raise ValueError('raw_mode must be a boolean')
        if type(t) not in (int, float) or _scalar(t) is None:
            raise ValueError('Render time must be finite')
        game = self.desktop.game
        key = (t, raw_mode, self.desktop.loading, game.paused, game.revision)
        if key == self._render_key:
            return self._render_sample
        if raw_mode or self.desktop.loading or game.paused:
            result = self.desktop.snapshot(t), RAW
        elif not game.lock.acquire(blocking=False):
            result = self.desktop.snapshot(t), RAW
        else:
            try:
                picture = self.desktop.snapshot(t)
                state = picture['state']
                inactive = (state.get('paused', True) or state.get('dead') or state.get('won')
                            or state.get('error') or state.get('gamestate') != 0)
                frame_key = (state.get('revision'), state.get('frame'))
                coherent = frame_key == (game.revision, game.frame_seq)
                if inactive or not coherent:
                    result = picture, RAW
                else:
                    if frame_key != self._frame_key:
                        self._frame_key = frame_key
                        try:
                            self._uniforms = TacticalOpticsDirector.compute_uniforms(
                                game.engine.monsters(), raw_mode=False)
                            self.last_error = None
                        except (ValueError, TypeError, OSError, RuntimeError) as error:
                            self._uniforms = RAW
                            self.last_error = str(error)[:240]
                    result = picture, self._uniforms
            finally:
                game.lock.release()
        self._render_key, self._render_sample = key, result
        return result


def _scalar(value):
    try:
        if isinstance(value, (str, bytes)) or np.ndim(value) != 0:
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def protected_pixels(st):
    """Header/warning/boss bands, bottom instruments and the native crosshair."""
    x, y = st[..., 0] * 640., (1. - st[..., 1]) * 400.
    return ((y < 88.) | (y >= 353.)
            | ((x >= 308.) & (x < 333.) & (y >= 180.) & (y < 209.)))


def numpy_optics(tex, st, surveyor_tic, raw, env):
    """HydraPy NumPy texture-op implementation; invalid uniforms select RAW."""
    original = env.sample(tex, st)
    mode = _scalar(raw)
    if mode is None or not 0. <= mode < .5:
        return original
    tic = _scalar(surveyor_tic)
    if tic is None or not 0. <= tic <= WARNING_TICS:
        return original
    tic = math.floor(tic)
    uv = np.asarray(st, dtype=np.float32)
    # Explicit edge clamp avoids wrap-around contours across opposite edges.
    half = .5 / env.res
    sample = lambda delta: env.sample(tex, np.clip(uv + delta, half, 1. - half))[..., :3]
    rgb = original[..., :3]
    weights = np.array([.2126, .7152, .0722], dtype=np.float32)
    # One native cell, independent of the Studio window's render resolution.
    gx = (sample((1. / 640., 0.)) - sample((-1. / 640., 0.))) @ weights
    gy = (sample((0., 1. / 400.)) - sample((0., -1. / 400.))) @ weights
    edge = np.clip(np.sqrt(gx * gx + gy * gy) * 3.2, 0., 1.)
    luma = rgb @ weights
    # A visible image bed retains materials; colour carries no enemy classification.
    colour = rgb * .4 + edge[..., None] * np.array([.12, .72, .50]) + luma[..., None] * np.array([.05, .15, .08])
    x, y = uv[..., 0] * 640., (1. - uv[..., 1]) * 400.
    if tic:
        position = (x - 96.) / 448. * WARNING_TICS
        index = np.floor(position)
        fraction = position - index
        segment = ((y >= 336.) & (y < 344.) & (position >= 0.) & (position < WARNING_TICS)
                   & (fraction >= .12) & (fraction < .88))
        offset = .36 - .20 * (tic - 1) / (WARNING_TICS - 1)
        radius = np.abs(uv[..., 0] - .5)
        vertical = (y >= 136.) & (y < 288.) & (np.abs(radius - offset) < .0045)
        caps = (((np.abs(y - 136.) < 2.) | (np.abs(y - 288.) < 2.))
                & (np.abs(radius - (offset - .012)) < .014))
        warning = np.array([.98, .22, .08] if tic >= 28 else [.98, .78, .16])
        colour = np.where((segment & (index >= tic))[..., None], [.10, .13, .12], colour)
        colour = np.where(((segment & (index < tic)) | vertical | caps)[..., None], warning, colour)
    out = original.copy()
    out[..., :3] = np.clip(colour, 0., 1.)
    return np.where(protected_pixels(uv)[..., None], original, out).astype(np.float32)


GLSL = r'''
vec4 original = texture2D(_tex, _st);
if (!(raw >= 0.0 && raw < 0.5) || !(surveyor_tic >= 0.0 && surveyor_tic <= 35.0)) return original;
vec2 pixel = vec2(_st.x * 640.0, (1.0 - _st.y) * 400.0);
if (pixel.y < 88.0 || pixel.y >= 353.0 ||
    (pixel.x >= 308.0 && pixel.x < 333.0 && pixel.y >= 180.0 && pixel.y < 209.0)) return original;
float tic = floor(surveyor_tic);
vec2 px = vec2(1.0 / 640.0, 1.0 / 400.0);
vec2 lo = 0.5 / resolution, hi = vec2(1.0) - lo;
vec3 weights = vec3(0.2126, 0.7152, 0.0722);
float gx = dot(texture2D(_tex, clamp(_st + vec2(px.x, 0.0), lo, hi)).rgb -
               texture2D(_tex, clamp(_st - vec2(px.x, 0.0), lo, hi)).rgb, weights);
float gy = dot(texture2D(_tex, clamp(_st + vec2(0.0, px.y), lo, hi)).rgb -
               texture2D(_tex, clamp(_st - vec2(0.0, px.y), lo, hi)).rgb, weights);
float edge = clamp(length(vec2(gx, gy)) * 3.2, 0.0, 1.0);
vec3 colour = original.rgb * 0.4 + edge * vec3(0.12, 0.72, 0.50) +
              dot(original.rgb, weights) * vec3(0.05, 0.15, 0.08);
if (tic > 0.0) {
    float position = (pixel.x - 96.0) / 448.0 * 35.0;
    float index = floor(position), fraction = fract(position);
    bool segment = pixel.y >= 336.0 && pixel.y < 344.0 && position >= 0.0 && position < 35.0 && fraction >= 0.12 && fraction < 0.88;
    float offset = 0.36 - 0.20 * (tic - 1.0) / 34.0;
    float radius = abs(_st.x - 0.5);
    bool vertical = pixel.y >= 136.0 && pixel.y < 288.0 && abs(radius - offset) < 0.0045;
    bool caps = (abs(pixel.y - 136.0) < 2.0 || abs(pixel.y - 288.0) < 2.0) && abs(radius - (offset - 0.012)) < 0.014;
    vec3 warning = tic >= 28.0 ? vec3(0.98, 0.22, 0.08) : vec3(0.98, 0.78, 0.16);
    if (segment && index >= tic) colour = vec3(0.10, 0.13, 0.12);
    if ((segment && index < tic) || vertical || caps) colour = warning;
}
return vec4(clamp(colour, 0.0, 1.0), original.a);
'''


def register_hydrapy_ops():
    """Explicit optional registration against HydraPy's actual Input/Op API."""
    from hydrapy import Input, Op, add_op
    add_op(Op('nullrunSurveyorOptics', 'texture', [
        Input('surveyor_tic', 'float', 0., scalar=True),
        Input('raw', 'float', 1., scalar=True),
    ], glsl=GLSL, np=numpy_optics,
        doc='Opt-in native Surveyor countdown; RAW is the default. No geometry displacement.'))
