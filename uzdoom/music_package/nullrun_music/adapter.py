# SPDX-License-Identifier: GPL-2.0-or-later
"""The dry-run live adapter and its contract.

The adapter maps director actions onto the tracker control verbs that exist in
the frozen HydraPy Studio today (read from studio.py, NOT invented):

* `tracker_score`   -- replace the score document (position preserved by
                       Tracker.replace / the _carry mapping; preserves phase
                       when timelines share geometry)
* `tracker_transport` -- enabled/playing/beat/fill, and the Gorgon-style bus
                       window {segment, sender, bus} (lease-based lane mutes)

DryRunStudio records every call so tests can assert latency bounds and call
shapes without any live Studio. It is NOT fake playback: it replays exactly
the verbs a real host would send, and never claims audio output.
"""
import copy

from .events import BAR, EIGHTH, ROW
from .export_tracker import section_document, transition_document
from .composer import compose_sting
from .scale import midi_to_name

SENDER_ID = 'deadbeef00000001'  # 16 hex digits, as the bus window contract asks


class DryRunStudio:
    """Records the adapter's calls; simulates the tracker's revision counter."""
    def __init__(self):
        self.calls = []          # (tick, verb, size_bytes, detail)
        self.revision = 0
        self.score = None        # the current document (dry-run only)
        self.segment = {'transport_revision': 0, 'start': {'tick': 0, 'entry': None}}

    def tracker_score(self, document, tick):
        self.revision += 1
        size = len(str(document))
        self.calls.append((tick, 'tracker_score', size, 'document replace'))
        self.score = document
        return {'revision': self.revision}

    def tracker_transport(self, payload, tick):
        self.calls.append((tick, 'tracker_transport', len(str(payload)), str(sorted(payload))))
        return {'start': dict(self.segment['start']), 'transport_revision': self.segment['transport_revision']}

    def calls_between(self, t0, t1):
        return [c for c in self.calls if t0 <= c[0] < t1]


class HostAdapter:
    """Feeds cues into the director and applies its actions against Studio verbs.

    Sting latency is bounded to the next 1/8 note; section changes land on bar
    boundaries; ducking uses bus windows; suspend releases every gate at once.
    """
    def __init__(self, engine, studio=None):
        self.engine = engine
        self.studio = studio or DryRunStudio()
        self.documents = {}       # (kind, floor, env) -> validated document
        self.current_doc = None
        self.current_doc_key = None
        self.current_section_start = 0
        self.log = []

    def _document(self, kind, floor, env):
        key = (kind, floor, env)
        if key not in self.documents:
            profile = self.engine.profiles[env or self.engine.section_env]
            content = self.engine._section(kind, floor, env)[1]
            doc = (transition_document(profile, content, self.engine.seed)
                   if kind in ('victory', 'death', 'bridge')
                   else section_document(profile, content, self.engine.seed))
            self.documents[key] = doc
        return self.documents[key]

    def apply(self, action):
        kind, t, payload = action['kind'], action['t'], action['payload']
        if kind == 'section':
            doc = self._document(payload['state'], payload['floor'],
                                 payload.get('env', self.engine.section_env))
            self.studio.tracker_score(doc, t)
            self.current_doc, self.current_doc_key = doc, (payload['state'], payload['floor'])
            self.current_section_start = t
            self.log.append(('section', t, payload['state']))
        elif kind == 'transition':
            doc = self._document(payload['kind'], payload.get('floor', 0),
                                 self.engine.section_env)
            self.studio.tracker_score(doc, t)
            self.current_doc, self.current_doc_key = doc, (payload['kind'], payload.get('floor', 0))
            self.current_section_start = t
            self.log.append(('transition', t, payload['kind']))
        elif kind == 'sting':
            self._apply_sting(payload['sting'], payload.get('cue_id', ''), t)
        elif kind == 'duck':
            self._bus_window(t, mask=payload['mask'], until=payload['until'])
        elif kind == 'suspend':
            # Prompt, safe: release every gate, freeze the transport.
            self.studio.tracker_transport(
                {'playing': False, 'enabled': self.engine.director.state != 'paused'}, t)
            self._bus_window(t, mask=[0, 1, 2, 3, 4, 5], until=None, release=True)
        elif kind == 'resume':
            self.studio.tracker_transport({'playing': True}, t)
        elif kind == 'silence':
            self._bus_window(t, mask=[0, 1, 2, 3, 4, 5], until=None)
        elif kind == 'reset':
            doc = self._document('exploration', 0, self.engine.section_env)
            self.studio.tracker_score(doc, t)
        return self.log[-1] if self.log else None

    def _apply_sting(self, sting_kind, cue_id, t):
        """Primary sting path: insert the sting's exact cells at the target row
        (a tracker_score edit), then pulse FILL for the sting's gate."""
        if self.current_doc is None:
            return
        profile = self.engine.section_profile
        sting = compose_sting(profile, self.engine.seed, sting_kind, cue_id)
        doc = copy.deepcopy(self.current_doc)
        index = doc['pattern'] if doc['loop'] else doc['chain'][0]
        pattern = doc['patterns'][index]
        rows = len(pattern['lanes'][0]['cells'])
        row = ((t - self.current_section_start) // ROW) % rows
        for i, note in enumerate(sting):
            cell_row = min(rows - 1, row + i)
            pattern['lanes'][5]['cells'][cell_row] = {'note': midi_to_name(note['midi']),
                                                      'vel': note['vel'], 'len': 1.0}
        self.studio.tracker_score(doc, t)          # the edit path exists in Studio
        gate_ticks = sting[0]['gate'] * ROW
        self.studio.tracker_transport({'fill': True}, t)
        self.studio.tracker_transport({'fill': False}, t + gate_ticks)
        self.log.append(('sting', t, sting_kind))

    def _bus_window(self, t, mask, until, release=False):
        """A Gorgon-style bus window: lane mutes from tick t (lease-based)."""
        from_tick = max(0, t)
        mutes = []
        for lane in range(6):
            on = lane in mask
            mutes.append([{'at': from_tick, 'on': on}] +
                         ([{'at': max(from_tick + 1, until), 'on': False}] if until else []))
        window = {'from': from_tick, 'fill': [{'at': from_tick, 'on': False}],
                  'mutes': mutes}
        self.studio.tracker_transport(
            {'segment': self.studio.segment, 'sender': SENDER_ID, 'bus': window}, t)
