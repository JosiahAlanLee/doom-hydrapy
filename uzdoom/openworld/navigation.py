# SPDX-License-Identifier: GPL-3.0-or-later
"""Capsule-clear local paths for concave polygon sectors and real portals."""
from collections import defaultdict
import heapq
import math
from .nrlib import point_in_poly


def edge_distance(p,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1];l=dx*dx+dy*dy
    t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/l)) if l else 0
    return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)


def segment_distance(a,b,c,d):
    def cross(p,q,r):return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    if cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0:return 0
    return min(edge_distance(a,c,d),edge_distance(b,c,d),edge_distance(c,a,b),edge_distance(d,a,b))


def connect(m,b,graph,base,safe_points):
    sectors=b.by_name;by_id={n['id']:n for n in graph['nodes']}
    floors=defaultdict(list)
    for c in b.controls:floors[c['tag']].append(c['top'])
    walls=defaultdict(list)
    for ln in b.lines:
        walls[ln['front'].name].append(ln)
        if ln['two']:walls[ln['back'].name].append(ln)
    def obstacles(s,z):
        out=[]
        for ln in walls[s.name]:
            other=ln['back'] if ln['front'] is s else ln['front']
            # A radius box can touch several20-unit treads. Their neighbouring
            # risers are support, rather than hard walls through the capsule.
            step_span=48 if ln['two'] and (s.kind=='stair' or other.kind=='stair') else 24
            if not ln['two'] or not any(abs(q-z)<=step_span and other.ceil-q>=72 for q in [other.floor,*floors[other.tag]]):out.append((ln['a'],ln['b']))
        return out
    # Match the support of a radius20 axis-aligned actor box against each
    # wall's normal, with2 units spare. A constant diagonal radius would
    # incorrectly reject narrow axis-aligned landings that native actors fit.
    def margin(a,c):
        dx,dy=c[0]-a[0],c[1]-a[1];length=math.hypot(dx,dy)
        return 20*(abs(dx)+abs(dy))/length+2 if length else 22
    def clear(p,blocked):return all(edge_distance(p,a,c)>=margin(a,c) for a,c in blocked)
    def visible(a,c,s,blocked):
        if any(segment_distance(a,c,p,q)<margin(p,q)-.1 for p,q in blocked):return False
        count=max(1,math.ceil(math.dist(a,c)/12))
        return all(point_in_poly(a[0]+(c[0]-a[0])*i/count,a[1]+(c[1]-a[1])*i/count,s.poly) for i in range(count+1))
    cache={};groups=defaultdict(list)
    def add(p,z,s):
        key=(round(p[0],5),round(p[1],5),z,s.index)
        if key not in cache:
            cache[key]=len(m.nodes);m.nodes.append(dict(x=p[0],y=p[1],z=base+z,sector=s.index,tile=0,edges=set(),custom=True,stair=s.kind=='stair'))
        return cache[key]
    def link(i,j):m.nodes[i]['edges'].add(j);m.nodes[j]['edges'].add(i)
    node_ids={}
    for n in graph['nodes']:
        s=sectors[n['sector']];blocked=obstacles(s,n['z'])
        p=next((p for p in safe_points(s,0) if clear(p,blocked)),None)
        if p is None:
            # A rotated20-unit tread can fall between the32-unit sample grid;
            # reconciled T-junction vertices can also bias its vertex average.
            xs=[p[0] for p in s.poly];ys=[p[1] for p in s.poly]
            fine=[(x,y) for x in range(math.ceil(min(xs)/8)*8,int(max(xs)),8)
                  for y in range(math.ceil(min(ys)/8)*8,int(max(ys)),8)
                  if point_in_poly(x,y,s.poly) and clear((x,y),blocked)]
            if fine:p=max(fine,key=lambda p:min((edge_distance(p,a,c) for a,c in blocked),default=1000))
        if p is None:raise ValueError('No capsule-clear nav centre: '+s.name)
        i=add(p,n['z'],s);node_ids[n['id']]=i;groups[s.name,n['z']].append(i)
    shared={}
    for ln in b.lines:
        if ln['two']:
            key=frozenset((ln['front'].name,ln['back'].name))
            old=shared.get(key)
            if old is None or math.dist(ln['a'],ln['b'])>math.dist(old['a'],old['b']):shared[key]=ln
    for e in graph['edges']:
        na,nc=by_id[e['a']],by_id[e['b']];sa,sc=sectors[na['sector']],sectors[nc['sector']]
        ln=shared[frozenset((sa.name,sc.name))];mid=((ln['a'][0]+ln['b'][0])/2,(ln['a'][1]+ln['b'][1])/2)
        ports=[]
        for n,s in ((na,sa),(nc,sc)):
            # The average point of a curved room can lie across its hollow
            # centre. A true inward edge normal is valid at the portal.
            dx,dy=ln['b'][0]-ln['a'][0],ln['b'][1]-ln['a'][1];length=math.hypot(dx,dy)
            candidates=[(mid[0]+sign*dy/length*4,mid[1]-sign*dx/length*4) for sign in (1,-1)]
            p=next((p for p in candidates if point_in_poly(*p,s.poly)),None)
            if p is None:raise ValueError('No inward portal: '+s.name)
            i=add(p,n['z'],s);groups[s.name,n['z']].append(i);ports.append(i)
            if sa.kind=='stair' or sc.kind=='stair':m.nodes[i]['stair']=True
        link(*ports)
    for (name,z),terminals in groups.items():
        terminals=list(dict.fromkeys(terminals));s=sectors[name];blocked=obstacles(s,z)
        points=[(m.nodes[i]['x'],m.nodes[i]['y']) for i in terminals]
        adj=[set() for p in points]
        for i,a in enumerate(points):
            for j in range(i):
                if visible(a,points[j],s,blocked):adj[i].add(j);adj[j].add(i)
        def reached():
            seen={0};todo=[0]
            for i in todo:
                for j in adj[i]:
                    if j not in seen:seen.add(j);todo.append(j)
            return seen
        if len(reached())<len(terminals):
            # Only difficult concave sectors need a temporary grid. Store
            # smoothed paths, not thousands of grid cells, in native metadata.
            grid={};xs=[p[0] for p in s.poly];ys=[p[1] for p in s.poly]
            for x in range(math.ceil(min(xs)/16)*16,int(max(xs)),16):
                for y in range(math.ceil(min(ys)/16)*16,int(max(ys)),16):
                    p=(x,y)
                    if point_in_poly(x,y,s.poly) and clear(p,blocked):grid[x,y]=len(points);points.append(p);adj.append(set())
            for p,i in grid.items():
                for dx,dy in [(16,0),(0,16),(16,16),(16,-16)]:
                    q=(p[0]+dx,p[1]+dy);j=grid.get(q)
                    if j is not None and visible(p,q,s,blocked):adj[i].add(j);adj[j].add(i)
            for i in range(len(terminals)):
                candidates=sorted(grid.values(),key=lambda j:math.dist(points[i],points[j]))
                attached=0
                for j in candidates:
                    if math.dist(points[i],points[j])>192:break
                    if visible(points[i],points[j],s,blocked):adj[i].add(j);adj[j].add(i);attached+=1
                    if attached==12:break
        for goal in range(1,len(terminals)):
            costs={0:0};previous={0:None};queue=[(0,0)]
            while queue:
                cost,i=heapq.heappop(queue)
                if i==goal:break
                if cost!=costs[i]:continue
                for j in adj[i]:
                    score=cost+math.dist(points[i],points[j])
                    if score<costs.get(j,math.inf):costs[j]=score;previous[j]=i;heapq.heappush(queue,(score,j))
            if goal not in previous:raise ValueError('No capsule-clear local path: '+name)
            path=[goal]
            while previous[path[-1]] is not None:path.append(previous[path[-1]])
            path.reverse();at=0;native=terminals[0]
            while at<len(path)-1:
                end=len(path)-1
                while end>at+1 and not visible(points[path[at]],points[path[end]],s,blocked):end-=1
                target=terminals[goal] if end==len(path)-1 else add(points[path[end]],z,s)
                link(native,target);native=target;at=end
    return node_ids
