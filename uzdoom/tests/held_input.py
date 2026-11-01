# SPDX-License-Identifier: GPL-3.0-or-later
"""Hold real Game.input movement continuously across six native map changes."""
from pathlib import Path
import argparse,importlib.util,json,math,os,time,zipfile,shutil
from uzdoom.engine import Engine

FIXTURE=r'''
class NRInputProbe : StaticEventHandler {
 override void OnRegister(){SetOrder(100);}
 override void WorldLoaded(WorldEvent e){
  if(level.levelnum<2)return;let p=players[0].mo;if(!p)return;
  // A straight service-hall lane isolates button state from spawn geometry.
  p.SetOrigin((12352,224,(level.levelnum-1)*512),false);p.FindFloorCeiling();p.Vel=(0,0,0);p.Angle=0;p.Pitch=0;p.ClearInterpolation();
 }
 override void NetworkProcess(ConsoleEvent e){if(e.Name=="nr_input_next")Exit_Normal(0);}
 override void WorldTick(){
  let p=players[0].mo;if(!p || level.time%7)return;
  Console.Printf("NRRECEIPT {\"fixture\":\"input_tick\",\"map\":%d,\"tics\":%d,\"x\":%.3f,\"y\":%.3f,\"z\":%.3f,\"floor\":%.3f,\"ceiling\":%.3f,\"reaction\":%d,\"forward\":%d,\"side\":%d}",level.levelnum,level.time,p.Pos.X,p.Pos.Y,p.Pos.Z,p.FloorZ,p.CeilingZ,p.ReactionTime,p.player.cmd.forwardmove,p.player.cmd.sidemove);
 }
}
'''


def run(a):
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    if a.game_source:
        spec=importlib.util.spec_from_file_location('uzdoom.baseline_game',a.game_source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    else:import uzdoom.game as module
    saved=json.loads((a.pk3.parent/'manifest.json').read_text())
    with zipfile.ZipFile(a.pk3) as z:files={n:z.read(n) for n in z.namelist()}
    files['ZSCRIPT']+=b'\n#include "input-probe.zs"\n';files['input-probe.zs']=FIXTURE.encode()
    files['MAPINFO']=files['MAPINFO'].replace(b'AddEventHandlers = "NRDirector"',b'AddEventHandlers = "NRDirector", "NRInputProbe"')
    pk3=out/'test.pk3'
    with zipfile.ZipFile(pk3,'w',zipfile.ZIP_DEFLATED) as z:
        for n,data in files.items():z.writestr(n,data)
    def build(seed,wad,folder,*args,**kwargs):
        folder.mkdir();shutil.copy2(pk3,folder/'nullrun.pk3');return saved
    class ProbeEngine(Engine):
        def __init__(self,*args,**kwargs):
            kwargs['extra_config']=f'vid_maxfps {a.fps}; bind b "netevent nr_input_next"';super().__init__(*args,**kwargs)
    original_build,original_engine=module.build,module.Engine;module.build=build;module.Engine=ProbeEngine
    os.environ.update(UZDOOM_BINARY=str(a.engine),UZDOOM_BRIDGE=str(a.bridge),NULLRUN_SEED=str(saved['seed']))
    report={'state':'running','checks':[],'scope':'Real Game.input and native Exit_Normal, same held movement throughout transitions. Test-only straight lane placement isolates input from world geometry; no incoming button resets in the fixture.'}
    game=None
    try:
        game=module.Game(a.iwad,out/'runs');owner=game.acquire()
        def drive(seconds,keys=('KeyW',)):
            until=time.monotonic()+seconds
            while time.monotonic()<until:
                game.input(owner,list(keys));time.sleep(.035)
                if game.error:raise RuntimeError(game.error)
        def ticks(count,keys=('KeyW',)):
            target=game.snapshot()['level_tics']+count;until=time.monotonic()+15
            while game.snapshot()['level_tics']<target:
                if time.monotonic()>until:raise TimeoutError('Native ticks did not advance: '+str(game.snapshot()))
                drive(.04,keys)
        drive(.15)
        for target in range(2,8):
            game.engine.key(98,True);drive(.16);game.engine.key(98,False)
            until=time.monotonic()+12
            while game.snapshot().get('map')!=target:
                if time.monotonic()>until:raise TimeoutError('Floor transition')
                drive(.04)
            start=game.snapshot();ticks(28);held=game.snapshot()
            distance=math.hypot(held['x']-start['x'],held['y']-start['y'])
            row={'map':target,'held_distance':distance,'resyncs':held.get('input_resyncs'),
                 'start':[start[k] for k in ('x','y','z')],'end':[held[k] for k in ('x','y','z')],
                 'native_input':game.engine.receipts[-5:],'effect':held.get('creatures'),'paused':held['paused'],'health':held['health']}
            report['checks'].append(row)
            if a.expect_stale:
                assert distance<.1,row
                ticks(7,());ticks(21);pressed=game.snapshot();row['fresh_press_distance']=math.hypot(pressed['x']-held['x'],pressed['y']-held['y'])
                assert row['fresh_press_distance']>2,row
            else:assert distance>2,row
            print(json.dumps({k:row.get(k) for k in ('map','held_distance','resyncs','fresh_press_distance')}),flush=True)
        game.input(owner,[],paused=True);report['state']='reproduced' if a.expect_stale else 'passed'
    except BaseException as error:report.update(state='failed',error=str(error));raise
    finally:
        if game:game.close()
        module.build,module.Engine=original_build,original_engine
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('pk3','output','engine','bridge','iwad'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--game-source',type=Path);p.add_argument('--expect-stale',action='store_true');p.add_argument('--fps',type=int,choices=(15,60),default=15);run(p.parse_args())
