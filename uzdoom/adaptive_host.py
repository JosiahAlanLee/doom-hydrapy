"""Real, bounded Studio tracker backend for the reviewed adaptive composer.

Runs outside the audio/render callbacks. Native controls remain entirely owned
by the game; this process reads state and changes only this session's tracker.
"""
from pathlib import Path
import argparse
import copy
import heapq
import json
import math
import signal
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parent
DEP=Path(__import__('os').environ['NULLRUN_DEPENDENCIES'])
sys.path[:0]=[str(ROOT/'music_package'),str(DEP/'hydrapy'),str(DEP/'Gorgon')]
from hydrapy.tracker_v3 import empty_pattern,validate,TICKS
from gorgon.launcher import api
from nullrun_music.engine import Engine
from nullrun_music.events import Cue,BAR,ROW
from nullrun_music.director import PRIORITY
from nullrun_music.composer import finalize_bar,compose_sting
from nullrun_music.scale import midi_to_name
from nullrun_music.snapshot_rules import propose

ROWS=128
CYCLE=ROWS*ROW
LOOP_STATES={'exploration','threat','combat','quiet','boss_sealed','boss_exposed','boss_one_down'}
TERMINAL={'death','victory','end'}

def document(engine,kind,floor,env,start_tick):
    """One fixed eight-bar geometry; rotate new material onto the live phase."""
    profile,content=engine._section(kind,floor,env)
    doc=json.loads((Path(__import__('os').environ['NULLRUN_INITIAL_SCORE'])).read_text())
    doc.update(bpm=profile['tempo'],key=profile['key'],seed=engine.seed,
               pattern=0,chain=[0],loop=True,mutes=[False]*6,
               bindings={'z':'','roll':'','feedback':''},lanes=[{'name':n} for n in profile['lanes']['names']])
    pattern=empty_pattern(0)
    pattern.update(name=f'{env[:12]} {kind}'[:40],bar=16,bars=8,rate=1)
    for lane in pattern['lanes']:lane.update(len=ROWS,cells=[None]*ROWS,transforms=[])
    offset=(int(start_tick)//ROW)%ROWS
    for bar in range(8):
        if bar>=len(content.lanes[0]) and not content.loop:break
        cells=finalize_bar(content,bar%len(content.lanes[0]))
        for lane,events in enumerate(cells):
            for row,note,velocity,gate in events:
                target=(offset+bar*16+row)%ROWS
                # A gate at the cycle boundary ends there, without a held note.
                length=min(float(gate),ROWS-target)
                pattern['lanes'][lane]['cells'][target]={'note':midi_to_name(note),'vel':velocity,'len':length}
    doc['patterns']=[None]*128;doc['patterns'][0]=pattern
    return validate(doc)


class Studio:
    def __init__(self,info):self.info=info;self.calls=0;self.maximum_ms=0.
    def get(self):return api(self.info,'tracker',timeout=3)
    def post(self,endpoint,payload):
        before=time.monotonic();result=api(self.info,endpoint,payload,timeout=5)
        self.calls+=1;self.maximum_ms=max(self.maximum_ms,(time.monotonic()-before)*1000)
        return result


class Backend:
    def __init__(self,studio,log=lambda event:None):
        self.studio=studio;self.log=log;self.queue=[];self.serial=0
        self.doc=None;self.base=None;self.kind='exploration';self.floor=1
        self.sting=None;self.duck_until=None;self.duck_mask=[];self.silent=False
        self.last_cycle=None;self.now=0.;self.paused=True;self.last_publish=-1
        self.accepted_revision=-1;self.accepted_transport=-1

    def accept(self,snapshot):
        self.accepted_revision=max(self.accepted_revision,snapshot.get('revision',-1))
        self.accepted_transport=max(self.accepted_transport,snapshot.get('transport_revision',-1))

    def fresh(self):
        # GET is a render-frame cache; POST replies are current. Following a
        # reset/edit, briefly ignore cached states preceding the accepted edit.
        deadline=time.monotonic()+3
        while True:
            snapshot=self.studio.get()
            if snapshot['revision']>=self.accepted_revision and snapshot['transport_revision']>=self.accepted_transport:
                return snapshot
            if time.monotonic()>=deadline:raise RuntimeError('Tracker snapshot did not catch up to accepted edit')
            time.sleep(.01)

    def clock(self,snapshot):
        if snapshot['revision']<self.accepted_revision or snapshot['transport_revision']<self.accepted_transport:
            return int(self.now)
        cycle=(snapshot['start']['tick']+snapshot['ticks'])%CYCLE
        if self.last_cycle is not None:
            delta=cycle-self.last_cycle
            if delta < -CYCLE/2:delta+=CYCLE
            if -2<=delta<0:delta=0. # seek's whole-tick rounding
            if delta<0 or delta>CYCLE/2:raise ValueError('Unexpected tracker seek')
            self.now+=delta
        self.last_cycle=cycle
        return int(self.now)

    def publish(self):
        doc=copy.deepcopy(self.base)
        if self.sting:
            for tick,note,vel,gate in self.sting['notes']:
                if tick+gate*ROW<=self.now:continue
                row=(tick//ROW)%ROWS
                doc['patterns'][0]['lanes'][5]['cells'][row]={'note':midi_to_name(note),'vel':vel,'len':min(gate,ROWS-row)}
        doc['mutes']=[self.silent or lane in self.duck_mask for lane in range(6)]
        doc=validate(doc)
        current=self.fresh()
        result=self.studio.post('tracker_score',{'document':doc,'revision':current['revision']})
        self.accept(result)
        self.doc=doc;self.last_publish=int(self.now)
        self.log({'type':'score','tick':int(self.now),'kind':self.kind,'revision':result['revision']})

    def reset(self,engine,floor,env,paused):
        self.engine=engine;self.floor=floor;self.env=env;self.kind='exploration'
        self.queue=[];self.now=0.;self.last_cycle=None;self.sting=None
        self.duck_until=None;self.duck_mask=[];self.silent=False
        self.base=document(engine,'exploration',floor,env,0)
        self.publish()
        state=self.studio.post('tracker_transport',{'enabled':not paused,'playing':True,'beat':0.})
        self.accept(state)
        self.paused=paused;self.last_cycle=(state['start']['tick']+state['ticks'])%CYCLE
        self.log({'type':'reset','seed':engine.seed,'environment':env,'paused':paused})

    def pause(self,value):
        if value==self.paused:return
        # Do not set playing=False: it also freezes the visual patch and hooks.
        state=self.studio.post('tracker_transport',{'enabled':not value,'playing':True})
        self.accept(state)
        self.clock(state);self.paused=value
        self.log({'type':'pause','paused':value,'tick':int(self.now)})

    def enqueue(self,actions):
        order={'transition':0,'section':1,'sting':2,'duck':3}
        for action in sorted(actions,key=lambda a:(a['t'],order.get(a['kind'],4))):
            if action['kind'] in ('suspend','resume'):continue # immediate host-owned transport policy
            if action['kind']=='transition' or action['kind']=='silence':
                # A new encounter/floor/end cadence replaces old future plans.
                self.queue=[item for item in self.queue if item[0]<action['t']]
                heapq.heapify(self.queue)
            if len(self.queue)>=64:raise ValueError('Adaptive action queue exceeded its bound')
            self.serial+=1;heapq.heappush(self.queue,(action['t'],self.serial,action))

    def advance(self,tick):
        self.now=max(self.now,float(tick))
        dirty=False
        if self.sting and tick>=self.sting['until']:
            self.sting=None;dirty=True
        if self.duck_until is not None and tick>=self.duck_until:
            self.duck_until=None;self.duck_mask=[];dirty=True
        while self.queue and self.queue[0][0]<=tick:
            scheduled,_,action=heapq.heappop(self.queue)
            kind,payload=action['kind'],action['payload']
            if kind in ('section','transition'):
                self.kind=payload['state'] if kind=='section' else payload['kind']
                self.floor=payload.get('floor',self.floor)
                self.base=document(self.engine,self.kind,self.floor,self.env,scheduled)
                if kind=='transition':
                    self.sting=None;self.duck_mask=[];self.duck_until=None
                self.silent=False;dirty=True
            elif kind=='sting':
                notes=compose_sting(self.engine.profiles[self.env],self.engine.seed,payload['sting'],payload.get('cue_id',''))
                # Real tracker cells start on sixteenths; the prototype's
                # finer 240-tick grid is rounded forward, never backwards.
                start=math.ceil(max(scheduled,tick)/ROW)*ROW
                out=[];cursor=start
                for note in notes:
                    gate=min(float(note['gate']),4.)
                    out.append((int(cursor),note['midi'],note['vel'],gate));cursor+=int(gate*ROW)
                self.sting={'notes':out,'until':cursor+ROW};dirty=True
            elif kind=='duck':
                self.duck_mask=list(payload['mask']);self.duck_until=payload['until'];dirty=True
            elif kind=='silence':self.silent=True;self.sting=None;dirty=True
            elif kind=='reset':continue # native seed/revision reset constructs a fresh engine
            self.log({'type':'action','tick':tick,'scheduled':scheduled,'kind':kind,
                      'state':self.kind,'late_ms':round(max(0,tick-scheduled)*60000/self.base['bpm']/TICKS,2)})
        if dirty:self.publish()


def fixture(seconds):
    bosses=[{'name':n,'phase':'sealed','health':300,'max_health':300,'on_seal':False,'open_ticks':0,'attacks':0}
            for n in ('REPETIEL','SCRIPTORAX')]
    game={'seed':20261031,'revision':1,'map':1,'health':100,'weapon':'pistol','ammo':50,'kills':0,
          'secrets':0,'paused':False,'dead':False,'won':False,'argon':{'warnings':0},'bosses':bosses,
          'environment':{'id':'drowned_records'}}
    if seconds>=2:game['health']=82;game['ammo']=49
    if seconds>=5:bosses[0]['on_seal']=True
    if seconds>=8:bosses[0].update(phase='exposed',open_ticks=180)
    if seconds>=12:bosses[0].update(phase='bound',health=0,on_seal=False,open_ticks=0)
    if seconds>=16:bosses[1].update(phase='bound',health=0)
    if seconds>=20:game['map']=2;game['bosses']=[]
    return game


def terminal_cues(cues,game):
    # Native damage/boss changes can arrive in the same snapshot as death.
    # Lower-priority handlers must not revive the arrangement afterward.
    if game.get('dead'):return [c for c in cues if c.type=='player_death']
    if game.get('won'):return [c for c in cues if c.type=='run_victory']
    return cues


def run(args):
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    log_file=(output/'events.jsonl').open('a',buffering=1)
    def log(event):log_file.write(json.dumps(dict(wall=time.monotonic(),**event),allow_nan=False)+'\n')
    info=json.loads(Path(args.studio).read_text());studio=Studio(info);backend=Backend(studio,log)
    if args.fixture:
        until=time.monotonic()+90
        while not studio.get().get('playing'):
            if time.monotonic()>until:raise RuntimeError('Fixture waited too long for capture Play')
            time.sleep(.1)
    started=time.monotonic();stopped=[False]
    signal.signal(signal.SIGTERM,lambda *_:stopped.__setitem__(0,True))
    signal.signal(signal.SIGINT,lambda *_:stopped.__setitem__(0,True))
    previous=None;context=None;engine=None;sequence=0;last_activity=None;last_combat_end=None
    def cue(kind,payload,tick,confirm=None):
        nonlocal sequence
        sequence+=1;return Cue(f'live-{sequence}',tick,kind,payload,confirm=confirm)
    last_status=0.
    while not stopped[0] and (not args.seconds or time.monotonic()-started<args.seconds):
        loop=time.monotonic()
        if args.fixture:
            elapsed=loop-started
            game=fixture(elapsed%6 if args.fixture_seeds else elapsed)
            if args.fixture_seeds:
                n=int(elapsed//6)
                game.update(seed=20261031+n,revision=1+n)
                game['environment']={'id':('drowned_records','switchyard_chapel','after_hours_pavilion')[n%3]}
        else:
            with urllib.request.urlopen(args.game+'/state',timeout=2) as response:game=json.load(response)
        if game.get('loading') or game.get('error'):
            backend.pause(True);time.sleep(.1);continue
        current_context=(game['seed'],game['revision'])
        env=(game.get('environment') or {}).get('id','drowned_records')
        terminal=bool(game.get('dead') or game.get('won'))
        paused=bool(game.get('paused')) and not terminal
        if current_context!=context:
            context=current_context;engine=Engine(game['seed'],env,materialize=False)
            engine.director.floor=game['map'];engine.director.env=env
            engine.director.begin(0);engine.director.take_actions()
            backend.reset(engine,game['map'],env,paused)
            previous=copy.deepcopy(game);last_activity=None;last_combat_end=None
            # A music-only restart can attach to an already active encounter.
            # Reconcile the current authoritative phases rather than treating
            # them as if this host had already received those cue edges.
            previous['dead']=False;previous['won']=False
            for boss in previous.get('bosses') or []:
                boss.update(phase='sealed',health=boss.get('max_health',boss.get('health',1)),
                            on_seal=False,open_ticks=0,attacks=0)
            if paused:engine.live(cue('pause',{},0),0);engine.director.take_actions()
        snapshot=studio.get();tick=backend.clock(snapshot)
        cues=[]
        if paused!=backend.paused:
            backend.pause(paused)
            cues.append(cue('pause' if paused else 'resume',{},tick))
        if previous is not None:
            cues.extend(c for c in propose(previous,game,tick,env_map={game.get('floor_name'):env},auto_id=f'snapshot-{sequence}')
                        if c.type not in ('pause','resume'))
            firing=(game.get('weapon')==previous.get('weapon') and game.get('ammo',0)<previous.get('ammo',0))
            hurt=game.get('health',0)<previous.get('health',0)
            warned=(game.get('argon') or {}).get('warnings',0)>(previous.get('argon') or {}).get('warnings',0)
            killed=game.get('kills',0)>previous.get('kills',0)
            if not paused and not terminal and (firing or hurt or warned or killed):
                last_activity=tick;last_combat_end=None
                if engine.director.state in ('exploration','quiet','threat','start'):
                    cues.append(cue('combat_start',{},tick))
                if warned:cues.append(cue('enemy_sting',{'enemy':'native_warning'},tick))
            if game.get('secrets',0)>previous.get('secrets',0):cues.append(cue('secret',{},tick))
            if last_activity is not None and tick-last_activity>12*TICKS and engine.director.state=='combat' and last_combat_end is None:
                cues.append(cue('combat_end',{},tick));last_combat_end=tick
        for event in sorted(terminal_cues(cues,game),key=lambda c:(-PRIORITY[c.type],c.id)):
            sequence+=1
            if event.type in ('combat_start','combat_end','enemy_sting') and engine.director.state.startswith('boss'):continue
            actions=engine.live(event,tick);backend.enqueue(actions)
            log({'type':'cue','cue':event.type,'tick':tick,'state':engine.director.state})
        backend.enqueue(engine.live_advance(tick));backend.advance(tick)
        previous=copy.deepcopy(game)
        if loop-last_status>.5:
            status={'state':'running','tick':tick,'director':engine.director.state,'arrangement':backend.kind,
                    'environment':env,'seed':game['seed'],'native_revision':game['revision'],'floor':game['map'],'paused':paused,
                    'pending_actions':len(backend.queue),'studio_calls':studio.calls,
                    'maximum_api_ms':round(studio.maximum_ms,3),'last_publish':backend.last_publish}
            tmp=output/'status.tmp';tmp.write_text(json.dumps(status,indent=2)+'\n');tmp.replace(output/'status.json')
            last_status=loop
        time.sleep(max(0,.05-(time.monotonic()-loop)))
    backend.pause(True)
    tmp=output/'status.tmp';tmp.write_text(json.dumps({'state':'stopped','paused':True,'tick':int(backend.now)})+'\n');tmp.replace(output/'status.json')
    log_file.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--studio',required=True)
    parser.add_argument('--game',default='http://127.0.0.1:8773')
    parser.add_argument('--output',required=True)
    parser.add_argument('--fixture',action='store_true')
    parser.add_argument('--fixture-seeds',action='store_true')
    parser.add_argument('--seconds',type=float,default=0)
    args=parser.parse_args()
    try:run(args)
    except Exception as exc:
        output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
        (output/'status.json').write_text(json.dumps({'state':'failed','error':type(exc).__name__+': '+str(exc)})+'\n')
        raise
