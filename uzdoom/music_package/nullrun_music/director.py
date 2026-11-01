# SPDX-License-Identifier: GPL-2.0-or-later
"""The adaptive director: a deterministic state machine over musical ticks.

Responsibilities (see DESIGN.md for the full table):
* fixed priorities and deterministic ordering for simultaneous cues
* cooldowns, dedup, minimum dwell, hysteresis for every transition
* every musical change scheduled at a documented boundary: sections and fills
  at bar starts, stings and ducking at the next 1/8 note
* the two-boss tier rule: one bound demon keeps tension; victory only after the
  second is bound AND game state confirms it
* bounded queues and bounded history, so a 35 Hz poll can never grow memory
* pause/resume with prompt all-notes-off, no backlog flush

The director schedules actions; it never composes or plays audio itself. It is
a pure function of (seed, cue stream, tick), so identical timelines replay
identically and a live host can mirror an offline run tick for tick.
"""
from .events import BAR, EIGHTH, Cue, Receipt

# Cue priorities: higher wins when several cues fall on the same boundary.
# Ties break by (tick asc, id asc) -- fully deterministic.
PRIORITY = {
    'player_death': 100, 'run_victory': 99,
    'new_seed': 95,
    'resume': 93, 'pause': 92, 'focus_lost': 91,
    'tier_victory': 81, 'boss_encounter': 80, 'boss_bound': 79,
    'boss_exposed': 78, 'boss_sealed': 77,
    'damage_burst': 60,
    'floor_change': 50,
    'combat_start': 41, 'combat_end': 40,
    'enemy_first_seen': 30, 'enemy_sting': 20,
    'secret': 10,
}

# Minimum dwell per state, in bars.
DWELL = {'start': 1, 'exploration': 2, 'threat': 2, 'combat': 4, 'quiet': 2,
         'boss_intro': 2, 'boss_sealed': 2, 'boss_exposed': 2, 'boss_one_down': 2,
         'victory': 4, 'death': 4, 'interlude': 1, 'end': 0, 'paused': 0}

# Cooldowns in ticks.
COOLDOWN = {
    'enemy_sting': 2 * BAR, 'enemy_first_seen': 4 * BAR, 'damage_burst': 1 * BAR,
    'secret': 4 * BAR, 'boss_sealed': 1 * BAR, 'boss_exposed': 1 * BAR,
}

QUEUE_MAX = 64            # pending cues
HISTORY_MAX = 512         # processed ids / receipts kept
HISTORY_HORIZON = 64 * BAR
THREAT_REVERT = 4 * BAR   # threat without combat_start reverts to exploration
INTERLUDE_MAX = 4 * BAR   # silence after tier victory is bounded
COMBAT_QUIET = 2 * BAR    # quiet time before combat_end is honoured

TRANSITION_LEN = {'victory': 4, 'death': 4, 'bridge': 2}  # bars


class Director:
    def __init__(self, seed, initial_env=None):
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 0xFFFFFFFF:
            raise ValueError('Seed must be a whole number from 0 to 4294967295')
        self.seed = seed
        self.initial_env = initial_env
        self.state = 'start'
        self.pre_pause = None
        self.floor = 0
        self.env = initial_env
        self.state_start = 0
        self.state_len = 0            # bars the current state's content lasts
        self.victory_kind = None      # 'tier' or 'run'
        self.boss_names = []
        self.bound = set()
        self.pending = []
        self.processed = {}
        self.cooldowns = {}
        self.last_cue_tick = -1
        self.last_combat_tick = -(1 << 40)
        self.sting_until = 0
        self.revert_due = None
        self.interlude_until = None
        self.bridge_until = 0
        self.receipts = []
        self.actions = []

    # -- bookkeeping ----------------------------------------------------------
    def begin(self, now):
        """The engine's start: exploration from bar 0."""
        t = (now + BAR - 1) // BAR * BAR
        self.state, self.state_start, self.state_len = 'exploration', t, None
        self.actions.append({'id': 'act-init', 't': t, 'kind': 'section',
                             'payload': {'state': 'exploration', 'floor': 0, 'env': self.env},
                             'cue_id': 'init'})

    def _boundary(self, tick, min_bars=None):
        """The next bar start at or after `tick`, honouring the dwell of the
        state being left (explicit min_bars overrides it for urgent entries)."""
        bound = (tick + BAR - 1) // BAR * BAR
        dwell = DWELL.get(self.state, 0) if min_bars is None else min_bars
        return max(bound, self.state_start + dwell * BAR)

    _bar_boundary = _boundary  # legacy name used by timers

    @staticmethod
    def _eighth(tick):
        return (tick + EIGHTH - 1) // EIGHTH * EIGHTH

    def _receipt(self, cue, ok, action, reason, tick):
        r = Receipt(cue.id, ok, action, reason, tick)
        self.receipts.append(r)
        if len(self.receipts) > HISTORY_MAX:
            self.receipts = self.receipts[-HISTORY_MAX:]
        return r

    def _act(self, kind, payload, tick, cue_id):
        self.actions.append({'id': f'act-{len(self.actions)}', 't': tick, 'kind': kind,
                             'payload': payload, 'cue_id': cue_id})
        self.actions.sort(key=lambda a: (a['t'], a['kind'], a['id']))

    def _cooldown(self, key, tick):
        return tick < self.cooldowns.get(key, 0)

    def _set_cooldown(self, key, until):
        self.cooldowns[key] = max(self.cooldowns.get(key, 0), until)
        if len(self.cooldowns) > 64:
            horizon = min(self.cooldowns.values())
            self.cooldowns = {k: v for k, v in self.cooldowns.items() if v > horizon}

    def _prune(self, tick):
        if self.processed and min(self.processed.values()) < tick - HISTORY_HORIZON:
            self.processed = {k: v for k, v in self.processed.items() if v >= tick - HISTORY_HORIZON}

    def next_timer(self):
        """The earliest tick a timer fires, or None (drives the engine's step)."""
        due = []
        if self.state == 'threat' and self.revert_due is not None:
            due.append(self.revert_due)
        if self.state == 'interlude' and self.interlude_until is not None:
            due.append(self.interlude_until)
        if self.state == 'boss_intro':
            due.append(self.state_start + TRANSITION_LEN['bridge'] * BAR)
        if self.state in ('victory', 'death'):
            due.append(self.state_start + TRANSITION_LEN[self.state] * BAR)
        return min(due) if due else None

    def bounds(self):
        """Sizes of the bounded structures (tests assert these stay small)."""
        return {'pending': len(self.pending), 'processed': len(self.processed),
                'cooldowns': len(self.cooldowns), 'receipts': len(self.receipts),
                'actions': len(self.actions)}

    # -- cue intake -----------------------------------------------------------
    def feed(self, cue, now):
        """Accept or reject one cue; valid cues wait in the bounded queue."""
        if not isinstance(cue, Cue):
            raise ValueError('Director.feed takes a Cue')
        if isinstance(now, bool) or not isinstance(now, int) or not 0 <= now <= (1 << 48):
            return self._receipt(cue, False, 'reject', 'invalid clock tick', now)
        self._prune(now)
        if cue.tick < self.last_cue_tick:
            return self._receipt(cue, False, 'reject', 'stale (tick before an earlier cue)', now)
        if cue.id in self.processed:
            return self._receipt(cue, False, 'duplicate', 'cue id already processed', now)
        if self._cooldown(cue.key(), cue.tick):
            return self._receipt(cue, False, 'cooldown', 'cue type/dedup window active', now)
        if self.state == 'end':
            return self._receipt(cue, False, 'reject', 'run over: only new_seed restarts', now)
        if cue.tick < now - 2 * BAR:
            return self._receipt(cue, False, 'reject', 'stale (arrived too late)', now)
        if cue.type == 'floor_change' and any(c.type == 'floor_change' for c in self.pending):
            self.pending = [c for c in self.pending if c.type != 'floor_change']
            self._receipt(cue, True, 'supersede', 'replaced an earlier pending floor change', now)
            self.pending.append(cue)
            self.pending.sort(key=lambda c: (-PRIORITY[c.type], c.tick, c.id))
            return self._receipt(cue, True, 'queued', '', now)
        if len(self.pending) >= QUEUE_MAX:
            return self._receipt(cue, False, 'reject', 'queue full (64 pending cues)', now)
        self.pending.append(cue)
        self.pending.sort(key=lambda c: (-PRIORITY[c.type], c.tick, c.id))
        self.last_cue_tick = max(self.last_cue_tick, cue.tick)
        return self._receipt(cue, True, 'queued', '', now)

    # -- advancement ----------------------------------------------------------
    def advance(self, now):
        """Process due cues and fire timers. Idempotent per tick."""
        due = [c for c in self.pending if c.tick <= now]
        self.pending = [c for c in self.pending if c.tick > now]
        for cue in due:
            self.processed[cue.id] = cue.tick
            self._handle(cue, now)
        self._timers(now)

    def take_actions(self):
        actions, self.actions = self.actions, []
        return actions

    # -- timers ---------------------------------------------------------------
    def _timers(self, now):
        if self.state == 'threat' and self.revert_due is not None and now >= self.revert_due:
            self.revert_due = None
            self._switch('exploration', now)
        if self.state == 'interlude' and self.interlude_until is not None and now >= self.interlude_until:
            self.interlude_until = None
            self._switch('exploration', now)
        if self.state == 'boss_intro' and now >= self.state_start + TRANSITION_LEN['bridge'] * BAR:
            self._switch('boss_sealed', now)
        if self.state == 'victory' and now >= self.state_start + TRANSITION_LEN['victory'] * BAR:
            t = self.state_start + TRANSITION_LEN['victory'] * BAR
            if self.victory_kind == 'run':
                self.state, self.state_start = 'end', t
            else:
                self.state, self.state_start = 'interlude', t
                self.interlude_until = t + INTERLUDE_MAX
            self._act('silence', {'reason': 'run victory' if self.victory_kind == 'run' else 'tier victory'}, t, 'timer')
        if self.state == 'death' and now >= self.state_start + TRANSITION_LEN['death'] * BAR:
            t = self.state_start + TRANSITION_LEN['death'] * BAR
            self.state, self.state_start = 'end', t
            self._act('silence', {'reason': 'death'}, t, 'timer')

    def _switch(self, state, now, cue=None, floor=None, env=None, min_bars=None):
        t = self._boundary(now, min_bars)
        self.state, self.state_start = state, t
        self.state_len = None
        if floor is not None:
            self.floor = floor
        if env is not None:
            self.env = env
        payload = {'state': state, 'floor': self.floor, 'env': self.env}
        self._act('section', payload, t, cue.id if cue else 'timer')
        if cue is not None:
            self._receipt(cue, True, f'enter {state}', '', t)

    # -- cue handlers ---------------------------------------------------------
    def _handle(self, cue, now):
        getattr(self, f'_on_{cue.type}')(cue, now)

    def _sting(self, cue, kind, now):
        if self.state == 'paused' or self.state in ('death', 'end'):
            self._receipt(cue, False, 'drop', f'no sting in {self.state}', now)
            return
        if now < self.sting_until:
            self._receipt(cue, False, 'sting busy', 'one sting voice; an earlier sting is still sounding', now)
            return
        t = self._eighth(now)
        self.sting_until = t + BAR
        self._act('sting', {'sting': kind, 'cue_id': cue.id}, t, cue.id)
        self._receipt(cue, True, f'sting {kind}', '', t)

    def _duck(self, cue, profile, now):
        t = self._eighth(now)
        beats = profile['duck']['beats']
        self._act('duck', {'mask': profile['duck']['mask'], 'until': t + beats * 2 * EIGHTH}, t, cue.id)

    def _profile(self):
        from .profiles import PROFILES
        return PROFILES[self.env or self.initial_env or 'drowned_records']

    def _require_confirm(self, cue):
        """Both demons must be bound AND the game state must confirm it."""
        if len(self.bound) < 2 or not set(self.boss_names) <= self.bound:
            return False, 'tier not fully bound'
        confirm = cue.confirm
        if not isinstance(confirm, dict):
            return False, 'needs game confirmation (attach the snapshot or send tier_victory with confirm)'
        if confirm.get('won') is True:
            return True, ''
        bosses = confirm.get('bosses')
        if isinstance(bosses, list):
            by_name = {b.get('name'): b for b in bosses if isinstance(b, dict)}
            if all(by_name.get(n, {}).get('phase') == 'bound' for n in self.boss_names):
                return True, ''
            if all(by_name.get(n, {}).get('health', 1) <= 0 for n in self.boss_names):
                return True, ''
        return False, 'game state does not confirm both demons bound'

    def _victory(self, cue, now, kind):
        ok, why = self._require_confirm(cue)
        if not ok and kind == 'tier' and len(self.bound) >= 2:
            ok, why = self._confirm_both(cue)
        if not ok:
            self._receipt(cue, False, 'reject', why, now)
            return
        t = self._boundary(now, 1)
        self.state, self.state_start, self.state_len = 'victory', t, TRANSITION_LEN['victory']
        self.victory_kind = kind
        self._act('transition', {'kind': 'victory', 'floor': self.floor}, t, cue.id)
        self._act('sting', {'sting': 'victory', 'cue_id': cue.id}, t, cue.id)
        self._receipt(cue, True, 'victory cadence', '', t)

    def _on_enemy_first_seen(self, cue, now):
        self._set_cooldown(cue.key(), cue.tick + COOLDOWN['enemy_first_seen'])
        if self.state in ('boss_intro', 'boss_sealed', 'boss_exposed', 'boss_one_down'):
            self._receipt(cue, True, 'ignored', 'boss music dominates enemy stings', now)
        elif self.state in ('exploration', 'quiet', 'start'):
            self.revert_due = self._boundary(now) + THREAT_REVERT
            self._switch('threat', now, cue)
        elif self.state == 'combat':
            self._sting(cue, 'enemy', now)
        else:
            self._receipt(cue, True, 'ignored', f'no reaction in {self.state}', now)

    def _on_enemy_sting(self, cue, now):
        self._set_cooldown(cue.key(), cue.tick + COOLDOWN['enemy_sting'])
        if self.state == 'combat':
            self._sting(cue, 'enemy', now)
        else:
            self._receipt(cue, True, 'ignored', f'enemy stings only during combat, not {self.state}', now)

    def _on_combat_start(self, cue, now):
        if self.state in ('exploration', 'threat', 'quiet', 'start'):
            self.revert_due = None
            self.last_combat_tick = cue.tick
            self._switch('combat', now, cue)
        elif self.state == 'combat':
            self.last_combat_tick = cue.tick
            self._receipt(cue, True, 'already', 'combat continues', now)
        else:
            self._receipt(cue, True, 'ignored', f'no combat entry from {self.state}', now)

    def _on_combat_end(self, cue, now):
        if self.state != 'combat':
            self._receipt(cue, True, 'ignored', f'not in combat ({self.state})', now)
            return
        if now - self.last_combat_tick < COMBAT_QUIET:
            self.pending.append(cue)
            self.pending.sort(key=lambda c: (-PRIORITY[c.type], c.tick, c.id))
            self._receipt(cue, True, 'deferred', f'combat must be quiet {COMBAT_QUIET // BAR} bars first', now)
            return
        self._switch('quiet', now, cue)

    def _on_damage_burst(self, cue, now):
        self._set_cooldown(cue.key(), cue.tick + COOLDOWN['damage_burst'])
        if self.state in ('death', 'end', 'paused'):
            self._receipt(cue, False, 'drop', f'no damage sting in {self.state}', now)
            return
        self.last_combat_tick = cue.tick
        self._sting(cue, 'damage', now)
        self._duck(cue, self._profile(), now)

    def _on_secret(self, cue, now):
        self._set_cooldown(cue.key(), cue.tick + COOLDOWN['secret'])
        if self.state in ('death', 'end', 'paused'):
            self._receipt(cue, False, 'drop', f'no secret sting in {self.state}', now)
        else:
            self._sting(cue, 'secret', now)

    def _on_boss_encounter(self, cue, now):
        names = cue.payload.get('names', [])
        if len(names) != 2 or len(set(names)) != 2:
            self._receipt(cue, False, 'reject', 'a tier encounter names exactly two distinct demons', now)
            return
        if self.state == 'end':
            self._receipt(cue, False, 'reject', 'run over', now)
            return
        self.boss_names, self.bound = list(names), set()
        t = self._boundary(now, 1)
        self.state, self.state_start = 'boss_intro', t
        self.state_len = TRANSITION_LEN['bridge']
        self._act('transition', {'kind': 'bridge', 'floor': self.floor,
                                 'boss_names': self.boss_names}, t, cue.id)
        self._act('sting', {'sting': 'boss', 'cue_id': cue.id}, t, cue.id)
        self._receipt(cue, True, 'boss intro', '', t)

    def _on_boss_sealed(self, cue, now):
        name = cue.payload['name']
        if name not in self.boss_names:
            self._receipt(cue, False, 'reject', 'unknown demon for this tier', now)
            return
        self._set_cooldown(cue.key(), cue.tick + COOLDOWN['boss_sealed'])
        if self.state == 'boss_exposed':
            self._switch('boss_sealed', now, cue)
        else:
            self._receipt(cue, True, 'already', 'arrangement stays sealed', now)

    def _on_boss_exposed(self, cue, now):
        name = cue.payload['name']
        if name not in self.boss_names:
            self._receipt(cue, False, 'reject', 'unknown demon for this tier', now)
            return
        self._set_cooldown(cue.key(), cue.tick + COOLDOWN['boss_exposed'])
        self.last_combat_tick = cue.tick
        if self.state in ('boss_intro', 'boss_sealed', 'boss_one_down'):
            self._switch('boss_exposed', now, cue)
        else:
            self._receipt(cue, True, 'already', 'arrangement already exposed', now)

    def _on_boss_bound(self, cue, now):
        name = cue.payload['name']
        if name not in self.boss_names:
            self._receipt(cue, False, 'reject', 'unknown demon for this tier', now)
            return
        if name in self.bound:
            self._receipt(cue, False, 'duplicate', 'demon already bound', now)
            return
        if not self.bound:
            # First bind keeps tension; no game confirmation needed.
            self.bound.add(name)
            if self.state in ('boss_intro', 'boss_sealed', 'boss_exposed'):
                self._switch('boss_one_down', now, cue)
            else:
                self._receipt(cue, True, 'tension kept', 'first demon bound', now)
            return
        # Second bind: the game state must confirm it before it counts; an
        # unconfirmed bind is not recorded, so a confirmed retry still works.
        ok, why = self._confirm_both(cue)
        if not ok:
            self._receipt(cue, False, 'needs game confirmation', why, now)
            return
        self.bound.add(name)
        self._victory(cue, now, 'tier')

    def _confirm_both(self, cue):
        """The snapshot must show both named demons bound (or the run won)."""
        confirm = cue.confirm
        if not isinstance(confirm, dict):
            return False, 'attach the snapshot (confirm), or send tier_victory with confirm'
        if confirm.get('won') is True:
            return True, ''
        bosses = confirm.get('bosses')
        if isinstance(bosses, list):
            by_name = {b.get('name'): b for b in bosses if isinstance(b, dict)}
            if all(by_name.get(n, {}).get('phase') == 'bound' for n in self.boss_names):
                return True, ''
            if all(by_name.get(n, {}).get('health', 1) <= 0 for n in self.boss_names):
                return True, ''
        return False, 'game state does not confirm both demons bound'

    def _on_tier_victory(self, cue, now):
        self._victory(cue, now, 'tier')

    def _on_floor_change(self, cue, now):
        if self.state == 'end':
            self._receipt(cue, False, 'reject', 'run over', now)
            return
        if self.state == 'paused':
            self.pending.append(cue)
            self.pending.sort(key=lambda c: (-PRIORITY[c.type], c.tick, c.id))
            self._receipt(cue, True, 'deferred', 'floor change waits for resume', now)
            return
        floor = cue.payload['floor']
        env = cue.payload.get('env', self.env)
        # Rapid floor changes coalesce: an earlier, not-yet-played bridge is
        # superseded by the new destination (latest wins).
        dropped = [a for a in self.actions
                   if a['kind'] == 'transition' and a['payload'].get('kind') == 'bridge']
        for a in dropped:
            self.actions.remove(a)
        superseded = bool(dropped) or now < self.bridge_until
        if superseded:
            self._receipt(cue, True, 'supersede',
                          'replaced an earlier or in-progress floor bridge', now)
        t = self._boundary(now, 1)
        self.state, self.state_start = 'exploration', t
        self.floor, self.env = floor, env
        self.bridge_until = t + TRANSITION_LEN['bridge'] * BAR
        self._act('transition', {'kind': 'bridge', 'floor': floor, 'env': env,
                                 'then': 'exploration'}, t, cue.id)
        self._receipt(cue, True, 'floor bridge', '', t)

    def _on_pause(self, cue, now):
        if self.state == 'paused':
            self._receipt(cue, True, 'already', 'already suspended', now)
            return
        t = self._eighth(now)
        self._act('suspend', {'reason': 'pause'}, t, cue.id)
        self.pre_pause, self.state = self.state, 'paused'
        self.pending = []   # documented backlog policy: pending cues are dropped
        self._receipt(cue, True, 'suspend', 'all notes off, transport frozen', t)

    def _on_focus_lost(self, cue, now):
        if self.state == 'paused':
            self._receipt(cue, True, 'already', 'already suspended', now)
            return
        t = self._eighth(now)
        self._act('suspend', {'reason': 'focus lost'}, t, cue.id)
        self.pre_pause, self.state = self.state, 'paused'
        self.pending = []
        self._receipt(cue, True, 'suspend', 'focus lost: all notes off, transport frozen', t)

    def _on_resume(self, cue, now):
        if self.state != 'paused':
            self._receipt(cue, True, 'already', 'not suspended', now)
            return
        t = self._eighth(now)
        self.state = self.pre_pause or 'exploration'
        self.pre_pause = None
        self._act('resume', {'state': self.state, 'floor': self.floor, 'env': self.env}, t, cue.id)
        self._receipt(cue, True, 'resume', 'transport continues from the frozen tick', t)

    def _on_player_death(self, cue, now):
        if self.state == 'end':
            self._receipt(cue, True, 'already', 'run already over', now)
            return
        t = self._boundary(now, 1)
        self.state, self.state_start, self.state_len = 'death', t, TRANSITION_LEN['death']
        self._act('transition', {'kind': 'death', 'floor': self.floor}, t, cue.id)
        self._receipt(cue, True, 'death treatment', '', t)

    def _on_run_victory(self, cue, now):
        if self.state == 'end':
            self._receipt(cue, True, 'already', 'run already over', now)
            return
        t = self._bar_boundary(now, 'victory')
        self.state, self.state_start, self.state_len = 'victory', t, TRANSITION_LEN['victory']
        self.victory_kind = 'run'
        self._act('transition', {'kind': 'victory', 'floor': self.floor}, t, cue.id)
        self._act('sting', {'sting': 'victory', 'cue_id': cue.id}, t, cue.id)
        self._receipt(cue, True, 'victory cadence', '', t)

    def _on_new_seed(self, cue, now):
        self.seed = cue.payload['seed']
        t = self._eighth(now)
        self._act('reset', {'seed': self.seed}, t, cue.id)
        self.state, self.pre_pause = 'start', None
        self.floor, self.env = 0, self.initial_env
        self.boss_names, self.bound = [], set()
        self.pending, self.processed, self.cooldowns = [], {}, {}
        self.revert_due = self.interlude_until = None
        self.victory_kind = None
        self.state_start = self._boundary(now, 1)
        self._receipt(cue, True, 'reset', 'new seed: exploration from bar 0', t)

    # -- serialization (pause-safe state, no hidden mutable globals) ----------
    def state_dict(self):
        return {'seed': self.seed, 'initial_env': self.initial_env,
                'state': self.state, 'pre_pause': self.pre_pause,
                'floor': self.floor, 'env': self.env,
                'state_start': self.state_start, 'state_len': self.state_len,
                'victory_kind': self.victory_kind,
                'boss_names': list(self.boss_names), 'bound': sorted(self.bound),
                'pending': [c.to_json() for c in self.pending],
                'processed': dict(self.processed),
                'cooldowns': {str(k): v for k, v in self.cooldowns.items()},
                'last_cue_tick': self.last_cue_tick,
                'last_combat_tick': self.last_combat_tick,
                'sting_until': self.sting_until, 'revert_due': self.revert_due,
                'interlude_until': self.interlude_until,
                'receipts': [r.to_json() for r in self.receipts[-HISTORY_MAX:]],
                'actions': [dict(a) for a in self.actions]}

    @classmethod
    def from_state(cls, d):
        self = cls(d['seed'], d.get('initial_env'))
        self.state, self.pre_pause = d['state'], d.get('pre_pause')
        self.floor, self.env = d['floor'], d.get('env')
        self.state_start, self.state_len = d['state_start'], d.get('state_len')
        self.victory_kind = d.get('victory_kind')
        self.boss_names, self.bound = list(d['boss_names']), set(d['bound'])
        self.pending = [Cue.from_json(c) for c in d['pending']]
        self.processed = {k: int(v) for k, v in d['processed'].items()}
        self.cooldowns = {eval(k): int(v) for k, v in d['cooldowns'].items()}
        self.last_cue_tick = d['last_cue_tick']
        self.last_combat_tick = d['last_combat_tick']
        self.sting_until = d['sting_until']
        self.revert_due, self.interlude_until = d.get('revert_due'), d.get('interlude_until')
        self.receipts = [Receipt(r['cue_id'], r['ok'], r['action'], r['reason'], r['t'])
                         for r in d['receipts']]
        self.actions = [dict(a) for a in d['actions']]
        return self
