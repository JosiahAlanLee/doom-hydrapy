# SPDX-License-Identifier: GPL-3.0-or-later
"""Reproduce a stale ReDead stun across a real native floor transition."""
from pathlib import Path
import argparse,json,time,zipfile,math
from uzdoom.engine import Engine

FIXTURE=r'''
class NRTransitionProbe : StaticEventHandler {
 bool Armed;
 override void OnRegister(){SetOrder(100);}
 override void NetworkProcess(ConsoleEvent e){
  if(e.Name!="nr_transition")return;let h=NRDirector.Get();let p=players[0].mo;if(!h||!p)return;
  h.Credits=44;h.Ranks[4]=1;p.GiveInventory('Shotgun',1);p.GiveInventory('Shell',8);
  // Model a recent encounter's deadlines on the outgoing floor's clock.
  h.ShriekUntil=level.time+10000;h.ImmunityUntil=level.time+11000;
  h.FlashUntil=level.time+12000;h.GripAt=level.time+1;h.GripDamageAt=level.time+35;h.EscapeTicks=17;
  Armed=true;Exit_Normal(0);
 }
 override void WorldLoaded(WorldEvent e){
  if(!Armed)return;let h=NRDirector.Get();let p=players[0].mo;
  bool reset=h.ShriekUntil==0 && h.ImmunityUntil==0 && h.FlashUntil==0 && h.GripAt==0 && h.GripDamageAt==0 && h.EscapeTicks==0 && !h.Holder;
  bool preserved=h.Credits==44 && h.Ranks[4]==1 && p.FindInventory('Shotgun') && p.FindInventory('Shell');
  Console.Printf("NRRECEIPT {\"fixture\":\"transition\",\"map\":%d,\"timers_reset\":%s,\"run_preserved\":%s,\"shriek_deadline\":%d}",level.levelnum,reset?"true":"false",preserved?"true":"false",h.ShriekUntil);
  Armed=false;
 }
}
'''


def run(a):
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(a.pk3) as z:files={n:z.read(n) for n in z.namelist()}
    files['ZSCRIPT']+=b'\n#include "transition-probe.zs"\n';files['transition-probe.zs']=FIXTURE.encode()
    files['MAPINFO']=files['MAPINFO'].replace(b'AddEventHandlers = "NRDirector"',b'AddEventHandlers = "NRDirector", "NRTransitionProbe"')
    pk3=out/'test.pk3'
    with zipfile.ZipFile(pk3,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)
    report={'state':'running','checks':[],'scope':'Real Exit_Normal transitions, real player inputs and collision. Test-only outgoing deadlines and run upgrades; no test setup resets the incoming timers.'}
    e=Engine(a.engine,a.bridge,a.iwad,pk3,out/'engine',extra_config='vid_maxfps 15; bind b "netevent nr_transition"')
    try:
        for target in ([2] if a.expect_stale else [2,3]):
            with e.lock:e.receipts.clear()
            e.pause(False);e.key(98,True);time.sleep(.16);e.key(98,False)
            e.wait(lambda:e.latest.get('map')==target,12)
            e.wait(lambda:any(r.get('fixture')=='transition' and r.get('map')==target for r in e.receipts),5)
            receipt=next(r for r in reversed(e.receipts) if r.get('fixture')=='transition' and r.get('map')==target)
            time.sleep(.15);start=e.state();distance=0
            for key in [119,115,97,100]:
                e.key(key,True);time.sleep(.23);e.key(key,False);time.sleep(.17)
                now=e.state();distance=math.hypot(now['x']-start['x'],now['y']-start['y'])
                if distance>2:break
            e.pause(True)
            row={**receipt,'movement_distance':distance,'effect':now['creatures']['effect']};report['checks'].append(row)
            if a.expect_stale:
                assert not receipt['timers_reset'] and distance<.01 and row['effect']=='shriek',row
            else:
                assert receipt['timers_reset'] and receipt['run_preserved'] and distance>2 and row['effect'] is None,row
            print(json.dumps(row),flush=True)
        report['state']='reproduced' if a.expect_stale else 'passed'
    except BaseException as error:
        report['state']='failed';report['error']=str(error);raise
    finally:
        e.close();(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('pk3','output','engine','bridge','iwad'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--expect-stale',action='store_true');run(p.parse_args())
