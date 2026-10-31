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

FAMILIES={'POSS':'skitter','SARG':'bastion','TROO':'cantor','HEAD':'shiver','BOSS':'repetiel','BOS2':'calmor',
          'SKEL':'hollow','CPOS':'redead','FATT':'probator','BSPI':'jurisiel',
          'SPOS':'surveyor','SSWV':'wire_shambler','VILE':'threshold_mimic','SKUL':'vore_spindle',
          'CYBR':'latchwing','PAIN':'relay_choir','TLP2':'service_lamp','TLMP':'cable_shrine','COLU':'directory_sign'}


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
    if kind in ('latchwing','relay_choir'):
        from rogue.threshold_assets import draw_creature
        return draw_creature(kind,seed,frame)
    if kind in ('service_lamp','cable_shrine','directory_sign'):
        from rogue.threshold_assets import draw_prop
        return draw_prop(kind)
    if kind in ['surveyor','wire_shambler','threshold_mimic','vore_spindle']:
        from rogue.argon_art import draw
        return draw(kind,seed,frame)
    if kind in ['hollow','redead','probator','jurisiel']:
        from rogue.gloam_art import draw
        return draw(kind,seed,frame)
    rng=random.Random((seed<<5)+list(FAMILIES.values()).index(kind))
    image=Image.new('RGBA',(96,112));pen=ImageDraw.Draw(image)
    phase=frame*math.pi/2
    sway=round(math.sin(phase)*3)
    core=(201,255,99,255);edge=(79,183,134,255);metal=(26,62,53,255);dark=(9,19,22,255)
    eye=(255,133,73,255)
    death_start={'skitter':7,'bastion':8,'cantor':8,'shiver':5,'repetiel':8,'calmor':8}[kind]
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
    elif kind=='shiver':
        for j in range(4):
            y=25+j*12
            pen.polygon([(cx,y-8),(cx-28+j*3,y+12),(cx,y+25),(cx+28-j*3,y+12)],outline=edge,fill=dark)
            pen.line((cx-22+j*3,y+12,cx+22-j*3,y+12),fill=core,width=1)
        pen.ellipse((cx-6,46,cx+6,58),fill=eye if attack else core)
        for j in range(5):
            x=cx-16+j*8;pen.line([(x,75),(x+sway*2,90),(x-sway,104)],fill=edge,width=1)
    elif kind=='repetiel':
        # Two mouths, one return tube; new pixel art from the book description.
        pen.line([(cx-24,27),(cx-24,73),(cx-18,87),(cx,94),(cx+18,87),(cx+24,73),(cx+24,27)],fill=edge,width=17)
        pen.line([(cx-24,27),(cx-24,73),(cx-18,87),(cx,94),(cx+18,87),(cx+24,73),(cx+24,27)],fill=metal,width=11)
        for sign in [-1,1]:
            x=cx+sign*24
            pen.ellipse((x-15,13,x+15,39),fill=dark,outline=core,width=2)
            pen.ellipse((x-12,16,x+12,36),outline=eye,width=2)
            for j in range(4):
                xx=x-9+j*6
                pen.polygon([(xx-2,17),(xx+2,17),(xx+1,24+(j%2)*2)],fill=core)
                pen.polygon([(xx-2,35),(xx+2,35),(xx-1,29-(j%2)*2)],fill=core)
            for y in [45,58,70]:pen.line((x-8,y,x+8,y),fill=core,width=1)
            pen.line((cx+sign*11,90,cx+sign*14,104,cx+sign*23,104),fill=edge,width=3)
        if attack:pen.arc((cx-43,3,cx+43,51),180,350,fill=eye,width=2)
    else:  # Calmor: muffled bell and its visible lining, not a generic giant.
        pen.line((cx-34,103,cx-34,13,cx+6,13,cx+6,24),fill=edge,width=3)
        pen.polygon([(cx,25),(cx+10,29),(cx+13,55),(cx+29,78),(cx+34,87),
                     (cx-34,87),(cx-29,78),(cx-13,55),(cx-10,29)],fill=metal,outline=core)
        pen.ellipse((cx-34,78,cx+34,95),fill=dark,outline=core,width=2)
        for j in range(8):
            x=cx-27+j*8
            pen.polygon([(x,82),(x+5,82),(x+7,90),(x+2,93)],fill=(151,142,116),outline=(72,64,51))
        for j in range(3):
            y=39+j*12;span=10+j*5
            pen.line((cx-span,y,cx,y+4,cx+span,y),fill=edge,width=2)
        pen.line((cx,65,cx,91+sway),fill=eye if attack else core,width=4)
        pen.ellipse((cx-5,88+sway,cx+5,99+sway),fill=eye if attack else core)
        for j in range(3):pen.arc((cx-37-j*3,28-j*3,cx+37+j*3,96+j*3),285,340,fill=edge,width=1)
    if kind in ['repetiel','calmor']:
        from rogue.gloam_art import finish
        image=finish(image,kind,seed)
    if dead:
        # Collapse after the family's real death-state boundary, leaving an
        # unmistakable corpse instead of animating a living silhouette.
        collapsed=Image.new('RGBA',image.size)
        small=image.resize((70,24),Image.Resampling.NEAREST)
        collapsed.alpha_composite(small,(13,84));image=collapsed
        p=ImageDraw.Draw(image)
        if kind in ['repetiel','calmor']:core=(213,190,133,255);metal=(80,61,45,255)
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


def sprite_lumps(assets,seed,environment=None):
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
        prop=None
        if environment and kind in ('service_lamp','cable_shrine','directory_sign'):
            from rogue.environments import picture as environment_picture
            prop=environment_picture(environment,'props',kind)
        for frame in range(26):
            if environment and kind in ('latchwing','relay_choir'):
                from rogue.environments import draw_mob
                image=draw_mob(environment,kind,seed,frame)
            else:image=prop if prop is not None else creature(kind,seed,frame)
            generated.append((family+chr(65+frame)+'0',patch(image,palette)))
    # Preserve the full flat namespace when adding the two native seal tiles.
    flats=[];active=False
    for name,data in lumps:
        if name=='F_START':active=True;continue
        if name=='F_END':active=False;continue
        if active:flats.append((name,data))
    if not flats:raise ValueError('Freedoom flat namespace not found')
    for kind,number in [('repetiel',5),('calmor',6),('probator',9),('jurisiel',10),('jurisiel-b',11)]:
        tile=Image.new('RGB',(64,64),(14,32,28));p=ImageDraw.Draw(tile)
        p.ellipse((3,3,60,60),outline=(201,255,99),width=3)
        p.ellipse((9,9,54,54),outline=(79,183,134),width=1)
        if number==5:
            p.line([(21,20),(21,40),(32,46),(43,40),(43,20)],fill=(201,255,99),width=3)
            p.ellipse((15,14,27,24),outline=(255,133,73),width=2)
            p.ellipse((37,14,49,24),outline=(255,133,73),width=2)
        elif number==6:
            p.polygon([(32,17),(39,22),(40,35),(47,43),(17,43),(24,35),(25,22)],outline=(201,255,99))
            p.ellipse((19,39,45,47),outline=(255,133,73),width=2)
        elif number==9:
            p.ellipse((18,14,43,39),outline=(201,255,99),width=3)
            p.line((38,37,46,49,29,48,23,39),fill=(255,133,73),width=3)
            p.ellipse((26,24,34,32),fill=(255,133,73))
        else:
            color=(255,173,71) if number==10 else (86,226,216)
            p.ellipse((3,3,60,60),outline=color,width=3)
            p.rectangle((20,15,43,48),outline=color,width=3)
            if number==10:
                p.line((25,43,32,22,39,43),fill=color,width=3)
                p.line((28,35,36,35),fill=color,width=3)
            else:
                p.line((26,22,26,43),fill=color,width=3)
                p.arc((22,22,39,33),270,90,fill=color,width=3)
                p.arc((22,32,39,43),270,90,fill=color,width=3)
                p.line((26,22,32,22),fill=color,width=2)
                p.line((26,33,32,33),fill=color,width=2)
                p.line((26,43,32,43),fill=color,width=2)
        rgb=np.asarray(tile).astype(np.int32)
        unique,inverse=np.unique(rgb.reshape(-1,3),axis=0,return_inverse=True)
        nearest=((unique[:,None,:]-palette[None,:,:].astype(np.int32))**2).sum(2).argmin(1)
        flats.append(('RSEAL10B' if number==11 else 'RSEAL'+str(number),nearest[inverse].astype(np.uint8).tobytes()))
    from rogue.threshold_assets import flat_lumps
    flats.extend(flat_lumps(palette,environment))
    return [('S_START',b'')]+original+generated+[('S_END',b''),('F_START',b'')]+flats+[('F_END',b'')]
