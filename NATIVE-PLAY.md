# Native Null Run with HydraPy and VCV Rack

`rogue.desktop` presents the live native engine through a HydraPy FrameSource.
Input belongs to that picture window. GLFW key callbacks feed ordinary engine
keys; the browser preview servers are separate and keep their own runs.

The reference Studio patch is `native_nullrun.py`. Put this repository on
PYTHONPATH alongside HydraPy and set FREEDOOM_WAD and NULLRUN_ROOT to absolute
paths. NULLRUN_ROOT holds generated WADs, the controller advertisement and view
preferences. Start the patch in Studio with its GL backend and a native window.
Music requires a separately configured Gorgon tracker score and Rack patch.
The patch reads the named JACK input `rack_return`; connect a Rack mix output
there for the optional treatment modulation. RAW bypasses that treatment.

The Afterimage ByteBus formant lead also needs the optical waveform registered
by `rogue.audio.optical_lead()`. It runs the original score-pitched Harmonograph
as an audio source without drawing it over the game. Omitting that source leaves
Lookup shaping a static address, which produces DC-like thumps when gated.
The private launcher checks for both optical source channels before playing.
Use the Audio-2 output's DC filter and remove residual subsonic content before
mastering recordings. Master the original float audio before encoding AAC.
Tracker `loop=false` selects the full chain; `loop=true` repeats one pattern.

## Controls

| Key | Action |
| --- | --- |
| Enter / Escape | Play / pause |
| WASD | Move and strafe |
| Arrows or Q/E | Turn |
| Space or Ctrl / F | Fire / use |
| Shift / Tab / 1–7 | Run / map / weapons |
| R / N | Retry the seed / choose another seed |
| F2 | Steady lighting view; illumination rules remain active |
| F3 | RAW, phosphor vector, ASCII, four-tone print |
| F4 / F5 | Fluorescent Hollow / five-floor campaign |
| F6 / F7 / F8 | Changing passages / five-corner pillar / corridor fold |

Losing window focus releases held controls and pauses a physical player.
View choices persist in NULLRUN_ROOT/view-settings.json. RAW is the default.
The optional loopback development controller has a per-session token and a
one-second input lease. It rejects gameplay takeover while a physical player
has the controls. Visual adjustments do not release the player's controls.

## Fluorescent Hollow

This adapts Argon's flashbulb-Hollow proposal to native simulation and collision.
The `strobe` study includes a lit alcove and a tagged corridor. Only validated
RSTROBE metadata can activate it; ordinary maps and ordinary Hollow encounters
retain their existing behavior.

Set DOOM_STROBE_STYLE=irregular for the fluorescent treatment: long lit periods
with short, uneven paired dips. The default BPM mode remains available for
clocked studies. Illumination is evaluated on the native 35 Hz tic and drives
both sector light and the Hollow's existing line-of-sight/FOV rule. Real ranged
shots brighten the corridor for exactly six tics. Fists and dry fire do not
create flashes. A steady view changes the picture without changing enemy rules.

The GPU treatments use native light and muzzle state from the same snapshot as
the picture. Feedback uses the previous framebuffer, clears on mode/run changes,
and is disabled in RAW. No host repository or shared VCV installation is changed.
The native engine's game sound remains disabled; music comes from Rack.

## Validation

Build with `make -C doomgeneric -f Makefile.ipc -j8`, set FREEDOOM_WAD, then run:

```
python -m unittest test_rogue test_bosses test_gloamwood test_architecture test_strobe test_desktop_controls
```

Tests cover authoritative light/gaze behavior, exact muzzle-flash length, dry
fire, deterministic irregular lighting, metadata scope, ordinary movement
through folds, view persistence, player ownership and a simulation-completion
race in the render hook. Rendering and audio capture must also be checked on
the target GPU/audio system; static tests cannot establish live performance.
