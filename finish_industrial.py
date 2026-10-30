# SPDX-License-Identifier: GPL-2.0-or-later
"""Record explicit final-video review and hash a measured industrial delivery."""
import argparse,hashlib,json,os,subprocess
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('delivery',type=Path)
    p.add_argument('--visual-review',required=True,help='Findings after viewing all four final-video sheets and final frame')
    args=p.parse_args();out=args.delivery
    d=json.loads((out/'completion.json').read_text())
    assert d['video']['fully_decoded'] and d['video']['chapters']==4
    assert d['gate_audit']['dropped_notes']==0
    assert d['demo_tracker_sync']['tic_mismatches']==0
    assert all((out/'review'/f'minute-{i}.png').is_file() for i in range(1,5))
    d['visual_review']=args.visual_review
    repo=Path(__file__).resolve().parent
    d['git_branch']=subprocess.check_output(['git','-C',str(repo),'branch','--show-current'],text=True).strip()
    d['git_commit']=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
    meta=json.loads((out/'ffprobe.json').read_text());d['video']['seconds']=float(meta['format']['duration'])
    def sha(path):
        h=hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        return h.hexdigest()
    d['artifacts']={f.name:dict(bytes=f.stat().st_size,sha256=sha(f)) for f in out.iterdir() if f.suffix in ('.wav','.mp4')}
    (out/'completion.json').write_text(json.dumps(d,indent=2)+'\n')
    g=d['gate_audit'];s=d['av_sync'];v=d['video'];a=d['audio']
    lines=['# Original industrial live take','','Decisions for Josiah: listening review and later hardware calibration remain open. No listening review is claimed.','',
           f"One simultaneous Rack/Studio pass: {v['seconds']:.3f} s, {v['width']}×{v['height']}, {v['fps']} fps, {v['frames']} decoded frames; {a['seconds']:.3f} s stereo WAV.",
           '','## Measured checks','',
           f"- Notes: {g['source_note_ons']} scheduled, {g['emitted_note_ons']} emitted, {g['observed_gate_edges']} physical cable edges; {g['dropped_notes']} dropped. This is cable proof, not acoustic note recognition.",
           f"- Frame holds: {d['held_frames']} ({d['held_percent']:.3f}%). XRUNs: {d['xruns']}; recorded discontinuities: {d['recorded_audio_discontinuities']}.",
           f"- Demo/tracker sync: {d['demo_tracker_sync']['frame_samples']} samples; {d['demo_tracker_sync']['tic_mismatches']} mismatches.",
           f"- Corrected A/V median offset: {s['corrected_median_offset_ms']:.3f} ms; drift {s['corrected_drift_ms']:.3f} ms; residual p95 {s['corrected_residual_p95_ms']:.3f} ms. Marker measurement resolution: 33.333 ms.",
           f"- WAV peak {a['peak']:.6f}, RMS {a['rms']:.6f}. Global gain {a['global_gain_db']:.3f} dB.",
           '- Studio producer counters: '+json.dumps(d['studio_counters_session']),
           '- Studio counters during play (summary-window estimate): '+json.dumps(d['studio_counters_during_play_summary_estimate']),
           '- Prewarm: '+json.dumps(d['prewarm']),'- Final-video inspection: '+args.visual_review,
           '','## Music and instruments','','Four original six-lane tracker-v3 scores; no existing game music used. See mapping.json and INSTRUMENTS.md. PVX is a behavioral approximation inspired by the Polivoks circuit, without measurements from Josiah’s hardware.','']
    for t in d['tracks']:lines.append(f"- {t['start']:.3f}–{t['end']:.3f}s: {t['title']}, {t['notes']} notes; {t['credit']}.")
    lines+=['','DEMO1–4 and melt/disk/vector/anaglyph scenes change at 0, 60, 120 and 180 seconds.','',*('- '+x for x in d['limitations']),'',f"Local code: {d['git_branch']} at {d['git_commit']}. Nothing pushed."]
    (out/'report.md').write_text('\n'.join(lines)+'\n')
    files=sorted(f for f in out.rglob('*') if f.is_file() and f.name!='SHA256SUMS')
    (out/'SHA256SUMS').write_text(''.join(f'{sha(f)}  {f.relative_to(out)}\n' for f in files))
    print('Signed off',len(files),'files')
if __name__=='__main__':main()
