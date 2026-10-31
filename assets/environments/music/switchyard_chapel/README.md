# Switchyard Chapel - 120-second score

Original written score for the **SWITCHYARD CHAPEL** kit.  This folder contains
note data and intent, not rendered audio.  No existing music, sample, motif or
recording is quoted or transcribed.

## Facts

| | |
| --- | --- |
| Tempo | 128 BPM |
| Meter | 4/4, 16 rows per bar, rate 1 |
| Bars / patterns | 64 bars, eight 8-bar patterns |
| Rows / ticks | 1,024 rows / 491,520 ticks |
| Duration | **120.000000 s**, `loop=False` |
| Key | D minor (tracker key 2) |
| Lanes | 1 kick, 2 snare, 3 hat/texture, 4 lead, 5 bass, 6 counterline/atmosphere |

Patterns: `gate-open`, `relay-drive`, `arc-response`, `breakdown`, `build`,
`peak`, `return`, `close`.  The arrangement is a call in the first third, a
sparse breakdown at pattern 3, a build/peak, and a developed return that
restates the gate figure rather than repeating it verbatim.

The kick uses several precise irregular figures instead of one loop.  The bass
is the strongest syncopated element; the lead answers in a higher register while
the hat lane carries the machinery.  Rests and the breakdown keep it from being
a six-lane wall.

## Reproduce and check

```sh
cd /home/echevarian/dev/shared/deepseek/nullrun-environments-20261031/music/switchyard_chapel
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python score.py
cd ..
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python check_music.py
```

`score.py` rewrites `score.json`.  `check_music.py` validates all three scores
with the supplied `hydrapy.tracker_v3`, checks exact timing, monophony, no gate
overlaps, MIDI 24..96, rests/dynamics, patch-plan intent and cross-score
distinctness, then writes `checks.json` and `catalogue.json`.

## Patch plan

`patch-plan.json` is **intent only**: one poly PVX for lead/counterline, one mono
PVX bass, compact oscillator/noise/envelope/VCA percussion, optional short clean
Spoon Bender.  PVX input2 is external AUDIO, not velocity; velocity goes to a
VCA.  Gorgon poly pitch12/gates11/velocity3 are the real bridge outputs.  No
firmware emulation, giant voice bank, GPU/audio/image sampling prerequisite, DC
pulse or loaded patch is present.

## Non-claims

No audio was rendered, auditioned or quality-reviewed here.  Native playback,
Rack mapping, final revoicing, xrun/performance checks and listening acceptance
remain with Codex and Josiah.  The score is original note data, not a claim about
the game's existing music or runtime.
