# SPDX-License-Identifier: GPL-2.0-or-later
"""Original game adaptations of two demons from Pseudomonarchia Escalationum.

Book by Josiah Alan-Lee; forms/bindings summarized, combat rules newly invented.
Source's critical actual-effect field is retained in summary alongside the rules.
No book artwork or apparatus drawing implementation is copied.
"""
import random

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
}


def encounter(seed,floor):
    order=list(BOSSES)
    random.Random(seed^0xD3A0B055).shuffle(order)
    if floor not in [3,5]:return None
    key=order[[3,5].index(floor)]
    return {'kind':key,**BOSSES[key],'source':SOURCE}
