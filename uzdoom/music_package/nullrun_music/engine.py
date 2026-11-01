# SPDX-License-Identifier: GPL-2.0-or-later
"""Engine: realizes director actions into the canonical schedule.

Two modes, one code path:

* offline(materialize=True): a full cue timeline becomes a Schedule of
  concrete note events (used for fixtures, tests and the reference renders).
* live(materialize=False): the same walk emits only director actions, which
  the host adapter maps onto the real tracker control verbs. Both modes run
  the identical director/composer code, so an offline run and a live run that
  feeds the same cues tick for tick produce identical music.

Bars are emitted whole, from the current section; loop sections repeat by
bar index, one-shot sections (victory, death, floor bridge) stop at their end.
The transport freezes on suspend and restarts the current bar on resume
(documented policy).
"""
from .composer import (compose_section, compose_transition, compose_fill_bar,
                       compose_sting, finalize_bar, LANES)
from .director import Director, PRIORITY, TRANSITION_LEN
from .events import BAR, ROW, Cue, ControlEvent, NoteEvent, Schedule
from .profiles import PROFILES

SECTION_STATES = ('exploration', 'threat', 'combat', 'quiet',
                  'boss_sealed', 'boss_exposed', 'boss_one_down')


class Engine:
    def __init__(self, seed, initial_env='drowned_records', materialize=True,
                 profiles=None):
        self.profiles = profiles or PROFILES
        self.seed = seed
        self.materialize = materialize
        self.director = Director(seed, initial_env)
        self.schedule = Schedule(initial_env, seed)
        self.cursor = 0
        self.section = None          # Section object currently playing
        self.section_kind = None
        self.section_start = 0
        self.section_floor = 0
        self.section_env = initial_env
        self.section_profile = self.profiles[initial_env]
        self.frozen = False
        self.duck_until = -1
        self.duck_mask = []
        self.note_id = 0
        self.fill_due = False        # one fill bar before the next switch
        self._cache = {}

    # -- section content ------------------------------------------------------
    def _section(self, state, floor, env):
        key = (state, floor, env)
        if key not in self._cache:
            profile = self.profiles[env or self.section_env]
            content = (compose_section(profile, self.seed, state, floor, env)
                       if state in SECTION_STATES
                       else compose_transition(profile, self.seed, state, floor))
            self._cache[key] = (profile, content)
        if len(self._cache) > 32:    # bounded: at most a few floors x states
            self._cache = dict(list(self._cache.items())[-32:])
        return self._cache[key]

    def _emit_bar(self, content, bar_idx, tick, fill=False, row0=0):
        """One bar of concrete notes. Lanes stay monophonic; gates stay inside
        the bar; row0 skips already-played rows after a resume."""
        if not self.materialize:
            return
        if fill:
            profile, section = self._fill(tick)
        else:
            profile, section = self._section(self.section_kind, self.section_floor,
                                             self.section_env)
        bars = len(section.lanes[0])
        cells = finalize_bar(section, bar_idx % bars if section.loop else bar_idx)
        for lane in range(LANES):
            for (row, midi, vel, gate) in cells[lane]:
                if row < row0:
                    continue
                ducked = lane in self.duck_mask and tick < self.duck_until
                self.note_id += 1
                self.schedule.add(NoteEvent(
                    id=f'n{self.note_id:07d}', tick=tick + row * ROW, lane=lane,
                    midi=midi, vel=vel, gate=gate * ROW,
                    origin=f"{profile['id']}:{self.section_kind}:floor{self.section_floor}",
                    tag='ducked' if ducked else None))

    def _fill(self, tick):
        profile = self.section_profile
        bar_idx = int(((tick - self.section_start) // BAR) % profile['bars_per_loop'])
        key = ('fill', profile['id'], self.section_kind, self.section_floor, bar_idx)
        if key not in self._cache:
            self._cache[key] = (profile, compose_fill_bar(
                profile, self.seed, self.section_kind, self.section_floor, bar_idx))
        return self._cache[key]

    # -- realization ----------------------------------------------------------
    MATERIALIZE_CAP_BARS = 1024   # offline materializes at most this many bars

    def realize_until(self, tick):
        """Emit bars of the current section covering [cursor, tick).

        The transport freezes on suspend and resumes exactly at the frozen
        tick: the first bar after a resume is emitted from its remaining rows.
        Offline realization is bounded: at most MATERIALIZE_CAP_BARS beyond the
        cursor (a multi-hour run is the live tracker's job; the canonical
        schedule materializes a bounded window and documents the gap)."""
        if self.frozen:
            self.cursor = tick
            return
        if tick > self.cursor + self.MATERIALIZE_CAP_BARS * BAR:
            tick = self.cursor + self.MATERIALIZE_CAP_BARS * BAR
        bar_start = (self.cursor // BAR) * BAR
        if self.section is not None:
            bar_start = max(bar_start, self.section_start)  # never emit before a section's start
        while bar_start + BAR <= tick:
            if self.section is None:
                break
            bar_idx = int((bar_start - self.section_start) // BAR)
            if not self.section.loop and bar_idx >= len(self.section.lanes[0]):
                break
            fill = self.fill_due and bar_start + BAR >= tick and self.section.loop
            row0 = max(0, (self.cursor - bar_start) // ROW) if bar_start == (self.cursor // BAR) * BAR else 0
            self._emit_bar(self.section, bar_idx, bar_start, fill, row0=row0)
            bar_start += BAR
        self.cursor = max(self.cursor, bar_start)

    def apply_action(self, action):
        t, kind, payload = action['t'], action['kind'], action['payload']
        if kind == 'section':
            state, floor, env = payload['state'], payload['floor'], payload.get('env', self.section_env)
            profile = self.profiles[env or self.section_env]
            self.section, self.section_kind = self._section(state, floor, env)[1], state
            self.section_start, self.section_floor, self.section_env = t, floor, env
            self.section_profile = profile
            self.fill_due = False
            self._control('section', dict(payload, t=t))
        elif kind == 'transition':
            trans = compose_transition(self.profiles[self.section_env], self.seed,
                                       payload['kind'], payload.get('floor', self.section_floor))
            self.section, self.section_kind = trans, payload['kind']
            self.section_start = t
            if 'env' in payload:
                self.section_env = payload['env']
                self.section_profile = self.profiles[payload['env']]
            self._control('transition', dict(payload, t=t))
            # What follows the one-shot: a floor bridge hands over to the new
            # floor's exploration. Victory/death/boss-intro endings are the
            # director's timers (single source of truth for state changes).
            after = t + TRANSITION_LEN[payload['kind']] * BAR
            if payload.get('then') == 'exploration':
                self.actions_later = getattr(self, 'actions_later', [])
                # A newer floor bridge replaces a pending one (latest wins).
                self.actions_later = [a for a in self.actions_later
                                      if not (a['kind'] == 'section'
                                              and a['payload'].get('state') == 'exploration')]
                self.actions_later.append({'t': after, 'kind': 'section',
                                           'payload': {'state': 'exploration',
                                                       'floor': payload.get('floor', self.section_floor),
                                                       'env': payload.get('env', self.section_env)}})
        elif kind == 'sting':
            profile = self.section_profile
            sting = compose_sting(profile, self.seed, payload['sting'], payload.get('cue_id', ''))
            self._control('sting', dict(payload, t=t))
            for note in sting:
                self.note_id += 1
                self.schedule.add(NoteEvent(
                    id=f'n{self.note_id:07d}', tick=t, lane=note['lane'], midi=note['midi'],
                    vel=note['vel'], gate=note['gate'] * ROW,
                    origin=f"{profile['id']}:sting:{payload['sting']}"))
        elif kind == 'duck':
            self._control('duck_on', dict(mask=payload['mask'], until=payload['until'], t=t))
            self.duck_mask, self.duck_until = payload['mask'], payload['until']
            self.actions_later = getattr(self, 'actions_later', [])
            self.actions_later.append({'t': payload['until'], 'kind': 'duck_off', 'payload': {}})
        elif kind == 'duck_off':
            self.duck_mask, self.duck_until = [], -1
            self._control('duck_off', {'t': t})
        elif kind == 'suspend':
            self._control('all_off', {'t': t, 'reason': payload.get('reason')})
            self._control('suspend', {'t': t, 'reason': payload.get('reason')})
            for note in self.schedule.notes:   # releasing gates: nothing rings on
                if note.tick < t < note.tick + note.gate:
                    note.gate = t - note.tick
            self.frozen = True
            self.freeze_tick = t
        elif kind == 'resume':
            self._control('resume', {'t': t})
            self.frozen = False
            self.cursor = getattr(self, 'freeze_tick', t)   # resume at the frozen tick
        elif kind == 'silence':
            self._control('all_off', {'t': t})
            self.section = None
        elif kind == 'reset':
            self._control('reset', dict(payload, t=t))
            self.seed = payload['seed']
            self.section = None
            self.duck_mask, self.duck_until = [], -1
        else:
            raise ValueError(f'unknown action {kind}')

    def _control(self, kind, payload):
        if self.materialize:
            self.schedule.add(ControlEvent(
                id=f'c{len(self.schedule.controls) + len(self.schedule.notes):07d}',
                tick=payload['t'], kind=kind, payload=payload))

    def take_later_actions(self):
        later, self.actions_later = getattr(self, 'actions_later', []), []
        return sorted(later, key=lambda a: a['t'])

    # -- the two drivers ------------------------------------------------------
    def offline(self, cues, tail_bars=2, end_tick=None):
        """Realize a full cue timeline into a Schedule.

        Actions scheduled for a future tick are deferred and applied when that
        tick arrives (before the bars at that tick are realized), so sections,
        ducks and stings land exactly where the director placed them.
        """
        events = sorted(cues, key=lambda c: (c.tick, -PRIORITY[c.type], c.id))
        times = [c.tick for c in events] + [0]
        self.director.begin(0)
        self.schedule.cues = list(events)
        deferred = []
        t = 0
        while times:
            t = min(times)
            times = [x for x in times if x > t]
            # Realize the CURRENT section up to t first; actions at t then take
            # effect exactly at t, so a section switch never rewrites earlier bars.
            self.realize_until(t)
            due = [c for c in events if c.tick <= t and c not in self._fed]
            for cue in due:
                self._fed.add(cue)
                self.director.feed(cue, t)
            self.director.advance(t)
            pending = deferred + self.director.take_actions() + self.take_later_actions()
            deferred = []
            for action in pending:
                if action['t'] <= t:
                    self.apply_action(action)
                else:
                    deferred.append(action)
                    times.append(action['t'])
            timer = self.director.next_timer()
            if timer is not None and timer > t:
                times.append(timer)
        finish = end_tick if end_tick is not None else max(self.cursor, t) + tail_bars * BAR
        self.realize_until(finish)
        for receipt in self.director.receipts:
            if receipt not in self.schedule.receipts:
                self.schedule.receipts.append(receipt)
        self.schedule.finish(finish)
        return self.schedule

    # fed bookkeeping per offline run
    @property
    def _fed(self):
        if not hasattr(self, '_fed_set'):
            self._fed_set = set()
        return self._fed_set

    def live(self, cue, now):
        """Feed one cue at the host's current tick; return new director actions.

        The host must feed cues in (tick, priority, id) order -- the adapter
        does -- so a live run mirrors the offline canonical run exactly.
        """
        self.director.feed(cue, now)
        self.director.advance(now)
        return self.director.take_actions()

    def live_advance(self, now):
        """Advance with no new cue (timers still fire)."""
        self.director.advance(now)
        return self.director.take_actions()
