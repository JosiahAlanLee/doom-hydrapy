# SPDX-License-Identifier: GPL-2.0-or-later
"""Native warning semantics, exact UI/RAW preservation and host sampling."""
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, main, skipUnless
from unittest.mock import Mock
import importlib.util
import os
import tempfile
import threading
import numpy as np
from rogue.optics import (MAX_ACTORS, RAW, NativeOpticsSampler,
                          TacticalOpticsDirector, numpy_optics, register_hydrapy_ops)


def surveyor(ticks=31, **changes):
    return dict({'class':11,'argon_kind':'surveyor','health':85,'missile':False,
                 'argon_phase':2,'warning_ticks':ticks}, **changes)


def enabled(mobs):return TacticalOpticsDirector.compute_uniforms(mobs, raw_mode=False)


class NativeTelemetry(TestCase):
    def test_native_countdown_counts_up_instead_of_going_backwards(self):
        self.assertEqual([enabled([surveyor(n)]).surveyor_tic for n in (35,31,8,1)],[1,5,28,35])
        self.assertEqual(enabled([surveyor(31)]).warning_ticks,31)
        self.assertEqual(enabled([surveyor(0,argon_phase=3)]).surveyor_tic,0)

    def test_most_urgent_surveyor_wins_independent_of_list_order(self):
        mobs=[surveyor(30),surveyor(4),surveyor(20)]
        self.assertEqual(enabled(mobs),enabled(list(reversed(mobs))))
        self.assertEqual(enabled(mobs).surveyor_tic,32)

    def test_dead_missiles_and_other_creatures_do_not_make_warnings(self):
        cases=[{'health':0},{'health':-1},{'missile':True},{'argon_kind':'wire_shambler'},
               {'class':15},{'argon_phase':1},{'argon_phase':3},{'argon_phase':4}]
        for change in cases:
            self.assertEqual(enabled([surveyor(**change)]).surveyor_tic,0,change)

    def test_malformed_or_legacy_fields_cannot_create_a_cue(self):
        bad=[None,[],{'hp':100,'kind':'SURVEYOR','warning_tic':35}]
        for value in (None,True,'31',31.5,-1,0,36,float('nan'),float('inf'),10**1000):
            bad.append(surveyor(value))
        for value in (None,True,'85',85.0,0,-1,float('nan'),float('inf'),10**1000):
            bad.append(surveyor(31,health=value))
        self.assertEqual(enabled(bad).surveyor_tic,0)
        self.assertEqual(enabled([dict(surveyor(),missile=None)]).surveyor_tic,0)
        self.assertEqual(enabled([surveyor(31,**{'class':11.0})]).surveyor_tic,0)

    def test_raw_is_default_and_lifecycle_states_bypass_telemetry(self):
        self.assertEqual(TacticalOpticsDirector.compute_uniforms([surveyor()]),RAW)
        for flag in ('paused','dead','won'):
            self.assertEqual(TacticalOpticsDirector.compute_uniforms(None,raw_mode=False,**{flag:True}),RAW)
        self.assertEqual(RAW.shader_inputs(),{'surveyor_tic':0,'raw':1.})

    def test_repeated_display_frames_do_not_advance_the_timer(self):
        before=enabled([surveyor(31)])
        for _ in range(120):self.assertEqual(enabled([surveyor(31)]),before)

    def test_invalid_batch_and_flags_are_rejected(self):
        for value in ({},'mobs',(n for n in []),[{}]*(MAX_ACTORS+1)):
            with self.assertRaises(ValueError):enabled(value)
        with self.assertRaises(ValueError):TacticalOpticsDirector.compute_uniforms([],raw_mode='false')


class SnapshotSampling(TestCase):
    def setUp(self):
        self.state={'revision':1,'frame':4,'gamestate':0,'paused':False,'dead':False,'won':False}
        self.game=SimpleNamespace(lock=threading.RLock(),revision=1,frame_seq=4,paused=False,
                                  engine=SimpleNamespace(monsters=Mock(return_value=[surveyor()])))
        self.desktop=SimpleNamespace(game=self.game,loading=False,
                                     snapshot=Mock(side_effect=lambda t:{'state':dict(self.state),'image':object()}))
        self.sampler=NativeOpticsSampler(self.desktop)

    def test_polls_once_per_native_frame_and_returns_one_render_snapshot(self):
        first=self.sampler.sample(0,raw_mode=False)
        self.assertIs(first,self.sampler.sample(0,raw_mode=False))
        self.sampler.sample(.016,raw_mode=False)
        self.game.engine.monsters.assert_called_once_with()
        self.state['frame']=self.game.frame_seq=5
        self.sampler.sample(.032,raw_mode=False)
        self.assertEqual(self.game.engine.monsters.call_count,2)

    def test_raw_does_no_polling_and_resume_reuses_only_the_same_native_frame(self):
        self.assertEqual(self.sampler.sample(0)[1],RAW)
        self.game.engine.monsters.assert_not_called()
        self.assertEqual(self.sampler.sample(.016,raw_mode=False)[1].surveyor_tic,5)
        self.game.paused=True;self.assertEqual(self.sampler.sample(.016,raw_mode=False)[1],RAW)
        self.game.paused=False
        self.assertEqual(self.sampler.sample(.016,raw_mode=False)[1].surveyor_tic,5)
        self.game.engine.monsters.assert_called_once_with()

    def test_incoherent_picture_cannot_use_newer_mob_data(self):
        self.game.frame_seq=5
        self.assertEqual(self.sampler.sample(0,raw_mode=False)[1],RAW)
        self.game.engine.monsters.assert_not_called()

    def test_restart_at_same_time_invalidates_previous_revision(self):
        self.sampler.sample(0,raw_mode=False)
        self.game.revision=self.state['revision']=2
        self.game.engine.monsters.return_value=[]
        self.assertEqual(self.sampler.sample(0,raw_mode=False)[1].surveyor_tic,0)
        self.assertEqual(self.game.engine.monsters.call_count,2)

    def test_busy_builder_and_failed_poll_fall_back_without_repeated_polling(self):
        self.desktop.loading=True
        self.assertEqual(self.sampler.sample(0,raw_mode=False)[1],RAW)
        self.game.engine.monsters.assert_not_called()
        self.desktop.loading=False;self.game.engine.monsters.side_effect=RuntimeError('no snapshot')
        self.assertEqual(self.sampler.sample(.016,raw_mode=False)[1],RAW)
        self.sampler.sample(.032,raw_mode=False)
        self.game.engine.monsters.assert_called_once_with()
        self.assertEqual(self.sampler.last_error,'no snapshot')

    def test_busy_simulation_never_blocks_the_render_thread(self):
        held=threading.Event();release=threading.Event()
        def own_lock():
            with self.game.lock:held.set();release.wait(3)
        thread=threading.Thread(target=own_lock);thread.start();self.assertTrue(held.wait(1))
        try:
            self.assertEqual(self.sampler.sample(0,raw_mode=False)[1],RAW)
            self.game.engine.monsters.assert_not_called()
        finally:release.set();thread.join(3)

    def test_invalid_render_clock_is_rejected(self):
        for t in (True,'1',float('nan'),float('inf'),10**1000):
            with self.assertRaises(ValueError):self.sampler.sample(t)


@skipUnless(importlib.util.find_spec('hydrapy'),'Make HydraPy importable for renderer checks')
class Rendering(TestCase):
    def setUp(self):
        from hydrapy.backend_np import Env
        self.env=Env(640,400,filter='nearest')
        self.tex=np.random.default_rng(24).random((400,640,4),dtype=np.float32)

    def draw(self,tic=35,raw=0):
        return numpy_optics(self.tex,self.env.base_st,tic,raw,self.env)

    def test_raw_preserves_every_rgba_channel_exactly(self):
        self.assertTrue(np.array_equal(self.draw(raw=1),self.tex))
        self.assertTrue(np.array_equal(self.draw(tic=float('nan'),raw=1),self.tex))

    def test_invalid_uniforms_fall_back_to_the_original_image(self):
        for tic,raw in [(float('nan'),0),(float('inf'),0),(-1,0),(36,0),(1,float('nan')),
                        (1,-1),(1,2),(1,'0'),([1,2],0)]:
            self.assertTrue(np.array_equal(self.draw(tic,raw),self.tex),(tic,raw))

    def test_current_hud_bands_and_crosshair_are_bit_exact(self):
        # Compare physical top-down image rows, independently of shader masks.
        original=self.tex[::-1]
        for tic in (0,1,27,28,35):
            image=self.draw(tic)[::-1]
            self.assertTrue(np.array_equal(image[:88],original[:88]))
            self.assertTrue(np.array_equal(image[353:],original[353:]))
            self.assertTrue(np.array_equal(image[180:209,308:333],original[180:209,308:333]))
            self.assertFalse(np.array_equal(image[100:130],original[100:130]))

    def test_segments_match_native_progress_and_colour_without_strobing(self):
        self.tex[:]=0;self.tex[...,3]=1
        for tic in (1,5,27,28,35):
            image=self.draw(tic)[::-1]
            for segment in range(35):
                x=int(96+(segment+.5)*448/35)
                expected=(.98,.22,.08) if tic>=28 else (.98,.78,.16)
                if segment>=tic:expected=(.10,.13,.12)
                np.testing.assert_allclose(image[340,x,:3],expected,atol=1e-6)
        self.assertTrue(np.array_equal(self.draw(28),self.draw(28)))

    def test_hydrapy_chain_uses_default_raw_and_preserves_image_orientation(self):
        from hydrapy import FrameSource,src
        from hydrapy.backend_np import render_chain
        register_hydrapy_ops()
        picture=(self.tex*255).astype(np.uint8)
        source=src(FrameSource(lambda t:picture))
        result=render_chain(source.nullrunSurveyorOptics(),size=(640,400),filter='nearest')
        self.assertTrue(np.array_equal(result,picture.astype(np.float32)/255))

    def test_integer_upscale_keeps_native_cell_edge_detail(self):
        from hydrapy import FrameSource,src
        from hydrapy.backend_np import render_chain
        register_hydrapy_ops()
        picture=(self.tex*255).astype(np.uint8)
        chain=src(FrameSource(lambda t:picture)).pixelate(640,400).nullrunSurveyorOptics(raw=0)
        native=render_chain(chain,size=(640,400),filter='nearest')
        large=render_chain(chain,size=(1280,800),filter='nearest')
        np.testing.assert_allclose(large[::2,::2],native,atol=1e-6)


@skipUnless(os.environ.get('FREEDOOM_WAD'),'Set FREEDOOM_WAD for real telemetry')
class EngineTelemetry(TestCase):
    def test_actual_surveyor_warning_then_attack_and_pause(self):
        from client import Doom
        from test_gloamwood import room
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'surveyor.wad';room(path,'surveyor')
            with Doom(os.environ['FREEDOOM_WAD'],demo=None,pwad=path,rogue_floors=1) as engine:
                engine.advance(2)
                mobs=engine.monsters();mob=next(m for m in mobs if m.get('argon_kind')=='surveyor')
                self.assertEqual(mob['argon_phase'],2);self.assertGreater(mob['warning_ticks'],0)
                cue=enabled(mobs)
                self.assertEqual(cue.warning_ticks,mob['warning_ticks'])
                self.assertGreater(cue.surveyor_tic,0)
                self.assertEqual(TacticalOpticsDirector.compute_uniforms(mobs,raw_mode=False,paused=True),RAW)
                engine.advance(40)
                self.assertEqual(enabled(engine.monsters()).surveyor_tic,0)


if __name__=='__main__':main(verbosity=2)
