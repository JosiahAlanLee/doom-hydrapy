# SPDX-License-Identifier: GPL-3.0-or-later
"""Single-controller UZDoom campaign; gameplay authority stays in ZScript."""
from pathlib import Path
import json,os,secrets,threading,time
from .build import build
from .engine import Engine,KEYS

MOTION_CODES=frozenset(KEYS[k] for k in ('KeyW','KeyS','KeyA','KeyD','KeyQ','KeyE','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','ShiftLeft','ShiftRight'))

class Game:
    def __init__(self,wad,run_dir,*,initial_mode='campaign',identity=True):
        self.wad=Path(wad);self.root=Path(run_dir);self.root.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.owner=None;self.paused=True;self.held=set();self.last_input=0
        self.revision=0;self.error=None;self.state={};self.frame_seq=0;self.engine=None;self.stop_event=threading.Event()
        self.input_map=None;self.input_resyncs=0;self.motion_rearm_tick=None;self.motion_release_pending=True
        self.new_run(int(os.environ.get('NULLRUN_SEED','20261031')))
        self.thread=threading.Thread(target=self.loop,daemon=True,name='uzdoom-campaign');self.thread.start()
    def new_run(self,seed,mode='campaign'):
        if mode!='campaign':raise ValueError('This player runs the tower campaign')
        with self.lock:
            folder=self.root/f'run-{time.time_ns()}-{seed}'
            try:recent=json.loads((self.root/'room-history.json').read_text())
            except (OSError,ValueError):recent=[]
            if not isinstance(recent,list) or any(not isinstance(p,str) for p in recent):recent=[]
            retry=getattr(self,'manifest',{}).get('seed')==seed
            plan=self.manifest.get('floor_plan') if retry else None
            manifest=build(seed,self.wad,folder,os.environ.get('NULLRUN_ENVIRONMENT') or None,floor_plan=plan,recent_openers=recent[-5:])
            candidate=Engine(os.environ['UZDOOM_BINARY'],os.environ['UZDOOM_BRIDGE'],self.wad,folder/'nullrun.pk3',folder/'engine',sound=os.environ.get('UZDOOM_SOUND')=='1')
            if candidate.latest.get('error'):candidate.close();raise RuntimeError(candidate.latest['error'])
            previous=self.engine;self.release();self.engine=candidate;self.manifest=manifest
            self.paused=True;self.owner=None;self.revision+=1;self.error=None;self.render()
            if previous:previous.close()
            if not retry:
                recent=(recent+[manifest['floor_plan'][0]['archetype']])[-5:]
                temp=self.root/'room-history.tmp';temp.write_text(json.dumps(recent));temp.replace(self.root/'room-history.json')
    def release(self):
        if self.engine:
            for code in self.held:self.engine.key(code,False)
        self.held=set()
    def acquire(self):
        with self.lock:
            if self.state.get('vending',{}).get('menu_open'):raise ValueError('Close the machine first')
            if self.owner:raise ValueError('Another controller has this run')
            self.owner=secrets.token_urlsafe(24);self.last_input=time.monotonic();self.paused=False;self.engine.pause(False);return self.owner
    def input(self,owner,keys,paused=False,turn=0,look=0):
        if not isinstance(keys,list) or len(keys)>32 or any(k not in KEYS for k in keys):raise ValueError('Unknown controls')
        if any(type(n) is not int or not -4096<=n<=4096 for n in (turn,look)):raise ValueError('Invalid mouse movement')
        with self.lock:
            if not owner or self.owner!=owner:raise ValueError('Click Play to take controls')
            self.last_input=time.monotonic();self.paused=bool(paused or self.state.get('vending',{}).get('menu_open') or self.state.get('dead') or self.state.get('won'))
            want={KEYS[k] for k in keys} if not self.paused else set()
            if self.motion_rearm_tick is None or self.state.get('level_tics',0)<self.motion_rearm_tick:
                want-=MOTION_CODES
            for code in self.held-want:self.engine.key(code,False)
            for code in want-self.held:self.engine.key(code,True)
            self.held=want;self.engine.pause(self.paused)
            if self.paused:self.owner=None
            elif turn or look:self.engine.move(turn,look)
    def purchase(self,vendor,slot,revision):
        with self.lock:
            if revision!=self.revision or not self.paused:raise ValueError('Open this run’s machine first')
            result=self.engine.buy(vendor,slot);self.render();return result
    def close_shop(self):
        with self.lock:self.engine.command('VCLOSE');self.engine.wait(lambda:not self.engine.latest.get('vending',{}).get('menu_open'));self.render()
    def render(self):
        # Keep the native contiguous RGBA layout. Converting to RGB here and
        # back to RGBA in FrameSource costs several full-frame copies.
        self.state=self.engine.state()
        if self.state.get('map') and self.state['map']!=self.input_map:
            # UZDoom releases native buttons on a map change. Invalidate our
            # sent-key cache too, so the next physical snapshot reasserts held
            # movement instead of waiting for a new press edge.
            self.release();self.input_map=self.state['map'];self.input_resyncs+=1
            self.motion_rearm_tick=None;self.motion_release_pending=True
        if self.motion_release_pending and self.state.get('level_tics',0)>0:
            # The first map picture can precede load completion. Once ticking,
            # clear the keyboard cache and wait seven native tics before new
            # held-movement presses. Putting both edges in one loading frame
            # can be discarded by the engine. Other actions keep their edges.
            self.engine.clear_movement(MOTION_CODES)
            self.motion_rearm_tick=self.state['level_tics']+7;self.motion_release_pending=False
        self.rgb=self.engine.frame();self.frame_seq=self.engine.frame_seq
    def snapshot(self):
        with self.lock:
            entry=self.manifest['floors'][min(7,max(1,self.state.get('map',1)))-1]
            current=next((b for b in entry.get('bosses',[]) if b['name']==(self.state.get('boss') or {}).get('name')),None)
            return dict(self.state,seed=self.manifest['seed'],floor_name=entry['name'],floors=7,mode='campaign',identity='threshold',
                        environment=self.manifest['environment'],boss_rule=current.get('game_rule') if current else None,
                        paused=self.paused,revision=self.revision,frame=self.frame_seq,input_resyncs=self.input_resyncs,error=self.error or self.state.get('error'))
    def loop(self):
        while not self.stop_event.wait(1/60):
            with self.lock:
                try:
                    if self.engine.proc.poll() is not None:raise RuntimeError('The UZDoom process exited; inspect its engine.log')
                    self.render()
                    if not self.paused and (time.monotonic()-self.last_input>1 or self.state.get('dead') or self.state.get('won') or self.state.get('vending',{}).get('menu_open')):
                        self.release();self.engine.pause(True);self.paused=True;self.owner=None
                except Exception as exc:self.error=str(exc);self.release();self.paused=True;self.owner=None;self.engine.pause(True)
    def close(self):
        self.stop_event.set()
        if getattr(self,'thread',None):self.thread.join(timeout=10)
        with self.lock:
            self.release()
            if self.engine:self.engine.close();self.engine=None
