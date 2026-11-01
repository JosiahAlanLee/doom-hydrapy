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


class EncounterHUD:
    """Small encounter-only display. Timers use game tics and stop on pause."""
    def __init__(self):
        self.run=None;self.floor=None;self.learned=set()
        self.previous={};self.recent={};self.hints={};self.shown=set();self.notices={}

    @staticmethod
    def on_seal(b):
        return b.get('on_seal') or b.get('class')==10 and b.get('on_secondary_seal')

    def prepare(self,state):
        run=(state.get('seed'),state.get('revision'))
        if run!=self.run:self.run=run;self.floor=None;self.learned.clear()
        if state.get('map')!=self.floor:
            self.floor=state.get('map');self.previous.clear();self.recent.clear()
            self.hints.clear();self.shown.clear();self.notices.clear()
        if state.get('paused') or state.get('dead') or state.get('won') or state.get('vending',{}).get('menu_open'):return None
        now=state.get('level_tics',0);candidates=[]
        for b in state.get('bosses') or []:
            name=b['name'];old=self.previous.get(name);ring=self.on_seal(b)
            if b.get('phase')=='exposed' or b.get('open_count',0):self.learned.add(b.get('class'))
            if old:
                if b.get('health',0)<old.get('health',0) or b.get('attacks',0)>old.get('attacks',0):self.recent[name]=now+105
                if b.get('proof') and not old.get('proof'):self.notices[name]=(now+105,'HIT RECORDED / F ON ITS SEAL')
                if b.get('gate_stage',0)>old.get('gate_stage',0):self.notices[name]=(now+105,'A REGISTERED / '+seal_guidance(state,b))
            if b.get('last_hit_ticks',0)>0:self.recent[name]=now+105
            if ring and not (old and self.on_seal(old)) and b.get('class') not in self.learned and name not in self.shown:
                self.shown.add(name);self.hints[name]=now+175
            self.previous[name]=dict(b)
            if b.get('phase')=='bound' or b.get('health',0)<=0:continue
            distance=b.get('distance',float('inf'));visible=b.get('visible',False) and distance<=1024
            if visible or ring and distance<=1280 or self.recent.get(name,-1)>=now and distance<=1280:
                candidates.append((not ring,not visible,distance,b))
        if not candidates:return None
        b=min(candidates,key=lambda c:c[:3])[3];name=b['name'];tip=None
        if b.get('phase')!='exposed':
            value,progress=binding_progress(b)
            if self.on_seal(b) and (value>0 or now<self.hints.get(name,-1)):
                message=b.get('hint') or progress
                tip={'text':name+' / '+message,'progress':value if value>0 else None}
            elif now<self.notices.get(name,(-1,''))[0]:
                tip={'text':name+' / '+self.notices[name][1],'progress':None}
        return {'boss':{k:b.get(k) for k in ('name','health','max_health','phase')},
                'seconds':round(b.get('open_ticks',0)/35,1),'tip':tip}


def decorate(image,state,encounter=None):
    image=base_decorate(image,{**state,'bosses':[]})
    from .weapons import LABELS
    d=ImageDraw.Draw(image);weapon=max(0,min(len(LABELS)-1,int(state.get('weapon',0))))
    d.rectangle((431,357,629,374),fill=PANEL)
    text(d,(434,359),LABELS[weapon],AMBER)
    encounter=encounter if encounter is not None else EncounterHUD().prepare(state)
    if not encounter:return image
    d=ImageDraw.Draw(image);b=encounter['boss'];exposed=b['phase']=='exposed';colour=OPEN if exposed else AMBER
    # One narrow bar near the title; tips sit above the bottom instruments.
    # Reserve the native warning line when another enemy has a cue.
    x=176;right=463;y=54 if state.get('argon',{}).get('cue') else 30
    d.rectangle((x,y,right,y+27),fill=PANEL,outline=LINE)
    text(d,(x+6,y+2),b['name'],INK,10)
    hp=f"{max(0,b['health'])}/{b['max_health']}"
    text(d,(right-6-d.textlength(hp,font=font(10)),y+2),hp,INK,10)
    status=f"EXPOSED {encounter['seconds']:.1f}s / 150%" if exposed else 'SHIELD / 60% DAMAGE'
    text(d,(x+6,y+13),status,colour,9)
    bar(d,x+6,y+24,275,100*b['health']/max(1,b['max_health']),colour)
    if encounter['tip']:
        tip=encounter['tip'];message=tip['text'];meter=tip['progress'] is not None
        available=580-(110 if meter else 0)
        while d.textlength(message,font=font(9))>available:message=message[:-4]+'...'
        width=min(608,max(280,round(d.textlength(message,font=font(9)))+24+(110 if meter else 0)))
        left=(640-width)//2;right=left+width
        d.rectangle((left,330,right,348),fill=PANEL)
        text(d,(left+8,333),message,AMBER,9)
        if meter:bar(d,right-106,338,98,100*tip['progress'],AMBER)
    return image
