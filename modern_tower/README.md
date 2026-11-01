# Experimental 3D tower

This separate UZDoom prototype tests the next engine path for Null Run: looking
up/down, stairs, and solid walkways stacked over the same map coordinates. It
uses the existing Drowned Records textures as placeholders. It does not replace
`rogue/campaign_live.py`, its native input, or the working adaptive music rig.

The map has three ten-step stair flights with 16-unit rises, landings at heights
160, 320 and 480, and stacked bridges through an atrium. The route gains 480 Doom
units, or 7.5 metres using the content-kit scale of 64 units per metre. Walkway
surfaces are solid 3D floors, with space to pass underneath. The generator checks
player clearance between surfaces. No mandatory jumps are needed.

## Build

From the repository root, with Python and the existing original environment art:

```sh
python modern_tower/build_tower.py --output runtime/tower-map
```

The default art directory is `assets/environments/art/drowned_records`; pass
`--art-root` to test another kit with matching `walls/01.png` through `08.png`
and `flats/01.png` through `04.png`. The output directory must be new. Outputs are an original PK3, editable UDMF
TEXTMAP and geometry/provenance manifest. The generated archive is deterministic.

Use an official UZDoom release, such as the verified 5.0.3 Linux AppImage from
https://github.com/UZDoom/UZDoom/releases/tag/5.0.3 . The engine and Freedoom IWAD
remain external; no binary or game asset download runs automatically. The
existing Freedoom 2 IWAD works. Portable/extracted engines must be able to locate
their supplied support PK3s, as required by that engine distribution.

## Optional original environment kits

A separate generated kit with `props3d.json`, `art/<id>/walls/`,
`art/<id>/flats/`, OBJ/MTL files and their textures can populate the test tower:

```sh
python modern_tower/build_kit_variants.py \
  --kit /absolute/path/to/environment-kit \
  --base-map runtime/tower-map \
  --output runtime/tower-variants
```

This reads asset data and does not run the kit's Python generator. It creates
one fresh variant directory per environment, replacing only the test textures
and adding three static model actors. It preserves original kit files and
records original/adapted mesh hashes. UZDoom's OBJ importer expects Y-up models
and texture names in `usemtl`; the adapter rotates Z-up vertices/normals and
maps materials to the provided atlas. A nonempty `COLU` base frame and suitable
actor bounds keep model actors visible. The models are visual props; their
proposed collision proxies and moving lifts are not implemented.

The bank's sprite atlases, music profiles and vertical layout documents remain
separate inputs. This adapter does not instantiate new enemy AI or music.

## Isolated verification

The harness requires Linux, `xvfb-run`, NumPy and Pillow. Its output directory
must be new. It owns and bounds its process group, uses a private virtual display
and configuration, and disables sound. It does not capture or send input to the
user's desktop.

```sh
python modern_tower/prove_tower.py \
  --engine /absolute/path/to/uzdoom \
  --iwad /absolute/path/to/freedoom2.wad \
  --pk3 runtime/tower-map/nullrun-tower-proof.pk3 \
  --output runtime/tower-proof-01
```

The test steers the actor with horizontal velocity through native collision,
step handling and gravity. Six waypoints must reach the expected landing heights;
the ascent never teleports. After the climb finishes, camera-only placements
capture ground and upper-landing views at pitches 0 and ±45 degrees. The test
checks engine telemetry, full-frame dimensions, nonblank images and distinct
up/down views. Inspect the five PNGs too: image statistics do not prove visual
quality. `verification.json` distinguishes the collision ascent from the later
camera placements.

The isolated display commonly uses Mesa/llvmpipe, so this is a functionality
check, not an RTX 4090 or VCV performance benchmark. Startup `-width/-height`
and `win_w/win_h` must agree; otherwise readback can contain stale borders.
Console waits must stay in one command string, and camera captures must wait
for the map and renderer to settle. The harness handles both issues.

## Manual prototype controls

For a separate manual preview, launch the map with a fresh config and set
`freelook=true`, `nr_probe=false`, `nr_camera_test=false`, and `nr_pose=0`.
The test flags default to false/zero; do not reuse the proof's automated config
for normal play. Use the source port's own mouse look and keyboard bindings.
A manual launch opens that engine's own window and can take focus.

## Migration work still required

This is a geometry/camera foundation. The custom C enemy/boss/binding logic,
architectural mutations, Null Run HUD, HydraPy presentation/input adapter and
adaptive Gorgon/PVX cue bridge have **not** been ported into UZDoom. A normal
WAD cannot carry those compiled C changes into another engine. The current game
remains the playable reference for their behavior.

Next, port one representative enemy and a minimal state/cue adapter; verify
mouse pitch/ownership and visual effects; then test under the real 4090 and
music load before expanding the campaign. Environment meshes and proposed
vertical AI require their own engine/collision review. Three new DeepSeek tower
kits are stored separately. The optional adapter loads their textures and static
props, while their enemy and music proposals still need runtime integration.

Original prototype code is GPL-2.0-or-later. Credits remain with Josiah Alan-Lee,
Argon, DeepSeek, Codex/Claude, id Software, doomgeneric/Chocolate Doom, the UZDoom
and GZDoom/ZDoom contributors, and the Freedoom project. This prototype reuses
only the project's original environment textures plus the externally supplied
Freedoom IWAD.
