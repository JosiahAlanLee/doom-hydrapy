# SPDX-License-Identifier: GPL-2.0-or-later
"""Live-cost measurement, including engine IPC, upload and GPU completion."""
from render_legible import *
e=Doom(ROOT/'data/freedoom-0.13.0/freedoom2.wad','demo2')
source=h.src(h.FrameSource(e.frame)).pixelate(640,400)
results={}
for name,chain in [('terminal',source.doomLegibleAscii(240)),('print',source.doomLegiblePrint())]:
 patch=h.core.Patch();chain.out(patch=patch);r=GLRenderer(patch=patch,size=(1920,1080),fps=60)
 ts=[]
 for n in range(210):
  t0=time.perf_counter();r.step(n/60);r.ctx.finish()
  if n>=30:ts.append((time.perf_counter()-t0)*1000)
 results[name]=dict(median_ms=float(np.median(ts)),p95_ms=float(np.percentile(ts,95)),frames=len(ts))
e.close();print(json.dumps(results,indent=2));(OUT/'doom-legible-livecost.json').write_text(json.dumps(results,indent=2))
