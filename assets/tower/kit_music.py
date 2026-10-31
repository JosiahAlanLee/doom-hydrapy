# SPDX-License-Identifier: GPL-2.0-or-later
"""Adaptive music profile proposals for the existing Null Run composer.

These JSON objects match the reviewed host profile schema field-for-field so
they can be dropped into the same composer once the host's PROFILE_NAMES tuple
is extended.  Nothing is rendered, auditioned or loaded by this kit.
"""
from __future__ import annotations

import json
from pathlib import Path

import kit_common as K

VALID_KEYS = (0, 2, 5, 7)
VALID_SCALES = ('minor', 'natural_minor', 'harmonic_minor', 'phrygian', 'dorian',
                'minor_pentatonic', 'locrian', 'lydian_dominant')
RHYTHM_STATES = ('exploration', 'threat', 'combat', 'quiet',
                 'boss_sealed', 'boss_exposed', 'boss_one_down')
RHYTHM_KEYS = ('perc_low', 'perc_high', 'bass', 'motif_rows', 'pad_rows')
TRANSITIONS = ('victory', 'death', 'bridge')
STINGS = ('enemy', 'damage', 'secret', 'boss', 'victory')


# Lane names are the identity; the six roles are always the same composer lanes.
def _lanes(names):
    roles = ['low percussion', 'high percussion', 'bass', 'lead / counterline',
             'pad / drone', 'sting voice (reserved)']
    return {'names': names, 'roles': {str(i): r for i, r in enumerate(roles)}}


PROFILES = {
    'ashbell_foundry': {
        'id': 'ashbell_foundry', 'title': 'Ashbell Foundry', 'env_id': 'ashbell_foundry',
        'tempo': 88, 'key': 2, 'scale': 'phrygian', 'bars_per_loop': 8,
        'lanes': _lanes(['anvil', 'chain', 'pressure', 'bell', 'furnace', 'sting']),
        'register': {'bass': [31, 43], 'lead': [55, 74], 'pad': [43, 55],
                     'perc_low': 36, 'perc_high': 79},
        'harmony': [0, 0, 0, 3, 3, 5, 5, 0],
        'motif': {'pulses': [[1, -3, 1], [-2, 4, -1, 2], [3, -1, -4], [1, 1, -5]],
                  'spans': [3, 7], 'density': 0.32},
        'rhythms': {
            'exploration': {'perc_low': 'X.......x.......', 'perc_high': '....x.......x...',
                            'bass': 'x.......x.......', 'motif_rows': [2, 6, 10, 14], 'pad_rows': [0]},
            'threat': {'perc_low': 'X.....x.x.......', 'perc_high': '.x..x.....x..x..',
                       'bass': 'x.......x...x...', 'motif_rows': [1, 5, 9, 13], 'pad_rows': [0]},
            'combat': {'perc_low': 'X..x..X..x..X...', 'perc_high': 'x.x.x.x.x.x.x.x.',
                       'bass': 'x...x...x...x...', 'motif_rows': [0, 2, 4, 6, 8, 10, 12, 14],
                       'pad_rows': []},
            'quiet': {'perc_low': 'X...............', 'perc_high': '..x.............',
                      'bass': 'x...............', 'motif_rows': [4, 12], 'pad_rows': [0]},
            'boss_sealed': {'perc_low': 'X...x...X...x...', 'perc_high': '.x.x...x.x...x.x',
                            'bass': 'x...x...x...x...', 'motif_rows': [1, 5, 9, 13], 'pad_rows': [0]},
            'boss_exposed': {'perc_low': 'X.x.X.x.X.x.X.x.', 'perc_high': 'x.x.x.x.x.x.x.x.',
                             'bass': 'x.x.x.x.x.x.x.x.',
                             'motif_rows': [0, 2, 4, 6, 8, 10, 12, 14], 'pad_rows': []},
            'boss_one_down': {'perc_low': 'X...x..........x', 'perc_high': '.x......x.......',
                              'bass': 'x.....x.....x...', 'motif_rows': [3, 11], 'pad_rows': [0]},
        },
        'transition': {
            'victory': {'bars': 4, 'degrees': [0, 3, 5, 7], 'contour': 'rise'},
            'death': {'bars': 4, 'degrees': [5, 3, 1, 0], 'contour': 'sink'},
            'bridge': {'bars': 2, 'degrees': [0, 3], 'contour': 'knock'},
        },
        'stings': {
            'enemy': {'notes': [59, 61], 'gate': 2, 'vel': 108},
            'damage': {'notes': [36], 'gate': 3, 'vel': 118},
            'secret': {'notes': [74, 82], 'gate': 1, 'vel': 90},
            'boss': {'notes': [47, 50, 53], 'gate': 4, 'vel': 112},
            'victory': {'notes': [48, 55, 60], 'gate': 5, 'vel': 110},
        },
        'duck': {'mask': [2, 3, 4], 'beats': 2}, 'ghost_prob': 12,
        'notes': ('Proposal, not rendered or auditioned. Heavy 88 BPM foundry phrygian: '
                  'anvil/chain low percussion, slow pressure bass, a bronze bell lead and '
                  'furnace drone. Combat doubles the anvil without raising volume; boss '
                  'states open the chain layer. 8-bar loops; 2-4 bar transitions; 1-5 row stings.'),
    },
    'boneglass_conservatory': {
        'id': 'boneglass_conservatory', 'title': 'Boneglass Conservatory',
        'env_id': 'boneglass_conservatory',
        'tempo': 66, 'key': 0, 'scale': 'locrian', 'bars_per_loop': 8,
        'lanes': _lanes(['breath', 'drip', 'sub', 'glass', 'root', 'sting']),
        'register': {'bass': [28, 40], 'lead': [60, 84], 'pad': [40, 52],
                     'perc_low': 33, 'perc_high': 86},
        'harmony': [0, 1, 1, 0, 5, 4, 4, 0],
        'motif': {'pulses': [[2, -1, -2], [1, -3, 2], [-4, 1, 2], [-1, 2, -5]],
                  'spans': [5, 11], 'density': 0.22},
        'rhythms': {
            'exploration': {'perc_low': 'X...............', 'perc_high': '......x.........',
                            'bass': 'x.......x.......', 'motif_rows': [4, 12], 'pad_rows': [0]},
            'threat': {'perc_low': 'X.......x.......', 'perc_high': '...x......x.....',
                       'bass': 'x.......x...x...', 'motif_rows': [2, 7, 12], 'pad_rows': [0]},
            'combat': {'perc_low': 'X....x..X.......', 'perc_high': '..x...x...x...x.',
                       'bass': 'x...x...x...x...', 'motif_rows': [0, 4, 8, 12], 'pad_rows': []},
            'quiet': {'perc_low': 'X...............', 'perc_high': '................',
                      'bass': 'x...............', 'motif_rows': [6, 14], 'pad_rows': [0]},
            'boss_sealed': {'perc_low': 'X.......x.......', 'perc_high': '....x.....x.....',
                            'bass': 'x.....x.....x...', 'motif_rows': [1, 5, 9, 13], 'pad_rows': [0]},
            'boss_exposed': {'perc_low': 'X...x...X...x...', 'perc_high': '.x...x...x...x..',
                             'bass': 'x..x..x..x..x...', 'motif_rows': [0, 3, 6, 9, 12, 15],
                             'pad_rows': []},
            'boss_one_down': {'perc_low': 'X...............', 'perc_high': '......x.........',
                              'bass': 'x.......x.......', 'motif_rows': [8], 'pad_rows': [0]},
        },
        'transition': {
            'victory': {'bars': 4, 'degrees': [0, 4, 5, 6], 'contour': 'thin-rise'},
            'death': {'bars': 4, 'degrees': [1, 0, 6, 0], 'contour': 'breathe-out'},
            'bridge': {'bars': 3, 'degrees': [0, 1], 'contour': 'still'},
        },
        'stings': {
            'enemy': {'notes': [72, 75], 'gate': 3, 'vel': 84},
            'damage': {'notes': [28], 'gate': 4, 'vel': 104},
            'secret': {'notes': [84, 88], 'gate': 2, 'vel': 78},
            'boss': {'notes': [36, 39, 42], 'gate': 5, 'vel': 98},
            'victory': {'notes': [60, 64, 67], 'gate': 6, 'vel': 88},
        },
        'duck': {'mask': [0, 1, 3], 'beats': 2}, 'ghost_prob': 26,
        'notes': ('Proposal, not rendered or auditioned. Very creepy 66 BPM locrian: '
                  'breath and drip percussion, a low sub pressure, high glass harmonics and '
                  'a root drone. Threat is a change of interval and density, not volume; '
                  'combat stays sparse. 8-bar loops; 3-4 bar transitions; long rests are '
                  'intentional. No jump-scare sting.'),
    },
    'skyhotel_service_well': {
        'id': 'skyhotel_service_well', 'title': 'Skyhotel Service Well',
        'env_id': 'skyhotel_service_well',
        'tempo': 100, 'key': 7, 'scale': 'dorian', 'bars_per_loop': 8,
        'lanes': _lanes(['rain', 'bell', 'bass', 'lift', 'pad', 'sting']),
        'register': {'bass': [33, 45], 'lead': [58, 76], 'pad': [45, 57],
                     'perc_low': 38, 'perc_high': 82},
        'harmony': [0, 0, 5, 5, 3, 3, 4, 4],
        'motif': {'pulses': [[1, -2, 3], [-3, 1, -1], [2, 2, -4], [-1, 4, -2]],
                  'spans': [2, 6], 'density': 0.38},
        'rhythms': {
            'exploration': {'perc_low': 'X.......x.......', 'perc_high': '..x...x...x...x.',
                            'bass': 'x.......x.......', 'motif_rows': [2, 6, 10, 14], 'pad_rows': [0]},
            'threat': {'perc_low': 'X...x...x.......', 'perc_high': '.x..x...x..x..x.',
                       'bass': 'x.......x...x...', 'motif_rows': [1, 5, 9, 13], 'pad_rows': [0]},
            'combat': {'perc_low': 'X..x.X..x.X..x..', 'perc_high': 'x.x.x.x.x.x.x.x.',
                       'bass': 'x..x..x..x..x...', 'motif_rows': [0, 2, 4, 6, 8, 10, 12, 14],
                       'pad_rows': []},
            'quiet': {'perc_low': 'X...............', 'perc_high': '......x.........',
                      'bass': 'x.......x.......', 'motif_rows': [4, 12], 'pad_rows': [0]},
            'boss_sealed': {'perc_low': 'X...x...X...x...', 'perc_high': '.x.x...x.x...x.x',
                            'bass': 'x...x...x...x...', 'motif_rows': [1, 5, 9, 13], 'pad_rows': [0]},
            'boss_exposed': {'perc_low': 'X.x.X.x.X.x.X.x.', 'perc_high': 'x.x.x.x.x.x.x.x.',
                             'bass': 'x.x.x.x.x.x.x.x.',
                             'motif_rows': [0, 2, 4, 6, 8, 10, 12, 14], 'pad_rows': []},
            'boss_one_down': {'perc_low': 'X...x..........x', 'perc_high': '.x......x.......',
                              'bass': 'x.....x.....x...', 'motif_rows': [3, 11], 'pad_rows': [0]},
        },
        'transition': {
            'victory': {'bars': 4, 'degrees': [0, 4, 5, 7], 'contour': 'lift-rise'},
            'death': {'bars': 4, 'degrees': [5, 3, 2, 0], 'contour': 'floor-sink'},
            'bridge': {'bars': 2, 'degrees': [0, 5], 'contour': 'rain-tick'},
        },
        'stings': {
            'enemy': {'notes': [62, 65], 'gate': 2, 'vel': 96},
            'damage': {'notes': [38], 'gate': 3, 'vel': 110},
            'secret': {'notes': [74, 81], 'gate': 2, 'vel': 86},
            'boss': {'notes': [50, 53, 57], 'gate': 4, 'vel': 106},
            'victory': {'notes': [55, 62, 67], 'gate': 5, 'vel': 102},
        },
        'duck': {'mask': [2, 3, 4], 'beats': 2}, 'ghost_prob': 18,
        'notes': ('Proposal, not rendered or auditioned. 100 BPM rainy dorian service hotel: '
                  'rain ticks and lift-bell high percussion, a walking bass, muted brass lead '
                  'and a low room drone. Threat raises the lift-bell pattern; combat keeps '
                  'the tempo but removes the pad. 8-bar loops; 2-4 bar transitions; one-bar '
                  'call-bell stings. Dirty amber, not bright.'),
    },
}


def validate_profile(p):
    """Mirror of nullrun_music/profiles.py validate_profile, without the host name list."""
    missing = {'id', 'title', 'env_id', 'tempo', 'key', 'scale', 'bars_per_loop', 'lanes',
               'register', 'harmony', 'motif', 'rhythms', 'transition', 'stings', 'duck',
               'ghost_prob', 'notes'} - set(p)
    if missing:
        raise ValueError(f'missing {sorted(missing)}')
    if not 60 <= p['tempo'] <= 200:
        raise ValueError('tempo')
    if p['key'] not in VALID_KEYS:
        raise ValueError('key')
    if p['scale'] not in VALID_SCALES:
        raise ValueError('scale')
    if not 1 <= p['bars_per_loop'] <= 8:
        raise ValueError('bars')
    if len(p['harmony']) != p['bars_per_loop'] or not all(0 <= d <= 6 for d in p['harmony']):
        raise ValueError('harmony')
    if len(p['lanes']['names']) != 6 or not all(1 <= len(n) <= 24 for n in p['lanes']['names']):
        raise ValueError('lanes')
    reg = p['register']
    for k in ('bass', 'lead', 'pad'):
        if len(reg[k]) != 2 or not all(0 <= v <= 127 for v in reg[k]) or reg[k][0] > reg[k][1]:
            raise ValueError(k)
    for k in ('perc_low', 'perc_high'):
        if not 0 <= reg[k] <= 127:
            raise ValueError(k)
    if not p['motif']['pulses'] or not all(
            pulse and all(-12 <= v <= 12 and v != 0 for v in pulse)
            for pulse in p['motif']['pulses']):
        raise ValueError('motif.pulses')
    if len(p['motif']['spans']) != 2 or not 1 <= p['motif']['spans'][0] <= p['motif']['spans'][1] <= 15:
        raise ValueError('motif.spans')
    if not 0 < p['motif']['density'] <= 1:
        raise ValueError('motif.density')
    for state in RHYTHM_STATES:
        r = p['rhythms'].get(state)
        if not isinstance(r, dict) or set(r) != set(RHYTHM_KEYS):
            raise ValueError(state)
        for key in ('perc_low', 'perc_high', 'bass'):
            if not isinstance(r[key], str) or len(r[key]) != 16 or any(ch not in '.xX' for ch in r[key]):
                raise ValueError(f'{state}.{key}')
        for key in ('motif_rows', 'pad_rows'):
            if not all(isinstance(x, int) and 0 <= x < 16 for x in r[key]):
                raise ValueError(f'{state}.{key}')
    for kind in TRANSITIONS:
        spec = p['transition'].get(kind)
        if not isinstance(spec, dict) or not 1 <= spec.get('bars', 0) <= 8 or not spec.get('degrees'):
            raise ValueError(kind)
    for kind in STINGS:
        s = p['stings'].get(kind)
        if not isinstance(s, dict) or not s.get('notes') or not all(0 <= n <= 127 for n in s['notes']):
            raise ValueError(kind)
        if not 1 <= s.get('gate', 0) <= 16 or not 1 <= s.get('vel', 0) <= 127:
            raise ValueError(kind)
    d = p['duck']
    if not d.get('mask') or not all(0 <= x <= 5 for x in d['mask']) or not 1 <= d.get('beats', 0) <= 8:
        raise ValueError('duck')
    if not 0 <= p['ghost_prob'] <= 100:
        raise ValueError('ghost_prob')
    return True


def write_profiles(out_root):
    out_root = Path(out_root)
    folder = out_root / 'music_profiles'
    folder.mkdir(parents=True, exist_ok=True)
    index = {
        'format': 'nullrun-music-profile-proposals-1',
        'license': K.LICENSE,
        'status': 'PROPOSAL ONLY: written profiles, not rendered, not auditioned, not loaded',
        'host_schema': ('mirrors nullrun_music/profiles.py validate_profile; host PROFILE_NAMES '
                        'currently lists only the three reviewed sets, so Codex must add these '
                        'env IDs before the existing composer can load them'),
        'profiles': [],
    }
    for pid, profile in PROFILES.items():
        validate_profile(profile)
        path = folder / f'{pid}.json'
        path.write_text(json.dumps(profile, indent=2, ensure_ascii=True) + '\n')
        index['profiles'].append({
            'id': pid, 'path': f'music_profiles/{pid}.json',
            'tempo': profile['tempo'], 'key': profile['key'], 'scale': profile['scale'],
            'bars_per_loop': profile['bars_per_loop'],
            'status': 'proposal; not rendered or auditioned',
            'host_change_required': 'add env ID to PROFILE_NAMES in nullrun_music/profiles.py',
        })
    (out_root / 'music_proposals.json').write_text(json.dumps(index, indent=2) + '\n')
    return index
