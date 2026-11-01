# SPDX-License-Identifier: GPL-3.0-or-later
"""Current native cues only: never queue effects across pauses or floor changes."""
import math
import time


def finite(value,default=0.):
    return float(value) if type(value) in (int,float) and math.isfinite(value) else default


def encounter_inputs(values):
    """Fail closed before uniform upload, which can sanitize NaN into zero."""
    result=dict(ritual_strength=0.,ritual_family=0.,ritual_progress=0.,ritual_open=0.,
                grip_strength=0.,grip_progress=0.,grip_warning=0.,grip_active=0.)
    for prefix,names in [('ritual',('strength','family','progress','open')),('grip',('strength','progress','warning','active'))]:
        data={n:values.get(prefix+'_'+n,0.) for n in names}
        if not all(type(v) in (int,float) and math.isfinite(v) for v in data.values()):continue
        if not 0<data['strength']<=1:continue
        if any(not 0<=v<=1 for n,v in data.items() if n!='family'):continue
        if prefix=='ritual' and data['family'] not in (1,2,3,4):continue
        if prefix=='grip' and data['active'] not in (0,1):continue
        result.update({prefix+'_'+n:float(v) for n,v in data.items()})
    return result


class Cues:
    def __init__(self):
        self.run=None;self.tick=None;self.updated=0.

    def sample(self,state,enabled=True,now=None):
        now=time.monotonic() if now is None else now
        result=dict(quiet_strength=0.,quiet_progress=0.,surveyor_strength=0.,surveyor_progress=0.,surveyor_count=0,
                    ritual_strength=0.,ritual_family=0.,ritual_progress=0.,ritual_open=0.,
                    grip_strength=0.,grip_warning=0.,grip_progress=0.,grip_active=0.)
        token=(state.get('seed'),state.get('revision'),state.get('map'))
        tick=state.get('level_tics')
        if token!=self.run or tick!=self.tick or now<self.updated:
            self.run=token;self.tick=tick;self.updated=now
        if not enabled or now-self.updated>.25 or tick is None or any(state.get(k) for k in ('paused','dead','won','error','loading')) or state.get('vending',{}).get('menu_open'):
            return result
        for b in state.get('bosses') or []:
            if b.get('class')!=6 or finite(b.get('health'))<=0 or b.get('phase')!='sealed' or not b.get('on_seal'):continue
            charge=finite(b.get('still_ticks'))
            if charge>0:
                result.update(quiet_strength=.42,quiet_progress=max(result['quiet_progress'],min(1.,charge/35.)))
        x=finite(state.get('x'));y=finite(state.get('y'))
        candidates=[]
        for b in state.get('bosses') or []:
            if b.get('class') not in (5,6,9,10) or finite(b.get('health'))<=0 or b.get('phase') not in ('sealed','exposed'):continue
            distance=finite(b.get('distance'),1e20)
            ring=b.get('on_seal') or b.get('class')==10 and b.get('on_secondary_seal')
            if not ((b.get('visible') and distance<=1024) or (ring and distance<=1280)):continue
            candidates.append((not ring,not b.get('visible',False),distance,b))
        if candidates:
            b=min(candidates,key=lambda c:c[:3])[3];kind=b['class']
            progress={5:min(1.,max(0.,finite(b.get('stamps'))/2)),
                      6:min(1.,max(0.,finite(b.get('still_ticks'))/35)),
                      9:.5 if b.get('proof') else 0.,10:.5 if b.get('gate_stage')==1 else 0.}[kind]
            opening=min(1.,max(0.,finite(b.get('open_ticks'))/420)) if b['phase']=='exposed' else 0.
            result.update(ritual_strength=.3,ritual_family={5:1,6:2,9:3,10:4}[kind],ritual_progress=progress,ritual_open=opening)
        for m in state.get('mobs') or []:
            if m.get('class')!=11 or finite(m.get('health'))<=0 or m.get('phase')!=2 or not m.get('sight'):continue
            remaining=finite(m.get('warning_ticks'))
            distance=math.hypot(finite(m.get('x'),1e20)-x,finite(m.get('y'),1e20)-y)
            if remaining<=0 or remaining>35 or distance>1536:continue
            result['surveyor_count']+=1
            result['surveyor_progress']=max(result['surveyor_progress'],1.-remaining/35.)
            result['surveyor_strength']=.55
        for m in state.get('mobs') or []:
            if m.get('class')!=8 or finite(m.get('health'))<=0 or m.get('phase')!=1 or not m.get('sight'):continue
            remaining=finite(m.get('warning_ticks'))
            distance=math.hypot(finite(m.get('x'),1e20)-x,finite(m.get('y'),1e20)-y)
            if 0<remaining<=28 and distance<=448:
                result.update(grip_strength=.4,grip_warning=max(result['grip_warning'],1.-remaining/28))
        creatures=state.get('creatures') or {}
        if creatures.get('effect')=='grip':
            # Zero escape progress is already an active grip. Progress follows
            # the real25-tic held-F escape, not elapsed time in the four-second hold.
            result.update(grip_strength=.45,grip_active=1.,grip_warning=0.,grip_progress=min(1.,max(0.,finite(creatures.get('escape_ticks'))/25)))
            result['quiet_strength']=result['ritual_strength']=0.
        # Keep a simultaneous attack warning clearer than the quiet ritual texture.
        if result['surveyor_count']:
            result['quiet_strength']*=.5;result['ritual_strength']*=.5
        return result
