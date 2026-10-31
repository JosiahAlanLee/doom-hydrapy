# SPDX-License-Identifier: GPL-2.0-or-later
"""Native WAD adapters for the reviewed Threshold kit; originals stay intact."""
from functools import lru_cache
from pathlib import Path
import struct
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

def flat_lumps(palette):
    return [(f'NFLAT{i:02}',palette_indices(picture(f'flats/NFLAT{i:02}.png'),palette)) for i in range(1,5)]

def wall_lumps(assets):
    from rogue.creatures import wad_lumps,patch
    lumps=dict(wad_lumps(assets))
    palette=np.frombuffer(lumps['PLAYPAL'][:768],dtype=np.uint8).reshape(256,3)
    pnames=lumps['PNAMES'];count=struct.unpack_from('<I',pnames)[0]
    if len(pnames)<4+8*count or count+6>=32768:raise ValueError('Invalid source PNAMES')
    names=[f'NWALL{i:02}' for i in range(1,7)]
    result=[(name,patch(picture(f'walls/{name}.png'),palette)) for name in names]
    result.append(('PNAMES',struct.pack('<I',count+6)+pnames[4:4+8*count]+b''.join(name.encode().ljust(8,b'\0') for name in names)))
    textures=lumps['TEXTURE1'];n=struct.unpack_from('<I',textures)[0]
    offsets=list(struct.unpack_from('<'+'I'*n,textures,4))
    old_header=4+4*n
    if any(offset<old_header or offset>=len(textures) for offset in offsets):raise ValueError('Invalid source TEXTURE1')
    data=bytearray(textures[old_header:]);new_offsets=[offset+24 for offset in offsets]
    header=4+4*(n+6)
    for k,name in enumerate(names):
        new_offsets.append(header+len(data))
        data.extend(struct.pack('<8sIHHIH',name.encode().ljust(8,b'\0'),0,128,128,0,1))
        data.extend(struct.pack('<5h',0,0,count+k,1,0))
    result.append(('TEXTURE1',struct.pack('<I',n+6)+struct.pack('<'+'I'*(n+6),*new_offsets)+data))
    return result

def apply_identity(floors,seed):
    from rogue.threshold_opening import generate,PROPS as PLACEMENTS
    first=generate(seed)
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
        if f.boss:occupied.add(tuple(f.boss['binding_cell']))
        candidates=[p for p in sorted(f.cells) if p not in occupied and p not in f.route
                    and f.profiles.get(p,{}).get('height',0)>=160 and not f.profiles.get(p,{}).get('tag')
                    and abs(p[0]-f.start[0])+abs(p[1]-f.start[1])>=3]
        f.architecture['props']=[]
        for name in PROPS:
            if not candidates:break
            x,y=candidates.pop(len(candidates)//2);type_id,_=PROPS[name]
            f.things.append((x*128+64,y*128+64,0,type_id,7))
            f.architecture['props'].append({'name':name,'cell':[x,y],'type':type_id,'solid':True})
    return floors
