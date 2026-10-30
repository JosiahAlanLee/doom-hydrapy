# SPDX-License-Identifier: GPL-2.0-or-later
"""Optional HydraPy plugin, kept entirely in the GPL repository.
Import doom explicitly: from ops_doom import doom. Own/close the engine separately.
"""
from hydrapy import FrameSource, src

def doom(engine):
    # Quantize UVs to texel centres, retaining crisp pixels with GL's linear sampler.
    return src(FrameSource(engine.frame)).pixelate(640,400)

class LaneKeys:
    """Call once per tracker update. Hits/gates must be booleans, pitch MIDI note.
    lane 1 gate -> fire, lead pitch <60/>60 -> turn, move gate -> forward.
    Pass held gates, not a stream of note-on-only events. close() releases all.
    """
    def __init__(self, engine): self.engine=engine;self.held=set()
    def update(self, fire=False, pitch=60, move=False, use=False):
        keys={k for k,v in [(0x9d,fire),(0xac,pitch<60),(0xae,pitch>60),(0xad,move),(32,use)] if v}
        for k in sorted(keys^self.held): self.engine.key(k,k in keys)
        self.held=keys
    def close(self): self.update()
