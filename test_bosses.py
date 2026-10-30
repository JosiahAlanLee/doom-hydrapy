# SPDX-License-Identifier: GPL-2.0-or-later
"""Book-boss selection and real native-engine binding/exit checks."""
from pathlib import Path
import math
import os
import tempfile
import unittest

from rogue.bosses import BOSSES,encounter
from rogue.maps import generate,campaign,distances
from rogue.inhabitants import options
from test_rogue import fixture_wad


def pulse(d,key,ticks=5):
    d.key(key,True);d.advance(ticks);d.key(key,False);d.advance(ticks)


def walk_x(d,target):
    # Fixtures face east: forward/backward only. This moves the real player,
    # rather than teleporting or changing the encounter's state from a test API.
    for _ in range(200):
        state=d.state()
        if state['won']:return
        x=state['x']
        if abs(target-x)<12:break
        key=0xad if target>x else 0xaf
        d.key(key,True);d.advance(1);d.key(key,False)
    else:raise AssertionError('fixture walk blocked')
    d.advance(20)


def arena(path,kind,on_seal=True):
    f=generate(42,1)
    f.cells={(x,y) for x in range(1,12) for y in range(1,7)}
    f.profiles={p:{'floor':0,'height':192,'light':224} for p in f.cells}
    f.profiles[(2,2)]['tag']=777
    if kind=='jurisiel':f.profiles[(3,2)]['tag']=778
    f.start=(2,2) if on_seal else (3,2);f.exit=(4,2);f.boss=None
    px,py=f.start[0]*128+64,f.start[1]*128+64
    data=BOSSES[kind]
    # The boss initially looks away so the binding rule is isolated from AI.
    # Real weapon damage and legitimate fixture pickups are still used.
    f.things=[(px,py,0,1,7),(1088,320,0,data['type'],options(kind)),
              (px,py,0,2006,7),(px,py,0,17,7),(px,py,0,17,7),(px,py,0,17,7),
              (px,py,0,2022,7)]
    fixture_wad(path,[f])


class BossMaps(unittest.TestCase):
    def test_seeded_order_and_reachable_bindings(self):
        orders=set()
        for seed in range(16):
            order=tuple(encounter(seed,n)['kind'] for n in [3,5]);orders.add(order)
            self.assertEqual(len(set(order)),2)
            self.assertTrue(set(order)<=set(BOSSES))
            self.assertIsNone(encounter(seed,1))
            for number in [3,5]:
                f=generate(seed,number);b=f.boss
                self.assertIn(tuple(b['binding_cell']),distances(f.cells,f.start))
                self.assertEqual(f.profiles[tuple(b['binding_cell'])]['tag'],777)
                self.assertEqual(sum(t[3] in [b['type'] for b in BOSSES.values()] for t in f.things),1)
                if b['kind']=='jurisiel':
                    self.assertIn(tuple(b['secondary_cell']),distances(f.cells,f.start))
                    self.assertEqual(f.profiles[tuple(b['secondary_cell'])]['tag'],778)
                self.assertTrue(b['source_actual_effect'])
                self.assertEqual(f.boss,generate(seed,number).boss)
        self.assertGreaterEqual(len(orders),4)
        self.assertEqual(set().union(*(set(order) for order in orders)),set(BOSSES))

    def test_practice_modes_start_on_the_seal(self):
        with tempfile.TemporaryDirectory() as t:
            for kind in BOSSES:
                m=campaign(42,Path(t)/f'{kind}.wad',practice=kind)
                self.assertEqual(len(m['floors']),1)
                f=m['floors'][0]
                self.assertEqual(f['monsters'],1)
                self.assertEqual(f['boss']['kind'],kind)
                self.assertEqual(tuple(f['start']),tuple(f['boss']['binding_cell']))
            with self.assertRaises(ValueError):campaign(42,Path(t)/'bad.wad',practice='unknown')


@unittest.skipUnless(os.environ.get('FREEDOOM_WAD'),'Set FREEDOOM_WAD')
class BossEngine(unittest.TestCase):
    def test_echo_direction_and_calmor_panic_burst(self):
        with tempfile.TemporaryDirectory() as t:
            for kind in ['repetiel','calmor']:
                path=Path(t)/'attacks.wad';f=generate(42,1)
                f.cells={(x,y) for x in range(1,12) for y in range(1,7)}
                f.profiles={p:{'floor':0,'height':192,'light':224} for p in f.cells}
                f.profiles[(6,2)]['tag']=777;f.exit=(10,5);f.boss=None
                b=BOSSES[kind]
                f.things=[(832,320,180,1,7),(320,320,0,b['type'],7|(b['class']<<8))]
                fixture_wad(path,[f])
                with self.engine(path) as d:
                    if kind=='calmor':d.key(0xa3,True)
                    first_angle=None
                    for _ in range(240):
                        d.advance(1);state=d.state()['boss']
                        shots=[m for m in d.monsters() if m['missile'] and m['source_class']==b['class']]
                        if kind=='repetiel':
                            if first_angle is None and shots:
                                first_angle=shots[0]['angle'];d.key(0xa0,True)
                            if state['echoes']:
                                self.assertTrue(any(abs(m['angle']-first_angle)<.01 for m in shots));break
                        elif state['last_burst']==3:
                            self.assertGreaterEqual(len(shots),3);break
                    else:self.fail(kind+' did not perform its custom attack')
                    d.key(0xa3,False);d.key(0xa0,False)

    def engine(self,path):
        from client import Doom
        return Doom(os.environ['FREEDOOM_WAD'],demo=None,pwad=path,rogue_floors=1)

    def test_shield_and_exit_guard(self):
        with tempfile.TemporaryDirectory() as t:
            for kind in BOSSES:
                with self.subTest(kind=kind):
                    path=Path(t)/'arena.wad';arena(path,kind,on_seal=False)
                    with self.engine(path) as d:
                        # Move just enough to pick up the arena's BFG/cells and
                        # test-only invulnerability. This is not game practice gear.
                        pulse(d,0xad,1);d.advance(90)
                        hp=d.state()['boss']['health']
                        d.key(0xa3,True);d.advance(90);d.key(0xa3,False);d.advance(5)
                        s=d.state();self.assertEqual(s['boss']['health'],hp)
                        self.assertGreater(s['boss']['blocked_hits'],0)
                        walk_x(d,640)
                        self.assertFalse(d.state()['won'])
                        self.assertEqual(d.state()['gamestate'],0)

    def test_repetiel_requires_two_distinct_presentations(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'arena.wad';arena(path,'repetiel')
            with self.engine(path) as d:
                self.assertEqual(d.state()['boss']['phase'],'sealed')
                d.key(0xa2,True);d.advance(45)
                self.assertEqual(d.state()['boss']['stamps'],1)
                self.assertEqual(d.state()['boss']['phase'],'sealed')
                d.key(0xa2,False);d.advance(5);pulse(d,0xa2)
                self.assertEqual(d.state()['boss']['phase'],'exposed')
                d.advance(8*35+2)
                self.assertEqual(d.state()['boss']['phase'],'sealed')

    def test_calmor_requires_quiet_and_stillness(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'arena.wad';arena(path,'calmor')
            with self.engine(path) as d:
                d.advance(35);self.assertGreater(d.state()['boss']['still_ticks'],25)
                pulse(d,0xa3,1);self.assertLess(d.state()['boss']['still_ticks'],5)
                # Fresh run isolates stillness from the shot's alert/knockback.
            with self.engine(path) as d:
                pulse(d,0xad,2);self.assertLess(d.state()['boss']['still_ticks'],5)
                d.advance(100);self.assertEqual(d.state()['boss']['phase'],'exposed')
                d.advance(8*35+2);self.assertEqual(d.state()['boss']['phase'],'sealed')

    def test_real_damage_and_defeat_unlock_exit(self):
        with tempfile.TemporaryDirectory() as t:
            for kind in BOSSES:
                with self.subTest(kind=kind):
                    path=Path(t)/'arena.wad';arena(path,kind)
                    with self.engine(path) as d:
                        pulse(d,0xad,1);d.advance(35)
                        if kind=='repetiel':pulse(d,0xa2);pulse(d,0xa2)
                        elif kind=='calmor':d.advance(90)
                        elif kind=='probator':
                            d.advance(60);pulse(d,ord('2'),1);d.advance(35)
                            pulse(d,0xa3,10)
                            self.assertTrue(d.state()['boss']['proof']);pulse(d,0xa2)
                        else:
                            walk_x(d,448);walk_x(d,320)
                        self.assertEqual(d.state()['boss']['phase'],'exposed')
                        hp=d.state()['boss']['health']
                        # BFG is fixture gear to test gate/death transitions
                        # quickly. Production studies use a shotgun and shells.
                        pulse(d,ord('7'),1);d.advance(30)
                        d.key(0xa3,True)
                        for _ in range(12):
                            d.advance(20)
                            if d.state()['boss']['health']==0:break
                        d.key(0xa3,False)
                        s=d.state();self.assertLess(s['boss']['health'],hp)
                        self.assertEqual(s['boss']['phase'],'bound')
                        walk_x(d,640);d.advance(4)
                        self.assertTrue(d.state()['won'])

    def test_ordinary_map_does_not_enable_boss_rules(self):
        from client import Doom
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'arena.wad';arena(path,'repetiel')
            with Doom(os.environ['FREEDOOM_WAD'],demo=None,pwad=path) as d:
                self.assertIsNone(d.state()['boss'])
                self.assertEqual(d.monsters()[0]['spawnhealth'],1000)


if __name__=='__main__':unittest.main(verbosity=2)
