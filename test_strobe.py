# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path
import os
import struct
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from rogue.strobe import study,metadata
from rogue.maps import map_lumps,campaign
from test_architecture import write_wad,turn_to


def fixture(path,empty=False,duty=15):
    f=study(42)
    # A large, fully marked room keeps the gaze and six-tic blackout test clear.
    f.cells={(x,y) for x in range(1,16) for y in range(1,9)}
    f.profiles={p:dict(floor=0,height=192,light=208,tag=1401) for p in f.cells}
    f.start=(3,4);f.exit=(14,7)
    f.things=[(448,576,0,1,7)]+([] if empty else [(1344,576,180,66,7|(7<<8))])
    f.architecture['strobe']['duty_percent']=duty
    write_wad(path,map_lumps(f)+[metadata(f)])


@unittest.skipUnless(os.environ.get('FREEDOOM_WAD'),'Set FREEDOOM_WAD')
class StrobeEngine(unittest.TestCase):
    def engine(self,path,enabled=True):
        from client import Doom
        return Doom(os.environ['FREEDOOM_WAD'],demo=None,pwad=path,rogue_floors=1 if enabled else None)
    def hollow(self,d):return next(m for m in d.monsters() if m['type']==66)

    def test_real_light_gaze_and_blackout_movement(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'room.wad';fixture(p)
            with self.engine(p) as d:
                d.advance(1);self.assertTrue(self.hollow(d)['frozen'])
                before=self.hollow(d)
                for _ in range(100):
                    d.advance(1);s=d.state()['strobe'];m=self.hollow(d)
                    if s['lit']:self.assertTrue(m['frozen'])
                    else:self.assertFalse(m['frozen'])
                after=self.hollow(d);self.assertLess(after['x'],before['x'])
                self.assertEqual(d.state()['health'],100)

    def test_real_pistol_shot_pins_for_exactly_six_tics(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'shot.wad';fixture(p)
            with self.engine(p) as d:
                d.advance(36)
                while d.state()['strobe']['lit']:d.advance(1)
                d.key(0xa3,True)
                for _ in range(20):
                    d.advance(1)
                    if d.state()['strobe']['shots']:break
                else:self.fail('pistol did not fire')
                d.key(0xa3,False);pos=self.hollow(d);remaining=[]
                for _ in range(6):
                    s=d.state()['strobe'];m=self.hollow(d)
                    self.assertTrue(s['muzzle']);self.assertTrue(m['frozen'])
                    self.assertEqual((m['x'],m['y']),(pos['x'],pos['y']))
                    remaining.append(s['muzzle_ticks']);d.advance(1)
                self.assertEqual(remaining,[6,5,4,3,2,1])
                self.assertFalse(d.state()['strobe']['muzzle'])
                self.assertEqual(d.state()['ammo'][0],49)

    def test_steady_view_changes_picture_but_not_native_rules(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'steady.wad';fixture(p)
            with self.engine(p) as a,self.engine(p) as b:
                b.command('STROBE_VIEW 0');difference=False
                for _ in range(70):
                    a.advance(1);b.advance(1)
                    ma,mb=self.hollow(a),self.hollow(b)
                    self.assertEqual((ma['x'],ma['y'],ma['frozen']),(mb['x'],mb['y'],mb['frozen']))
                    if not a.state()['strobe']['lit']:
                        difference|=not np.array_equal(a.frame(0),b.frame(0))
                self.assertTrue(difference)

    def test_fist_and_dry_fire_do_not_create_flashes(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'ammo.wad';fixture(p,empty=True)
            with self.engine(p) as d:
                d.advance(35);d.key(ord('1'),True);d.advance(1);d.key(ord('1'),False);d.advance(45)
                d.key(0xa3,True);d.advance(80);d.key(0xa3,False)
                self.assertEqual(d.state()['strobe']['shots'],0)
            with self.engine(p) as d:
                d.advance(35);d.key(0xa3,True);d.advance(1200)
                self.assertEqual(d.state()['ammo'][0],0)
                count=d.state()['strobe']['shots'];self.assertEqual(count,50)
                d.advance(250);self.assertEqual(d.state()['strobe']['shots'],count)
                self.assertFalse(d.state()['strobe']['muzzle'])

    def test_map_scope_invalid_metadata_and_music_phase(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'scope.wad';fixture(p)
            with self.engine(p) as d:
                d.advance(30);d.command('STROBE_SYNC 1050')
                self.assertAlmostEqual(d.state()['strobe']['phase'],.5,places=5)
                self.assertFalse(d.state()['strobe']['lit'])
            with self.engine(p,enabled=False) as d:self.assertFalse(d.state()['strobe']['active'])
            f=study(42);write_wad(p,map_lumps(f)+[('RSTROBE',struct.pack('<4s4i',b'RST1',1,999,38,1401))])
            with self.engine(p) as d:
                s=d.state()['strobe'];self.assertFalse(s['active']);self.assertTrue(s['invalid'])

    def test_irregular_fluorescent_has_long_lit_stretches_and_short_dips(self):
        with tempfile.TemporaryDirectory() as t,patch.dict(os.environ,{'DOOM_STROBE_STYLE':'irregular'}):
            p=Path(t)/'flicker.wad';fixture(p,empty=True)
            sequences=[]
            for _ in range(2):
                with self.engine(p) as d:
                    levels=[]
                    for tick in range(840):
                        d.advance(1);s=d.state()['strobe']
                        self.assertEqual(s['style'],'irregular')
                        self.assertEqual(s['lit'],s['illumination']>=.35)
                        levels.append(s['illumination'])
                    sequences.append(levels)
            self.assertEqual(sequences[0],sequences[1])
            dark=[i for i,v in enumerate(sequences[0]) if v<.35]
            self.assertGreater(len(dark),12);self.assertLess(len(dark),840*.15)
            starts=[i for i in dark if i-1 not in dark]
            self.assertGreater(len(set(b-a for a,b in zip(starts,starts[1:]))),3)
            self.assertGreater(len(set(sequences[0])),3)


class StrobeMap(unittest.TestCase):
    def test_study_has_safe_lit_alcove_and_marked_hall(self):
        f=study(42);self.assertEqual(f.profiles[f.start]['tag'],0)
        self.assertEqual(f.profiles[(13,5)]['tag'],1401)
        self.assertEqual(len(metadata(f)[1]),20)
        with tempfile.TemporaryDirectory() as t:
            m=campaign(42,Path(t)/'strobe.wad',practice='strobe')
            self.assertEqual(m['mode'],'strobe');self.assertEqual(m['floors'][0]['monsters'],1)


if __name__=='__main__':unittest.main(verbosity=2)
