# SPDX-License-Identifier: GPL-2.0-or-later
"""Topology/property tests, plus real-engine tests with FREEDOOM_WAD set."""
from pathlib import Path
import hashlib
import math
import os
import struct
import tempfile
import time
import threading
import json
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import unittest

from rogue.maps import FLOORS, SIZE, TILE, campaign, distances, generate, map_lumps


def fixture_wad(path,floors,player_only=False):
    lumps=[]
    for f in floors:
        for name,data in map_lumps(f):
            if name=='THINGS' and player_only:data=struct.pack('<5h',*f.things[0])
            lumps.append((name,data))
    raw=bytearray();directory=[]
    for name,data in lumps:
        directory.append(struct.pack('<II8s',12+len(raw),len(data),name.encode().ljust(8,b'\0')))
        raw.extend(data)
    path.write_bytes(struct.pack('<4sII',b'PWAD',len(lumps),12+len(raw))+raw+b''.join(directory))


class MapTests(unittest.TestCase):
    def test_connected_safe_spawn_and_different_seeds(self):
        for seed in [0,1,42,20261030,4294967295]:
            for n in range(1,FLOORS+1):
                f=generate(seed,n)
                self.assertEqual(len(distances(f.cells,f.start)),len(f.cells))
                self.assertGreater(len(f.route),10)
                self.assertNotEqual(f.start,f.exit)
                self.assertEqual(f.things[0][3],1)
                self.assertTrue(all(0<x<SIZE-1 and 0<y<SIZE-1 for x,y in f.cells))
                for x,y,_,kind,_ in f.things:
                    self.assertIn((x//TILE,y//TILE),f.cells)
                    if kind in [3004,3001,3002,9,3005]:
                        self.assertGreaterEqual(abs(x//TILE-f.start[0])+abs(y//TILE-f.start[1]),6)
        self.assertNotEqual(generate(41,1).cells,generate(42,1).cells)

    def test_deterministic_pwad(self):
        with tempfile.TemporaryDirectory() as t:
            a,b=Path(t)/'a.wad',Path(t)/'b.wad'
            m=campaign(42,a);campaign(42,b)
            self.assertEqual(a.read_bytes(),b.read_bytes())
            self.assertEqual(m['sha256'],hashlib.sha256(a.read_bytes()).hexdigest())

    def test_bsp_points_resolve_to_their_own_sectors(self):
        f=generate(42,1);lumps=dict(map_lumps(f))
        nodes=list(struct.iter_unpack('<12h2H',lumps['NODES']))
        for y in range(SIZE):
            for x in range(SIZE):
                child=len(nodes)-1
                while not child&0x8000:
                    n=nodes[child];px,py=x*TILE+64,y*TILE+64
                    side=int(px<=n[0]) if n[2]==0 else int(py>n[1])
                    child=n[12+side]
                self.assertEqual(child&0x7fff,y*SIZE+x)
        self.assertEqual(len(nodes),SIZE*SIZE-1)
        self.assertEqual(len(lumps['SSECTORS'])//4,SIZE*SIZE)


@unittest.skipUnless(os.environ.get('FREEDOOM_WAD'),'Set FREEDOOM_WAD for real-engine tests')
class EngineTests(unittest.TestCase):
    def test_death_is_terminal_and_disconnect_releases_controls(self):
        from rogue.server import Game
        with tempfile.TemporaryDirectory() as t:
            game=Game(os.environ['FREEDOOM_WAD'],t)
            try:
                owner=game.acquire();game.input(owner,['KeyW'])
                with self.assertRaises(ValueError):game.acquire()
                # Simulate a missing browser heartbeat. The real game loop must
                # release keys and stop advancing, not keep walking into danger.
                with game.lock:game.last_input=time.monotonic()-2
                time.sleep(.15)
                with game.lock:
                    self.assertTrue(game.paused);self.assertFalse(game.held)
                    tic=game.engine.state()['tic']
                time.sleep(.12)
                with game.lock:self.assertEqual(game.engine.state()['tic'],tic)
                # The actual run deliberately protects its spawn room. Use an
                # exposed test arena to exercise real enemy damage and death.
                with game.lock:
                    from client import Doom
                    f=generate(20261030,1)
                    f.cells={(x,y) for x in range(1,9) for y in range(1,5)}
                    f.start=(2,2);f.exit=(7,3)
                    f.things=[(320,320,0,1,7),(576,320,180,9,7),(576,448,180,9,7)]
                    fixture_wad(Path(t)/'arena.wad',[f])
                    game.engine.close()
                    game.engine=Doom(os.environ['FREEDOOM_WAD'],demo=None,pwad=Path(t)/'arena.wad',rogue_floors=1)
                    for _ in range(20):
                        game.engine.advance(350)
                        if game.engine.state()['dead']:break
                    game.render();self.assertTrue(game.state['dead'])
                owner=game.acquire();game.input(owner,['KeyF','Space'])
                with game.lock:
                    self.assertFalse(game.held)
                    game.engine.advance(3);self.assertTrue(game.engine.state()['dead'])
            finally:game.close()

    def test_http_input_session_and_origin(self):
        from rogue.server import Game,handler
        with tempfile.TemporaryDirectory() as t:
            game=Game(os.environ['FREEDOOM_WAD'],t)
            server=ThreadingHTTPServer(('127.0.0.1',0),handler(game,'test',0))
            port=server.server_port;server.RequestHandlerClass=handler(game,'test',port)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            def post(path,data,token='test',origin=None):
                headers={'Content-Type':'application/json','X-Run-Token':token}
                if origin:headers['Origin']=origin
                req=Request(f'http://127.0.0.1:{port}/api/{path}',data=json.dumps(data).encode(),headers=headers)
                try:
                    with urlopen(req) as response:return response.status,json.load(response)
                except HTTPError as e:return e.code,json.load(e)
            try:
                self.assertEqual(post('control',{},token='wrong')[0],403)
                self.assertEqual(post('control',{},origin='https://example.invalid')[0],403)
                status,data=post('control',{});self.assertEqual(status,200);owner=data['owner']
                self.assertEqual(post('input',{'owner':owner,'keys':['BAD']})[0],400)
                self.assertEqual(post('input',{'owner':'wrong','keys':['KeyW']})[0],400)
                self.assertEqual(post('new',{'owner':owner,'seed':True})[0],400)
                self.assertEqual(post('input',{'owner':owner,'keys':[],'paused':True})[0],200)
                self.assertTrue(game.snapshot()['paused'])
            finally:server.shutdown();server.server_close();game.close();thread.join(timeout=2)

    def test_keyboard_fire_release_and_new_seed(self):
        from client import Doom
        from rogue.server import KEYS
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'map.wad';campaign(20261030,p)
            with Doom(os.environ['FREEDOOM_WAD'],demo=None,pwad=p,rogue_floors=FLOORS) as d:
                before=d.state();d.key(KEYS['KeyW'],True);d.advance(15)
                d.key(KEYS['KeyW'],False);d.advance(25);after=d.state()
                self.assertGreater(math.hypot(after['x']-before['x'],after['y']-before['y']),20)
                d.advance(50);stopped=d.state()
                self.assertLess(math.hypot(stopped['x']-after['x'],stopped['y']-after['y']),8)
                d.key(KEYS['Space'],True);d.advance(20);d.key(KEYS['Space'],False);d.advance(2)
                self.assertLess(d.state()['ammo'][0],before['ammo'][0])

    def test_walk_all_five_floors_and_win(self):
        """Walk generated routes with native keys: no teleport/debug commands.

        Remove encounter/pickup THINGS only for this geometry fixture. Combat
        maps are tested separately; path traversal must not depend on enemy AI.
        """
        from client import Doom
        floors=[generate(20261030,i) for i in range(1,FLOORS+1)]
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'routes.wad'
            fixture_wad(p,floors,player_only=True)
            with Doom(os.environ['FREEDOOM_WAD'],demo=None,pwad=p,rogue_floors=FLOORS) as d:
                # Spend one round: inventory must survive all descents.
                d.key(0xa3,True);d.advance(8);d.key(0xa3,False);d.advance(15)
                ammo=d.state()['ammo'][:]
                for f in floors:
                    route=f.route[1:]
                    for target in route:
                        for attempt in range(150):
                            s=d.state()
                            if s['map']!=f.number or s['won']:break
                            dx,dy=target[0]*TILE+64-s['x'],target[1]*TILE+64-s['y']
                            if math.hypot(dx,dy)<25:break
                            desired=math.degrees(math.atan2(dy,dx))%360
                            delta=(desired-s['angle']+180)%360-180
                            held={0xac if delta>0 else 0xae} if abs(delta)>6 else {0xad}
                            for key in [0xac,0xae,0xad]:d.key(key,key in held)
                            d.advance(1)
                        else:self.fail(f'Route stuck on floor {f.number}, target {target}, state {s}')
                        for key in [0xac,0xae,0xad]:d.key(key,False)
                        if s['map']!=f.number or s['won']:break
                    d.advance(3);s=d.state()
                    self.assertEqual(s['ammo'],ammo)
                    if f.number<FLOORS:self.assertEqual(s['map'],f.number+1)
                    else:self.assertTrue(s['won'])


if __name__=='__main__':unittest.main(verbosity=2)
