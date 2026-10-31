# SPDX-License-Identifier: GPL-3.0-or-later
"""The same world-treatment chain for live play and GPU verification."""
from hydrapy import Fn
import legible_ops
import uzdoom.cue_ops


def world_effects(source,mode,cues):
    treated=source.blend(source.ruttetra(100,.12,1.1,.25).color(.4,1,.8),Fn(lambda c:float(mode()==1)))
    treated=treated.blend(source.doomLegibleAscii(240),Fn(lambda c:float(mode()==2)))
    treated=treated.blend(source.doomLegiblePrint(),Fn(lambda c:float(mode()==3)))
    treated=treated.nullRunQuietCue(Fn(lambda c:cues(c.time)['quiet_strength']),Fn(lambda c:cues(c.time)['quiet_progress']))
    return treated.nullRunSurveyorCue(Fn(lambda c:cues(c.time)['surveyor_strength']),Fn(lambda c:cues(c.time)['surveyor_progress']))
