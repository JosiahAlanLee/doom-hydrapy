# Null Run - original weapon and hand art bank v1

Seven functional slots, original industrial-occult instruments and one coherent glove/sleeve design.
Generated on CPU from `generate_weapons.py`; no IWAD pixels, no Freedoom/Doom recolours, no external images.

## Contents

- `frames/<slot>/` - 8 RGBA body frames per slot, 640x400, bottom-half view sprite.
- `flashes/` - 14 separate RGBA discharge overlays (2 per slot), pre-aligned to fire frames.
- `icons/` - 7 original 96x64 pickup icons.
- `sheets/` - per-slot contact sheets, flash sheet, icon sheet, master sheet and
  a fire-composite preview that stacks each body fire frame with its overlay.
- `manifest.json` - roles, timings, poses, offsets, bboxes, muzzle points, safe region.
- `materials.json`, `geometry.json` - palette and construction source data.
- `PROVENANCE.md`, `INTEGRATION.md`, `validation_report.json`, `SHA256SUMS`.
- `SHA256SUMS` covers every artefact except itself and `validation_report.json`
  (the report is written after the sums and records the validation run).

## Regenerate

```
/home/echevarian/miniconda3/envs/hydrapy/bin/python generate_weapons.py --out .
/home/echevarian/miniconda3/envs/hydrapy/bin/python validate.py
```

## Slots

| slot | name | frames | notes |
|---|---|---|---|
| melee | Fathom Hook | 8 | Surveyor's rule shaft, brass plumb counterweight, honed billhook; oxblood wrap; bone inlay. |
| sidearm | Registrar | 8 | Rivet sidearm: gunmetal slide, brass register plate, vial sight, oxblood grip. |
| scattergun | Transit-12 | 8 | Pump scattergun built from a surveyor's level: walnut pump, octagonal barrel, brass level vial. |
| repeater | Comptroller | 8 | Adding-machine repeater: paper feed, typebar fins, cooling rings, brass carry handle. |
| launcher | Plumb Bombard | 8 | Breech mortar / theodolite hybrid: wide brass-ringed tube, spirit level, side shell rack. |
| projector | Aethometer | 8 | Aether projector: brass coils, glass condenser, pressure gauge, forbidden green discharge. |
| heavy | Hymnodyne | 8 | Heavy ritual instrument: five organ pipes on a brass hub, bone mouths, censer chain, winding crank. |

## Frame timing (all slots)

| state | ms | role |
|---|---|---|
| idle | 900 | ready loop |
| raise_low / raise_mid | 90 + 90 | raise; play low then mid, then idle |
| fire_peak / fire_settle | 60 + 80 | recoil, overlay flash A then B |
| recover | 110 | return to idle |
| reload_a / reload_b | 240 + 300 | cycle, pump, feed or breech depending on slot |

Melee substitutes windup (120), impact (90, spark A), follow (160, spark B), recover (220), guard (600).
Per-slot roles and exact timings are in `manifest.json`.

## Safe view

Body frames leave x 220..420, y 40..180 empty; muzzle/pipe tips only enter y>=190 inside x 250..440.
Idle bodies sit broadly below y=240. Flashes are allowed above that, as overlays.

## Limits

- Painted noise is sampled in screen space, so its grain is fixed in the frame rather than stuck to each surface.
- Poses are baked 2D approximations of a 3D view; part animation uses small translations, not true articulation.
- Contact sheets are for review; the individual frames are the deliverable.
- No engine integration or ZScript API testing was done. See INTEGRATION.md.
