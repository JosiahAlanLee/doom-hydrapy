# SPDX-License-Identifier: GPL-2.0-or-later
"""Compile tracker-v3's evaluated events, preserving conditions and repeats."""
import json, math, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'gorgon-r3b-20261030/runtime'))
from hydrapy.tracker_v3 import validate, Timeline, evaluate, TICKS
from hydrapy.studio_tracker import note_midi

def drum_family(note):
    for family,pitches in enumerate([(35,36),(38,40),(42,44,46),(41,43,45,47,48,50),(49,51,52,55,57,59),(56,53),(37,39,54,60,61,62,63,64,75,76,77)]):
        if note in pitches:return family
    return 7

def compile_scores(paths, output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    notes=[];tracks=[];offset=0
    for path in paths:
        score=json.loads(Path(path).read_text());validate(score)
        timeline=Timeline(score);scale=60/score['bpm']/TICKS
        duration=timeline.cycle*scale
        if not math.isclose(duration,60,abs_tol=.001):
            raise ValueError(f'{path}: {duration}s; one-minute compositions required')
        events=evaluate(score,{'tick':0},0,timeline.cycle)
        start=len(notes)
        for e in events:
            if not e['fires']:continue
            if e.get('locks'):raise ValueError('Unmapped per-note locks; map them before performing')
            notes.append(dict(id=len(notes)+1,start=offset+e['at']*scale,end=offset+(e['at']+e['duration'])*scale,
                              ch=e['lane'],note=note_midi(e['note']),vel=e['vel'],track=Path(path).stem))
        tracks.append(dict(title=Path(path).stem,bpm=score['bpm'],credit='Original composition by DeepSeek; reviewed by Codex',
                           start=offset,end=offset+duration,notes=len(notes)-start,source=str(path)))
        offset+=duration
    routes=[];events=[]
    for lane in range(6):
        if not any(n['ch']==lane for n in notes):raise ValueError(f'Empty lane {lane}')
    keys=sorted({(n['ch'],drum_family(n['note']) if n['ch']>=4 else -1) for n in notes})
    for lane,family in keys:
        inst=['PVX','PVX','CZish','Vastish','OtisSampler','OtisSampler'][lane]
        ns=sorted((n for n in notes if n['ch']==lane and (lane<4 or drum_family(n['note'])==family)),key=lambda n:(n['start'],n['id']))
        ends=[]
        for n in ns:
            slot=next((i for i,end in enumerate(ends) if end+2/48000<=n['start']),len(ends))
            if slot==len(ends):ends.append(n['end'])
            else:ends[slot]=n['end']
            n['slot']=slot
        limit=16 if inst=='OtisSampler' else 8
        for bank in range(math.ceil(len(ends)/limit)):
            subset=[n for n in ns if n['slot']//limit==bank];idx=len(routes)
            routes.append(dict(index=idx,channel=lane,kind='drum' if lane>=4 else 'melody',family=family if lane>=4 else None,
                               bank=bank,voices=max(n['slot']%limit for n in subset)+1,instrument=inst,notes=len(subset)))
            for n in subset:
                n.update(route=idx,voice=n['slot']%limit)
                events.extend([[n['start'],1,idx,n['voice'],n['note'],n['vel']/127,n['id']],
                               [n['end'],0,idx,n['voice'],0,0,n['id']]])
    if len(routes)>32:raise ValueError('Stream capacity exceeded')
    events.sort(key=lambda e:(e[0],e[1],e[6]))
    doc=dict(schema=1,tracks=tracks,routes=routes,events=events,source_notes=len(notes),duration=offset,bpm=120,ppqn=32)
    for name,data in [('schedule',doc),('mapping',{k:v for k,v in doc.items() if k!='events'}),('notes',notes)]:
        (output/f'{name}.json').write_text(json.dumps(data,indent=2)+'\n')
    return doc
if __name__=='__main__':
    d=compile_scores(sys.argv[2:],sys.argv[1]);print('Compiled',d['source_notes'],'notes across',len(d['routes']),'routes;',d['duration'],'seconds')
