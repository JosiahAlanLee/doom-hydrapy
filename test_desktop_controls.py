# SPDX-License-Identifier: GPL-2.0-or-later
"""Keep remote visual adjustments separate from the native player's controls."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase,main
from unittest.mock import Mock
import json
import threading
import numpy as np
from PIL import Image
from rogue.desktop import Desktop


class DesktopControls(TestCase):
    def control(self,root):
        d=Desktop.__new__(Desktop)
        d.root=Path(root);d.mode=1;d.flicker=True;d.view_lock=threading.Lock()
        d.clear_frames=0;d.input_source='physical';d.owner='native-player'
        d.game=SimpleNamespace(paused=False,lock=threading.RLock(),engine=SimpleNamespace(command=Mock()))
        return d

    def test_visual_change_preserves_live_player_and_saves_preference(self):
        with TemporaryDirectory() as root:
            d=self.control(root)
            d.action({'action':'filter','mode':0},automated=True)
            self.assertEqual((d.mode,d.owner,d.input_source),(0,'native-player','physical'))
            self.assertFalse(d.game.paused)
            self.assertEqual(json.loads((Path(root)/'view-settings.json').read_text()),{'mode':0,'flicker':True})

    def test_remote_control_cannot_interrupt_native_player(self):
        with TemporaryDirectory() as root:
            d=self.control(root)
            for action in ['resume','pause','keys','new']:
                with self.assertRaisesRegex(ValueError,'native player'):d.action({'action':action},automated=True)
            self.assertEqual(d.owner,'native-player')

    def test_steady_view_is_visual_only_and_validates_boolean(self):
        with TemporaryDirectory() as root:
            d=self.control(root)
            with self.assertRaises(ValueError):d.action({'action':'flicker','enabled':0},automated=True)
            d.action({'action':'flicker','enabled':False},automated=True)
            d.game.engine.command.assert_called_once_with('STROBE_VIEW 0')
            self.assertEqual(d.owner,'native-player');self.assertFalse(d.game.paused)

    def test_unchanged_native_picture_does_not_redraw_text_every_display_frame(self):
        with TemporaryDirectory() as root:
            d=self.control(root);d.cache=None;d.last_time=None;d.loading=False
            state={'revision':1,'frame':1,'paused':True,'strobe':{'lit':True,'illumination':1}}
            d.game.snapshot=lambda:dict(state)
            d.game.rgb=np.zeros((400,640,3),dtype=np.uint8);d.game.error=None
            d.draw_screen=Mock(side_effect=lambda *_:Image.new('RGB',(640,400)))
            a=d.snapshot(0);b=d.snapshot(.016)
            self.assertIs(a['image'],b['image']);self.assertEqual(d.draw_screen.call_count,1)
            state['frame']=2;c=d.snapshot(.032)
            self.assertIsNot(c['image'],b['image']);self.assertEqual(d.draw_screen.call_count,2)
            d.mode=0;d.snapshot(.048);self.assertEqual(d.draw_screen.call_count,3)

    def test_simulation_releasing_controls_during_frame_keeps_hook_alive(self):
        from collections import deque
        from time import monotonic
        with TemporaryDirectory() as root:
            d=self.control(root);d.closed=False;d.bind=Mock();d.focused=True
            d.frames=deque(maxlen=181);d.need_sync=False;d.capture_requested=False;d.loading=False
            d.last_report=monotonic();d.keys={'KeyW'}
            d.game.input=Mock(side_effect=ValueError('Click Play to take the controls.'))
            renderer=SimpleNamespace(ctx=SimpleNamespace(info={'GL_RENDERER':'test'}))
            d.tick(None,renderer)
            self.assertIsNone(d.owner);self.assertIsNone(d.input_source)
            self.assertFalse(d.keys)


if __name__=='__main__':main(verbosity=2)
