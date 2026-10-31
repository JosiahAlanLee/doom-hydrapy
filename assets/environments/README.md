# Null Run environment kits - three municipal-horror material sets

Three original, static, CPU-drawn environment kits for the merged Null Run game:
**Drowned Records**, **Switchyard Chapel** and **After Hours Pavilion**. Each kit
is a coherent wall/flat/prop family with its own palette, geometry and landmark.
They are designed to be selected per run or per tier, not mixed room by room.

Source seed: `20261031`. License: **GPL-2.0-or-later** for this kit's source,
metadata, PNG art and contact sheets. The rest of the game retains its own
licenses and notices; nothing here re-licenses or alters existing game assets.

## What is in each set

| Set | Character | Landmark (walls 07-08) | One impossible detail |
| --- | --- | --- | --- |
| `drowned_records` | Flood-marked paper archive and pump bureaucracy: chalk/bone filing walls, petrol waterlines, silted ceramic panels, copper shelf trim. | **The Flood Register** - a drawer facade and a bolted circular tide-register wheel. | The register scale has two zero marks and its pointer sweeps into a drawer bank. |
| `switchyard_chapel` | Ossified power exchange: ivory porcelain brick, rust-red iron, relay niches, charcoal cable braids, warm amber indicators. | **The Silent Conductor** - a nine-fin porcelain insulator fan and a braided cable gallery. | One cable braid terminates in a blank porcelain cap. |
| `after_hours_pavilion` | Deserted transit/convention concourse: dusty plum plaster, worn brass, pale terrazzo, folded baffles, shuttered service bays, contradictory pictograms. | **The Split-Faced Night Kiosk** - a real directory face and the same face inlaid solid in terrazzo. | The route line leaves the map and re-enters at the wrong height; the second face has no opening. |

No religious symbol is copied from an existing game. No generic skull decoration,
solid-green treatment, bloom, strobing or live-reflection/portal effect is used.
Lit ceilings are static fixture geometry, not animated light.

## Layout

```
art.py                         deterministic generator and CLI
checks.py                      independent structural checks
make_manifest.py               hashes sources, metadata and PNGs
environments.json             format nullrun-environment-kit-1, three sets
manifest.json                  SHA256 record plus dimensions/modes/seams
checks.json                    mutable check output (not hashed)
art/<set>/walls/01..08.png    128x128 RGB, seamless both axes
art/<set>/flats/01..04.png     64x64 RGB, seamless both axes
art/<set>/props/              96x128 RGBA cut-outs:
  service_lamp.png            small set-specific fixture
  cable_shrine.png            freestanding material/utility object
  directory_sign.png          landmark / directory object
sheets/<set>-kit.png          labelled whole-set overview
sheets/<set>-tiling.png       2x2 seam proofs plus landmark pair
```

Wall roles are `01 primary`, `02 relief/panel`, `03 structural`, `04 service
hardware`, `05 shutter/window`, `06 wayfinding/accent`, `07 landmark A`,
`08 landmark B`. Flat roles are `01 primary floor`, `02 utility floor`,
`03 ordinary ceiling`, `04 lit/fixture ceiling`.

## Generate

```sh
cd /home/echevarian/dev/shared/deepseek/nullrun-environments-20261031
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python art.py --out .
```

Optional seed: `--seed INTEGER` (default `20261031`). A fresh folder receives the
45 art PNGs, six sheets and `environments.json`. The generator uses local
`random.Random` instances only; it does not use global random state or Python
`hash()`. Two fresh folders at the same seed produce byte-identical PNGs and
sheets. `art.py` draws every pixel from code; no game pixel, font, logo or
texture is sampled.

## Checks actually run

```sh
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python checks.py
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python make_manifest.py
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python checks.py
```

Result at the delivered state: **19/19 checks passed**, `checks.json` written,
then `manifest.json` written, then checks re-run so the manifest was verified.
Art bundle SHA256 at that state: `ec32c74a83bcda524012df63ccfb37e6574e55a9e17d4ab3524ef6a7c8bf7daf`.

Exact check IDs: `art_count_45`, `sheet_count_6`, `environments_json_present`,
`dimensions_and_modes`, `unique_assets`, `nonblank_contrast`,
`prop_alpha_padding_anchor`, `seam_exact_edges`, `seam_behavior_documented`,
`floor_ceiling_distinction`, `wall_bright_dark_hierarchy`,
`inter_set_difference_beyond_recolor`, `distinct_prop_fiction`,
`environments_schema`, `sheets_present_and_sized`, `bounded_output_size`,
`reproducible_same_seed`, `seed_affects_assets`, `manifest_integrity`.

`checks.py` independently confirms:

1. exactly 45 art PNGs and six sheets, with the expected paths;
2. exact dimensions and modes (walls/flats RGB, props RGBA);
3. unique, nonblank, minimum-contrast assets;
4. transparent prop margins, bottom-anchored bases and no opaque rectangular backdrops;
5. exact opposite-edge equality for all eight walls and all four flats in every set;
6. declared seam behaviour in `environments.json`;
7. darker floors than ceilings and a bright static fixture ceiling in each set;
8. a bright/dark wall hierarchy in each set;
9. geometric inter-set structure IoU well below recolor similarity, and distinct prop silhouettes;
10. valid metadata schema, palettes, landmarks and per-slot prop fiction;
11. six readable sheets at the documented dimensions;
12. bounded output size;
13. byte-identical regeneration into two fresh folders, also matching the committed art;
14. seed sensitivity (all 45 art PNGs change at `seed + 1`);
15. manifest hashes and per-asset metadata.

Detailed values, including the structure-IoU matrices and floor/ceiling means,
are in `checks.json`. The check score is **not** a visual-acceptance claim.

## Integration notes (metadata only)

`environments.json` is the integration contract. Codex owns seeded selection,
native loaders, collision, performance checks, visual review and PR publication.
Suggestions recorded there, not enforced here:

- select one kit per whole run or whole tier; do not mix kits per room;
- keep landmark walls 07 and 08 adjacent;
- use `flats/01` as the primary floor, `flats/02` in service/plant rooms,
  `flats/03` as the ordinary ceiling and `flats/04` only as a lit ceiling;
- derive the kit choice from the run seed separately from map layout, so a layout
  can be replayed with a different identity.

The palettes are deliberately mid-dark with muted accents so bright binding-ring
colours remain legible. No gameplay, collision, light, audio or creature changes
are made or claimed by this kit. Props are solid landmark objects; no false door
or walk-through arch is drawn. The split-faced kiosk and the other impossible
details are visual fiction, not hidden routes.

## Honest limitations

- These assets have **not** been rendered in the native Doom/Null Run renderer or
  quantised to the game's `PLAYPAL`. Colours may shift under palette conversion;
  Codex must perform the native visual check.
- Contact sheets use nearest-neighbour upscaling. They are readable, but a screen
  preview is not a substitute for walking the level at 640x400.
- The props are drawn to the existing 96x128 sprite slot with a bottom-anchored
  base. Codex must confirm offsets, sprite alignment, collision footprint and
  placement; no new native actor IDs are introduced.
- Art is static. There is no animation, strobing, bloom, reflection or portal.
- `checks.py` proves structural properties, not artistic quality. Visual
  acceptance remains a human/Codex decision.
- This kit does not contain engine code, map geometry, audio, creatures or the
  rest of Null Run. Existing projects, engine sources and upstream assets retain
  their own authorship and licenses.

## Credits

See `CREDITS.md`. In short: creative direction and project by Josiah Alan-Lee;
model-assisted procedural code and art by DeepSeek; native integration and
review by Codex. The 128/64/96 slot conventions follow the reviewed Threshold kit,
but every pixel in this folder is newly drawn by `art.py`.
