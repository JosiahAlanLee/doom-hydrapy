# SPDX-License-Identifier: GPL-2.0-or-later
"""Native-window controls and coherent Doom snapshots for a real Studio patch."""
from collections import deque
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import atexit
import io
import json
import math
import os
import secrets
import threading
import time

from PIL import Image,ImageDraw,ImageFont
from rogue.server import Game,KEYS
from rogue.inhabitants import CREATURES

_current=None


class NativeGame(Game):
    def new_run(self,seed,mode='campaign'):
        return super().new_run(seed,mode)

    def render(self):
        # The picture stays in memory; native play has no JPEG/HTTP presentation path.
        self.state=self.engine.state()
        self.rgb=self.engine.frame(0)[:,:,:3]
        self.frame_seq+=1


class Desktop:
    def __init__(self,root,wad,port=8773,campaign_only=True,autostart=True):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.campaign_only=bool(campaign_only);self.autostart=bool(autostart);self.pending_start=self.autostart
        self.game=NativeGame(wad,self.root/'runs')
        self.owner=None;self.keys=set();self.input_source=None;self.api_until=0
        try:preferences=json.loads((self.root/'view-settings.json').read_text())
        except (OSError,ValueError):preferences={}
        mode=preferences.get('mode',0)
        self.mode=mode if type(mode) is int and 0<=mode<=3 else 0
        if self.campaign_only:self.mode=0
        self.view_lock=threading.Lock()
        self.flicker=preferences.get('flicker',True) is not False;self.loading=False;self.closed=False
        self.window=None;self.focused=False;self.need_sync=False;self.clear_frames=4
        self.last_time=None;self.cache=None;self.frames=deque(maxlen=181)
        self.gpu='';self.bound=False;self.physical_events=0;self.api_events=0
        self.last_report=0;self.capture_requested=False;self.jpeg=b'';self.capture_count=0
        self.token=secrets.token_urlsafe(32);self.port=port
        self.font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',12)
        self.titlefont=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',25)
        self._serve()
        atexit.register(self.close)

    def _serve(self):
        control=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def send(self,body,code=200,kind='application/json'):
                raw=body if isinstance(body,bytes) else json.dumps(body,allow_nan=False).encode()
                self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(raw)))
                self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
            def do_GET(self):
                if self.path=='/state':return self.send(control.status())
                if self.path=='/frame':return self.send(control.jpeg,200 if control.jpeg else 204,'image/jpeg')
                self.send({'error':'Not found'},404)
            def do_POST(self):
                if self.headers.get('X-Run-Token')!=control.token:return self.send({'error':'Invalid session'},403)
                if self.headers.get('Origin') not in [None,f'http://127.0.0.1:{control.port}',f'http://localhost:{control.port}']:
                    return self.send({'error':'Invalid origin'},403)
                try:
                    n=int(self.headers.get('Content-Length','0'));assert 0<n<=4096
                    data=json.loads(self.rfile.read(n));assert isinstance(data,dict)
                    control.action(data,automated=True);self.send({'ok':True})
                except (ValueError,TypeError,AssertionError) as e:self.send({'error':str(e)},400)
                except Exception as e:self.send({'error':type(e).__name__+': '+str(e)},500)
        self.http=ThreadingHTTPServer(('127.0.0.1',self.port),Handler)
        self.http_thread=threading.Thread(target=self.http.serve_forever,daemon=True,name='nullrun-control')
        self.http_thread.start()
        p=self.root/'control.json'
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w') as f:json.dump({'url':f'http://127.0.0.1:{self.port}','token':self.token,'pid':os.getpid()},f)

    def status(self):
        if self.loading:return {'loading':True,'input_source':self.input_source,'gpu':self.gpu}
        with self.game.lock:s=self.game.snapshot()
        fps=(len(self.frames)-1)/(self.frames[-1]-self.frames[0]) if len(self.frames)>1 else 0
        return dict(s,native_input=self.bound,focused=self.focused,input_source=self.input_source,
                    treatment=['RAW','PHOSPHOR VECTOR','ASCII','PRINT'][self.mode],flicker=self.flicker,
                    gpu=self.gpu,display_fps=round(fps,2),physical_events=self.physical_events,
                    api_events=self.api_events,capture_count=self.capture_count,loading=False)

    def pause(self):
        if self.owner:
            try:self.game.input(self.owner,[],paused=True)
            except ValueError:pass
        self.owner=None;self.keys.clear();self.input_source=None;self.clear_frames=4

    def resume(self,automated=False):
        self.pause()
        if self.loading or self.game.state.get('dead') or self.game.state.get('won'):return
        self.owner=self.game.acquire();self.input_source='api' if automated else 'physical'
        self.api_until=time.monotonic()+1;self.need_sync=True;self.clear_frames=4

    def new(self,mode=None,random_seed=False):
        if self.loading:return
        mode=mode or self.game.manifest['mode']
        if self.campaign_only and mode!='campaign':raise ValueError('This player runs the five-floor campaign')
        if mode not in ['strobe','campaign','memory','pillar','corridor',*CREATURES]:raise ValueError('Unknown run mode')
        self.pause()
        seed=secrets.randbits(32) if random_seed else self.game.manifest['seed']
        self.loading=True
        def build():
            try:
                self.game.new_run(seed,mode)
                with self.game.lock:self.game.engine.command(f'STROBE_VIEW {int(self.flicker)}')
                self.clear_frames=4
            except Exception as e:self.game.error=str(e)
            finally:
                self.loading=False
                if self.autostart and not self.game.error:self.pending_start=True
        self.builder=threading.Thread(target=build,daemon=True,name='nullrun-new-study');self.builder.start()

    def action(self,data,automated=False):
        action=data.get('action')
        if automated and action in ['resume','pause','keys','new'] and self.input_source=='physical' and not self.game.paused:
            raise ValueError('The native player has the controls')
        if action=='resume':self.resume(automated)
        elif action=='pause':self.pause()
        elif action=='keys':
            keys=data.get('keys',[])
            if not isinstance(keys,list) or any(k not in KEYS for k in keys) or len(keys)>24:raise ValueError('Unknown keys')
            if not self.owner or self.input_source!='api':raise ValueError('Acquire test controls first')
            self.keys=set(keys);self.api_until=time.monotonic()+1;self.api_events+=1
        elif action=='new':self.new(data.get('mode'),data.get('random_seed',False))
        elif action=='filter':
            mode=data.get('mode');
            if type(mode) is not int or not 0<=mode<=3:raise ValueError('Unknown treatment')
            self.mode=mode;self.clear_frames=4
            self.save_view()
        elif action=='flicker':
            enabled=data.get('enabled')
            if type(enabled) is not bool:raise ValueError('Expected boolean')
            self.flicker=enabled;self.clear_frames=4
            self.save_view()
            with self.game.lock:self.game.engine.command(f'STROBE_VIEW {int(enabled)}')
        elif action=='screenshot':self.capture_requested=True
        else:raise ValueError('Unknown action')

    def save_view(self):
        with self.view_lock:
            p=self.root/'view-settings.tmp'
            p.write_text(json.dumps(dict(mode=self.mode,flicker=self.flicker)))
            p.replace(self.root/'view-settings.json')

    def bind(self):
        if self.bound:return
        import glfw
        window=glfw.get_current_context()
        if not window:return
        self.window=window;self.glfw=glfw
        # Studio's performance window normally declines input. Make this game's
        # own window focusable; no global key listener or desktop hook is used.
        import ctypes as C
        import ctypes.util
        class Hints(C.Structure):
            _fields_=[('flags',C.c_long),('input',C.c_int),('initial_state',C.c_int),('icon_pixmap',C.c_ulong),
                      ('icon_window',C.c_ulong),('icon_x',C.c_int),('icon_y',C.c_int),('icon_mask',C.c_ulong),('window_group',C.c_ulong)]
        x11=C.CDLL(ctypes.util.find_library('X11') or 'libX11.so.6')
        display=C.c_void_p(glfw.get_x11_display());xwindow=C.c_ulong(glfw.get_x11_window(window))
        x11.XSetWMHints.argtypes=[C.c_void_p,C.c_ulong,C.POINTER(Hints)]
        x11.XFlush.argtypes=[C.c_void_p]
        x11.XSetWMHints(display,xwindow,C.byref(Hints(flags=3,input=1,initial_state=1)));x11.XFlush(display)
        glfw.set_window_title(window,'NULL RUN' if self.campaign_only else 'NULL RUN / HydraPy + VCV / 4090')
        glfw.set_window_attrib(window,glfw.FOCUS_ON_SHOW,glfw.TRUE)
        if self.autostart:glfw.focus_window(window)
        keymap={glfw.KEY_W:'KeyW',glfw.KEY_A:'KeyA',glfw.KEY_S:'KeyS',glfw.KEY_D:'KeyD',
                glfw.KEY_Q:'KeyQ',glfw.KEY_E:'KeyE',glfw.KEY_LEFT:'ArrowLeft',glfw.KEY_RIGHT:'ArrowRight',
                glfw.KEY_UP:'ArrowUp',glfw.KEY_DOWN:'ArrowDown',glfw.KEY_SPACE:'Space',
                glfw.KEY_F:'KeyF',glfw.KEY_LEFT_CONTROL:'ControlLeft',glfw.KEY_LEFT_SHIFT:'ShiftLeft',
                glfw.KEY_RIGHT_SHIFT:'ShiftRight',glfw.KEY_TAB:'Tab',**{glfw.KEY_1+i:f'Digit{i+1}' for i in range(7)}}
        def key(_window,k,scancode,action,mods):
            self.physical_events+=1
            if k in keymap:
                if self.input_source=='api':self.pause()
                if action==glfw.RELEASE:self.keys.discard(keymap[k])
                elif not self.game.paused:self.keys.add(keymap[k])
            if action!=glfw.PRESS:return
            if k==glfw.KEY_ENTER:
                self.pause() if self.owner else self.resume()
            elif k in [glfw.KEY_ESCAPE,glfw.KEY_F1]:self.pause()
            elif k==glfw.KEY_R:self.new()
            elif k==glfw.KEY_N:self.new(random_seed=True)
            elif not self.campaign_only and k==glfw.KEY_F2:self.action({'action':'flicker','enabled':not self.flicker})
            elif not self.campaign_only and k==glfw.KEY_F3:self.action({'action':'filter','mode':(self.mode+1)%4})
            elif not self.campaign_only and k in [glfw.KEY_F4,glfw.KEY_F5,glfw.KEY_F6,glfw.KEY_F7,glfw.KEY_F8]:
                self.new(['strobe','campaign','memory','pillar','corridor'][k-glfw.KEY_F4])
        def focus(_window,focused):
            self.focused=bool(focused)
            if not focused and self.input_source=='physical':self.pause()
        self._key_callback=key;self._focus_callback=focus
        glfw.set_key_callback(window,key);glfw.set_window_focus_callback(window,focus)
        def close_window(_window):
            self.pause()
            (self.root/'quit.request').write_text('Window closed\n')
        self._close_callback=close_window
        previous_close=glfw.set_window_close_callback(window,close_window)
        if previous_close:
            def close_with_previous(w):
                close_window(w);previous_close(w)
            self._close_callback=close_with_previous
            glfw.set_window_close_callback(window,close_with_previous)
        self.focused=bool(glfw.get_window_attrib(window,glfw.FOCUSED));self.bound=True

    def snapshot(self,t):
        if self.last_time==t and self.cache is not None:return self.cache
        if not self.loading and self.game.lock.acquire(blocking=False):
            try:state=self.game.snapshot();rgb=self.game.rgb.copy()
            finally:self.game.lock.release()
        elif self.cache:
            state=self.cache['state'];rgb=self.cache['raw'].copy()
        else:raise RuntimeError('No native frame available')
        st=state.get('strobe',{});paused=state.get('paused',True) or self.loading
        visual_key=(state.get('revision'),state.get('frame'),paused,self.mode,self.flicker,self.loading,self.game.error)
        if self.cache and self.cache.get('visual_key')==visual_key:
            im=self.cache['image']
        else:
            im=self.draw_screen(rgb,state,st,paused)
        dt=max(0,t-self.last_time) if self.last_time is not None else 1/60
        decay=0 if paused or self.clear_frames or self.mode==0 else math.exp(-min(dt,2)/.28)
        self.cache=dict(image=im,raw=rgb,state=state,visual_key=visual_key,
                        light=1 if paused else st.get('illumination',1 if st.get('lit',True) else .04),
                        muzzle=0 if paused else float(st.get('muzzle',False)),decay=decay)
        self.last_time=t;return self.cache

    def draw_screen(self,rgb,state,st,paused):
        im=Image.fromarray(rgb);draw=ImageDraw.Draw(im)
        if self.campaign_only:
            header=state.get('argon',{}).get('cue') or (state.get('floor_name','NULL RUN')+f"   |   FLOOR {state.get('map',1)} / {state.get('floors',5)}")
            draw.rectangle((0,0,640,24),fill=(10,12,12));draw.text((9,5),header,font=self.font,fill=(226,222,205))
            if paused or state.get('dead') or state.get('won'):
                draw.rectangle((34,65,606,326),fill=(12,15,16),outline=(163,157,133),width=2)
                title='NULL RUN / FIVE FLOORS'
                prompt='ENTER resume / ESC pause'
                if self.loading:prompt='ARRANGING THE NEXT RUN...'
                elif state.get('dead'):title='THE RUN ENDS HERE';prompt='R retries this seed / N starts a new run'
                elif state.get('won'):title='YOU FOUND THE WAY OUT';prompt='R retries this seed / N starts a new run'
                draw.text((54,83),title,font=self.titlefont,fill=(231,223,198))
                lines=[prompt,'WASD move / arrows or Q-E turn','SPACE or CTRL fire / F use','SHIFT run / TAB map / 1-7 weapons','R retry / N new seed']
                if self.game.error:lines[0]='ERROR: '+self.game.error[:72]
                for i,line in enumerate(lines):draw.text((54,139+i*30),line,font=self.font,fill=(201,201,188))
            return im
        phase='FLASH / PINNED' if st.get('muzzle') else 'LIT / WATCH IT' if st.get('lit') else 'LAMP FAILURE / IT MOVES'
        if not st.get('active'):phase=state.get('floor_name','NULL RUN')
        draw.rectangle((0,0,640,24),fill=(9,14,12));draw.text((9,5),phase+'   |   '+['RAW','PHOSPHOR','ASCII','PRINT'][self.mode]+(' / STEADY' if not self.flicker else ''),font=self.font,fill=(204,228,177))
        if paused or state.get('dead') or state.get('won'):
            draw.rectangle((34,65,606,326),fill=(12,19,17),outline=(142,174,99),width=2)
            draw.text((54,80),'NULL RUN / FULL STACK',font=self.titlefont,fill=(213,231,171))
            lines=['HYDRAPY ON THE 4090 / VCV RACK INSTRUMENTS',
                   'Fluorescent flicker. F2 = steady view; light rules stay active.',
                   'ENTER play / ESC pause / R retry / N new seed',
                   'WASD move / arrows or Q-E turn / SPACE fire / F use',
                   'SHIFT run / TAB map / 1-7 weapons / F3 treatments',
                   'F4 Fluorescent Hollow / F5 five-floor descent',
                   'F6 changing room / F7 five corners / F8 corridor']
            if self.loading:lines[2]='ARRANGING THE NEXT RUN...'
            elif state.get('dead'):lines[2]='THE HOLLOW GOT YOU. R retries this seed.'
            elif state.get('won'):lines[2]='YOU FOUND THE LIGHT. R retries / N changes the seed.'
            if self.game.error:lines[1]='ERROR: '+self.game.error[:74]
            for i,line in enumerate(lines):draw.text((54,124+i*26),line,font=self.font,fill=(180,201,178))
        return im

    def tick(self,ctx,renderer,beat=None):
        if self.closed:return
        self.bind();renderer.settle=1e9
        self.gpu=renderer.ctx.info.get('GL_RENDERER','')
        now=time.monotonic();self.frames.append(now)
        if getattr(self,'pending_start',False) and self.focused and not self.loading:
            self.pending_start=False;self.resume()
        if self.owner:
            if self.game.paused or (self.input_source=='api' and now>self.api_until) or (self.input_source=='physical' and not self.focused):self.pause()
            elif not self.loading:
                if self.need_sync and beat is not None and self.game.state.get('strobe',{}).get('style')=='bpm':
                    phase=round(float(beat(ctx))%1*2100)%2100
                    with self.game.lock:self.game.engine.command(f'STROBE_SYNC {phase}')
                self.need_sync=False
                try:self.game.input(self.owner,sorted(self.keys))
                except ValueError:
                    # The simulation can finish the level and release ownership
                    # between the paused check above and this input snapshot.
                    self.pause()
        if self.clear_frames:self.clear_frames-=1
        if self.capture_requested:
            self.capture_requested=False
            image=Image.fromarray(renderer.read()).convert('RGB');data=io.BytesIO();image.save(data,format='JPEG',quality=95,subsampling=0)
            self.jpeg=data.getvalue();self.capture_count+=1
            (self.root/'gpu-frame.jpg').write_bytes(self.jpeg)
        if now-self.last_report>=1:
            self.last_report=now
            p=self.root/'native-status.tmp';p.write_text(json.dumps(self.status(),allow_nan=False));p.replace(self.root/'native-status.json')

    def close(self):
        if self.closed:return
        self.closed=True;self.pause()
        self.http.shutdown();self.http.server_close()
        if getattr(self,'builder',None) and self.builder.is_alive():self.builder.join(timeout=20)
        self.game.close()


def start(root,wad,port=8773,campaign_only=True,autostart=True):
    global _current
    if _current is not None:_current.close()
    _current=Desktop(root,wad,port,campaign_only,autostart);return _current
