# SPDX-License-Identifier: GPL-3.0-or-later
"""Argon's frozen-signal exhibition, adapted as safe optional native art.

Three seeded branching forms, three discrete states each. Art is suspended,
non-solid and never changes map collision. Only a nearby console changes it;
there is no hidden damage, flashing, progression lock or moving wall.
"""
import math
import random
from .models import md3


class Pose:
    def __init__(self,name,text):self.stem=name;self.text=text
    def read_text(self):return self.text


def poses(seed,installation):
    result=[]
    for state in range(3):
        rng=random.Random(seed ^ (installation*7919) ^ (state*104729))
        vertices=[];faces=[]
        def cube(x,y,z,size):
            r=size/2;o=len(vertices)
            vertices.extend((x+dx*r,y+dy*r,z+dz*r) for dx,dy,dz in
                            [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)])
            faces.extend(tuple(o+i+1 for i in tri) for tri in
                         [(0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),
                          (1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,0,4),(3,4,7)])
        def branch(x,y,z,length,yaw,pitch,depth):
            if depth==0:return
            cube(x,y,z,length*.4)
            nx=x+length*math.cos(pitch)*math.cos(yaw);ny=y+length*math.cos(pitch)*math.sin(yaw);nz=z+length*math.sin(pitch)
            angle=rng.uniform(.3,.8);factor=rng.uniform(.6,.8)
            for sign in (-1,1):branch(nx,ny,nz,length*factor,yaw+sign*angle,pitch+.2,depth-1)
        branch(0,0,136,64,rng.uniform(0,2*math.pi),math.pi/2,4)
        if len(faces)!=180 or not all(math.isfinite(c) and abs(c)<384 for v in vertices for c in v):raise ValueError('Art budget/bounds')
        text=''.join('v %.6f %.6f %.6f\n'%v for v in vertices)+'vt .5 .5\n'
        text+=''.join('f '+' '.join(str(v)+'/1' for v in f)+'\n' for f in faces)
        result.append(Pose(f'signal-{installation}-{state}',text))
    return result


def artwork(seed,png):
    from PIL import Image,ImageDraw
    files={};defs=[];classes=[]
    for i,colour in enumerate([(103,211,191),(223,174,106),(181,157,215)]):
        root=f'models/signals/{i}';skin=root+'/signal.png'
        files[skin]=png(Image.new('RGB',(16,16),colour));files[root+'/signal.md3']=md3(poses(seed,i),skin,1)
        frames=' '.join(f'FrameIndex NRMA {chr(65+s)} 0 {s}' for s in range(3))
        defs.append(f'Model NRSignal{i} {{ Path "{root}" Model 0 "signal.md3" Skin 0 "signal.png" Scale 1 1 1 {frames} }}')
        classes.append(f'class NRSignal{i} : NRSignal {{ }}')
        im=Image.new('RGBA',(48,64));d=ImageDraw.Draw(im)
        d.rectangle((5,12,43,63),fill=(28,35,40),outline=colour,width=2)
        d.rectangle((11,18,37,39),fill=colour);d.text((21,43),'F',fill=colour)
        files[f'sprites/NACN{chr(65+i)}0.png']=png(im,True)
    files['uzdoom/signals.zs']='\n'.join(classes).encode()
    return files,'\n'.join(defs)


def add_room(m,base):
    # The exit is a permanent independent gate. All changing art is above the
    # player's capsule; even a hostile console state cannot block this room.
    sec=m.rectangle(16000,-2000,1024,base,base+512,flat='EFLAT02',light=208)
    m.surface(16512,-1488,base,sec,1024)
    for i in range(3):
        x=16256+i*256
        m.thing(x,-1456,18200+i,z=0,args=(i,))
        m.thing(x,-1648,18210,z=0,args=(i,))
    outside=(12352,160,base);inside=(16128,-1872,base)
    m.gate(6,outside,inside,'CHLADNI_ARCHIVE')
    m.gate(7,inside,outside,'RETURN_TO_SERVICE_STAIR')
    return dict(name='Chladni Archive',entry=outside,exit=inside,consoles=[[16256+i*256,-1648,base] for i in range(3)],states=3,triangles_per_form=180)
