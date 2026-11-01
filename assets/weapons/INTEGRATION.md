# Proposed integration notes (not tested in an engine)

This is art replacement only: no balance, damage, ammo, sound or engine-behaviour changes are proposed or tested. Nothing below claims a working ZScript/ACS/engine API; treat it as a layout description.

## Body frames

Each `frames/<slot>/<id>_<index>_<state>.png` is a 640x400 RGBA image already anchored to the viewport. Draw it at screen (0,0) on the bottom weapon layer. The central aiming rect (220,40)-(420,180) is empty. Forearms reach the bottom edge deliberately; other edges are untouched.

Suggested sequence, using the manifest state names:

- Ready: loop `idle` at 900 ms (or hold).
- Raise: `raise_low` 90 ms, `raise_mid` 90 ms, then `idle`.
- Fire: `fire_peak` 60 ms + flash A, `fire_settle` 80 ms + flash B, `recover` 110 ms, `idle`.
- Cycle/reload: `reload_a` 240 ms, `reload_b` 300 ms, `idle`. Melee: `windup`, `impact` + spark A, `follow` + spark B, `recover`, `guard`.

If the engine needs explicit offsets/pivots, use the manifest's `origin`, `content_bbox` and per-frame `generation_pose`; the baked frames need none. Muzzle points are recorded for flash or light spawning.

## Flashes

Flash PNGs are separate 640x400 RGBA overlays generated from the matching fire frame's pose. Composite at (0,0) over the body layer with normal alpha, or additively if the renderer supports it. The manifest records `muzzle_world`, `for_frame_index` and `duration_ms`. Flash alpha is already anti-aliased and has no opaque background.

## Icons

`icons/<id>_icon_96x64.png` is a side-profile pickup sprite with a transparent margin. Native size is 96x64; scale by an integer factor for larger HUD use.

## What is not provided

No DECORATE/ZScript/ACS, no wad/pk3 packaging, no palette conversion, no HUD layout, no audio. The frames are true-colour RGBA; conversion to a limited palette is a game-side decision.
