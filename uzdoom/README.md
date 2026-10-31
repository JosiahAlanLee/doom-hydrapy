# Null Run: UZDoom campaign

This is a separate playable backend for the seven-floor campaign. UZDoom owns
movement, damage, collisions, enemies and progress; HydraPy displays its private
1280×800 picture, applies optional filters and draws a separate readable HUD.
Gorgon and a minimal VCV Rack patch play the adaptive score. The existing
`native_nullrun.py` and browser versions retain their behavior.

Each seeded floor has two book demons, UPKEEP upgrades, an uncanny service annex
and a real 480-unit stair atrium. Corridor folds preserve viewing angle and pitch;
memory rooms change their actual ceilings only when unobserved and unoccupied.
The annex puzzle and both bosses gate the route upward. Six environment palettes
select different art and score profiles. Reviewed Wavefront props become static
3D models; enemies currently use animated sprites. New humanoid assets are a
separate review task and are not included in this implementation.

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

The two HUD cards show health, damage mode and opening time. The highlighted card
owns the current hint and progress meter; standing on a seal takes priority over
aim direction. The guidance points toward that boss's next seal. World markers
identify F, A and B seals and change when opened or completed. An overhead badge
confirms shield impacts. Other enemies and projectiles remain dangerous during a
binding attempt.

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
ASCII and PRINT. RAW is the default; HUD and aim marks remain unfiltered.

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

The adaptive backend tests use HydraPy's real tracker. Add
`uzdoom/music_package` and the dependency roots to `PYTHONPATH`, set
`NULLRUN_INITIAL_SCORE` to the supplied score and `NULLRUN_ROOT` to an owned
directory, then run `python -m unittest uzdoom.tests.test_music`.

See `assets/tower/CREDITS.md`, the existing project credits and the IWAD/engine
licenses for attribution. External model output is reviewed before promotion.
`tools/ask_argon.py` is an optional Gemini helper; attachments leave the machine
and need the owner's permission. Credentials are supplied locally and are never
part of the game, patch or source tree.
