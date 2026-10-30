# SPDX-License-Identifier: GPL-2.0-or-later
"""Measure the paired 1 Hz video square and captured audio gate."""
from pathlib import Path
import json,subprocess,sys
import numpy as np
import soundfile as sf

def sync(capture):
    capture=Path(capture);audio,sr=sf.read(capture/'capture.wav',always_2d=True)
    x=audio[:,15]>.5
    ai=np.flatnonzero(x & ~np.r_[False,x[:-1]])/sr
    # Marker centre: st=(.023,.975), top-left in video coordinates.
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(capture/'studio.mp4'),'-vf','crop=4:4:42:24','-f','rawvideo','-pix_fmt','rgb24','-'])
    px=np.frombuffer(raw,np.uint8).reshape(-1,4,4,3).mean(axis=(1,2,3))
    y=px>200
    vi=np.flatnonzero(y & ~np.r_[False,y[:-1]])/30
    if len(vi)<5 or len(ai)<5:raise RuntimeError(f'sync markers absent: audio {ai[:15]}, video {vi[:15]}, range {px.min()}..{px.max()}')
    # Exclude the startup frame which can show beat zero before transport starts.
    aa=ai[ai>.5];vv=vi[vi>.5]
    # Startup is <500 ms; nearest pulses have the same integer second identity.
    pairs=[]
    for t in vv:
        idx=np.argmin(abs(aa-t))
        if abs(aa[idx]-t)<.5:pairs.append((t,aa[idx]))
    pairs=np.array(pairs);d=pairs[:,1]-pairs[:,0]
    slope,intercept=np.polyfit(pairs[:,0],d,1)
    result=dict(audio_pulses=len(ai),video_pulses=len(vi),matched_pulses=len(pairs),audio_minus_video_seconds=float(np.median(d)),offset_intercept_seconds=float(intercept),drift_seconds_per_second=float(slope),drift_over_take_ms=float(slope*(pairs[-1,0]-pairs[0,0])*1000),residual_p95_ms=float(np.percentile(abs(d-(slope*pairs[:,0]+intercept)),95)*1000),frame_resolution_ms=1000/30,video_marker_minmax=[float(px.min()),float(px.max())],pairs=pairs.tolist())
    return result
if __name__=='__main__':
    result=sync(sys.argv[1]);text=json.dumps(result,indent=2)+'\n'
    if len(sys.argv)>2:Path(sys.argv[2]).write_text(text)
    print(text[:1000])
