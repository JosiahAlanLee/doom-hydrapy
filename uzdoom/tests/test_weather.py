# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from types import SimpleNamespace
from uzdoom.weather import configure,lump,mist_texture


class WeatherContract(unittest.TestCase):
    def test_opt_in_and_sector_boundary(self):
        m=SimpleNamespace(number=2,sectors=[{}]*12)
        cistern={'id':'flooded-resonance-cistern','geometry_sectors':7}
        self.assertIsNone(configure(m,cistern,'off',17))
        self.assertIsNone(configure(m,{'id':'inhabited-archive'},'cistern',17))
        self.assertIsNone(configure(m,None,'cistern',17))
        p=configure(m,cistern,'cistern',17)
        self.assertEqual(p['sectors'],list(range(7)))
        self.assertEqual(p,configure(m,cistern,'cistern',17))
        self.assertNotEqual(p['seed'],configure(m,cistern,'cistern',73)['seed'])
        self.assertLess(p['visibility'],1536)
        self.assertLessEqual(p['particles_per_emission']*((p['lifetime']+p['emission_interval']-1)//p['emission_interval']),70)
        with self.assertRaises(ValueError):configure(m,cistern,'rain',17)
        with self.assertRaises(ValueError):configure(m,dict(cistern,geometry_sectors=13),'cistern',17)
    def test_native_lump_contract(self):
        p=configure(SimpleNamespace(number=1,sectors=[{}]*8),{'id':'flooded-resonance-cistern','geometry_sectors':6},'cistern',0xffffffff)
        rows=lump(p).decode().splitlines()
        self.assertEqual(list(map(int,rows[0].split())),[p['density'],p['visibility'],p['seed']])
        self.assertEqual(list(map(int,rows[1].split())),p['colour'])
        self.assertEqual(list(map(int,rows[2].split())),p['sectors'])
    def test_mist_has_soft_transparent_edges(self):
        a=mist_texture();self.assertEqual(a.size,(64,64));self.assertEqual(a.tobytes(),mist_texture().tobytes())
        self.assertTrue(all(a.getpixel((x,0))[3]==0 and a.getpixel((x,63))[3]==0 for x in range(64)))
        self.assertGreater(a.getpixel((31,31))[3],a.getpixel((16,31))[3])


if __name__=='__main__':unittest.main()
