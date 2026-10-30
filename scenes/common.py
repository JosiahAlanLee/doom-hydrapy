# SPDX-License-Identifier: GPL-2.0-or-later
import atexit, os, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from client import Doom
from ops_doom import doom

def source():
    wad=os.environ.get('FREEDOOM_WAD')
    if not wad: raise RuntimeError('Set FREEDOOM_WAD to official freedoom2.wad')
    engine=Doom(wad, demo=os.environ.get('FREEDOOM_DEMO','demo1'),loop_seconds=60)
    atexit.register(engine.close)
    return doom(engine)
