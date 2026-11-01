# SPDX-License-Identifier: GPL-2.0-or-later
"""Native collision, evasion and fair tells for Threshold's two new enemies."""
from pathlib import Path
import os,tempfile,unittest
from client import Doom
from test_gloamwood import room

@unittest.skipUnless(os.environ.get('FREEDOOM_WAD'),'Set FREEDOOM_WAD')
class ThresholdEnemies(unittest.TestCase):
    def engine(self,path):return Doom(os.environ['FREEDOOM_WAD'],demo=None,pwad=path,rogue_floors=1)
    def creature(self,game,kind):return next(m for m in game.monsters() if m.get('argon_kind')==kind)

    def test_latchwing_warns_then_delivers_only_one_dash_hit(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'latch.wad';room(p,'latchwing',enemy=(704,448))
            with self.engine(p) as d:
                d.advance(2);self.assertEqual(self.creature(d,'latchwing')['argon_phase'],2)
                self.assertEqual(d.state()['health'],100)
                d.advance(56);self.assertEqual(d.state()['health'],90)
                self.assertEqual(self.creature(d,'latchwing')['attack_count'],1)
                d.advance(40);self.assertEqual(d.state()['health'],90)

    def test_latchwing_dash_can_be_sidestepped_and_stops_at_wall(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'wall.wad';room(p,'latchwing',enemy=(448,448),player=(192,448))
            with self.engine(p) as d:
                d.advance(2);d.key(0xa0,True);d.advance(27);d.key(0xa0,False);d.advance(28)
                m=self.creature(d,'latchwing')
                self.assertEqual(d.state()['health'],100);self.assertEqual(m['attack_count'],1)
                self.assertGreaterEqual(m['x'],146,'The dash must not cross the west wall')

    def test_relay_charges_a_slow_three_spore_fan_and_stays_anchored(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'choir.wad';room(p,'relay_choir')
            with self.engine(p) as d:
                d.advance(2);self.assertEqual(self.creature(d,'relay_choir')['argon_phase'],2)
                self.assertEqual(d.state()['health'],100)
                d.advance(38)
                shots=[m for m in d.monsters() if m['missile'] and m['source_class']==16]
                self.assertEqual(len(shots),3);self.assertEqual(len({m['angle'] for m in shots}),3)
                self.assertEqual((self.creature(d,'relay_choir')['x'],self.creature(d,'relay_choir')['y']),(1088,448))
                self.assertTrue(all(m['speed']==8*65536 for m in shots))

    def test_relay_warning_leaves_time_to_move_outside_the_fan(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'dodge.wad';room(p,'relay_choir')
            with self.engine(p) as d:
                d.advance(2);d.key(0xa0,True);d.advance(30);d.key(0xa0,False);d.advance(100)
                self.assertEqual(d.state()['health'],100)
                self.assertEqual(self.creature(d,'relay_choir')['attack_count'],1)

    def test_new_families_take_weapon_damage_and_leave_a_counted_corpse(self):
        with tempfile.TemporaryDirectory() as t:
            for kind in ('latchwing','relay_choir'):
                p=Path(t)/(kind+'.wad');room(p,kind,enemy=(832,448))
                with self.engine(p) as d:
                    d.advance(2);d.key(0xa3,True);d.advance(400);d.key(0xa3,False);d.advance(220)
                    self.assertLessEqual(self.creature(d,kind)['health'],0)
                    self.assertEqual(d.state()['kills'],1)
                    self.assertFalse(any(m['missile'] and m['source_class']==16 for m in d.monsters()))

    def test_latchwing_archetype_does_not_replace_the_calmor_boss(self):
        from rogue.maps import generate
        from test_rogue import fixture_wad
        with tempfile.TemporaryDirectory() as t:
            f=generate(42,5,boss_kind='calmor');f.number=1
            p=Path(t)/'shared-archetype.wad';fixture_wad(p,[f])
            with self.engine(p) as d:
                d.advance(2);mobs=d.monsters()
                self.assertEqual(sum(m['class']==6 for m in mobs),1)
                self.assertEqual(sum(m['class']==15 for m in mobs),1)
                self.assertEqual({m['type'] for m in mobs if m['class'] in (6,15)},{69})

if __name__=='__main__':unittest.main(verbosity=2)
