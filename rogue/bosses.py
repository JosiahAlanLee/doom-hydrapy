# SPDX-License-Identifier: GPL-2.0-or-later
"""Four encounter families and fourteen allocated book demons.

Book by Josiah Alan-Lee; forms/bindings summarized, combat rules newly invented.
Source's critical actual-effect field is retained in summary alongside the rules.
No book artwork or apparatus drawing implementation is copied.
"""
import json
import struct
from pathlib import Path

SOURCE='https://github.com/JosiahAlanLee/Codex-Intervallorum/blob/b789e03f30034bc8403f8a40aaf83842885aaad5/books/03_escalationum/manuscript/catalogue.json'
BOSSES={
    'repetiel':{'name':'REPETIEL','class':5,'type':3003,'source_id':'01',
                'appearance':'A return tube carrying a mouth at both ends.',
                'binding':'Present the same intake identifier a second time.',
                'source_actual_effect':'Repeated diagnostics already recorded and delayed the work.',
                'game_rule':'On the ring, tap F, release it, and tap F again. The seal opens for eight seconds.',
                'attack':'An aimed shot followed by an echo along the original direction.'},
    'calmor':{'name':'CALMOR','class':6,'type':69,'source_id':'12',
              'appearance':'A muffled bell with a soft lining.',
              'binding':'Present an account from which urgency has been removed.',
              'source_actual_effect':'Rejected the request for its tone while leaving the technical evidence unread.',
              'game_rule':'Stand on the ring for two seconds without moving or firing. The seal opens for eight seconds.',
              'attack':'An aimed shot, or a three-shot bell burst while the player is firing.'},
    'probator':{'name':'PROBATOR','class':9,'flag':7,'type':67,'source_id':'16',
                'appearance':'A magnifying glass examining its own handle.',
                'binding':'Proof that the proposed act cannot cause another incident.',
                'source_actual_effect':'Demanded evidence available only after the repair, while withholding permission to repair.',
                'game_rule':'Hit its sealed shield to record proof. Then stand on the ring and tap F. The seal opens for eight seconds.',
                'attack':'One pair of closely spaced fireballs per attack cycle.'},
    'jurisiel':{'name':'JURISIEL','class':10,'flag':7,'type':68,'source_id':'34',
                'appearance':'A sideways doorway carried through another doorway.',
                'binding':'A scope statement signed by the owner whose identity remains disputed.',
                'source_actual_effect':'Passed the physical fault between service definitions until neither queue retained it.',
                'game_rule':'Enter the amber A ring, then cross into the cyan B ring. The seal opens for eight seconds.',
                'attack':'Two diverging shots framing a narrow passage.'},
}


def encounter(kind):
    """One isolated study using an already implemented combat family."""
    if kind not in BOSSES:raise ValueError('Unknown demon')
    return {'kind':kind,'archetype':kind,**BOSSES[kind],'source':SOURCE}


# These pairs are a game allocation, not the book's hierarchy. An office gives
# each tier its identity; its two encounters are handoffs touching that office.
# Forms currently share four combat/sprite families. Preserve that distinction
# rather than claiming fourteen independently implemented mechanics.
TIER_PAIRS=(
    ('repetiel','scriptorax'),
    ('calmor','redacth'),
    ('promissor','consenth'),
    ('jurisiel','margor'),
    ('absentiel','exceptor'),
    ('choraz','posthum'),
    ('probator','velaroth'),
)
ARCHETYPES={
    'repetiel':'repetiel','scriptorax':'probator',
    'calmor':'calmor','redacth':'jurisiel',
    'promissor':'repetiel','consenth':'jurisiel',
    'jurisiel':'jurisiel','margor':'repetiel',
    'absentiel':'probator','exceptor':'repetiel',
    'choraz':'calmor','posthum':'jurisiel',
    'probator':'probator','velaroth':'calmor',
}
CATALOGUE=json.loads(Path(__file__).with_name('demons.json').read_text())
OFFICES=tuple(CATALOGUE['offices'])
DEMONS={}
for handoff in CATALOGUE['handoffs']:
    key=handoff['name'].lower();archetype=ARCHETYPES[key]
    DEMONS[key]={**BOSSES[archetype],**{k:v for k,v in handoff.items() if k not in ('id','actual_effect')},
                 'kind':key,'archetype':archetype,'source_id':handoff['id'],
                 'source_office':handoff['source'],'target_office':handoff['target'],
                 'source_actual_effect':handoff['actual_effect'],'source':CATALOGUE['source']}


def tier_encounters(number):
    if type(number) is not int or not 1<=number<=len(TIER_PAIRS):
        raise ValueError('tier must be 1..7')
    return [dict(DEMONS[key]) for key in TIER_PAIRS[number-1]]


def is_boss_thing(thing):
    """The variant flag disambiguates Calmor from the Latchwing archetype."""
    flag=(thing[4]>>8)&7
    return any(thing[3]==b['type'] and flag==b.get('flag',b['class']) for b in BOSSES.values())


def metadata(floors):
    """Map-scoped identities and independent seal tags for native encounters.

    No remote state mutation: actors still spawn from ordinary map THINGS and
    bind through player actions. The engine matches by map, position and class.
    """
    records=[]
    for floor in floors:
        for b in floor.bosses:
            x,y=b['cell'];tag=b['seal_tag']
            records.append(struct.pack('<6h24s',floor.number,x*128+64,y*128+64,
                                       tag,tag+1 if b['class']==10 else 0,b['class'],
                                       b['name'].encode('ascii').ljust(24,b'\0')))
    return 'RBOSSES',struct.pack('<4sH',b'NRB1',len(records))+b''.join(records)
