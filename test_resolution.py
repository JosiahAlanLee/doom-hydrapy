# SPDX-License-Identifier: GPL-2.0-or-later
"""Real raster detail, unchanged simulation and native retry at doubled resolution."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main, skipUnless
import os

import numpy as np
from client import Doom
from rogue.maps import campaign


class ResolutionValidation(TestCase):
    def test_invalid_scale_and_legacy_hud_fail_before_starting_a_process(self):
        for scale in (True, False, 0, 3, 2.0, '2'):
            with self.assertRaisesRegex(ValueError, 'render_scale'):
                Doom('unused.wad', render_scale=scale)
        with self.assertRaisesRegex(ValueError, 'clean HUD'):
            Doom('unused.wad', render_scale=2)


@skipUnless(os.environ.get('FREEDOOM_WAD'), 'Set FREEDOOM_WAD and build both IPC engines')
class NativeResolution(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=TemporaryDirectory();cls.root=Path(cls.tmp.name)
        cls.wad=os.environ['FREEDOOM_WAD']
        cls.map=cls.root/'campaign.wad'
        campaign(20261031,cls.map,assets=cls.wad,identity=True)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def engine(self, scale):
        return Doom(self.wad,demo=None,pwad=self.map,rogue_floors=7,
                    clean_hud=True,render_scale=scale)

    def test_double_raster_adds_detail_instead_of_repeating_old_pixels(self):
        frames=[]
        for scale in (1,2):
            with self.engine(scale) as engine:
                engine.advance(35)
                state=engine.state();image=engine.frame(0)
                self.assertEqual(state['video'],dict(native_width=320*scale,native_height=200*scale,
                                                    output_width=640,output_height=400))
                self.assertEqual(image.shape,(400,640,4));self.assertTrue(np.all(image[...,3]==255))
                frames.append(image)
        repeated=lambda image:np.repeat(np.repeat(image[::2,::2],2,axis=0),2,axis=1)
        np.testing.assert_array_equal(frames[0],repeated(frames[0]))
        novelty=np.any(frames[1]!=repeated(frames[1]),axis=2)
        self.assertGreater(float(novelty.mean()),.01)
        # Rows past 255 must remain real floor samples, not wrapped plane bytes.
        self.assertGreater(float(frames[1][260:,:,:3].std()),5)

    def test_render_resolution_does_not_change_controls_combat_or_clock(self):
        def run(scale):
            with self.engine(scale) as engine:
                samples=[]
                for key,down,turn,tics in [(0xad,True,0,18),(0xad,False,80,1),
                                           (0xa3,True,0,70),(0xa3,False,-90,1),
                                           (9,True,0,1),(9,False,0,2)]:
                    engine.key(key,down);engine.turn(turn);engine.advance(tics)
                    state=engine.state();state.pop('video')
                    samples.append((state,engine.monsters()))
                return samples
        self.assertEqual(run(1),run(2))

    def test_native_game_keeps_higher_resolution_across_a_new_run(self):
        from rogue.desktop import NativeGame
        game=NativeGame(self.wad,self.root/'native-retry')
        try:
            self.assertEqual(game.state['video']['native_width'],640)
            self.assertEqual(game.rgb.shape,(400,640,3))
            before=game.revision
            game.new_run(20261033)
            self.assertTrue(game.paused);self.assertGreater(game.revision,before)
            self.assertEqual(game.state['video']['native_height'],400)
            self.assertEqual(game.manifest['environment']['id'],'after_hours_pavilion')
        finally:game.close()


if __name__=='__main__':main(verbosity=2)
