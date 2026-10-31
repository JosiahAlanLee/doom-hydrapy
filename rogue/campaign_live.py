# SPDX-License-Identifier: GPL-2.0-or-later
"""Native seven-tier player. Rack supplies independent, lightweight ambience."""
from pathlib import Path
import os
import numpy as np
from hydrapy import FrameSource,src,scene,render,o0
from hydrapy.live import register_hook
import hydrapy.live as live_resources
from rogue.desktop import start

ROOT=Path(os.environ['NULLRUN_ROOT'])
STUDIO=dict(title='NULL RUN')
game=start(ROOT,os.environ['FREEDOOM_WAD'],port=int(os.environ.get('NULLRUN_PORT','8773')),
           campaign_only=True,autostart=True,resources=live_resources)
last_image=[None]

def picture(t):
    image=game.snapshot(t)['image']
    if image is last_image[0]:return None
    last_image[0]=image
    return np.asarray(image)

source=src(FrameSource(picture)).pixelate(640,400)
scene('nullrun')(lambda:source)
render(o0)

def frame(ctx,renderer):
    game.tick(ctx,renderer)
register_hook(frame)
