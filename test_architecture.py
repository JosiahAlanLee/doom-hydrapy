# SPDX-License-Identifier: GPL-2.0-or-later
"""Architectural folds exercised using ordinary native movement and collision."""
from pathlib import Path
import os
import struct
import tempfile
import unittest

import numpy as np
from rogue.architecture import STUDIES, study, metadata, flats, cellpoint
from rogue.maps import map_lumps, campaign
from rogue.inhabitants import options

def turn_to(d, target):
    # Release for a real tic between taps, keeping the native slow-turn step.
    for _ in range(250):
        delta = (target-d.state()['angle']+180)%360-180
        if abs(delta) < .9: return
        key = 0xac if delta > 0 else 0xae
        d.key(key, True); d.advance(1); d.key(key, False); d.advance(1)
    raise AssertionError('native turn did not converge')


def write_wad(path, lumps):
    raw = bytearray(); directory = []
    for name, data in lumps:
        directory.append(struct.pack('<II8s', 12+len(raw), len(data), name.encode().ljust(8, b'\0')))
        raw.extend(data)
    path.write_bytes(struct.pack('<4sII', b'PWAD', len(lumps), 12+len(raw))+raw+b''.join(directory))


def fixture(path, kind, custom=None, edit=None):
    f = study(42, kind)
    if edit: edit(f)
    lumps = map_lumps(f)
    if custom is not False: lumps.append(custom or metadata(f))
    write_wad(path, lumps)
    return f


def move_to(d, axis, target, limit=600):
    """Walk along the current heading; no teleport or writable debug API."""
    for _ in range(limit):
        s = d.state()
        velocity = s['motion']['mom'+axis]
        error = target-s[axis]
        if s['won'] or (abs(error) < 10 and abs(velocity) < .5): break
        angle = s['angle']*np.pi/180
        forward = np.cos(angle) if axis == 'x' else np.sin(angle)
        left = -np.sin(angle) if axis == 'x' else np.cos(angle)
        desired = error-10*velocity
        key = None
        if abs(desired) > 5:
            if abs(forward) > .7: key = 0xad if desired*forward > 0 else 0xaf
            else: key = 0xa0 if desired*left > 0 else 0xa1
        if key: d.key(key, True)
        d.advance(1)
        if key: d.key(key, False)
    else: raise AssertionError(('walk blocked', axis, target, d.state()))
    d.advance(25)


class ArchitectureMaps(unittest.TestCase):
    def test_bounded_metadata_and_rotational_flats(self):
        for kind in STUDIES:
            f = study(42, kind)
            name, data = metadata(f)
            magic, number, k, ns, nc = struct.unpack_from('<4s4i', data)
            self.assertEqual((name, magic, number, k), ('RARCH', b'RAR1', 1, STUDIES[kind]['kind']))
            self.assertEqual(len(data), 20+ns*40+nc*20)
            self.assertIn(f.start, f.cells); self.assertIn(f.exit, f.cells)
            self.assertEqual(data, metadata(study(42, kind))[1])
        wad = os.environ.get('FREEDOOM_WAD')
        if wad:
            yy, xx = np.indices((64, 64))
            for _, data in flats(wad):
                a = np.frombuffer(data, np.uint8).reshape(64, 64)
                self.assertTrue(np.array_equal(a, a[(-xx)%64, yy]))


@unittest.skipUnless(os.environ.get('FREEDOOM_WAD'), 'Set FREEDOOM_WAD')
class ArchitectureEngine(unittest.TestCase):
    def engine(self, path, enabled=True):
        from client import Doom
        return Doom(os.environ['FREEDOOM_WAD'], demo=None, pwad=path, rogue_floors=1 if enabled else None)

    def test_corridor_preserves_motion_heading_and_pixels_both_directions(self):
        with tempfile.TemporaryDirectory() as t:
            a, b = Path(t)/'fold.wad', Path(t)/'reference.wad'
            fixture(a, 'corridor'); fixture(b, 'corridor', custom=False)
            with self.engine(a) as d, self.engine(b) as ref:
                for g in [d, ref]: g.key(0xad, True)
                for _ in range(250):
                    d.advance(1); ref.advance(1)
                    if d.state()['architecture']['swaps']: break
                else: self.fail('forward seam did not trigger')
                s, r = d.state(), ref.state()
                self.assertEqual(s['architecture']['swaps'], 1)
                self.assertEqual(s['x'], r['x']); self.assertAlmostEqual(s['y']-r['y'], 1792, places=7)
                for field in ['angle', 'motion', 'health', 'ammo', 'weapon']:
                    self.assertEqual(s[field], r[field], field)
                self.assertTrue(np.array_equal(d.frame(0), ref.frame(0)))
                for g in [d, ref]: g.key(0xad, False); g.key(0xaf, True)
                for _ in range(100):
                    d.advance(1); ref.advance(1)
                    if d.state()['architecture']['swaps'] == 2: break
                else: self.fail('inverse seam did not trigger')
                s, r = d.state(), ref.state()
                self.assertEqual((s['x'], s['y'], s['angle'], s['motion']), (r['x'], r['y'], r['angle'], r['motion']))
                self.assertTrue(np.array_equal(d.frame(0), ref.frame(0)))

    def test_destination_occupant_blocks_without_telefrag(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t)/'blocked.wad'
            fixture(path, 'corridor', edit=lambda f: f.things.append((*cellpoint((14,22)), 180, 66, options('hollow'))))
            with self.engine(path) as d:
                enemy = next(m for m in d.monsters() if m['type'] == 66)
                d.key(0xad, True)
                for _ in range(250):
                    d.advance(1)
                    if d.state()['architecture']['blocked']: break
                else: self.fail('occupied destination did not reject transfer')
                s = d.state(); after = next(m for m in d.monsters() if m['type'] == 66)
                self.assertEqual(s['architecture']['swaps'], 0)
                self.assertLess(abs(s['y']-cellpoint((14,8))[1]), 1)
                self.assertEqual((s['health'], after['health']), (100, enemy['health']))

    def test_five_left_corners_return_to_start_heading(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t)/'pillar.wad'; fixture(path, 'pillar')
            with self.engine(path) as d:
                # Corners 1 and 2 in the first copy. Native left turns only.
                move_to(d, 'y', cellpoint((4,4))[1]); turn_to(d, 0)
                move_to(d, 'x', cellpoint((14,4))[0]); turn_to(d, 90)
                for swaps, target in [(1, (25,4)), (2, (25,20)), (3, (9,20)), (4, (4,9))]:
                    d.key(0xad, True)
                    for _ in range(180):
                        d.advance(1)
                        if d.state()['architecture']['swaps'] == swaps: break
                    else: self.fail('pillar fold did not trigger')
                    d.key(0xad, False); d.advance(25)
                    s = d.state()
                    self.assertEqual(s['architecture']['last_seam'], 2*swaps-1)
                    if swaps < 4:
                        self.assertLess(abs((s['angle']+180)%360-180), 8)
                        self.assertLess(abs(s['y']-cellpoint(target)[1]), 24)
                        # Corners 3, 4, 5 are the right bottom corner of each copy.
                        right = [30,30,14][swaps-1]
                        move_to(d, 'x', cellpoint((right,target[1]))[0]); turn_to(d, 90)
                s = d.state()
                self.assertLess(abs(s['x']-cellpoint((4,9))[0]), 24)
                self.assertLess(abs(s['y']-cellpoint((4,9))[1]), 90)
                self.assertLess(abs(s['angle']-270), 8)
                self.assertEqual(s['health'], 100)
                move_to(d, 'y', cellpoint((4,6))[1]); turn_to(d, 180)
                move_to(d, 'x', cellpoint((2,6))[0]); turn_to(d, 270)
                move_to(d, 'y', cellpoint((2,5))[1]); turn_to(d, 180)
                move_to(d, 'x', cellpoint((1,5))[0])
                self.assertTrue(d.state()['won'])

    def test_mutation_requires_observation_then_unwatched_empty_interval(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t)/'memory.wad'; fixture(path, 'memory')
            with self.engine(path) as d:
                d.advance(300); self.assertEqual(d.state()['architecture']['mutations'], 0)
                turn_to(d, 180); d.advance(25)
                self.assertEqual(d.state()['architecture']['phases'], [1])
                self.assertEqual(d.state()['architecture']['mutations'], 1)
                d.advance(300); self.assertEqual(d.state()['architecture']['mutations'], 1)
                turn_to(d, 0); d.advance(10); turn_to(d, 180); d.advance(25)
                self.assertEqual(d.state()['architecture']['mutations'], 2)
                self.assertEqual(d.state()['architecture']['phases'], [0])
            fixture(path, 'memory', edit=lambda f: f.things.append((*cellpoint((16,10)), 0, 2035, 7)))
            with self.engine(path) as d:
                d.advance(30); turn_to(d, 180); d.advance(300)
                self.assertEqual(d.state()['architecture']['mutations'], 0)
                self.assertEqual(d.state()['architecture']['phases'], [0])

    def test_mutation_changes_real_passage_collision(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t)/'collision.wad'; fixture(path, 'memory')
            with self.engine(path) as d:
                d.advance(30); turn_to(d, 180); d.advance(25); turn_to(d, 0)
                # Strafe north while facing east: the watched guard remains armed.
                move_to(d, 'y', cellpoint((10,10))[1])
                d.key(0xad, True); d.advance(200); d.key(0xad, False); d.advance(25)
                self.assertLess(d.state()['x'], 16*128)
                self.assertGreater(d.state()['x'], 15*128)
                self.assertEqual(d.state()['health'], 100)
                move_to(d, 'x', cellpoint((14,10))[0])
                move_to(d, 'y', cellpoint((14,18))[1])
                d.key(0xad, True); d.advance(150); d.key(0xad, False)
                self.assertGreater(d.state()['x'], 18*128)
                self.assertEqual(d.state()['health'], 100)

    def test_invalid_or_disabled_metadata_cannot_change_engine(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t)/'invalid.wad'
            base = metadata(study(42, 'corridor'))[1]
            bad = [b'BAD!'+base[4:], base[:12]+struct.pack('<i', 17)+base[16:], base[:24]+struct.pack('<i', -2147483648)+base[28:]]
            for data in bad:
                fixture(path, 'corridor', custom=('RARCH', data))
                with self.engine(path) as d:
                    d.advance(20); a = d.state()['architecture']
                    self.assertFalse(a['active']); self.assertTrue(a['invalid'])
            fixture(path, 'corridor')
            with self.engine(path, enabled=False) as d:
                d.advance(20); self.assertFalse(d.state()['architecture']['active'])

    def test_level_change_resets_architectural_state(self):
        from client import Doom
        with tempfile.TemporaryDirectory() as t:
            path = Path(t)/'levels.wad'
            first, second = study(42, 'memory'), study(42, 'corridor')
            second.number = 2
            write_wad(path, map_lumps(first)+map_lumps(second)+[metadata(first)])
            with Doom(os.environ['FREEDOOM_WAD'], demo=None, pwad=path, rogue_floors=2) as d:
                d.advance(20); turn_to(d, 180); d.advance(25)
                self.assertEqual(d.state()['architecture']['mutations'], 1)
                d.key(0xad, True)
                for _ in range(160):
                    d.advance(1)
                    if d.state()['map'] == 2: break
                else: self.fail('ordinary exit did not advance to the next map')
                d.key(0xad, False); d.advance(5)
                a = d.state()['architecture']
                self.assertFalse(a['active']); self.assertFalse(a['invalid'])
                self.assertEqual((a['swaps'], a['mutations'], a['phases']), (0, 0, []))


if __name__ == '__main__': unittest.main(verbosity=2)
