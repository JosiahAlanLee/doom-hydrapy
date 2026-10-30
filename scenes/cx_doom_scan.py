# SPDX-License-Identifier: GPL-2.0-or-later
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import source
import ascii_op
SCENE=dict(name='cx-doom-scan',author='Codex; engine by id Software/doomgeneric; game data by Freedoom',algorithms=['Doom engine', 'Rutt Etra displacement', 'raster scan'],palette='Freedoom processed',keys='Demo advances 35 tics per second of renderer time',notes='GPL plugin, engine runs in child process')
def build(ctx):
    return source().ruttetra(100,.12,1.1,.25).color(.4,1,.8)
