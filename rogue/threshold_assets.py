# SPDX-License-Identifier: GPL-2.0-or-later
"""Native WAD adapters for the reviewed Threshold kit; originals stay intact."""
from functools import lru_cache
from pathlib import Path
import struct
import random
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]/'assets/threshold'
CREATURES=('latchwing','relay_choir')
PROPS={'service_lamp':(86,'TLP2'),'cable_shrine':(85,'TLMP'),'directory_sign':(2028,'COLU')}

@lru_cache(maxsize=8)
def picture(relative):
    with Image.open(ROOT/'art'/relative) as image:return image.convert('RGBA')

def draw_creature(kind,seed,frame):
    n=CREATURES.index(kind);variant='AB'[(int(seed)+n)&1]
    atlas=picture(f'creatures/{kind}_{variant}.png')
    if atlas.size!=(512,768):raise ValueError('Threshold creature atlas must be 512x768')
    frame=min(max(int(frame),0),23);x,y=frame%4*128,frame//4*128
    return atlas.crop((x,y,x+128,y+128))

def draw_prop(kind):return picture(f'props/{kind}.png').copy()

def palette_indices(image,palette):
    rgb=np.asarray(image.convert('RGB'),dtype=np.int32)
    unique,inverse=np.unique(rgb.reshape(-1,3),axis=0,return_inverse=True)
    nearest=((unique[:,None,:]-palette[None,:,:].astype(np.int32))**2).sum(2).argmin(1)
    return nearest[inverse].astype(np.uint8).tobytes()

def flat_lumps(palette,environment=None):
    result=[(f'NFLAT{i:02}',palette_indices(picture(f'flats/NFLAT{i:02}.png'),palette)) for i in range(1,5)]
    if environment:
        from rogue.environments import picture as environment_picture
        result.extend((f'EFLAT{i:02}',palette_indices(environment_picture(environment,'flats',i),palette)) for i in range(1,5))
    return result

def wall_lumps(assets,environment=None):
    from rogue.creatures import wad_lumps,patch
    lumps=dict(wad_lumps(assets))
    palette=np.frombuffer(lumps['PLAYPAL'][:768],dtype=np.uint8).reshape(256,3)
    images=[(f'NWALL{i:02}',picture(f'walls/NWALL{i:02}.png')) for i in range(1,7)]
    if environment:
        from rogue.environments import picture as environment_picture
        images.extend((f'EWALL{i:02}',environment_picture(environment,'walls',i)) for i in range(1,9))
    extra=len(images)
    pnames=lumps['PNAMES'];count=struct.unpack_from('<I',pnames)[0]
    if len(pnames)<4+8*count or count+extra>=32768:raise ValueError('Invalid source PNAMES')
    names=[name for name,_ in images]
    result=[(name,patch(image.convert('RGBA'),palette)) for name,image in images]
    result.append(('PNAMES',struct.pack('<I',count+extra)+pnames[4:4+8*count]+b''.join(name.encode().ljust(8,b'\0') for name in names)))
    textures=lumps['TEXTURE1'];n=struct.unpack_from('<I',textures)[0]
    offsets=list(struct.unpack_from('<'+'I'*n,textures,4))
    old_header=4+4*n
    if any(offset<old_header or offset>=len(textures) for offset in offsets):raise ValueError('Invalid source TEXTURE1')
    data=bytearray(textures[old_header:]);new_offsets=[offset+4*extra for offset in offsets]
    header=4+4*(n+extra)
    for k,name in enumerate(names):
        new_offsets.append(header+len(data))
        data.extend(struct.pack('<8sIHHIH',name.encode().ljust(8,b'\0'),0,128,128,0,1))
        data.extend(struct.pack('<5h',0,0,count+k,1,0))
    result.append(('TEXTURE1',struct.pack('<I',n+extra)+struct.pack('<'+'I'*(n+extra),*new_offsets)+data))
    return result

def opening_bosses(floor,seed,props):
    """Adapt the kit to the campaign without altering its authored geometry.

    The original eight encounters and prop coordinates stay intact. Bindings
    occupy free tiles on the authored route; no alcoves or sectors are carved.
    """
    from rogue.bosses import tier_encounters
    from rogue.inhabitants import options
    used={(t[0]//128,t[1]//128) for t in floor.things}|{cell for _,cell,_ in props}|{floor.start,floor.exit}
    rng=random.Random(seed^0xF0A501)
    route=floor.route
    def choose(index):
        candidates=[(abs(i-index),i,p) for i,p in enumerate(route) if p not in used
                    and floor.profiles[p]['height']>=128 and not floor.profiles[p].get('special')
                    and not floor.profiles[p].get('tag')
                    and abs(p[0]-floor.start[0])+abs(p[1]-floor.start[1])>=8]
        if not candidates:raise ValueError('No free opening encounter tile')
        _,i,p=min(candidates);used.add(p);return i,p
    floor.bosses=[]
    for index,b in enumerate(tier_encounters(floor.number)):
        at,cell=choose(len(route)//2 if index==0 else len(route)-6)
        _,ring=choose(at-4)
        tag=777+index*2
        floor.profiles[ring].update(tag=tag,light=255,flat='FLOOR4_6')
        b.update(cell=cell,binding_cell=ring,seal_tag=tag,intake=b['source_id'])
        floor.bosses.append(b)
        roll=rng.randrange(16);x,y=cell[0]*128+64,cell[1]*128+64
        floor.things.append((x,y,rng.randrange(4)*90,b['type'],options(b['archetype'],roll)))
        floor.variants.append({'kind':b['kind'],'roll':roll,'x':x,'y':y})
        nearby=sorted((p for p in floor.cells-used if abs(p[0]-ring[0])+abs(p[1]-ring[1])<=2
                       and not floor.profiles[p].get('special')),key=lambda p:(abs(p[0]-ring[0])+abs(p[1]-ring[1]),p))
        if len(nearby)<4:raise ValueError('No free opening encounter supplies')
        for p,kind in zip(nearby,[2049,2012,2049,2012]):
            used.add(p);floor.things.append((p[0]*128+64,p[1]*128+64,0,kind,7))
    floor.boss=floor.bosses[0]
    floor.architecture['campaign_encounters']='Two Foras handoffs added on free authored-route tiles; original kit encounters retained.'


def apply_identity(floors,seed):
    from rogue.threshold_opening import generate,PROPS as PLACEMENTS
    from rogue.maps import distances
    first=generate(seed)
    opening_bosses(first,seed,PLACEMENTS)
    first.architecture['props']=[]
    occupied={(t[0]//128,t[1]//128) for t in first.things}|{first.start,first.exit}
    for name,(x,y),angle in PLACEMENTS:
        source_cell=(x,y)
        if first.profiles[(x,y)]['height']<128:
            candidates=[p for p in first.cells if p not in occupied and p not in first.route
                        and first.profiles[p]['height']>=128
                        and all(q in first.cells for q in ((p[0]-1,p[1]),(p[0]+1,p[1]),(p[0],p[1]-1),(p[0],p[1]+1)))]
            if not candidates:continue
            x,y=min(candidates,key=lambda p:(abs(p[0]-x)+abs(p[1]-y),p))
        occupied.add((x,y))
        type_id,_=PROPS[name]
        first.things.append((x*128+64,y*128+64,angle,type_id,7))
        first.architecture['props'].append({'name':name,'cell':[x,y],'source_cell':list(source_cell),'type':type_id,'solid':True})
    # Codex adaptation: make the authored optional cache an actual native secret.
    first.profiles[(31,10)]['special']=9
    first.architecture['secret_design']='Optional pump-hall cache; its first inner tile is native secret sector 9.'
    first.architecture['identity']='Threshold / reviewed DeepSeek kit with native Codex adapters'
    floors=[first,*floors[1:]]
    for f in floors[1:]:
        f.architecture['identity']='threshold'
        wall=f'NWALL{min(f.number,6):02}'
        flat='NFLAT02' if f.number%2==0 else 'NFLAT01'
        ceiling='NFLAT04' if f.number%2==0 else 'NFLAT03'
        f.theme=(f.theme[0],wall,flat,ceiling,f.theme[4])
        for profile in f.profiles.values():
            profile.update(wall=wall,flat=flat,ceiling=ceiling)
        occupied={(t[0]//128,t[1]//128) for t in f.things}
        for boss in f.bosses:
            occupied.add(tuple(boss['binding_cell']))
            if 'secondary_cell' in boss:occupied.add(tuple(boss['secondary_cell']))
        candidates=[p for p in sorted(f.cells) if p not in occupied and p not in f.route
                    and f.profiles.get(p,{}).get('height',0)>=160 and not f.profiles.get(p,{}).get('tag')
                    and abs(p[0]-f.start[0])+abs(p[1]-f.start[1])>=3]
        f.architecture['props']=[]
        for name in PROPS:
            if not candidates:break
            # A prop can close an off-route branch or surround a free tile.
            # Check accumulated solid placements, not just the authored route.
            blocked={tuple(p['cell']) for p in f.architecture['props']}
            middle=len(candidates)//2
            for at in sorted(range(len(candidates)),key=lambda i:(abs(i-middle),i)):
                cell=candidates[at];remaining=f.cells-blocked-{cell}
                if len(distances(remaining,f.start))==len(remaining):break
            else:continue
            x,y=candidates.pop(at);type_id,_=PROPS[name]
            f.things.append((x*128+64,y*128+64,0,type_id,7))
            f.architecture['props'].append({'name':name,'cell':[x,y],'type':type_id,'solid':True})
    return floors
