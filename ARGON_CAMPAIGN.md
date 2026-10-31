# Native Argon campaign

The native player now starts a seven-tier campaign in RAW view, with two book demons per tier. See [SEVEN_TIERS.md](SEVEN_TIERS.md) for their allocation and the four shared encounter families. It focuses its own window and starts when that window has focus. Losing focus pauses play. Enter or left click resumes and captures the mouse; Escape releases it and pauses. R retries the current seed; N builds a new seed. WASD moves, the mouse or arrows/Q/E turn, left click/Space/Ctrl fires, right click/F uses, Shift runs, Tab opens the map and 1–7 selects weapons. Brackets adjust and save mouse sensitivity.

The campaign window exposes no encounter-study or visual-treatment selectors. Internal study maps and the browser preview remain available for development. A loopback test controller cannot interrupt an active physical player, and the campaign rejects study mode changes before releasing controls. Closing the native window writes `NULLRUN_ROOT/quit.request` so an owning supervisor can shut down its audio as well.

## Four Argon families

| Family | Native encounter |
| --- | --- |
| Surveyor | One-second warning locks the aim; sidestep before its line shot. |
| Wire Shambler / Ballast Husk | Short electrical warning; leave range or break line of sight before the arc. |
| Threshold Mimic | A stationary false door awakens nearby and warns before a close bite. Back away; it never chases. |
| Vore Spindle | Low-hanging creature launches a native collision-tested spore. Steering is bounded and the projectile expires after five seconds. |

All four take ordinary weapon damage, count as kills and leave corpses. They use signed map options scoped to campaign mode, private per-actor definitions, native sight/collision and the 35 Hz game simulation. Unmarked monsters retain their original behavior. These are adaptations of Argon's designs, with intentionally bounded attacks; they do not implement every proposed mechanic from the original Python sketch.

Each family has two deterministic art variants and 24 frames covering idle, walk, warning, attack, hurt and death. The Mimic's normal pose stays stationary. Atlas pixels come from the reviewed procedural art bank; they are converted into the supplied IWAD palette at map build time. These are front-facing sprite views, not a set of eight directional rotations. Original Argon input, the art renderer, GPL license, atlas hashes and attribution are in `assets/argon/`.

The first tier includes Surveyor and Husk; the second introduces Mimic and Spindle. Later tiers combine them, with all four on tiers five through seven. They replace part of the existing encounter budget and retain the protected starting area. Existing Gloamwood creatures and weapons remain.

## Small ambient Rack accompaniment

`rogue/campaign_live.py` is a HydraPy Studio patch for this native campaign. Set `NULLRUN_ROOT` to a private writable run directory and `FREEDOOM_WAD` to the installed Freedoom 2 IWAD. Optional `NULLRUN_PORT` defaults to loopback port 8773. Start Studio with a window output, GL rendering and audio output disabled in its private workspace. It does not need a tracker, optical waveform source or Rack-to-Hydra audio analysis.

The companion preset in `presets/nullrun-ambient.vcv` uses one PVX voice, a slow Fundamental LFO gate, clean Spoon Bender ambience and Core Audio-2. Select the desired audio device locally. The prepared render-PC rig uses 48 kHz, one engine thread and a 2048-frame buffer. Rack runs headless with fresh private state for every launch; its support modules have no GUI rendering loop. The preset requires PVXLab 2.0.0, SpoonBenderLab 2.2.1 and Fundamental 2.6.4; plugin binaries are not distributed here.

Studio prepares a replacement game while the current run remains alive. It activates the candidate after renderer validation and closes the old game after all new resources activate. A validation or device-activation failure restores the previous run. Saved steady-view settings are applied to the engine before the first picture.

Reducing both the patch and Rack's display removes several sources of load. It does not prove which component caused the old audible breakup. Verify live audio under game load; an isolated audio pass alone does not establish desktop stability.

## Verification

Build with `make -C doomgeneric -f Makefile.ipc`. With `FREEDOOM_WAD` set, run the native game, boss, Gloamwood, architecture, strobe, desktop-control and Argon test modules. The Argon checks exercise reachable placements, variant frames, dodging, cover, Mimic anchoring, homing spores, weapon damage, death and ordinary-map isolation. Visual review must also use the real native palette and engine; static or behavioral checks alone do not establish readable sprites.
