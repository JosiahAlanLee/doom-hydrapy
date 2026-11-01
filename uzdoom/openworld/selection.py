# SPDX-License-Identifier: GPL-3.0-or-later
"""Reproducible shuffled floors with explicit, caller-owned opener history."""
import random

# These are the independently reviewed structural variants supplied with the
# geometry bank. A run still shuffles distinct architectures, starts, boss
# pairings and score/art seeds; unverified arbitrary geometry stays out of play.
VARIANTS=(17,73,211)


def choose(seed,identities,recent=(),floors=7):
    pool=tuple(dict.fromkeys(identities))
    if not pool or not 1<=floors<=7:raise ValueError('Invalid floor pool')
    rng=random.Random(seed);last=recent[-1] if recent else None
    bag=[];result=[]
    for number in range(1,floors+1):
        if not bag:bag=list(pool);rng.shuffle(bag)
        # History contains previous opening archetypes, not the last floor of
        # the last run. First prefer an opener absent from the recent window.
        choices=[p for p in bag if p!=last]
        if number==1:
            fresh=[p for p in choices if p not in recent]
            if fresh:choices=fresh
        if not choices:choices=list(bag)
        identity=choices[0];bag.remove(identity)
        result.append(dict(floor=number,archetype=identity,seed=rng.choice(VARIANTS)))
        last=identity
    return result
