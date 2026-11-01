# SPDX-License-Identifier: GPL-3.0-or-later
"""Effects follow real semantic state and cannot outlive a stale native tick."""
import copy,unittest
from uzdoom.cues import Cues,encounter_inputs


def state():
    return dict(seed=42,revision=1,map=1,level_tics=10,x=0,y=0,paused=False,health=100,
                bosses=[dict(name='CALMOR',**{'class':6},health=180,phase='sealed',on_seal=True,still_ticks=17)],
                mobs=[dict(**{'class':11},health=85,phase=2,sight=True,warning_ticks=20,x=256,y=0)])


class CueTests(unittest.TestCase):
    def test_real_charge_and_most_urgent_warning(self):
        s=state();s['mobs'].append(dict(s['mobs'][0],warning_ticks=3))
        c=Cues().sample(s,now=0)
        self.assertEqual(c['surveyor_count'],2);self.assertAlmostEqual(c['surveyor_progress'],32/35)
        self.assertAlmostEqual(c['quiet_progress'],17/35);self.assertGreater(c['quiet_strength'],0)
        self.assertLess(c['quiet_strength'],Cues().sample(dict(s,mobs=[]),now=0)['quiet_strength'])
    def test_pause_modal_death_and_disabled_are_raw(self):
        for field in ('paused','dead','won','error','loading'):
            s=state();s[field]=True;c=Cues().sample(s,now=0)
            self.assertEqual(c['quiet_strength'],0);self.assertEqual(c['surveyor_strength'],0)
        for s,enabled in [(dict(state(),vending={'menu_open':True}),True),(state(),False)]:
            c=Cues().sample(s,enabled,now=0);self.assertEqual(c['quiet_strength']+c['surveyor_strength'],0)
    def test_charge_stops_on_exposure_and_leaving_seal(self):
        for update in ({'phase':'exposed'},{'phase':'bound'},{'on_seal':False},{'still_ticks':0},{'health':0}):
            s=state();s['bosses'][0].update(update)
            self.assertEqual(Cues().sample(s,now=0)['quiet_strength'],0)
    def test_irrelevant_dead_hidden_distant_and_finished_enemies_do_not_warn(self):
        for update in ({'class':12},{'health':0},{'sight':False},{'x':5000},{'phase':3},{'warning_ticks':0},{'warning_ticks':99},{'x':float('nan')},{'warning_ticks':float('inf')}):
            s=state();s['mobs'][0].update(update)
            self.assertEqual(Cues().sample(s,now=0)['surveyor_strength'],0,update)
    def test_stale_tick_clears_and_fresh_tick_restores(self):
        s=state();c=Cues();self.assertGreater(c.sample(s,now=0)['surveyor_strength'],0)
        self.assertEqual(c.sample(s,now=.3)['surveyor_strength'],0)
        s['level_tics']+=1;self.assertGreater(c.sample(s,now=.31)['surveyor_strength'],0)
    def test_new_floor_or_seed_cannot_replay_an_old_warning(self):
        c=Cues();s=state();c.sample(s,now=0)
        for key in ('map','revision','seed'):
            fresh=dict(s,**{key:s[key]+1},level_tics=0,mobs=[],bosses=[])
            values=c.sample(fresh,now=1);self.assertEqual(values['quiet_strength']+values['surveyor_strength'],0)
    def test_ritual_uses_native_family_and_twelve_second_opening(self):
        s=dict(state(),mobs=[])
        s['bosses']=[dict(name='SCRIPTORAX',**{'class':9},health=180,phase='exposed',visible=True,distance=300,open_ticks=420)]
        values=Cues().sample(s,now=0)
        self.assertEqual(values['ritual_family'],3);self.assertEqual(values['ritual_open'],1)
        s['bosses'][0]['open_ticks']=210
        self.assertEqual(Cues().sample(s,now=0)['ritual_open'],.5)
        s['bosses'][0].update(visible=False,on_seal=False)
        self.assertEqual(Cues().sample(s,now=0)['ritual_strength'],0)
    def test_ritual_selects_current_seal_not_distant_open_boss(self):
        s=dict(state(),mobs=[])
        s['bosses']=[dict(name='FAR',**{'class':5},health=100,phase='exposed',visible=False,distance=3000,open_ticks=420),
                     dict(name='NEAR',**{'class':10},health=100,phase='sealed',visible=True,distance=240,on_seal=True,gate_stage=1)]
        values=Cues().sample(s,now=0)
        self.assertEqual(values['ritual_family'],4);self.assertEqual(values['ritual_progress'],.5)
        self.assertEqual(values['ritual_open'],0)
    def test_grip_is_visible_before_escape_input_and_uses_held_f_ticks(self):
        s=dict(state(),mobs=[],creatures=dict(effect='grip',escape_ticks=0))
        values=Cues().sample(s,now=0)
        self.assertEqual(values['grip_active'],1);self.assertEqual(values['grip_progress'],0)
        self.assertGreater(values['grip_strength'],0);self.assertEqual(values['quiet_strength'],0)
        s['creatures']['escape_ticks']=12
        self.assertEqual(Cues().sample(s,now=0)['grip_progress'],12/25)
        s['creatures']['effect']=None
        self.assertEqual(Cues().sample(s,now=0)['grip_strength'],0)
    def test_mask_warning_is_phase_one_and_excludes_the_lunge(self):
        s=dict(state(),bosses=[],mobs=[dict(**{'class':8},health=140,phase=1,sight=True,warning_ticks=28,x=256,y=0)])
        values=Cues().sample(s,now=0);self.assertGreater(values['grip_strength'],0)
        self.assertEqual(values['grip_active'],0);self.assertEqual(values['grip_warning'],0)
        for update in ({'phase':2},{'sight':False},{'x':500},{'warning_ticks':29}):
            other=copy.deepcopy(s);other['mobs'][0].update(update)
            self.assertEqual(Cues().sample(other,now=0)['grip_strength'],0)
    def test_new_effects_clear_on_raw_stale_and_modal_state(self):
        s=dict(state(),creatures=dict(effect='grip',escape_ticks=8))
        for other,enabled in [(dict(s,paused=True),True),(dict(s,dead=True),True),(dict(s,vending={'menu_open':True}),True),(s,False)]:
            v=Cues().sample(other,enabled=enabled,now=0)
            self.assertEqual(v['grip_strength']+v['ritual_strength'],0)
        c=Cues();c.sample(s,now=0);v=c.sample(s,now=.3)
        self.assertEqual(v['grip_strength']+v['ritual_strength'],0)
    def test_invalid_uniforms_fail_closed_before_backend_coercion(self):
        valid=dict(ritual_strength=.3,ritual_family=1,ritual_progress=.5,ritual_open=0)
        self.assertGreater(encounter_inputs(valid)['ritual_strength'],0)
        for field,value in [('ritual_progress',float('nan')),('ritual_open',float('inf')),('ritual_family',1.5),('ritual_strength',[.3]),('ritual_progress','0.5')]:
            bad=dict(valid);bad[field]=value
            self.assertEqual(encounter_inputs(bad)['ritual_strength'],0)


if __name__=='__main__':unittest.main()
