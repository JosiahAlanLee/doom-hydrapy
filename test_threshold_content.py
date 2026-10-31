# SPDX-License-Identifier: GPL-2.0-or-later
"""The new materials, secret and five-floor route run in the real engine."""
from pathlib import Path
import math,os,struct,tempfile,unittest
import numpy as np
from client import Doom
from rogue.maps import campaign,generate,distances,TILE,ENEMY_TYPES
from rogue.threshold_assets import apply_identity
from rogue.creatures import wad_lumps

def repack(path,lumps):
    raw=bytearray();directory=[]
    for name,data in lumps:
        directory.append(struct.pack('<II8s',12+len(raw),len(data),name.encode().ljust(8,b'\0')));raw.extend(data)
    path.write_bytes(struct.pack('<4sII',b'PWAD',len(lumps),12+len(raw))+raw+b''.join(directory))

@unittest.skipUnless(os.environ.get('FREEDOOM_WAD'),'Set FREEDOOM_WAD')
class ThresholdContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name);cls.wad=Path(os.environ['FREEDOOM_WAD'])
        cls.map=cls.root/'threshold.wad';cls.manifest=campaign(20261030,cls.map,assets=cls.wad,identity=True)
        cls.floors=apply_identity([generate(20261030,i) for i in range(1,6)],20261030)
        # This geometry fixture keeps the real solid props and pickups. Combat
        # is covered separately, so route traversal need not depend on its AI.
        lumps=[]
        for name,data in wad_lumps(cls.map):
            if name=='THINGS':data=b''.join(struct.pack('<5h',*t) for t in struct.iter_unpack('<5h',data) if t[3] not in ENEMY_TYPES)
            lumps.append((name,data))
        cls.safe=cls.root/'geometry.wad';repack(cls.safe,lumps)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def walk(self,d,route,floor=1):
        for target in route:
            for attempt in range(150):
                s=d.state()
                if s['map']!=floor or s['won']:break
                dx,dy=target[0]*TILE+64-s['x'],target[1]*TILE+64-s['y']
                if math.hypot(dx,dy)<25:break
                desired=math.degrees(math.atan2(dy,dx))%360
                delta=(desired-s['angle']+180)%360-180
                held={0xac if delta>0 else 0xae} if abs(delta)>6 else {0xad}
                for key in (0xac,0xae,0xad):d.key(key,key in held)
                d.advance(1)
            else:self.fail(f'Native route stuck on floor{floor}, target{target}, state{s}')
            for key in (0xac,0xae,0xad):d.key(key,False)
            if s['map']!=floor or s['won']:break

    def test_new_textures_preserve_the_source_texture_namespace(self):
        source=dict(wad_lumps(self.wad));custom=dict(wad_lumps(self.map))
        old_count=struct.unpack_from('<I',source['PNAMES'])[0]
        self.assertEqual(custom['PNAMES'][4:4+8*old_count],source['PNAMES'][4:4+8*old_count])
        def names(raw):
            n=struct.unpack_from('<I',raw)[0]
            return {raw[o:o+8].rstrip(b'\0').decode() for o in struct.unpack_from('<'+'I'*n,raw,4)}
        self.assertTrue(names(source['TEXTURE1'])<=names(custom['TEXTURE1']))
        self.assertTrue({f'NWALL{i:02}' for i in range(1,7)}<=names(custom['TEXTURE1']))
        with Doom(self.wad,demo=None,pwad=self.map,rogue_floors=5,clean_hud=True) as d:
            d.advance(3);frame=d.frame(0)
            self.assertGreater(float(np.std(frame[40:340,:,:3])),8)
            self.assertEqual(d.state()['total_kills'],8)

    def test_solid_props_leave_routes_and_boss_bindings_clear(self):
        for f in self.floors:
            props={tuple(p['cell']) for p in f.architecture['props']}
            self.assertFalse(props&set(f.route))
            self.assertEqual(len(distances(f.cells-props,f.start)),len(f.cells-props))
            if f.boss:self.assertNotIn(tuple(f.boss['binding_cell']),props)

    def test_optional_cache_counts_as_one_real_native_secret(self):
        f=self.floors[0];blocked={tuple(p['cell']) for p in f.architecture['props']}
        parents=distances(f.cells-blocked,f.start);route=[(31,10)]
        while route[-1]!=f.start:route.append(parents[route[-1]])
        route.reverse()
        with Doom(self.wad,demo=None,pwad=self.safe,rogue_floors=5,clean_hud=True) as d:
            self.walk(d,route[1:]);d.advance(10)
            self.assertEqual(d.state()['map'],1);self.assertEqual(d.state()['secrets'],1)

    def test_walk_the_new_opener_and_all_four_generated_floors(self):
        with Doom(self.wad,demo=None,pwad=self.safe,rogue_floors=5,clean_hud=True) as d:
            for f in self.floors:
                self.walk(d,f.route[1:],f.number);d.advance(3)
                if f.number<5:self.assertEqual(d.state()['map'],f.number+1)
                else:self.assertTrue(d.state()['won'])

if __name__=='__main__':unittest.main(verbosity=2)
