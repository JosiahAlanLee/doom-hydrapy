# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise real UZDoom gameplay in an explicitly instrumented test-only PK3."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,time,zipfile
import numpy as np
from PIL import Image
from uzdoom.engine import Engine

def run(args):
    root=args.output.resolve();root.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(args.pk3) as z:files={n:z.read(n) for n in z.namelist()}
    assert not any('fixture' in n.lower() for n in files),'Production input contains test fixture'
    files['ZSCRIPT']+=b'\n#include "native_fixture.zs"\n'
    files['native_fixture.zs']=Path(__file__).with_name('native_fixture.zs').read_bytes()
    files['MAPINFO']=files['MAPINFO'].replace(b'AddEventHandlers = "NRDirector"',b'AddEventHandlers = "NRDirector", "NRFixture"')
    pk3=root/'instrumented.pk3'
    with zipfile.ZipFile(pk3,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)
    (root/'compiler.ini').write_text('[GlobalSettings]\nvid_preferbackend=0\nvid_rendermode=4\n')
    env=dict(os.environ,SDL_VIDEODRIVER='offscreen',XDG_CONFIG_HOME=str(root/'compile-config'),XDG_CACHE_HOME=str(root/'compile-cache'))
    compiled=subprocess.run([str(args.engine),'-iwad',str(args.iwad),'-config',str(root/'compiler.ini'),'-file',str(pk3),
                             '-errorlog',str(root/'compiler-error.log'),'-noautoload','-nosound'],env=env,cwd=root,capture_output=True,text=True,timeout=35)
    (root/'compiler.log').write_text(compiled.stdout+'\n'+compiled.stderr)
    # UZDoom's compile-only success sentinel is1337 (exit status57 on POSIX).
    if compiled.returncode not in (0,57) or 'Script error' in compiled.stdout:raise RuntimeError('Native fixture compilation failed; inspect compiler.log')
    report={'state':'running','production_sha256':hashlib.sha256(args.pk3.read_bytes()).hexdigest(),
            'fixture_sha256':hashlib.sha256(files['native_fixture.zs']).hexdigest(),'checks':[],'limits':'Test-only setup places actors and clears unrelated encounters; this is mechanics validation, not a complete human combat-balance playthrough.'}
    def save():
        (root/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    save()
    e=Engine(args.engine,args.bridge,args.iwad,pk3,root/'engine',extra_config='bind b "netevent nr_fixture 0"; bind x "netevent nr_fixture 1"; bind n "netevent nr_fixture 2"')
    held=set()
    def hold(key,on=True):e.key(key,on);held.add(key) if on else held.discard(key)
    def fixture(code,tag):
        with e.lock:e.receipts.clear()
        e.pulse(code);e.wait(lambda:any(r.get('fixture')==tag for r in e.receipts),4)
        with e.lock:return next(r for r in reversed(e.receipts) if r.get('fixture')==tag)
    def live(seconds):e.pause(False);time.sleep(seconds)
    labels=['native UPKEEP purchase and capacities','health-cap purchase, native healing and preserved overheal',
            'native incoming damage reduction','ammo capacity before weapon pickup and native Backpack',
            'Hollow freezes when watched and hunts when unobserved','ReDead warning, grip and actual use-key escape',
            'Repetiel separate use edges expose and allow native death','Calmor native stillness binding',
            'Probator actual weapon shield impact then acknowledgement','Jurisiel actual movement from A to B',
            'bidirectional physical corridor folds preserve pitch','blocked fold keeps the player on the source side',
            'unobserved sector mutation changes native collision','native collision stair climb reaches480',
            'seven native levels preserve run upgrades and end in victory',
            'Surveyor warning and native line attack','Ballast Husk warning and arc damage','False Door warning and close damage',
            'Spindle launches an actual homing spore','Latchwing telegraph and physical contact dash','Relay Choir launches three native spores']
    try:
        first=e.frame()[:,:,:3];Image.fromarray(first).save(root/'startup.png')
        report['startup_texture_roughness']=float(np.abs(np.diff(first.astype(float),n=2,axis=1)).mean())
        if report['startup_texture_roughness']<.3:raise AssertionError('Startup picture is still the stale buffer')
        for test_id,label in enumerate(labels):
            item={'id':test_id,'name':label}
            try:
                e.pause(True)
                for key in list(held):hold(key,False)
                ready=fixture(98,'ready');assert ready['case']==test_id,ready
                live(.15)
                if test_id in (0,1):
                    e.pulse(102);e.wait(lambda:e.latest['vending']['menu_open'])
                    e.pause(True);result=e.buy(e.latest['map'],0);assert result['ok'],result
                    duplicate=e.buy(e.latest['map'],0);assert not duplicate['ok'],'Duplicate purchase succeeded'
                elif test_id==4:
                    e.wait(lambda:e.latest['mobs'][0]['frozen']);before=e.latest['mobs'][0].copy();time.sleep(.2)
                    assert e.latest['mobs'][0]['x']==before['x'],'Watched Hollow moved'
                    e.move(1024);e.wait(lambda:not e.latest['mobs'][0]['frozen']);time.sleep(.5)
                elif test_id==5:
                    e.wait(lambda:any(m.get('class')==8 and m.get('phase')==1 and 0<m.get('warning_ticks',0)<=28 for m in e.latest.get('mobs',[])),3)
                    item['native_warning_telemetry']='28-tick mask phase, not lunge'
                    e.wait(lambda:e.latest['creatures']['effect']=='grip',5);hold(102)
                    e.wait(lambda:e.latest['creatures']['effect']!='grip',3);hold(102,False)
                elif test_id==6:
                    e.pulse(102);time.sleep(.15);e.pulse(102);e.wait(lambda:e.latest['bosses'][0]['phase']=='exposed')
                elif test_id==7:e.wait(lambda:e.latest['bosses'][0]['phase']=='exposed',4)
                elif test_id==8:
                    time.sleep(.6);hold(1073742048);e.wait(lambda:e.latest['bosses'][0]['proof'],3);hold(1073742048,False)
                    e.pulse(102);e.wait(lambda:e.latest['bosses'][0]['phase']=='exposed')
                elif test_id==9:
                    hold(119);e.wait(lambda:e.latest['bosses'][0]['phase']=='exposed',4);hold(119,False)
                elif test_id==10:
                    hold(119);e.wait(lambda:e.latest['architecture']['swaps']>=1);hold(119,False)
                    e.move(1024);time.sleep(.1);hold(119);e.wait(lambda:e.latest['architecture']['swaps']>=2);hold(119,False)
                elif test_id==11:
                    hold(119);e.wait(lambda:e.latest['architecture']['blocked']>0);time.sleep(.15);hold(119,False)
                elif test_id==12:
                    time.sleep(.5);assert e.latest['architecture']['mutations']==0,'Mutation happened while watched'
                    e.move(1024);e.wait(lambda:e.latest['architecture']['mutations']==1,3)
                elif test_id==13:
                    e.wait(lambda:any(r.get('fixture')=='climb_done' for r in e.receipts),40)
                elif test_id==14:
                    for target in range(2,8):
                        e.pulse(102);e.wait(lambda:e.latest['map']==target,10)
                        state=e.state();assert state['vending']['credits']==44 and state['vending']['perks'][4]['rank']==1,'Run state lost at level change'
                        e.pause(True);fixture(110,'ready');live(.15)
                    e.pulse(102);e.wait(lambda:e.latest['won'],3)
                elif test_id>=15:
                    e.wait(lambda:e.latest['argon']['warnings']>0,3)
                    Image.fromarray(e.frame()[:,:,:3]).save(root/f'warning-{test_id:02}.png')
                    e.wait(lambda:e.latest['mobs'][0]['attack_count']>0,4)
                    if test_id in (15,16,17,19):e.wait(lambda:e.latest['health']<100,3)
                e.pause(True);checked=fixture(120,'check');assert checked['ok'],checked
                item.update(state='passed',detail=checked['detail'])
                Image.fromarray(e.frame()[:,:,:3]).save(root/f'case-{test_id:02}.png')
            except Exception as error:item.update(state='failed',error=str(error))
            report['checks'].append(item);save();print(json.dumps(item),flush=True)
        report['state']='passed' if all(c['state']=='passed' for c in report['checks']) else 'failed'
    finally:
        e.close();save()
    return report['state']=='passed'

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('engine','bridge','iwad','pk3','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('engine','bridge','iwad','pk3'):setattr(a,name,getattr(a,name).resolve())
    raise SystemExit(0 if run(a) else 1)
