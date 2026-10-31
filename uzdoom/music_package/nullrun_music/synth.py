# SPDX-License-Identifier: GPL-2.0-or-later
"""Offline reference synthesizer (CPU, numpy).

A small proof renderer only -- NOT a claim of the final Rack patch. Six
monophonic lanes with per-lane phase carry (no clicks at note boundaries),
per-note envelopes, ducking from the canonical control events, conservative
master gain, DC removal and a clip report. 48 kHz stereo PCM16 WAV.

Ticks map to seconds through the tempo map: each section control event carries
its profile, so floor/profile switches change the tick rate correctly.
"""
import json
import math
import struct
import wave

import numpy as np

from .events import TICKS

SAMPLE_RATE = 48000
MASTER = 0.9

VOICE_GAIN = [0.34, 0.22, 0.5, 0.42, 0.3, 0.5]   # kick, hat, bass, lead, pad, sting
PAN = [0.0, -0.18, 0.0, 0.24, -0.14, 0.1]        # -1..1 left..right


def tempo_map(controls, profiles, default_profile, end_tick):
    """[(tick, bpm)] so seconds(t) integrates dtick / TICKS * 60 / bpm."""
    segments = [(0, profiles[default_profile]['tempo'])]
    for control in controls:
        if control.kind in ('section', 'transition'):
            env = control.payload.get('env') or default_profile
            if env in profiles and profiles[env]['tempo'] != segments[-1][1]:
                segments.append((control.tick, profiles[env]['tempo']))
    segments.append((end_tick, segments[-1][1]))
    return segments


def ticks_to_seconds(segments, tick):
    t = 0.0
    for (t0, bpm), (t1, _) in zip(segments, segments[1:]):
        if tick <= t0:
            break
        t += (min(tick, t1) - t0) / TICKS * 60.0 / bpm
        if tick <= t1:
            break
    return t


def _envelope(n, attack, release):
    env = np.ones(n)
    a = max(1, int(attack * SAMPLE_RATE))
    r = max(1, int(release * SAMPLE_RATE))
    a, r = min(a, n), min(r, n)
    env[:a] = np.linspace(0, 1, a)
    if r:
        env[-r:] *= np.linspace(1, 0, r)
    return env


def _osc(phase0, freq, n, harmonics, vibrato=0.0):
    t = np.arange(n) / SAMPLE_RATE
    f = freq * (1 + vibrato * np.sin(2 * np.pi * 5.2 * t)) if vibrato else freq
    phase = phase0 + 2 * np.pi * np.cumsum(f) / SAMPLE_RATE
    out = np.zeros(n)
    for k, weight in harmonics:
        out += weight * np.sin(k * phase)
    total = np.asarray(f).sum() if hasattr(f, 'sum') else f * n
    return out, (phase0 + 2 * np.pi * total / SAMPLE_RATE) % (2 * np.pi)


def _midi_hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def render_schedule(schedule, profiles, duration_seconds=None, out_path=None):
    """Render the canonical schedule to a stereo float buffer in [-1, 1)."""
    segments = tempo_map(schedule.controls, profiles, schedule.profile,
                         schedule.meta['end_tick'])
    end_seconds = (duration_seconds if duration_seconds is not None
                   else ticks_to_seconds(segments, schedule.meta['end_tick']))
    n_total = int(end_seconds * SAMPLE_RATE)
    left = np.zeros(n_total)
    right = np.zeros(n_total)
    phase = [0.0] * 6
    notes = list(schedule.notes)
    # Duck windows: (start_tick, until_tick, mask)
    ducks = []
    for control in schedule.controls:
        if control.kind == 'duck_on':
            ducks.append([control.tick, control.payload['until'], control.payload['mask']])
        elif control.kind == 'duck_off':
            for d in ducks:
                if d[1] == control.tick:
                    d[1] = control.tick
    for note in notes:
        if note.vel <= 0:
            continue
        start_s = ticks_to_seconds(segments, note.tick)
        end_s = ticks_to_seconds(segments, note.tick + note.gate)
        if start_s >= end_seconds:
            continue
        end_s = min(end_s, end_seconds)
        n = max(1, int((end_s - start_s) * SAMPLE_RATE))
        vel = note.vel / 127.0
        for tick0, until, mask in ducks:
            if tick0 <= note.tick < until and note.lane in mask:
                vel *= 0.45
                break
        gain = VOICE_GAIN[note.lane] * vel
        i0 = int(start_s * SAMPLE_RATE)
        if i0 >= n_total:
            continue
        n = min(n, n_total - i0)
        if n < 1:
            continue
        hz = _midi_hz(note.midi)
        lane = note.lane
        if lane == 0:       # low percussion: pitch-swept sine
            f = np.linspace(hz * 2.1, hz * 0.55, n)
            ph = phase[lane] + 2 * np.pi * np.cumsum(f) / SAMPLE_RATE
            buf = np.sin(ph)
            phase[lane] = ph[-1] % (2 * np.pi) if n else phase[lane]
            buf *= _envelope(n, 0.004, 0.12) * np.exp(-np.arange(n) / SAMPLE_RATE * 14)
        elif lane == 1:     # high percussion: brittle noise tick (smoothed so
            # the tick is bright, not a raw click train)
            rng = np.random.RandomState(1103515245 + note.midi * 131 + note.tick % 99991)
            buf = rng.uniform(-1, 1, n + 8)
            for _ in range(2):               # two one-poles bound the derivative
                acc = 0.0
                for i in range(len(buf)):
                    acc += 0.14 * (buf[i] - acc)
                    buf[i] = acc
            buf = np.diff(buf, prepend=0.0)[:n]  # highpass: brittle
            buf *= _envelope(n, 0.002, 0.05) * np.exp(-np.arange(n) / SAMPLE_RATE * 26)
        elif lane == 2:     # bass: soft saw stack
            buf, phase[lane] = _osc(phase[lane], hz, n, [(k, 1 / k) for k in range(1, 7)])
            buf *= _envelope(n, 0.006, 0.05)
        elif lane == 3:     # lead: reedy odd harmonics + vibrato
            buf, phase[lane] = _osc(phase[lane], hz, n, [(1, 1.0), (3, 0.45), (5, 0.18)],
                                    vibrato=0.004)
            buf *= _envelope(n, 0.012, 0.06)
        elif lane == 4:     # pad: detuned pair
            a, ph = _osc(phase[lane], hz * 0.9965, n, [(1, 1.0)])
            b, _ = _osc(phase[lane], hz * 1.0035, n, [(1, 1.0)])
            phase[lane] = ph
            buf = (a + b) * 0.5 * _envelope(n, 0.05, 0.1)
        else:               # sting: FM bell-ish stab
            t = np.arange(n) / SAMPLE_RATE
            mod = np.sin(2 * np.pi * hz * 2.01 * t + phase[lane])
            buf = np.sin(2 * np.pi * hz * t + 2.2 * mod)
            phase[lane] = (phase[lane] + 2 * np.pi * hz * 2.01 * n / SAMPLE_RATE) % (2 * np.pi)
            buf *= _envelope(n, 0.002, 0.09)
        buf *= gain
        pan = PAN[lane]
        l_gain = min(1.0, 1.0 - max(0, pan))
        r_gain = min(1.0, 1.0 + min(0, pan))
        if pan >= 0:
            left[i0:i0 + n] += buf * (1 - pan)
            right[i0:i0 + n] += buf
        else:
            left[i0:i0 + n] += buf
            right[i0:i0 + n] += buf * (1 + pan)
        del l_gain, r_gain
    # Mixdown: DC block, normalize under MASTER, hard clip guard.
    left, right = _dc_block(left), _dc_block(right)
    peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))), 1e-12)
    if peak > MASTER:
        left, right = left * (MASTER / peak), right * (MASTER / peak)
    left, right = np.clip(left, -0.999, 0.999), np.clip(right, -0.999, 0.999)
    clipped = int(np.sum(np.abs(left) > 0.999) + np.sum(np.abs(right) > 0.999))
    stats = {'sample_rate': SAMPLE_RATE, 'duration_seconds': round(end_seconds, 3),
             'channels': 2, 'bit_depth': 16, 'peak': round(peak, 5),
             'peak_after_master': round(max(float(np.max(np.abs(left))), float(np.max(np.abs(right)))), 5),
             'rms_left': round(float(np.sqrt(np.mean(left ** 2))), 6),
             'rms_right': round(float(np.sqrt(np.mean(right ** 2))), 6),
             'dc_left': round(float(np.mean(left)), 8),
             'dc_right': round(float(np.mean(right)), 8),
             'clipped_samples': clipped,
             'nonfinite_samples': int(np.sum(~np.isfinite(left)) + np.sum(~np.isfinite(right))),
             'notes_rendered': len(notes)}
    if out_path:
        write_wav(out_path, left, right)
    return left, right, stats


def _dc_block(x):
    """First-order DC blocker (y[n] = x[n]-x[n-1] + 0.995 y[n-1])."""
    y = np.empty_like(x)
    prev_x = 0.0
    prev_y = 0.0
    for n in range(len(x)):
        y[n] = x[n] - prev_x + 0.995 * prev_y
        prev_x, prev_y = x[n], y[n]
    return y


def write_wav(path, left, right):
    data = np.empty(len(left) * 2, dtype='<i2')
    data[0::2] = np.clip(left * 32767, -32768, 32767).astype('<i2')
    data[1::2] = np.clip(right * 32767, -32768, 32767).astype('<i2')
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(data.tobytes())


def markers(schedule, profiles, segments):
    """Cue/sting/section markers with second offsets, for the integrator."""
    out = []
    for control in schedule.controls:
        if control.kind in ('section', 'transition', 'suspend', 'resume', 'silence'):
            out.append({'t': control.tick,
                        's': round(ticks_to_seconds(segments, control.tick), 3),
                        'kind': control.kind,
                        'state': control.payload.get('state') or control.payload.get('kind')})
        elif control.kind == 'sting':
            out.append({'t': control.tick,
                        's': round(ticks_to_seconds(segments, control.tick), 3),
                        'kind': 'sting', 'state': control.payload.get('sting')})
    out.sort(key=lambda m: m['t'])
    return out
