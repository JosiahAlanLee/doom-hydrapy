# Null Run: UZDoom campaign

This is a separate playable backend for the seven-floor campaign. UZDoom owns
movement, damage, collisions, enemies and progress; HydraPy displays its private
1280×800 picture, applies optional filters and draws a separate readable HUD.
Gorgon and a minimal VCV Rack patch play the adaptive score. The existing
`native_nullrun.py` and browser versions retain their behavior.

Each floor has two book demons, UPKEEP upgrades, an uncanny service annex
and a real 480-unit stair atrium. Corridor folds preserve viewing angle and pitch;
memory rooms change their actual ceilings only when unobserved and unoccupied.
The annex puzzle and both bosses gate the route upward. Six environment palettes
select different art and score profiles. Nine architecture families now supply
seven distinct main floors per run: relay atrium, resonance cistern, hanging
garden, switchback quarry, negative cathedral, pump-organ amphitheatre, transit
hall, ossuary conservatory and inhabited archive. The geometry bank uses reviewed
variants 17/73/211; a master seed shuffles families, starts, boss pairings and art.
The ossuary/archive variants also add or remove real branches. New runs avoid the
last five opening families where possible; R retries the exact saved floor plan.
The manifest records the plan, geometry seeds, anchors and provenance.

Fourteen humanoid book demons carry their role emblems. Hollow, Stone ReDead,
Surveyor and Spindle use model-backed versions of the same native AI. Reviewed
same-topology OBJ poses become one MD3 per identity: neutral, two movement slots,
warning, attack, hurt and death. The bosses reuse a neutral return step; the four
new mobs have two distinct locomotion poses. Hard-edged normals and atlas seams
are retained. Three environmental sculptures have conservative physical bounds
and are placed clear of route segments and seals. Other enemies retain the
original procedural sprite art.

An optional **Chladni Archive** opens from the lower service stair. Three seeded,
suspended signal sculptures each have three forms. Nearby F consoles tune them;
held F counts once. Changing forms are non-solid and above player height. The
independent return gate stays usable in every state. This is the first adapted
Argon art concept; the proposed moving labyrinth and parallax ritual remain
design prototypes.

Seven original weapon/hand designs replace all nine native weapon classes'
ready/fire art, flashes and weapon pickups. Chainsaw uses the Fathom Hook art;
Super Shotgun uses Transit-12. Native actions, ammo, timing and damage remain
unchanged. 640x400 source images use 320x200 logical weapon coordinates; generated
flash overlays are aligned to the frame actually used by each native action.
This is still an IWAD-backed game. Every build includes **asset-audit.json**,
listing remaining Freedoom pickups, projectiles/impacts, sounds and fallback/base
resources. Freedoom attribution remains required; no claim of a standalone asset
replacement is made.

## Bosses

The UZDoom rules deliberately differ from the older native-C balancing described
in `BOSSES.md`. Bosses have roughly 140–240 HP, depending on family and roll.
Shielded weapon hits still deal **60% damage**. Binding opens a **12-second** window
at **150% damage**, with a one-second stagger. A ritual is an advantage; defeating
a shielded boss with ordinary weapons also opens its gate. Bosses return to their
encounter area after a long chase and drop shells and a medikit when defeated.

| Family | Binding action |
| --- | --- |
| Repetition | On its marked F seal, press and release F twice. Holding counts once. |
| Quiet | On its marked F seal, stand still without firing for one second. The boss pauses during the charge. |
| Proof | Hit its shield once, then use F on its seal. Holding F while entering works. |
| Passage | Enter amber A, then cyan B. |

One compact health card appears for a nearby visible boss, an active seal or a
recent nearby attack/hit. It clears after combat, defeat or leaving the encounter;
there is no permanent pair of cards during exploration. Seal entry briefly shows
an unfamiliar ritual tip; successful binding teaches that family for the run.
Active ritual progress stays visible in one narrow strip above the bottom HUD.
Proof and A-seal acknowledgements last three seconds; exposure needs only the
health card's timer. Standing on a seal takes priority over aim direction. World
markers identify F, A and B seals; overhead badges flash only on hits/opening.
Other enemies and projectiles remain dangerous during a binding attempt.

## Requirements and launch

Tested on Ubuntu 22.04, Linux x86-64, UZDoom 5.0.3 with SDL2 2.26.5 and NVIDIA
OpenGL, Python 3.11, the current HydraPy/Gorgon tracker runtime, Pillow, NumPy,
JACK/PipeWire, VCV Rack 2 and Freedoom 0.13.0. Engine, IWAD, plugin binaries and
Python dependencies are supplied separately. There are no automatic downloads or
system installations. The private bridge is SDL2/Linux x86-64 specific.

Build the opt-in bridge in an owned runtime directory:

```sh
c++ -std=c++17 -shared -fPIC -O2 uzdoom/bridge/capture.cpp -ldl -o /path/to/runtime/capture.so
```

Set these environment variables before running the supervisor:

| Variable | Meaning |
| --- | --- |
| `NULLRUN_ROOT` | Owned job directory; persistent runs, logs and private control token. |
| `UZDOOM_BINARY` | UZDoom executable. |
| `UZDOOM_BRIDGE` | Compiled `capture.so`. |
| `FREEDOOM_WAD` | Freedoom2 IWAD. |
| `NULLRUN_DEPENDENCIES` | Frozen directory containing `hydrapy/` and `Gorgon/`. |
| `NULLRUN_RACK` | Rack executable. |
| `NULLRUN_RACK_PLUGINS` | Reviewed Linux Rack plugin directory. |
| `NULLRUN_PORT` | Loopback control port, default 8774. |
| `NULLRUN_SEED` | Optional unsigned 32-bit seed, default 20261031. |
| `NULLRUN_ENVIRONMENT` | Optional one of the six IDs in `build.PACKS`. |
| `NULLRUN_CUE_SHADERS` | Set to `1` to enable the reviewed event effects on first launch; saved F4 preference takes priority. |

Copy `rig/initial-score.json` and `rig/adaptive-live.vcv` into
`$NULLRUN_ROOT/music/` before first launch. Preserve an existing rig. The supplied
patch targets JACK, 48 kHz, 2048 frames and the render PC's Digi 003 stereo output.
For another device, configure both the patch and `NULLRUN_AUDIO_DEVICE` before
launching. The supervisor uses the existing audio server and routes only its
identified Rack client. GorgonBridge provides CV; PVX, VCA, Sum and restrained
Spoon Bender provide the sound. Required plugin models are in the patch JSON.

```sh
python -m uzdoom.session start
python -m uzdoom.session status
python -m uzdoom.session restart-music
python -m uzdoom.session stop
```

The supervisor currently targets the render PC's desktop session `:1`, user ID
1000 and its GDM authority path. Adjust `session.environment()` for another desktop
account before freezing a runtime. Run from a frozen source copy with that copy
on `PYTHONPATH`. A running source snapshot must not be edited.

The game starts paused. Click/Enter resumes; Escape releases controls and pauses.
WASD moves, mouse looks on both axes, click/Ctrl fires, Space jumps, F/right click
uses, Shift runs, Tab maps, and 1–7 select weapons. R retries the seed; N creates
another. F2 selects steady/irregular annex lighting. F3 cycles RAW, PHOSPHOR,
ASCII and PRINT. RAW is the default. F4 toggles the event effects and returns the
world to its base picture. When event effects are enabled, F3 immediately returns
to RAW; further F3 presses cycle the other filters. The F4 preference is saved.
HUD and aim marks remain unfiltered.

Event effects are brief native cues: peripheral stillness during a Quiet seal's
one-second charge and restrained Surveyor warning brackets/edge accents. The
center20% of both screen dimensions remains unchanged. Warning cues require a
living nearby Surveyor with actual line of sight; simultaneous warnings use the
most urgent countdown, reducing Quiet intensity while an attack is pending.
Pause, menus, death, victory, disabled effects and native telemetry older than
250ms clear them. Only current native state is used, so old effects do not queue
across floors or seeds. Texture operators and the live renderer share
`presentation.world_effects`; the HUD is layered afterward.

Argon's additional ritual/grip suggestion is adapted to the current native rules:
families come from classes 5/6/9/10, openings count down from 420 tics, stillness is
35 tics, and ReDead's mask warning is phase 1 for 28 tics. An active grip appears
from escape progress 0 and follows the real 25-tic held-F escape. Family status,
opening ticks, warning chevrons and grip rails stay peripheral. They add no
full-world colour wash or UV displacement; logical header/bottom bands, the
central 20% rectangle and source alpha are preserved. Invalid scalar values fail
closed before GPU uniform upload. Grip suppresses quiet/boss decoration, while
attack warnings retain priority. F3 RAW and F4 apply to all effects.

One controller owns the game. Ordinary stop refuses while the physical player is
active. Restarting music preserves the game. Do not use `stop --force` without
an explicit request to interrupt play. Native engine sound effects are disabled
by default; `UZDOOM_SOUND=1` is an experimental opt-in, separate from Rack music.

## Validation

The test runners below create a fresh instrumented copy of a production PK3;
fixtures are never included by the playable builder. Their placement shortcuts
and reduced interference establish mechanics, not human combat difficulty.

```sh
python -m uzdoom.build --assets /path/freedoom2.wad --seed 1233599628 --output /new/build
python -m uzdoom.tests.native --engine /path/uzdoom --bridge /path/capture.so --iwad /path/freedoom2.wad --pk3 /new/build/nullrun.pk3 --output /new/native-check
python -m uzdoom.tests.boss_encounter --engine /path/uzdoom --bridge /path/capture.so --iwad /path/freedoom2.wad --pk3 /new/build/nullrun.pk3 --output /new/boss-check
python -m uzdoom.tests.architecture --help
python -m uzdoom.tests.transition --engine /path/uzdoom --bridge /path/capture.so --iwad /path/freedoom2.wad --pk3 /new/build/nullrun.pk3 --output /new/transition-check
python -m uzdoom.tests.held_input --engine /path/uzdoom --bridge /path/capture.so --iwad /path/freedoom2.wad --pk3 /new/build/nullrun.pk3 --output /new/held-input-check
python -m uzdoom.tests.routes --engine /path/uzdoom --bridge /path/capture.so --iwad /path/freedoom2.wad --pk3 /new/build/nullrun.pk3 --output /new/route-check
python -m unittest uzdoom.tests.test_cues
python -m unittest uzdoom.tests.test_art
python -m uzdoom.tests.encounter_render --output /new/gpu-check
```

On 2026-10-31, all 21 native checks passed after the boss revision, including all
four binding families, real pistol proof, native damage/healing/ammo upgrades,
Hollow/ReDead, six special attacks, reversible/blocked folds, collision-changing
rooms, the stair climb and seven-level run state. Ten additional checks on the
last human-play seed retained both authored bosses and seals: correct focus,
held-F entry, press progress, 12-second opening, 60%/150% native damage, markers,
leash recovery and defeat without binding. Screenshots of progress and exposure
were visually inspected. Nine prior architecture checks cover rotated folds and
the authored memory room.

The preceding integrated runtime reached approximately 60 fps during physical
play. A passive 30.04-second tap of its existing Rack outputs had peak 0.257,
nonzero stereo RMS, no clipped samples, no xruns and no clock discontinuities.
This is a bounded measurement, not a guarantee for every future run or device.
The boss revision leaves that audio rig and render path unchanged. Combat balance
and complete human runs still need playtesting.

Level-local grip, shriek, immunity and muzzle-flash timers reset when a new floor
loads. The native transition regression seeds old-clock deadlines, uses real
`Exit_Normal` changes through MAP02/MAP03, and verifies both player movement and
retained run upgrades. `--expect-stale` reproduces the frozen arrival on an older
package; its setup never clears the incoming timer itself.

The Python controller also invalidates its sent-key cache when the native map
changes. The engine releases buttons during a transition; the next physical
input snapshot must therefore reassert movement that is still held. Once the
new floor is ticking, movement is released and rearmed after seven native ticks
to cover delayed input clearing during loading; use, attack, jump and weapon
selection keep their press edges. The separate
`held_input` runner uses the real `Game.input` loop and a straight test lane to
isolate this from terrain collision. `input_resyncs` is exposed in game status.

The adaptive backend tests use HydraPy's real tracker. Add
`uzdoom/music_package` and the dependency roots to `PYTHONPATH`, set
`NULLRUN_INITIAL_SCORE` to the supplied score and `NULLRUN_ROOT` to an owned
directory, then run `python -m unittest uzdoom.tests.test_music`.

See `assets/tower/CREDITS.md`, the existing project credits and the IWAD/engine
licenses for attribution. External model output is reviewed before promotion.
`tools/ask_argon.py` is an optional Gemini helper; attachments leave the machine
and need the owner's permission. Credentials are supplied locally and are never
part of the game, patch or source tree.
