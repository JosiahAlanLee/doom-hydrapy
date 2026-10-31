# Null Run environment kits - credits, license and source trail

## People and provenance

- **Creative direction and project:** Josiah Alan-Lee. The three kit directions,
  the municipal/institutional horror tone, the demand for distinct run identities
  and the native-game context come from Josiah's project.
- **Model-assisted procedural source and art:** DeepSeek, running through the
  Claude Code headless harness on the job delegated by Codex
  (`20261031-010111-deepseek-nullrun-environments`). The generator, the 45 art
  PNGs, the six contact/tiling sheets, `environments.json` and the checks were
  produced in that run.
- **Integration, seeded selection, collision, performance checks, visual review
  and publication:** Codex. Those steps are deliberately outside this kit and are
  not claimed here.
- **Earlier Threshold kit:** the reviewed Threshold environment kit established
  the engine-facing conventions used here: 128x128 wall textures, 64x64 flats,
  96x128 RGBA props, the `service_lamp` / `cable_shrine` / `directory_sign` slot
  names and the GPL-2.0-or-later project context. That earlier kit is a separate
  work; this folder contains new code and new pixels, not a copy of it.

## What was original in this run

- Every pixel in `art/` and `sheets/` is drawn by `art.py` from geometric
  primitives, periodic value fields and local seeded randomness.
- No existing game sprite, texture, font, logo, UI or map is sampled, traced,
  recoloured or composited into the art.
- The contact sheets use Pillow's bundled default label font for sheet labels
  only. No font file is shipped in the game kit and no font is drawn into the
  wall/flat/prop art.
- The written metadata, checks and documentation were written for this kit.

## License

This kit - `art.py`, `checks.py`, `make_manifest.py`, `environments.json`,
`README.md`, `CREDITS.md`, `art/**` and `sheets/**` - is released as
**GPL-2.0-or-later**. SPDX headers are present in the Python sources. The full
GPL-2.0 text is available from the Free Software Foundation at
<https://www.gnu.org/licenses/old-licenses/gpl-2.0.html> and in the parent
project's `LICENSE` file. No attempt is made to relicense the engine, Freedoom,
HydraPy, DSP_Emulation or any other existing project; their own notices continue
to apply.

The generated PNGs are original raster outputs, not copies of any upstream art.
The use of Pillow (HPND) and numpy (BSD-3-Clause) as build tools does not change
the license of this kit's original output.

## Honest limits of the credit

This is an environment-art kit, not the game. It does not include or assert
ownership of the Doom engine, doomgeneric, Chocolate Doom, Freedoom, the Null Run
maps, the seven-tier campaign, the binding-ring control code, the creature art,
the music or the native renderer. Native rendering, palette conversion,
placement, collision and final visual acceptance remain with Codex and Josiah.
