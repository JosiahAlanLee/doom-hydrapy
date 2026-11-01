# SPDX-License-Identifier: GPL-2.0-or-later
"""Optical carrier required by the Afterimage ByteBus formant instrument."""
from hydrapy import Fn, Harmonograph, Param, XY, tracker


class _Carrier(XY):
    def _draw_phosphor(self, xy, z):
        # This voice feeds Studio's optical ports without a picture overlay.
        pass


def optical_lead():
    """Register the score-pitched XY voice before Studio opens its audio ports.

    The ByteBus Lookup modules shape an incoming waveform; a gated static
    address is a DC pulse, not an oscillator. These streams must remain present
    even when the displayed scene is a native game framebuffer.
    """
    dolly = Param('Dolly Z', .3, min=0, max=1)
    Param('Roll', 0, min=-45, max=45, step=1, unit='degrees')
    Param('Feedback', .3, min=0, max=.9)
    lead = tracker.ahead(.066)
    hz = 440 * 2 ** ((lead.note(4)-69)/12)
    partial = Fn(lambda c: (0, 2, 3, 4)[min(3, int(float(dolly(c))*4))])
    figure = Harmonograph(1, 2, partial, 0, phase=1.5708, size=.92, speed=.25)
    return _Carrier(figure, rate=hz, fps=60, gain=.9, jump=0, record=False,
                    preview=(16, 16), persistence=0)
