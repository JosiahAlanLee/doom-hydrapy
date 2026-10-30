# SPDX-License-Identifier: GPL-2.0-or-later
"""Original seeded pixel creatures, encoded as native Doom column patches.

The complete sprite namespace is assembled from the user's Freedoom IWAD,
replacing only four monster families. Other sprites remain unmodified so the
classic engine's single S_START/S_END namespace also contains weapons/items.
Generated monsters are deliberately billboard creatures (rotation 0).
"""
from pathlib import Path
import math
import random
import struct

import numpy as np
from PIL import Image,ImageDraw

FAMILIES={'POSS':'skitter','SARG':'bastion','TROO':'cantor','HEAD':'shiver'}


def wad_lumps(path):
    data=Path(path).read_bytes()
    magic,count,offset=struct.unpack_from('<4sII',data)
    if magic not in [b'IWAD',b'PWAD'] or not 0<count<100000 or offset+count*16>len(data):
        raise ValueError('Invalid asset WAD')
    result=[]
    for i in range(count):
        pos,length,name=struct.unpack_from('<II8s',data,offset+i*16)
        if pos+length>len(data):raise ValueError('Invalid WAD lump range')
        result.append((name.rstrip(b'\0').decode('ascii'),data[pos:pos+length]))
    return result


def creature(kind,seed,frame):
    rng=random.Random((seed<<5)+list(FAMILIES.values()).index(kind))
    image=Image.new('RGBA',(96,112));pen=ImageDraw.Draw(image)
    phase=frame*math.pi/2
    sway=round(math.sin(phase)*3)
    core=(201,255,99,255);edge=(79,183,134,255);metal=(26,62,53,255);dark=(9,19,22,255)
    eye=(255,133,73,255)
    death_start={'skitter':7,'bastion':8,'cantor':8,'shiver':5}[kind]
    dead=frame>=death_start
    attack=frame in range(max(3,death_start-3),death_start)
    cx=48+sway;cy=52
    limb=rng.randint(18,24);spikes=rng.randint(3,6);girth=rng.randint(13,19)
    if kind=='skitter':
        for sign in [-1,1]:
            for j in range(3):
                y=49+j*13;step=round(math.sin(phase+j)*5)
                pen.line([(cx+sign*7,y),(cx+sign*(limb+5),y+step),(cx+sign*(limb+10),y+18)],fill=edge,width=3)
        pen.polygon([(cx,24),(cx-girth,44),(cx-10,79),(cx,90),(cx+10,79),(cx+girth,44)],fill=metal,outline=edge)
        for j in range(spikes):
            y=36+j*8;pen.line((cx-10,y,cx+10,y),fill=core,width=1)
        pen.polygon([(cx-7,44),(cx,35),(cx+7,44),(cx,55)],fill=eye if attack else core)
        pen.line((cx-9,33,cx-18,15,cx-25,12),fill=edge,width=2)
        pen.line((cx+9,33,cx+18,15,cx+25,12),fill=edge,width=2)
    elif kind=='bastion':
        for sign in [-1,1]:
            for j in range(3):
                y=49+j*15;step=round(math.sin(phase+j)*4)
                pen.line([(cx+sign*17,y),(cx+sign*36,y+step),(cx+sign*39,y+14)],fill=metal,width=7)
                pen.line([(cx+sign*17,y-2),(cx+sign*36,y+step-2)],fill=edge,width=2)
        pen.polygon([(cx-23,27),(cx-30,45),(cx-27,84),(cx,95),(cx+27,84),(cx+30,45),(cx+23,27)],fill=metal,outline=core)
        for j in range(4):
            y=38+j*13;pen.line((cx-22,y,cx,y+7,cx+22,y),fill=edge,width=2)
        pen.rectangle((cx-11,29,cx+11,38),fill=eye if attack else core)
    elif kind=='cantor':
        for sign in [-1,1]:
            pen.polygon([(cx+sign*12,37),(cx+sign*42,14),(cx+sign*31,59),(cx+sign*15,72)],fill=metal,outline=edge)
        pen.polygon([(cx,18),(cx-17,44),(cx-11,76),(cx,90),(cx+11,76),(cx+17,44)],fill=dark,outline=core)
        for j in range(spikes):
            y=40+j*8;pen.line((cx-13,y,cx+13,y+3),fill=edge,width=1)
        pen.ellipse((cx-8,40,cx+8,56),fill=eye if attack else core)
        for j in range(5):
            x=cx-14+j*7;pen.line([(x,74),(x+sway,88),(x-sway,102)],fill=edge,width=1)
        if attack:
            pen.ellipse((cx-23,30,cx+23,76),outline=eye,width=2)
    else:
        for j in range(4):
            y=25+j*12
            pen.polygon([(cx,y-8),(cx-28+j*3,y+12),(cx,y+25),(cx+28-j*3,y+12)],outline=edge,fill=dark)
            pen.line((cx-22+j*3,y+12,cx+22-j*3,y+12),fill=core,width=1)
        pen.ellipse((cx-6,46,cx+6,58),fill=eye if attack else core)
        for j in range(5):
            x=cx-16+j*8;pen.line([(x,75),(x+sway*2,90),(x-sway,104)],fill=edge,width=1)
    if dead:
        # Collapse after the family's real death-state boundary, leaving an
        # unmistakable corpse instead of animating a living silhouette.
        collapsed=Image.new('RGBA',image.size)
        small=image.resize((70,24),Image.Resampling.NEAREST)
        collapsed.alpha_composite(small,(13,84));image=collapsed
        p=ImageDraw.Draw(image)
        for j in range(7):
            x=rng.randrange(15,81);y=rng.randrange(90,109)
            p.rectangle((x,y,x+2,y+1),fill=core if j%2 else metal)
    return image


def patch(image,palette):
    rgba=np.asarray(image)
    rgb=rgba[:,:,:3].astype(np.int32)
    # Palette assignment only on the small original color set, not one large
    # pixel x palette x channel allocation for every animation frame.
    unique,inverse=np.unique(rgb.reshape(-1,3),axis=0,return_inverse=True)
    distances=((unique[:,None,:]-palette[None,:,:].astype(np.int32))**2).sum(2)
    indexed=distances.argmin(1)[inverse].reshape(rgb.shape[:2])
    height,width=rgba.shape[:2]
    columns=[]
    for x in range(width):
        data=bytearray();y=0
        while y<height:
            if not rgba[y,x,3]:y+=1;continue
            top=y
            while y<height and rgba[y,x,3]:y+=1
            count=y-top
            data.extend(bytes([top,count,0]));data.extend(indexed[top:y,x].astype(np.uint8).tobytes());data.append(0)
        data.append(255);columns.append(bytes(data))
    offsets=[];position=8+width*4
    for data in columns:offsets.append(position);position+=len(data)
    return struct.pack('<4h',width,height,width//2,height)+struct.pack('<'+'I'*width,*offsets)+b''.join(columns)


def sprite_lumps(assets,seed):
    lumps=wad_lumps(assets)
    palette=np.frombuffer(next(data for name,data in lumps if name=='PLAYPAL')[:768],dtype=np.uint8).reshape(256,3)
    active=False;original=[]
    for name,data in lumps:
        if name=='S_START':active=True;continue
        if name=='S_END':active=False;continue
        if active and name[:4] not in FAMILIES:original.append((name,data))
    if not original:raise ValueError('Freedoom sprite namespace not found')
    generated=[]
    for family,kind in FAMILIES.items():
        for frame in range(26):
            generated.append((family+chr(65+frame)+'0',patch(creature(kind,seed,frame),palette)))
    return [('S_START',b'')]+original+generated+[('S_END',b'')]
