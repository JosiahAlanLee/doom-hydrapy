# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise the actual live GL chain with encounter cues and hostile scalars."""
from pathlib import Path
import argparse,json
import numpy as np
from PIL import Image
from hydrapy import FrameSource,src
from hydrapy.core import Patch
from hydrapy.backend_gl import GLRenderer
from uzdoom.presentation import world_effects


def run(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    report={'state':'running','checks':[],'limits':'Actual GPU presentation chain with synthetic encounter uniforms; native semantic and combined-audio checks are separate.'}
    for w,h in [(640,400),(960,540),(1024,256)]:
        y,x=np.mgrid[:h,:w];image=np.empty((h,w,4),np.uint8)
        image[:,:,0]=(x*7+y*13)%256;image[:,:,1]=(x*3+y*5)%256;image[:,:,2]=(x+y*17)%256;image[:,:,3]=(x+y)%200+55
        state={};base=dict(quiet_strength=0.,quiet_progress=0.,surveyor_strength=0.,surveyor_progress=0.,ritual_strength=0.,ritual_family=0.,ritual_progress=0.,ritual_open=0.,grip_strength=0.,grip_progress=0.,grip_warning=0.,grip_active=0.)
        patch=Patch(size=(w,h));source=src(FrameSource(lambda t:image));world_effects(source,lambda:0,lambda t:state).out(patch=patch)
        renderer=GLRenderer(patch,size=(w,h),fps=60);renderer.settle=1e9
        report['renderer']=renderer.ctx.info.get('GL_RENDERER')
        def shot(values):
            state.clear();state.update(base);state.update(values)
            for _ in range(2):renderer.step(renderer.frame/60)
            # read() presents RGB over black. Inspect the actual RGBA history
            # texture to test source alpha rather than a composited screenshot.
            fbo=renderer.ctx.framebuffer(color_attachments=[renderer.displayed_texture()])
            try:data=fbo.read(components=4,dtype='f1',alignment=1)
            finally:fbo.release()
            return np.frombuffer(data,np.uint8).reshape(h,w,4)[::-1].copy()
        cases=[]
        for family in range(1,5):
            for progress in (0.,.5,1.):cases.append((f'family{family}-stage{progress}',dict(ritual_strength=.3,ritual_family=family,ritual_progress=progress),True))
            for opening in (1.,.5):cases.append((f'family{family}-open{opening}',dict(ritual_strength=.3,ritual_family=family,ritual_open=opening),True))
        for p in (0.,.5,1.):cases.append((f'mask-warning-{p}',dict(grip_strength=.4,grip_warning=p),True))
        for p in (0.,.48,.96):cases.append((f'active-grip-{p}',dict(grip_strength=.45,grip_active=1.,grip_progress=p),True))
        for field,value in [('ritual_family',0.),('ritual_family',1.5),('ritual_progress',float('nan')),('ritual_open',float('inf')),('ritual_strength',2.)]:
            values=dict(ritual_strength=.3,ritual_family=1.,ritual_progress=.5);values[field]=value;cases.append(('invalid-'+field,values,False))
        for field,value in [('grip_progress',float('nan')),('grip_active',float('inf')),('grip_warning',-1.),('grip_strength',2.)]:
            values=dict(grip_strength=.45,grip_active=1.,grip_progress=.5);values[field]=value;cases.append(('invalid-'+field,values,False))
        try:
            raw=shot({})
            protected=(((y+.5)/h<88/400)|((y+.5)/h>=328/400)|
                       ((abs((x+.5)/w-.5)<=.1)&(abs((y+.5)/h-.5)<=.1)))
            for name,values,active in cases:
                pixels=shot(values);delta=np.max(abs(pixels.astype(int)-raw.astype(int)),axis=2)
                checks=dict(protected_unchanged=bool(np.array_equal(pixels[protected],raw[protected])),alpha_unchanged=bool(np.array_equal(pixels[:,:,3],raw[:,:,3])),finite=bool(np.isfinite(pixels).all()),visible_or_raw=bool(np.count_nonzero(delta>1)>20) if active else bool(np.array_equal(pixels,raw)))
                report['checks'].append(dict(size=[w,h],name=name,**checks));assert all(checks.values()),(name,[w,h],checks)
                if w==640 and name in ('family3-open1.0','active-grip-0.0','mask-warning-1.0'):Image.fromarray(pixels).save(output/(name+'.png'))
            assert np.array_equal(shot({}),raw),'RAW restoration changed'
        except BaseException as error:
            report.update(state='failed',error=str(error));raise
        finally:renderer.release();(output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    report['state']='passed';(output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'state':report['state'],'checks':len(report['checks']),'renderer':report['renderer']}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);run(p.parse_args().output)
