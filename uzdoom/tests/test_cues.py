# SPDX-License-Identifier: GPL-3.0-or-later
"""Effects follow real semantic state and cannot outlive a stale native tick."""
import copy,unittest
from uzdoom.cues import Cues


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


if __name__=='__main__':unittest.main()
