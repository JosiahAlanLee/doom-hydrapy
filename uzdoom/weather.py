# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in native cistern mist; unrelated floors and the default build stay dry."""
import math
from PIL import Image

PRESETS=('off','cistern')


def configure(m,world,preset,seed):
    if preset not in PRESETS:raise ValueError('Unknown weather preset')
    if preset=='off' or not world or world['id']!='flooded-resonance-cistern':return None
    # Open geometry precedes the dry service annex and exit stair sectors.
    count=world['geometry_sectors']
    if not 0<count<=len(m.sectors):raise ValueError('Invalid weather sector range')
    return dict(preset='cistern',density=112,visibility=384,colour=[44,50,56],
                sectors=list(range(count)),seed=(seed ^ (m.number*2654435761))&0xffffffff,
                emission_interval=3,particles_per_emission=2,lifetime=105,live_particle_bound=70)


def lump(profile):
    return ('%d %d %d\n%s\n%s\n'%(profile['density'],profile['visibility'],profile['seed'],
            ' '.join(map(str,profile['colour'])),' '.join(map(str,profile['sectors'])))).encode()


def mist_texture():
    image=Image.new('RGBA',(64,64))
    for y in range(64):
        for x in range(64):
            r=math.hypot((x-31.5)/31.5,(y-31.5)/31.5)
            alpha=round(255*max(0,1-r)**2)
            image.putpixel((x,y),(208,220,228,alpha))
    return image
