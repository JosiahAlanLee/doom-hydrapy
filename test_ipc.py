# SPDX-License-Identifier: GPL-2.0-or-later
"""Integration checks: FREEDOOM_WAD=... python test_ipc.py"""
import hashlib,json,os,time
from client import Doom

def digest(f): return hashlib.sha256(f).hexdigest()
wad=os.environ['FREEDOOM_WAD']
results=[]
for run in range(2):
    with Doom(wad,demo='demo2',loop_seconds=60) as engine:
        samples=[]
        for t in [0,1,15,59,60,119,120,179,180,239,240]:
            samples.append((t,digest(engine.frame(t)),engine.tic-engine.base))
            assert engine.tic-engine.base==int(35*(t%60))
        assert digest(engine.frame(15))==samples[2][1]
        results.append(samples)
assert results[0]==results[1]
with Doom(wad,demo=None,locked=False) as engine:
    t=engine.tic;time.sleep(.2);engine.frame(0);assert engine.tic>t
with Doom(wad,demo=None) as engine:
    engine.key(0xad,True);moving=digest(engine.frame(1));engine.key(0xad,False)
with Doom(wad,demo=None) as engine:
    assert digest(engine.frame(1))!=moving
print(json.dumps(dict(deterministic_240s=True,loop_seconds=60,backwards_seek=True,free_running=True,keyboard_queue=True,samples=results[0]),indent=2))
