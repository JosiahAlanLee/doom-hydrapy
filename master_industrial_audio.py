# SPDX-License-Identifier: GPL-2.0-or-later
"""Master the captured stereo pair, preserving the already-reviewed video packets."""
from pathlib import Path
import hashlib,json,subprocess,tempfile
import numpy as np
import soundfile as sf
REPO=Path(__file__).resolve().parent
ROOT=REPO.parent/'doom-hydrapy-20261030/industrial-run'
OUT=REPO.parent/'doom-hydrapy-20261030/take-industrial'

def run(cmd):return subprocess.run(cmd,check=True,capture_output=True,text=True)
def video_hash(path):return run(['ffmpeg','-v','error','-i',str(path),'-map','0:v:0','-c:v','copy','-f','hash','-hash','sha256','-']).stdout.strip()
def main():
    report=json.loads((OUT/'completion.json').read_text());av=report['av_sync'];duration=report['seconds']
    wav=OUT/'doom-freedoom-industrial-1080p.wav';video=OUT/'doom-freedoom-industrial-1080p.mp4'
    assert av['applied_audio_trim_seconds']<=0,'Opening music must be preserved'
    before=video_hash(video)
    with tempfile.TemporaryDirectory(prefix='master-',dir=ROOT/'tmp') as temp:
        temp=Path(temp);raw,sr=sf.read(ROOT/'poly-capture/capture.wav',dtype='float32',always_2d=True)
        native=temp/'native-stereo.wav';sf.write(native,raw[:,:2],sr,subtype='FLOAT');del raw
        filters=[]
        if av['applied_audio_trim_seconds']<0:filters.append(f"adelay={-av['applied_audio_trim_seconds']*1000:.6f}:all=1")
        filters += [f"asetrate={av['applied_capture_rate']}",'aresample=48000','highpass=f=5:p=2','apad',f'atrim=duration={duration}']
        corrected=temp/'corrected.wav'
        run(['ffmpeg','-v','error','-y','-i',str(native),'-af',','.join(filters),'-c:a','pcm_f32le',str(corrected)])
        x,sr=sf.read(corrected,dtype='float32',always_2d=True);peak=float(abs(x).max());assert peak>1e-5 and np.isfinite(x).all()
        gain=10**(-1/20)/peak;del x
        mastered=temp/'master.wav';run(['ffmpeg','-v','error','-y','-i',str(corrected),'-af',f'volume={gain:.12f}','-c:a','pcm_s24le',str(mastered)])
        mux=temp/'master.mp4';run(['ffmpeg','-v','error','-y','-i',str(video),'-i',str(mastered),'-map','0:v:0','-map','1:a:0','-map_metadata','0','-map_chapters','0','-c:v','copy','-c:a','aac','-b:a','256k','-t',str(duration),'-movflags','+faststart',str(mux)])
        after=video_hash(mux);assert before==after,'Video packet stream changed during audio remux'
        run(['ffmpeg','-v','error','-i',str(mux),'-f','null','-'])
        meta=json.loads(run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-show_chapters','-of','json',str(mux)]).stdout)
        x,sr=sf.read(mastered,dtype='float32',always_2d=True)
        integrity=dict(finite=bool(np.isfinite(x).all()),mean=x.mean(axis=0).tolist(),first_sample=x[0].tolist(),last_sample=x[-1].tolist(),last_50ms_rms=float(np.sqrt(np.mean(x[-int(.05*sr):]**2))),last_1s_rms=float(np.sqrt(np.mean(x[-sr:]**2))),frames=len(x),sample_rate=sr)
        assert integrity['finite'] and float(abs(x).max())<.9
        report['audio'].update(peak=float(abs(x).max()),rms=float(np.sqrt(np.mean(x*x))),global_gain_db=float(20*np.log10(gain)),mastering='5 Hz two-pole DC block; peak normalization measured after rate correction/filtering',dc_mean=integrity['mean'])
        mastering=dict(filters=filters,peak_before_final_gain=peak,gain=gain,gain_db=float(20*np.log10(gain)),target_peak_dbfs=-1,video_packet_hash_before=before,video_packet_hash_after=after,video_packets_unchanged=True)
        mastered.replace(wav);mux.replace(video)
    (OUT/'completion.json').write_text(json.dumps(report,indent=2)+'\n')
    (OUT/'audio-integrity.json').write_text(json.dumps(integrity,indent=2)+'\n')
    (OUT/'audio-mastering.json').write_text(json.dumps(mastering,indent=2)+'\n')
    (OUT/'ffprobe.json').write_text(json.dumps(meta,indent=2)+'\n')
    # Re-extract from the actual final MP4, even though compressed video packets match.
    for i in range(4):run(['ffmpeg','-v','error','-y','-ss',str(i*60),'-i',str(video),'-vf',"select='eq(n,60)+eq(n,300)+eq(n,540)+eq(n,780)+eq(n,1020)+eq(n,1260)+eq(n,1500)+eq(n,1740)',scale=480:270,tile=4x2",'-frames:v','1',str(OUT/'review'/f'minute-{i+1}.png')])
    run(['ffmpeg','-v','error','-y','-ss',str(duration-.2),'-i',str(video),'-frames:v','1',str(OUT/'review/final-frame.png')])
    print(json.dumps(dict(audio=report['audio'],integrity=integrity,video_packets_unchanged=True),indent=2))
if __name__=='__main__':main()
