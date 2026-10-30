# SPDX-License-Identifier: GPL-2.0-or-later
"""Pipe-controlled engine; no engine library is loaded into Python."""
from pathlib import Path
import mmap, os, select, struct, subprocess, tempfile
import numpy as np

class Doom:
    def __init__(self, wad, demo='demo1', locked=True, loop_seconds=None):
        if loop_seconds is not None and (not np.isfinite(loop_seconds) or loop_seconds<=0): raise ValueError("positive loop duration required")
        self.loop_seconds=loop_seconds
        self.wad, self.demo, self.locked = str(Path(wad).resolve()), demo, locked
        self.tmp = tempfile.TemporaryDirectory(prefix='doom-', dir=Path(__file__).parent/'runtime')
        self.start()
    def start(self):
        env = dict(os.environ, DOOM_FRAME=self.tmp.name+'/frame')
        if self.locked: env['DOOM_LOCKED']='1'
        else: env.pop('DOOM_LOCKED',None)
        args=[str(Path(__file__).parent/'doomgeneric/doom-ipc'), '-iwad',self.wad, '-config',self.tmp.name+'/doom.cfg']
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
        if not line or line[0]!=prefix: raise RuntimeError('engine failed: '+self.tmp.name+'/engine.log')
        self.tic,self.frames=map(int,line[1:])
    def command(self, text):
        self.proc.stdin.write(text+'\n');self.proc.stdin.flush();self._read()
    def key(self, code, down): self.command(f'KEY {int(down)} {code}')
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
