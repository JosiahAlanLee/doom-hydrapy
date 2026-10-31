# SPDX-License-Identifier: GPL-3.0-or-later
"""Native encounter feedback, using the same authoritative state as combat."""
import math
from PIL import ImageDraw
from rogue.hud import decorate as base_decorate, text, bar, INK, MUTED, AMBER, PANEL, LINE, font

OPEN=(86,226,216)


def seal_guidance(state,boss):
    secondary=boss.get('class')==10 and boss.get('gate_stage',0)==1
    prefix='seal_b_' if secondary else 'seal_'
    label=('B' if secondary else 'A') if boss.get('class')==10 else 'F'
    if boss.get('on_secondary_seal' if secondary else 'on_seal'):
        return f'ON {label} SEAL'
    dx=boss.get(prefix+'x',0)-state.get('x',0)
    dy=boss.get(prefix+'y',0)-state.get('y',0)
    delta=(math.degrees(math.atan2(dy,dx))-state.get('angle',0)+180)%360-180
    direction='AHEAD' if abs(delta)<20 else 'BEHIND' if abs(delta)>145 else 'LEFT' if delta>0 else 'RIGHT'
    dz=boss.get(prefix+'z',0)-state.get('z',0)
    height=' / ABOVE' if dz>40 else ' / BELOW' if dz<-40 else ''
    return f'{label} SEAL {direction}{height} / {math.hypot(dx,dy)/64:.0f}m'


def binding_progress(boss):
    kind=boss.get('class')
    if kind==5:
        n=min(2,boss.get('stamps',0));return n/2,f'F PRESSES {n}/2'
    if kind==6:
        n=min(35,boss.get('still_ticks',0));return n/35,f'STILL {100*n//35}%'
    if kind==9:
        ready=boss.get('proof',False);return .5 if ready else 0,'HIT RECORDED / F TO CONFIRM' if ready else 'HIT SHIELD / THEN F'
    ready=boss.get('gate_stage',0)==1
    return .5 if ready else 0,'A REGISTERED / FIND B' if ready else 'ENTER A / THEN B'


def decorate(image,state):
    # Keep the browser/native-C HUD unchanged; this panel describes UZDoom rules.
    image=base_decorate(image,{**state,'bosses':[]})
    pair=state.get('bosses') or []
    if not pair or state.get('paused'):return image
    d=ImageDraw.Draw(image);current=state.get('boss') or {}
    for i,b in enumerate(pair[:2]):
        x=8+316*i;right=x+307
        selected=b.get('name')==current.get('name') and b.get('phase')!='bound'
        phase=b.get('phase');colour=OPEN if phase=='exposed' else MUTED if phase=='bound' else AMBER
        d.rectangle((x,54,right,88),fill=PANEL,outline=colour if selected else LINE)
        text(d,(x+6,56),b.get('name','DEMON'),colour)
        hp=f"{max(0,b.get('health',0))}/{b.get('max_health',0)}"
        text(d,(right-6-d.textlength(hp,font=font()),56),hp,INK)
        status='DEFEATED' if phase=='bound' else f"EXPOSED / {b.get('open_ticks',0)/35:.1f}s / 150% DAMAGE" if phase=='exposed' else 'SHIELD / 60% DAMAGE'
        if phase=='sealed' and b.get('last_hit_ticks',0)>0:status+=' / HIT'
        text(d,(x+6,71),status,colour,9)
        bar(d,x+6,84,295,100*b.get('health',0)/max(1,b.get('max_health',1)),colour)
    if all(b.get('phase')=='bound' for b in pair):
        d.rectangle((8,94,631,114),fill=PANEL)
        text(d,(14,98),'BOTH DEFEATED / SERVICE ANNEX OPEN',OPEN)
        return image
    d.rectangle((8,94,631,137),fill=PANEL)
    exposed=current.get('phase')=='exposed'
    message=current.get('hint','')
    text(d,(14,97),message,OPEN if exposed else AMBER)
    if exposed:
        text(d,(14,113),'SHIELD BROKEN / FIRE FOR 150% DAMAGE',OPEN)
        value=current.get('open_ticks',0)/420;progress='12 SECOND OPENING'
    else:
        text(d,(14,113),seal_guidance(state,current),INK)
        value,progress=binding_progress(current)
    text(d,(329,113),progress,OPEN if exposed else AMBER,9)
    bar(d,329,130,292,value*100,OPEN if exposed else AMBER)
    return image
