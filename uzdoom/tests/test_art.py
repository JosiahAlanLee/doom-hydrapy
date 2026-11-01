# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression checks for pose compatibility, bounded art and native placement."""
import hashlib
import math
import struct
import unittest
from uzdoom.art_sections import poses
from uzdoom.models import md3,obj
from uzdoom.build import make_maps,PACKS
from uzdoom.openworld.selection import choose
from uzdoom.openworld.campaign import IDS


class ArtChecks(unittest.TestCase):
    def test_shuffled_floors_and_recent_openers(self):
        for seed in range(64):
            plan=choose(seed,IDS);self.assertEqual(len({p['archetype'] for p in plan}),7)
            recent=[plan[0]['archetype']]
            alternate=choose(seed,IDS,recent)
            self.assertNotEqual(alternate[0]['archetype'],recent[0])
            self.assertEqual(plan,choose(seed,IDS))
    def test_signal_morphs_are_repeatable_bounded_and_compatible(self):
        for seed in [0,17,73,211,0xffffffff]:
            for i in range(3):
                p=poses(seed,i);parsed=[obj(x) for x in p]
                self.assertEqual([len(t) for v,u,t in parsed],[180]*3)
                self.assertTrue(all(min(v[2] for v in row[0])>112 for row in parsed))
                a=md3(p,'models/signals/test.png',1)
                self.assertEqual(a,md3(poses(seed,i),'models/signals/test.png',1))
                self.assertEqual(a[:4],b'IDP3')
                self.assertEqual(struct.unpack_from('<i',a,76)[0],3)
                self.assertEqual(struct.unpack_from('<i',a,104)[0],len(a))
        self.assertNotEqual(md3(poses(17,0),'a',1),md3(poses(73,0),'a',1))

    def test_morph_topology_changes_are_rejected(self):
        p=poses(17,0);p[1].text=p[1].text.replace('f 1/1 3/1 2/1','f 1/1 2/1 3/1')
        with self.assertRaisesRegex(ValueError,'topology'):md3(p,'test',1)

    def test_generated_campaigns_keep_physical_invariants(self):
        for seed in [0,17,73,211,0xffffffff]:
            maps,levels=make_maps(seed,PACKS[seed%len(PACKS)])
            self.assertEqual(len(maps),7)
            for m,level in zip(maps,levels):
                self.assertLess(len(m.nodes),2048)
                self.assertEqual(len(m.gates),7)
                self.assertTrue(all(type(t['angle']) is int for t in m.things))
                world=level['open_world']
                if not world:continue
                self.assertEqual(len(world['bosses']),2)
                self.assertTrue(world['route_graph']['metrics']['has_cycle'])
                self.assertFalse(world['route_graph']['metrics']['unreachable_anchors'])
                for b in world['bosses']:
                    self.assertEqual(b['seal'][2],b['secondary_seal'][2])
                    self.assertGreaterEqual(math.dist(b['seal'],b['secondary_seal']),176)


if __name__=='__main__':unittest.main()
