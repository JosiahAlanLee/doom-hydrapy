# SPDX-License-Identifier: GPL-2.0-or-later
"""New art/encounters exercised with the real native game's controls."""
from pathlib import Path
import os
import tempfile
import unittest

from rogue.inhabitants import NEW_CREATURES
from rogue.maps import campaign, generate, distances
from test_gloamwood import room


class ArgonCampaign(unittest.TestCase):
    def test_all_four_families_are_reachable_in_five_floors(self):
        for seed in [0,42,20261030,4294967295]:
            found=set()
            for number in range(1,6):
                floor=generate(seed,number);reachable=distances(floor.cells,floor.start)
                for kind,entry in NEW_CREATURES.items():
                    for t in floor.things:
                        if t[3]!=entry['type']:continue
                        found.add(kind);cell=t[0]//128,t[1]//128
                        self.assertIn(cell,reachable)
                        self.assertGreaterEqual(abs(cell[0]-floor.start[0])+abs(cell[1]-floor.start[1]),6)
                        self.assertLess(t[4],32768)
                        self.assertEqual((t[4]>>8)&7,7)
            self.assertEqual(found,set(NEW_CREATURES))
            first=generate(seed,1)
            self.assertTrue(any(t[3]==NEW_CREATURES['surveyor']['type'] for t in first.things))

    def test_bank_frames_and_corpses_are_deterministic(self):
        from rogue.argon_art import draw
        for kind in NEW_CREATURES:
            for frame in range(24):
                image=draw(kind,42,frame)
                self.assertEqual(image.size,(128,128));self.assertTrue(image.getbbox())
                self.assertEqual(image.tobytes(),draw(kind,42,frame).tobytes())
            self.assertEqual(draw(kind,42,25).tobytes(),draw(kind,42,23).tobytes())
            self.assertNotEqual(draw(kind,42,0).tobytes(),draw(kind,43,0).tobytes())


@unittest.skipUnless(os.environ.get('FREEDOOM_WAD'),'Set FREEDOOM_WAD')
class ArgonEngine(unittest.TestCase):
    def engine(self,path,enabled=True):
        from client import Doom
        return Doom(os.environ['FREEDOOM_WAD'],demo=None,pwad=path,rogue_floors=1 if enabled else None)

    def mob(self,engine,kind):
        return next(m for m in engine.monsters() if m['type']==NEW_CREATURES[kind]['type'] and not m['missile'])

    def test_warning_then_locked_line_can_be_sidestepped(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'line.wad';room(p,'surveyor')
            with self.engine(p) as d:
                d.advance(2);self.assertEqual(self.mob(d,'surveyor')['argon_phase'],2)
                d.advance(40);self.assertEqual(self.mob(d,'surveyor')['attack_count'],1)
                self.assertLess(d.state()['health'],100)
            with self.engine(p) as d:
                d.advance(2);d.key(0xa0,True);d.advance(27);d.key(0xa0,False);d.advance(15)
                self.assertEqual(self.mob(d,'surveyor')['attack_count'],1)
                self.assertEqual(d.state()['health'],100)

    def test_husk_arc_can_be_cancelled_by_cover(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'arc.wad'
            room(p,'wire_shambler',enemy=(960,960),player=(704,960),wall=True)
            with self.engine(p) as d:
                d.advance(2);self.assertEqual(self.mob(d,'wire_shambler')['argon_phase'],2)
                d.key(0xa1,True);d.advance(22);d.key(0xa1,False);d.advance(15)
                self.assertEqual(self.mob(d,'wire_shambler')['attack_count'],1)
                self.assertEqual(d.state()['health'],100)
            room(p,'wire_shambler',enemy=(960,960),player=(704,960))
            with self.engine(p) as d:
                d.advance(35);self.assertLess(d.state()['health'],100)

    def test_false_door_is_stationary_and_has_a_proximity_warning(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'door.wad';room(p,'threshold_mimic')
            with self.engine(p) as d:
                d.advance(150);m=self.mob(d,'threshold_mimic')
                self.assertFalse(m['awake']);self.assertEqual(m['attack_count'],0)
                self.assertEqual((m['x'],m['y']),(1088,448))
            room(p,'threshold_mimic',enemy=(576,448))
            with self.engine(p) as d:
                d.advance(2);self.assertEqual(self.mob(d,'threshold_mimic')['argon_phase'],2)
                self.assertEqual(d.state()['health'],100)
                d.advance(25);self.assertLess(d.state()['health'],100)
                self.assertEqual((self.mob(d,'threshold_mimic')['x'],self.mob(d,'threshold_mimic')['y']),(576,448))
                hp=d.state()['health'];d.key(0xaf,True);d.key(0xb6,True);d.advance(20)
                d.key(0xaf,False);d.key(0xb6,False);d.advance(140)
                self.assertEqual(d.state()['health'],hp)

    def test_spindle_launches_native_homing_spore(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'spore.wad';room(p,'vore_spindle')
            with self.engine(p) as d:
                d.advance(40);m=self.mob(d,'vore_spindle')
                self.assertEqual(m['class'],14);self.assertEqual(m['attack_count'],1)
                shots=[m for m in d.monsters() if m['missile'] and m['source_class']==14]
                self.assertEqual(len(shots),1);angle=shots[0]['angle']
                d.key(0xa0,True);d.advance(20);d.key(0xa0,False)
                shots=[m for m in d.monsters() if m['missile'] and m['source_class']==14]
                self.assertEqual(len(shots),1);self.assertNotEqual(shots[0]['angle'],angle)

    def test_all_new_enemies_take_real_weapon_damage_and_leave_corpses(self):
        with tempfile.TemporaryDirectory() as t:
            for kind in NEW_CREATURES:
                p=Path(t)/(kind+'.wad');room(p,kind,enemy=(832,448))
                with self.engine(p) as d:
                    d.advance(35);before=self.mob(d,kind)['health']
                    d.key(0xa3,True);d.advance(400);d.key(0xa3,False);d.advance(40)
                    m=self.mob(d,kind)
                    self.assertLess(m['health'],before);self.assertLessEqual(m['health'],0)
                    self.assertEqual(d.state()['kills'],1)

    def test_unmarked_mode_keeps_original_actor_behavior(self):
        with tempfile.TemporaryDirectory() as t:
            for kind in NEW_CREATURES:
                p=Path(t)/(kind+'.wad');room(p,kind)
                with self.engine(p,False) as d:
                    self.assertFalse(any(m['class']>=11 or 'argon_kind' in m for m in d.monsters()))


if __name__=='__main__':unittest.main(verbosity=2)
