# SPDX-License-Identifier: GPL-2.0-or-later
import copy,json,tempfile,unittest
from pathlib import Path
from industrial_music import compile_scores
from hydrapy.tracker_v3 import empty_pattern
ROOT=Path(__file__).resolve().parent.parent
class CompileTests(unittest.TestCase):
    def score(self):
        d=json.loads((ROOT/'gorgon-r3b-20261030/score.json').read_text())
        p=empty_pattern(0);p.update(bar=16,bars=4)
        for lane in p['lanes']:
            lane['cells'][0]={'note':'C3','vel':100,'len':8}
            lane['cells'][1]={'note':'D3','vel':80,'len':8}
        d.update(bpm=64,loop=False,pattern=0,chain=[0]*4,patterns=[p]+[None]*127,mutes=[False]*6)
        # 4 repetitions *16 quarter notes /64 BPM =60 seconds.
        return d
    def test_evaluated_repeats_overlap_and_conditions(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'doom-hydrapy/runtime') as tmp:
            path=Path(tmp)/'score.json';score=self.score()
            score['patterns'][0]['lanes'][0]['cells'][1]['cond']={'kind':'first'}
            path.write_text(json.dumps(score));d=compile_scores([path]*4,Path(tmp)/'compiled')
            self.assertEqual(d['duration'],240)
            self.assertEqual(d['source_notes'],180)
            self.assertEqual(sum(e[1]==1 for e in d['events']),180)
            self.assertEqual(sum(e[1]==0 for e in d['events']),180)
            self.assertTrue(all(r['voices']==2 for r in d['routes']))
            self.assertEqual([t['start'] for t in d['tracks']],[0,60,120,180])
    def test_stutters_and_drum_families(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'doom-hydrapy/runtime') as tmp:
            path=Path(tmp)/'score.json';score=self.score()
            score['patterns'][0]['lanes'][1]['transforms']=[{'kind':'ply','n':2}]
            drums=score['patterns'][0]['lanes'][4]['cells']
            drums[0]['note']='C2';drums[1]['note']='D2'
            path.write_text(json.dumps(score));d=compile_scores([path],Path(tmp)/'compiled')
            self.assertEqual(d['source_notes'],56)
            self.assertEqual({r['family'] for r in d['routes'] if r['channel']==4},{0,1})
    def test_reject_wrong_duration(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'doom-hydrapy/runtime') as tmp:
            path=Path(tmp)/'score.json';score=self.score();score['bpm']=120
            path.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError,'one-minute'):compile_scores([path],Path(tmp)/'compiled')
if __name__=='__main__':unittest.main()
