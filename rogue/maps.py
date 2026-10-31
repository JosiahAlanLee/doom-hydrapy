# SPDX-License-Identifier: GPL-2.0-or-later
"""Original grid BSP/PWAD writer. No external node builder or borrowed maps.

Every tile is a convex subsector. Closed tiles have zero headroom; shared
two-sided lines make the open tiles ordinary Doom rooms and corridors. A balanced
axis BSP uses the same boundaries, so no segment splitting is needed. Keep the
map small enough for vanilla Doom's signed-short coordinates and block offsets.
"""
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
import argparse
import hashlib
import json
import math
import random
import struct
from rogue.bosses import BOSSES, OFFICES, tier_encounters, is_boss_thing
from rogue.inhabitants import CREATURES, NEW_CREATURES, options

TILE = 128
FLOORS = 7
SIZE = 33
ENEMY_TYPES={3004,3001,3002,9,3005}|{b['type'] for b in (CREATURES|BOSSES).values()}
THEMES = [
    ('RELAY / 01', 'STARTAN3', 'FLOOR4_8', 'CEIL3_5', 192),
    ('OXIDE / 02', 'BROWN1', 'FLOOR0_1', 'CEIL3_5', 160),
    ('STATIC / 03', 'STONE2', 'FLAT5_4', 'CEIL5_1', 176),
    ('FOUNDRY / 04', 'METAL2', 'FLOOR4_8', 'CEIL5_1', 144),
    ('NULL / 05', 'STONE3', 'FLAT5_4', 'CEIL3_5', 128),
    ('BRIDGE / 06', 'METAL2', 'FLOOR0_1', 'CEIL5_1', 128),
    ('ABYSS / 07', 'STONE3', 'FLAT5_4', 'CEIL5_1', 112),
]


@dataclass
class Floor:
    number: int
    cells: set
    rooms: list
    start: tuple
    exit: tuple
    route: list
    things: list
    theme: tuple
    architecture: dict = field(default_factory=dict)
    profiles: dict = field(default_factory=dict)
    variants: list = field(default_factory=list)
    boss: dict | None = None
    bosses: list = field(default_factory=list)


def distances(cells, start):
    parent = {start: None}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for p in [(x+1,y),(x-1,y),(x,y+1),(x,y-1)]:
            if p in cells and p not in parent:
                parent[p] = (x, y)
                queue.append(p)
    return parent


def generate(seed, number, boss_kind=None):
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 0xffffffff:
        raise ValueError('seed must be an unsigned 32-bit integer')
    if type(number) is not int or not 1 <= number <= FLOORS:
        raise ValueError('floor must be 1..7')
    rng = random.Random((seed << 8) | number)
    cells, rooms, shapes = set(), [], []
    profiles = {}
    for attempt in range(400):
        w, h = rng.randint(5, 9), rng.randint(5, 9)
        x, y = rng.randint(1, SIZE-w-1), rng.randint(1, SIZE-h-1)
        if any(x-1 < a+c and x+w+1 > a and y-1 < b+d and y+h+1 > b for a,b,c,d in rooms):
            continue
        index=len(rooms)
        shape=['nave','ring','ribs','cross','terrace','cloister'][index%6]
        room={(a,b) for a in range(x,x+w) for b in range(y,y+h)}
        cx,cy=x+w//2,y+h//2
        if shape=='ring':
            room-={(a,b) for a in range(cx-1,cx+2) for b in range(cy-1,cy+2)}
        elif shape in ['ribs','cloister','nave']:
            # Paired piers frame a clear central nave. They are solid geometry.
            for a in range(x+1,x+w-1,2):
                for b in [y+1,y+h-2]:
                    if abs(b-cy)>0:room.discard((a,b))
        elif shape=='cross':
            room={p for p in room if abs(p[0]-cx)<=1 or abs(p[1]-cy)<=1}
        rooms.append((x,y,w,h));shapes.append(shape)
        cells.update(room)
        for p in sorted(room):
            profiles[p]={'floor':0,'height':rng.choice([384,512,640]) if shape!='cross' else 192,
                         'light':{'ring':160,'ribs':160,'nave':192,'cross':144,'terrace':192,'cloister':176}[shape],
                         'wall':rng.choice([THEMES[number-1][1], 'METAL2']),
                         'flat':THEMES[number-1][2], 'ceiling':THEMES[number-1][3], 'shape':shape}
        if len(rooms) >= 7 + number:
            break
    if len(rooms) < 3:
        raise RuntimeError('insufficient rooms')
    # Connect the nearest unconnected room to the existing tree; add two cycles.
    centres = []
    for x,y,w,h in rooms:
        candidates=[p for p in sorted(cells) if x<=p[0]<x+w and y<=p[1]<y+h]
        centres.append(min(candidates,key=lambda p:(abs(p[0]-(x+w//2))+abs(p[1]-(y+h//2)),p)))
    joined = {0}
    edges = []
    while len(joined) < len(rooms):
        _, a, b = min((abs(centres[a][0]-centres[b][0])+abs(centres[a][1]-centres[b][1]),a,b)
                      for a in sorted(joined) for b in range(len(rooms)) if b not in joined)
        joined.add(b)
        edges.append((a,b))
    for _ in range(2):
        edges.append(tuple(rng.sample(range(len(rooms)),2)))
    for a,b in edges:
        x,y = centres[a]; xx,yy = centres[b]
        if rng.randrange(2):
            cells.update((i,y) for i in range(min(x,xx),max(x,xx)+1))
            cells.update((xx,j) for j in range(min(y,yy),max(y,yy)+1))
        else:
            cells.update((x,j) for j in range(min(y,yy),max(y,yy)+1))
            cells.update((i,yy) for i in range(min(x,xx),max(x,xx)+1))
    start = centres[0]
    # Room construction and connecting passages can cut through a pier. The
    # final cell set, not the earlier room mask, is authoritative.
    for p in sorted(cells):
        if p not in profiles:
            profiles[p]={'floor':0,'height':112,'light':128,'wall':'METAL2',
                         'flat':THEMES[number-1][2],'ceiling':THEMES[number-1][3],'shape':'passage'}
    boundary=[p for p in sorted(cells) if any(q not in cells for q in [(p[0]+1,p[1]),(p[0]-1,p[1]),(p[0],p[1]+1),(p[0],p[1]-1)])]
    depths={p:0 for p in boundary};queue=deque(boundary)
    while queue:
        p=queue.popleft()
        for q in [(p[0]+1,p[1]),(p[0]-1,p[1]),(p[0],p[1]+1),(p[0],p[1]-1)]:
            if q in cells and q not in depths:depths[q]=depths[p]+1;queue.append(q)
    for p in sorted(cells):
        profile=profiles[p]
        if profile['shape'] in ['terrace','ring','cloister']:profile['floor']=16*min(depths[p],3)
        # Quantized room heights keep Doom's visplane budget predictable.
        room=next((r for r in rooms if r[0]<=p[0]<r[0]+r[2] and r[1]<=p[1]<r[1]+r[3]),None)
        if room and profile['shape']!='passage':
            index=rooms.index(room);profile['height']=[512,640,384,192,384,512][index%6]
    # Enforce walkable rises on EVERY edge, including carved connections.
    changed=True
    while changed:
        changed=False
        for p in sorted(cells):
            for q in [(p[0]+1,p[1]),(p[0]-1,p[1]),(p[0],p[1]+1),(p[0],p[1]-1)]:
                if q in cells and profiles[p]['floor']>profiles[q]['floor']+16:
                    profiles[p]['floor']=profiles[q]['floor']+16;changed=True
    parents = distances(cells,start)
    assert len(parents) == len(cells)
    # BFS insertion order is deterministic; the last point is a furthest tile.
    exit_cell = list(parents)[-1]
    route = [exit_cell]
    while route[-1] != start:
        route.append(parents[route[-1]])
    route.reverse()
    from rogue.bosses import encounter
    bosses=([encounter(boss_kind)] if boss_kind else tier_encounters(number))
    reserved=set()
    for index,boss in enumerate(bosses):
        # Two separated encounters along the descent. Bindings belong to one
        # actor each, even when both actors share the same combat family.
        position=len(route)-5 if len(bosses)==1 or index else max(8,len(route)//2-3)
        boss_cell=route[position];anchor=route[position-4];binding_cell=anchor
        # Prefer a two-cell, L-shaped side alcove. Its walls give the player
        # cover while performing the binding, especially Calmor's stillness.
        found=False
        for dx,dy in [(1,0),(0,1),(-1,0),(0,-1)]:
            a=(anchor[0]+dx,anchor[1]+dy)
            for px,py in [(-dy,dx),(dy,-dx)]:
                b=(a[0]+px,a[1]+py)
                if any(not(1<=p[0]<SIZE-1 and 1<=p[1]<SIZE-1) for p in [a,b]):continue
                neighbors=lambda p:{(p[0]+1,p[1]),(p[0]-1,p[1]),(p[0],p[1]+1),(p[0],p[1]-1)}
                if a in cells or b in cells or (neighbors(a)&cells)!={anchor} or neighbors(b)&cells:continue
                for p in [a,b]:profiles[p]={**profiles[anchor],'height':112,'shape':'binding-alcove','light':224}
                cells.update([a,b]);binding_cell=b;found=True;break
            if found:break
        tag=777+index*2
        profiles[binding_cell]={**profiles[binding_cell],'tag':tag,'light':255,'flat':'FLOOR4_6'}
        boss={**boss,'cell':boss_cell,'binding_cell':binding_cell,'intake':boss['source_id'],
              'seal_tag':tag,'archetype':boss.get('archetype',boss['kind'])}
        if boss['class']==10:
            secondary_cell=a if found else route[position-3]
            profiles[secondary_cell]={**profiles[secondary_cell],'tag':tag+1,'light':255,'flat':'FLOOR4_6'}
            boss['secondary_cell']=secondary_cell
        bosses[index]=boss
        reserved|={p for p in cells if min(abs(p[0]-boss_cell[0])+abs(p[1]-boss_cell[1]),
                                         abs(p[0]-binding_cell[0])+abs(p[1]-binding_cell[1]))<=2}
    occupied = {start, exit_cell}|reserved
    things = []
    def item(cell, kind, angle=0):
        if cell in occupied:
            return False
        occupied.add(cell)
        things.append((cell[0]*TILE+TILE//2,cell[1]*TILE+TILE//2,angle,kind,7))
        return True
    # Pistol start; first room has a shotgun, shells and health. Never spawn
    # monsters within six tiles' Manhattan distance of the starting point.
    start_room = [(x,y) for x in range(rooms[0][0],rooms[0][0]+rooms[0][2])
                  for y in range(rooms[0][1],rooms[0][1]+rooms[0][3]) if (x,y)!=start and (x,y) in cells]
    rng.shuffle(start_room)
    for kind in [2001,2008,2008,2011]:
        item(start_room.pop(),kind)
    candidates = sorted(cells - occupied)
    rng.shuffle(candidates)
    distant = [p for p in candidates if abs(p[0]-start[0])+abs(p[1]-start[1]) >= 6
               and abs(p[0]-exit_cell[0])+abs(p[1]-exit_cell[1]) >= 2]
    enemy_kinds = [3004,3004,3001,3001] + ([3002] if number >= 2 else [])
    if number >= 4:
        enemy_kinds += [3005]
    # Put the new creatures on the actual route, with a safe start and spacing.
    schedule=[['surveyor','wire_shambler'],['threshold_mimic','vore_spindle'],
              ['surveyor','threshold_mimic'],['wire_shambler','vore_spindle'],
              list(NEW_CREATURES),list(NEW_CREATURES),list(NEW_CREATURES)][number-1]
    new_cells=[];distant_set=set(distant)
    for name in schedule:
        choices=[p for p in route if p in distant_set and p not in occupied
                 and all(abs(p[0]-q[0])+abs(p[1]-q[1])>=3 for q in new_cells)]
        if not choices:
            choices=[p for p in distant if p not in occupied]
        if choices:
            p=choices[0]
            if item(p,NEW_CREATURES[name]['type'],rng.randrange(4)*90):new_cells.append(p)
    legacy=[p for p in distant if p not in occupied]
    for p in legacy[:max(0,5+number*3-len(new_cells))]:
        item(p,rng.choice(enemy_kinds),rng.randrange(4)*90)
    # Sparse Gloamwood encounters; keep the start, exits and boss alcoves clear.
    for name in ['hollow']+(['redead'] if number>=2 else []):
        for p in distant:
            if p not in occupied and abs(p[0]-start[0])+abs(p[1]-start[1])>=10:
                if item(p,CREATURES[name]['type'],rng.randrange(4)*90):break
    variants=[]
    classes={3004:(1,'skitter'),3002:(2,'bastion'),3001:(3,'cantor'),3005:(4,'shiver'),66:(7,'hollow'),65:(7,'redead'),
             **{b['type']:(7,name) for name,b in NEW_CREATURES.items()}}
    for i,t in enumerate(things):
        if t[3] in classes:
            variant,name=classes[t[3]];roll=rng.randrange(16)
            things[i]=(*t[:4],t[4]|(variant<<8)|(roll<<11))
            variants.append({'kind':name,'roll':roll,'x':t[0],'y':t[1]})
    remaining = [p for p in candidates if p not in occupied]
    for i,p in enumerate(remaining[:12+number]):
        item(p,[2007,2008,2011,2012,2018,2048][i%6])
    if number >= 2:
        for p in remaining[12+number:]:
            if item(p,2002):
                break
    for boss in bosses:
        p=boss['cell'];variant=boss['class'];roll=rng.randrange(16)
        things.append((p[0]*TILE+64,p[1]*TILE+64,rng.randrange(4)*90,boss['type'],options(boss['archetype'],roll)))
        variants.append({'kind':boss['kind'],'roll':roll,'x':p[0]*TILE+64,'y':p[1]*TILE+64})
        # Supply the fight without requiring a lucky weapon/ammo roll.
        used={tuple(b['cell']) for b in bosses}|{tuple(b['binding_cell']) for b in bosses}|{start,exit_cell}
        used|={tuple(b['secondary_cell']) for b in bosses if 'secondary_cell' in b}
        used|={(t[0]//TILE,t[1]//TILE) for t in things}
        nearby=sorted((p for p in reserved-used if abs(p[0]-boss['cell'][0])+abs(p[1]-boss['cell'][1])<=2),
                      key=lambda p:(abs(p[0]-boss['cell'][0])+abs(p[1]-boss['cell'][1]),p))
        for p in nearby[:3]:
            things.append((p[0]*TILE+64,p[1]*TILE+64,0,2049 if len(things)%2 else 2012,7))
            occupied.add(p)
    direction = route[1][0]-start[0], route[1][1]-start[1]
    angle = {(1,0):0,(0,1):90,(-1,0):180,(0,-1):270}[direction]
    things.insert(0,(start[0]*TILE+64,start[1]*TILE+64,angle,1,7))
    return Floor(number,cells,rooms,start,exit_cell,route,things,THEMES[number-1],
                 {'rooms':[{'shape':s,'bounds':r} for r,s in zip(rooms,shapes)],'max_step':16},profiles,variants,bosses[0],bosses)


def name8(s):
    return s.encode('ascii').ljust(8,b'\0')


def map_lumps(floor,custom_seals=False):
    n = SIZE
    wall, flat, ceiling, light = floor.theme[1:]
    vertices = [(x*TILE,y*TILE) for y in range(n+1) for x in range(n+1)]
    vindex = lambda x,y: y*(n+1)+x
    sindex = lambda x,y: y*n+x
    sides, lines = [], []
    cell_segs = [[] for _ in range(n*n)]
    def edge(a,b,front,back):
        if front is None:
            a,b,front,back=b,a,back,front
        side_ids = []
        for cell in [front,back]:
            if cell is None:
                side_ids.append(65535)
                continue
            side_ids.append(len(sides))
            # A closed cell's facing wall uses the neighboring room's material.
            material=floor.profiles.get(cell,{}).get('wall',wall)
            sides.append(struct.pack('<hh8s8s8sH',0,0,name8(material),name8(material),name8(material if back is None else '-'),sindex(*cell)))
        idx = len(lines)
        is_exit = floor.exit in [front,back] and front in floor.cells and back in floor.cells
        flags = 4 if back is not None else 1
        lines.append((vindex(*a),vindex(*b),flags,52 if is_exit else 0,0,*side_ids))
        for cell,reverse in [(front,0),(back,1)]:
            if cell is not None:
                x1,y1 = vertices[vindex(*(b if reverse else a))]
                x2,y2 = vertices[vindex(*(a if reverse else b))]
                angle = round(math.atan2(y2-y1,x2-x1)*65536/(2*math.pi)) & 65535
                cell_segs[sindex(*cell)].append((vindex(*(b if reverse else a)),vindex(*(a if reverse else b)),angle,idx,reverse,0))
    for y in range(n+1):
        for x in range(n):
            edge((x,y),(x+1,y),(x,y-1) if y else None,(x,y) if y<n else None)
    for x in range(n+1):
        for y in range(n):
            edge((x,y),(x,y+1),(x,y) if x<n else None,(x-1,y) if x else None)
    segs, subsectors = [], []
    for group in cell_segs:
        subsectors.append(struct.pack('<HH',len(group),len(segs)))
        segs.extend(struct.pack('<6H',*s) for s in group)
    nodes = []
    def bbox(rect):
        x0,y0,x1,y1=rect
        return (y1*TILE,y0*TILE,x0*TILE,x1*TILE)
    def node(rect):
        x0,y0,x1,y1=rect
        if x1-x0==y1-y0==1:
            return 0x8000 | sindex(x0,y0)
        if x1-x0 >= y1-y0:
            mid=(x0+x1)//2
            a,b=(mid,y0,x1,y1),(x0,y0,mid,y1)
            partition=(mid*TILE,y0*TILE,0,(y1-y0)*TILE)
        else:
            mid=(y0+y1)//2
            a,b=(x0,y0,x1,mid),(x0,mid,x1,y1)
            partition=(x0*TILE,mid*TILE,(x1-x0)*TILE,0)
        ca,cb=node(a),node(b)
        index=len(nodes)
        nodes.append(struct.pack('<12h2H',*partition,*bbox(a),*bbox(b),ca,cb))
        return index
    node((0,0,n,n))
    sectors=[]
    for y in range(n):
        for x in range(n):
            opened=(x,y) in floor.cells
            exit_tile=(x,y)==floor.exit
            profile=floor.profiles.get((x,y),{})
            z=profile.get('floor',0)
            tile_flat=profile.get('flat',flat)
            tile_ceiling=profile.get('ceiling',ceiling)
            if not custom_seals:
                if tile_flat=='RARCHFL':tile_flat=flat
                if tile_ceiling=='RARCHCL':tile_ceiling=ceiling
            if custom_seals:
                for boss in floor.bosses:
                    if (x,y)==tuple(boss['binding_cell']):tile_flat='RSEAL'+str(boss['class'])
                    if (x,y)==tuple(boss.get('secondary_cell',(-1,-1))):tile_flat='RSEAL10B'
            sectors.append(struct.pack('<hh8s8shhh',z,z+profile.get('height',128+32*(floor.number%2)) if opened else z,
                                       name8(('NFLAT04' if floor.architecture.get('identity') else 'FLOOR0_1') if exit_tile else tile_flat),name8(tile_ceiling),
                                       255 if exit_tile else profile.get('light',light),profile.get('special',0),profile.get('tag',0)))
    # BLOCKMAP: add each line to both sides of a block boundary, including
    # endpoints. Offsets are 16-bit WORD indices, not byte offsets.
    dim=n+2; origin=-TILE; blocks=[set() for _ in range(dim*dim)]
    for i,line in enumerate(lines):
        (x1,y1),(x2,y2)=vertices[line[0]],vertices[line[1]]
        lo_x=max(0,math.floor((min(x1,x2)-origin-.01)/TILE))
        hi_x=min(dim-1,math.floor((max(x1,x2)-origin+.01)/TILE))
        lo_y=max(0,math.floor((min(y1,y2)-origin-.01)/TILE))
        hi_y=min(dim-1,math.floor((max(y1,y2)-origin+.01)/TILE))
        for y in range(lo_y,hi_y+1):
            for x in range(lo_x,hi_x+1):blocks[y*dim+x].add(i)
    offsets=[]; entries=[]
    for block in blocks:
        offsets.append(4+dim*dim+len(entries))
        entries += [0]+sorted(block)+[65535]
    assert max(offsets)<65536
    blockmap=struct.pack('<hhHH',origin,origin,dim,dim)+struct.pack('<'+'H'*(len(offsets)+len(entries)),*(offsets+entries))
    return [
        (f'MAP{floor.number:02}',b''),
        ('THINGS',b''.join(struct.pack('<5h',*t) for t in floor.things)),
        ('LINEDEFS',b''.join(struct.pack('<7H',*l) for l in lines)),
        ('SIDEDEFS',b''.join(sides)),
        ('VERTEXES',b''.join(struct.pack('<hh',*v) for v in vertices)),
        ('SEGS',b''.join(segs)),('SSECTORS',b''.join(subsectors)),('NODES',b''.join(nodes)),
        ('SECTORS',b''.join(sectors)),('REJECT',bytes((n*n*n*n+7)//8)),('BLOCKMAP',blockmap),
    ]


def creature_study(seed,kind):
    if kind not in CREATURES:raise ValueError('Unknown creature study')
    if isinstance(seed,bool) or not isinstance(seed,int) or not 0<=seed<=0xffffffff:
        raise ValueError('seed must be an unsigned 32-bit integer')
    cells={(x,y) for x in range(1,13) for y in range(1,8)}-{(6,5),(6,6),(7,5),(7,6)}
    start,exit_cell=(3,3),(11,6)
    profiles={p:{'floor':0,'height':192,'light':208,'wall':'STONE2',
                 'flat':'FLAT5_4','ceiling':'CEIL5_1','shape':'gloam-gallery'} for p in cells}
    parent=distances(cells,start);route=[exit_cell]
    while route[-1]!=start:route.append(parent[route[-1]])
    route.reverse()
    b=CREATURES[kind];x,y=448,448;mx,my=(1088,448) if kind=='hollow' else (960,448)
    things=[(x,y,0,1,7),(mx,my,180,b['type'],options(kind,seed%16)),
            (x,y,0,2001,7),(x,y,0,2049,7),(x,y,0,2049,7),(x,y,0,2018,7),
            (320,832,0,2012,7)]
    return Floor(1,cells,[(1,1,12,7)],start,exit_cell,route,things,
                 ('STUDY / '+b['name'],*THEMES[2][1:]),
                 {'rooms':[{'shape':'gloam-gallery','bounds':(1,1,12,7)}],'max_step':0},
                 profiles,[{'kind':kind,'roll':seed%16,'x':mx,'y':my}])


def campaign(seed, output, assets=None, practice=None, identity=False, vending=False):
    from rogue.architecture import STUDIES,study,metadata,flats
    from rogue.strobe import STROBES,study as strobe_study,metadata as strobe_metadata
    output=Path(output)
    floors=[]
    if practice:
        if practice in STROBES:f=strobe_study(seed)
        elif practice in STUDIES:f=study(seed,practice)
        elif practice in CREATURES:f=creature_study(seed,practice)
        elif practice in BOSSES:f=generate(seed,3,boss_kind=practice)
        else:raise ValueError('Unknown encounter study')
    if practice in BOSSES:
        f.number=1;f.start=tuple(f.boss['binding_cell'])
        parents=distances(f.cells,f.start);f.route=[f.exit]
        while f.route[-1]!=f.start:f.route.append(parents[f.route[-1]])
        f.route.reverse()
        f.theme=('STUDY / '+f.boss['name'],*f.theme[1:])
        a=f.route[1];dx,dy=a[0]-f.start[0],a[1]-f.start[1]
        angle={(1,0):0,(0,1):90,(-1,0):180,(0,-1):270}[dx,dy]
        x,y=f.start[0]*TILE+64,f.start[1]*TILE+64
        # Isolate the boss instead of importing a floor's ordinary encounters
        # into a supposed practice fight. Campaign encounters are unchanged.
        f.things=[(x,y,angle,1,7)]+[t for t in f.things if t[3]!=1 and
                 (t[3] not in ENEMY_TYPES or (is_boss_thing(t) and t[3]==f.boss['type']))]+[(x,y,0,2001,7),(x,y,0,2049,7),(x,y,0,2049,7),(x,y,0,2019,7)]
        f.variants=[v for v in f.variants if v['kind']==practice]
    if practice:floors=[f]
    else:floors=[generate(seed,i) for i in range(1,FLOORS+1)]
    environment=None
    if identity and not practice:
        if not assets:raise ValueError('Threshold identity requires the supplied Freedoom assets')
        from rogue.threshold_assets import apply_identity
        floors=apply_identity(floors,seed)
        from rogue.environments import apply as apply_environment
        environment=apply_environment(floors,seed)
    use_vending = bool(vending and identity and not practice)
    if use_vending:
        from rogue.vending import place
        place(floors, seed)
    lumps=[lump for f in floors for lump in map_lumps(f,custom_seals=bool(assets))]
    if use_vending:
        from rogue.vending import metadata as vending_metadata
        lumps.append(vending_metadata(floors, seed))
    from rogue.bosses import metadata as boss_metadata
    lumps.append(boss_metadata(floors))
    if practice in STUDIES:lumps.append(metadata(floors[0]))
    if practice in STROBES:lumps.append(strobe_metadata(floors[0]))
    if assets:
        from rogue.creatures import sprite_lumps, FAMILIES
        bank=sprite_lumps(assets,seed,environment)
        if use_vending:
            from rogue.vending import sprite_lumps as vending_sprites
            at=next(i for i,(name,_) in enumerate(bank) if name=='S_END')
            bank[at:at]=vending_sprites(assets)
        if practice in STUDIES:
            at=next(i for i,(name,_) in enumerate(bank) if name=='F_END')
            bank[at:at]=flats(assets)
        lumps.extend(bank)
        if identity and not practice:
            from rogue.threshold_assets import wall_lumps
            lumps.extend(wall_lumps(assets,environment))
    data=bytearray(); directory=[]
    for name,payload in lumps:
        directory.append(struct.pack('<II8s',12+len(data),len(payload),name8(name)))
        data.extend(payload)
    wad=struct.pack('<4sII',b'PWAD',len(lumps),12+len(data))+data+b''.join(directory)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(wad)
    manifest={'format':'doom-rogue-7','seed':seed,'mode':practice or 'campaign',
              'identity':'threshold' if identity and not practice else 'classic',
              'floors':[], 'sha256':hashlib.sha256(wad).hexdigest()}
    if environment:
        from rogue.environments import describe
        manifest['environment']=describe(environment)
    if assets:
        manifest['sprite_assets']={'sha256':hashlib.sha256(Path(assets).read_bytes()).hexdigest(),
                                   'source':'Freedoom IWAD supplied by the operator',
                                   'generated_families':list(FAMILIES),
                                   'other_sprites':'Freedoom originals; retain Freedoom license and credits'}
    for f in floors:
        manifest['floors'].append({'number':f.number,'name':f.theme[0],'rooms':len(f.rooms),
                                  'open_tiles':len(f.cells),'start':f.start,'exit':f.exit,
                                  'route':f.route,'monsters':sum(t[3] in ENEMY_TYPES for t in f.things),
                                  'architecture':f.architecture,'variants':f.variants,
                                  'boss':f.boss,
                                  'bosses':f.bosses,'office':None if practice else OFFICES[f.number-1],
                                  'cells':sorted(f.cells)})
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,default=20261030)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--assets',type=Path,help='Freedoom IWAD for the complete generated-creature sprite namespace')
    args=parser.parse_args()
    manifest=campaign(args.seed,args.out,assets=args.assets)
    args.out.with_suffix('.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(args.out,manifest['sha256'])
