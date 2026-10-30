# SPDX-License-Identifier: GPL-2.0-or-later
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import source
import ascii_op
SCENE=dict(name='cx-doom-feedback',author='Codex; engine by id Software/doomgeneric; game data by Freedoom',algorithms=['Doom engine', 'recursive feedback', 'posterization'],palette='Freedoom processed',keys='Demo advances 35 tics per second of renderer time',notes='GPL plugin, engine runs in child process')
def build(ctx):
    return source().blend(ctx.prev.scale(1.006).scrollX(.002),.25).posterize(5,.7).saturate(.6)
