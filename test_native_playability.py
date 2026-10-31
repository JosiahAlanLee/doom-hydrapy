# SPDX-License-Identifier: GPL-2.0-or-later
"""Mouse ownership, failed replacements, and real native input regressions."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, main, skipUnless
from unittest.mock import Mock, patch
from urllib.request import urlopen
import importlib.util
import json
import os
import sys
import threading

import numpy as np
from rogue import desktop
from rogue.desktop import Desktop


class FakeGame:
    def __init__(self, wad, root, initial_mode='campaign'):
        self.lock=threading.RLock();self.engine=SimpleNamespace(command=Mock())
        self.paused=True;self.error=None;self.closed=False;self.owner=None
        self.state={'dead':False,'won':False};self.rgb=np.zeros((400,640,3),dtype=np.uint8)
        self.manifest={'seed':42,'mode':initial_mode};self.inputs=[]
    def render(self):pass
    def snapshot(self):return dict(self.state,paused=self.paused)
    def acquire(self):self.owner='owner';self.paused=False;return self.owner
    def input(self,owner,keys,paused=False,turn=0):
        if owner!=self.owner:raise ValueError('Wrong owner')
        self.inputs.append((list(keys),turn,paused));self.paused=paused
        if paused:self.owner=None
    def close(self):self.closed=True


class GLFW:
    PRESS=1;RELEASE=0;TRUE=1;FALSE=0
    MOUSE_BUTTON_LEFT=0;MOUSE_BUTTON_RIGHT=1
    CURSOR=10;CURSOR_DISABLED=11;CURSOR_NORMAL=12;RAW_MOUSE_MOTION=13
    FOCUSED=14;FOCUS_ON_SHOW=15;PLATFORM_X11=16
    def __init__(self):self.callbacks={};self.modes=[];self.constants={};self.context=object()
    def __getattr__(self,name):
        if name.startswith('KEY_'):
            key=name[4:]
            if len(key)==1:return ord(key)
            if key.startswith('F') and key[1:].isdigit():return 289+int(key[1:])
            return {'ENTER':257,'ESCAPE':256,'TAB':258,'SPACE':32,'LEFT_BRACKET':91,'RIGHT_BRACKET':93,
                    'LEFT':263,'RIGHT':262,'UP':265,'DOWN':264,'LEFT_CONTROL':341,'RIGHT_CONTROL':345,
                    'LEFT_SHIFT':340,'RIGHT_SHIFT':344}[key]
        if name.startswith('set_') and name.endswith('_callback'):
            def setter(window,value):
                previous=self.callbacks.get(name);self.callbacks[name]=value;return previous
            return setter
        raise AttributeError(name)
    def get_current_context(self):return self.context
    def get_platform(self):return 0 # Wayland: must not call Xlib with a null display.
    def set_window_title(self,*args):pass
    def set_window_attrib(self,*args):pass
    def focus_window(self,*args):pass
    def get_window_attrib(self,*args):return 1
    def set_input_mode(self,window,mode,value):self.modes.append((mode,value))
    def raw_mouse_motion_supported(self):return True


class NativeControls(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.root=Path(self.tmp.name)
        self.fake=patch.object(desktop,'NativeGame',FakeGame);self.fake.start()
        self.games=[]
    def tearDown(self):
        for d in reversed(self.games):d.close()
        self.fake.stop();self.tmp.cleanup()
    def player(self,**kw):
        d=Desktop(self.root,'fixture.wad',port=0,autostart=False,**kw)
        self.games.append(d);return d
    def bind(self,d):
        g=GLFW()
        with patch.dict(sys.modules,{'glfw':g}):d.bind()
        return g
    def tick(self,d):
        d.tick(None,SimpleNamespace(ctx=SimpleNamespace(info={'GL_RENDERER':'fixture'})))

    def test_captured_mouse_turns_once_and_pause_discards_pending_motion(self):
        d=self.player();g=self.bind(d);d.resume()
        self.assertIn((g.CURSOR,g.CURSOR_DISABLED),g.modes)
        g.callbacks['set_cursor_pos_callback'](d.window,100,50)
        g.callbacks['set_cursor_pos_callback'](d.window,112,900)
        self.tick(d);self.tick(d)
        self.assertEqual([i[1] for i in d.game.inputs[-2:]],[36,0])
        d.mouse_motion(200,20);self.assertNotEqual(d.mouse_turn,0)
        g.callbacks['set_window_focus_callback'](d.window,False)
        self.assertTrue(d.game.paused);self.assertEqual(d.mouse_turn,0)
        self.assertIn((g.CURSOR,g.CURSOR_NORMAL),g.modes)
        d.mouse_motion(300,10);self.assertEqual(d.mouse_turn,0)

    def test_capture_click_does_not_fire_and_buttons_release(self):
        d=self.player();g=self.bind(d)
        callback=g.callbacks['set_mouse_button_callback']
        callback(d.window,g.MOUSE_BUTTON_LEFT,g.PRESS,0)
        self.assertFalse(d.game.paused);self.assertFalse(d.keys)
        callback(d.window,g.MOUSE_BUTTON_LEFT,g.RELEASE,0)
        callback(d.window,g.MOUSE_BUTTON_LEFT,g.PRESS,0)
        callback(d.window,g.MOUSE_BUTTON_RIGHT,g.PRESS,0)
        self.tick(d);self.assertEqual(set(d.game.inputs[-1][0]),{'MouseFire','MouseUse'})
        callback(d.window,g.MOUSE_BUTTON_LEFT,g.RELEASE,0)
        callback(d.window,g.MOUSE_BUTTON_RIGHT,g.RELEASE,0)
        self.tick(d);self.assertFalse(d.game.inputs[-1][0])

    def test_escape_releases_all_controls_and_enter_recaptures_cleanly(self):
        d=self.player();g=self.bind(d);callback=g.callbacks['set_key_callback']
        callback(d.window,g.KEY_ENTER,0,g.PRESS,0)
        callback(d.window,g.KEY_W,0,g.PRESS,0)
        self.assertTrue(d.mouse_captured);self.assertIn('KeyW',d.keys)
        d.mouse_motion(100,0);d.mouse_motion(120,0)
        callback(d.window,g.KEY_ESCAPE,0,g.PRESS,0)
        self.assertTrue(d.game.paused);self.assertFalse(d.keys)
        self.assertFalse(d.mouse_captured);self.assertEqual(d.mouse_turn,0)
        callback(d.window,g.KEY_ENTER,0,g.PRESS,0)
        self.assertTrue(d.mouse_captured);d.mouse_motion(10000,0)
        self.assertEqual(d.mouse_turn,0)

    def test_remote_session_does_not_capture_mouse_and_physical_click_takes_over(self):
        d=self.player();g=self.bind(d);d.resume(automated=True)
        d.mouse_motion(100,0);d.mouse_motion(200,0)
        self.assertFalse(d.mouse_captured);self.assertEqual(d.mouse_turn,0)
        d.mouse_button(g.MOUSE_BUTTON_LEFT,g.PRESS)
        self.assertEqual(d.input_source,'physical');self.assertTrue(d.mouse_captured)
        self.assertFalse(d.keys)

    def test_credits_pause_release_mouse_and_redraw_without_a_new_engine_frame(self):
        d=self.player();g=self.bind(d);d.resume()
        first=d.snapshot(0)['image']
        callback=g.callbacks['set_key_callback'];callback(d.window,g.KEY_C,0,g.PRESS,0)
        self.assertTrue(d.show_credits);self.assertTrue(d.game.paused)
        self.assertFalse(d.mouse_captured)
        credits=d.snapshot(.016)['image'];self.assertIsNot(first,credits)
        callback(d.window,g.KEY_C,0,g.PRESS,0)
        self.assertFalse(d.show_credits);self.assertIsNot(credits,d.snapshot(.032)['image'])
        d.resume();self.assertFalse(d.show_credits);self.assertTrue(d.mouse_captured)

    def test_close_restores_previous_callbacks_and_does_not_remove_new_owner(self):
        d=self.player();g=GLFW();previous=Mock()
        g.set_key_callback(g.context,previous)
        with patch.dict(sys.modules,{'glfw':g}):d.bind()
        d.resume();new_motion=Mock();g.set_cursor_pos_callback(d.window,new_motion)
        d.close()
        self.assertIs(g.callbacks['set_key_callback'],previous)
        self.assertIs(g.callbacks['set_cursor_pos_callback'],new_motion)
        self.assertIn((g.CURSOR,g.CURSOR_NORMAL),g.modes)
        self.assertIsNone(g.callbacks['set_mouse_button_callback'])

    def test_preference_applied_before_first_frame_and_sensitivity_persists(self):
        (self.root/'view-settings.json').write_text(json.dumps({'flicker':False,'mouse_sensitivity':4}))
        d=self.player()
        d.game.engine.command.assert_called_once_with('STROBE_VIEW 0')
        d.adjust_mouse(1.25);d.close()
        again=self.player();self.assertEqual(again.mouse_sensitivity,5)
        self.assertFalse(again.flicker)

    def test_escape_during_new_run_cancels_autostart(self):
        d=self.player();d.autostart=True
        entered=threading.Event();release=threading.Event()
        def build(*args):entered.set();release.wait(3)
        d.game.new_run=build
        d.new();self.assertTrue(entered.wait(2));self.assertTrue(d.pending_start)
        d.pause();release.set();d.builder.join(3)
        self.assertFalse(d.loading);self.assertFalse(d.pending_start)


@skipUnless(importlib.util.find_spec('hydrapy'),'Install HydraPy or set PYTHONPATH to its checkout')
class StudioResourceReplacement(TestCase):
    def setUp(self):
        import hydrapy.live as resources
        self.resources=resources;self.previous_resources=resources._RESOURCES
        self.previous_current=desktop._current
        resources._RESOURCES=[];desktop._current=None
        self.tmp=TemporaryDirectory();self.root=Path(self.tmp.name)
        self.fake=patch.object(desktop,'NativeGame',FakeGame);self.fake.start()
    def tearDown(self):
        self.resources.close_resources()
        if desktop._current:desktop._current.close()
        self.resources._RESOURCES=self.previous_resources;desktop._current=self.previous_current
        self.fake.stop();self.tmp.cleanup()
    def start(self,port=0):
        return desktop.start(self.root,'fixture.wad',port,autostart=False,resources=self.resources)
    def advertised(self):return json.loads((self.root/'control.json').read_text())
    def assert_serving(self,d):
        advertised=self.advertised();self.assertEqual(advertised['token'],d.token)
        with urlopen(advertised['url']+'/state',timeout=2) as response:self.assertEqual(response.status,200)

    def test_failed_construction_preserves_current_run_and_server(self):
        old=self.start();engine=old.game.engine;advertised=self.advertised()
        with patch.object(desktop,'NativeGame',side_effect=RuntimeError('Invalid candidate')):
            with self.assertRaisesRegex(RuntimeError,'Invalid candidate'):self.start(old.port)
        self.assertIs(desktop._current,old);self.assertIs(old.game.engine,engine)
        self.assertFalse(old.closed);self.assertEqual(self.advertised(),advertised);self.assert_serving(old)

    def test_aborted_renderer_validation_does_not_activate_candidate(self):
        old=self.start();engine=old.game.engine
        with self.assertRaisesRegex(RuntimeError,'Shader validation'):
            with self.resources.ResourceStage():
                candidate=self.start(old.port);candidate.bind=Mock()
                candidate.tick(None,None)
                candidate.bind.assert_not_called()
                self.assertIs(desktop._current,old);self.assert_serving(old)
                raise RuntimeError('Shader validation')
        self.assertTrue(candidate.closed);self.assertFalse(old.closed)
        self.assertIs(old.game.engine,engine);self.assert_serving(old)

    def test_successful_commit_hands_over_port_and_closes_previous_game(self):
        old=self.start();port=old.port
        with self.resources.ResourceStage() as stage:
            candidate=self.start(port);self.assertIsNone(candidate.http)
            stage.commit()
        self.assertIs(desktop._current,candidate);self.assertTrue(old.closed)
        self.assertTrue(old.game.closed);self.assertEqual(candidate.port,port)
        self.assert_serving(candidate)

    def test_disarmed_studio_starts_software_play_after_validation(self):
        old=self.start();port=old.port
        with self.resources.ResourceStage() as stage:
            candidate=self.start(port);candidate.bind=Mock()
            candidate.tick(None,None);candidate.bind.assert_not_called()
            stage.commit(armed=False)
            candidate.tick(None,None);candidate.bind.assert_not_called()
        self.assertTrue(old.closed);self.assertIsNone(candidate.http)
        renderer=SimpleNamespace(ctx=SimpleNamespace(info={'GL_RENDERER':'fixture'}))
        candidate.tick(None,renderer)
        candidate.bind.assert_called_once_with();self.assertIs(desktop._current,candidate)
        self.assertEqual(candidate.port,port);self.assert_serving(candidate)

    def test_later_resource_failure_restores_previous_game_and_port(self):
        old=self.start();engine=old.game.engine
        class FailingDevice:
            _resource_state='pending'
            def _activate(self):raise RuntimeError('Device unavailable')
        with self.assertRaisesRegex(RuntimeError,'Device unavailable'):
            with self.resources.ResourceStage() as stage:
                candidate=self.start(old.port);self.resources._RESOURCES.append(FailingDevice())
                stage.commit()
        self.assertTrue(candidate.closed);self.assertFalse(old.closed)
        self.assertIs(desktop._current,old);self.assertIs(old.game.engine,engine)
        self.assertTrue(old.game.paused);self.assert_serving(old)


@skipUnless(os.environ.get('FREEDOOM_WAD'),'Set FREEDOOM_WAD for native engine checks')
class NativeInputEngine(TestCase):
    def test_mouse_turn_is_bounded_one_shot_and_does_not_move_player(self):
        from client import Doom
        from rogue.maps import generate
        from test_rogue import fixture_wad
        with TemporaryDirectory() as t:
            f=generate(42,1);path=Path(t)/'mouse.wad';fixture_wad(path,[f],player_only=True)
            with Doom(os.environ['FREEDOOM_WAD'],demo=None,pwad=path,rogue_floors=1) as engine:
                before=engine.state();engine.turn(20);engine.advance(4);after=engine.state()
                self.assertNotEqual(before['angle'],after['angle'])
                self.assertEqual((before['x'],before['y']),(after['x'],after['y']))
                engine.advance(20);self.assertEqual(engine.state()['angle'],after['angle'])
                for value in [True,1.5,4097,-4097]:
                    with self.assertRaises(ValueError):engine.turn(value)
                engine.turn(-20);engine.advance(4)
                self.assertLess(abs((engine.state()['angle']-before['angle']+180)%360-180),1)

    def test_saved_steady_view_is_applied_to_real_engine_on_startup(self):
        with TemporaryDirectory() as t:
            root=Path(t);(root/'view-settings.json').write_text('{"flicker":false}')
            d=Desktop(root,os.environ['FREEDOOM_WAD'],port=0,campaign_only=False,
                      autostart=False,defer=True,initial_mode='strobe')
            try:
                self.assertFalse(d.game.state['strobe']['flicker'])
                with d.game.lock:
                    d.game.engine.advance(100);self.assertFalse(d.game.engine.state()['strobe']['flicker'])
            finally:d.close()


if __name__=='__main__':main(verbosity=2)
