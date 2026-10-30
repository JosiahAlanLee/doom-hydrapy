# SPDX-License-Identifier: GPL-2.0-or-later
import base64,copy,json,os,shutil,sys
from pathlib import Path
import numpy as np
REPO=Path(__file__).resolve().parent;ROOT=Path(os.environ.get('DOOM_TAKE_ROOT',str(REPO.parent/'doom-hydrapy-20261030')))
OLD=REPO.parent/'gorgon-r3b-20261030'
sys.path.insert(0,str(OLD/'runtime'))
from hydrapy.tracker_v3 import validate,empty_pattern

def generate(smoke=False):
    prefix='smoke' if smoke else 'poly';workspace=ROOT/(prefix+'-workspace');workspace.mkdir(exist_ok=True)
    schedule=json.loads((ROOT/'poly/schedule.json').read_text())
    if smoke:
        ev=[]
        offs={e[6]:e for e in schedule['events'] if e[1]==0}
        for i,tr in enumerate(schedule['tracks']):
            start=tr['start'];stop=start+3
            for original in schedule['events']:
                if not start<=original[0]<stop:continue
                if original[1] in (2,3):
                    event=copy.copy(original);event[0]=event[0]-start+i*3;ev.append(event)
                elif original[1]==1:
                    end=min(offs[original[6]][0],stop-1/48000)
                    if end<=original[0]:continue
                    event=copy.copy(original);event[0]=event[0]-start+i*3;ev.append(event)
                    off=copy.copy(offs[original[6]]);off[0]=end-start+i*3;ev.append(off)
        schedule['events']=sorted(ev,key=lambda e:(e[0],e[1]));(ROOT/'poly/smoke-schedule.json').write_text(json.dumps(schedule))
    score=json.loads((OLD/'score.json').read_text());score.update(bpm=120,loop=False,pattern=0,chain=[0,1,2,3,4],seed=20261030,sound=False,patterns=[None]*128,mutes=[True]*6)
    names=['doom-melt','doom-disk','doom-vector','doom-relief'] if os.environ.get('DOOM_INDUSTRIAL')=='1' else ['doom-terminal','doom-print','doom-scan','doom-feedback']
    for i,name in enumerate(names):
        p=empty_pattern(i);rows=6 if smoke else 120;p.update(name=name,rate=.25,bar=rows if smoke else 30,bars=1 if smoke else 4)
        p['lanes']=[dict(len=rows,cells=[None]*rows,transforms=[]) for _ in range(6)];p['scenes']=[dict(r=0,name=name,fade=0)];p['keys']['z']=[dict(r=0,v=(i*(3 if smoke else 60))/240),dict(r=rows-1,v=(i*(3 if smoke else 60)+(rows-1)*.5)/240)];p['easing']['z']='linear';score['patterns'][i]=p
    tail=empty_pattern(4);tail["keys"]["z"]=[dict(r=0,v=(12 if smoke else 240)/240)];score["patterns"][4]=tail
    score["modes"]={"program":"o1","aux":"o0"}
    validate(score);(ROOT/(prefix+'-score.json')).write_text(json.dumps(score))
    (workspace/'.hydrapy').mkdir(exist_ok=True);(workspace/'.hydrapy/tracker.json').write_text(json.dumps(score))
    # Patch remains in GPL repo; workspace is only a tiny import shim.
    (workspace/'studio_live.py').write_text(f"import sys\nsys.path.insert(0,{str(REPO)!r})\nfrom performance import *\n")
    modules=[dict(id=1,plugin='GorgonBridge',model='Gorgon',pos=[0,0],params=[],data=dict(ppqn=32,audio={})),dict(id=2,plugin='DoomPoly',model='Stream',pos=[32,0],params=[],data=dict(schedule=str(ROOT/'poly'/('smoke-schedule.json' if smoke else 'schedule.json')),proof=str(ROOT/(prefix+'-gate-proof.bin')))),dict(id=3,plugin='Core',model='AudioInterface16',pos=[50,0],params=[],data=dict(audio={}))]
    cables=[]
    def cable(out,oid,inp,iid):cables.append(dict(id=len(cables)+1,outputModuleId=out,outputId=oid,inputModuleId=inp,inputId=iid))
    cable(1,2,2,0);cable(1,0,2,1);cable(1,8,2,66)
    # Original substitute drum samples. No id samples or music recordings.
    rng=np.random.default_rng(20261030);sr=29760;t=np.arange(int(sr*.8))/sr
    samples=[]
    samples.append(np.sin(2*np.pi*(48*t+90*.025*(1-np.exp(-t/.025))))*np.exp(-t*12))
    noise=rng.normal(0,1,len(t));samples.append((noise*.65+np.sin(2*np.pi*180*t)*.35)*np.exp(-t*18))
    noise=rng.normal(0,1,len(t));samples.append((noise-np.roll(noise,1))*.4*np.exp(-t*40))
    samples.append(np.sin(2*np.pi*(110*t+40*.03*(1-np.exp(-t/.03))))*np.exp(-t*9))
    noise=rng.normal(0,1,len(t));samples.append((noise-np.roll(noise,1))*.3*np.exp(-t*5))
    samples.append((np.sign(np.sin(2*np.pi*540*t))+np.sign(np.sin(2*np.pi*800*t)))*.25*np.exp(-t*14))
    samples.append(np.sin(2*np.pi*700*t)*np.exp(-t*65))
    noise=rng.normal(0,1,len(t));samples.append(noise*.5*np.exp(-t*28))
    for route in schedule['routes']:
        idx=route['index'];mid=100+idx;inst=route['instrument'];data={};params=[]
        if inst=='PVX':
            config=json.loads((ROOT/'pvx-routing.json').read_text())
            plugin=config['plugin'];audioport=config['audio'];pitchport=config['pitch'];gateport=config['gate']
            params=[dict(id=int(k),value=v) for k,v in config.get('params',{}).get(str(route['channel']),{}).items()]
        elif inst=='CZish':
            plugin='CZishLab';params=[dict(id=k,value=v) for k,v in [(0,(idx%3)),(5,.7),(8,0),(4,160)]];audioport=2;pitchport=0;gateport=1
            # schema omitted intentionally: installed plugin migrates legacy envelope times.
        elif inst=='Vastish':
            plugin='VastishLab';audioport=0;pitchport=0;gateport=1
            preset={1:3,2:4,4:2,5:3,7:5,8:4,10:1}.get(route['channel'],1)
            table=json.loads((REPO/'vastish_presets.json').read_text());params=[dict(id=k,value=v) for k,v in enumerate(table[preset])];data=dict(program=preset)
        else:
            plugin='OtisLab';audioport=0;pitchport=1;gateport=2
            pcm=np.clip(samples[route['family']]*20000,-32767,32767).astype('<i2')
            data=dict(schema=1,rate=sr,name='Doom substitute family '+str(route['family']),pcm16le=base64.b64encode(pcm.tobytes()).decode(),engineMode=0,filterMode=2,gated=False,linearLevel=True,declick=True)
            params=[dict(id=6,value=.7)]
        modules.append(dict(id=mid,plugin=plugin,model=config['model'] if inst=='PVX' else inst,pos=[idx*40,380],params=params,data=data))
        cable(2,idx*3,mid,pitchport);cable(2,idx*3+1,mid,gateport)
        if inst=='Vastish':cable(2,idx*3+2,mid,2)
        if inst=='PVX' and config.get('velocity') is not None:cable(2,idx*3+2,mid,config['velocity'])
        if inst=='OtisSampler':cable(2,idx*3+2,mid,8)
        cable(2,idx*3+1,2,2+idx) # physical gate return for edge audit
        cable(mid,audioport,2,34+idx)
    modules.append(dict(id=50,plugin='SpoonBenderLab',model='SpoonBender',pos=[80,0],params=[dict(id=k,value=v) for k,v in [(0,.3),(1,.18),(5,.1),(14,.12),(16,.2)]],data={}))
    cable(2,96,50,0);cable(2,97,50,1);cable(50,0,3,0);cable(50,1,3,1)
    cable(2,98,3,15)
    patch=ROOT/(prefix+'-rack.vcv');patch.write_text(json.dumps(dict(version='2.6.6',modules=modules,cables=cables)))
    rig=json.loads((OLD/'rig.json').read_text());rig['workspace']=str(workspace);rig['rack']['patch']=str(patch)
    rig['rack']['user_dir']=str(OLD/'take/rack-user');rig['capture']['prewarm']=True;rig['audio']['quantum']=2048
    # Child env is inherited by capture's Studio and Rack processes.
    (ROOT/(prefix+'-rig.json')).write_text(json.dumps(rig,indent=2))
    print(prefix,'prepared',len(modules),'modules',len(cables),'cables')
if __name__=='__main__':generate('--smoke' in sys.argv)
