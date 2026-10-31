# Architectural studies

Three original, selectable studies add bounded spatial tricks to the existing
classic Doom child process. Choose one under **Next Run**, then **Retry**. The
five-floor campaign and creature/binding studies remain available.

* **Afterimage / Corridor:** a matched corridor transfers the player between
  physical copies. The zero-rotation seam retains heading, exact local offset,
  velocity, relative height and camera height. Walk backwards through it to
  return. Different rooms lie beyond the far bend; follow the hall to the light.
* **Five Corners / Pillar:** keep the pillar on your left. Five visible left
  turns and four concealed quarter/half-turn transfers return to the original
  hallway and heading. The entrance is the bent alcove off that first hallway.
  All four copies have matching blind alcoves, wall materials and floor/ceiling
  phases. Floors are symmetric about Doom's texture origin for quarter turns.
* **Unreliable Memory / Room:** look at the two passages, then turn away. One
  closes and the other opens after twelve continuously unseen, empty native
  tics. Look back, then away, to arm the next change. The exit is in the original
  room, outside both changing sectors.

These are fixed study layouts; the run seed still controls generated creature
art elsewhere. They are not random campaign events yet. No MyHouse map or art
is included.

## Native behavior

`rogue/architecture.py` authors ordinary classic BSP geometry plus a binary
`RARCH` lump. `doomgeneric/rogue_arch.c` reads that bounded map metadata and acts
after native physics, before drawing. It exposes read-only counters through
the existing `STATE` reply; it adds no writable IPC command.

Seams detect a directional plane crossing, preserve the sub-tile offset and
rotate the player's momentum and heading by whole quarter turns. The inverse
plane is paired for immediate backtracking. Only one seam may fire per tic.
Jumps longer than 64 map units in one tic do not trigger another seam. The
seams use collision-checked `P_RogueRelocate`, avoiding telefrag, pickup, fog,
sound and reaction-time freeze. A blocked destination rejects the move and
leaves both actors intact. A zero-rotation seam preserves the absolute angle;
the pillar's rotations preserve the apparent direction through matching halls.

The room study swaps only the ceilings of two complementary 128-unit square
sectors. A conservative padded camera-frustum test treats even occluded boxes
as watched. Nearby boxes also defer. Any overlapping solid, shootable, pickup
or missile object defers both changes; this includes the player. An observed
pair must remain unseen and clear for the full delay. Both ceilings change in
one native tic, followed by normal sector collision updates. Another change
requires a new observation. There are no crushing floors or moving exits.

Architecture state resets before level geometry is freed. The feature needs
`DOOM_ROGUE_FLOORS` and valid metadata for the current map. Missing, disabled
or other-map metadata leaves ordinary behavior active. Invalid metadata is
reported and disabled without executing its actions.

## Metadata

Little-endian signed 32-bit words after a four-byte `RAR1` signature:

```
header: map, kind, seam_count, change_count
seam: id, source_x, source_y, destination_x, destination_y,
      axis, sign, quarter_turns, half_width, reserved_zero
change: id, sector_tag_a, sector_tag_b, open_height, unseen_delay
```

The parser requires the exact byte length, at most 16 seams and 8 changes,
coordinates within ±32760, axis 0/1, sign ±1, rotations 0–3 and half-width
16–512. Changes require distinct unique sector tags, rectangular 128-unit
boxes, complementary initial heights, open height 64–1024 and delay 4–350.
Malformed inputs do not expose script execution or runtime editing.

## Verification and limits

`test_architecture.py` drives the actual child engine with ordinary keys.
It checks deterministic metadata and texture symmetry; exact corridor images
and motion against an unmodified reference in both directions; an occupied
destination without damage; the five-left-turn route and real exit; observed,
unobserved and occupied mutation timing; passage collision before/after the
change; level reset; disabled and malformed metadata. Run it alongside
`test_rogue`, `test_bosses`, `test_gloamwood` and `test_ipc.py`, with
`FREEDOOM_WAD` pointing to a supplied Freedoom 2 IWAD. Native checkpoints must
also be visually reviewed, including each study and both sides of a seam.

Transfers affect the player only. Monsters and projectiles do not cross them.
These are classic physical-copy illusions rather than render-through portals;
the automap can expose the copies. The scene is deliberately plain so corner
counting and passage changes are readable. Browser audio, save/resume and the
remaining prototype limitations described in `GLOAMWOOD.md` still apply.
