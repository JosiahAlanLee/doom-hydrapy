# SPDX-License-Identifier: GPL-3.0-or-later
"""Reuse the native player's focus, ownership, pause and shopping rules in 3D."""
import json,math,os,threading
import numpy as np
from PIL import Image,ImageDraw
from rogue.desktop import Desktop as BaseDesktop
from rogue.hud import overlay,shop_overlay,text,PANEL,MUTED,INK
from .hud import decorate,EncounterHUD
from .cues import Cues
from .game import Game

class Desktop(BaseDesktop):
    def __init__(self,*args,**kwargs):
        self.encounter_hud=EncounterHUD()
        self.shader_cues=Cues();self.cues_enabled=os.environ.get('NULLRUN_CUE_SHADERS')=='1'
        self.mouse_look=0.
        super().__init__(*args,**kwargs,game_factory=Game)
        try:preferences=json.loads((self.root/'view-settings.json').read_text())
        except (OSError,ValueError):preferences={}
        if isinstance(preferences,dict) and type(preferences.get('cue_shaders')) is bool:self.cues_enabled=preferences['cue_shaders']
        if not (self.root/'view-settings.json').exists():self.mouse_sensitivity=1.
    def save_view(self):
        with self.view_lock:
            p=self.root/'view-settings.tmp'
            p.write_text(json.dumps(dict(mode=self.mode,flicker=self.flicker,mouse_sensitivity=self.mouse_sensitivity,cue_shaders=self.cues_enabled)))
            p.replace(self.root/'view-settings.json')
    def action(self,data,automated=False):
        if data.get('action')=='cues':
            enabled=data.get('enabled')
            if type(enabled) is not bool:raise ValueError('Expected boolean')
            if enabled:super().action({'action':'filter','mode':0},automated)
            self.cues_enabled=enabled;self.last_time=None;self.save_view();return
        result=super().action(data,automated)
        if data.get('action')=='filter':
            self.cues_enabled=False;self.last_time=None;self.save_view()
        return result
    def status(self):
        state=super().status()
        state['cue_shaders_enabled']=self.cues_enabled
        state['shader_cues']=(self.cache or {}).get('cues',{})
        if self.cues_enabled and self.mode==0:state['treatment']='EVENT EFFECTS'
        return state
    def mouse_motion(self,x,y):
        if self.closed or not self.mouse_captured or not self.focused or self.input_source!='physical' or self.game.paused:return
        if not all(math.isfinite(v) for v in (x,y)):self.mouse_last=None;return
        if self.mouse_last is not None:
            self.mouse_turn=max(-4096.,min(4096.,self.mouse_turn+(x-self.mouse_last[0])*self.mouse_sensitivity))
            self.mouse_look=max(-4096.,min(4096.,self.mouse_look+(y-self.mouse_last[1])*self.mouse_sensitivity))
        self.mouse_last=(x,y)
    def capture_mouse(self):self.mouse_look=0.;super().capture_mouse()
    def release_mouse(self):self.mouse_look=0.;super().release_mouse()
    def tick(self,ctx,renderer,beat=None):
        if self.owner and not self.game.paused and not self.loading and self.focused and self.input_source=='physical':
            look=max(-4096,min(4096,int(self.mouse_look)))
            if look:
                with self.game.lock:self.game.engine.move(0,look)
                self.mouse_look-=look
        super().tick(ctx,renderer,beat)
    def bind(self):
        was=self.bound;super().bind()
        if was or not self.bound:return
        g=self.glfw;previous=self._key_callback
        def key(w,k,s,a,m):
            if a==g.PRESS and not self.shopping():
                if k==g.KEY_F2:self.action({'action':'flicker','enabled':not self.flicker});return
                if k==g.KEY_F3:self.action({'action':'filter','mode':0 if self.cues_enabled else (self.mode+1)%4});return
                if k==g.KEY_F4:self.action({'action':'cues','enabled':not self.cues_enabled});return
            previous(w,k,s,a,m)
        g.set_key_callback(self.window,key)
        # Replace our callback identity so inherited unbind restores correctly.
        self._callbacks=[(setter,key if callback is previous else callback,old) for setter,callback,old in self._callbacks]
        self._key_callback=key
        g.set_window_title(self.window,'NULL RUN / TOWER')
    def hud(self,state,paused,encounter=None):
        layer=decorate(Image.new('RGBA',(640,400),(0,0,0,0)),{**state,'paused':paused},encounter)
        if state.get('vending',{}).get('menu_open'):return shop_overlay(layer,state,self.shop_error)
        if paused or state.get('dead') or state.get('won'):
            layer=overlay(layer,state,self.show_credits,self.game.error,self.loading,self.mouse_sensitivity)
            d=ImageDraw.Draw(layer)
            if self.show_credits:
                d.rectangle((46,147,592,173),fill=PANEL)
                text(d,(46,149),'3D ENGINE',MUTED);text(d,(190,149),'UZDOOM / COMMUNITY CONTRIBUTORS',INK)
            else:
                d.rectangle((46,147,594,226),fill=PANEL)
                for i,line in enumerate(['WASD move / MOUSE look up, down and turn','CLICK / CTRL fire / SPACE jump / F use','SHIFT run / TAB map / 1-7 weapons']):text(d,(46,149+28*i),line,INK)
                text(d,(46,328),'F2 light / F3 RAW + filters / F4 event effects '+('ON' if self.cues_enabled else 'OFF'),MUTED)
        return layer
    def draw_screen(self,rgb,state,st,paused):
        layer=self.hud(state,paused).resize((1280,800),Image.Resampling.NEAREST)
        return Image.alpha_composite(Image.fromarray(rgb).convert('RGBA'),layer).convert('RGB')
    def snapshot(self,t):
        if self.last_time==t and self.cache is not None:return self.cache
        if not self.loading and self.game.lock.acquire(blocking=False):
            # Game.render replaces its array; it never modifies an old frame.
            # Holding this reference is safe after releasing the game lock.
            try:state=self.game.snapshot();rgb=self.game.rgb
            finally:self.game.lock.release()
        elif self.cache:state=self.cache['state'];rgb=self.cache['raw']
        else:raise RuntimeError('No native tower frame available')
        paused=state.get('paused',True) or self.loading
        cues=self.shader_cues.sample({**state,'paused':paused},enabled=self.cues_enabled and self.mode==0)
        # World pixels and instruments have separate GPU sources. Paint the
        # small instrument layer only when visible information changes.
        encounter=self.encounter_hud.prepare({**state,'paused':paused})
        visible={k:state.get(k) for k in ('health','armor','ammo','weapon','kills','total_kills','secrets','floor_name','map','floors','angle','argon','vending','dead','won','revision')}
        visible['encounter']=encounter
        key=(json.dumps(visible,sort_keys=True),paused,self.show_credits,self.game.error,self.shop_error,self.loading,self.mouse_sensitivity,self.cues_enabled)
        hud=self.cache['hud'] if self.cache and self.cache.get('hud_key')==key else np.asarray(self.hud(state,paused,encounter).resize((1280,800),Image.Resampling.NEAREST))
        self.cache={'raw':rgb,'state':state,'hud':hud,'hud_key':key,'cues':cues};self.last_time=t
        return self.cache

def start(root,wad,port=8774,autostart=False,*,resources=None):
    candidate=Desktop(root,wad,port,campaign_only=True,autostart=autostart,defer=True)
    candidate._manage_current=True;candidate._stage_resources=resources
    try:
        if resources is None:candidate._activate()
        else:
            resources._open_resource(candidate,candidate._activate);resources._RESOURCES.append(candidate)
        if candidate._resource_state=='active' and candidate._previous:candidate._previous.close()
        return candidate
    except BaseException:candidate.close();raise
