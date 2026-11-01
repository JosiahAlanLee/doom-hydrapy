# SPDX-License-Identifier: GPL-2.0-or-later
"""Original classic-BSP studies; gameplay folds use matching physical copies."""
import struct
import numpy as np

STUDIES={
    'corridor':{'name':'CORRIDOR / AFTERIMAGE','kind':1,'rule':'Follow the corridor and find the exit. Try returning the same way.'},
    'pillar':{'name':'PILLAR / FIVE CORNERS','kind':2,'rule':'Keep the central pillar on your left. Count the corners, then find the entrance alcove again.'},
    'memory':{'name':'ROOM / UNRELIABLE MEMORY','kind':3,'rule':'Look at the two passages. Turn away, wait a moment, then look back.'},
}

def cellpoint(p):return (p[0]*128+64,p[1]*128+64)

def pair(index,source,target,axis,sign,turns=0):
    sx,sy=cellpoint(source);dx,dy=cellpoint(target)
    vx,vy=(sign,0) if axis==0 else (0,sign)
    for _ in range(turns):vx,vy=-vy,vx
    return [dict(id=index,sx=sx,sy=sy,dx=dx,dy=dy,axis=axis,sign=sign,turns=turns,width=64),
            dict(id=index+1,sx=dx,sy=dy,dx=sx,dy=sy,axis=0 if vx else 1,sign=-(vx or vy),turns=(-turns)%4,width=64)]

def study(seed,kind):
    from rogue.maps import Floor
    if isinstance(seed,bool) or not isinstance(seed,int) or not 0<=seed<=0xffffffff:raise ValueError('Unsigned seed required')
    if kind not in STUDIES:raise ValueError('Unknown architecture study')
    cells=set();profiles={};seams=[];changes=[]
    def add(points,**kwargs):
        for p in points:
            cells.add(p);profiles[p]={'floor':0,'height':192,'light':192,'wall':'METAL2','flat':'RARCHFL','ceiling':'RARCHCL','shape':'annex',**kwargs}
    def box(x0,y0,x1,y1,**kwargs):add(((x,y) for x in range(x0,x1+1) for y in range(y0,y1+1)),**kwargs)
    if kind=='corridor':
        for y in [8,22]:
            add(((x,y) for x in range(4,27)),height=128)
            add(((26,j) for j in range(y,y+4)),height=128)
            box(2,y-2,5,y+2);box(25,y+3,29,y+6)
        cells.discard((27,26))
        start=(6,8);exit_cell=(28,27);angle=0
        seams=pair(1,(14,8),(14,22),0,1)
        route=[start,(14,8),(14,22),(26,22),(26,25),exit_cell]
    elif kind=='pillar':
        bases=[(4,4),(20,4),(20,20),(4,20)]
        for bx,by in bases:
            add(((x,by) for x in range(bx,bx+11)),height=128)
            add(((x,by+10) for x in range(bx,bx+11)),height=128)
            add(((bx,y) for y in range(by,by+11)),height=128)
            add(((bx+10,y) for y in range(by,by+11)),height=128)
            add([(bx-1,by+2),(bx-1,by+1),(bx+2,by+11),(bx+1,by+11),
                 (bx+11,by+8),(bx+11,by+9),(bx+8,by-1),(bx+9,by-1)],height=128)
        box(1,4,2,6,height=128,light=208);add([(3,5)],height=128)
        seams+=pair(1,(14,9),(25,4),1,1,3)
        seams+=pair(3,(30,9),(25,20),1,1,3)
        seams+=pair(5,(30,25),(9,20),1,1,3)
        seams+=pair(7,(14,25),(4,9),1,1,2)
        start=(4,9);exit_cell=(1,5);angle=270
        route=[start,(4,4),(14,4),(14,9),(25,4),(30,4),(30,9),(25,20),(30,20),(30,25),(9,20),(14,20),(14,25),start]
    else:
        box(4,5,14,23);box(18,5,28,23)
        for y in [10,18]:add(((x,y) for x in range(15,18)))
        profiles[(16,10)]['tag']=1301;profiles[(16,18)]['tag']=1302;cells.remove((16,18))
        start=(10,14);exit_cell=(5,14);angle=0
        changes=[dict(id=1,a=1301,b=1302,height=192,delay=12)];route=[start,exit_cell]
    assert all(0<x<32 and 0<y<32 for x,y in cells)
    x,y=cellpoint(start)
    architecture={'study':kind,'kind':STUDIES[kind]['kind'],'seams':seams,'changes':changes,'rooms':[],
                  'max_step':0,'corners':5 if kind=='pillar' else None,'checkpoint':cellpoint(start),'planned_route':route}
    return Floor(1,cells,[],start,exit_cell,route,[(x,y,angle,1,7)],
                 ('STUDY / '+STUDIES[kind]['name'],'METAL2','FLOOR4_8','CEIL3_5',192),architecture,profiles)

def metadata(floor):
    a=floor.architecture;seams=a['seams'];changes=a['changes']
    result=struct.pack('<4s4i',b'RAR1',floor.number,a['kind'],len(seams),len(changes))
    for s in seams:result+=struct.pack('<10i',*(s[k] for k in ['id','sx','sy','dx','dy','axis','sign','turns','width']),0)
    for c in changes:result+=struct.pack('<5i',*(c[k] for k in ['id','a','b','height','delay']))
    return ('RARCH',result)

def flats(assets):
    from rogue.creatures import wad_lumps
    palette=np.frombuffer(next(v for n,v in wad_lumps(assets) if n=='PLAYPAL')[:768],dtype=np.uint8).reshape(256,3).astype(np.int32)
    yy,xx=np.indices((64,64));dx=np.minimum(xx,64-xx);dy=np.minimum(yy,64-yy)
    # Quarter-turn symmetry about tile boundary zero hides the rotated folds.
    tile=np.full((64,64,3),[92,92,75],dtype=np.int32)
    tile[(dx<2)|(dy<2)]=[45,49,43];tile[((dx//8+dy//8)%2)==0]=[100,100,81]
    tile[(dx==2)|(dy==2)]=[130,126,98]
    ceiling=np.full_like(tile,[117,121,106]);ceiling[(dx<3)|(dy<3)]=[64,67,58]
    result=[]
    for name,rgb in [('RARCHFL',tile),('RARCHCL',ceiling)]:
        colors,inverse=np.unique(rgb.reshape(-1,3),axis=0,return_inverse=True)
        nearest=((colors[:,None,:]-palette[None,:,:])**2).sum(2).argmin(1)
        result.append((name,nearest[inverse].astype(np.uint8).tobytes()))
    return result
