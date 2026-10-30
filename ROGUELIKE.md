# Null Run: a playable generative Doom campaign

Five original seeded floors, one life. Connected rooms and corridors, increasing
encounters, supplies, a bright exit tile, and inventory/health carried between
floors. Clearing floor five wins. Death ends the run; Retry rebuilds the same
seed and New Run chooses a different one.

This is a first playable prototype, with the real Doom combat simulation and
Freedoom 2 assets. It does not play a prerecorded demo. It is separate from the
timed Rack/Studio capture workers and uses no JACK device. Game sound and the
tracker-driven soundtrack are not connected to this browser mode yet.

## Run

Linux x86-64; existing engine compiler requirements plus Python 3.10+, NumPy and
Pillow. Obtain Freedoom 2 from its official release; assets are not bundled.

```sh
make -C doomgeneric -f Makefile.ipc -j4
python -m rogue.server --wad /absolute/path/to/freedoom2.wad --port 8767
```

Open <http://127.0.0.1:8767> on the same machine. For a remote render PC, keep an
SSH tunnel open on the computer where you want to play:

```sh
ssh -N -L 8767:127.0.0.1:8767 user@render-host
```

Use the same local port; Host/Origin validation intentionally accepts only the
loopback addresses on the configured port. The server does not bind to a LAN or
public interface. Ctrl-C stops it and closes its own engine child.

Each run is written to its own folder beneath `runtime/rogue` (override with
`--run-dir`). Its PWAD, seed, manifest, reachable route and SHA256 are retained.
This is not a save-game/resume system. Restarting the server starts a fresh run.
The algorithm version and source revision matter when comparing seeds.

## Controls

Click Enter the Run to claim the controller. WASD moves and strafes, left/right
arrows turn (Q/E also turn), Space or left Control fires, F uses, Shift runs,
Tab toggles the normal explored Doom map, and 1–7 selects owned weapons. Escape
pauses. Native Doom aiming applies; there is no mouse look or pointer lock yet.
Browser shortcuts involving Control may still be reserved by the browser; Space
is the recommended fire button.

Cross any edge into the bright exit tile to descend. The tile is a normal Doom
walk-over exit special. New maps retain the Doom player's health, ammunition
and acquired weapons. The starting room has a shotgun and supplies; enemies
are kept away from the initial spawn. Encounters ramp over five floors. There
are no perk drafts, persistent unlocks, shops or save slots in this first build.

There is one controller at a time. Inputs are full held-key snapshots, not
unbounded keydown repeats. Lost focus/hidden tabs pause and release keys. A
one-second input-heartbeat timeout also stops the game and releases controls.
Death and victory suppress further live inputs until a new run is generated.

Raw, phosphor, ink and four-tone print views are browser WebGL treatments of
the same engine frame. They can be changed without touching the simulation;
the fallback on browsers without WebGL is raw 2D video. These are not the
full Argon/HydraPy scene stack. JPEG frames travel over HTTP at up to 30 fps;
the locked engine advances at 35 tics/s. Under a slow connection playback may
lag; this transport is a local prototype, not a competitive streaming service.

## Implementation boundaries

`rogue/maps.py` writes classic binary PWADs directly: THINGS, LINEDEFS,
SIDEDEFS, VERTEXES, SEGS, SSECTORS, NODES, SECTORS, REJECT and BLOCKMAP.
Every 128-unit tile is a convex subsector, with a balanced axis-aligned BSP.
Closed tiles have no headroom. Shared two-sided lines form the open rooms and
passages. The generator joins rooms through a tree plus loops and verifies
reachability before placing a far exit. No external node builder is required.
Original maps use only Freedoom's existing texture/flat/thing identifiers.

`client.Doom` accepts an optional `pwad` and `rogue_floors`; existing demo
arguments remain compatible. The engine's additive `STATE` command returns
JSON health, ammo, map, position, kills and terminal status. In roguelike mode
only, intermissions advance immediately through `G_WorldDone`, retaining
inventory; the fifth exit is exposed as victory. Five floors avoid Doom II's
MAP06 narrative-finale path. Outside this mode, intermissions are unchanged.

The input backend now drains releases as well as presses in a single tic.
The server maps physical browser key codes to existing Doom key IDs: upstream
doomgeneric disables normal configuration loading, so a WASD config file would
not have been sufficient.

The HTTP service serializes engine access, accepts a bounded set of key names,
checks Host/Origin and a per-process request token, and uses an expiring
controller lease. No arbitrary console command or filesystem path is exposed.

## Verify

```sh
python -m unittest -v test_rogue
FREEDOOM_WAD=/path/to/freedoom2.wad python -m unittest -v test_rogue
FREEDOOM_WAD=/path/to/freedoom2.wad python test_ipc.py
```

Tests cover connected/varied seeds, spawn safety, BSP tile classification,
deterministic WAD bytes, movement/fire/releases, lost-heartbeat pause, real
enemy-caused death and no respawn, request/controller validation, all five
floors and victory. The all-floor traversal fixture removes monsters/pickups
so geometry is tested independently of combat; it walks with real keys and
confirms ammunition survives descents. The death fixture uses real enemies
in an exposed arena. Neither uses teleport or health-setting commands.

Licensed GPL-2.0-or-later with this repository. Freedoom assets retain their
own license and credits; see the repository provenance and upstream licenses.
