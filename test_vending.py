# SPDX-License-Identifier: GPL-2.0-or-later
"""Placement, native money/perk effects and safe native shop input."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, main, skipUnless
from unittest.mock import Mock, patch
import os
import struct
import threading
import time
import math

from client import Doom
from rogue.maps import generate, distances
from rogue.vending import TYPE, place, metadata, sprite_lumps, picture
from rogue.desktop import Desktop
from test_rogue import fixture_wad
from test_bosses import pulse, walk_x
from test_gloamwood import turn_to


def face(d,angle):
    # TURN is native relative mouse input: eight angle units per mouse unit.
    for _ in range(3):
        delta=(angle-d.state()['angle']+180)%360-180
        if abs(delta)<.05:return
        d.turn(max(-4096,min(4096,round(-delta*65536/(360*8)))));d.advance(1)
    raise AssertionError('Could not align the real player')


def next_floor(d):
    before=d.state()['map'];face(d,0);d.key(0xad,True)
    for _ in range(200):
        d.advance(1)
        if d.state()['map']!=before:
            d.key(0xad,False);d.advance(20);return
    d.key(0xad,False)
    raise AssertionError('Native player did not cross the exit')


class VendingPlacement(TestCase):
    def test_safe_connected_deterministic_start_locations_across_all_floors(self):
        from rogue.threshold_assets import apply_identity
        from rogue.environments import apply
        for seed in [0,1,42,20261030,20261031,0xffffffff,*range(100,120)]:
            floors=apply_identity([generate(seed,n) for n in range(1,8)],seed)
            apply(floors,seed)
            old=[set(f.things) for f in floors]
            place(floors,seed)
            for f,before in zip(floors,old):
                v=f.architecture['vending'];cell=tuple(v['cell'])
                self.assertEqual(len([t for t in f.things if t[3]==TYPE]),1)
                self.assertTrue(before<=set(f.things))
                self.assertNotIn(cell,f.route);self.assertNotIn(cell,[f.start,f.exit])
                self.assertLessEqual(abs(cell[0]-f.start[0])+abs(cell[1]-f.start[1]),3)
                self.assertFalse(f.profiles[cell].get('tag') or f.profiles[cell].get('special'))
                blocked={tuple(p['cell']) for p in f.architecture['props'] if p['solid']}|{cell}
                remaining=f.cells-blocked
                self.assertEqual(len(distances(remaining,f.start)),len(remaining))
                self.assertEqual(sorted(v['order']),list(range(5)))
            name,raw=metadata(floors,seed)
            self.assertEqual(name,'RVEND');self.assertEqual(len(raw),12+7*16)
            same=apply_identity([generate(seed,n) for n in range(1,8)],seed);apply(same,seed);place(same,seed)
            self.assertEqual(raw,metadata(same,seed)[1])

    def test_original_cabinet_has_binary_alpha_and_a_spent_state(self):
        a,b=picture(),picture(True)
        self.assertEqual(a.size,(80,112));self.assertTrue(a.getbbox())
        self.assertEqual(set(a.getchannel('A').tobytes()),{0,255})
        self.assertNotEqual(a.tobytes(),b.tobytes())


def fixture(path,order=(0,1,2,3,4),*,secret=False,hazard=False,pickups=(),monster=False,wall=False,high=False,raw=None,marked=True):
    floors=[]
    for n in range(1,8):
        f=generate(42,n);f.cells={(x,y) for x in range(1,13) for y in range(1,8)}
        f.profiles={p:dict(floor=0,height=192,light=224) for p in f.cells}
        f.start=(3,3);f.exit=(7,3);f.boss=None;f.bosses=[]
        f.things=[(448,448,90,1,7),(448,512,0,TYPE,7)]
        f.things += [(448,448,0,k,7) if isinstance(k,int) else (k[1],k[2],0,k[0],7) for k in pickups]
        if monster:f.things.append((1088,448,0,3004,7))
        if secret:f.profiles[(3,3)]['special']=9
        if hazard:f.profiles[(3,3)]['special']=5
        if wall:
            # Thin solid cell wall between nearby centres; range alone cannot
            # authorize a purchase through closed native geometry.
            f.things[0]=(448,500,90,1,7);f.things[1]=(448,556,0,TYPE,7)
            f.cells.remove((3,4));f.profiles[(3,4)]['height']=0
        if high:
            f.things[1]=(448,528,0,TYPE,7);f.profiles[(3,4)]['floor']=64
        x,y=f.things[1][:2]
        f.architecture={'vending':dict(id=n,x=x,y=y,order=list(order))}
        floors.append(f)
    extra=[('S_START',b''),*sprite_lumps(os.environ['FREEDOOM_WAD']),('S_END',b'')]
    # Retain the IWAD sprites by adding only VEND via SS_START/SS_END is not
    # supported by this legacy renderer. A fixture includes the whole namespace.
    from rogue.creatures import wad_lumps
    active=False;original=[]
    for name,data in wad_lumps(os.environ['FREEDOOM_WAD']):
        if name=='S_START':active=True;continue
        if name=='S_END':active=False;continue
        if active:original.append((name,data))
    extra[1:1]=original
    if marked:extra.append(('RVEND',raw) if raw is not None else metadata(floors,42))
    fixture_wad(path,floors,extra_lumps=extra)


@skipUnless(os.environ.get('FREEDOOM_WAD'),'Set FREEDOOM_WAD and build the IPC engines')
class VendingEngine(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def engine(self,name='test',**kw):
        path=self.root/(name+'.wad');fixture(path,**kw)
        return Doom(os.environ['FREEDOOM_WAD'],demo=None,pwad=path,rogue_floors=7,clean_hud=True,render_scale=2)
    def open(self,d):
        d.advance(3)
        # Doom collects overlapping items on movement, not spawn. Give the
        # fixture's starting equipment through an ordinary native step.
        d.key(0xaf,True);d.advance(1);d.key(0xaf,False);d.advance(5)
        pulse(d,0xa2,1)
        self.assertTrue(d.state()['vending']['menu_open'])
    def buy(self,d,slot=0):
        self.open(d);v=d.state()['vending']['vendor']
        result=d.buy(v['id'],slot);self.assertTrue(result['ok'],result)
        return result

    def test_native_purchase_is_atomic_and_one_per_floor_with_fresh_run_reset(self):
        for _ in range(2):
            with self.engine() as d:
                d.advance(3);self.assertEqual(d.state()['vending']['credits'],6)
                self.assertFalse(d.buy(1,0)['ok'],'Must actually open the machine')
                self.open(d);self.assertFalse(d.buy(2,0)['ok'])
                self.assertTrue(d.buy(1,0)['ok'])
                s=d.state();self.assertEqual((s['health'],s['vending']['max_health']),(125,125))
                self.assertEqual((s['vending']['credits'],s['vending']['spent']),(0,6))
                self.assertFalse(d.buy(1,0)['ok']);pulse(d,0xa2,1)
                self.assertFalse(d.state()['vending']['menu_open'])
                self.assertEqual(d.state()['vending']['perks'][0]['rank'],1)
                self.assertTrue(d.state()['vending']['vendor']['spent'])

    def test_health_capacity_keeps_overheal_and_normal_medkits_can_fill_new_cap(self):
        with self.engine('overheal',pickups=(2013,)) as d:
            self.buy(d);self.assertEqual(d.state()['health'],200)
        with self.engine('medkit',hazard=True,pickups=((2012,704,448),(2012,704,448))) as d:
            self.buy(d);before=d.state()['health'];d.advance(35)
            self.assertLess(d.state()['health'],before)
            face(d,0);walk_x(d,704);self.assertEqual(d.state()['health'],125)

    def test_ammo_capacity_refill_and_real_forward_speed(self):
        for _,raw in sprite_lumps(os.environ['FREEDOOM_WAD']):
            self.assertEqual(struct.unpack_from('<hh',raw),(48,72))
        with self.engine('ammo',order=(3,0,1,2,4)) as d:
            self.buy(d);s=d.state()
            self.assertEqual(s['vending']['ammo_caps'],[300,75,450,75])
            self.assertEqual(s['ammo'],[80,8,30,2])
        with self.engine('backpack',order=(3,0,1,2,4),pickups=(8,)) as d:
            self.buy(d);self.assertEqual(d.state()['vending']['ammo_caps'],[600,150,900,150])
        travel=[]
        for buy in (False,True):
            with self.engine('speed',order=(4,0,1,2,3)) as d:
                self.open(d)
                if buy:self.assertTrue(d.buy(1,0)['ok'])
                else:d.command('VCLOSE')
                face(d,0);start=d.state()['x']
                d.key(0xad,True);d.advance(12);d.key(0xad,False)
                travel.append(d.state()['x']-start)
        self.assertGreater(travel[1],travel[0]*1.08)
        self.assertLess(travel[1],travel[0]*1.12)

    def test_damage_and_lining_modify_real_combat_and_hazards(self):
        damage=[];injury=[]
        for buy in (False,True):
            with self.engine('damage',order=(2,0,1,3,4),monster=True) as d:
                self.open(d)
                if buy:self.assertTrue(d.buy(1,0)['ok'])
                else:d.command('VCLOSE')
                face(d,0);d.advance(35)
                before=next(m for m in d.monsters() if m['type']==3004)['health']
                ammo=d.state()['ammo'][0];d.key(0xa3,True)
                for _ in range(35):
                    d.advance(1)
                    if d.state()['ammo'][0]<ammo:break
                d.key(0xa3,False)
                after=next(m for m in d.monsters() if m['type']==3004)['health']
                damage.append(before-after)
            with self.engine('lining',order=(1,0,2,3,4),hazard=True) as d:
                self.open(d)
                if buy:self.assertTrue(d.buy(1,0)['ok'])
                else:d.command('VCLOSE')
                hp=d.state()['health'];d.advance(32);injury.append(hp-d.state()['health'])
        self.assertGreater(damage[0],0);self.assertEqual(damage[1],damage[0]*120//100)
        self.assertEqual(injury,[10,9])

    def test_kills_and_native_caches_pay_once_and_inventory_survives_real_exit(self):
        with self.engine('rewards',secret=True,monster=True,pickups=(2006,17,2022)) as d:
            self.buy(d);s=d.state()['vending']
            self.assertEqual((s['credits'],s['earned']),(3,3))
            face(d,0);d.advance(35);d.key(0xa3,True);d.advance(200);d.key(0xa3,False)
            self.assertEqual(d.state()['kills'],1)
            self.assertEqual(d.state()['vending']['credits'],4)
            d.advance(70);self.assertEqual(d.state()['vending']['earned'],4)
            next_floor(d)
            self.assertEqual(d.state()['map'],2)
            s=d.state()['vending'];self.assertEqual(s['perks'][0]['rank'],1)
            self.assertFalse(s['vendor']['spent']);self.assertEqual(s['credits'],7)
            pulse(d,0xa2,1);self.assertTrue(d.state()['vending']['menu_open'])
            offers=d.state()['vending']['vendor']['offers'];slot=next(i for i,o in enumerate(offers) if o['rank']==1)
            self.assertFalse(d.buy(2,slot)['ok'],'Rank two is more expensive')
            self.assertEqual(d.state()['vending']['credits'],7)

    def test_second_rank_is_capped_and_removed_from_later_stock(self):
        with self.engine('ranks',secret=True) as d:
            self.buy(d)
            for floor in (2,3,4):
                next_floor(d);self.assertEqual(d.state()['map'],floor)
            self.assertEqual(d.state()['vending']['credits'],12)
            pulse(d,0xa2,1);self.assertTrue(d.buy(4,0)['ok'])
            self.assertEqual(d.state()['vending']['max_health'],150)
            next_floor(d);s=d.state()['vending']
            self.assertEqual(s['perks'][0]['rank'],2)
            self.assertNotIn(0,[o['id'] for o in s['vendor']['offers']])

    def test_range_facing_height_closed_and_invalid_metadata_fail_closed(self):
        with self.engine('facing') as d:
            d.advance(3);turn_to(d,0);pulse(d,0xa2,1)
            self.assertFalse(d.state()['vending']['menu_open']);self.assertFalse(d.buy(1,0)['ok'])
            turn_to(d,270);d.key(0xad,True);d.advance(15);d.key(0xad,False)
            turn_to(d,90);pulse(d,0xa2,1);self.assertFalse(d.state()['vending']['menu_open'])
        with self.engine('height',high=True) as d:
            d.advance(3);pulse(d,0xa2,1);self.assertFalse(d.state()['vending']['menu_open'])
        with self.engine('wall',wall=True) as d:
            d.advance(3);pulse(d,0xa2,1);self.assertFalse(d.state()['vending']['menu_open'])
        for i,raw in enumerate((b'bad',struct.pack('<4sIHH',b'RVN1',42,1,0)+struct.pack('<HHhh5B3x',1,1,448,512,0,0,2,3,4))):
            with self.engine('invalid'+str(i),raw=raw) as d:
                d.advance(3);self.assertFalse(d.state()['vending']['active'])
                self.assertTrue(d.state()['vending']['invalid']);self.assertFalse(d.buy(1,0)['ok'])
        with self.engine('unmarked',marked=False) as d:
            d.advance(3);self.assertFalse(d.state()['vending']['active'])
            pulse(d,0xa2,1);self.assertFalse(d.buy(1,0)['ok'])


@skipUnless(os.environ.get('FREEDOOM_WAD'),'Set FREEDOOM_WAD and build the IPC engines')
class NativeShopClock(TestCase):
    def test_real_host_pauses_releases_controls_refreshes_purchase_and_resets_retry(self):
        from rogue.desktop import NativeGame
        with TemporaryDirectory() as root:
            game=NativeGame(os.environ['FREEDOOM_WAD'],root)
            try:
                s=game.snapshot();v=s['vending']['vendor'];angle=math.degrees(math.atan2(v['y']-s['y'],v['x']-s['x']))%360
                delta=(angle-s['angle']+180)%360-180;owner=game.acquire()
                game.input(owner,[],turn=round(-delta*65536/(360*8)))
                time.sleep(.07)
                deadline=time.monotonic()+3
                while not game.snapshot()['vending']['vendor']['near']:
                    self.assertLess(time.monotonic(),deadline)
                    game.input(owner,['KeyW']);time.sleep(.025)
                game.input(owner,['KeyF'])
                while not game.paused:
                    self.assertLess(time.monotonic(),deadline);time.sleep(.025)
                self.assertTrue(game.snapshot()['vending']['menu_open'])
                self.assertIsNone(game.owner);self.assertFalse(game.held)
                before=game.snapshot()['level_tics'];time.sleep(.15)
                self.assertEqual(game.snapshot()['level_tics'],before,'Choosing must freeze native simulation')
                with self.assertRaisesRegex(ValueError,'earlier run'):game.purchase(v['id'],0,game.revision-1)
                frame=game.frame_seq;result=game.purchase(v['id'],0,game.revision)
                self.assertTrue(result['ok']);self.assertGreater(game.frame_seq,frame)
                self.assertEqual(game.snapshot()['vending']['credits'],0);self.assertTrue(game.paused)
                self.assertFalse(game.snapshot()['vending']['menu_open'])
                game.new_run(game.manifest['seed'])
                s=game.snapshot()['vending'];self.assertEqual(s['credits'],6)
                self.assertTrue(all(p['rank']==0 for p in s['perks']))
            finally:game.close()


class ShopControls(TestCase):
    def desktop(self):
        d=Desktop.__new__(Desktop);d.loading=False;d.closed=False;d.owner='p';d.input_source='physical'
        d.shop_source=None;d.shop_error=None;d.keys={'KeyF'};d.pending_start=False;d.clear_frames=0
        d.release_mouse=Mock();d.capture_mouse=Mock();d.show_credits=False
        state={'vending':{'menu_open':True,'vendor':{'id':1}},'dead':False,'won':False}
        d.game=SimpleNamespace(state=state,paused=True,revision=7,lock=threading.RLock(),
                               input=Mock(),purchase=Mock(),close_shop=Mock(),acquire=Mock(return_value='new'))
        return d

    def test_paused_physical_shop_blocks_remote_takeover_before_and_after_hook(self):
        d=self.desktop()
        for sync in (False,True):
            if sync:d.sync_shop()
            for action in ('buy','close_shop','new','keys','resume','pause'):
                with self.assertRaisesRegex(ValueError,'native player'):d.action({'action':action},automated=True)
        self.assertEqual(d.shop_source,'physical');self.assertFalse(d.keys)

    def test_failed_purchase_stays_paused_success_clears_keys_and_resumes_same_source(self):
        d=self.desktop();d.game.purchase.return_value={'ok':False,'error':'Not enough scrap.'}
        self.assertFalse(d.choose_offer(0)['ok']);self.assertEqual(d.shop_error,'Not enough scrap.');d.game.acquire.assert_not_called()
        d.game.purchase.side_effect=lambda *args:(d.game.state['vending'].update(menu_open=False) or {'ok':True})
        d.choose_offer(1);self.assertIsNone(d.shop_source);self.assertEqual(d.input_source,'physical')
        self.assertFalse(d.keys);d.game.acquire.assert_called_once_with()

    def test_leave_stays_paused_and_acquire_cannot_resume_an_open_shop(self):
        d=self.desktop();d.resume();d.game.acquire.assert_not_called()
        d.leave_shop();d.game.close_shop.assert_called_once_with();d.game.acquire.assert_not_called()
        self.assertFalse(d.keys);self.assertIsNone(d.shop_source)

    def test_native_digit_and_scaled_window_click_choose_without_weapon_or_fire_input(self):
        import sys
        from rogue import desktop
        from test_native_playability import FakeGame, GLFW
        with TemporaryDirectory() as root, patch.object(desktop,'NativeGame',FakeGame):
            d=Desktop(root,'fixture.wad',port=0,autostart=False)
            try:
                g=GLFW()
                with patch.dict(sys.modules,{'glfw':g}):d.bind()
                d.resume();d.game.state['vending']={'menu_open':True,'vendor':{'id':1}}
                d.game.paused=True;d.choose_offer=Mock();d.input_source='api';d.shop_source='api'
                key=g.callbacks['set_key_callback']
                key(d.window,g.KEY_2,0,g.PRESS,0)
                d.choose_offer.assert_called_once_with(1)
                self.assertNotIn('Digit2',d.keys)
                self.assertEqual(d.shop_source,'physical')
                d.choose_offer.reset_mock()
                g.get_window_size=lambda _: (1280,800)
                g.get_cursor_pos=lambda _: (200,400) # second row in 640x400 UI
                d.mouse_button(g.MOUSE_BUTTON_LEFT,g.PRESS)
                d.choose_offer.assert_called_once_with(1)
                self.assertNotIn('MouseFire',d.keys)
                d.game.acquire=Mock();d._focus_callback(d.window,False)
                self.assertEqual(d.shop_source,'physical');d.game.acquire.assert_not_called()
            finally:d.close()


if __name__=='__main__':main(verbosity=2)
