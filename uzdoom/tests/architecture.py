# SPDX-License-Identifier: GPL-3.0-or-later
"""Check the authored pillar seams and memory room on native MAP02/MAP03."""
from pathlib import Path
import argparse,json,time,zipfile
from PIL import Image
from uzdoom.engine import Engine

def run(a):
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(a.pk3) as z:files={n:z.read(n) for n in z.namelist()}
    files['ZSCRIPT']+=b'\n#include "native_fixture.zs"\n'
    files['native_fixture.zs']=Path(__file__).with_name('native_fixture.zs').read_bytes()
    files['MAPINFO']=files['MAPINFO'].replace(b'AddEventHandlers = "NRDirector"',b'AddEventHandlers = "NRDirector", "NRFixture"')
    pk3=out/'instrumented.pk3'
    with zipfile.ZipFile(pk3,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)
    report={'checks':[],'limits':'Only the test overlay can place the player; seam traversal and sector collisions run through the real engine.'}
    for number in (2,3):
        e=Engine(a.engine,a.bridge,a.iwad,pk3,out/f'map-{number:02}',initial_map=number,
                 extra_config='bind v "netevent nr_fixture 3"; bind m "netevent nr_fixture 4"; bind x "netevent nr_fixture 1"')
        def command(code,tag):
            with e.lock:e.receipts.clear()
            e.pulse(code);e.wait(lambda:any(r.get('fixture')==tag for r in e.receipts))
            with e.lock:return next(r for r in reversed(e.receipts) if r.get('fixture')==tag)
        try:
            for index in range(8 if number==2 else 1):
                result={'map':number,'seam':index if number==2 else None}
                try:
                    command(118 if number==2 else 109,'ready');e.pause(False)
                    if number==2:
                        e.key(119,True);e.wait(lambda:e.latest['architecture']['swaps']==1,4);e.key(119,False)
                    else:
                        time.sleep(.5);assert e.latest['architecture']['mutations']==0
                        e.move(1024);e.wait(lambda:e.latest['architecture']['mutations']==1,3)
                    e.pause(True);receipt=command(120,'check');assert receipt['ok'],receipt
                    result.update(state='passed',detail=receipt['detail'])
                    Image.fromarray(e.frame()[:,:,:3]).save(out/f'map-{number:02}-case-{index:02}.png')
                except Exception as error:result.update(state='failed',error=str(error))
                finally:e.key(119,False);e.pause(True)
                report['checks'].append(result);print(json.dumps(result),flush=True)
                (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        finally:e.close()
    report['state']='passed' if all(c['state']=='passed' for c in report['checks']) else 'failed'
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report['state']=='passed'

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('engine','bridge','iwad','pk3','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('engine','bridge','iwad','pk3'):setattr(a,name,getattr(a,name).resolve())
    raise SystemExit(0 if run(a) else 1)
