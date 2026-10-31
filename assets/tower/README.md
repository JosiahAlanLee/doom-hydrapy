# Null Run tower environment bank

Three original tower environments for the null-run direction: **Ashbell Foundry**,
**Boneglass Conservatory** and **Skyhotel Service Well**. Each kit is a coherent
wall/flat/prop family, two signature mobs with A/B atlases, a 3D prop set, a
vertical-layout design table and an adaptive music profile proposal.

Source seed: `20261031`. License: **GPL-2.0-or-later** for this folder. No engine,
map, running game or existing asset was modified.

## The three environments

| ID | Character | Landmark | Tower height | Signature mobs |
| --- | --- | --- | --- | --- |
| `ashbell_foundry` | Soot iron, firebrick, bronze, verdigris, furnace orange; casting bells and chain lifts in open shafts. | **The Ninth Bell** | 15.0 m / 6 levels | Chain Hound, Pouring Choir |
| `boneglass_conservatory` | Bone-white tile, black peat, pale fungus, root cages and descending canopy; very creepy through silhouette and negative space. | **The Root Cage** | 15.0 m / 6 levels | Root Stilt, Hollow Nurse |
| `skyhotel_service_well` | Blue-grey night, rain glass, dirty amber, staggered balconies around a deep service atrium. | **The 33rd Floor Lift** | 18.0 m / 7 levels | Night Porter, Call-Bell Choir |

The three layouts are deliberately different: foundry is a central casting shaft with
chain galleries; conservatory is a glasshouse atrium with organic planter shelves;
skyhotel is an orthogonal, staggered room stack around a service well.

## Folder contents

```
art/<env>/walls/01..08.png       128x128 RGB, seamless both axes
art/<env>/flats/01..04.png       64x64 RGB, seamless both axes
art/<env>/props/*.png            96x128 RGBA: service_lamp, cable_shrine, directory_sign
mobs/<env>/<role>_A.png          512x768 RGBA atlas
mobs/<env>/<role>_B.png          second structural variant
props3d/<env>/*.obj,*.mtl,*.png  3 setting props per environment
props3d/shared/*                  stair_flight, stair_landing, guardrail
sheets/*                         kit, tiling, mob, 3D and overview contact sheets
environments.json                nullrun-environment-kit-1 contract
encounters.json                  nullrun-environment-mobs-1 contract
props3d.json                     3D bounds, triangles, textures, collision proxies
vertical_layouts.json / LAYOUTS.md  physical tower design tables
music_profiles/*.json            adaptive composer profile proposals
manifest.json                    SHA256 of generated files and source modules
```

Wall roles are `01 primary`, `02 relief/panel`, `03 structural`, `04 service hardware`,
`05 shutter/window`, `06 wayfinding/accent`, `07 landmark A`, `08 landmark B`. Flat
roles are `01 primary floor`, `02 utility floor`, `03 ordinary ceiling`, `04 lit ceiling`.

## Generate

```sh
cd /home/echevarian/dev/shared/deepseek/nullrun-tower-environments-20261031
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python generate.py --out . --seed 20261031
```

A fresh folder receives the 45 art PNGs, 12 mob atlases, 12 OBJ/MTL/texture sets,
15 contact sheets, all JSON/Markdown contracts and `manifest.json`.
The generator uses local `random.Random` / NumPy generators and stable hashes only.

## 3D kit

Coordinates are **Z-up, metres**, with the requested conversion **1 m = 64 Doom units**.
Each mesh is a simple UV-mapped OBJ with an adjacent 256x256 procedural texture and an
MTL that references it through `map_Kd`. Meshes are under 5000 triangles each; the JSON
records mesh-derived bounds, triangle/vertex counts, UV ranges and simple collision
proxies. UVs follow the standard OBJ convention (V=0 at the bottom of the map_Kd image).
The shared stair uses eight 12-unit risers (1.5 m) and a landing; two flights
plus a landing make one 3.0 m storey. glTF was omitted rather than growing a new export
framework, as the brief permits.

The 3D sheets are software orthographic previews (flat-shaded, painter-sorted), not
engine renders. They are included so silhouettes from above and below can be inspected.
No prop is a plain recoloured box: every silhouette has a distinct primary mass and at
least one asymmetric feature (cage, bell, spout, rose, wheel, stepped shelf).

## Mobs

Each environment has two identities. A and B are structural variants (extra legs, split
heads, different crown/muzzle/tail or coat/case construction), not recolours. All atlases
are 512x768 RGBA, four columns by six rows, rows `idle/walk/warn/attack/hurt/death`;
frame 23 is a visible corpse. Tells and counterplay are in `encounters.json`.

The six designs use the existing `latchwing` (class 15 CYBR) and `relay_choir` (class 16
PAIN) adapter roles. **All proposed vertical AI is labelled `PROPOSED, NOT IMPLEMENTED`.**
No working game AI, new actor ID or new projectile mechanic is claimed.

## Vertical layouts

`vertical_layouts.json` and `LAYOUTS.md` give the lower/middle/upper routes, an explicit
stair and lift alternative, fall recovery, safe spawn, readable return path, arena/perch
spacing and room-over-room uses. Each tower physically gains height: 15 m, 15 m and 18 m
of real walkable floor levels, not a single tall ceiling. Required routes use stairs and
static lift landings; no mandatory jumps, precision platforming or unseen hits are
specified for the first pass. Native step height (16 units / 0.25 m), native
player clearance/headroom (96 units / 1.5 m) and mesh collision needs are listed separately.

## Music

`music_profiles/*.json` are **proposals only: not rendered, not auditioned, not loaded**.
They mirror the existing composer schema field-for-field. The host `PROFILE_NAMES` tuple
must be extended by Codex before the existing composer can load them. There are no
rendered audio files in this kit.

## Integration notes (metadata only)

- The reviewed native loader currently names the three earlier kit IDs; add these IDs
  before loading. Keep one kit per whole run or tier; do not mix kits per room.
- Keep walls 07 and 08 adjacent; use flats 01 as primary floor and 04 only as a lit ceiling.
- All props remain the existing `service_lamp`, `cable_shrine`, `directory_sign` roles.
- The mob atlases and 3D meshes are art/source proposals, not engine-loaded assets.
- Every 3D mesh has an honest bounds entry; collision proxies are proposals and must be
  converted to native sectors or source-port collision by Codex.
- Bitmap props include small semi-transparent base shadows (alpha 45-62). The native
  patch path treats any nonzero alpha as opaque, so Codex may threshold or drop them.

## Visual review

The 15 contact sheets in `sheets/` were reviewed locally with the image viewer available
in this run: kit families, 2x2 seam proofs, mob atlases, 3D front/top/bottom previews and
the overview. This is a readability/silhouette review of generated previews, not a native
engine render. Codex must still walk the levels at 640x400 and check palette conversion.

## Honest limitations

- Not rendered in the native Doom/Null Run renderer and not quantised to `PLAYPAL`.
  Palette conversion may shift colours; Codex must do the native visual/palette check.
- Contact sheets use nearest-neighbour (bitmaps) or software flat shading (3D); they are
  not a substitute for walking the level at native resolution.
- Music profiles are written proposals only; no audio was rendered or heard.
- Vertical mob behaviour is proposed only; none of it is implemented.
- Checks prove structural properties, not artistic acceptance.
- No engine, map, running game, existing asset or other agent output was modified.

## Generate and check

```sh
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python generate.py --out . --seed 20261031
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python checks.py
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python make_manifest.py
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python checks.py
```
