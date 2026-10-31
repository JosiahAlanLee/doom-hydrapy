# SPDX-License-Identifier: GPL-3.0-or-later
"""Current native cues only: never queue effects across pauses or floor changes."""
import math
import time


def finite(value,default=0.):
    return float(value) if type(value) in (int,float) and math.isfinite(value) else default


class Cues:
    def __init__(self):
        self.run=None;self.tick=None;self.updated=0.

    def sample(self,state,enabled=True,now=None):
        now=time.monotonic() if now is None else now
        result=dict(quiet_strength=0.,quiet_progress=0.,surveyor_strength=0.,surveyor_progress=0.,surveyor_count=0)
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
        for m in state.get('mobs') or []:
            if m.get('class')!=11 or finite(m.get('health'))<=0 or m.get('phase')!=2 or not m.get('sight'):continue
            remaining=finite(m.get('warning_ticks'))
            distance=math.hypot(finite(m.get('x'),1e20)-x,finite(m.get('y'),1e20)-y)
            if remaining<=0 or remaining>35 or distance>1536:continue
            result['surveyor_count']+=1
            result['surveyor_progress']=max(result['surveyor_progress'],1.-remaining/35.)
            result['surveyor_strength']=.55
        # Keep a simultaneous attack warning clearer than the quiet ritual texture.
        if result['surveyor_count']:result['quiet_strength']*=.5
        return result
