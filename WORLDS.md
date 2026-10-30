# Null Run 002 — inhabitants and architecture

The second playable iteration adds original generated creature sprites and native
enemy modifiers, alongside a larger architectural grammar. Controls and the
five-floor, one-life loop remain as described in [ROGUELIKE.md](ROGUELIKE.md).

## Architecture

The map grid is now 33 x 33 cells. Seeded placement combines naves, ring chambers,
paired piers/ribbed halls, crosses, terraced courts and cloisters. Carved passages
connect the room graph and add loops. Rooms reach 192–640 units high, contrasting
with 112-unit passages. Stepped rooms rise in 16-unit increments, and the generator
relaxes heights across every traversable edge to keep each rise walkable. The
floor route, supplies and encounters are computed from the final carved geometry.

These are real Doom sectors and solid piers, with a conventional BSP. There is no
room-over-room geometry, impossible portal space, or live moving architecture in
this iteration. The all-floor test walks the generated topology through the engine.
The room masks may be cut by connecting corridors; their final carved cell set is
authoritative. Layouts changed from algorithm `doom-rogue-1` to `doom-rogue-2`;
the first build's same-number seeds intentionally produce different maps.

## Inhabitants

`rogue/creatures.py` draws four original seeded pixel creatures and animation/death
frames, quantizes them into the supplied Freedoom palette and encodes native Doom
column patches. Each seed changes the families' proportions and details. All
individuals of a family share that run's sprite set; they are billboard sprites,
not new 3D meshes or eight independently drawn viewing directions.

| Family | Native base | Changed behavior |
| --- | --- | --- |
| Skitter | possessed rifleman | Faster chase, lower health, reduced hitscan damage, immediate initial reaction |
| Bastion | demon | Slower, much tougher, harder to stagger, heavier, stronger melee |
| Cantor | imp | Variable chase/health, two diverging fireballs, modified projectile speed/damage |
| Shiver | floating head | Faster floating pursuit, lower health, modified projectiles, luminous oscillating silhouette |

Each monster's class and a 0–15 roll are generated deterministically into the
THING options. Native code clones only that instance's info at level lifetime;
shared base definitions remain intact. Projectile variants use bounded static
caches instead of allocating an info copy per shot. Unmarked ordinary maps, and
all runs outside roguelike mode, retain their base enemy behavior.

These augment Doom's existing state machines and navigation. The cantor fan and
shiver visual animation are custom behavior; the underlying archetype AI is still
Doom's. Bastion toughness is health/mass/pain resistance, not armor absorption.
The shiver was visually reviewed with native spectre fuzz, found too hard to read,
and changed to a visible full-bright silhouette. Hit volumes are taller to match
the new drawings, while remaining compatible with the narrow passages.

The generated PWAD carries a complete sprite namespace: the four replaced
families are original generated art, and the remaining sprite bytes come unchanged
from the provided Freedoom IWAD. This is necessary for the classic engine's single
sprite namespace. The manifest records the asset WAD hash. Retain Freedoom's
license/credits with distributed output WADs; no asset WAD is committed here.

## Green-vector view

The browser defaults to `ARGON / GREEN VECTOR`. This ports the central-difference
edge/color kernel from Argon's `doomSobelVectorScope`, with cyan-green architectural
traces and red/amber hazard isolation. The source remains GPL-2.0-or-later;
authorship is credited inline. It is a browser adaptation of that operator,
without the original capture scene's tracker modulation and feedback history.
Raw, plain phosphor, ink and print remain selectable. No geometry/input changes
are hidden in the visual treatment.

## Tests and review

Ten automated tests cover the original game loop plus new room types, reachable
steps, native monster rolls/stats, ordinary-map isolation, a real two-projectile
cantor attack and valid deterministic sprite patches. The all-floor traversal
fixture removes monsters/pickups to isolate navigation; combat is tested in
separate native-engine arenas. Existing `test_ipc.py` demo regression also passes.

Review included actual engine renders of ring/rib/cross/terrace/cloister rooms and
all four creatures, with the original generated art shown beside the engine view.
A bounded 140-frame check in a rotating ribbed hall measured engine tick, state,
frame readback and JPEG encoding against the 35 Hz budget. This is not end-to-end
input latency, network timing or a whole-campaign worst-case stress test.

Audio, mouse look, perks and save-game resume remain future work. Native save
compatibility for generated instance modifiers has not been implemented; use the
browser run/retry lifecycle. The currently running first build can coexist with
this preview on a separate port, so there is no need to discard an ongoing run.
