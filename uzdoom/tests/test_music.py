# SPDX-License-Identifier: GPL-3.0-or-later
"""Backend checks use the real tracker clock, validator and replacement code."""
import copy
import os
from pathlib import Path
import json
import unittest
from uzdoom.adaptive_host import Backend,document,ROOT,Engine,BAR,ROW,CYCLE,TICKS
from hydrapy.studio_tracker import Tracker


class StudioFixture:
    def __init__(self):
        self.tracker=Tracker(json.loads((Path(os.environ['NULLRUN_INITIAL_SCORE'])).read_text()))
        self.time=0.;self.rendering=True;self.calls=0;self.maximum_ms=0
    def get(self):return self.tracker.snapshot(self.time,True)
    def post(self,endpoint,payload):
        self.calls+=1
        if endpoint=='tracker_score':self.tracker.replace(payload['document'],self.time,payload['revision'])
        elif endpoint=='tracker_transport':
            self.rendering=payload.get('playing',True)
            enabled=payload.get('enabled',self.tracker.enabled)
            if 'beat' in payload or enabled!=self.tracker.enabled:
                self.tracker.seek(payload.get('beat',self.tracker.beat(self.time)),self.time)
            self.tracker.enabled=enabled
        else:raise AssertionError(endpoint)
        return self.get()


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.studio=StudioFixture();self.backend=Backend(self.studio)
        self.engine=Engine(20261031,'drowned_records',materialize=False)
        self.backend.reset(self.engine,1,'drowned_records',False)

    def test_all_sections_have_one_fixed_valid_eight_bar_loop(self):
        for env in self.engine.profiles:
            for kind in ['exploration','threat','combat','quiet','boss_sealed','boss_exposed','boss_one_down','bridge','death','victory']:
                doc=document(self.engine,kind,1,env,BAR*3)
                self.assertEqual(doc['chain'],[0]);self.assertTrue(doc['loop'])
                self.assertEqual(sum(p is not None for p in doc['patterns']),1)
                self.assertTrue(all(l['len']==128 and len(l['cells'])==128 for l in doc['patterns'][0]['lanes']))
                self.assertFalse(doc['patterns'][0]['scenes'])

    def test_pause_freezes_music_but_keeps_renderer_and_input_hooks_running(self):
        self.studio.time=2.
        frozen=self.backend.clock(self.studio.get())
        self.backend.pause(True)
        self.studio.time=112.
        self.assertEqual(self.backend.clock(self.studio.get()),frozen)
        self.assertTrue(self.studio.rendering);self.assertFalse(self.studio.tracker.enabled)
        self.backend.pause(False);self.studio.time+=.25
        self.assertGreater(self.backend.clock(self.studio.get()),frozen)
        self.assertTrue(self.studio.rendering)

    def test_score_change_preserves_actual_tracker_phase(self):
        self.studio.time=2.5
        now=self.backend.clock(self.studio.get())
        self.assertEqual(now,BAR)
        before=self.studio.get()
        self.backend.enqueue([{'kind':'section','t':BAR,'payload':{'state':'combat','floor':1}}])
        self.backend.advance(now)
        after=self.studio.get()
        self.assertEqual(before['transport_revision'],after['transport_revision'])
        self.assertAlmostEqual(before['beat'],after['beat'])
        self.assertEqual(self.backend.kind,'combat')
        # The first bar of the new motif starts at the current bar, not row0.
        unrotated=document(self.engine,'combat',1,'drowned_records',0)
        for lane in range(6):
            self.assertEqual(self.backend.base['patterns'][0]['lanes'][lane]['cells'][16:32],
                             unrotated['patterns'][0]['lanes'][lane]['cells'][:16])

    def test_sting_is_monophonic_and_removed_before_loop_repeats(self):
        self.backend.enqueue([{'kind':'sting','t':0,'payload':{'sting':'enemy','cue_id':'e1'}}])
        self.backend.advance(0)
        cells=self.backend.doc['patterns'][0]['lanes'][5]['cells']
        notes=[(i,c) for i,c in enumerate(cells) if c]
        self.assertEqual(len(notes),2)
        self.assertLessEqual(notes[0][0]+notes[0][1]['len'],notes[1][0])
        self.backend.advance(int(self.backend.sting['until']))
        self.assertTrue(all(c is None for c in self.backend.doc['patterns'][0]['lanes'][5]['cells']))
        self.backend.advance(CYCLE*2)
        self.assertTrue(all(c is None for c in self.backend.doc['patterns'][0]['lanes'][5]['cells']))

    def test_new_seed_replaces_cached_music_and_pending_actions(self):
        before=copy.deepcopy(self.backend.base)
        self.backend.enqueue([{'kind':'sting','t':BAR,'payload':{'sting':'enemy','cue_id':'old'}}])
        self.backend.reset(Engine(43,'drowned_records',materialize=False),1,'drowned_records',False)
        self.assertFalse(self.backend.queue)
        self.assertNotEqual(before['patterns'],self.backend.base['patterns'])
        self.assertEqual(self.backend.now,0)

    def test_duck_restores_voices_without_touching_game_transport(self):
        self.backend.enqueue([{'kind':'duck','t':0,'payload':{'mask':[2,3,4],'until':TICKS*2}}])
        self.backend.advance(0)
        self.assertEqual(self.backend.doc['mutes'],[False,False,True,True,True,False])
        self.backend.advance(TICKS*2)
        self.assertEqual(self.backend.doc['mutes'],[False]*6)
        self.assertTrue(self.studio.rendering)

    def test_death_cancels_future_combat_that_would_restart_music(self):
        self.backend.enqueue([{'kind':'section','t':BAR*4,'payload':{'state':'combat','floor':1}}])
        self.backend.enqueue([{'kind':'transition','t':BAR,'payload':{'kind':'death','floor':1}}])
        self.backend.advance(BAR*4)
        self.assertEqual(self.backend.kind,'death')
        self.assertFalse(self.backend.queue)

    def test_all_emitted_game_cues_follow_the_real_event_contract(self):
        from nullrun_music.events import Cue
        for kind,payload in [('combat_start',{}),('combat_end',{}),('enemy_sting',{'enemy':'native_warning'}),
                             ('secret',{}),('pause',{}),('resume',{})]:
            self.assertEqual(Cue('test-'+kind,0,kind,payload).type,kind)

    def test_boss_transition_keeps_its_own_sting_in_the_same_action_batch(self):
        self.backend.enqueue([
            {'kind':'sting','t':0,'payload':{'sting':'boss','cue_id':'boss1'}},
            {'kind':'transition','t':0,'payload':{'kind':'bridge','floor':1}}])
        self.backend.advance(0)
        self.assertEqual(self.backend.kind,'bridge')
        self.assertEqual(sum(c is not None for c in self.backend.doc['patterns'][0]['lanes'][5]['cells']),3)

    def test_same_frame_boss_activity_cannot_override_player_death(self):
        from uzdoom.adaptive_host import terminal_cues
        from nullrun_music.events import Cue
        cues=[Cue('d',0,'player_death',{}),Cue('b',0,'boss_encounter',{'names':['A','B'],'tier':1}),
              Cue('c',0,'combat_start',{})]
        self.assertEqual([c.type for c in terminal_cues(cues,{'dead':True})],['player_death'])

    def test_stale_cached_snapshot_after_retry_cannot_rewind_music(self):
        self.studio.time=8.
        self.backend.clock(self.studio.get())
        stale=copy.deepcopy(self.studio.get())
        self.backend.reset(Engine(43,'after_hours_pavilion',materialize=False),1,'after_hours_pavilion',False)
        self.assertEqual(self.backend.clock(stale),0)
        self.studio.time+=.1
        self.assertGreater(self.backend.clock(self.studio.get()),0)

    def test_same_score_but_old_transport_snapshot_is_ignored(self):
        old=copy.deepcopy(self.studio.get())
        self.backend.pause(True)
        old['revision']=self.backend.accepted_revision
        self.assertEqual(self.backend.clock(old),0)


if __name__=='__main__':unittest.main(verbosity=2)
