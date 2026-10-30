# SPDX-License-Identifier: GPL-2.0-or-later
"""Optional Studio patch. Gorgon's tracker is the source of time for every tic."""
import atexit, bisect, json, math, os, sys, time
from pathlib import Path
import numpy as np
from hydrapy import *
from hydrapy.live import register_hook
from client import Doom
import ascii_op
ROOT=Path(os.environ['DOOM_TAKE_ROOT']);SMOKE=os.environ.get('DOOM_SMOKE')=='1'
STUDIO=dict(title='Freedoom / Gorgon / polyphonic live take')
set_bpm(120)
beat=tracker.beat();intervals=[0,3,6,9] if SMOKE else ([0,60,120,180] if os.environ.get('DOOM_INDUSTRIAL')=='1' else [0,7,70,145])
configs=[('freedoom1.wad','demo1'),('freedoom2.wad','demo2'),('freedoom1.wad','demo3'),('freedoom2.wad','demo4')]
engines=[Doom(Path(os.environ.get('DOOM_DATA_ROOT',str(ROOT)))/'data/freedoom-0.13.0'/wad,demo) for wad,demo in configs]
for e in engines:atexit.register(e.close)
trace=open(ROOT/('smoke-frame-trace.jsonl' if SMOKE else 'poly-frame-trace.jsonl'),'w',buffering=65536)
last={}
def seconds(t):return max(0,float(beat(Ctx(time=t,bpm=120)))/2)
def draw(t):
    sec=seconds(t);idx=max(i for i,start in enumerate(intervals) if sec>=start)
    local=sec-intervals[idx];engine=engines[idx];frame=engine.frame(local)
    last.update(seconds=sec,demo=idx+1,local=local,tic=engine.tic-engine.base,expected=int(local*35+1e-8))
    return frame
source=src(FrameSource(draw)).pixelate(640,400)
if os.environ.get('DOOM_INDUSTRIAL')=='1':
    import doom_math_ops
    from hydrapy.signals import Fn1
    schedule=json.loads((ROOT/'poly/schedule.json').read_text())
    notes=json.loads((ROOT/'poly/notes.json').read_text())
    kick_times=sorted(n['start'] for n in notes if n['ch']==4 and n['note'] in (35,36))
    snare_times=sorted(n['start'] for n in notes if n['ch']==4 and n['note'] in (38,40))
    def music_seconds(ctx):
        sec=seconds(ctx.time)
        if SMOKE:
            i=min(3,int(sec//3));sec=i*60+(sec-i*3)
        return sec
    def pulse_at(ctx,times,decay):
        sec=music_seconds(ctx);i=bisect.bisect_right(times,sec)-1
        return math.exp(-(sec-times[i])/decay) if i>=0 else 0.
    def score_beats(ctx):
        sec=music_seconds(ctx);total=0.
        for track in schedule['tracks']:
            total+=max(0.,min(sec,track['end'])-track['start'])*track['bpm']/60
        return total
    music_beat=Fn(score_beats)
    kick=Fn(lambda c:pulse_at(c,kick_times,.25));snare=Fn(lambda c:pulse_at(c,snare_times,.30))
    scene('doom-melt')(lambda:source.doomMeltShear(melt=.08+.18*kick+.06*Fn1('sin',music_beat*.5),shear=.05+.10*snare,columns=160.,phase=music_beat*.85).blend(src(o0).scale(1.004),.18).contrast(1.12).saturate(1.15))
    scene('doom-disk')(lambda:source.doomPoincareCathedral(zoom=1.05+.25*kick+.12*Fn1('sin',music_beat*.25),twist=Time()*.18+.08*Fn1('cos',music_beat*.5),hud_ring=1.,sectors=6.).contrast(1.14).saturate(1.18))
    scene('doom-vector')(lambda:source.doomSobelVectorScope(edge_gain=2.2+.9*snare,hazard_glow=1.3+.8*kick,phosphor=.72,scan=200.).blend(src(o0).scale(1.003),.22).contrast(1.16))
    scene('doom-relief')(lambda:source.doomAnaglyphRelief(parallax=.014+.016*kick+.005*Fn1('sin',music_beat*.5),light_depth=.65,horizon=.56,mode=0.).contrast(1.12).saturate(1.15))
else:
    scene('doom-terminal')(lambda:source.doomAscii(100).contrast(1.1))
    scene('doom-print')(lambda:source.brightness(.12).saturate(.3).halftone(5,.65,.75).color(1,.82,.59))
    scene('doom-scan')(lambda:source.ruttetra(100,.12,1.1,.25).color(.4,1,.8))
    scene('doom-feedback')(lambda:source.blend(src(o0).scale(1.006).scrollX(.002),.25).posterize(5,.7).saturate(.6))
# A 1 Hz white sync square in the top-left corner, paired with an audio gate.
# It also gives the held-frame audit a changing reference during slow passages.
flash=Fn(lambda c:float((float(beat(c))/2)%1<.05))
marker=solid(flash,flash,flash).mask(shape(4,.025,0).scroll(.477,-.475))
# Composite to a second output so scene registration stays on o0.
src(o0).layer(marker).out(o1);render(o1)
def record_frame(context,renderer):
    sec=seconds(context.time)
    trace.write(json.dumps(dict(wall=time.monotonic(),canvas=context.time,seconds=sec,**{k:v for k,v in last.items() if k!='seconds'},scenes={k:v for k,v in (renderer.patch.scene_weights or {}).items() if v>.01}))+'\n')
    if context.frame%60==0:trace.flush()
register_hook(record_frame)
