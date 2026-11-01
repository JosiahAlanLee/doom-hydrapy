# SPDX-License-Identifier: GPL-3.0-or-later
"""One private UZDoom process with bounded input and coherent RGBA snapshots."""
from pathlib import Path
import json,mmap,os,secrets,signal,struct,subprocess,threading,time
import numpy as np

KEYS={'KeyW':119,'KeyS':115,'KeyA':97,'KeyD':100,'KeyQ':113,'KeyE':101,
      'ArrowUp':1073741906,'ArrowDown':1073741905,'ArrowLeft':1073741904,'ArrowRight':1073741903,
      'Space':32,'ControlLeft':1073742048,'ControlRight':1073742052,
      'MouseFire':1073742048,'MouseUse':102,'KeyF':102,'ShiftLeft':1073742049,'ShiftRight':1073742053,
      'Tab':9,**{f'Digit{i}':ord(str(i)) for i in range(1,8)}}

class Engine:
    def __init__(self,engine,bridge,iwad,pk3,folder,*,sound=False,extra_config='',gl_version=None,initial_map=1):
        if type(initial_map) is not int or not 1<=initial_map<=7:raise ValueError('Native map must be1–7')
        self.root=Path(folder);self.root.mkdir(parents=True,exist_ok=False)
        self.lock=threading.RLock();self.changed=threading.Condition(self.lock)
        self.send_lock=threading.Lock();self.latest={};self.receipts=[];self.mem=None;self.fd=None;self.closed=False
        self.native_paused=False;self.error=None
        config='[GlobalSettings]\nvid_preferbackend=0\nvid_rendermode=4\nvid_vsync=false\nvid_maxfps=60\nvid_fullscreen=false\nwin_w=1280\nwin_h=800\nvid_activeinbackground=true\nvid_lowerinbackground=false\nfreelook=true\nlookspring=false\n'
        (self.root/'engine.ini').write_text(config)
        binds={'w':'+forward','s':'+back','a':'+moveleft','d':'+moveright','q':'+left','e':'+right',
               'uparrow':'+forward','downarrow':'+back','leftarrow':'+left','rightarrow':'+right',
               'space':'+jump','ctrl':'+attack','rctrl':'+attack','f':'+use','shift':'+speed','rshift':'+speed',
               'tab':'togglemap','p':'pause','u':'netevent nr_buy 0','i':'netevent nr_buy 1','o':'netevent nr_buy 2',
               'j':'netevent nr_close','h':'netevent nr_flicker 0','k':'netevent nr_flicker 1'}
        cfg='unbindall; '+ '; '.join(f'bind {k} "{v}"' for k,v in binds.items())
        cfg+='; '+ '; '.join(f'bind {i} "slot {i}"' for i in range(1,8))
        cfg+='; freelook true; lookspring false; m_filter false; sensitivity 1; screenblocks 12; crosshair 0; con_notifytime 0; snd_musicvolume 0; '+extra_config+'\n'
        (self.root/'controls.cfg').write_text(cfg)
        env=dict(os.environ,LD_PRELOAD=str(Path(bridge).resolve()),NULLRUN_FRAME=str(self.root/'frame'),
                 XDG_CONFIG_HOME=str(self.root/'config'),XDG_DATA_HOME=str(self.root/'data'),XDG_CACHE_HOME=str(self.root/'cache'))
        env.setdefault('SDL_VIDEODRIVER','offscreen')
        cmd=[str(engine),'-iwad',str(iwad),'-file',str(pk3),'-config',str(self.root/'engine.ini'),'-savedir',str(self.root/'saves'),
             '-noautoload','-nojoy','-stdout','-window','-width','1280','-height','800','-warp',str(initial_map),'+exec',str(self.root/'controls.cfg')]
        if not sound:cmd.insert(1,'-nosound')
        if gl_version:cmd[1:1]=['-glversion',str(gl_version)]
        self.log=(self.root/'engine.log').open('w',buffering=1)
        try:
            self.proc=subprocess.Popen(cmd,cwd=self.root,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                       text=True,bufsize=1,start_new_session=True)
            (self.root/'process.json').write_text(json.dumps({'pid':self.proc.pid,'command':cmd,'frame_protocol':'NRF1'},indent=2)+'\n')
            self.reader=threading.Thread(target=self._read,daemon=True,name='uzdoom-state');self.reader.start()
            self.wait(lambda:bool(self.latest.get('map')),45)
            deadline=time.monotonic()+10
            while not (self.root/'frame').is_file():
                if time.monotonic()>deadline:raise RuntimeError('No UZDoom picture; inspect '+str(self.root/'engine.log'))
                time.sleep(.02)
            self.fd=(self.root/'frame').open('rb');self.mem=mmap.mmap(self.fd.fileno(),0,access=mmap.ACCESS_READ)
            if self.mem[:4]!=b'NRF1' or struct.unpack_from('<II',self.mem,4)!=(1280,800):raise RuntimeError('Unsupported native frame')
            self.pause(True)
        except BaseException:self.close();raise

    def _read(self):
        try:
            for line in self.proc.stdout:
                if len(line)>262144:raise RuntimeError('Oversized native state')
                with self.changed:
                    if line.startswith('NRSTATE '):self.latest=json.loads(line[8:])
                    elif line.startswith('NRRECEIPT '):self.receipts.append(json.loads(line[10:]));self.receipts=self.receipts[-16:]
                    else:self.log.write(line)
                    self.changed.notify_all()
        except Exception as e:self.error=str(e)
        finally:
            with self.changed:self.changed.notify_all()

    def wait(self,test,seconds=3):
        deadline=time.monotonic()+seconds
        with self.changed:
            while not test():
                if self.proc.poll() is not None or self.error:raise RuntimeError(self.error or 'U ZDoom exited; inspect '+str(self.root/'engine.log'))
                remaining=deadline-time.monotonic()
                if remaining<=0:raise TimeoutError('Native acknowledgement timed out: '+str(self.root))
                self.changed.wait(min(.1,remaining))

    def send(self,text):
        if '\n' in text:raise ValueError('One bridge command required')
        with self.send_lock:self.proc.stdin.write(text+'\n');self.proc.stdin.flush()

    def key(self,code,down):self.send(f'KEY {int(down)} {int(code)}')
    def clear_movement(self,codes):
        # The engine's keyboard cache can survive loading after its movement
        # buttons were cleared. Separate these releases from the new presses by
        # native game ticks; callers exclude fire/use/jump/slot keys.
        if not codes:return
        packet=''.join(f'KEY 0 {int(code)}\n' for code in sorted(codes))
        with self.send_lock:self.proc.stdin.write(packet);self.proc.stdin.flush()
    def pulse(self,code):
        self.key(code,True);time.sleep(.04);self.key(code,False);time.sleep(.04)
    def move(self,x,y=0):self.send(f'MOVE {int(x)} {int(y)}')
    def pause(self,value):
        if self.native_paused!=bool(value):self.pulse(112);self.native_paused=bool(value)
    def command(self,text):
        if text.startswith('STROBE_VIEW '):self.pulse(107 if text.endswith('1') else 104)
        elif text=='VCLOSE':self.pulse(106)
        else:raise ValueError('Unsupported native command')
    def state(self):
        with self.lock:return json.loads(json.dumps(self.latest))
    def frame(self,_=0):
        for _ in range(30):
            before=struct.unpack_from('<Q',self.mem,32)[0]
            if before&1:time.sleep(.001);continue
            picture=np.frombuffer(self.mem,dtype=np.uint8,offset=64,count=1280*800*4).reshape(800,1280,4)[::-1].copy()
            after=struct.unpack_from('<Q',self.mem,32)[0]
            if before==after:self.last_picture=picture;return picture
        if hasattr(self,'last_picture'):return self.last_picture.copy()
        raise RuntimeError('No coherent native picture')
    @property
    def frame_seq(self):return struct.unpack_from('<Q',self.mem,16)[0] if self.mem else 0
    def buy(self,vendor,slot):
        if type(slot) is not int or not 0<=slot<3 or vendor!=self.latest.get('vending',{}).get('vendor',{}).get('id'):raise ValueError('Unknown offer')
        with self.lock:self.receipts.clear()
        self.pulse((117,105,111)[slot]);self.wait(lambda:bool(self.receipts))
        with self.lock:result=self.receipts[-1]
        if result['ok']:self.wait(lambda:not self.latest.get('vending',{}).get('menu_open'))
        return result
    def close(self):
        if self.closed:return
        self.closed=True
        p=getattr(self,'proc',None)
        if p and p.poll() is None:
            try:self.send('QUIT');p.wait(timeout=3)
            except (OSError,subprocess.TimeoutExpired):
                try:os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=3)
                except ProcessLookupError:pass
                except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait(timeout=3)
        if getattr(self,'reader',None):self.reader.join(timeout=2)
        if self.mem:self.mem.close()
        if self.fd:self.fd.close()
        self.log.close()
