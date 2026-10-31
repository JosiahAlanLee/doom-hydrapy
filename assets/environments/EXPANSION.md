# Null Run environment expansion - signature mobs and keyed scores

This expansion adds **six original mob designs** and **three original 120-second
scores** to the completed three-kit environment deliverable.  It is art, written
note data and patch intent only: no engine code, actor IDs, native frame mapping,
audio render or audition is included.  Codex owns integration, labels, behavior,
native frame mapping, Rack/audio work and visual/audio acceptance.

## The creepy set

**Drowned Records is the very creepy set.**  Its two signature mobs are built
from absence and found objects rather than gore or a cartoon skull:

- **Shelf Widow** (`shelf_widow`, latchwing slot): an ordinary bowed filing
  shelf that opens into a low, long-limbed negative-space body.  Drawer mouths,
  paper folds and a dark core replace a face.  Warning is a slow separating
  cabinet; attack is the existing locked-direction dash as a low lunge.
- **Redacted Choir** (`redacted_choir`, relay_choir slot): a hunched stack of
  waterlogged registrars and paper-veiled almost-faces with large blank regions.
  Warning is a slow, visible rise of ink pressure behind the paper, with a copper
  pressure gauge; attack opens three wet paper tongues for the existing
  three-projectile fan pose.

`sheets/drowned-records-creepy.png` is a 2x detail board of both A/B variants in
idle, warning, attack and death.  It is original art, not a fabricated game
screenshot.  The full atlas sheet is `sheets/drowned_records-mobs.png`.

## Six identities, two existing behavior families

| Set | latchwing slot (class 15, CYBR) | relay_choir slot (class 16, PAIN) |
| --- | --- | --- |
| Drowned Records | `shelf_widow` / SHELF WIDOW | `redacted_choir` / REDACTED CHOIR |
| Switchyard Chapel | `insulator_widow` / INSULATOR WIDOW | `transformer_cantor` / TRANSFORMER CANTOR |
| After Hours Pavilion | `queue_stalker` / QUEUE STALKER | `usher_cluster` / USHER CLUSTER |

Each identity has two variants (A/B), each a **512x768 RGBA atlas**: 4 columns x
6 rows of 128x128 cells, 24 frames per atlas, 12 atlases and **288 frames** total.
Rows are idle, walk, warning, attack, hurt, death.  Every cell has at least 3 px
transparent padding, a stable floor anchor at y=120, crisp 0/255 alpha, and a
visible final death corpse.  A/B variants differ in shape and detail, not merely
hue.  `encounters.json` is the schema (`nullrun-environment-mobs-1`) and states
the honest limits: six new identities on the **existing** latchwing and
relay_choir families.  No new AI, actor ID, phasing, teleportation, gaze or
mechanic is introduced.

Generation and checks:

```sh
cd /home/echevarian/dev/shared/deepseek/nullrun-environments-20261031
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python mob_art.py --out .
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python mob_checks.py
```

`mob-checks.json` records 14/14 passing structural checks (12 atlases, 288
frames, padding/anchors, final corpses, >=100 changed pixels on every
consecutive frame pair, A/B max silhouette IoU 0.832, cross-design max 0.686,
deterministic regeneration).  These are not visual-acceptance claims.

## Three environment-keyed scores

All scores are original written note data, six monophonic lanes, 4/4, 16 rows
per bar, rate 1, `loop=False`, and exactly **120.000000 seconds**.  They differ in
tempo, key, bar/pattern count, rhythm, contour, density, register and
arrangement; none is a transposition or recolor of another.

| Set | BPM | Bars | Patterns | Ticks | Key | Character |
| --- | --- | --- | --- | --- | --- | --- |
| Drowned Records | 96 | 48 | 6 x 8 | 368,640 | F minor | Sparse broken pulses, long low bass, restrained near-interval motif |
| Switchyard Chapel | 128 | 64 | 8 x 8 | 491,520 | D minor | Driving syncopated electro/FM machinery, irregular percussion, call/response, breakdown and return |
| After Hours Pavilion | 112 | 56 | 7 x 8 | 430,080 | G minor | Off-kilter broken lounge, displaced bell/reed phrase, gentle bass, missing beats, quiet middle |

Each folder `music/<set_id>/` contains `score.py`, `score.json`, `checks.json`,
`patch-plan.json` and `README.md`.  `music/catalogue.json` maps each set to its
score path, BPM, `seconds: 120.0`, bars, patterns, mood and exact SHA256.

Regenerate and validate:

```sh
cd /home/echevarian/dev/shared/deepseek/nullrun-environments-20261031
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python music/drowned_records/score.py
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python music/switchyard_chapel/score.py
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python music/after_hours_pavilion/score.py
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python music/check_music.py
```

`check_music.py` uses the supplied `hydrapy.tracker_v3` validator and an
independent full-chain duration/gate-overlap calculation.  Each per-set
`checks.json` has **21/21 passed**: exact 120.000 s timeline, pattern geometry,
six lane names, no chords, no monophonic gate overlap, MIDI 24..96, sensible
dynamics/rests, score-file match, deterministic build, low-CPU patch-plan intent,
and cross-score distinctness (BPM, bars, patterns, key, density, kick rhythm,
lead contour and lead register).

## Patch plans

The three `patch-plan.json` files are **intent only, not loaded patches**.  They
propose one poly PVX for lead/counterline, one mono PVX bass, a few simple
oscillator/noise/envelope/VCA percussion supports and an optional restrained
clean Spoon Bender.  They state that:

- PVX input2 is **external AUDIO, not velocity**; velocity suggestions go to a VCA.
- Gorgon poly **pitch12/gates11/velocity3** are the real bridge outputs.
- There is no firmware emulation, giant voice bank, GPU/audio/image sampling
  prerequisite, DC pulse or loaded module.
- Parameter ranges are starting suggestions; Codex owns real revoicing.

## Preservation and file map

The completed 45-art kit is untouched: `art.py`, `art/`, `environments.json`,
the original `manifest.json`/`checks.json`, original sheets, README and CREDITS
all remain as the 45-art receipt.  The old `checks.py`/`manifest.json` are a
frozen snapshot for that 45-art tree; because this expansion adds files below
the same folder, a naive rerun of the old manifest check would see a larger set.
`expansion-checks.py` verifies the original 57 hashed files and the 45 art PNGs
are unchanged, and `art.py` still regenerates the original art at seed 20261031.
Expansion files are new:

```
mob_art.py, mob_checks.py, mob-checks.json
mobs/<set_id>/{latchwing,relay_choir}_{A,B}.png   (12 atlases, 288 frames)
encounters.json
sheets/<set_id>-mobs.png, sheets/drowned-records-creepy.png
music/common.py, music/check_music.py, music/catalogue.json
music/<set_id>/{score.py,score.json,checks.json,patch-plan.json,README.md}
EXPANSION.md, expansion-manifest.json, expansion-checks.json
make_expansion_manifest.py
```

`expansion-manifest.json` hashes stable expansion sources, art, scores, patch
plans and docs; it references the original manifest/check receipt and excludes
itself and mutable check outputs.  `expansion-checks.json` verifies the original
45-art hashes remain intact, the 12/288 mob inventory, the three 120-second score
receipts and catalogue hashes, the no-audio/no-firmware boundary, and the
expansion manifest.  Run:

```sh
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python expansion_checks.py
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python make_expansion_manifest.py
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python expansion_checks.py
```


## Credits and license

Directed by **Josiah Alan-Lee**.  Model-assisted procedural mob art, score code
and written note data by **DeepSeek**.  Native integration, behavior mapping,
Rack/audio work and final review by **Codex**.  This expansion is
**GPL-2.0-or-later**; the original `CREDITS.md` and source notices remain in
force.  No existing game pixel, sample, recording or music is copied.

## Honest limitations

- **Not rendered and not auditioned.** No asset was rendered in the native game; no score
  was auditioned as audio. Native/audio acceptance is pending Codex/Josiah.
- **No native game, sprite-palette or frame-mapping acceptance.**  The 128 px
  atlases have not been quantised to the game palette or rendered in Doom/Null
  Run.  Warning/attack readability was reviewed on contact sheets only.
- **No audio rendered or auditioned.**  There is no WAV/MP3/OGG, sample, Rack
  patch, synth render or loudness/xrun result.  Patch plans are text intent.
- The six identities deliberately reuse two proven behavior families.  They do
  not add AI, actor IDs, phasing, teleportation, gaze detection or new mechanics.
- Numeric checks prove structure and separation, not artistic quality or fun.
- Codex owns behavior labels, native frame mapping, collision, performance,
  Rack implementation, audio review and PR publication.
