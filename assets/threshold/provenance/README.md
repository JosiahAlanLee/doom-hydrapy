# Threshold — opening floor, art kit and 120-second score

Original, deterministic content for the Null Run Argon build. This is a
**content kit**, not an integrated game build: Codex owns native behavior,
WAD assembly, HUD/font replacement, live testing and rendering. Nothing here
was launched in Doom, rendered to audio/video, or auditioned.

Everything in this folder is GPL-2.0-or-later, model-assisted work directed by
Josiah; see `CREDITS.md`. No existing map, sprite, texture, music or font was
copied or sampled.

## Contents

```
opening.py                  hand-authored Floor generator + 12-seed checks
opening-overview.png/.json  plan, route, things, props and geometry
art.py                      procedural creature/tile/prop generator + checks
art/                        generated atlases, tiles, 2x2 sheets, contacts
score.py                    deterministic Gorgon score generator
score.json                  the 120.000 s six-lane score
check_score.py, score-checks.json
patch-plan.json             low-CPU voice/routing intent (not loaded)
art-checks.json, checks.json, manifest.json
```

## Opening floor

`generate(seed, number=1) -> rogue.maps.Floor`. Put the tested Argon game root
on `PYTHONPATH`; this module imports `Floor` and `inhabitants.options` from it
and does not replace or patch them.

```
PYTHONPATH=/home/echevarian/dev/shared/codex/doom-hydrapy-argon-native \
PYTHONDONTWRITEBYTECODE=1 ~/miniconda3/envs/hydrapy/bin/python opening.py
```

Plan: a foyer, two-tile north gallery, a 13x13 service atrium around the solid
**Dry Stack** landmark, a relay bay and pump hall with two service shafts, a
south return corridor, and an exit vestibule reached across the atrium again.
Genuine loops: the atrium ring; foyer to atrium via two node-disjoint routes;
atrium to works via the east approach or north link; relay/pump via x=25 and
x=29. The side cache off the pump hall is an optional resource detour with
**no native secret tag or trigger**. Max adjacent step 8 units (limit 16); no lifts, jumps,
crouching or timing platforms; every prop cell is off-route and the floor stays
connected with all props removed.

Eight spaced encounters, no boss: husk (84) in the west approach, surveyor (9)
on the atrium south edge, latchwing (69) over the atrium north side, relay
choir (71) at the pump mouth, husk in the relay bay, latchwing on the south
return, relay choir at the cache mouth, surveyor before the exit. Start
clearance is at least 6 Manhattan tiles.

Reserved native types for this experiment: **69 latchwing, class 15** and
**71 relay_choir, class 16**, both flag 7, skill bits 7, `options = 1799 + roll
* 2048`. Existing surveyor/husk use the same signed option space. Props are a
separate metadata list; no native decor type IDs or collision sizes are guessed.

`opening-overview.png` is the readable plan; `.json` has cells, things, props,
routes, loops, sightlines and profile hints. Wall/flat names `NWALL01..06`,
`NFLAT01..04` are generated-asset names and metadata hints only; this kit does
not claim the current writer already supports them.

## Art

`art.py` draws everything from primitives and tileable value noise.

```
PYTHONDONTWRITEBYTECODE=1 ~/miniconda3/envs/hydrapy/bin/python art.py
```

* Creatures: `art/creatures/{latchwing,relay_choir}_{A,B}.png`, 512x768 RGBA,
  four columns x six rows of 128x128. Rows are idle, walk, warning, attack,
  hurt, death; four frames per state. Transparent padding, feet/body anchored,
  visible final corpse. Latchwing is a low cable/moth inspection rig whose wing
  aperture opens across the warning row before a locked-direction dash pose.
  Relay Choir is a stacked duct/ceramic mask frame with a three-spore fan, not
  a door or a skull soldier. Frame timing and native behavior are Codex's.
* Walls: `art/walls/NWALL01..06.png`, 128x128 RGB; flats:
  `art/flats/NFLAT01..04.png`, 64x64 RGB. Every tile has matching wrap edges and
  a `art/sheets/*_2x2.png` preview. Palettes stay in bone/plaster, slate/petrol,
  oxidised metal and amber; no strobe or bloom is baked in.
* Props: `art/props/service_lamp.png`, `cable_shrine.png`, `directory_sign.png`,
  96x128 RGBA with transparent padding. Codex chooses native actors and
  collision.

Contact sheets: `art/contact_creatures.png`, `contact_materials.png`,
`contact_props.png`. `art-checks.json` records geometry, frame-motion,
transparency, seam and 2x2 checks.

## Score

`score.py` writes `score.json`; `check_score.py` validates and writes
`score-checks.json`.

```
PYTHONDONTWRITEBYTECODE=1 ~/miniconda3/envs/hydrapy/bin/python score.py
PYTHONDONTWRITEBYTECODE=1 ~/miniconda3/envs/hydrapy/bin/python check_score.py
```

144 BPM, 4/4, 16 rows/bar, rate 1, nine 8-bar patterns = 72 bars = 1152 rows =
120.000 s, `loop=False`. Three 40-second acts (`threshold-foyer`,
`works-descent`, `return-escape`) are scene markers only; they do not force
player timing. Lanes: kick, snare, hat, riff/lead, bass, ambient/counterline.
All lanes are monophonic with no overlapping gates. Written harmony is D minor
with Eb (Phrygian b2) colour; the lead uses both b2 and b6. Gesture A is the
syncopated 0,3,6,8,11,14 drive; gesture B is a half-time 0,6,10 stomp. The
return restates act 1 material and ends on a D2/D4 downbeat with an eight-row
tail that can loop back to pattern 0, though the delivered chain is finite and
exactly 120 s. No earlier melody or rhythm is quoted or transcribed.

`patch-plan.json` is intent only: two PVX voices (lead/bass), one compact
algorithmic/noise percussion source for lanes 1-3, one restrained Spoon Bender
for the sparse counterline. It asserts no loaded patch, parameter values,
firmware, voice bank, optical source or DC pulse.

## Verification and non-claims

`check_all.py` reruns the suites and writes `checks.json` + `manifest.json`.
Verified here: Python geometry/validator checks, deterministic regeneration,
asset dimensions/anchors/seams, exact score timeline and monophony, file hashes.
**Not verified here:** native Doom gameplay, WAD/texture assembly, sprite
readability in the native palette, enemy behavior/dodging, audio audition,
Rack patch load, or any video render. Codex must supply Departure Mono and the
HUD/layout; this kit contains no font or UI files.
