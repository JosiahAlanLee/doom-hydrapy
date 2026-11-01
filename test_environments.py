# SPDX-License-Identifier: GPL-2.0-or-later
"""The environment bank changes recognizable art without changing navigation."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import os
import struct
import unittest

import numpy as np

from rogue import environments as env
from rogue.maps import FLOORS, campaign, generate
from rogue.threshold_assets import apply_identity, wall_lumps
from rogue.creatures import wad_lumps


class EnvironmentKit(unittest.TestCase):
    def test_seed_selection_is_stable_and_all_three_worlds_are_available(self):
        self.assertEqual([env.select(i) for i in range(6)], list(env.PACK_IDS) * 2)
        self.assertEqual(env.select(0xffffffff), env.PACK_IDS[0xffffffff % 3])
        self.assertEqual(set(env.catalogue()), set(env.PACK_IDS))
        for bad in (True, -1, 0x100000000, 1.5, '1'):
            with self.assertRaises(ValueError):
                env.select(bad)

    def test_art_tiles_seam_and_props_have_transparent_padding(self):
        masks = {role: set() for role in env.PROP_ROLES}
        for pack in env.PACK_IDS:
            for group, count in (('walls', 8), ('flats', 4)):
                for number in range(1, count + 1):
                    image = env.picture(pack, group, number)
                    pixels = np.asarray(image)
                    self.assertGreater(float(pixels.std()), 8, (pack, group, number))
                    if group == 'flats' or number <= 6:
                        np.testing.assert_array_equal(pixels[0], pixels[-1])
                        np.testing.assert_array_equal(pixels[:, 0], pixels[:, -1])
            for role in env.PROP_ROLES:
                image = env.picture(pack, 'props', role)
                alpha = np.asarray(image)[:, :, 3]
                self.assertGreater(np.count_nonzero(alpha), 500)
                self.assertFalse(np.any(alpha[:3]))
                self.assertFalse(np.any(alpha[:, :3]))
                self.assertFalse(np.any(alpha[:, -3:]))
                self.assertFalse(np.any(alpha[-3:]))
                self.assertGreater(np.where(alpha > 0)[0].max(), 105)
                masks[role].add(hashlib.sha256((alpha > 0).tobytes()).hexdigest())
        for role, shapes in masks.items():
            self.assertEqual(len(shapes), 3, role)

    def test_art_cache_is_not_mutable_by_callers(self):
        image = env.picture(env.PACK_IDS[0], 'walls', 1)
        before = image.tobytes()
        image.paste((255, 0, 255), (0, 0, 128, 128))
        self.assertEqual(env.picture(env.PACK_IDS[0], 'walls', 1).tobytes(), before)

    def test_signature_mobs_have_all_native_state_frames_and_persistent_corpses(self):
        for pack in env.PACK_IDS:
            for role in env.MOB_ROLES:
                frames=[env.draw_mob(pack,role,0,i) for i in (0,4,8,12,16,20,23)]
                self.assertTrue(all(image.size==(128,128) and image.getbbox() for image in frames))
                self.assertEqual(len({image.tobytes() for image in frames}),len(frames))
                self.assertEqual(env.draw_mob(pack,role,0,25).tobytes(),frames[-1].tobytes())
                self.assertNotEqual(frames[0].tobytes(),env.draw_mob(pack,role,1,0).tobytes())

    def test_warning_labels_keep_native_counts_and_behavior_hints(self):
        state={'argon':{'latchwing':2,'relay_choir':1,'cue':'LATCHWING / SIDESTEP THE DASH'}}
        shown=env.present_state(state,'drowned_records')
        self.assertEqual(shown['argon']['cue'],'SHELF WIDOW / SIDESTEP THE DASH')
        self.assertEqual(shown['argon']['latchwing'],2)
        self.assertEqual(state['argon']['cue'],'LATCHWING / SIDESTEP THE DASH')

    def test_each_world_is_keyed_to_its_validated_written_score(self):
        for pack in env.PACK_IDS:
            entry=env.describe(pack)['music']
            path=env.ROOT/entry['score']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),entry['sha256'])
            self.assertEqual(entry['seconds'],120)

    def test_decorating_all_tiers_preserves_geometry_things_and_binding_rules(self):
        for seed in (0, 1, 2, 42, 0xffffffff):
            floors = apply_identity([generate(seed, i) for i in range(1, FLOORS + 1)], seed)
            before = deepcopy(floors)
            pack = env.apply(floors, seed)
            self.assertEqual(pack, env.select(seed))
            for old, new in zip(before, floors):
                for name in ('cells', 'rooms', 'start', 'exit', 'route', 'things', 'bosses', 'variants'):
                    self.assertEqual(getattr(old, name), getattr(new, name), (seed, new.number, name))
                for cell in old.profiles:
                    for key in set(old.profiles[cell]) | set(new.profiles[cell]):
                        if key not in ('wall', 'flat', 'ceiling'):
                            self.assertEqual(old.profiles[cell].get(key), new.profiles[cell].get(key), (seed, cell, key))
                self.assertTrue(new.architecture['environment']['feature_cells'], (seed, new.number))
                self.assertEqual(new.architecture['environment']['id'], pack)
                for prop in new.architecture.get('props', []):
                    self.assertEqual(prop['environment'], pack)


@unittest.skipUnless(os.environ.get('FREEDOOM_WAD'), 'Set FREEDOOM_WAD')
class EnvironmentNative(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.wad = Path(os.environ['FREEDOOM_WAD'])
        cls.maps = []
        for seed in range(3):
            path = cls.root / f'{seed}.wad'
            manifest = campaign(seed, path, assets=cls.wad, identity=True)
            cls.maps.append((path, manifest))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_each_world_loads_in_native_palette_with_both_demons_and_original_encounters(self):
        from client import Doom
        source = dict(wad_lumps(self.wad))
        for seed, (path, manifest) in enumerate(self.maps):
            self.assertEqual(manifest['environment']['id'], env.select(seed))
            self.assertEqual(len(manifest['floors']), 7)
            self.assertNotIn('PLAYPAL',dict(wad_lumps(path)))  # Inherit the IWAD palette.
            with Doom(self.wad, demo=None, pwad=path, rogue_floors=7, clean_hud=True) as game:
                game.advance(3)
                state = game.state()
                self.assertEqual(state['total_kills'], 10)
                self.assertEqual([b['name'] for b in state['bosses']], ['REPETIEL', 'SCRIPTORAX'])
                self.assertTrue(all(b['has_seal'] for b in state['bosses']))
                self.assertGreater(float(game.frame(0)[40:340, :, :3].std()), 8)

    def test_new_wall_namespace_preserves_every_original_texture_and_patch_reference(self):
        source = dict(wad_lumps(self.wad))
        def names(data):
            count = struct.unpack_from('<I', data)[0]
            return [data[o:o + 8].rstrip(b'\0').decode('ascii')
                    for o in struct.unpack_from('<' + 'I' * count, data, 4)]
        for pack in env.PACK_IDS:
            bank = dict(wall_lumps(self.wad, pack))
            self.assertTrue(set(names(source['TEXTURE1'])) <= set(names(bank['TEXTURE1'])))
            self.assertTrue({f'NWALL{i:02}' for i in range(1, 7)} <= set(names(bank['TEXTURE1'])))
            self.assertTrue({f'EWALL{i:02}' for i in range(1, 9)} <= set(names(bank['TEXTURE1'])))
            old_count = struct.unpack_from('<I', source['PNAMES'])[0]
            count = struct.unpack_from('<I', bank['PNAMES'])[0]
            self.assertEqual(count, old_count + 14)
            self.assertEqual(bank['PNAMES'][4:4 + old_count * 8], source['PNAMES'][4:4 + old_count * 8])
            data = bank['TEXTURE1']
            for offset in struct.unpack_from('<' + 'I' * struct.unpack_from('<I', data)[0], data, 4):
                patches = struct.unpack_from('<H', data, offset + 20)[0]
                for i in range(patches):
                    index = struct.unpack_from('<h', data, offset + 22 + i * 10 + 4)[0]
                    self.assertTrue(0 <= index < count)

    def test_same_seed_rebuilds_the_same_art_and_native_wad(self):
        path = self.root / 'repeat.wad'
        again = campaign(0, path, assets=self.wad, identity=True)
        self.assertEqual(again['environment'], self.maps[0][1]['environment'])
        self.assertEqual(path.read_bytes(), self.maps[0][0].read_bytes())

    def test_study_identity_is_unchanged_and_does_not_load_new_environment_names(self):
        paths = [self.root / 'study-a.wad', self.root / 'study-b.wad']
        a = campaign(0, paths[0], assets=self.wad, identity=False, practice='strobe')
        b = campaign(0, paths[1], assets=self.wad, identity=True, practice='strobe')
        self.assertNotIn('environment', b)
        self.assertEqual(a['sha256'], b['sha256'])
        self.assertFalse(any(name.startswith('EWALL') for name, _ in wad_lumps(paths[1])))


if __name__ == '__main__':
    unittest.main(verbosity=2)
