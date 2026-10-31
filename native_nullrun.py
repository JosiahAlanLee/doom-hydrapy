# SPDX-License-Identifier: GPL-2.0-or-later
"""Reference native-window Studio patch; see NATIVE-PLAY.md for the private rig."""
from pathlib import Path
import os
import numpy as np
from hydrapy import *
from hydrapy.live import register_hook
import hydrapy.live as live_resources
from rogue.desktop import start
from rogue.audio import optical_lead
import rogue.strobe_ops

ROOT = Path(os.environ['NULLRUN_ROOT'])
STUDIO = dict(title='NULL RUN / Fluorescent Hollow / HydraPy + VCV')
set_bpm(120)
carrier = optical_lead()
game = start(ROOT, os.environ['FREEDOOM_WAD'],campaign_only=False,autostart=False,
             initial_mode='strobe',resources=live_resources)
beat = tracker.beat()
music = Audio(jack='rack_return', sr=48000, bins=4, smooth=.6, scale=1, cutoff=0)


def sample(ctx):
    return game.snapshot(ctx.time)


last_image = [None]


def draw(t):
    image = game.snapshot(t)['image']
    if image is last_image[0]:
        return None
    last_image[0] = image
    return np.asarray(image)


source = src(FrameSource(draw)).pixelate(640, 400)
live = source.nullrunScreen(light=Fn(lambda c: sample(c)['light']),
                           muzzle=Fn(lambda c: sample(c)['muzzle']),
                           mode=Fn(lambda c: game.mode),
                           flicker=Fn(lambda c: float(game.flicker)), music=music.vol)
ghost = src(o0).color(Fn(lambda c: sample(c)['decay']*.70),
                     Fn(lambda c: sample(c)['decay']),
                     Fn(lambda c: sample(c)['decay']*.85))
scene('nullrun')(lambda: live.lighten(ghost, 1))
render(o0)


def frame(ctx, renderer):
    game.tick(ctx, renderer, beat)


register_hook(frame)
