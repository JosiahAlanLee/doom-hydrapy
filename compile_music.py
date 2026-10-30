# SPDX-License-Identifier: GPL-2.0-or-later
"""Lossless note/tempo compiler for the official Freedoom MIDI lumps.
No quantization, note reduction, or stems. One schedule feeds all Rack voices.
"""
import collections, heapq, json, math
from pathlib import Path
import mido
TRACKS=[('D_INTRO',0.,'Fight for Freedom','Korp, based on Fountain Dance by Tyler "Picklehammer" Pantella'),('D_BUNNY',7.,'Impactean Welcome Party','Goji'),('D_INTER',70.,'YOU LIVE!!!!','Stratos'),('D_E3M2',145.,'The Long Road','Lola "BlueWorrior" Harvey')]

def drum_family(n):
    if n in (35,36):return 0
    if n in (38,40):return 1
    if n in (42,44,46):return 2
    if n in (41,43,45,47,48,50):return 3
    if n in (49,51,52,55,57,59):return 4
    if n in (56,53):return 5
    if n in (37,39,54,60,61,62,63,64,75,76,77):return 6
    return 7

def compile_music(lumps, output):
    output=Path(output);output.mkdir(exist_ok=True,parents=True)
    notes=[]; controls=[];tracks=[];source_on=source_off=orphan_off=0;serial=0
    for lump,offset,title,credit in TRACKS:
        mid=mido.MidiFile(Path(lumps)/(lump+'.mid'));now=offset;program=[0]*16;sustain=[False]*16;bend_range=[2]*16;rpn_msb=[127]*16;rpn_lsb=[127]*16
        active=collections.defaultdict(collections.deque);deferred=collections.defaultdict(list);tracknotes=[];unknown=collections.Counter()
        # Reset channel controllers for each composition.
        for ch in range(16):
            for cc,val in [(7,100),(11,127),(10,64)]: controls.append([offset,'cc',ch,cc,val])
            controls.append([offset,'bend',ch,0,2])
        for msg in mid: # mido integrates every tempo change into seconds
            now+=msg.time
            if msg.type=='program_change':program[msg.channel]=msg.program
            elif msg.type=='control_change':
                ch=msg.channel
                if msg.control==64:
                    sustain[ch]=msg.value>=64
                    if not sustain[ch]:
                        for n in deferred[ch]:n['end']=now
                        deferred[ch].clear()
                elif msg.control==101:rpn_msb[ch]=msg.value
                elif msg.control==100:rpn_lsb[ch]=msg.value
                elif msg.control==6 and rpn_msb[ch]==0 and rpn_lsb[ch]==0:bend_range[ch]=msg.value
                elif msg.control in (1,7,10,11): controls.append([now,'cc',ch,msg.control,msg.value])
                else: unknown[msg.control]+=1
            elif msg.type=='pitchwheel':controls.append([now,'bend',msg.channel,msg.pitch/8192*bend_range[msg.channel],2])
            elif msg.type=='note_on' and msg.velocity:
                serial+=1;source_on+=1
                n=dict(id=serial,start=now,end=None,ch=msg.channel,note=msg.note,vel=msg.velocity,program=program[msg.channel],track=lump)
                active[msg.channel,msg.note].append(n);tracknotes.append(n)
            elif msg.type in ('note_off','note_on'):
                k=(msg.channel,msg.note)
                if not active[k]:orphan_off+=1;continue
                source_off+=1
                n=active[k].popleft()
                if sustain[msg.channel] and msg.channel!=9:deferred[msg.channel].append(n)
                else:n['end']=now
        if any(active.values()):raise ValueError('unreleased MIDI notes: '+lump)
        for pending in deferred.values():
            for n in pending:n['end']=now
        for n in tracknotes:
            if n['end'] is None: raise ValueError('unclosed sustain')
            if n['end']<=n['start']:n['end']=n['start']+1/48000
        notes+=tracknotes
        tracks.append(dict(lump=lump,title=title,credit=credit,start=offset,end=now,notes=len(tracknotes),other_cc=dict(unknown)))
    # Melodic routes retain channel identity. Drums split into eight substitute timbres.
    keys=sorted(set(('drum',drum_family(n['note'])) if n['ch']==9 else ('melody',n['ch']) for n in notes))
    routes=[];events=[];mapping={}
    for key in keys:
        ns=sorted([n for n in notes if (('drum',drum_family(n['note'])) if n['ch']==9 else ('melody',n['ch']))==key],key=lambda n:(n['start'],n['id']))
        limit=16 if key[0]=='drum' else 8
        free=[];voice_end=[]
        for n in ns:
            # Reserve 2 samples after off, so back-to-back notes produce real gate edges.
            slot=next((i for i,end in enumerate(voice_end) if end+2/48000<=n['start']),len(voice_end))
            if slot==len(voice_end):voice_end.append(n['end'])
            else:voice_end[slot]=n['end']
            n['bank']=slot//limit;n['voice']=slot%limit
        for bank in range(math.ceil(len(voice_end)/limit)):
            subset=[n for n in ns if n['bank']==bank];idx=len(routes)
            inst='OtisSampler' if key[0]=='drum' else 'CZish' if key[1]%3==0 else 'Vastish'
            route=dict(index=idx,kind=key[0],channel=9 if key[0]=='drum' else key[1],family=key[1] if key[0]=='drum' else None,bank=bank,voices=max(n['voice'] for n in subset)+1,instrument=inst,notes=len(subset),programs=sorted(set(n['program'] for n in subset)),midi_notes=sorted(set(n['note'] for n in subset)))
            routes.append(route)
            for n in subset:
                n['route']=idx
                events.append([n['start'],1,idx,n['voice'],n['note'],n['vel']/127,n['id']])
                events.append([n['end'],0,idx,n['voice'],0,0,n['id']])
    for t,kind,ch,a,b in controls:
        for r in routes:
            if r['channel']==ch:events.append([t,2 if kind=='bend' else 3,r['index'],int(a) if kind=='cc' else 0,b if kind=='cc' else a,0,0])
    events.sort(key=lambda e:(e[0],{0:0,2:1,3:1,1:2}[e[1]],e[6]))
    assert sum(e[1]==1 for e in events)==source_on==source_off
    doc=dict(schema=1,tracks=tracks,routes=routes,events=events,source_notes=source_on,orphan_noteoffs=orphan_off,duration=240,bpm=120,ppqn=32)
    (output/'schedule.json').write_text(json.dumps(doc,separators=(',',':'))+'\n')
    (output/'notes.json').write_text(json.dumps(notes,separators=(',',':'))+'\n')
    (output/'mapping.json').write_text(json.dumps({k:v for k,v in doc.items() if k!='events'},indent=2)+'\n')
    print('Compiled',source_on,'notes;',len(routes),'polyphonic instruments;',len(events),'events')
    return doc
if __name__=='__main__':
    import sys
    compile_music(sys.argv[1],sys.argv[2])
