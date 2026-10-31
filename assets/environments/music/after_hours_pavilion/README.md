# After Hours Pavilion - 120-second score

Original written score for the **AFTER HOURS PAVILION** kit.  This folder
contains note data and intent, not rendered audio.  No existing music, sample,
motif or recording is quoted or transcribed.

## Facts

| | |
| --- | --- |
| Tempo | 112 BPM |
| Meter | 4/4, 16 rows per bar, rate 1 |
| Bars / patterns | 56 bars, seven 8-bar patterns |
| Rows / ticks | 896 rows / 430,080 ticks |
| Duration | **120.000000 s**, `loop=False` |
| Key | G minor (tracker key 7) |
| Lanes | 1 kick, 2 snare, 3 hat/texture, 4 lead, 5 bass, 6 counterline/atmosphere |

Patterns: `concourse`, `queue-drift`, `quiet-a`, `quiet-b`, `return`, `late`,
`close`.  Patterns 2-3 are the deliberately quiet middle: no hat bed, no
backbeat grid and much lower event density.  The lead is a displaced bell/reed
phrase that enters off the expected beat; the bass is gentle and mechanical.
Kick and snare omit downbeats that the listener expects, giving the concourse
its off-kilter walk.

## Reproduce and check

```sh
cd /home/echevarian/dev/shared/deepseek/nullrun-environments-20261031/music/after_hours_pavilion
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python score.py
cd ..
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python check_music.py
```

`score.py` rewrites `score.json`.  `check_music.py` validates all three scores
with the supplied `hydrapy.tracker_v3`, checks exact timing, monophony, no gate
overlaps, MIDI 24..96, rests/dynamics, patch-plan intent and cross-score
distinctness, then writes `checks.json` and `catalogue.json`.

## Patch plan

`patch-plan.json` is **intent only**: one poly PVX for the bell/reed lead and
counterline, one gentle mono PVX bass, soft oscillator/noise/envelope/VCA
percussion, optional small dark Spoon Bender.  PVX input2 is external AUDIO, not
velocity; velocity goes to a VCA.  Gorgon poly pitch12/gates11/velocity3 are the
real bridge outputs.  No firmware emulation, giant voice bank, GPU/audio/image
sampling prerequisite, DC pulse or loaded patch is present.

## Non-claims

No audio was rendered, auditioned or quality-reviewed here.  Native playback,
Rack mapping, final revoicing, xrun/performance checks and listening acceptance
remain with Codex and Josiah.  The score is original note data, not a claim about
the game's existing music or runtime.
