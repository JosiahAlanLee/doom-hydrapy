# Opt-in Surveyor optics

`rogue/optics.py` adapts Argon's revised Gameplay Optics submission to the native
Null Run telemetry and the Threshold HUD. It provides a read-only director,
coherent desktop sampler and matching HydraPy NumPy/GLSL texture operator.
RAW is the default. Importing this module does not register an operator or start
an engine, device, thread or network service.

## Native contract

An active warning requires **all** of these fields from one `MOBS` response:

| Field | Accepted value |
|---|---|
| `argon_kind` | `"surveyor"` |
| `class` | integer `11` |
| `missile` | boolean `false` |
| `health` | positive signed 32-bit integer |
| `argon_phase` | integer `2` (warning) |
| `warning_ticks` | integer `1..35`, counting **down** |

The visual segment count is `36 - warning_ticks`: 35 remaining gives segment 1,
31 gives segment 5, 8 gives segment 28, and 1 gives segment 35. Zero, another
phase or death clears the warning. With multiple valid Surveyors, the earliest
discharge wins. A warning denotes an engine attack state, not a guarantee that
its eventual shot will hit the player or that the enemy is on screen.

The director has no display-time accumulator. Repeated renders of the same
snapshot cannot advance the countdown. It skips malformed records and rejects
oversized batches (more than 4,096 actors). Legacy `hp`, `kind`, `warning_tic`
and `charge_tics` fields are not accepted as substitutes for native telemetry.

`NativeOpticsSampler` takes a `rogue.desktop.Desktop`. On the render thread it
reads the picture and `MOBS` under the native game's existing lock, checking
revision/frame agreement. It polls at most once per native frame and caches the
picture/uniform pair for repeated callbacks at one render time. Lock contention,
loading, pause, death, victory, non-play states, incoherent frames and telemetry
errors select RAW. RAW itself makes no `MOBS` request. A failed request is not
retried until the native frame changes; `last_error` records a bounded diagnostic.
The engine protocol still uses the existing client's request timeout.

## Picture behavior

The optional treatment combines a visible material image with a green central
difference edge filter. This is an image effect, not Sobel/depth reconstruction
or enemy detection. The sampling offsets use one native 640×400 cell even when
Studio renders at a larger resolution; edge taps clamp instead of wrapping.
There is no UV displacement.

During a warning, a 35-segment bar fills at native tics and two brackets converge
outside the crosshair. Segments 1–27 are amber and 28–35 are steady red. There is
no flashing clock or strobe. The following native screen regions retain the
original RGBA values after all processing:

| Protected area | Top-down 640×400 coordinates |
|---|---|
| Title, cue and paired-boss bands | rows `0..87`, full width |
| Bottom instruments | rows `353..399`, full width |
| Crosshair | columns `308..332`, rows `180..208` |

The bar occupies rows `336..343`, columns `96..543`. These masks describe the
current HUD contract; a future HUD layout change must update both implementations
and the preservation tests. Pause/credits panels bypass the treatment entirely.
Invalid or non-finite scalar uniforms also return the unchanged source sample,
including alpha. RAW bypasses this operator; upstream/downstream effects can
still change an image if the host applies them.

Rear-ambush shear, proximity/range rings and colour-based hazard classification
are removed. Current actor telemetry supplies no reliable wall-occlusion signal.
The proposal's broader roster, jammer, gaze and geometry claims are not engine
features supplied by this module.

## HydraPy integration

This is an optional building block for the rendering-PC thread. The standard
`rogue/campaign_live.py`, GUI controls, environment assets and music engine are
unchanged. Use the existing `Desktop` instance (`game` in that patch) and replace
its picture/chain construction with this pattern:

```python
import numpy as np
from hydrapy import Fn, FrameSource, src
from rogue.optics import NativeOpticsSampler, register_hydrapy_ops

register_hydrapy_ops()       # explicit; does not happen on import
sampler = NativeOpticsSampler(game)
view = {"raw": True}        # host UI owns this flag on the render thread
last_image = [None]

def sample(t):
    return sampler.sample(t, raw_mode=view["raw"])

def picture(t):
    image = sample(t)[0]["image"]
    if image is last_image[0]:
        return None
    last_image[0] = image
    return np.asarray(image)

source = src(FrameSource(picture)).pixelate(640, 400).nullrunSurveyorOptics(
    surveyor_tic=Fn(lambda ctx: sample(ctx.time)[1].surveyor_tic),
    raw=Fn(lambda ctx: sample(ctx.time)[1].raw),
)
```

Keep the patch's existing scene, render call, input hook and resource lifecycle.
Use the **same** render time and RAW flag in every callback so the sampler returns
one coherent pair. Setting `view["raw"] = False` opts into the treatment; setting
it to `True` bypasses it on the next render without rebuilding the graph. No
extra polling loop is needed. The registered operator is deliberately named
`nullrunSurveyorOptics` so the archived proposal's `doomTacticalOptics` cannot
silently replace it. Direct users can call `TacticalOpticsDirector.compute_uniforms`
on their own coherent native snapshot and pass `.shader_inputs()` to the operator.

## Verification

On 2026-10-31, all **110** combined game/controller/content/optics tests passed,
including **21** optics tests with real Freedoom telemetry and HydraPy importable.
All **12** WebGL comparisons passed: RAW and protected pixels were exact, and
world-treatment differences were at most one 8-bit level. The integration example
above also passed a RAW/OPTICS toggle check using HydraPy's actual Fn/FrameSource
path and GLSL generation. Native-opening frames with segment 5 and segment 35
overlays were visually reviewed.

Make HydraPy importable, build the existing IPC engine, then run:

```sh
make -C doomgeneric -f Makefile.ipc -j4
FREEDOOM_WAD=/absolute/path/to/freedoom2.wad python -m unittest -v test_optics
```

Tests cover the real Surveyor warning/attack payload, invalid/corpse records,
countdown direction, multiple enemies, repeated display frames, restart/pause,
nonblocking lock contention, failed polling, complete RGBA RAW preservation,
current HUD masks and the actual HydraPy chain at native and double resolution.
The telemetry test requires `FREEDOOM_WAD`; renderer tests require HydraPy.

The optional WebGL parity check requires Playwright and Chromium:

```sh
node tools/check_surveyor_optics.cjs
# Optional: PLAYWRIGHT_MODULE=/absolute/path/to/playwright CHROME_BIN=/path/to/chromium
```

It compares 12 NumPy/GLSL cases, including invalid uniforms and the amber/red
boundary, in an RGBA8 framebuffer. RAW and protected pixels must match exactly;
the world treatment allows at most two 8-bit levels of rounding difference.
Cloud validation uses Chromium's SwiftShader. Native HydraPy GL execution,
physical controls with the treatment enabled and target GPU timing still need
checking on the render PC; no hardware performance or live audio result is claimed.

## Source and license

Argon's revised submission, supplied as `Doom Gameplay Optics (1).py`, is preserved
byte-for-byte at `assets/argon/provenance/Gameplay-Optics-original.py` with its
GPL-2.0-or-later notice. Its SHA-256 is
`b6a397f3f4f7bdd8d31c1ced3f81209dc7ce7d757cb3642425a1ca861e1526ee`.
That archive is not imported by the runtime. Codex adapted the telemetry,
sampling, HUD protection, defaults and tests; the derivative retains the same
license. The accompanying white paper is a design proposal, not the native
engine/API specification or a source of validated performance measurements.
