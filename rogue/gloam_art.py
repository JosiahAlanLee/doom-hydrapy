# SPDX-License-Identifier: GPL-2.0-or-later
"""Original procedural billboard art for Gloamwood and Book III adaptations.

No Minecraft geometry/atlas or third-party game character art is imported.
Frame numbers match the native archetypes plus reserved live creature poses.
"""
import math
import random
from PIL import Image, ImageDraw


def draw(kind,seed,frame):
    height=128 if kind=='hollow' else 112
    image=Image.new('RGBA',(96,height));p=ImageDraw.Draw(image)
    rng=random.Random((seed<<5)+['hollow','redead','probator','jurisiel'].index(kind))
    phase=frame*math.pi/2;sway=round(math.sin(phase)*2);cx=48+sway+rng.randint(-2,2)
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
                p.line([(x,86),(cx+sign*30,99+step),(cx+sign*40,119)],fill=edge,width=5)
                for f in range(3):p.line((cx+sign*40,117,cx+sign*(37+f*3),124-f),fill=edge,width=2)
            p.line([(30,94),(20,109),(12,114)],fill=bark,width=8)
            p.line([(62,97),(72,111),(84,116)],fill=edge,width=5)
            fx,fy=51,84
            if frame==25:
                p.line([(26,87),(11,79),(3,102)],fill=edge,width=5)
                p.line([(69,87),(84,79),(93,102)],fill=edge,width=5)
        else:
            p.polygon([(35,12),(45,23),(48,43),(54,23),(63,7),(66,61),(61,96),(68,118),(49,123),(28,120),(36,96),(31,59)],fill=bark,outline=edge)
            for sign in [-1,1]:
                p.line([(48+sign*13,49),(48+sign*30,69),(48+sign*27,105)],fill=edge,width=5)
                p.line([(48+sign*13,28),(48+sign*27,15),(48+sign*30,3)],fill=edge,width=3)
                for f in range(3):
                    p.line((48+sign*27,101,48+sign*(24+f*4),116-f),fill=edge,width=2)
                    p.line((48+sign*6,113,48+sign*(15+f*5),126),fill=edge,width=3)
            fx,fy=48,67
        p.ellipse((fx-14,fy-20,fx+14,fy+23),fill=dark,outline=edge,width=3)
        p.polygon([(fx-7,fy-13),(fx+7,fy-12),(fx+8,fy+7),(fx,fy+14),(fx-8,fy+6)],fill=pale)
        p.line((fx-6,fy-5,fx-2,fy-4),fill=dark,width=2)
        p.line((fx+2,fy-4,fx+6,fy-5),fill=dark,width=2)
        p.line((fx-3,fy+6,fx+4,fy+7),fill=dark,width=2)
        for sign in [-1,1]:
            for j in range(3):p.line((fx+sign*13,fy-12+j*10,fx+sign*18,fy-7+j*10),fill=edge,width=2)
        for j in range(7):
            x=fx+rng.randint(-10,10);y=fy+rng.randint(12,23)
            p.line((x,y,x+rng.choice([-2,2]),y+4),fill=red,width=1)
    elif kind=='redead':
        stone=(171,184,174,255);edge=(95,119,113,255);body=(31,49,47,255)
        warning=frame==20;grip=frame==22;lean=10 if frame==21 else -6 if frame==23 else sway
        x=cx+lean
        p.polygon([(x-12,38),(x+12,38),(x+8,71),(x+13,80),(x-12,80)],fill=body,outline=edge)
        for j in range(5):
            y=44+j*6;p.line((x-11,y,x,y+3,x+10,y),fill=edge,width=2)
        for sign in [-1,1]:
            step=round(math.sin(phase+sign)*4) if frame<4 else 0
            p.line([(x+sign*7,76),(cx+sign*14,94+step),(cx+sign*17,108)],fill=edge,width=4)
            if warning:arm=[(x+sign*12,42),(x+sign*25,20),(x+sign*15,9)]
            elif grip:arm=[(x+sign*12,42),(cx+sign*35,53),(cx+sign*41,85)]
            else:arm=[(x+sign*12,42),(x+sign*24,66),(x+sign*26,92)]
            p.line(arm,fill=edge,width=4)
            for finger in range(3):
                ex,ey=arm[-1];p.line((ex,ey,ex+sign*(finger*3-2),ey+8),fill=stone,width=1)
        p.polygon([(x-13,10),(x+12,9),(x+15,25),(x+8,39),(x-9,38),(x-15,25)],fill=stone,outline=edge)
        p.rectangle((x-10,19,x-3,22),fill=dark);p.rectangle((x+3,19,x+10,22),fill=dark)
        p.polygon([(x-6,28),(x+7,28),(x+4,36),(x-4,36)],fill=warm if warning else dark)
        p.line((x+1,10,x-3,18,x+2,24,x-1,28),fill=dark,width=1)
        p.line((x+11,25,x+7,27,x+8,34),fill=dark,width=1)
        for _ in range(3):
            xx=x+rng.randint(-9,9);yy=rng.randint(11,33)
            p.line((xx,yy,xx+rng.choice([-3,3]),yy+3),fill=edge,width=1)
    elif kind=='probator':
        metal=(37,68,60,255);attack=frame in [6,7,8]
        p.line([(cx+10,59),(cx+23,83),(cx+13,99),(cx-14,94),(cx-22,77),(cx-9,61)],fill=green,width=9)
        p.line([(cx+10,59),(cx+23,83),(cx+13,99),(cx-14,94),(cx-22,77),(cx-9,61)],fill=metal,width=5)
        p.ellipse((cx-26,9,cx+26,64),fill=metal,outline=lime,width=3)
        p.ellipse((cx-20,15,cx+20,58),fill=dark,outline=green,width=2)
        p.ellipse((cx-8,31,cx+15,53),fill=warm if attack else pale)
        p.ellipse((cx-1,39,cx+8,52),fill=red)
        p.line((cx+3,48,cx+12,83),fill=green,width=1)
        for sign in [-1,1]:
            p.line((cx+sign*10,95,cx+sign*22,107),fill=green,width=3)
        if attack:p.arc((cx-32,3,cx+32,71),12,165,fill=warm,width=2)
    else:
        # Two carried frames intersect; their voids and bright edges stay legible.
        metal=(34,52,50,255);attack=frame in [4,5,6]
        p.rectangle((cx-25,8,cx+25,99),fill=metal,outline=green,width=4)
        p.rectangle((cx-18,16,cx+18,91),fill=dark,outline=lime,width=2)
        p.polygon([(cx-43,44),(cx+29,26),(cx+43,79),(cx-29,97)],fill=metal,outline=green,width=3)
        p.polygon([(cx-32,49),(cx+23,35),(cx+32,74),(cx-23,88)],fill=dark,outline=warm if attack else lime,width=2)
        p.line((cx-8,44,cx+3,82),fill=green,width=2)
        for sign in [-1,1]:
            p.ellipse((cx+sign*25-4,68,cx+sign*25+4,80),fill=warm)
            p.line((cx+sign*16,95,cx+sign*24,108),fill=green,width=4)
        p.ellipse((cx+12,54,cx+17,59),fill=warm)
    if dead:
        collapsed=Image.new('RGBA',image.size)
        small=image.resize((76,22),Image.Resampling.NEAREST)
        collapsed.alpha_composite(small,(10,height-24));image=collapsed
        q=ImageDraw.Draw(image)
        for j in range(8):
            x=rng.randrange(9,86);y=rng.randrange(height-23,height-2)
            q.rectangle((x,y,x+2,y+1),fill=pale if kind in ['hollow','redead'] else green)
    return image
