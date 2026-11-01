# SPDX-License-Identifier: GPL-2.0-or-later
"""Profile loading and validation. Profiles live in ../profiles/*.json."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE_NAMES = ('drowned_records', 'switchyard_chapel', 'after_hours_pavilion', 'ashbell_foundry', 'boneglass_conservatory', 'skyhotel_service_well')
_PROFILE_SCHEMA = {
    'id': str, 'title': str, 'env_id': str, 'tempo': int, 'key': int,
    'scale': str, 'bars_per_loop': int, 'lanes': dict, 'register': dict,
    'harmony': list, 'motif': dict, 'rhythms': dict, 'transition': dict,
    'stings': dict, 'duck': dict, 'ghost_prob': int, 'notes': str,
}
VALID_KEYS = (0, 2, 5, 7)
VALID_SCALES = ('minor', 'natural_minor', 'harmonic_minor', 'phrygian', 'dorian',
                'minor_pentatonic', 'locrian', 'lydian_dominant')
_RHYTHM_KEYS = ('perc_low', 'perc_high', 'bass', 'motif_rows', 'pad_rows')
_RHYTHM_STATES = ('exploration', 'threat', 'combat', 'quiet',
                  'boss_sealed', 'boss_exposed', 'boss_one_down')
_TRANSITIONS = ('victory', 'death', 'bridge')
_STINGS = ('enemy', 'damage', 'secret', 'boss', 'victory')


def load_profile(name, profiles_dir=None):
    """Load and fully validate one profile by id."""
    if name not in PROFILE_NAMES:
        raise ValueError(f'Unknown profile {name!r}: expected one of {PROFILE_NAMES}')
    folder = Path(profiles_dir) if profiles_dir else ROOT / 'profiles'
    data = json.loads((folder / f'{name}.json').read_text())
    validate_profile(data)
    return data


def validate_profile(p):
    missing = set(_PROFILE_SCHEMA) - set(p)
    extra = set(p) - set(_PROFILE_SCHEMA)
    if missing or extra:
        raise ValueError(f'Profile fields: missing {sorted(missing)} extra {sorted(extra)}')
    if not 60 <= p['tempo'] <= 200:
        raise ValueError('tempo must be 60-200 BPM')
    if p['key'] not in VALID_KEYS:
        raise ValueError('key must be C, D, F or G minor (tracker3)')
    if p['scale'] not in VALID_SCALES:
        raise ValueError(f'scale must be one of {VALID_SCALES}')
    if not 1 <= p['bars_per_loop'] <= 8:
        raise ValueError('bars_per_loop must be 1-8 (128-row pattern limit)')
    if len(p['harmony']) != p['bars_per_loop']:
        raise ValueError('harmony must have one chord degree per bar of the loop')
    if not all(isinstance(d, int) and 0 <= d <= 6 for d in p['harmony']):
        raise ValueError('harmony degrees are 0-6')
    if not isinstance(p['lanes'].get('names'), list) or len(p['lanes']['names']) != 6 \
            or not all(isinstance(n, str) and 1 <= len(n) <= 24 for n in p['lanes']['names']):
        raise ValueError('six lane names of 1-24 characters are required')
    reg = p['register']
    for k in ('bass', 'lead', 'pad'):
        if not isinstance(reg.get(k), list) or len(reg[k]) != 2 \
                or not all(isinstance(v, int) and 0 <= v <= 127 for v in reg[k]) \
                or reg[k][0] > reg[k][1]:
            raise ValueError(f'register.{k} must be [lo, hi] within MIDI range')
    for k in ('perc_low', 'perc_high'):
        if not isinstance(reg.get(k), int) or not 0 <= reg[k] <= 127:
            raise ValueError(f'register.{k} must be a MIDI pitch')
    if len(p['motif'].get('pulses', [])) < 1 or not all(
            isinstance(pulse, list) and pulse and all(isinstance(v, int) and -12 <= v <= 12 and v != 0 for v in pulse)
            for pulse in p['motif']['pulses']):
        raise ValueError('motif.pulses: non-empty lists of nonzero steps within an octave')
    spans = p['motif'].get('spans')
    if not isinstance(spans, list) or len(spans) != 2 or not 1 <= spans[0] <= spans[1] <= 15:
        raise ValueError('motif.spans must be [lo, hi] row gaps within a bar')
    if not isinstance(p['motif'].get('density'), (int, float)) or not 0 < p['motif']['density'] <= 1:
        raise ValueError('motif.density must be 0-1')
    for state in _RHYTHM_STATES:
        rhythm = p['rhythms'].get(state)
        if not isinstance(rhythm, dict) or set(rhythm) != set(_RHYTHM_KEYS):
            raise ValueError(f'rhythms.{state} must have exactly {_RHYTHM_KEYS}')
        for key in ('perc_low', 'perc_high', 'bass'):
            s = rhythm[key]
            if not isinstance(s, str) or len(s) != 16 or any(ch not in '.xX' for ch in s):
                raise ValueError(f'rhythms.{state}.{key} must be a 16-character step string of . x X')
        for key in ('motif_rows', 'pad_rows'):
            rows = rhythm[key]
            if not isinstance(rows, list) or not all(isinstance(r, int) and 0 <= r < 16 for r in rows):
                raise ValueError(f'rhythms.{state}.{key} must be rows within the bar')
    for kind in _TRANSITIONS:
        spec = p['transition'].get(kind)
        if not isinstance(spec, dict) or not 1 <= spec.get('bars', 0) <= 8 \
                or not isinstance(spec.get('degrees'), list) or not spec['degrees']:
            raise ValueError(f'transition.{kind} needs bars 1-8 and chord degrees')
    for kind in _STINGS:
        sting = p['stings'].get(kind)
        if not isinstance(sting, dict) or not isinstance(sting.get('notes'), list) or not sting['notes'] \
                or not all(isinstance(n, int) and 0 <= n <= 127 for n in sting['notes']) \
                or not 1 <= sting.get('gate', 0) <= 16 or not 1 <= sting.get('vel', 0) <= 127:
            raise ValueError(f'stings.{kind}: notes in MIDI range, gate 1-16 rows, vel 1-127')
    duck = p['duck']
    if not isinstance(duck.get('mask'), list) or not all(isinstance(l, int) and 0 <= l <= 5 for l in duck['mask']) \
            or not isinstance(duck.get('beats'), int) or not 1 <= duck['beats'] <= 8:
        raise ValueError('duck: lane mask and 1-8 beat window')
    if not isinstance(p.get('ghost_prob'), int) or not 0 <= p['ghost_prob'] <= 100:
        raise ValueError('ghost_prob must be 0-100')
    return p


def load_profiles(profiles_dir=None):
    return {name: load_profile(name, profiles_dir) for name in PROFILE_NAMES}


PROFILES = load_profiles()
