# SPDX-License-Identifier: GPL-2.0-or-later
"""Original grid BSP/PWAD writer. No external node builder or borrowed maps.

Every tile is a convex subsector. Closed tiles have zero headroom; shared
two-sided lines make the open tiles ordinary Doom rooms and corridors. A balanced
axis BSP uses the same boundaries, so no segment splitting is needed. Keep the
map small enough for vanilla Doom's signed-short coordinates and block offsets.
"""
from collections import deque
from dataclasses import dataclass
from pathlib import Path
import argparse
import hashlib
import json
import math
import random
import struct

TILE = 128
FLOORS = 5
SIZE = 25
THEMES = [
    ('RELAY / 01', 'STARTAN3', 'FLOOR4_8', 'CEIL3_5', 192),
    ('OXIDE / 02', 'BROWN1', 'FLOOR0_1', 'CEIL3_5', 160),
    ('STATIC / 03', 'STONE2', 'FLAT5_4', 'CEIL5_1', 176),
    ('FOUNDRY / 04', 'METAL2', 'FLOOR4_8', 'CEIL5_1', 144),
    ('NULL / 05', 'STONE3', 'FLAT5_4', 'CEIL3_5', 128),
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


def generate(seed, number):
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 0xffffffff:
        raise ValueError('seed must be an unsigned 32-bit integer')
    if not 1 <= number <= FLOORS:
        raise ValueError('floor must be 1..5')
    rng = random.Random((seed << 8) | number)
    cells, rooms = set(), []
    for attempt in range(180):
        w, h = rng.randint(3, 6), rng.randint(3, 6)
        x, y = rng.randint(1, SIZE-w-1), rng.randint(1, SIZE-h-1)
        if any(x-1 < a+c and x+w+1 > a and y-1 < b+d and y+h+1 > b for a,b,c,d in rooms):
            continue
        rooms.append((x,y,w,h))
        cells.update((a,b) for a in range(x,x+w) for b in range(y,y+h))
        if len(rooms) >= 7 + number:
            break
    if len(rooms) < 3:
        raise RuntimeError('insufficient rooms')
    # Connect the nearest unconnected room to the existing tree; add two cycles.
    centres = [(x+w//2,y+h//2) for x,y,w,h in rooms]
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
    parents = distances(cells,start)
    assert len(parents) == len(cells)
    # BFS insertion order is deterministic; the last point is a furthest tile.
    exit_cell = list(parents)[-1]
    route = [exit_cell]
    while route[-1] != start:
        route.append(parents[route[-1]])
    route.reverse()
    occupied = {start, exit_cell}
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
                  for y in range(rooms[0][1],rooms[0][1]+rooms[0][3]) if (x,y)!=start]
    rng.shuffle(start_room)
    for kind in [2001,2008,2008,2011]:
        item(start_room.pop(),kind)
    candidates = sorted(cells - occupied)
    rng.shuffle(candidates)
    distant = [p for p in candidates if abs(p[0]-start[0])+abs(p[1]-start[1]) >= 6
               and abs(p[0]-exit_cell[0])+abs(p[1]-exit_cell[1]) >= 2]
    enemy_kinds = [3004,3004,3001,3001] + ([3002,9] if number >= 2 else [])
    if number >= 4:
        enemy_kinds += [3005]
    for p in distant[:5+number*3]:
        item(p,rng.choice(enemy_kinds),rng.randrange(4)*90)
    remaining = [p for p in candidates if p not in occupied]
    for i,p in enumerate(remaining[:12+number]):
        item(p,[2007,2008,2011,2012,2018,2048][i%6])
    if number >= 2:
        for p in remaining[12+number:]:
            if item(p,2002):
                break
    direction = route[1][0]-start[0], route[1][1]-start[1]
    angle = {(1,0):0,(0,1):90,(-1,0):180,(0,-1):270}[direction]
    things.insert(0,(start[0]*TILE+64,start[1]*TILE+64,angle,1,7))
    return Floor(number,cells,rooms,start,exit_cell,route,things,THEMES[number-1])


def name8(s):
    return s.encode('ascii').ljust(8,b'\0')


def map_lumps(floor):
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
            sides.append(struct.pack('<hh8s8s8sH',0,0,name8(wall),name8(wall),name8(wall if back is None else '-'),sindex(*cell)))
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
            sectors.append(struct.pack('<hh8s8shhh',0,128+32*(floor.number%2) if opened else 0,
                                       name8('FLOOR0_1' if exit_tile else flat),name8(ceiling),
                                       255 if exit_tile else light,0,0))
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


def campaign(seed, output):
    output=Path(output)
    floors=[generate(seed,i) for i in range(1,FLOORS+1)]
    lumps=[lump for f in floors for lump in map_lumps(f)]
    data=bytearray(); directory=[]
    for name,payload in lumps:
        directory.append(struct.pack('<II8s',12+len(data),len(payload),name8(name)))
        data.extend(payload)
    wad=struct.pack('<4sII',b'PWAD',len(lumps),12+len(data))+data+b''.join(directory)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(wad)
    manifest={'format':'doom-rogue-1','seed':seed,'floors':[], 'sha256':hashlib.sha256(wad).hexdigest()}
    for f in floors:
        manifest['floors'].append({'number':f.number,'name':f.theme[0],'rooms':len(f.rooms),
                                  'open_tiles':len(f.cells),'start':f.start,'exit':f.exit,
                                  'route':f.route,'monsters':sum(t[3] in [3004,3001,3002,9,3005] for t in f.things),
                                  'cells':sorted(f.cells)})
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,default=20261030)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    manifest=campaign(args.seed,args.out)
    args.out.with_suffix('.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(args.out,manifest['sha256'])
