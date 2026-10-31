# SPDX-License-Identifier: GPL-2.0-or-later
"""Cues, note and control events, receipts and the canonical JSONL schedule.

Timebase: integer musical ticks, 1920 per quarter note -- the same grid as
hydrapy-tracker-3, so exported scores and the canonical schedule share one clock.
Gameplay 35 Hz and display 60 Hz are never tempo sources; the host stamps cues
with ticks read from the tracker transport (documented in INTEGRATION.md).
"""
from __future__ import annotations

import json

TICKS = 1920          # per quarter note (matches hydrapy.tracker_v3.TICKS)
ROW = TICKS // 4      # one 16th-note base row (480)
EIGHTH = ROW // 2     # 1/8 note: the sting quantization bound (240)
BAR = TICKS * 4       # one 4/4 bar (7680)
MAX_TICK = 1 << 48    # ticks beyond this are rejected as implausible
MAX_SCHEDULE = 1 << 20  # hard bound on realized events in one schedule

CUE_TYPES = frozenset({
    'enemy_first_seen', 'enemy_sting', 'combat_start', 'combat_end',
    'damage_burst', 'secret', 'boss_encounter', 'boss_sealed', 'boss_exposed',
    'boss_bound', 'tier_victory', 'floor_change', 'pause', 'resume',
    'player_death', 'run_victory', 'new_seed', 'focus_lost',
})

# Required and optional payload keys per cue type. 'required' keys must be present
# with the stated type; anything else is rejected (no silent extension).
CUE_SPEC = {
    'enemy_first_seen': {'req': {'enemy': str}},
    'enemy_sting': {'req': {'enemy': str}},
    'combat_start': {'req': {}},
    'combat_end': {'req': {}},
    'damage_burst': {'req': {'amount': int}, 'opt': {'source': str}},
    'secret': {'req': {'secret': str}},
    'boss_encounter': {'req': {'names': list, 'tier': int}},
    'boss_sealed': {'req': {'name': str}},
    'boss_exposed': {'req': {'name': str}},
    'boss_bound': {'req': {'name': str}},
    'tier_victory': {'req': {'tier': int}},
    'floor_change': {'req': {'floor': int}, 'opt': {'env': str}},
    'pause': {'req': {}},
    'resume': {'req': {}},
    'player_death': {'req': {}},
    'run_victory': {'req': {}},
    'new_seed': {'req': {'seed': int}},
    'focus_lost': {'req': {}},
}


def _typecheck(value, kind):
    if kind is str:
        return isinstance(value, str) and 0 < len(value) <= 64
    if kind is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if kind is list:
        return isinstance(value, list) and 0 < len(value) <= 8 and all(isinstance(v, str) and 0 < len(v) <= 40 for v in value)
    raise AssertionError(kind)


class Cue:
    """One host-supplied request. Immutable, stable id required (stable event IDs)."""
    __slots__ = ('id', 'tick', 'type', 'payload', 'source', 'confirm')

    def __init__(self, id, tick, type, payload=None, source='host', confirm=None):
        self.id, self.tick, self.type, self.payload = id, tick, type, payload or {}
        self.source = source
        self.confirm = confirm  # optional game-state confirmation snapshot (see snapshot_rules)

    @classmethod
    def from_json(cls, data):
        try:
            if not isinstance(data, dict):
                raise ValueError('Cue must be an object')
            id = data['id']
            if not isinstance(id, str) or not 1 <= len(id) <= 64:
                raise ValueError('id: 1-64 character string (stable event IDs required)')
            tick = data['t']
            if isinstance(tick, bool) or not isinstance(tick, int) or not 0 <= tick <= MAX_TICK:
                raise ValueError('t: integer ticks 0 to 2^48')
            cue_type = data['type']
            if cue_type not in CUE_TYPES:
                raise ValueError(f'type: one of {sorted(CUE_TYPES)}')
            payload = data.get('payload') or {}
            if not isinstance(payload, dict):
                raise ValueError('payload must be an object')
            spec = CUE_SPEC[cue_type]
            for key, kind in spec['req'].items():
                if key not in payload or not _typecheck(payload[key], kind):
                    raise ValueError(f'{cue_type} payload requires {key}')
            allowed = set(spec['req']) | set(spec.get('opt', {}))
            for key, value in payload.items():
                if key not in allowed:
                    raise ValueError(f'{cue_type} payload does not take {key}')
                if key in spec.get('opt', {}) and not _typecheck(value, spec['opt'][key]):
                    raise ValueError(f'{cue_type} payload {key} has the wrong type')
            if cue_type == 'boss_encounter' and len(set(payload['names'])) != len(payload['names']):
                raise ValueError('boss_encounter names must be distinct (two demons per tier)')
            if cue_type == 'new_seed' and not 0 <= payload['seed'] <= 0xFFFFFFFF:
                raise ValueError('seed must be 0..2^32-1')
            source = data.get('source', 'host')
            confirm = data.get('confirm')
            if confirm is not None and not isinstance(confirm, dict):
                raise ValueError('confirm must be a snapshot object or absent')
            return cls(id, tick, cue_type, payload, source, confirm)
        except KeyError as e:
            raise ValueError(f'cue missing field {e}') from None
        except (TypeError, ValueError) as e:
            raise ValueError(f'{data.get("type", "cue")} rejected: {e}') from None

    def key(self):
        """Identity for dedup/cooldown: type plus the payload's distinguishing field."""
        if self.type == 'enemy_sting':
            return ('enemy_sting', self.payload.get('enemy'))
        if self.type == 'damage_burst':
            return ('damage_burst',)
        if self.type == 'secret':
            return ('secret', self.payload.get('secret'))
        if self.type == 'boss_bound':
            return ('boss_bound', self.payload.get('name'))
        if self.type == 'boss_exposed':
            return ('boss_exposed', self.payload.get('name'))
        if self.type == 'boss_sealed':
            return ('boss_sealed', self.payload.get('name'))
        if self.type == 'enemy_first_seen':
            return ('enemy_first_seen', self.payload.get('enemy'))
        return (self.type,)

    def to_json(self):
        out = {'id': self.id, 't': self.tick, 'type': self.type, 'payload': self.payload}
        if self.source != 'host':
            out['source'] = self.source
        if self.confirm is not None:
            out['confirm'] = self.confirm
        return out


class NoteEvent:
    """One canonical note: (lane, midi, vel, gate). Lanes are monophonic."""
    __slots__ = ('id', 'tick', 'lane', 'midi', 'vel', 'gate', 'origin', 'tag')

    def __init__(self, id, tick, lane, midi, vel, gate, origin='', tag=None):
        self.id, self.tick, self.lane = id, tick, lane
        self.midi, self.vel, self.gate = midi, vel, gate
        self.origin, self.tag = origin, tag

    def to_json(self):
        return {'id': self.id, 't': self.tick, 'lane': self.lane, 'midi': self.midi,
                'vel': self.vel, 'gate': self.gate, 'origin': self.origin,
                **({'tag': self.tag} if self.tag else {})}


class ControlEvent:
    """Director control on the schedule: sections, ducking, transport, sting pulses."""
    __slots__ = ('id', 'tick', 'kind', 'payload')

    def __init__(self, id, tick, kind, payload):
        self.id, self.tick, self.kind, self.payload = id, tick, kind, payload

    def to_json(self):
        return {'id': self.id, 't': self.tick, 'kind': self.kind, 'payload': self.payload}


class Receipt:
    """The director's answer to one cue: accepted, or why not."""
    __slots__ = ('cue_id', 'ok', 'action', 'reason', 'tick')

    def __init__(self, cue_id, ok, action, reason, tick):
        self.cue_id, self.ok, self.action, self.reason, self.tick = cue_id, ok, action, reason, tick

    def to_json(self):
        return {'cue_id': self.cue_id, 'ok': self.ok, 'action': self.action,
                'reason': self.reason, 't': self.tick}


class Schedule:
    """The canonical artifact: cues, receipts, control and note events, time-sorted."""
    def __init__(self, profile, seed):
        self.profile, self.seed = profile, seed
        self.cues, self.receipts, self.controls, self.notes = [], [], [], []
        self.meta = {'profile': profile, 'seed': seed, 'ticks_per_quarter': TICKS,
                     'bars': None, 'end_tick': None}

    def add(self, event):
        target = {'note': self.notes, 'control': self.controls, 'receipt': self.receipts}[event_kind(event)]
        target.append(event)
        if len(self.notes) > MAX_SCHEDULE:
            raise RuntimeError('Schedule bound exceeded: the director must not grow unboundedly')

    def finish(self, end_tick):
        self.meta['end_tick'] = end_tick
        self.meta['bars'] = (end_tick + BAR - 1) // BAR
        self.notes.sort(key=lambda n: (n.tick, n.lane, n.id))
        self.controls.sort(key=lambda c: (c.tick, c.id))
        self.receipts.sort(key=lambda r: (r.cue_id, r.tick))

    def write(self, folder, prefix):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f'{prefix}_schedule.json').write_text(json.dumps(self.meta, indent=2) + '\n')
        for name, rows, attr in (('notes', self.notes, 'to_json'),
                                 ('controls', self.controls, 'to_json'),
                                 ('receipts', self.receipts, 'to_json'),
                                 ('cues', self.cues, 'to_json')):
            with open(folder / f'{prefix}_{name}.jsonl', 'w') as f:
                for item in rows:
                    f.write(json.dumps(getattr(item, attr)(), sort_keys=True) + '\n')


def event_kind(event):
    if isinstance(event, NoteEvent):
        return 'note'
    if isinstance(event, ControlEvent):
        return 'control'
    if isinstance(event, Receipt):
        return 'receipt'
    raise TypeError(event)


def read_jsonl(path, parser):
    out = []
    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            out.append(parser(json.loads(line), lineno))
    return out


def validate_cue_json(data, lineno=0):
    try:
        return Cue.from_json(data)
    except ValueError as e:
        raise ValueError(f'line {lineno}: {e}') from None


def read_cues(path):
    """Read a JSONL cue timeline; invalid or corrupt lines raise with the line number."""
    return read_jsonl(path, validate_cue_json)


def write_jsonl(path, rows):
    with open(path, 'w') as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + '\n')
