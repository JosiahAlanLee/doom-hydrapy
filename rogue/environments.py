# SPDX-License-Identifier: GPL-2.0-or-later
"""Seeded environment art; map topology and native encounter rules stay intact."""
from functools import lru_cache
from pathlib import Path
import json

from PIL import Image

ROOT = Path(__file__).resolve().parents[1] / 'assets/environments'
PACK_IDS = ('drowned_records', 'switchyard_chapel', 'after_hours_pavilion')
PROP_ROLES = ('service_lamp', 'cable_shrine', 'directory_sign')
MOB_ROLES = ('latchwing', 'relay_choir')


@lru_cache(maxsize=1)
def catalogue():
    data = json.loads((ROOT / 'environments.json').read_text())
    if data.get('format') != 'nullrun-environment-kit-1':
        raise ValueError('Unsupported environment kit')
    entries = data.get('sets', [])
    if len(entries) != len(PACK_IDS) or {p['id'] for p in entries} != set(PACK_IDS):
        raise ValueError('Environment kit must contain the three reviewed sets')
    return {p['id']: p for p in entries}


def select(seed):
    if type(seed) is not int or not 0 <= seed <= 0xffffffff:
        raise ValueError('seed must be an unsigned 32-bit integer')
    return PACK_IDS[seed % len(PACK_IDS)]


def describe(pack):
    entry = catalogue()[pack]
    return {'id': pack, 'name': entry['name'], 'description': entry['description'],
            'landmark': entry['landmark']['name'], 'selection': 'seed % 3',
            'mobs': {role: encounters()[pack][role]['name'] for role in MOB_ROLES},
            'music': music()[pack],
            'art_source': 'DeepSeek procedural environment kit; Codex runtime adapter'}


@lru_cache(maxsize=1)
def encounters():
    data = json.loads((ROOT / 'encounters.json').read_text())
    if data.get('format') != 'nullrun-environment-mobs-1' or set(data.get('sets', {})) != set(PACK_IDS):
        raise ValueError('Unsupported environment mob kit')
    return data['sets']


@lru_cache(maxsize=1)
def music():
    data = json.loads((ROOT / 'music/catalogue.json').read_text())
    if data.get('format') != 'nullrun-environment-score-catalogue-1' or set(data.get('sets', {})) != set(PACK_IDS):
        raise ValueError('Unsupported environment score catalogue')
    return data['sets']


@lru_cache(maxsize=12)
def _mob_atlas(pack, role, variant):
    if pack not in PACK_IDS or role not in MOB_ROLES or variant not in ('A', 'B'):
        raise ValueError('Unknown environment mob')
    with Image.open(ROOT / 'mobs' / pack / (role + '_' + variant + '.png')) as image:
        if image.size != (512, 768) or image.mode != 'RGBA':
            raise ValueError('Environment mob atlas must be 512x768 RGBA')
        return image.copy()


def draw_mob(pack, role, seed, frame):
    variant = 'AB'[(int(seed) + MOB_ROLES.index(role)) & 1]
    atlas = _mob_atlas(pack, role, variant)
    frame = min(max(int(frame), 0), 23)
    x, y = frame % 4 * 128, frame // 4 * 128
    return atlas.crop((x, y, x + 128, y + 128))


def present_state(state, pack):
    """Keep native class/count fields and give warning text its current identity."""
    result = dict(state)
    argon = dict(state.get('argon') or {})
    cue = argon.get('cue')
    if cue:
        for role in MOB_ROLES:
            old_name = role.replace('_', ' ').upper()
            if cue.startswith(old_name + ' / '):
                argon['cue'] = encounters()[pack][role]['name'] + cue[len(old_name):]
                break
    result['argon'] = argon
    return result


@lru_cache(maxsize=64)
def _picture(pack, group, name):
    if pack not in PACK_IDS or group not in ('walls', 'flats', 'props'):
        raise ValueError('Unknown environment art')
    if group == 'props':
        if name not in PROP_ROLES:
            raise ValueError('Unknown prop role')
        size, mode = (96, 128), 'RGBA'
    else:
        if type(name) is not int or not 1 <= name <= (8 if group == 'walls' else 4):
            raise ValueError('Unknown environment tile')
        size, mode = ((128, 128) if group == 'walls' else (64, 64)), 'RGB'
        name = f'{name:02}'
    with Image.open(ROOT / 'art' / pack / group / (name + '.png')) as image:
        if image.size != size or image.mode != mode:
            raise ValueError('Unexpected environment art dimensions or mode')
        return image.copy()


def picture(pack, group, name):
    return _picture(pack, group, name).copy()


def _feature_cells(floor):
    """Choose existing wall faces; this never adds sectors or solid things."""
    solid = {tuple(p) for p in floor.architecture.get('landmark', {}).get('cells', [])}
    if solid:
        return sorted(p for p in floor.cells if any(
            (p[0] + dx, p[1] + dy) in solid for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))))
    rooms = sorted(floor.rooms, key=lambda b: (-b[2] * b[3], tuple(b)))
    for x, y, width, height in rooms:
        inside = {p for p in floor.cells if x <= p[0] < x + width and y <= p[1] < y + height
                  and not floor.profiles.get(p, {}).get('tag')
                  and not floor.profiles.get(p, {}).get('special')
                  and p not in (floor.start, floor.exit)}
        for p in sorted(inside):
            for dx, dy in ((1, 0), (0, 1)):
                q = p[0] + dx, p[1] + dy
                if q not in inside:
                    continue
                for nx, ny in ((-dy, dx), (dy, -dx)):
                    if (p[0] + nx, p[1] + ny) not in floor.cells and (q[0] + nx, q[1] + ny) not in floor.cells:
                        return [p, q]
    return []


def apply(floors, seed):
    pack = select(seed)
    entry = catalogue()[pack]
    for floor in floors:
        # Rotate the first three structural materials; utility/accent roles keep
        # their meanings. The chosen world and its prop silhouettes persist.
        turn = ((seed >> 8) + floor.number - 1) % 3 if floor.number > 1 else 0
        walls = {f'NWALL{i:02}': f'EWALL{1 + (i - 1 + turn) % 3 if i <= 3 else i:02}'
                 for i in range(1, 7)}
        flats = {f'NFLAT{i:02}': f'EFLAT{i:02}' for i in range(1, 5)}
        name, wall, flat, ceiling, light = floor.theme
        floor.theme = (f"{entry['name']} / {floor.number:02}", walls.get(wall, wall),
                       flats.get(flat, flat), flats.get(ceiling, ceiling), light)
        for profile in floor.profiles.values():
            for field, mapping in (('wall', walls), ('flat', flats), ('ceiling', flats)):
                if profile.get(field) in mapping:
                    profile[field] = mapping[profile[field]]
        feature = _feature_cells(floor)
        for i, cell in enumerate(feature):
            floor.profiles[cell]['wall'] = f'EWALL{7 + i % 2:02}'
        floor.architecture['environment'] = dict(describe(pack), feature_cells=[list(p) for p in feature],
                                                 material_rotation=turn, original_floor_name=name)
        for prop in floor.architecture.get('props', []):
            role = prop['name']
            if role in PROP_ROLES:
                prop['display_name'] = entry['props'][role]['display_name']
                prop['environment'] = pack
    return pack
