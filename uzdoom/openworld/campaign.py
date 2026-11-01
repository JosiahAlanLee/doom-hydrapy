# SPDX-License-Identifier: GPL-3.0-or-later
"""Adapt the reviewed polygon worlds into a complete native campaign floor."""
import math
import random
from pathlib import Path
from .environments import BUILDERS as ORIGINAL_BUILDERS
from .archetypes import BUILDERS as ROOM_BUILDERS
from .archetypes_extra import BUILDERS as EXTRA_BUILDERS
from .navigation import connect
from .nrlib import point_in_poly
from .routegraph import build_graph
from uzdoom.models import actor_id,installation_specs

BUILDERS={**ORIGINAL_BUILDERS,**ROOM_BUILDERS,**EXTRA_BUILDERS}
IDS=tuple(BUILDERS)


def distance_edge(p,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1];l=dx*dx+dy*dy
    t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/l)) if l else 0
    return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)


def clearance(p,poly):
    return min(distance_edge(p,a,poly[(i+1)%len(poly)]) for i,a in enumerate(poly)) if point_in_poly(*p,poly) else -1


def safe_points(sector,margin=28):
    poly=sector.poly;xs=[p[0] for p in poly];ys=[p[1] for p in poly]
    centre=(sum(xs)/len(xs),sum(ys)/len(ys))
    result=[(x,y) for x in range(math.ceil(min(xs)/32)*32,int(max(xs)),32)
            for y in range(math.ceil(min(ys)/32)*32,int(max(ys)),32) if clearance((x,y),poly)>=margin]
    if clearance(centre,poly)>=margin:result.append(centre)
    if not result:raise ValueError('No radius-20 placement in '+sector.name)
    return sorted(result,key=lambda p:math.dist(p,centre))


def add_floor(m,number,seed,base,bosses,order,plan):
    identity=plan['archetype'];layout_seed=plan['seed']
    b=BUILDERS[identity](layout_seed);graph=build_graph(b)
    if graph['metrics']['unreachable_anchors']:raise ValueError('Disconnected required anchors')
    anchors={a['role']:a for a in graph['anchors']}
    sectors={s.name:s for s in b.sectors}
    offset=len(m.sectors)
    if offset:raise ValueError('Open geometry must precede annex geometry')
    for s in b.sectors:
        m.sectors.append(dict(id=s.tag,heightfloor=base+s.floor,heightceiling=base+s.ceil,
                              texturefloor=s.tf,textureceiling=s.tc,lightlevel=max(184,min(224,s.light+32)),special=0))
    controls={c['sector']:c for c in b.controls};used=set()
    for ln in b.lines:
        front=ln['front'];back=ln['back'];two=ln['two'];side=len(m.sides)
        m.sides.append(dict(sector=front.index,texturetop=front.tw,texturebottom=front.tw,texturemiddle='-' if two else front.tw))
        line=dict(v1=m.vertex(ln['a']),v2=m.vertex(ln['b']),sidefront=side,blocking=not two)
        if two:
            line.update(sideback=len(m.sides),twosided=True)
            m.sides.append(dict(sector=back.index,texturetop=back.tw,texturebottom=back.tw,texturemiddle='-'))
        if front.name in controls and front.name not in used and not two:
            used.add(front.name);c=controls[front.name]
            line.update(special=160,arg0=c['tag'],arg1=1,arg2=0,arg3=255,arg4=0)
        m.lines.append(line)
    m.open_geometry=[(s.poly,base+s.floor) for s in b.sectors if s.kind!='control']
    node_ids=connect(m,b,graph,base,safe_points)
    def at(role):
        a=anchors[role];return (a['x'],a['y'],base+a['z'])
    def thing(point,type,angle=0,args=()):
        x,y,z=point;m.thing(x,y,type,angle,z=z-m.floor_at(x,y),args=args)
    # Spawn follows the route graph's real entry surface, including its Z.
    start=at('entry');centre=m.nodes[node_ids[graph['start']]]
    start=(centre['x'],centre['y'],centre['z'])
    thing(start,1,math.degrees(math.atan2(-start[1],-start[0]))%360)
    boss_rows=[]
    occupied=[start]
    for i,original in enumerate(bosses):
        a=anchors['encounter_'+('a','b')[i]];s=sectors[a['sector']]
        # Radial rooms consist of several ordinary sectors at one height.
        # Use their connected surface for a local ritual, rather than forcing
        # both seals into one narrow wedge or putting them on another storey.
        connected={a['node']};todo=[a['node']]
        by_id={n['id']:n for n in graph['nodes']}
        for current in todo:
            for edge in graph['edges']:
                other_id=edge['b'] if edge['a']==current else edge['a'] if edge['b']==current else None
                if other_id is None or other_id in connected:continue
                n=by_id[other_id]
                if n['z']!=a['z'] or math.hypot(n['x']-a['x'],n['y']-a['y'])>480:continue
                connected.add(other_id);todo.append(other_id)
        candidates=[]
        for nid in sorted(connected):
            try:candidates.extend(safe_points(sectors[by_id[nid]['sector']]))
            except ValueError:pass
        candidates.sort(key=lambda p:math.hypot(p[0]-a['x'],p[1]-a['y']))
        if not candidates:raise ValueError('No local boss clearance: '+s.name)
        pos=candidates[0]
        ring=next((p for p in candidates if 112<=math.dist(p,pos)<=240),None)
        if ring is None:raise ValueError('No readable local seal spacing: '+s.name)
        # Each native seal has a72-unit radius. Keep the two activation
        # regions disjoint, so A->B requires an actual deliberate crossing.
        other=next((p for p in candidates if math.dist(p,pos)>=80 and 176<=math.dist(p,ring)<=320),None)
        if other is None:raise ValueError('No A/B seal spacing: '+s.name)
        z=base+a['z'];kind=original['class'];title=original['name']
        thing((*pos,z),actor_id(kind,title),270,args=(kind,(seed+i)%5,i+1))
        m.meta.append('B '+' '.join(map(str,[kind,*ring,z,*other,z]))+' '+title)
        # Native markers locate the exact small ritual rings without painting
        # an entire large, irregular room as one giant seal.
        row=dict(original);row.update(position=[*pos,z],seal=[*ring,z],secondary_seal=[*other,z]);boss_rows.append(row)
        occupied.extend([(*pos,z),(*ring,z),(*other,z)])
    v=at('vendor');thing(v,15999)
    m.meta.append('V '+' '.join(map(str,[*v,*order])))
    # Sparse encounters use broad real surfaces and never a decorative void or
    # a stair. Every new creature gets native AI, not a static gallery actor.
    rng=random.Random(seed+number*31337)
    candidates=[n for n in graph['nodes'] if n['kind']=='sector' and sectors[n['sector']].kind not in ('stair','control')]
    rng.shuffle(candidates);placed=[]
    for n in candidates:
        s=sectors[n['sector']]
        try:x,y=safe_points(s)[0]
        except ValueError:continue
        p=(x,y,base+n['z'])
        if s.ceil-n['z']<80 or any(math.dist(p[:2],q[:2])<160 for q in occupied+[v]):continue
        k=(7,8,11,14,1,3)[len(placed)%6]
        thing(p,actor_id(k),rng.randrange(360),args=(k,number,0));occupied.append(p);placed.append({'kind':k,'position':p})
        if len(placed)>=6:break
    # Supplies are outside the player and vendor cylinders, on verified ground.
    supplies=[]
    for role,item in [('entry',2001),('entry',2008),('vendor',2012),('optional_reward',2019),('overlook',2008)]:
        a=anchors[role];s=sectors[a['sector']]
        for p in safe_points(s):
            q=(*p,base+a['z'])
            if all(math.dist(q[:2],o[:2])>=48 for o in occupied+[v]):
                thing(q,item);occupied.append(q);supplies.append(q);break
    art=[]
    specs=installation_specs(Path(__file__).resolve().parents[2]/'assets/installations')
    for spec in specs:
        if spec['environment']!=identity:continue
        radius=spec['radius'];choices=[]
        for s in b.sectors:
            if not s.walk or s.kind in ('control','stair') or s.ceil-s.floor<spec['height']+32:continue
            try:points=safe_points(s,radius+24)
            except ValueError:continue
            for p in points:
                z=base+s.floor
                if any(math.dist(p,q[:2])<radius+112 for q in occupied+[v]):continue
                clear=True
                for ni,n in enumerate(m.nodes):
                    if abs(n['z']-z)>spec['height']+24:continue
                    for nj in n['edges']:
                        o=m.nodes[nj]
                        if distance_edge(p,(n['x'],n['y']),(o['x'],o['y']))<radius+32:clear=False;break
                    if not clear:break
                if clear:choices.append((math.dist(p,v[:2]),p,z))
        if choices:
            _,p,z=min(choices)
            thing((*p,z),spec['type'],spec['yaw_deg'])
            art.append(dict(key=spec['key'],position=[*p,z],radius=radius,height=spec['height']))
    return dict(id=identity,title=b.title,seed=layout_seed,start=start,exit=at('exit'),
                bosses=boss_rows,vending=dict(x=v[0],y=v[1],z=v[2],order=order),
                geometry_sectors=len(b.sectors),route_graph=graph,encounters=placed,
                anchors={k:at(k) for k in anchors},installations=art)
