# SPDX-License-Identifier: GPL-3.0-or-later
"""Walk required native collision routes in a private instrumented package."""
from pathlib import Path
from collections import deque
import argparse,json,os,subprocess,time,zipfile,math
from PIL import Image
from uzdoom.build import make_maps,PACKS
from uzdoom.engine import Engine


def run(a):
    OUT=a.output.resolve();OUT.mkdir(parents=True,exist_ok=False)
    SOURCE=a.pk3.resolve();ENGINE=a.engine.resolve();IWAD=a.iwad.resolve();BRIDGE=a.bridge.resolve()
    saved=json.loads((a.manifest or SOURCE.parent/'manifest.json').read_text())
    maps,manifest=make_maps(saved['seed'],PACKS[saved['seed']%len(PACKS)],floor_plan=saved['floor_plan'])
    routes={};details=[]
    for number in range(1,8):
        m=maps[number-1];world=manifest[number-1]['open_world'];indices=[i for i,n in enumerate(m.nodes) if n.get('custom')]
        def nearest(p):return min(indices,key=lambda i:math.dist((m.nodes[i]['x'],m.nodes[i]['y'],m.nodes[i]['z']),p))
        def path(a,b):
            previous={a:None};q=deque([a])
            while q and b not in previous:
                i=q.popleft()
                for j in m.nodes[i]['edges']:
                    if j in indices and j not in previous:previous[j]=i;q.append(j)
            if b not in previous:raise AssertionError('Unreachable required surface')
            result=[b]
            while previous[result[-1]] is not None:result.append(previous[result[-1]])
            return result[::-1]
        roles=['entry','vendor','encounter_a','encounter_b','overlook','pit_recovery','exit']
        targets=[nearest(world['anchors'][r]) for r in roles]
        for n in world['route_graph']['nodes']:
            if n['kind']=='deck':targets.append(nearest((n['x'],n['y'],n['z']+manifest[number-1]['base_altitude'])))
        sequence=[targets[0]];strict={0}
        for goal in targets[1:]:
            sequence.extend(path(sequence[-1],goal)[1:]);strict.add(len(sequence)-1)
        points=[]
        for at,i in enumerate(sequence):
            n=m.nodes[i];step=n.get('stair',False)
            points.append((n['x'],n['y'],n['z'],4 if at in strict else 40 if step else 24,12 if step else 8))
        routes[number]=points;details.append({'map':number,'world':world['id'],'waypoints':len(points),'roles':roles,'deck_surfaces':sum(n['kind']=='deck' for n in world['route_graph']['nodes'])})
    pushes=''.join('if(level.levelnum==%d) {%s}'%(number,''.join('Add((%.6f,%.6f,%.6f),%.3f,%.3f);'%p for p in points)) for number,points in routes.items())
    fixture='''
    class NRWalkPoint : Object { Vector3 Point; double ZTolerance,Reach; }
    class NRWalkProbe : StaticEventHandler {
     Array<NRWalkPoint> Points; int At,Started,Stuck,LastProgress; double Best; bool Walking;
     void Add(Vector3 q,double tolerance,double reach) {let n=new('NRWalkPoint');n.Point=q;n.ZTolerance=tolerance;n.Reach=reach;Points.Push(n);}
     override void OnRegister() {SetOrder(100);}
     override void WorldLoaded(WorldEvent e) {'''+pushes+'''}
     override void NetworkProcess(ConsoleEvent e) {
      if(e.Name!="nr_walk")return;
      let h=NRDirector.Get();if(!h || !Points.Size())return;
      for(int i=0;i<h.Mobs.Size();i++)if(h.Mobs[i])h.Mobs[i].Destroy();
      h.Mobs.Clear();h.Bosses.Clear();if(h.Vendor)h.Vendor.Destroy();h.Vendor=null;
      h.Seams.Clear();h.Changes.Clear();h.Doors.Clear();h.HaveLast=false;
      At=0;Started=level.time;Stuck=0;LastProgress=level.time;Best=1e30;Walking=true;
     }
     override void WorldTick() {
      if(!Walking)return;let p=players[0].mo;if(!p)return;
      Vector3 goal=Points[At].Point;Vector2 d=goal.XY-p.Pos.XY;double length=d.Length();
      double score=length+max(0.,abs(p.Pos.Z-goal.Z)-Points[At].ZTolerance)*2;
      if(score<Best-2) {Best=score;LastProgress=level.time;}
      if(level.time%35==0)Console.Printf("NRRECEIPT {\\"fixture\\":\\"walk_progress\\",\\"at\\":%d,\\"x\\":%.3f,\\"y\\":%.3f,\\"z\\":%.3f,\\"gx\\":%.3f,\\"gy\\":%.3f,\\"gz\\":%.3f}",At,p.Pos.X,p.Pos.Y,p.Pos.Z,goal.X,goal.Y,goal.Z);
      // A radius-20 capsule straddling a 16-unit stair boundary stands on its
      // higher side, even when this portal waypoint is four units into the low
      // sector. Deck-vs-underpass mistakes remain much larger than one step.
      bool standing=p.Pos.Z>=p.FloorZ-.1 && p.Pos.Z+p.Height<=p.CeilingZ+.1;
      bool anchor=Points[At].ZTolerance<8;
      if(length<=Points[At].Reach && abs(p.Pos.Z-goal.Z)<=Points[At].ZTolerance && standing && (!anchor || abs(p.Pos.Z-p.FloorZ)<.1)) {
       At++;Stuck=0;LastProgress=level.time;Best=1e30;p.Vel=(0,0,p.Vel.Z);
       if(At==Points.Size()) {Walking=false;Console.Printf("NRRECEIPT {\\"fixture\\":\\"walk\\",\\"ok\\":true,\\"points\\":%d,\\"ticks\\":%d}",At,level.time-Started);}
       return;
      }
      if(p.Vel.XY.Length()<.3)Stuck++;else Stuck=0;
      if(Stuck>105 || level.time-LastProgress>140 || level.time-Started>20000) {
       Walking=false;p.Vel=(0,0,0);
       Console.Printf("NRRECEIPT {\\"fixture\\":\\"walk\\",\\"ok\\":false,\\"at\\":%d,\\"x\\":%.4f,\\"y\\":%.4f,\\"z\\":%.4f,\\"floor\\":%.4f,\\"gx\\":%.4f,\\"gy\\":%.4f,\\"gz\\":%.4f}",At,p.Pos.X,p.Pos.Y,p.Pos.Z,p.FloorZ,goal.X,goal.Y,goal.Z);return;
      }
      if(length>0) {double speed=Points[At].Reach>8?4.:12.;p.Angle=atan2(d.Y,d.X);p.Vel=(min(speed,length)*d.X/length,min(speed,length)*d.Y/length,p.Vel.Z);}
     }
    }
    '''
    with zipfile.ZipFile(SOURCE) as z:files={n:z.read(n) for n in z.namelist()}
    files['ZSCRIPT']+=b'\n#include "route-probe.zs"\n';files['route-probe.zs']=fixture.encode()
    files['MAPINFO']=files['MAPINFO'].replace(b'AddEventHandlers = "NRDirector"',b'AddEventHandlers = "NRDirector", "NRWalkProbe"')
    pk3=OUT/'routes.pk3'
    with zipfile.ZipFile(pk3,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in files.items():z.writestr(n,b)
    ini=OUT/'compiler.ini';ini.write_text('[GlobalSettings]\nvid_preferbackend=0\nvid_rendermode=4\n')
    c=subprocess.run([str(ENGINE),'-iwad',str(IWAD),'-file',str(pk3),'-config',str(ini),'-errorlog',str(OUT/'errors.log'),'-noautoload','-nosound'],env=dict(os.environ,SDL_VIDEODRIVER='offscreen',XDG_CONFIG_HOME=str(OUT/'config')),capture_output=True,text=True,timeout=35)
    (OUT/'compile.log').write_text(c.stdout+c.stderr)
    assert c.returncode in (0,57) and 'Script error' not in c.stdout,(c.stdout+c.stderr)[-1800:]
    report={'state':'running','checks':[],'limits':'Native velocity walking with real collision; required anchors demand exact height and grounded feet. Intermediate narrow-stair waypoints allow capsule support from adjacent risers. Unrelated mobs/vendor removed only in the private test; sculptures and collision retained; no noclip.'}
    for detail in details:
        number=detail['map'];e=Engine(ENGINE,BRIDGE,IWAD,pk3,OUT/f'map-{number}',initial_map=number,extra_config='vid_maxfps 15; bind b "netevent nr_walk"')
        try:
            e.pulse(98);e.pause(False)
            deadline=time.monotonic()+550
            while not any(r.get('fixture')=='walk' for r in e.receipts):
                if time.monotonic()>deadline:raise TimeoutError('Native route deadline')
                if e.proc.poll() is not None:raise RuntimeError('Private native walker exited')
                latest=next((r for r in reversed(e.receipts) if r.get('fixture')=='walk_progress'),None)
                if latest:(OUT/'progress.json').write_text(json.dumps({'map':number,**latest})+'\n')
                time.sleep(.5)
            r=next(r for r in e.receipts if r.get('fixture')=='walk');detail.update(r)
            Image.fromarray(e.frame()[:,:,:3]).save(OUT/f'finish-{number}.png')
        finally:e.close()
        report['checks'].append(detail);(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(detail),flush=True)
    report['state']='passed' if all(v.get('ok') for v in report['checks']) else 'failed'
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('engine','bridge','iwad','pk3','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--manifest',type=Path)
    run(p.parse_args())
