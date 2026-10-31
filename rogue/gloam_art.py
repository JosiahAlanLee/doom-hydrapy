# SPDX-License-Identifier: GPL-2.0-or-later
"""Original procedural billboard art for Gloamwood and Book III adaptations.

No Minecraft geometry/atlas or third-party game character art is imported.
Frame numbers match the native archetypes plus reserved live creature poses.
"""
import math
import random
import numpy as np
from PIL import Image, ImageDraw


def finish(image,kind,seed):
    """Seeded material shading in sprite space, before native palette mapping.

    Broad planes, a narrow bevel and sparse chips retain large readable masses
    under the green-vector treatment. No blur, glow or resampling is applied.
    """
    common={(10,17,20):(16,15,13),(222,222,187):(211,197,161),
            (157,56,48):(118,43,32),(255,141,70):(210,106,56)}
    palettes={
        'hollow':{(66,47,33):(82,61,40),(133,107,68):(162,135,94)},
        'redead':{(171,184,174):(177,166,141),(95,119,113):(119,115,92),
                  (31,49,47):(80,60,49)},
        'probator':{(37,68,60):(91,75,52),(92,201,142):(174,153,104),
                    (201,255,99):(230,214,166),(222,222,187):(172,158,119)},
        'jurisiel':{(34,52,50):(83,67,47),(92,201,142):(174,153,112),
                    (201,255,99):(229,214,171),(255,141,70):(166,75,35)},
        'repetiel':{(201,255,99):(234,213,167),(79,183,134):(160,139,96),
                    (26,62,53):(80,61,45),(9,19,22):(17,13,12),(255,133,73):(183,65,45)},
        'calmor':{(201,255,99):(226,209,163),(79,183,134):(155,135,94),
                  (26,62,53):(84,69,47),(9,19,22):(17,15,13),(255,133,73):(183,84,48)},
    }
    colors=common|palettes[kind]
    a=np.asarray(image).copy();rgb=a[:,:,:3];alpha=a[:,:,3]>0
    h,w=alpha.shape;yy,xx=np.indices((h,w))
    rng=np.random.default_rng((seed*17+list(palettes).index(kind)*7919)&0xffffffffffffffff)
    grain=rng.integers(-5,6,size=(h,w))
    chips=rng.random((h,w))
    result=rgb.astype(np.int16).copy()
    for source in np.unique(rgb[alpha],axis=0):
        mask=alpha&np.all(rgb==source,axis=2)
        base=np.array(colors.get(tuple(source),tuple(source)),dtype=np.float32)
        # Each material's broad shading is anchored to its own bounding box.
        my,mx=np.nonzero(mask)
        tx=(xx-mx.min())/max(1,int(mx.max()-mx.min()))
        ty=(yy-my.min())/max(1,int(my.max()-my.min()))
        light=1.10-.19*tx-.10*ty
        top=mask&~np.roll(mask,1,axis=0);left=mask&~np.roll(mask,1,axis=1)
        bottom=mask&~np.roll(mask,-1,axis=0)
        shade=np.rint((light-.62)/.16).astype(np.int16)
        shade+=(grain==5).astype(np.int16)-(grain==-5).astype(np.int16)
        shade+=(top|left).astype(np.int16)-bottom.astype(np.int16)-(chips>.975).astype(np.int16)
        levels=np.array([.62,.79,.94,1.08,1.24],dtype=np.float32)
        material=base[None,None,:]*levels[np.clip(shade,0,4)][:,:,None]
        result[mask]=np.clip(material[mask],0,255).astype(np.int16)
    a[:,:,:3]=np.clip(result,0,255).astype(np.uint8)
    return Image.fromarray(a)


def draw(kind,seed,frame):
    height=128 if kind=='hollow' else 112
    image=Image.new('RGBA',(96,height));p=ImageDraw.Draw(image)
    rng=random.Random((seed<<5)+['hollow','redead','probator','jurisiel'].index(kind))
    phase=frame*math.pi/2;sway=round(math.sin(phase)*2);cx=min(50,48+sway+rng.randint(-2,2))
    dark=(10,17,20,255);green=(92,201,142,255);lime=(201,255,99,255)
    pale=(222,222,187,255);red=(157,56,48,255);warm=(255,141,70,255)
    death={'hollow':11,'redead':7,'probator':10,'jurisiel':7}[kind]
    dead=death<=frame<20
    if kind=='hollow':
        bark=(66,47,33,255);edge=(133,107,68,255)
        crawl=frame in [20,21,22,23,25]
        if crawl:
            # A split horizontal trunk with a face recessed in the open chest.
            p.polygon([(25,76),(54,65),(69,77),(68,98),(51,109),(25,99)],fill=bark,outline=edge)
            for sign in [-1,1]:
                x=cx+sign*15;step=round(math.sin(phase+(sign+1))*5)
                p.line([(x,86),(cx+sign*30,99+step),(cx+sign*40,119)],fill=bark,width=8)
                p.line([(x-1,84),(cx+sign*30-1,97+step),(cx+sign*40-1,117)],fill=edge,width=2)
                for f in range(3):p.line((cx+sign*40,117,cx+sign*(37+f*3),124-f),fill=edge,width=2)
            p.line([(30,94),(20,109),(12,114)],fill=bark,width=8)
            p.line([(62,97),(72,111),(84,116)],fill=edge,width=5)
            fx,fy=51,84
            if frame==25:
                p.line([(26,87),(11,79),(4,102)],fill=edge,width=7)
                p.line([(69,87),(84,79),(91,102)],fill=edge,width=7)
        else:
            p.polygon([(33,12),(44,23),(48,43),(55,23),(64,7),(69,61),(64,96),(70,118),(49,123),(25,120),(33,96),(28,59)],fill=bark,outline=edge)
            for sign in [-1,1]:
                p.line([(48+sign*13,49),(48+sign*30,69),(48+sign*27,105)],fill=bark,width=9)
                p.line([(47+sign*13,48),(47+sign*30,68),(47+sign*27,104)],fill=edge,width=2)
                p.line([(48+sign*13,28),(48+sign*27,15),(48+sign*30,3)],fill=edge,width=3)
                for f in range(3):
                    p.line((48+sign*27,101,48+sign*(24+f*4),116-f),fill=edge,width=2)
                    p.line((48+sign*6,113,48+sign*(15+f*5),126),fill=edge,width=3)
            fx,fy=48,67
        p.ellipse((fx-14,fy-20,fx+14,fy+23),fill=dark,outline=edge,width=3)
        p.polygon([(fx-8,fy-14),(fx+7,fy-13),(fx+9,fy+6),(fx+3,fy+15),(fx-6,fy+10),(fx-9,fy-1)],fill=pale)
        p.polygon([(fx+2,fy-12),(fx+7,fy-11),(fx+7,fy+6),(fx+2,fy+12)],fill=(151,140,112))
        p.polygon([(fx-7,fy-6),(fx-1,fy-5),(fx-3,fy-1),(fx-7,fy-2)],fill=dark)
        p.polygon([(fx+2,fy-5),(fx+7,fy-7),(fx+7,fy-2),(fx+3,fy-1)],fill=dark)
        p.line((fx,fy-1,fx-2,fy+5,fx+1,fy+5),fill=(130,119,94),width=1)
        p.polygon([(fx-4,fy+8),(fx+5,fy+7),(fx+3,fy+12),(fx-3,fy+11)],fill=dark)
        for sign in [-1,1]:
            for j in range(3):p.line((fx+sign*13,fy-12+j*10,fx+sign*18,fy-7+j*10),fill=edge,width=2)
        for j in range(7):
            x=fx+rng.randint(-10,10);y=fy+rng.randint(12,23)
            p.line((x,y,x+rng.choice([-2,2]),y+4),fill=red,width=1)
        for sign in [-1,1]:
            for j in range(4):
                x=fx+sign*(16+rng.randrange(4));y=fy-15+j*9
                p.line((x,y,x-sign*2,y+6),fill=edge,width=2)
    elif kind=='redead':
        stone=(171,184,174,255);edge=(95,119,113,255);body=(31,49,47,255)
        warning=frame==20;grip=frame==22;lean=10 if frame==21 else -6 if frame==23 else sway
        x=cx+lean
        top,hip,hy=(65,98,45) if grip else (38,80,0)
        p.polygon([(x-14,top),(x+14,top),(x+8,hip-9),(x+13,hip),(x-12,hip)],fill=body,outline=edge)
        for j in range(5):
            y=top+5+j*5;p.line((x-12,y,x,y+3,x+11,y),fill=edge,width=3)
        p.line((x,top+3,x-1,hip-5),fill=(145,130,100),width=2)
        p.polygon([(x-13,hip-4),(x+12,hip-4),(x+10,hip+4),(x-9,hip+5)],fill=(60,56,41),outline=edge)
        for sign in [-1,1]:
            step=round(math.sin(phase+sign)*4) if frame<4 else 0
            leg=[(x+sign*7,94),(cx+sign*25,102),(cx+sign*33,108)] if grip else [(x+sign*7,76),(cx+sign*14,94+step),(cx+sign*17,108)]
            p.line(leg,fill=body,width=7);p.line([(a-1,b-1) for a,b in leg],fill=edge,width=2)
            if warning:arm=[(x+sign*12,42),(x+sign*25,20),(x+sign*15,9)]
            elif grip:arm=[(x+sign*12,71),(cx+sign*33,53),(cx+sign*41,85)]
            else:arm=[(x+sign*12,42),(x+sign*24,66),(x+sign*26,92)]
            p.line(arm,fill=body,width=7);p.line([(a-1,b-1) for a,b in arm],fill=edge,width=2)
            ex,ey=arm[1];p.ellipse((ex-3,ey-3,ex+3,ey+3),fill=edge)
            for finger in range(3):
                ex,ey=arm[-1];p.line((ex,ey,ex+sign*(finger*3-2),ey+8),fill=stone,width=1)
        p.polygon([(x-13,10+hy),(x+12,9+hy),(x+15,25+hy),(x+8,39+hy),(x-9,38+hy),(x-15,25+hy)],fill=stone,outline=edge)
        p.polygon([(x+5,11+hy),(x+12,10+hy),(x+14,25+hy),(x+8,38+hy),(x+5,30+hy)],fill=(117,125,115))
        p.polygon([(x-11,19+hy),(x-3,20+hy),(x-4,25+hy),(x-10,24+hy)],fill=dark)
        p.polygon([(x+3,20+hy),(x+10,18+hy),(x+10,23+hy),(x+4,25+hy)],fill=dark)
        p.line((x,23+hy,x-2,28+hy,x+2,28+hy),fill=(100,105,94),width=1)
        p.polygon([(x-6,29+hy),(x+7,28+hy),(x+4,36+hy),(x-4,36+hy)],fill=warm if warning else dark)
        p.line((x+1,10+hy,x-3,18+hy,x+2,24+hy,x-1,28+hy),fill=dark,width=1)
        p.line((x+11,25+hy,x+7,27+hy,x+8,34+hy),fill=dark,width=1)
        for _ in range(3):
            xx=x+rng.randint(-9,9);yy=rng.randint(11,33)+hy
            p.line((xx,yy,xx+rng.choice([-3,3]),yy+3),fill=edge,width=1)
    elif kind=='probator':
        metal=(37,68,60,255);attack=frame in [6,7,8]
        p.line([(cx+10,59),(cx+23,83),(cx+13,99),(cx-14,94),(cx-22,77),(cx-9,61)],fill=green,width=13)
        p.line([(cx+10,59),(cx+23,83),(cx+13,99),(cx-14,94),(cx-22,77),(cx-9,61)],fill=metal,width=5)
        p.ellipse((cx-26,9,cx+26,64),fill=metal,outline=lime,width=3)
        p.ellipse((cx-20,15,cx+20,58),fill=dark,outline=green,width=2)
        p.ellipse((cx-16,20,cx+16,53),fill=(28,40,36),outline=(72,87,69),width=2)
        p.arc((cx-15,17,cx+15,48),188,270,fill=pale,width=2)
        p.ellipse((cx-6,34,cx+13,53),fill=warm if attack else (139,127,95))
        p.polygon([(cx+3,37),(cx+8,42),(cx+6,53),(cx+1,49)],fill=red)
        p.line((cx+3,48,cx+12,83),fill=green,width=1)
        for sign in [-1,1]:
            p.line((cx+sign*10,95,cx+sign*22,107),fill=green,width=6)
        for a in range(0,360,45):
            px=cx+round(math.cos(math.radians(a))*23);py=36+round(math.sin(math.radians(a))*25)
            p.rectangle((px-1,py-1,px+1,py+1),fill=dark)
        if attack:p.arc((cx-32,3,cx+32,71),12,165,fill=warm,width=2)
    else:
        # Two carried frames intersect; their voids and bright edges stay legible.
        metal=(34,52,50,255);attack=frame in [4,5,6]
        p.rectangle((cx-25,8,cx+25,99),fill=metal,outline=green,width=4)
        p.rectangle((cx-18,16,cx+18,91),fill=dark,outline=lime,width=2)
        p.line((cx-22,11,cx-22,96),fill=(171,155,119),width=2)
        p.polygon([(cx-43,44),(cx+29,26),(cx+43,79),(cx-29,97)],fill=metal,outline=green,width=3)
        p.polygon([(cx-32,49),(cx+23,35),(cx+32,74),(cx-23,88)],fill=dark,outline=warm if attack else lime,width=2)
        p.line((cx-8,44,cx+3,82),fill=green,width=2)
        for j in range(4):
            px=cx-27+j*15;py=46-j*3
            p.line((px,py,px+8,py-2),fill=(191,177,139),width=2)
        for px,py in [(cx-27,68),(cx+26,47)]:
            p.rectangle((px-2,py-4,px+3,py+5),fill=warm,outline=dark)
        for sign in [-1,1]:
            p.ellipse((cx+sign*25-4,68,cx+sign*25+4,80),fill=warm)
            p.line((cx+sign*16,95,cx+sign*24,108),fill=green,width=7)
        p.ellipse((cx+12,54,cx+17,59),fill=warm)
    image=finish(image,kind,seed)
    if dead:
        collapsed=Image.new('RGBA',image.size)
        small=image.resize((76,22),Image.Resampling.NEAREST)
        collapsed.alpha_composite(small,(10,height-24));image=collapsed
        q=ImageDraw.Draw(image)
        for j in range(8):
            x=rng.randrange(9,86);y=rng.randrange(height-23,height-2)
            q.rectangle((x,y,x+2,y+1),fill=(203,189,151) if kind in ['hollow','redead'] else (151,130,87))
    return image
