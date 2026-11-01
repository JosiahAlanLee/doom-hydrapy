# SPDX-License-Identifier: GPL-3.0-or-later
"""Native cistern fog A/B and actual enemy awareness in an unobstructed room."""
from pathlib import Path
import argparse,json,time,zipfile,hashlib
from PIL import Image,ImageDraw
from uzdoom.engine import Engine
from uzdoom.build import Map,wad
from uzdoom.models import actor_id
from uzdoom.weather import lump


def run(a):
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    saved=json.loads((a.pk3.parent/'manifest.json').read_text())
    first=saved['floors'][0];assert first['open_world']['id']=='flooded-resonance-cistern'
    q=first['open_world']['anchors']['overlook']
    fixture='''
class NRWeatherProbe : StaticEventHandler {
 override void NetworkProcess(ConsoleEvent e){
  if(e.Name!="nr_weather_probe")return;let h=NRDirector.Get();let p=players[0].mo;
  if(e.Args[0]<3){for(int i=0;i<h.Mobs.Size();i++)if(h.Mobs[i])h.Mobs[i].Destroy();h.Mobs.Clear();h.Bosses.Clear();}
  if(e.Args[0]==2){p.SetOrigin((%f,%f,%f),false);p.FindFloorCeiling();p.Vel=(0,0,0);p.ClearInterpolation();p.Angle=atan2(-p.Pos.Y,-p.Pos.X);p.Pitch=8;}
  else h.Weather.SetEnabled(e.Args[0]==1 || e.Args[0]==11);
 }
}
'''%tuple(q)
    with zipfile.ZipFile(a.pk3) as z:original={n:z.read(n) for n in z.namelist()}
    files=dict(original);files['ZSCRIPT']+=b'\n#include "weather-probe.zs"\n';files['weather-probe.zs']=fixture.encode()
    files['MAPINFO']=files['MAPINFO'].replace(b'AddEventHandlers = "NRDirector"',b'AddEventHandlers = "NRDirector", "NRWeatherProbe"')
    def pack(path,data):
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
            for n,b in data.items():z.writestr(n,b)
    pk3=out/'cistern.pk3';pack(pk3,files)
    report={'state':'running','production_sha256':hashlib.sha256(a.pk3.read_bytes()).hexdigest(),'checks':[],
            'scope':'Private native visual A/B, actual AI line-of-sight range and opt-in scope. Cistern visual fixture removes monsters only; AI check uses native production Surveyors in one unobstructed sector. Full integrated music performance remains a later playtest.'}
    def engine(pk3,folder,initial_map=1):return Engine(a.engine,a.bridge,a.iwad,pk3,out/folder,initial_map=initial_map,
        extra_config='vid_maxfps 15; bind b "netevent nr_weather_probe 0"; bind v "netevent nr_weather_probe 1"; bind z "netevent nr_weather_probe 2"; bind x "netevent nr_weather_probe 10"; bind c "netevent nr_weather_probe 11"')
    def pulse(e,key):e.key(ord(key),True);time.sleep(.16);e.key(ord(key),False);time.sleep(.16)
    def shot(e,name):Image.fromarray(e.frame()[:,:,:3]).save(out/(name+'.png'))
    e=engine(pk3,'cistern')
    try:
        e.pause(False);pulse(e,'b');time.sleep(3.3);e.pause(True);shot(e,'entry-clear');clear=e.state()
        e.pause(False);pulse(e,'v');time.sleep(3.3);e.pause(True);shot(e,'entry-fog');fog=e.state()
        assert not clear['weather']['enabled'] and fog['weather']['enabled'] and fog['weather']['in_fog'] and fog['weather']['emitted']>0
        report['checks'].append({'name':'Cistern native fog toggles and emits bounded mist','ok':True,'clear':clear['weather'],'fog':fog['weather']})
        e.pause(False);pulse(e,'z');time.sleep(2);e.pause(True);shot(e,'overlook-fog')
        e.pause(False);pulse(e,'b');time.sleep(3.3);e.pause(True);shot(e,'overlook-clear')
    finally:e.close()
    e=engine(a.pk3,'dry-floor',2)
    try:
        assert not e.state()['weather']['enabled'];report['checks'].append({'name':'Other architectural families remain dry','ok':True,'weather':e.state()['weather']})
    finally:e.close()
    # A flat test room makes geometry occlusion unable to explain the AI result.
    room=Map(1);room.rectangle(0,0,2048,0,256,light=224);room.thing(320,512,1,0);room.thing(160,128,15999)
    room.surface(320,512,0,0,2048);room.meta=['P 0 0','V 160 128 0 0 1 2 3 4']
    for x in (580,1120):room.thing(x,512,actor_id(11),180,args=(11,0,0))
    data=dict(files);data['maps/MAP01.wad']=room.bytes();data['NRMAP01']=room.data()
    profile=dict(first['weather'],sectors=[0]);data['NRWX01']=lump(profile)
    sight=out/'sight.pk3';pack(sight,data);e=engine(sight,'sight')
    try:
        e.pause(False);time.sleep(.8);e.pause(True);s=e.state();near,far=sorted(s['mobs'],key=lambda m:m['x'])
        assert near['awake'] and near['sight'] and not far['awake'] and not far['sight'] and far['attack_count']==0,(near,far)
        report['checks'].append({'name':'Fog conceals distant target from real Surveyor AI','ok':True,'near':near,'far':far})
        shot(e,'awareness-fog');e.pause(False);pulse(e,'x');time.sleep(.3);e.pause(True);s=e.state();far=max(s['mobs'],key=lambda m:m['x'])
        assert not s['weather']['enabled'] and far['awake'] and far['sight'],far
        report['checks'].append({'name':'Disabling fog restores ordinary awareness','ok':True,'far':far});shot(e,'awareness-clear')
    finally:e.close()
    canvas=Image.new('RGB',(1280,856),(12,12,16));draw=ImageDraw.Draw(canvas)
    for i,name in enumerate(('entry-clear','entry-fog','overlook-clear','overlook-fog')):
        im=Image.open(out/(name+'.png'));im.thumbnail((640,400));x=(i%2)*640;y=(i//2)*428;canvas.paste(im,(x,y+28));draw.text((x+8,y+7),name,fill='white')
    canvas.save(out/'contact.jpg');report['state']='passed_pending_visual_review'
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('pk3','output','engine','bridge','iwad'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
