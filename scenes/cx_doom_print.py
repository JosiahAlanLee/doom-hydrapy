# SPDX-License-Identifier: GPL-2.0-or-later
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import source
import ascii_op
SCENE=dict(name='cx-doom-print',author='Codex; engine by id Software/doomgeneric; game data by Freedoom',algorithms=['Doom engine', 'halftone screening', 'limited ink'],palette='Freedoom processed',keys='Demo advances 35 tics per second of renderer time',notes='GPL plugin, engine runs in child process')
def build(ctx):
    return source().brightness(.12).saturate(.3).halftone(5,0.65,0.75).color(1,.82,.59)
