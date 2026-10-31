# SPDX-License-Identifier: GPL-3.0-or-later
"""Render the actual presentation chain, including its post-effect HUD."""
from pathlib import Path
import argparse,json,time,urllib.request
import numpy as np
from PIL import Image
from hydrapy import FrameSource,src
from hydrapy.core import Patch
from hydrapy.backend_gl import GLRenderer
from uzdoom.presentation import world_effects


def run(a):
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    with urllib.request.urlopen(a.game+'/state',timeout=3) as f:live=json.load(f)
    if not live.get('paused',True) and live.get('input_source')=='physical':raise RuntimeError('Preserve physical play; GPU verification deferred')
    image=np.asarray(Image.open(a.image).convert('RGBA'));h,w=image.shape[:2]
    instruments=np.zeros_like(image);instruments[:44]=(31,119,173,255);instruments[-94:]=(177,90,43,255)
    instruments[h//2-2:h//2+2,w//2-2:w//2+2]=(240,225,120,255)
    state={'mode':0,'quiet_strength':0.,'quiet_progress':0.,'surveyor_strength':0.,'surveyor_progress':0.}
    patch=Patch(size=(w,h));source=src(FrameSource(lambda t:image));hud=src(FrameSource(lambda t:instruments))
    chain=world_effects(source,lambda:state['mode'],lambda t:state).layer(hud);chain.out(patch=patch)
    renderer=GLRenderer(patch,size=(w,h),fps=60)
    renderer.settle=1e9
    report={'renderer':renderer.ctx.info.get('GL_RENDERER'),'checks':[],'limits':'Actual HydraPy GL chain with a preserved world frame and synthetic scalar cues. Native semantic cue/combined audio checks are separate.'}
    def save(): (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    def shot(name,values):
        state.update(mode=0,quiet_strength=0.,quiet_progress=0.,surveyor_strength=0.,surveyor_progress=0.);state.update(values)
        for _ in range(3):renderer.step(renderer.frame/60)
        pixels=renderer.read();Image.fromarray(pixels).save(out/(name+'.png'));return pixels
    try:
        raw=shot('raw',{})
        overlay=instruments[:,:,3]>0
        for name,values in [('quiet',{'quiet_strength':.42,'quiet_progress':.85}),('surveyor',{'surveyor_strength':.55,'surveyor_progress':.85}),('both',{'quiet_strength':.21,'quiet_progress':.85,'surveyor_strength':.55,'surveyor_progress':.85})]:
            pixels=shot(name,values);y,x=np.mgrid[:h,:w];center=(abs((x+.5)/w-.5)<=.1)&(abs((y+.5)/h-.5)<=.1)
            delta=np.max(abs(pixels.astype(int)-raw.astype(int)),axis=2)
            checks={'center_unchanged':int(delta[center].max())<=1,'hud_unchanged':int(delta[overlay].max())<=1,'effect_visible':bool(np.count_nonzero(delta>1)>50),'pixels_finite':bool(np.isfinite(pixels).all())}
            report['checks'].append({'name':name,**checks});assert all(checks.values()),(name,checks)
        restored=shot('raw-restored',{});assert np.array_equal(restored,raw),'RAW restoration differs'
        report['checks'].append({'name':'RAW restored exactly','passed':True})
        for mode in (1,2,3):shot('legacy-'+str(mode),{'mode':mode})
        report['compiled_variants']=len(renderer._variants);report['state']='passed';save();print(json.dumps(report),flush=True)
    except BaseException as e:report.update(state='failed',error=str(e));save();raise
    finally:renderer.release()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--image',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--game',default='http://127.0.0.1:8774');run(p.parse_args())
