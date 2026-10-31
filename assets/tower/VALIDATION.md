# Mechanical validation report

Result: **39/39 checks passed** in 6.77 s.
Failed: none.

These are structural/deterministic checks, not an artistic or native-render acceptance claim.

## Commands run
```sh
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python generate.py --out . --seed 20261031
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python checks.py
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python make_manifest.py
PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python checks.py
```

Visual review: The 15 contact sheets were viewed locally with the image viewer in this run; this is not a native-engine render. Codex must still perform the native 640x400 and palette check.

| Check | Result | Detail |
| --- | --- | --- |
| `art_count_45` | PASS | 45 art PNGs; missing=[]; extra=[] |
| `mob_atlas_count_12` | PASS | 12 mob atlases; expected 12 |
| `mesh_obj_count_12` | PASS | 12 OBJ meshes; expected 12 |
| `sheet_count_15` | PASS | 15 contact sheets; expected 15 |
| `metadata_present` | PASS | missing metadata: [] |
| `bounded_output_size` | PASS | 6.96 MB output (< 50 MB) |
| `image_dimensions_modes` | PASS | walls 128x128 RGB, flats 64x64 RGB, props 96x128 RGBA |
| `atlas_dimensions_modes` | PASS | all 12 atlases are 512x768 RGBA |
| `sheet_modes_sizes` | PASS | 15 sheets are RGB and at least 400x400 |
| `seams_exact` | PASS | opposite edge rows and columns match exactly for 36 walls/flats |
| `seams_documented` | PASS | environments.json documents wall/flat/prop seam behaviour |
| `props_alpha_bounds_anchor` | PASS | all 9 props are bottom-anchored RGBA cut-outs with 3 px margins and no backdrop |
| `assets_nonblank_contrast` | PASS | 45 art PNGs are nonblank with a minimum colour and contrast floor |
| `assets_unique` | PASS | 45/45 unique art PNG hashes |
| `atlases_unique` | PASS | 12/12 unique atlas hashes |
| `palette_separation_grey_proxy` | PASS | set mean RGB separation > 25 and wall structure IoU mean <= 0.55/max <= 0.80 |
| `inter_set_structure` | PASS | wall 0.185/0.196; flat 0.213/0.235; prop 0.378/0.395 |
| `atlas_layout_24_padding_anchor` | PASS | 288 cells: 24 per atlas, >=3 px padding, exact y=120 floor anchor, crisp alpha |
| `atlas_frames_unique_animated` | PASS | all 24 cells unique; every consecutive pair changes >=100 px; minimum 153 |
| `atlas_frame23_corpse` | PASS | all 12 frame-23 cells contain a visible corpse |
| `atlas_ab_structural_variants` | PASS | A/B idle silhouettes differ structurally (IoU <= 0.92) |
| `atlas_six_identities_distinct` | PASS | all six identities have distinct idle silhouettes (IoU <= 0.80) |
| `mesh_parse_counts` | PASS | 12 OBJ files parse as triangles; face/vertex/UV/normal counts and finite values are valid |
| `mesh_bounds_triangles_honest` | PASS | mesh-derived bounds match props3d.json and every mesh is <5000 triangles |
| `mesh_texture_references` | PASS | every OBJ has an MTL with map_Kd and an adjacent 256x256 RGB PNG |
| `mesh_collision_metadata` | PASS | all 12 entries have finite footprint/z proxies, notes and stair/guardrail limits |
| `layouts_schema_and_tower_proof` | PASS | 3 environments; 6-7 levels; real 15/15/18 m height; routes, stairs, lifts, recovery, spawn, return, spacing and room-over-room present |
| `layouts_native_vs_mesh_constraints` | PASS | native step 16 u / headroom 96 u are kept separate from mesh 12-unit risers |
| `music_profiles_valid` | PASS | 3 profiles pass the mirrored host schema validator |
| `music_host_schema_accepts` | PASS | host validate_profile accepted all 3 proposals |
| `music_no_rendered_audio` | PASS | no rendered audio files exist; profiles are written proposals only |
| `music_proposal_status` | PASS | music_proposals.json states proposal-only, not rendered/auditioned |
| `environments_schema` | PASS | nullrun-environment-kit-1 with 3 sets, 8 wall roles, 4 flat roles and 3 prop slots |
| `encounters_schema` | PASS | 6 identities, A/B atlases, tells/counterplay and unimplemented vertical proposals |
| `props3d_schema` | PASS | Z-up metres, 1 m=64 Doom units, 9 environment + 3 shared entries, no engine-load claim |
| `reproducible_two_runs` | PASS | two fresh folders are byte-identical (120 files; 2.0s + 1.9s) |
| `matches_committed_output` | PASS | fresh generation matches committed generated files (120 files) |
| `seed_sensitivity` | PASS | seed+1 changes 45/45 art, 12/12 atlases, 12/12 textures; OBJ/MTL geometry is intentionally stable |
| `manifest_integrity` | PASS | manifest hashes 119 generated files and 9 source modules |

## Per-atlas frames

| Atlas | Unique cells | Consecutive min px | Corpse bbox | Corpse coverage |
| --- | --- | --- | --- | --- |
| `mobs/ashbell_foundry/latchwing_A.png` | 24 | 153 | (4, 94, 122, 120) | 0.114 |
| `mobs/ashbell_foundry/latchwing_B.png` | 24 | 153 | (4, 94, 122, 120) | 0.114 |
| `mobs/ashbell_foundry/relay_choir_A.png` | 24 | 153 | (22, 97, 98, 120) | 0.080 |
| `mobs/ashbell_foundry/relay_choir_B.png` | 24 | 153 | (22, 97, 98, 120) | 0.080 |
| `mobs/boneglass_conservatory/latchwing_A.png` | 24 | 153 | (20, 102, 108, 120) | 0.081 |
| `mobs/boneglass_conservatory/latchwing_B.png` | 24 | 153 | (20, 102, 108, 120) | 0.081 |
| `mobs/boneglass_conservatory/relay_choir_A.png` | 24 | 153 | (18, 98, 100, 120) | 0.089 |
| `mobs/boneglass_conservatory/relay_choir_B.png` | 24 | 153 | (18, 98, 100, 120) | 0.089 |
| `mobs/skyhotel_service_well/latchwing_A.png` | 24 | 153 | (24, 96, 112, 120) | 0.103 |
| `mobs/skyhotel_service_well/latchwing_B.png` | 24 | 153 | (24, 96, 112, 120) | 0.103 |
| `mobs/skyhotel_service_well/relay_choir_A.png` | 24 | 153 | (22, 90, 98, 120) | 0.083 |
| `mobs/skyhotel_service_well/relay_choir_B.png` | 24 | 153 | (22, 90, 98, 120) | 0.083 |

## Per-mesh validation

| Mesh | Triangles | Vertices | Bounds m (min -> max) | UV range |
| --- | --- | --- | --- | --- |
| `balcony_bay` | 252 | 756 | [-1.5, -0.62, 0.0] -> [1.5, 0.6, 3.0] | [0.03044, 0.03044]..[0.93956, 0.93956] |
| `casting_furnace` | 746 | 2238 | [-1.2, -0.7, 0.0] -> [1.76, 0.7, 3.7] | [0.03044, 0.03044]..[0.93956, 0.93956] |
| `chain_lift_cage` | 1096 | 3288 | [-0.84, -0.84, 0.0] -> [1.12, 0.84, 4.0] | [0.03044, 0.03044]..[0.93956, 0.93956] |
| `dumbwaiter_winch_head` | 580 | 1740 | [-0.75, -0.36, 0.0] -> [0.75, 0.48, 2.25] | [0.03044, 0.03044]..[0.93956, 0.93956] |
| `growth_chamber` | 336 | 1008 | [-0.7, -0.53, 0.0] -> [0.7, 0.4, 2.3] | [0.03044, 0.03044]..[0.93956, 0.93956] |
| `guardrail` | 108 | 324 | [-0.05, -0.1, 0.0] -> [2.05, 0.1, 1.12] | [0.03044, 0.03044]..[0.93956, 0.46956] |
| `root_cage_planter` | 1746 | 5238 | [-0.822038, -0.822038, 0.0] -> [0.822038, 0.822038, 3.455201] | [0.03044, 0.03044]..[0.93956, 0.93956] |
| `service_lift_car` | 188 | 564 | [-1.0, -1.015, 0.0] -> [1.0, 1.0, 2.62] | [0.03044, 0.03044]..[0.93956, 0.93956] |
| `stair_flight` | 228 | 684 | [-0.895, -0.002998, 0.0] -> [0.895, 2.44, 1.5] | [0.03044, 0.03044]..[0.93956, 0.93956] |
| `stair_landing` | 96 | 288 | [-0.9, -0.9, 0.0] -> [0.9, 0.9, 1.55] | [0.03044, 0.03044]..[0.46956, 0.93956] |
| `suspended_ninth_bell` | 1812 | 5436 | [-0.647826, -0.647826, 1.55] -> [0.9, 0.647826, 3.95] | [0.03044, 0.03044]..[0.93956, 0.93956] |
| `watering_gantry` | 788 | 2364 | [-1.52, -0.22, 0.0] -> [1.52, 0.264127, 2.58] | [0.03044, 0.03044]..[0.93956, 0.93956] |

## Reproducibility

- Two fresh generator runs were byte-identical; the committed output matches them.
- Seed + 1 changed all 45 art PNGs, all 12 mob atlases and all 12 3D textures; mesh geometry is intentionally seed-stable.
- The manifest hashes generated files and source modules separately.

## Metrics
```json
{
  "palette_separation": {
    "means": {
      "ashbell_foundry": [
        50.5,
        45.2,
        40.4
      ],
      "boneglass_conservatory": [
        137.2,
        134.6,
        122.9
      ],
      "skyhotel_service_well": [
        57.7,
        62.6,
        69.1
      ]
    },
    "pairs": [
      {
        "pair": [
          "ashbell_foundry",
          "boneglass_conservatory"
        ],
        "mean_rgb_distance": 149.39
      },
      {
        "pair": [
          "ashbell_foundry",
          "skyhotel_service_well"
        ],
        "mean_rgb_distance": 34.3
      },
      {
        "pair": [
          "boneglass_conservatory",
          "skyhotel_service_well"
        ],
        "mean_rgb_distance": 120.03
      }
    ],
    "structure": [
      {
        "pair": [
          "ashbell_foundry",
          "boneglass_conservatory"
        ],
        "wall_structure_iou_mean": 0.218,
        "max": 0.299
      },
      {
        "pair": [
          "ashbell_foundry",
          "skyhotel_service_well"
        ],
        "wall_structure_iou_mean": 0.159,
        "max": 0.204
      },
      {
        "pair": [
          "boneglass_conservatory",
          "skyhotel_service_well"
        ],
        "wall_structure_iou_mean": 0.177,
        "max": 0.205
      }
    ],
    "note": "Freedoom PLAYPAL is not present in this folder; this is a mean-RGB + high-pass structure proxy. Codex must perform the real palette conversion."
  },
  "inter_set_structure": {
    "wall_mean": 0.185,
    "wall_max": 0.196,
    "flat_mean": 0.213,
    "flat_max": 0.235,
    "prop_mean": 0.378,
    "prop_max": 0.395
  },
  "atlas_animation": {
    "min_consecutive_changed_pixels": 153,
    "unique_cells": {
      "mobs/ashbell_foundry/latchwing_A.png": 24,
      "mobs/ashbell_foundry/latchwing_B.png": 24,
      "mobs/ashbell_foundry/relay_choir_A.png": 24,
      "mobs/ashbell_foundry/relay_choir_B.png": 24,
      "mobs/boneglass_conservatory/latchwing_A.png": 24,
      "mobs/boneglass_conservatory/latchwing_B.png": 24,
      "mobs/boneglass_conservatory/relay_choir_A.png": 24,
      "mobs/boneglass_conservatory/relay_choir_B.png": 24,
      "mobs/skyhotel_service_well/latchwing_A.png": 24,
      "mobs/skyhotel_service_well/latchwing_B.png": 24,
      "mobs/skyhotel_service_well/relay_choir_A.png": 24,
      "mobs/skyhotel_service_well/relay_choir_B.png": 24
    }
  },
  "seed_sensitivity": {
    "art": [
      45,
      45
    ],
    "mobs": [
      12,
      12
    ],
    "textures": [
      12,
      12
    ],
    "seconds": 1.88
  }
}
```

## Limitations
- Structural checks only; not artistic or native-render acceptance.
- Freedoom PLAYPAL is not in this folder; palette separation uses a mean-RGB/high-pass proxy.
- Music profiles are schema proposals; no audio was rendered or auditioned.
- Vertical mob AI and moving lifts are proposals only and are not implemented.
- Visual review was performed on the generated contact sheets; Codex must still render in the native engine.
