# SPDX-License-Identifier: GPL-2.0-or-later
import json,tempfile
from pathlib import Path
import mido
import compile_music as cm
repo=Path(__file__).parent
with tempfile.TemporaryDirectory(dir=repo/'runtime') as temp:
    root=Path(temp);mid=mido.MidiFile(ticks_per_beat=480);tr=mido.MidiTrack();mid.tracks.append(tr)
    tr.extend([mido.MetaMessage('set_tempo',tempo=500000),mido.Message('control_change',control=101,value=0),mido.Message('control_change',control=100,value=0),mido.Message('control_change',control=6,value=12),mido.Message('pitchwheel',pitch=4096),mido.Message('control_change',control=64,value=127),mido.Message('note_on',note=60,velocity=100,time=240),mido.Message('note_off',note=60,time=240),mido.MetaMessage('set_tempo',tempo=1000000),mido.Message('control_change',control=64,value=0,time=480)])
    mid.save(root/'TEST.mid');saved=cm.TRACKS;cm.TRACKS=[('TEST',0,'test','test')]
    doc=cm.compile_music(root,root/'output');cm.TRACKS=saved
    note=json.loads((root/'output/notes.json').read_text())[0]
    assert note['start']==.25 and note['end']==1.5, note
    assert any(e[1]==2 and e[4]==6 for e in doc['events']), 'RPN bend range not applied'
root=repo.parent/'doom-hydrapy-20261030'
doc=json.loads((root/'poly/schedule.json').read_text());notes=json.loads((root/'poly/notes.json').read_text())
ons={e[6]:e for e in doc['events'] if e[1]==1};offs={e[6]:e for e in doc['events'] if e[1]==0}
count=sum(1 for p in ['D_INTRO','D_BUNNY','D_INTER','D_E3M2'] for tr in mido.MidiFile(root/'phase1-lumps'/(p+'.mid')).tracks for m in tr if m.type=='note_on' and m.velocity)
assert len(ons)==len(offs)==len(notes)==count==5857
for n in notes:
    a,b=ons[n['id']],offs[n['id']]
    assert a[0]==n['start'] and b[0]==n['end'] and a[4]==n['note'] and abs(a[5]*127-n['vel'])<1e-9
    assert b[0]<=240
# Check intervals on each physical voice: no stealing, and distinct gate edges possible.
voices={}
for n in sorted(notes,key=lambda n:n['start']):
    key=n['route'],n['voice'];assert voices.get(key,-1)+1/48000<n['start'];voices[key]=n['end']
print('PASS tempo change, sustain, RPN bend range; 5857 source notes preserved exactly; no stolen voices')
