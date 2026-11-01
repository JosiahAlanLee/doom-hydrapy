# Threshold and seven-tier integration

This combines the content/GUI checkpoint `64fe0c8504969721b40a417b91f679f324e46f1e`
with the seven-tier engine/controller work `21e38b7b66535a5001530955bfaf5f7ba4dba817`.
The original checkpoint remains unchanged on `codex/threshold-identity`.
Its handoff is preserved verbatim in [THRESHOLD_HANDOFF.md](THRESHOLD_HANDOFF.md).

## Result

- The preferred Threshold browser layout, native instrument panel, Departure Mono
  typography, credits, materials, props and two new enemy families are retained.
- Seven office tiers retain all fourteen allocated book demons. Both demons
  must be bound and defeated before each exit opens; MAP06 leads to MAP07.
- The authored opener keeps its geometry, original eight enemies, pickups,
  optional cache and prop locations. The campaign adapter adds Repetiel and
  Scriptorax, independent binding rings and supplies on free route tiles.
- The original four Argon families, Latchwing and Relay Choir coexist. Calmor
  and Latchwing share native type 69 but use distinct variant flags; boss
  classification and isolated studies preserve that distinction.
- Mouse turn/fire/use, focus-loss pause, pointer release, saved sensitivity,
  steady-view restoration and transactional Studio replacement are retained.
  A hardware-disarmed Studio starts software play after validation.
- The clean native display preserves palette updates. The bounded visplane
  repair from the content branch is retained. Study and direct-engine callers
  keep the original status display unless they explicitly opt into clean HUD.
- Props are placed only where their combined solid footprint leaves the whole
  floor and every binding ring reachable. This fixes a tier-seven placement
  that enclosed one otherwise walkable cell.

The fourteen book identities continue to share four combat/sprite families;
fourteen bespoke designs and mechanics remain future work. The manifest format
is `doom-rogue-6`. Identical seeds from earlier formats describe different runs.

## Source and audio

All 46 hashes in the Threshold runtime asset manifest still match. Original
worker sources, the authored opening generator, licenses and attribution remain
intact. Integration changes are confined to runtime adapters and game code.

The supplied 120-second score remains data. This integration does not render,
audition or deploy it, and does not change the existing Rack ambience preset.
The standard campaign patch remains RAW. A later [opt-in Surveyor optics
adapter](SURVEYOR_OPTICS.md) is available separately for rendering-PC integration.

## Verification

The complete combined suite passed: **89 tests**.

```sh
make -C doomgeneric -f Makefile.ipc -j4
FREEDOOM_WAD=/absolute/path/to/freedoom2.wad python -m unittest -v \
  test_rogue test_bosses test_gloamwood test_architecture test_strobe \
  test_desktop_controls test_argon_native test_native_playability \
  test_threshold_native test_threshold_content
FREEDOOM_WAD=/absolute/path/to/freedoom2.wad python test_ipc.py
```

HydraPy must be importable for the real ResourceStage replacement checks.
The tests cover actual weapon damage and corpses, Latchwing/Calmor coexistence,
both-demon exit locking, all seven pairs, the native secret, traversal through
the opener and six procedural tiers with solid props, inventory carryover,
input ownership and reload rollback. Four additional map seeds verify that
prop placement preserves every room and binding. The deterministic 240-second
IPC regression also passed.

Both variants of each new creature were reviewed through the native software
renderer and IWAD palette. Native opening/pause/credits frames and the browser
layout were visually reviewed. A browser check verified movement, Escape
pause, both demon identities, hidden study/treatment controls, font delivery
and credits without JavaScript errors.

Physical native-window input, target GPU frame timing and live Rack audio
still need checking on the render PC. No new live performance or audio result
is claimed by this integration.
