# SPDX-License-Identifier: GPL-2.0-or-later
"""Loopback-only, single-controller play server for the Doom child process.

Run: python -m rogue.server --wad /path/to/freedoom2.wad --port 8767
Reach another machine through an SSH tunnel; the engine and all saves stay here.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import argparse
import io
import json
import secrets
import threading
import time

from PIL import Image

from client import Doom
from rogue.maps import campaign, FLOORS
from rogue.bosses import BOSSES
from rogue.inhabitants import CREATURES

ROOT=Path(__file__).resolve().parent
# Doom key IDs; WASD maps to the engine's forward/strafe defaults. Browser codes are
# physical positions, independent of the user's character-key layout.
KEYS={'KeyW':0xad,'KeyS':0xaf,'KeyA':0xa0,'KeyD':0xa1,
      'ArrowUp':0xad,'ArrowDown':0xaf,'ArrowLeft':0xac,'ArrowRight':0xae,
      'KeyQ':0xac,'KeyE':0xae,'Space':0xa3,'ControlLeft':0xa3,
      'KeyF':0xa2,'ShiftLeft':0xb6,'ShiftRight':0xb6,'Tab':9,
      **{f'Digit{i}':ord(str(i)) for i in range(1,8)}}


class Game:
    def __init__(self,wad,run_dir,seed=20261030):
        self.wad=Path(wad).resolve()
        self.run_dir=Path(run_dir).resolve();self.run_dir.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.engine=None;self.stop_event=threading.Event()
        self.owner=None;self.last_input=0;self.held=set();self.paused=True
        self.revision=0;self.error=None;self.jpeg=b'';self.state={};self.frame_seq=0
        self.new_run(seed)
        self.thread=threading.Thread(target=self.loop,daemon=True,name='doom-run')
        self.thread.start()

    def new_run(self,seed,mode='campaign'):
        if isinstance(seed,bool) or not isinstance(seed,int) or not 0<=seed<=0xffffffff:
            raise ValueError('Seed must be a whole number from 0 to 4294967295.')
        if mode not in ['campaign',*BOSSES,*CREATURES]:raise ValueError('Unknown run mode.')
        with self.lock:
            self.release()
            if self.engine:self.engine.close();self.engine=None
            self.revision+=1;self.error=None;self.paused=True;self.owner=None
            folder=self.run_dir/f'run-{time.time_ns()}-{seed}'
            folder.mkdir()
            self.manifest=campaign(seed,folder/'dungeon.wad',assets=self.wad,practice=None if mode=='campaign' else mode)
            (folder/'manifest.json').write_text(json.dumps(self.manifest,indent=2)+'\n')
            self.engine=Doom(self.wad,demo=None,locked=True,pwad=folder/'dungeon.wad',rogue_floors=len(self.manifest['floors']))
            self.frame_seq=0;self.render()

    def release(self):
        if self.engine:
            for key in sorted(self.held):self.engine.key(key,False)
        self.held=set()

    def acquire(self):
        with self.lock:
            if self.owner and time.monotonic()-self.last_input<4:
                raise ValueError('Another tab has the controls. Pause it or wait four seconds.')
            self.owner=secrets.token_urlsafe(24);self.last_input=time.monotonic()
            self.paused=False
            return self.owner

    def input(self,owner,keys,paused=False):
        if not isinstance(keys,list) or len(keys)>24 or any(not isinstance(k,str) or k not in KEYS for k in keys):
            raise ValueError('Unknown controls.')
        with self.lock:
            if not owner or owner!=self.owner:raise ValueError('Click Play to take the controls.')
            self.last_input=time.monotonic()
            self.paused=bool(paused)
            requested={KEYS[k] for k in keys} if not paused else set()
            if self.state.get('dead') or self.state.get('won'):requested=set()
            # Full snapshots are idempotent; missed browser key-up events cannot
            # leave a key held. Transitions go to the engine exactly once.
            for k in sorted(self.held-requested):self.engine.key(k,False)
            for k in sorted(requested-self.held):self.engine.key(k,True)
            self.held=requested
            if paused:self.owner=None

    def snapshot(self):
        with self.lock:
            floor=min(max(self.state.get('map',1),1),len(self.manifest['floors']))
            return {**self.state,'seed':self.manifest['seed'],'floor_name':self.manifest['floors'][floor-1]['name'],
                    'floors':len(self.manifest['floors']),'mode':self.manifest['mode'],
                    'study_rule':CREATURES.get(self.manifest['mode'],{}).get('rule'),
                    'boss_rule':self.manifest['floors'][floor-1]['boss']['game_rule'] if self.manifest['floors'][floor-1]['boss'] else None,
                    'paused':self.paused,'revision':self.revision,
                    'frame':self.frame_seq,'error':self.error}

    def render(self):
        self.state=self.engine.state()
        # frame(0) is safe while using advance() directly: target stays zero.
        rgb=self.engine.frame(0)[:,:,:3]
        image=Image.fromarray(rgb)
        output=io.BytesIO();image.save(output,format='JPEG',quality=88,subsampling=0)
        self.jpeg=output.getvalue();self.frame_seq+=1

    def loop(self):
        deadline=time.monotonic()
        while not self.stop_event.is_set():
            with self.lock:
                try:
                    if not self.paused and time.monotonic()-self.last_input>1.0:
                        self.release();self.paused=True;self.owner=None
                    if not self.paused and not self.state.get('dead') and not self.state.get('won'):
                        self.engine.advance(1);self.render()
                        if self.state.get('dead') or self.state.get('won'):
                            self.release();self.paused=True;self.owner=None
                except Exception as exc:
                    self.error=str(exc);self.paused=True;self.owner=None
            deadline+=1/35
            now=time.monotonic()
            if now-deadline>.25:deadline=now
            self.stop_event.wait(max(0,deadline-now))

    def close(self):
        self.stop_event.set();self.thread.join(timeout=25)
        with self.lock:
            self.release()
            if self.engine:self.engine.close();self.engine=None


def handler(game,token,port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,fmt,*args):
            if not args or ' /api/' not in str(args[0]):super().log_message(fmt,*args)

        def respond(self,data,mime='application/json',status=200):
            if not isinstance(data,bytes):data=json.dumps(data).encode()
            self.send_response(status);self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            try:self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError):pass

        def allowed(self):
            host=self.headers.get('Host','')
            return host in [f'127.0.0.1:{port}',f'localhost:{port}']

        def do_GET(self):
            if not self.allowed():return self.respond({'error':'Use the loopback address.'},status=403)
            path=urlsplit(self.path).path
            if path=='/':
                html=(ROOT/'index.html').read_text().replace('__TOKEN__',token)
                return self.respond(html.encode(),'text/html; charset=utf-8')
            if path in ['/app.js','/style.css']:
                return self.respond((ROOT/path[1:]).read_bytes(),'text/javascript' if path.endswith('.js') else 'text/css')
            if path=='/api/state':return self.respond(game.snapshot())
            if path=='/api/frame':
                with game.lock:data=game.jpeg
                return self.respond(data,'image/jpeg')
            return self.respond({'error':'Not found.'},status=404)

        def do_POST(self):
            origin=self.headers.get('Origin')
            if not self.allowed() or origin not in [None,f'http://127.0.0.1:{port}',f'http://localhost:{port}'] or self.headers.get('X-Run-Token')!=token:
                return self.respond({'error':'Invalid session.'},status=403)
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=4096:raise ValueError('Request too large or empty.')
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict):raise ValueError('Expected object.')
                path=urlsplit(self.path).path
                if path=='/api/control':result={'owner':game.acquire()}
                elif path=='/api/input':
                    game.input(data.get('owner'),data.get('keys',[]),data.get('paused',False));result={'ok':True}
                elif path=='/api/new':
                    with game.lock:
                        if game.owner and data.get('owner')!=game.owner:raise ValueError('Another tab has the controls.')
                        game.new_run(data.get('seed'),data.get('mode','campaign'));result=game.snapshot()
                else:return self.respond({'error':'Not found.'},status=404)
                self.respond(result)
            except (ValueError,TypeError) as exc:self.respond({'error':str(exc)},status=400)
            except Exception as exc:self.respond({'error':str(exc)},status=500)
    return Handler


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--wad',type=Path,required=True);p.add_argument('--port',type=int,default=8767)
    p.add_argument('--seed',type=int,default=20261030)
    p.add_argument('--run-dir',type=Path,default=Path(__file__).resolve().parents[1]/'runtime/rogue')
    args=p.parse_args()
    if not args.wad.is_file():p.error('Freedoom 2 IWAD file does not exist')
    game=Game(args.wad,args.run_dir,args.seed)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler(game,secrets.token_urlsafe(32),args.port))
    print(f'Doom / Null Run: http://127.0.0.1:{args.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close();game.close()


if __name__=='__main__':main()
