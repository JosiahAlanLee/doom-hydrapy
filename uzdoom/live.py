# SPDX-License-Identifier: GPL-3.0-or-later
"""1280x800 native UZDoom through HydraPy, with a separate readable HUD."""
from pathlib import Path
import os
import numpy as np
from PIL import Image
from hydrapy import FrameSource,Fn,src,scene,render,o0
from hydrapy.live import register_hook
import hydrapy.live as resources
from uzdoom.desktop import start

import legible_ops

STUDIO=dict(title='NULL RUN / TOWER')
game=start(Path(os.environ['NULLRUN_ROOT']),os.environ['FREEDOOM_WAD'],port=int(os.environ.get('NULLRUN_PORT','8774')),resources=resources)

_last_world=[None]
_last_hud=[None]
def world(t):
    frame=game.snapshot(t)['raw']
    if frame is _last_world[0]:return None
    _last_world[0]=frame
    return frame
def hud(t):
    frame=game.snapshot(t)['hud']
    if frame is _last_hud[0]:return None
    _last_hud[0]=frame
    return frame

source=src(FrameSource(world));instruments=src(FrameSource(hud))
# The CPU mask remains sharp after world treatment. No default green filter.
treated=source.blend(source.ruttetra(100,.12,1.1,.25).color(.4,1,.8),Fn(lambda c:float(game.mode==1)))
treated=treated.blend(source.doomLegibleAscii(240),Fn(lambda c:float(game.mode==2)))
treated=treated.blend(source.doomLegiblePrint(),Fn(lambda c:float(game.mode==3)))
scene('tower')(lambda:treated.layer(instruments))
render(o0)
register_hook(lambda ctx,renderer:game.tick(ctx,renderer))
