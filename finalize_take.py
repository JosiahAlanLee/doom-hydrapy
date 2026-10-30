# SPDX-License-Identifier: GPL-2.0-or-later
"""Verify and package one simultaneous live Rack/Studio capture."""
from pathlib import Path
import hashlib,json,subprocess,sys,shutil,os
import numpy as np
import soundfile as sf
from analyze_sync import sync
REPO=Path(__file__).resolve().parent;ROOT=Path(os.environ.get('DOOM_TAKE_ROOT',str(REPO.parent/'doom-hydrapy-20261030')));CAP=ROOT/'poly-capture';OUT=Path(os.environ.get('DOOM_DELIVERY_DIR',str(ROOT/'take')));OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT.parent/'gorgon-r3b-20261030/runtime'))
from hydrapy.recording import fit,load,offset

def run(cmd):return subprocess.run(cmd,check=True,capture_output=True,text=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    capture=json.loads((CAP/'capture.json').read_text());mapping=json.loads((ROOT/'poly/mapping.json').read_text())
    a=np.fromfile(ROOT/'poly-gate-proof.bin',dtype='<f8');proof=a[8:].reshape(-1,8);scheduled=mapping['source_notes']
    assert int(a[3])==int(a[4])==int(a[5])==scheduled, a[:8]
    assert np.all(proof[:,2]>=0) and np.all(proof[:,7]>0)
    expected=json.loads((ROOT/'poly/notes.json').read_text())
    for n in expected:
        p=proof[n['id']-1];assert p[4]==n['route'] and p[5]==n['voice'] and p[6]==n['note'] and abs(p[7]*127-n['vel'])<1e-9
    gate=dict(source_note_ons=scheduled,emitted_note_ons=int(a[3]),note_offs=int(a[4]),observed_gate_edges=int(a[5]),dropped_notes=0,per_route=[dict(route=r['index'],channel=r['channel']+1,instrument=r['instrument'],voices=r['voices'],notes=r['notes'],observed=int(np.sum((proof[:,4]==r['index'])&(proof[:,2]>=0)))) for r in mapping['routes']],gate_loopback_delay_us=float(np.median(proof[:,2]-proof[:,1])*1e6))
    stamps=load(next((CAP/'studio/.hydrapy/exports').glob('*.timestamps.json')))
    clock=fit(stamps);audio_clock=np.load(CAP/'capture-clock.npz');clock_offset=offset(stamps,audio_start_frame=audio_clock['jack_frames'][0])
    av=sync(CAP);(OUT/'av-sync.json').write_text(json.dumps(av,indent=2)+'\n')
    # Fit an offset using the optical/audio pulses. Their sampling is one video frame.
    # Correct only the measured sample-clock rate mismatch; no musical time-grid changes.
    rate=int(round(48000*(1+clock['drift_ppm']/1e6)));factor=rate/48000
    pairs=np.array(av['pairs']);audio_shift=float(np.median(pairs[:,1]-pairs[:,0]*factor))
    raw,sr=sf.read(CAP/'capture.wav',dtype='float32',always_2d=True)
    mix=raw[:,:2];peak=float(np.max(abs(mix)));assert peak>1e-4
    gain=10**(-1/20)/peak
    sf.write(OUT/'rack-mix-unaligned.wav',mix,sr,subtype='FLOAT')
    del raw,mix
    filters=[f'atrim=start={audio_shift:.9f}','asetpts=PTS-STARTPTS'] if audio_shift>=0 else [f'adelay={-audio_shift*1000:.6f}:all=1']
    filters+=[f'asetrate={rate}','aresample=48000',f'volume={gain:.9f}','apad','atrim=duration=240']
    label='industrial' if os.environ.get('DOOM_INDUSTRIAL')=='1' else 'poly'
    wav=OUT/f'doom-freedoom-{label}-1080p.wav';video=OUT/f'doom-freedoom-{label}-1080p.mp4'
    run(['ffmpeg','-v','error','-y','-i',str(OUT/'rack-mix-unaligned.wav'),'-af',','.join(filters),'-c:a','pcm_s24le',str(wav)])
    (OUT/'rack-mix-unaligned.wav').unlink() # created only by this packaging run
    chapters=OUT/'chapters.ffmeta';chapters.write_text(';FFMETADATA1\n'+''.join(f'[CHAPTER]\nTIMEBASE=1/1000\nSTART={i*60000}\nEND={(i+1)*60000}\ntitle={title}\n' for i,title in enumerate(['Terminal','Halftone print','Rutt Etra scan','Feedback'])))
    run(['ffmpeg','-v','error','-y','-i',str(CAP/'studio.mp4'),'-i',str(wav),'-i',str(chapters),'-map','0:v:0','-map','1:a:0','-map_metadata','2','-map_chapters','2','-c:v','copy','-c:a','aac','-b:a','256k','-t','240','-movflags','+faststart',str(video)])
    run(['ffmpeg','-v','error','-i',str(video),'-f','null','-'])
    meta=json.loads(run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-show_chapters','-of','json',str(video)]).stdout)
    rows=[json.loads(s) for s in (ROOT/'poly-frame-trace.jsonl').read_text().splitlines() if s.strip()]
    trace=[r for r in rows if capture['play_monotonic']<=r['wall']<=capture['stop_monotonic']]
    mismatches=[r for r in trace if r.get('tic')!=r.get('expected')];assert not mismatches
    diag=[json.loads(s) for s in (CAP/'studio/.hydrapy/stress.jsonl').read_text().splitlines() if s.strip()]
    summaries=[d for d in diag if d.get('kind')=='summary'];before=[d for d in summaries if d['monotonic']<=capture['play_monotonic']];during=[d for d in summaries if capture['play_monotonic']<=d['monotonic']<=capture['stop_monotonic']]
    counters=summaries[-1]['counters'];base=before[-1]['counters'] if before else {k:0 for k in counters}
    end=during[-1]['counters'] if during else counters
    approx={k:end[k]-base[k] for k in counters}
    held=int(np.sum(np.diff(np.asarray(stamps['present'][:7200]))==0))
    residual=(pairs[:,1]-audio_shift)/factor-pairs[:,0];slope,intercept=np.polyfit(pairs[:,0],residual,1)
    av.update(applied_audio_trim_seconds=audio_shift,applied_capture_rate=rate,output_rate=48000,measured_jack_clock=clock,clock_timestamp_offset_seconds=clock_offset,corrected_median_offset_ms=float(np.median(residual)*1000),corrected_drift_ms=float(slope*(pairs[-1,0]-pairs[0,0])*1000),corrected_residual_p95_ms=float(np.percentile(abs(residual),95)*1000),method='Paired 1 Hz optical square/audio gate; rate from JACK/video timestamps; constant trim plus fractional sample-clock rate correction; 33.333 ms video resolution.')
    (OUT/'av-sync.json').write_text(json.dumps(av,indent=2)+'\n')
    audio,sr=sf.read(wav,dtype='float32');audio_metrics=dict(sample_rate=sr,channels=2,seconds=len(audio)/sr,peak=float(np.max(abs(audio))),rms=float(np.sqrt(np.mean(audio**2))),global_gain_db=float(20*np.log10(gain)),native_live_rate=48000)
    demos=[dict(start=0,end=7,wad='freedoom1.wad',lump='DEMO1',map='E1M6'),dict(start=7,end=70,wad='freedoom2.wad',lump='DEMO2',map='MAP10'),dict(start=70,end=145,wad='freedoom1.wad',lump='DEMO3',map='E3M9'),dict(start=145,end=240,wad='freedoom2.wad',lump='DEMO4',map='MAP23')]
    if os.environ.get('DOOM_INDUSTRIAL')=='1':
        for i,demo in enumerate(demos):demo.update(start=i*60,end=(i+1)*60)
    report=dict(outcome='done',simultaneous_live_capture=True,stem_passes=False,note_reduction=False,seconds=240,video=dict(width=1920,height=1080,fps=30,frames=int(meta['streams'][0]['nb_read_frames']),fully_decoded=True,chapters=len(meta['chapters'])),audio=audio_metrics,gate_audit=gate,demos=demos,tracks=mapping['tracks'],prewarm=capture['prewarm'],held_frames=held,held_percent=held/7200*100,xruns=capture['xruns_in_take'],recorded_audio_discontinuities=capture['discontinuities_in_take'],studio_counters_session=counters,studio_counters_during_play_summary_estimate=approx,demo_tracker_sync=dict(frame_samples=len(trace),tic_mismatches=0,max_tic_error=0,tics_per_second=35,origin='Gorgon tracker beat / 2'),av_sync={k:v for k,v in av.items() if k!='pairs'},visual_review='PENDING: inspect review sheets extracted from this final MP4 before delivery.',limitations=['Synth timbres are documented substitutions, not General MIDI replicas.','Gate audit verifies physical cable edges and capacity, not acoustic note recognition.','Source-producer counters are separated from the recorded JACK mix; counters during Play use summary-window estimates.','Music finishes at 226.600 s, followed by effect decay and a quiet game-only tail.','Studio keyboard and game-event signals remain future work.'])
    if os.environ.get('DOOM_INDUSTRIAL')=='1':
        report['limitations']=[x for x in report['limitations'] if 'Music finishes' not in x]
        report['limitations'].append('Original tracker-v3 scores evaluated deterministically into the polyphonic live stream; tracker audio lanes muted.')
    for name in ['INSTRUMENTS.md','inventory.json','mapping.json']:
        shutil.copy2(ROOT/'poly'/name,OUT/name)
    shutil.copy2(ROOT/'provenance.json',OUT/'provenance.json')
    (OUT/'gate-audit.json').write_text(json.dumps(gate,indent=2)+'\n')
    (OUT/'completion.json').write_text(json.dumps(report,indent=2)+'\n')
    (OUT/'ffprobe.json').write_text(json.dumps(meta,indent=2)+'\n')
    (OUT/'review').mkdir(exist_ok=True)
    for i in range(4):
        # Eight evenly spaced frames from each minute of the FINAL muxed artifact.
        run(['ffmpeg','-v','error','-y','-ss',str(i*60),'-i',str(video),'-vf',"select='eq(n,60)+eq(n,300)+eq(n,540)+eq(n,780)+eq(n,1020)+eq(n,1260)+eq(n,1500)+eq(n,1740)',scale=480:270,tile=4x2",'-frames:v','1',str(OUT/'review'/f'minute-{i+1}.png')])
    print(json.dumps({k:report[k] for k in ['held_frames','held_percent','xruns','recorded_audio_discontinuities','studio_counters_session','studio_counters_during_play_summary_estimate','demo_tracker_sync','av_sync']},indent=2))
if __name__=='__main__':main()
