# SPDX-License-Identifier: GPL-3.0-or-later
"""Own the adaptive session; music failure must not destroy a playable run."""
from pathlib import Path
from datetime import datetime,timezone
import fcntl
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT=Path(os.environ['NULLRUN_ROOT']).resolve()
SOURCE=Path(__file__).resolve().parents[1]
DEP=Path(os.environ['NULLRUN_DEPENDENCIES']).resolve()
PY=sys.executable
RACK=Path(os.environ['NULLRUN_RACK']).resolve()
DEVICE=os.environ.get('NULLRUN_AUDIO_DEVICE','Digi 003 Rack Multichannel')
PORT=int(os.environ.get('NULLRUN_PORT','8774'))
CONFIG={'audio':{'backend':'pipewire','rate':48000,'quantum':2048,'device':DEVICE,'start_services':False}}

def stamp():return datetime.now(timezone.utc).isoformat()
def save(path,data):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(path)
def identity(pid):
    try:return Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19]
    except (OSError,IndexError):return None
def alive(record):return record.get('start') is not None and identity(record.get('pid',0))==record['start']
def environment():
    return dict(os.environ,DISPLAY=':1',XAUTHORITY='/run/user/1000/gdm/Xauthority',
                XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus',
                PYTHONDONTWRITEBYTECODE='1',DOOM_STROBE_STYLE='irregular',NULLRUN_ROOT=str(ROOT),NULLRUN_PORT=str(PORT),NULLRUN_INITIAL_SCORE=str(ROOT/'music/initial-score.json'),
                FREEDOOM_WAD=os.environ['FREEDOOM_WAD'],
                PYTHONPATH=f'{DEP}/Gorgon:{DEP}/hydrapy:{SOURCE}:{SOURCE}/uzdoom/music_package')
def read_state():
    try:return json.loads((ROOT/'service.json').read_text())
    except (OSError,ValueError):return {}
def game_state():
    with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/state',timeout=3) as response:return json.load(response)


def run():
    lock=(ROOT/'service.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1',PORT))==0:raise RuntimeError('A native game is already present; preserve it and attach audio deliberately')
    os.environ.update(environment())
    from gorgon import audio
    session=ROOT/'sessions'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    workspace=session/'studio';(workspace/'.hydrapy').mkdir(parents=True)
    text=(SOURCE/'uzdoom/live.py').read_text()
    compile(text,'tower_live.py','exec');(workspace/'tower_live.py').write_text(text)
    save(workspace/'.hydrapy/outputs.json',{'audio':{'enabled':False},'native':{'monitor':'window'}})
    quit_file=ROOT/'quit.request'
    if quit_file.exists():quit_file.rename(session/'previous-quit.request')
    env=environment();env['HYDRAPY_STUDIO_FILE']=str(session/'studio.json')
    state={'supervisor':{'pid':os.getpid(),'start':identity(os.getpid())},'state':'starting',
           'session':str(session),'source':str(SOURCE),'started':stamp(),'children':{},'audio_generation':0}
    save(ROOT/'service.json',state)
    children={};logs=[];stopped=[False]
    signal.signal(signal.SIGTERM,lambda *_:stopped.__setitem__(0,True))
    signal.signal(signal.SIGINT,lambda *_:stopped.__setitem__(0,True))
    def launch(name,command,cwd,child_env):
        log=(session/(name+'.log')).open('a');logs.append(log)
        p=subprocess.Popen(command,cwd=cwd,env=child_env,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        children[name]=p;state['children'][name]={'pid':p.pid,'start':identity(p.pid),'command':command}
        save(ROOT/'service.json',state);return p
    def terminate(name):
        p=children.get(name)
        if p is None or p.poll() is not None:return
        if name=='rack' and p.stdin:
            try:p.stdin.write(b'\n');p.stdin.flush();p.wait(timeout=3)
            except (BrokenPipeError,OSError,subprocess.TimeoutExpired):pass
        if p.poll() is None:
            try:os.killpg(p.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:p.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid,signal.SIGKILL);p.wait(timeout=5)
    def wait(callback,seconds):
        until=time.monotonic()+seconds
        while time.monotonic()<until and not stopped[0]:
            try:
                result=callback()
                if result:return result
            except (OSError,ValueError,KeyError):pass
            if children.get('studio') and children['studio'].poll() is not None:raise RuntimeError('Native game/Studio exited during startup')
            time.sleep(.2)
        raise RuntimeError('Session readiness timed out')

    def start_audio():
        terminate('music');terminate('rack')
        state['audio_generation']+=1;generation=state['audio_generation']
        host_output=session/f'music-{generation:02}'
        music=launch('music',[PY,str(SOURCE/'uzdoom/adaptive_host.py'),'--studio',str(session/'studio.json'),
                              '--game',f'http://127.0.0.1:{PORT}','--output',str(host_output)],ROOT,env)
        def music_ready():
            if music.poll() is not None:raise RuntimeError('Adaptive host exited; inspect music.log')
            p=host_output/'status.json'
            if p.is_file() and json.loads(p.read_text()).get('state')=='running':return True
        wait(music_ready,45)
        graph=audio.ensure_server(CONFIG)
        baseline={p['name'].split(':',1)[0] for p in graph['ports'] if p['name'].startswith('VCV Rack')}
        rack_user=session/f'rack-user-{generation:02}';rack_user.mkdir()
        (rack_user/'plugins-lin-x64').symlink_to(Path(os.environ['NULLRUN_RACK_PLUGINS']),target_is_directory=True)
        save(rack_user/'settings.json',{'sampleRate':48000,'threadCount':1})
        rack_env=dict(env,PIPEWIRE_LATENCY='2048/48000',PIPEWIRE_RATE='1/48000',PIPEWIRE_PROPS='{ priority.session = -1 }')
        rack=launch('rack',['pw-jack','xvfb-run','-a','-n','147',str(RACK),'-h','-u',str(rack_user),str(ROOT/'music/adaptive-live.vcv')],RACK.parent,rack_env)
        def rack_ready():
            if rack.poll() is not None:raise RuntimeError('Played Rack exited; inspect rack.log')
            graph=audio.probe(CONFIG);groups={}
            for port in graph['ports']:
                match=re.fullmatch(r'(VCV Rack[^:]*):outport (\d+)',port['name'])
                if match and match[1] not in baseline and port['flags']&2:
                    groups.setdefault(match[1],{})[int(match[2])]=port
            candidates=[v for v in groups.values() if 0 in v and 1 in v]
            return (graph,candidates[0]) if len(candidates)==1 else None
        graph,ports=wait(rack_ready,45)
        group=ports[0]['name'].split(':',1)[0]
        targets=[p['name'] for p in graph['ports'] if p['flags']&1 and p['name'].startswith(DEVICE+':')]
        targets.sort(key=lambda n:int(re.search(r'(\d+)$',n)[1]));assert len(targets)>=2
        operations=[]
        for port in graph['ports']:
            if port['name'].startswith(DEVICE+':') and port['flags']&2:
                operations.extend(('disconnect',port['name'],dest) for dest in port['connections'] if dest.startswith(group+':inport '))
        for i,port in ports.items():
            operations.extend(('disconnect',port['name'],dest) for dest in port['connections']
                              if dest.startswith(DEVICE+':playback_') and (i>=2 or dest!=targets[i]))
        operations.extend(('connect',ports[i]['name'],targets[i]) for i in (0,1))
        graph=audio.probe(CONFIG,operations)
        save(session/f'routing-{generation:02}.json',{'rack_client':group,'outputs':[ports[i]['name'] for i in (0,1)],'targets':targets[:2],'operations':operations})
        state.update(state='running',rack_client=group,music_status=str(host_output/'status.json'),ready=stamp(),audio_error=None)
        save(ROOT/'service.json',state)

    try:
        studio=launch('studio',[PY,'-m','hydrapy.cli','studio',str(workspace/'tower_live.py'),
                               '--root',str(workspace),'--backend','gl','--size','1280x800','--fps','60',
                               '--native-output','window','--no-browser','--tracker','--port','0',
                               '--diagnostics',str(session/'stress.jsonl')],SOURCE,env)
        def studio_ready():
            p=session/'studio.json'
            if not p.is_file():return
            info=json.loads(p.read_text())
            if os.getpgid(info['pid'])!=studio.pid:raise RuntimeError('Studio advertisement is not owned by this session')
            game=game_state()
            return game if game.get('native_input') and game.get('floors')==7 else None
        wait(studio_ready,120)
        try:start_audio()
        except Exception as exc:
            terminate('music');terminate('rack')
            state.update(state='running_audio_failed',audio_error=str(exc));save(ROOT/'service.json',state)
        print('U ZDoom adaptive session ready; click/Enter to play.',flush=True)
        restart=ROOT/'music-restart.request'
        while not stopped[0] and not quit_file.exists() and studio.poll() is None:
            if restart.exists():
                restart.rename(session/f'restart-{time.time_ns()}.request')
                try:start_audio()
                except Exception as exc:
                    terminate('music');terminate('rack')
                    state.update(state='running_audio_failed',audio_error=str(exc));save(ROOT/'service.json',state)
            if state['state']=='running' and any(children[name].poll() is not None for name in ('music','rack')):
                terminate('music');terminate('rack')
                state.update(state='running_audio_failed',audio_error='An owned audio process exited; native game preserved')
                save(ROOT/'service.json',state)
            time.sleep(.3)
        state.update(state='stopping',reason='Window closed' if quit_file.exists() or studio.poll() is not None else 'Requested stop')
        save(ROOT/'service.json',state)
    except Exception as exc:
        state.update(state='failed',error=str(exc));save(ROOT/'service.json',state);raise
    finally:
        for name in ('music','rack','studio'):terminate(name)
        for log in logs:log.close()
        if state['state']!='failed':state.update(state='stopped',stopped=stamp());save(ROOT/'service.json',state)


if __name__=='__main__':
    command=sys.argv[1] if len(sys.argv)>1 else 'status'
    if command=='run':run()
    elif command=='start':
        state=read_state()
        if alive(state.get('supervisor',{})):raise SystemExit('This adaptive session is already active')
        with (ROOT/'service.log').open('a') as log:
            p=subprocess.Popen([PY,'-m','uzdoom.session','run'],cwd=ROOT,env=environment(),stdin=subprocess.DEVNULL,
                               stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        print('Starting adaptive desktop session',p.pid)
    elif command=='stop':
        state=read_state()
        if alive(state.get('supervisor',{})):
            if '--force' not in sys.argv[2:]:
                try:current=game_state()
                except (OSError,ValueError):current={}
                if current.get('input_source')=='physical' and not current.get('paused',True):
                    raise SystemExit('The native player has the controls. Pause in the window before stopping this session; --force is only for an explicitly requested forced stop.')
            os.kill(state['supervisor']['pid'],signal.SIGTERM)
    elif command=='restart-music':
        if not alive(read_state().get('supervisor',{})):raise SystemExit('No owned session to restart music in')
        (ROOT/'music-restart.request').write_text(stamp())
    elif command=='status':
        state=read_state();state['supervisor_alive']=alive(state.get('supervisor',{}));print(json.dumps(state,indent=2))
    else:raise SystemExit('Use start|stop|restart-music|status')
