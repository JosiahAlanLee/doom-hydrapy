# SPDX-License-Identifier: GPL-2.0-or-later
"""Offline reconstruction using original recording slots and unchanged WAV."""
import os,sys,json,time,subprocess,hashlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from scipy.ndimage import gaussian_filter,sobel
REPO=Path(__file__).resolve().parent;ROOT=REPO.parent/'doom-hydrapy-20261030';OUT=ROOT/'take';WORK=REPO/'analysis-legible';WORK.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT.parent/'gorgon-r3b-20261030/runtime'))
import hydrapy as h
from hydrapy.backend_gl import GLRenderer
from client import Doom
import ascii_op,legible_ops

def run(args):return subprocess.run(args,check=True,capture_output=True,text=True)
def sha(p):
 with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def metric(a,b):
 def edges(x):
  y=np.dot(x[::4,::4,:3],[.2126,.7152,.0722]);y=gaussian_filter(y,1.5)
  return np.hypot(sobel(y,0),sobel(y,1)).ravel()
 x,y=edges(a),edges(b)
 return float(np.corrcoef(x,y)[0,1]) if x.std()*y.std()>0 else 0.
def main():
 assert not subprocess.run(['pgrep','-f','[p]ython.*-m gorgon.*render'],capture_output=True).stdout,'capture active'
 wav=OUT/'doom-freedoom-poly-1080p.wav';audiohash=sha(wav)
 stamps=json.loads(next((ROOT/'poly-capture/studio/.hydrapy/exports').glob('*.timestamps.json')).read_text())
 rows=[json.loads(s) for s in (ROOT/'poly-frame-trace.jsonl').read_text().splitlines()]
 walls=np.array([r['wall'] for r in rows]);indices=np.searchsorted(walls,np.array(stamps['rendered'])-1e-6)
 mapped=[rows[min(int(i),len(rows)-1)] for i in indices]
 gaps=[r['wall']-stamp for r,stamp in zip(mapped,stamps['rendered'])]
 assert max(gaps)<.04,(min(gaps),max(gaps))
 engines=[Doom(ROOT/'data/freedoom-0.13.0'/w,d) for w,d in [('freedoom1.wad','demo1'),('freedoom2.wad','demo2'),('freedoom1.wad','demo3'),('freedoom2.wad','demo4')]]
 holder=[np.zeros((400,640,4),np.uint8)]
 source=h.src(h.FrameSource(lambda t:holder[0])).pixelate(640,400)
 chains=[source.doomAscii(100).contrast(1.1),source.doomLegibleAscii(240),source.brightness(.12).saturate(.3).halftone(5,.65,.75).color(1,.82,.59),source.doomLegiblePrint()]
 # Separate output objects, one shared GL context: independent hidden scenes and valid GL object IDs.
 renderers=[]
 for chain in chains:
  patch=h.core.Patch();chain.out(patch=patch);renderers.append(GLRenderer(patch=patch,size=(1920,1080),fps=30,ctx=renderers[0].ctx if renderers else None))
 original=OUT/'doom-freedoom-poly-1080p.mp4'
 dec=subprocess.Popen(['ffmpeg','-v','error','-i',str(original),'-vsync','0','-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
 temp=WORK/'video.mp4';enc=subprocess.Popen(['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r','30','-i','-','-an','-c:v','h264_nvenc','-preset','p5','-cq','18',str(temp)],stdin=subprocess.PIPE)
 times=[[],[]];scores=[[],[],[],[]];checks=[];sheets=[];n=0
 while True:
  data=dec.stdout.read(1920*1080*3)
  if not data:break
  old=np.frombuffer(data,np.uint8).reshape(1080,1920,3);row=mapped[n];sec=row['seconds'];sample=n%30==0
  if sec<120 or sample:
   e=engines[row['demo']-1];t0=time.perf_counter();holder[0]=e.frame(row['local']);engine_ms=(time.perf_counter()-t0)*1000
   assert e.tic-e.base==row['expected']==row['tic'];checks.append(dict(frame=n,demo=row['demo'],tic=e.tic-e.base,expected=row['expected']))
   # Engine is 640x400 (2x the internal 320x200 raster).
   plain=np.asarray(Image.fromarray(holder[0][:,:,:3]).resize((1920,1080),Image.Resampling.NEAREST))
   imgs={}
   active=1 if sec<60 else 3
   for j,r in enumerate(renderers):
    if j!=active and not sample:continue
    t0=time.perf_counter();r.step(n/30);r.ctx.finish();ms=(time.perf_counter()-t0)*1000
    imgs[j]=r.read()
    if j in (1,3) and n>30:times[j//2].append(ms+engine_ms)
    if sample:scores[j].append(metric(plain,imgs[j]))
   if sec<120:
    frame=imgs[active];frame[:60,:60]=old[:60,:60] # retain original optical sync pulse exactly
   else:frame=old
   if n==300: Image.fromarray(frame).save(WORK/'checkpoint-terminal.png')
   if n in [300,900,1500,2100,2700,3300,4200,5700]:
    tile=Image.new('RGB',(1440,310));draw=ImageDraw.Draw(tile)
    j=0 if sec<60 else 2
    for k,(title,arr) in enumerate([('Plain',plain),('Before',imgs[j]),('After',imgs[j+1])]):
     tile.paste(Image.fromarray(arr).resize((480,270)),(k*480,30));draw.text((k*480+8,8),f'{title} / {sec:.2f}s',fill='white')
    sheets.append(tile)
  else:frame=old
  enc.stdin.write(frame.tobytes());n+=1
  if n%900==0:print('frames',n,flush=True)
 enc.stdin.close();assert enc.wait()==0;assert dec.wait()==0
 for e in engines:e.close()
 sheet=Image.new('RGB',(1440,310*len(sheets)))
 for i,im in enumerate(sheets):sheet.paste(im,(0,310*i))
 sheet.save(OUT/'doom-legible-before-after.jpg')
 final=OUT/'doom-freedoom-poly-legible-1080p.mp4'
 run(['ffmpeg','-y','-v','error','-i',str(temp),'-i',str(wav),'-i',str(OUT/'chapters.ffmeta'),'-map','0:v','-map','1:a','-map_metadata','2','-map_chapters','2','-c:v','copy','-c:a','aac','-b:a','256k','-movflags','+faststart',str(final)])
 run(['ffmpeg','-v','error','-i',str(final),'-f','null','-'])
 meta=json.loads(run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(final)]).stdout)
 original_meta=json.loads(run(['ffprobe','-v','error','-show_streams','-of','json',str(original)]).stdout)
 assert int(meta['streams'][0]['nb_read_frames'])==n==int(original_meta['streams'][0]['nb_frames'])
 assert meta['streams'][0]['duration']==original_meta['streams'][0]['duration']
 assert sha(wav)==audiohash
 # Identical WAV + identical AAC settings should reproduce the original AAC payload.
 def audio_digest(path):return run(['ffmpeg','-v','error','-i',str(path),'-map','0:a','-c','copy','-f','hash','-hash','sha256','-']).stdout.strip()
 report=dict(frames=n,tic_samples=len(checks),tic_mismatches=0,slot_trace_max_gap_ms=max(gaps)*1000,metrics=dict(zip(['ascii_before','ascii_after','print_before','print_after'],[float(np.mean(s)) for s in scores])),metric='Pearson correlation of luminance edge magnitude after 4x reduction and sigma=1.5 blur; every second across entire take',offline_loaded_p95_ms=[float(np.percentile(t,95)) for t in times],wav_sha256=audiohash,aac_payload_identical=audio_digest(original)==audio_digest(final),video=meta)
 (WORK/'tic-checks.json').write_text(json.dumps(checks));(OUT/'doom-legible-verification.json').write_text(json.dumps(report,indent=2));(OUT/'SHA256SUMS-legible').write_text(f'{sha(final)}  {final.name}\n{sha(wav)}  {wav.name}\n');print(json.dumps({k:v for k,v in report.items() if k!='video'},indent=2))
if __name__=='__main__':main()
