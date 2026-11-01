# SPDX-License-Identifier: GPL-2.0-or-later
"""Reviewed Argon/DeepSeek sprite bank, cropped without changing its pixels."""
from functools import lru_cache
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent/'assets'/'argon'
KINDS = ['surveyor', 'wire_shambler', 'threshold_mimic', 'vore_spindle']


@lru_cache(maxsize=8)
def atlas(kind, variant):
    with Image.open(ROOT/f'{kind.upper()}_{variant}.png') as image:
        if image.size != (512, 768):
            raise ValueError('Argon atlas must contain four columns and six rows')
        return image.convert('RGBA')


def draw(kind, seed, frame):
    if kind in ('latchwing','relay_choir'):
        from rogue.threshold_assets import draw_creature
        return draw_creature(kind,seed,frame)
    index = KINDS.index(kind)
    variant = 'AB'[(int(seed)+index)&1]
    # The last two native slots retain the completed corpse.
    frame = min(max(int(frame), 0), 23)
    x, y = frame%4*128, frame//4*128
    return atlas(kind, variant).crop((x, y, x+128, y+128))
