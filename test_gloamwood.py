# SPDX-License-Identifier: GPL-2.0-or-later
"""Behavior checks use real Doom input, damage, sight and collision."""
from pathlib import Path
import math
import os
import tempfile
import unittest

from rogue.bosses import BOSSES
from rogue.inhabitants import CREATURES,options
from rogue.maps import generate,campaign,distances
from test_rogue import fixture_wad
from test_bosses import arena,pulse,walk_x


def room(path,kind,enemy=(1088,448),player=(448,448),wall=False):
    f=generate(42,1)
    f.cells={(x,y) for x in range(1,13) for y in range(1,8)}
    if wall:f.cells-={(6,y) for y in range(1,7)}
    f.profiles={p:{'floor':0,'height':192,'light':224} for p in f.cells}
    f.start=(player[0]//128,player[1]//128);f.exit=(11,6);f.boss=None
    b=CREATURES[kind]
    f.things=[(*player,0,1,7),(*enemy,180,b['type'],options(kind))]
    fixture_wad(path,[f])


def turn_to(d,angle):
    for _ in range(100):
        delta=(angle-d.state()['angle']+180)%360-180
        if abs(delta)<4:return
        key=0xac if delta>0 else 0xae
        d.key(key,True);d.advance(1);d.key(key,False)
    raise AssertionError('native turn did not converge')


class GloamMaps(unittest.TestCase):
    def test_sparse_encounters_and_signed_options(self):
        for seed in [0,42,20261030,4294967295]:
            for number in range(1,8):
                f=generate(seed,number)
                for kind in ['hollow']+(['redead'] if number>=2 else []):
                    things=[t for t in f.things if t[3]==CREATURES[kind]['type']]
                    self.assertEqual(len(things),1)
                    t=things[0]
                    self.assertGreaterEqual(abs(t[0]//128-f.start[0])+abs(t[1]//128-f.start[1]),10)
                    self.assertLess(t[4],32768)
                    self.assertIn((t[0]//128,t[1]//128),distances(f.cells,f.start))
                for kind in CREATURES|BOSSES:
                    self.assertLess(options(kind,15),32768)

    def test_isolated_creature_studies_and_original_art(self):
        from rogue.creatures import creature
        with tempfile.TemporaryDirectory() as t:
            for kind in CREATURES:
                m=campaign(42,Path(t)/f'{kind}.wad',practice=kind)
                self.assertEqual(m['floors'][0]['monsters'],1)
                self.assertIsNone(m['floors'][0]['boss'])
        for kind,frame in [('hollow',24),('hollow',20),('redead',20),('probator',0),('jurisiel',0)]:
            a=creature(kind,42,frame)
            self.assertTrue(a.getbbox())
            self.assertEqual(a.tobytes(),creature(kind,42,frame).tobytes())
            self.assertNotEqual(a.tobytes(),creature(kind,43,frame).tobytes())


@unittest.skipUnless(os.environ.get('FREEDOOM_WAD'),'Set FREEDOOM_WAD')
class GloamEngine(unittest.TestCase):
    def engine(self,path,rogue=True):
        from client import Doom
        return Doom(os.environ['FREEDOOM_WAD'],demo=None,pwad=path,rogue_floors=1 if rogue else None)

    def mob(self,d,kind):
        return next(m for m in d.monsters() if m['type']==CREATURES[kind]['type'] and not m['missile'])

    def wait_grip(self,d):
        for _ in range(150):
            d.advance(1)
            if d.state()['creatures']['effect']=='grip':return
        self.fail('Stone ReDead did not complete its warning/lunge/grip')

    def test_hollow_watched_pose_freezes_then_crawls(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'gaze.wad';room(path,'hollow')
            with self.engine(path) as d:
                d.advance(10);a=self.mob(d,'hollow')
                self.assertTrue(a['awake'] and a['frozen'])
                d.advance(70);b=self.mob(d,'hollow')
                self.assertEqual((a['x'],a['y'],a['pose']),(b['x'],b['y'],b['pose']))
                turn_to(d,180);before=self.mob(d,'hollow');d.advance(20);after=self.mob(d,'hollow')
                self.assertFalse(after['frozen'])
                self.assertLess(after['x'],before['x'])
                self.assertFalse(any(m['missile'] and m['source_class']==7 for m in d.monsters()))
                p=d.state();angle=math.degrees(math.atan2(after['y']-p['y'],after['x']-p['x']))%360
                turn_to(d,angle);a=self.mob(d,'hollow');hp=d.state()['health'];d.advance(70);b=self.mob(d,'hollow')
                self.assertTrue(b['frozen'])
                self.assertEqual((a['x'],a['y'],a['pose']),(b['x'],b['y'],b['pose']))
                self.assertEqual(d.state()['health'],hp)

    def test_hidden_hollow_stays_dormant_and_redead_cannot_shriek_through_wall(self):
        with tempfile.TemporaryDirectory() as t:
            for kind in CREATURES:
                path=Path(t)/'wall.wad';room(path,kind,enemy=(960,448),player=(576,448),wall=True)
                with self.engine(path) as d:
                    d.advance(150);m=self.mob(d,kind)
                    self.assertEqual((m['x'],m['y']),(960,448))
                    self.assertFalse(m['awake'])
                    self.assertFalse(d.state()['creatures']['shriek_warning'])
                    self.assertIsNone(d.state()['creatures']['effect'])

    def test_grip_damage_hold_to_escape_and_timeout(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'grip.wad';room(path,'redead',enemy=(576,448))
            with self.engine(path) as d:
                d.advance(5);self.assertEqual(self.mob(d,'redead')['creature_phase'],1)
                self.assertIsNone(d.state()['creatures']['effect'])
                self.wait_grip(d);hp=d.state()['health'];d.advance(36)
                self.assertEqual(d.state()['health'],hp-4)
                d.key(0xa2,True);d.advance(24)
                self.assertEqual(d.state()['creatures']['effect'],'grip')
                self.assertEqual(d.state()['creatures']['escape_ticks'],24)
                d.advance(1);d.key(0xa2,False)
                self.assertIsNone(d.state()['creatures']['effect'])
                self.assertEqual(self.mob(d,'redead')['creature_phase'],4)
                d.advance(90);self.assertIsNone(d.state()['creatures']['effect'])
            with self.engine(path) as d:
                self.wait_grip(d);hp=d.state()['health'];d.advance(140)
                self.assertIsNone(d.state()['creatures']['effect'])
                self.assertGreaterEqual(d.state()['health'],hp-12)

    def test_grip_keeps_real_weapon_damage_available(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'escape.wad';room(path,'redead',enemy=(576,448))
            with self.engine(path) as d:
                self.wait_grip(d);hp=self.mob(d,'redead')['health']
                pulse(d,0xa3,10)
                self.assertLess(self.mob(d,'redead')['health'],hp)
                self.assertIsNone(d.state()['creatures']['effect'])

    def test_warning_can_be_dodged_by_retreat(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'warning.wad';room(path,'redead',enemy=(832,448))
            with self.engine(path) as d:
                d.advance(2);self.assertEqual(self.mob(d,'redead')['creature_phase'],1)
                d.key(0xb6,True);d.key(0xaf,True);d.advance(20);d.key(0xaf,False);d.key(0xb6,False)
                d.advance(12)
                self.assertIsNone(d.state()['creatures']['effect'])
                self.assertEqual(d.state()['health'],100)

    def test_probator_needs_real_shield_proof_and_a_fresh_use(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'proof.wad';arena(path,'probator')
            with self.engine(path) as d:
                pulse(d,0xad,1);d.advance(90);pulse(d,ord('2'),1);d.advance(35)
                d.key(0xa2,True);d.advance(10)
                self.assertEqual(d.state()['boss']['phase'],'sealed')
                hp=d.state()['boss']['health'];pulse(d,0xa3,10)
                self.assertTrue(d.state()['boss']['proof'])
                self.assertEqual(d.state()['boss']['health'],hp)
                self.assertEqual(d.state()['boss']['phase'],'sealed')
                d.key(0xa2,False);d.advance(5);pulse(d,0xa2)
                self.assertEqual(d.state()['boss']['phase'],'exposed')
                d.advance(8*35+2)
                self.assertEqual(d.state()['boss']['phase'],'sealed')
                self.assertFalse(d.state()['boss']['proof'])

    def test_jurisiel_requires_a_then_b_and_does_not_reopen_in_place(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'gates.wad';arena(path,'jurisiel',on_seal=False)
            with self.engine(path) as d:
                d.advance(5);self.assertEqual(d.state()['boss']['gate_stage'],0)
                pulse(d,0xa2);self.assertEqual(d.state()['boss']['phase'],'sealed')
                walk_x(d,320);self.assertEqual(d.state()['boss']['gate_stage'],1)
                walk_x(d,448);self.assertEqual(d.state()['boss']['phase'],'exposed')
                d.advance(8*35+5);self.assertEqual(d.state()['boss']['phase'],'sealed')
                d.advance(15);self.assertEqual(d.state()['boss']['phase'],'sealed')

    def test_new_boss_projectile_pairs(self):
        with tempfile.TemporaryDirectory() as t:
            for kind,width in [('probator',11.25),('jurisiel',45)]:
                path=Path(t)/'pair.wad';arena(path,kind)
                # Facing the boss alerts it through a real pistol shot.
                with self.engine(path) as d:
                    d.advance(25);pulse(d,0xa3,10)
                    for _ in range(250):
                        d.advance(1);b=d.state()['boss']
                        shots=[m for m in d.monsters() if m['missile'] and m['source_class']==b['class']]
                        if b['last_burst']==2 and len(shots)>=2:
                            a,z=shots[-2:]
                            delta=abs((a['angle']-z['angle']+180)%360-180)
                            self.assertAlmostEqual(delta,width,places=2);break
                    else:self.fail(kind+' did not produce its native projectile pair')

    def test_unmarked_native_archetypes_keep_original_behavior(self):
        with tempfile.TemporaryDirectory() as t:
            for kind,hp in [('hollow',300),('redead',70)]:
                path=Path(t)/'normal.wad';room(path,kind)
                with self.engine(path,rogue=False) as d:
                    m=self.mob(d,kind)
                    self.assertEqual(m['spawnhealth'],hp)
                    self.assertNotIn('creature_phase',m)


if __name__=='__main__':unittest.main(verbosity=2)
