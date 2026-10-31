# Drowned Records - 120-second score

Original written score for the **DROWNED RECORDS** kit.  This folder contains
note data and intent, not rendered audio.  No existing music, sample, motif or
recording is quoted or transcribed.

## Facts

| | |
| --- | --- |
| Tempo | 96 BPM |
| Meter | 4/4, 16 rows per bar, rate 1 |
| Bars / patterns | 48 bars, six 8-bar patterns |
| Rows / ticks | 768 rows / 368,640 ticks |
| Duration | **120.000000 s**, `loop=False` |
| Key | F minor (tracker key 5) |
| Lanes | 1 kick, 2 snare, 3 hat/texture, 4 lead, 5 bass, 6 counterline/atmosphere |

Patterns: `archive-intro`, `first-pressure`, `waterline-rising`,
`drawer-open`, `ink-pressure`, `register-close`.  The three broad acts are
patterns 0-1, 2-3 and 4-5; they are an arrangement description, not a forced
player timeline.

The restrained five-note motif (scale degrees 0-1-4-3-0) is stated in the
intro, fragmented under the waterline, and developed in `ink-pressure` before a
thin close.  Occasional b2 and tritone colour in the lead/counterline provides
the unease; the low bass and broken kick carry the slow pressure.  The score is
deliberately sparse and leaves breath between phrases.

## Reproduce and check

```sh
cd /home/echevarian/dev/shared/deepseek/nullrun-environments-20261031/music/drowned_records
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python score.py
cd ..
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python check_music.py
```

`score.py` rewrites `score.json`.  `check_music.py` validates all three scores
with the supplied `hydrapy.tracker_v3`, checks the exact timeline, six
monophonic lanes, no gate overlaps, MIDI 24..96, rests/dynamics, patch-plan
intent and cross-score distinctness, then writes `checks.json` and
`catalogue.json`.

## Patch plan

`patch-plan.json` is **intent only**.  It proposes one poly PVX for lead and
counterline, one mono PVX bass, a few simple oscillator/noise/envelope/VCA
percussion supports, and an optional clean Spoon Bender return.  It states that
PVX input2 is external AUDIO, not velocity; velocity goes to a VCA.  Gorgon poly
pitch12/gates11/velocity3 are the real bridge outputs.  No firmware emulation,
giant voice bank, GPU/audio/image sampling prerequisite, DC pulse or loaded
patch is present.

## Non-claims

No audio was rendered, auditioned or quality-reviewed here.  Native playback,
Rack mapping, final revoicing, xrun/performance checks and listening acceptance
remain with Codex and Josiah.  The score is original note data, not a claim about
the game's existing music or runtime.
