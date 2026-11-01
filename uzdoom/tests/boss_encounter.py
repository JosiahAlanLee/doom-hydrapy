# SPDX-License-Identifier: GPL-3.0-or-later
"""Reproduce the last human-play boss pair, including held-use acknowledgement."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,time,zipfile
from PIL import Image
from uzdoom.engine import Engine
from uzdoom.hud import decorate


def run(args):
    root=args.output.resolve();root.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(args.pk3) as z:files={n:z.read(n) for n in z.namelist()}
    assert not any('fixture' in n.lower() for n in files)
    files['ZSCRIPT']+=b'\n#include "boss_encounter_fixture.zs"\n'
    files['boss_encounter_fixture.zs']=Path(__file__).with_name('boss_encounter_fixture.zs').read_bytes()
    files['MAPINFO']=files['MAPINFO'].replace(b'AddEventHandlers = "NRDirector"',b'AddEventHandlers = "NRDirector", "NRBossEncounterFixture"')
    pk3=root/'instrumented.pk3'
    with zipfile.ZipFile(pk3,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)
    (root/'compiler.ini').write_text('[GlobalSettings]\nvid_preferbackend=0\nvid_rendermode=4\n')
    env=dict(os.environ,SDL_VIDEODRIVER='offscreen',XDG_CONFIG_HOME=str(root/'compile-config'))
    p=subprocess.run([str(args.engine),'-iwad',str(args.iwad),'-config',str(root/'compiler.ini'),'-file',str(pk3),'-errorlog',str(root/'compiler-error.log'),'-noautoload','-nosound'],env=env,cwd=root,capture_output=True,text=True,timeout=35)
    (root/'compiler.log').write_text(p.stdout+'\n'+p.stderr)
    if p.returncode not in (0,57) or 'Script error' in p.stdout:raise RuntimeError('Encounter fixture compile failed')
    report={'production_sha256':hashlib.sha256(args.pk3.read_bytes()).hexdigest(),'state':'running','checks':[],
            'limits':'Both authored bosses/seals remain. Other enemies are removed, attacks held off and player health raised for repeatable mechanics checks; this does not establish human difficulty.'}
    def check(name,okay,**detail):
        report['checks'].append(dict(name=name,ok=bool(okay),**detail))
        (root/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report['checks'][-1]),flush=True)
        assert okay,name
    binds='; '.join(f'bind {key} "netevent nr_boss_encounter {n}"' for n,key in enumerate('bzxcvnmq'))
    e=Engine(args.engine,args.bridge,args.iwad,pk3,root/'engine',extra_config=binds)
    def fixture(code):
        with e.lock:e.receipts.clear()
        e.pulse(ord('bzxcvnmq'[code]));e.wait(lambda:any(r.get('fixture')=='encounter' for r in e.receipts),4)
        r=e.receipts[-1];assert r['case']==code and r['ok'],r
        return r
    def shot(name):
        state={**e.state(),'paused':False,'floor_name':'DROWNED RECORDS / 01','floors':7}
        (root/(name+'.json')).write_text(json.dumps(state,indent=2)+'\n')
        world=Image.fromarray(e.frame()).convert('RGBA')
        hud=decorate(Image.new('RGBA',(640,400)),state).resize((1280,800),Image.Resampling.NEAREST)
        Image.alpha_composite(world,hud).convert('RGB').save(root/(name+'.png'))
    try:
        e.pause(False);r=fixture(0);check('authored pair uses reduced health',True,health=[b['max_health'] for b in e.state()['bosses']])
        r=fixture(7);check('both seals and boss badges exist',True,detail=r['detail'])
        fixture(1);e.wait(lambda:e.latest['boss']['name']=='REPETIEL' and e.latest['boss']['on_seal'])
        check('first seal focuses its own boss',True)
        e.key(102,True);e.wait(lambda:e.latest['bosses'][0]['stamps']==1);time.sleep(.4)
        check('held use stays one press with visible progress',e.state()['bosses'][0]['stamps']==1)
        shot('repetition-progress');e.key(102,False);time.sleep(.06);e.pulse(102)
        e.wait(lambda:e.latest['bosses'][0]['phase']=='exposed')
        check('two released presses open a twelve-second window',e.state()['bosses'][0]['open_ticks']>385)
        r=fixture(2);check('proof hit deals damage and records acknowledgement',True,detail=r['detail'])
        e.key(102,True);time.sleep(.1);fixture(3)
        e.wait(lambda:e.latest['boss']['name']=='SCRIPTORAX' and e.latest['boss']['phase']=='exposed')
        e.key(102,False);check('holding use while entering the other seal works and selects it',True)
        shot('proof-open')
        r=fixture(4);check('shield and exposed native damage are sixty and one-fifty percent',True,detail=r['detail'])
        fixture(5);e.wait(lambda:e.latest['bosses'][0]['returning'],3)
        before=e.state()['mobs']
        first=next(m for m in before if m['boss_index']==0)
        e.wait(lambda:not e.latest['bosses'][0]['returning'],40)
        after=next(m for m in e.state()['mobs'] if m['boss_index']==0)
        check('boss returns from last-run chase location to its encounter',True,before=[first['x'],first['y']],after=[after['x'],after['y']])
        r=fixture(6);check('ordinary hits can defeat a shielded boss without ritual',True,detail=r['detail'])
        shot('defeated')
        report['state']='passed'
    except BaseException as error:
        report['state']='failed';report['error']=str(error);raise
    finally:
        e.close();(root/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('engine','bridge','iwad','pk3','output'):p.add_argument('--'+name,type=Path,required=True)
    run(p.parse_args())
