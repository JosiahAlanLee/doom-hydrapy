# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit test-only native setup/driver, imported only by a headless trial."""
from pathlib import Path
import hashlib,json,time,zipfile
_installed=False


def install():
    global _installed
    if _installed:return
    _installed=True
    import uzdoom.game as module
    build=module.build;Engine=module.Engine
    def instrument(*args,**kwargs):
        manifest=build(*args,**kwargs);folder=Path(args[2]);path=folder/'nullrun.pk3'
        with zipfile.ZipFile(path) as z:files={n:z.read(n) for n in z.namelist()}
        files['ZSCRIPT']+=b'\n#include "native_fixture.zs"\n#include "cue_fixture.zs"\n'
        files['native_fixture.zs']=Path(__file__).with_name('native_fixture.zs').read_bytes()
        files['cue_fixture.zs']=b'class NRShaderFixture : NRFixture { override void NetworkProcess(ConsoleEvent e) { if(e.Name=="nr_shader_fixture") {TestId=e.Args[0]==77?7:e.Args[0];Setup();if(e.Args[0]==77)Make(\'NRFixture11\',players[0].mo.Pos+(256,64,0),NRDirector.Get());return;} Super.NetworkProcess(e); } }\n'
        files['MAPINFO']=files['MAPINFO'].replace(b'AddEventHandlers = "NRDirector"',b'AddEventHandlers = "NRDirector", "NRShaderFixture"')
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
            for name,data in files.items():z.writestr(name,data)
        manifest.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),test_only=True)
        (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');return manifest
    class Instrumented(Engine):
        def __init__(self,*args,**kwargs):
            kwargs['extra_config']=kwargs.get('extra_config','')+'; bind b "netevent nr_shader_fixture 7"; bind v "netevent nr_shader_fixture 15"; bind m "netevent nr_shader_fixture 77"'
            super().__init__(*args,**kwargs)
    module.build=instrument;module.Engine=Instrumented


def attach(desktop):
    from hydrapy.live import register_hook
    started=[None];phase=[-1];pending=[None];owner=[None];last=[0.];done=[False]
    root=desktop.root
    captured=set()
    def tick(ctx,renderer):
        if done[0] or not (root/'cue-test-go.json').exists():return
        now=time.monotonic()
        if started[0] is None:
            owner[0]=desktop.game.acquire();started[0]=now
        desktop.game.last_input=now
        elapsed=now-started[0]
        if pending[0] and now>=pending[0][1]:desktop.game.engine.key(pending[0][0],False);pending[0]=None
        index=0 if elapsed<4 else 1 if elapsed<9 else 2 if elapsed<13 else 3 if elapsed<18 else 4 if elapsed<22 else 5 if elapsed<26 else 6
        if phase[0]!=index:
            phase[0]=index;desktop.action({'action':'cues','enabled':index!=4})
            key=109 if index==2 else 98 if index in (0,5) else 118
            desktop.game.engine.key(key,True);pending[0]=(key,now+.07)
        if now-last[0]>.1:
            last[0]=now;s=desktop.status()
            row=dict(t=round(elapsed,3),phase=index,fps=s.get('display_fps'),cues=s.get('shader_cues'),health=s.get('health'),paused=s.get('paused'),boss=s.get('boss'),mobs=s.get('mobs'))
            with (root/'cue-trace.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
            cues=s.get('shader_cues') or {}
            wanted=index in (0,2,5) and cues.get('quiet_progress',0)>.5 or index in (1,3,6) and cues.get('surveyor_progress',0)>.6 or index==4 and any(m.get('class')==11 and m.get('warning_ticks',0)>5 for m in s.get('mobs',[]))
            if wanted and index not in captured:
                from PIL import Image
                Image.fromarray(renderer.read()).save(root/('phase-'+str(index)+'.png'));captured.add(index)
        if elapsed>=30:
            if pending[0]:desktop.game.engine.key(pending[0][0],False)
            desktop.game.input(owner[0],[],paused=True);done[0]=True
            (root/'cue-test-done.json').write_text(json.dumps({'seconds':elapsed})+'\n')
    register_hook(tick)
