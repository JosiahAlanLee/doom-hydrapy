# Seeded environment worlds

The Threshold campaign can now select one coherent environment from the run seed.
Walls, floors, ceilings, props, signature mob art and a written score belong to
the same world across all seven tiers. Later tiers rotate structural materials
and place landmark art on existing wall faces.

| World | Signature mobs | Written score |
| --- | --- | --- |
| Drowned Records | Shelf Widow; Redacted Choir | 96 BPM, 48 bars, 120 seconds |
| Switchyard Chapel | Insulator Widow; Transformer Cantor | 128 BPM, 64 bars, 120 seconds |
| After Hours Pavilion | Queue Stalker; Usher Cluster | 112 BPM, 56 bars, 120 seconds |

Selection is `seed % 3` in that order. Seeds 0/1/2 select the three worlds;
3/4/5 select their other signature-mob variants. A/B selection also includes the
mob role, preserving the existing two-slot convention. The campaign manifest
format is `doom-rogue-7` and records the environment, original art credit,
landmark, mob names and matching score metadata/hash. Older identical seeds
retain their navigation/encounters, with a new appearance in identity mode.

The original authored Threshold opener, all seven pairs of book demons, room
connectivity, things, prop collision footprints, actor IDs, binding/secret tags,
floor heights and gameplay lighting are unchanged. Classic and isolated study
calls retain their existing assets. The new images append to the complete
IWAD texture namespace; source textures and patch references remain available.

## Art and behavior

The three kits contain 24 wall images, 12 flats and nine props. Twelve creature
atlases contain 288 frames: six designs, two variants each, six states with four
frames per state. The existing native six-row frame convention directly maps
idle, walk, warning, attack, hurt and persistent corpse art.

These six identities reuse two proven behavior families. The Latchwing slot is
a telegraphed locked-direction dash; the Relay Choir slot is an anchored slow
three-projectile fan. They are new art identities, not six newly implemented
AIs. Warning labels use the current identity while retaining the native class,
count and behavior fields. The other Argon, Gloamwood and book families remain.

Drowned Records is the creepier found-object set: filing shelves unfold into
low bodies and blank paper-veiled registrars build pressure before attacking.
The material/creature generators, original manifests, checks and source credits
are preserved under `assets/environments/`. Native palette conversion can shift
the muted source colors; the code-drawn forms provide identity as well as hue.

## Music status

Each world is keyed to its original six-lane score through
`assets/environments/music/catalogue.json`. All three finite scores validate at
exactly 120 seconds with no monophonic gate overlap. The manifest exposes the
matching score, BPM, duration, patch-plan path and SHA256.

This change does not start playback or a Rack patch. These are written scores
and patch plans. The existing ambience remains a separate runtime choice. Live
revoicing, audition and simultaneous game/Rack performance tests are pending.

## Verification and reproduction

`test_environments.py` checks seeded selection, art seams and transparent
padding, mob state/corpse frames, warning labels, score hashes, geometry and
binding invariance, native loading of all three worlds, preserved texture
references, deterministic WAD reproduction and study isolation. It belongs in
the combined native suite alongside the previous Threshold tests.

```sh
make -C doomgeneric -f Makefile.ipc -j4
FREEDOOM_WAD=/absolute/path/to/freedoom2.wad python -m unittest -v \
  test_rogue test_bosses test_gloamwood test_architecture test_strobe \
  test_desktop_controls test_argon_native test_native_playability \
  test_threshold_native test_threshold_content test_environments
```

HydraPy must be importable for the real Studio resource-staging regressions.
Art can be regenerated into a fresh directory using `assets/environments/art.py`
and `mob_art.py`; their READMEs document exact commands. The original 45-art
manifest is a preserved pre-expansion inventory. `expansion_checks.py` verifies
its original hashes alongside the additions; running its older whole-folder
checker on an expanded tree is not the same inventory test.

Independent native software-renderer gallery frames cover all three sets and
both signature-mob variants. A gallery validates the palette/frame mapping,
not physical mouse input, GPU frame timing, combat balance or live audio. No
desktop game or audio session is started by this feature.

## Credits

Original procedural sources, art and written music: model-assisted DeepSeek
work directed by Josiah Alan-Lee, GPL-2.0-or-later. Native adapters, seeded
selection and independent verification: Codex. Existing Threshold sources,
Departure Mono/OFL notices, Freedoom and Doom engine notices remain intact.
See the preserved `assets/environments/CREDITS.md` and `EXPANSION.md` for the
artifact-level provenance and limitations.
