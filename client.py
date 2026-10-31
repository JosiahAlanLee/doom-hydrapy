# SPDX-License-Identifier: GPL-2.0-or-later
"""Pipe-controlled engine; no engine library is loaded into Python."""
from pathlib import Path
import json, mmap, os, select, struct, subprocess, tempfile
import numpy as np

class Doom:
    def __init__(self, wad, demo='demo1', locked=True, loop_seconds=None,
                 pwad=None, rogue_floors=None, clean_hud=False):
        if loop_seconds is not None and (not np.isfinite(loop_seconds) or loop_seconds<=0): raise ValueError("positive loop duration required")
        self.loop_seconds=loop_seconds
        self.wad, self.demo, self.locked = str(Path(wad).resolve()), demo, locked
        self.pwad = str(Path(pwad).resolve()) if pwad else None
        self.rogue_floors = rogue_floors
        self.clean_hud = bool(clean_hud)
        if rogue_floors is not None and (not isinstance(rogue_floors, int) or not 1 <= rogue_floors <= 5):
            raise ValueError('rogue_floors must be 1..5')
        (Path(__file__).parent/'runtime').mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix='doom-', dir=Path(__file__).parent/'runtime')
        self.start()
    def start(self):
        env = dict(os.environ, DOOM_FRAME=self.tmp.name+'/frame')
        env.pop('DOOM_ROGUE_FLOORS', None)
        if self.rogue_floors: env['DOOM_ROGUE_FLOORS']=str(self.rogue_floors)
        env.pop('DOOM_CLEAN_HUD',None)
        if self.clean_hud:
            env['DOOM_CLEAN_HUD']='1'
            Path(self.tmp.name+'/doom.cfg').write_text('screenblocks 11\n')
        if self.locked: env['DOOM_LOCKED']='1'
        else: env.pop('DOOM_LOCKED',None)
        args=[str(Path(__file__).parent/'doomgeneric/doom-ipc'), '-iwad',self.wad, '-config',self.tmp.name+'/doom.cfg']
        if self.pwad: args += ['-file', self.pwad]
        if self.demo: args += ['-playdemo',self.demo]
        else: args += ['-warp','1','-skill','3']
        self.log=open(self.tmp.name+'/engine.log','w')
        self.proc=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True,bufsize=1,cwd=self.tmp.name,env=env)
        self._read('READY')
        self.fd=open(self.tmp.name+'/frame','r+b');self.mem=mmap.mmap(self.fd.fileno(),0)
        self.base=self.tic;self.target=0
    def _read(self, prefix='OK'):
        if not select.select([self.proc.stdout],[],[],20)[0]: raise TimeoutError('engine timeout: '+self.tmp.name+'/engine.log')
        line=self.proc.stdout.readline().strip().split()
        if not line or line[0]!=prefix:
            self.log.flush()
            detail=Path(self.tmp.name+'/engine.log').read_text(errors='replace')[-1200:]
            raise RuntimeError('engine failed (exit '+str(self.proc.poll())+', response '+str(line)[:160]+'): '+self.tmp.name+'/engine.log\n'+detail)
        self.tic,self.frames=map(int,line[1:])
    def command(self, text):
        self.proc.stdin.write(text+'\n');self.proc.stdin.flush();self._read()
    def key(self, code, down): self.command(f'KEY {int(down)} {code}')
    def state(self):
        self.proc.stdin.write('STATE\n');self.proc.stdin.flush()
        if not select.select([self.proc.stdout],[],[],20)[0]: raise TimeoutError('engine STATE timeout')
        line=self.proc.stdout.readline()
        if not line.startswith('STATE '): raise RuntimeError('invalid engine state response')
        return json.loads(line[6:])
    def monsters(self):
        self.proc.stdin.write('MOBS\n');self.proc.stdin.flush()
        if not select.select([self.proc.stdout],[],[],20)[0]: raise TimeoutError('engine MOBS timeout')
        line=self.proc.stdout.readline()
        if not line.startswith('MOBS '):raise RuntimeError('invalid monster state response')
        return json.loads(line[5:])
    def advance(self,n):
        if not 0<=n<=35000: raise ValueError('STEP range 0..35000')
        old=self.tic;self.command(f'STEP {n}')
        if self.locked and self.tic-old!=n: raise RuntimeError('tic drift')
    def frame(self, seconds):
        if not np.isfinite(seconds): raise ValueError('finite time required')
        seconds=max(0,seconds) # renderer prewarm visits negative times
        if self.loop_seconds is not None: seconds%=self.loop_seconds
        target=int(seconds*35+1e-8)
        if target<self.target:
            self.stop();self.start()
        if self.locked:
            left=target-self.target
            while left: n=min(left,35000);self.advance(n);left-=n
        else: self.advance(0)
        self.target=target
        w,h=struct.unpack_from('<II',self.mem,4)
        for attempt in range(1000):
            before=struct.unpack_from("<Q",self.mem,32)[0]
            if before%2: continue
            bgra=np.frombuffer(self.mem,dtype=np.uint8,offset=64,count=w*h*4).reshape(h,w,4).copy()
            if before==struct.unpack_from("<Q",self.mem,32)[0]: break
        else: raise RuntimeError("frame writer busy")
        rgba=bgra[:,:,[2,1,0,3]].copy();rgba[:,:,3]=255
        return rgba
    def stop(self):
        if hasattr(self,'mem'): self.mem.close();self.fd.close()
        if self.proc.poll() is None:
            self.proc.stdin.write('QUIT\n');self.proc.stdin.flush()
            try: self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired: self.proc.kill();self.proc.wait()
        self.proc.stdin.close();self.proc.stdout.close();self.log.close()
    def close(self): self.stop();self.tmp.cleanup()
    def __enter__(self): return self
    def __exit__(self,*exc): self.close()
