# SPDX-License-Identifier: GPL-2.0-or-later
"""PROPOSED cue derivation from real game snapshots.

Available state vs proposed cues: the game exposes exactly the snapshot fields
of rogue/server.py (map, health, dead, won, bosses[], paused, ...). This module
reads ONLY those fields and proposes cues from them. The host decides what to
send; the director only ever trusts the cues it is fed.

Fields used, and the cue each transition proposes:

    dead false->true              player_death            (confirm: snapshot)
    won false->true               run_victory
    paused false->true / true->false   pause / resume
    map change                    floor_change            (env only via env_map)
    health decreased              damage_burst {amount}
    boss phase sealed->exposed    boss_exposed {name}
    boss phase exposed->sealed    boss_sealed {name}
    boss alive -> bound           boss_bound {name}       (confirm: snapshot)
    two bosses, both bound        tier_victory {tier}     (confirm: snapshot)
    boss living and actively engaged (on_seal, open_ticks,
      attacks, or damaged)        boss_encounter {names, tier}  engagement edge

Missing native hooks, deliberately NOT invented here:
    * first sight of an ordinary monster. The snapshot carries creature counts
      and status, but no per-monster visibility/proximity/hit-source data, and
      a count is not "first seen". Enemy sighting cues must come from the host
      (or a future engine hook); this module documents that gap.
    * a boss merely existing on the map is not an encounter: only the
      engagement heuristics above propose boss_encounter, and the host may
      override with its own authoritative cue.
"""
from .events import Cue

BOSS_ENGAGE = ('on_seal',)  # strongest available signal; see engage() below


def engage(snapshot):
    """A living demon the snapshot shows as actively engaged with the player.

    on_seal (player standing on its binding ring), an open exposure window, a
    recorded attack or taken damage are the available signals. Documented as a
    heuristic, not an authoritative encounter.
    """
    out = []
    for b in snapshot.get('bosses') or []:
        if not isinstance(b, dict) or b.get('phase') == 'bound':
            continue
        if b.get('on_seal') or b.get('open_ticks', 0) > 0 or b.get('attacks', 0) > 0 \
                or b.get('health', b.get('max_health', 1)) < b.get('max_health', 1):
            out.append(b)
    return out


def propose(prev, snap, tick, *, env_map=None, auto_id=None):
    """Proposed cues for the transition prev -> snap at musical tick `tick`.

    env_map: {'floor_name': 'profile_id'} for floor changes; without it the
    floor_change cue carries no env and the director keeps the current profile.
    Returns a list of Cues with source 'proposed' and stable ids.
    """
    if not isinstance(prev, dict) or not isinstance(snap, dict):
        return []
    n = 0

    def cue(type, payload, confirm=False):
        nonlocal n
        n += 1
        base = f'{auto_id or "proposed"}-{tick}-{type}-{n}'
        return Cue(base, tick, type, payload, source='proposed',
                   confirm=snap if confirm else None)

    out = []
    if not prev.get('dead') and snap.get('dead'):
        out.append(cue('player_death', {}))
    if not prev.get('won') and snap.get('won'):
        out.append(cue('run_victory', {}))
    if prev.get('paused') and not snap.get('paused'):
        out.append(cue('resume', {}))
    elif not prev.get('paused') and snap.get('paused'):
        out.append(cue('pause', {}))
    if snap.get('map') != prev.get('map'):
        payload = {'floor': snap.get('map', prev.get('map', 1))}
        env = (env_map or {}).get(snap.get('floor_name'))
        if env:
            payload['env'] = env
        out.append(cue('floor_change', payload))
    if (prev.get('health', 0) or 0) > (snap.get('health', 0) or 0):
        out.append(cue('damage_burst',
                       {'amount': prev['health'] - snap['health']}))
    prev_bosses = {b.get('name'): b for b in (prev.get('bosses') or []) if isinstance(b, dict)}
    bosses = [b for b in (snap.get('bosses') or []) if isinstance(b, dict)]
    living = [b for b in bosses if b.get('phase') != 'bound']
    bound_names = {b.get('name') for b in bosses if b.get('phase') == 'bound'}
    # Boss presence is not previous engagement. Compare engagement on two
    # snapshots from the same run/floor; names are reused after a retry.
    same_context = all(prev.get(key) == snap.get(key) for key in ('seed', 'revision', 'map'))
    if same_context:
        engaged = engage(snap) if living else []
        if engaged and len(bosses) == 2 and len({b.get('name') for b in bosses}) == 2:
            known = {b.get('name') for b in engage(prev)}
            if not known & {b.get('name') for b in engaged}:
                out.append(cue('boss_encounter',
                               {'names': sorted(b.get('name') for b in bosses),
                                'tier': max(1, snap.get('map', 1))}))
        for b in bosses:
            name, phase = b.get('name'), b.get('phase')
            before = prev_bosses.get(name, {})
            if before.get('phase') != 'bound' and phase == 'bound':
                out.append(cue('boss_bound', {'name': name}, confirm=True))
            elif before.get('phase') == 'sealed' and phase == 'exposed':
                out.append(cue('boss_exposed', {'name': name}))
            elif before.get('phase') == 'exposed' and phase == 'sealed':
                out.append(cue('boss_sealed', {'name': name}))
    before_complete = len(prev_bosses) == 2 and all(b.get('phase') == 'bound' for b in prev_bosses.values())
    complete = len(bosses) == 2 and not living and len(bound_names) == 2
    if same_context and complete and not before_complete:
        # Both demons bound; the director still requires game confirmation.
        out.append(cue('tier_victory',
                       {'tier': max(1, snap.get('map', 1))}, confirm=True))
    return out
