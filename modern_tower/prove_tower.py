# SPDX-License-Identifier: GPL-2.0-or-later
"""Verify a native stair climb and 3D camera under an isolated X display."""
from pathlib import Path
import argparse,hashlib,json,os,re,signal,subprocess
import numpy as np
from PIL import Image

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--engine',type=Path,required=True)
parser.add_argument('--iwad',type=Path,required=True)
parser.add_argument('--pk3',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True,help='Fresh, nonexistent output directory')
args=parser.parse_args()
for name in ['engine','iwad','pk3']:
    p=getattr(args,name).resolve()
    if not p.is_file():parser.error(f'{name} must name an existing file')
    setattr(args,name,p)
root=args.output.resolve();root.mkdir(parents=True,exist_ok=False)
shots=root/'shots';shots.mkdir()
commands=['vid_vsync false','vid_maxfps 35','freelook true','lookspring false','screenblocks 11','crosshair 1',
          'con_notifytime 0','nr_camera_test true','nr_probe true','wait 1100',
          'nr_pose 2','nr_pitch 0','wait 140',f'screenshot "{shots}/crown-level.png"',
          'nr_pitch 45','wait 140',f'screenshot "{shots}/crown-down.png"',
          'nr_pitch -45','wait 140',f'screenshot "{shots}/crown-up.png"',
          'nr_pose 1','nr_pitch 0','wait 140',f'screenshot "{shots}/ground-level.png"',
          'nr_pitch -45','wait 140',f'screenshot "{shots}/ground-up.png"','wait 5','quit']
# wait defers the remainder of one command string, not other exec-file lines.
(root/'proof.cfg').write_text('; '.join(commands)+'\n')
(root/'proof.ini').write_text('[GlobalSettings]\nvid_preferbackend=0\nvid_rendermode=4\nvid_vsync=false\nvid_maxfps=35\nvid_fullscreen=false\nwin_w=1280\nwin_h=800\nvid_activeinbackground=true\nvid_lowerinbackground=false\nfreelook=true\nlookspring=false\n')
command=['xvfb-run','-a','-n','189','-s','-screen 0 1280x800x24',str(args.engine),
 '-iwad',str(args.iwad),'-config',str(root/'proof.ini'),'-savedir',str(root/'saves'),
 '-nosound','-nojoy','-noautoload','-stdout','-window','-width','1280','-height','800',
 '-warp','1','-file',str(args.pk3),'+exec',str(root/'proof.cfg')]
env=dict(os.environ,XDG_CONFIG_HOME=str(root/'config'),XDG_DATA_HOME=str(root/'data'),
         XDG_CACHE_HOME=str(root/'cache'),SDL_AUDIODRIVER='dummy')
report={'state':'running','command':command,'isolated':True,'sound_disabled':True,
        'scope':'Geometry/camera feasibility only; custom AI, HUD, HydraPy and Gorgon are not ported'}
try:
    with (root/'engine.log').open('w') as log:
        process=subprocess.Popen(command,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:start=Path(f'/proc/{process.pid}/stat').read_text().rsplit(')',1)[1].split()[19]
        except (OSError,IndexError):start=None
        (root/'process.json').write_text(json.dumps({'pid':process.pid,'start':start,'command':command},indent=2)+'\n')
        try:code=process.wait(timeout=90)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
            raise RuntimeError('Owned proof timed out; its process group was stopped')
    text=(root/'engine.log').read_text(errors='replace')
    if code!=0:raise RuntimeError(f'Engine exited {code}; inspect engine.log')
    stages=re.findall(r'NULLTOWER_LANDING stage=(\d+) x=([-\d.]+) y=([-\d.]+) z=([-\d.]+)',text)
    if [int(s[0]) for s in stages]!=list(range(6)):raise RuntimeError('The six route waypoints were not reached')
    heights=[float(s[3]) for s in stages]
    if heights!=[160,160,320,320,480,480]:raise RuntimeError(f'Wrong native landing heights: {heights}')
    done=re.search(r'NULLTOWER_DONE x=([-\d.]+) y=([-\d.]+) z=([-\d.]+) ticks=(\d+)',text)
    if not done or float(done[3])!=480:raise RuntimeError('The collision climb did not complete')
    first_camera=text.find('NULLTOWER_CAMERA')
    if first_camera<text.find('NULLTOWER_DONE'):raise RuntimeError('Camera-only placement preceded climb completion')
    for marker in ['pose=2 pitch=45.000000','pose=2 pitch=-45.000000','pose=1 pitch=-45.000000']:
        if marker not in text:raise RuntimeError(f'Missing native camera evidence: {marker}')
    images={};hashes={}
    for name in ['crown-level','crown-down','crown-up','ground-level','ground-up']:
        path=shots/(name+'.png')
        with Image.open(path) as im:
            if im.size!=(1280,800):raise RuntimeError(f'Wrong dimensions: {name}')
            a=np.asarray(im.convert('RGB'))
        if float(a.std())<3 or np.count_nonzero(a)<a.size*.1:raise RuntimeError(f'Blank camera image: {name}')
        images[name]=a;hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    if len(set(hashes.values()))!=5:raise RuntimeError('Camera captures did not change')
    for a,b in [('crown-up','crown-down'),('ground-up','ground-level')]:
        if np.abs(images[a].astype(float)-images[b]).mean()<5:raise RuntimeError(f'Insufficient view change: {a}/{b}')
    report.update(state='passed',landing_heights=heights,climb_ticks=int(done[4]),
                  climb_metres_at_64_units_per_metre=7.5,render_size=[1280,800],
                  renderer=next((l.partition(':')[2].strip() for l in text.splitlines() if l.startswith('GL_RENDERER:')),''),
                  camera_pitch_degrees=[-45,0,45],screenshots=hashes,
                  note='Walk uses forced horizontal velocity with native collision/gravity; camera-only teleports happen afterward. No desktop GPU/audio benchmark.')
except Exception as exc:
    report.update(state='failed',error=str(exc));raise
finally:
    (root/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
