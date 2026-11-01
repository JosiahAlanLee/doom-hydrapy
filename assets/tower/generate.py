#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Deterministic generator for the Null Run tower environment bank.

    PYTHONDONTWRITEBYTECODE=1 python generate.py --out . --seed 20261031

Writes original bitmap art, six mob identities (A/B atlases), a 3D OBJ+MTL kit,
vertical-layout tables, adaptive music profile proposals, contact sheets, the
metadata contract and a SHA256 manifest.  No engine file is read or written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import kit_common as K
import kit_art as A
import kit_mobs as M
import kit_3d as T
import kit_layouts as L
import kit_music as MU

ROOT = Path(__file__).resolve().parent
DEFAULT_SEED = K.DEFAULT_SEED


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + '\n')


def write_art(out, seed):
    art = out / 'art'
    sheets = out / 'sheets'
    sheets.mkdir(parents=True, exist_ok=True)
    for si, sid in enumerate(K.SET_IDS):
        walls = [fn(K.asset_seed(seed, si, 1, i)) for i, fn in enumerate(A.WALLS[sid], 1)]
        flats = [fn(K.asset_seed(seed, si, 2, i)) for i, fn in enumerate(A.FLATS[sid], 1)]
        props = {slot: A.safe_prop(A.PROPS[sid][slot](K.asset_seed(seed, si, 3, i)))
                 for i, slot in enumerate(K.PROP_SLOTS, 1)}
        for i, tile in enumerate(walls, 1):
            p = art / sid / 'walls' / f'{i:02d}.png'
            p.parent.mkdir(parents=True, exist_ok=True)
            tile.save(p)
        for i, tile in enumerate(flats, 1):
            p = art / sid / 'flats' / f'{i:02d}.png'
            p.parent.mkdir(parents=True, exist_ok=True)
            tile.save(p)
        for slot, tile in props.items():
            p = art / sid / 'props' / f'{slot}.png'
            p.parent.mkdir(parents=True, exist_ok=True)
            tile.save(p)
        meta = dict(K.SETS[sid])
        meta['palette'] = K.PALETTES[sid]
        A.compose_kit_sheet(sid, walls, flats, props, meta, seed, sheets / f'{sid}-kit.png')
        A.compose_tiling_sheet(sid, walls, flats, meta, seed, sheets / f'{sid}-tiling.png')
    return {'sets': list(K.SET_IDS), 'walls_per_set': 8, 'flats_per_set': 4, 'props_per_set': 3}


def write_mobs(out, seed):
    mobs = out / 'mobs'
    sheets = out / 'sheets'
    sheets.mkdir(parents=True, exist_ok=True)
    atlases = {}
    for si, sid in enumerate(K.SET_IDS):
        for ri, role in enumerate(K.MOB_ROLES):
            for vi, variant in enumerate('AB'):
                atlas = M.build_atlas(sid, role, variant, seed)
                p = mobs / sid / f'{role}_{variant}.png'
                p.parent.mkdir(parents=True, exist_ok=True)
                atlas.save(p)
                atlases[(sid, role, variant)] = atlas
        M.compose_mob_sheet(sid, {(r, v): atlases[(sid, r, v)] for r in K.MOB_ROLES for v in 'AB'},
                            K.MOBS[sid], seed, sheets / f'{sid}-mobs.png')
    # encounters contract
    families = {
        'latchwing': ('Existing class 15 CYBR family: telegraphed locked-direction dash. '
                      'The design art uses it unchanged.'),
        'relay_choir': ('Existing class 16 PAIN family: anchored telegraphed slow three-projectile '
                        'fan. The design art uses it unchanged.'),
    }
    doc = {
        'format': 'nullrun-environment-mobs-1',
        'source_seed': int(seed),
        'license': K.LICENSE,
        'title': 'Null Run tower signature mobs: six original identities',
        'behavior_families': families,
        'notes': [
            'ART ONLY. Six new identities use the two existing behavior family identifiers; no new AI, actor IDs, frame mapping, projectiles or mechanics are introduced.',
            'A and B are two structural variants of the same identity and behavior family; they are not recolours.',
            'Every atlas is 512x768 RGBA: four columns x six rows of 128x128 cells, rows idle/walk/warn/attack/hurt/death, frame 23 a corpse.',
            'Proposed vertical behaviour is marked unimplemented in each identity; Codex owns behavior, frame mapping, collision and visual validation.',
            'The 128 px atlas and y=120 floor anchor follow the reviewed native mob-kit convention.',
        ],
        'sets': {},
    }
    for sid in K.SET_IDS:
        doc['sets'][sid] = {}
        for role in K.MOB_ROLES:
            m = K.MOBS[sid][role]
            doc['sets'][sid][role] = {
                'id': m['id'], 'name': m['name'], 'description': m['description'],
                'variant_a': m['variant_a'], 'variant_b': m['variant_b'],
                'tells': m['tells'], 'counterplay': m['counterplay'],
                'behavior_family': role,
                'warning_notes': m['tells'],
                'limits': ('Existing ' + role + ' family only: latchwing class 15 CYBR telegraphed '
                           'locked-direction dash, or relay_choir class 16 PAIN anchored slow '
                           'three-projectile fan. No new AI, actor ID or mechanics. Codex owns '
                           'behavior, labels and native frame mapping.'),
                'atlas': f'mobs/{sid}/{role}_A.png',
                'atlas_a': f'mobs/{sid}/{role}_A.png',
                'atlas_b': f'mobs/{sid}/{role}_B.png',
                'vertical_behavior_proposal': {
                    'status': 'PROPOSED, NOT IMPLEMENTED',
                    'proposal': m['vertical_proposal'],
                    'requires': ['new navigation/ledge queries', 'new lift state handling where named',
                                 'vertical projectile/line-of-fire checks where named',
                                 'Codex review before any gameplay claim'],
                },
            }
    _write_json(out / 'encounters.json', doc)
    return doc


def write_environments(out, seed):
    doc = {
        'format': 'nullrun-environment-kit-1',
        'source_seed': int(seed),
        'license': K.LICENSE,
        'title': 'Null Run tower environment kits: Ashbell Foundry, Boneglass Conservatory, Skyhotel Service Well',
        'paths': {
            'wall': 'art/{set_id}/walls/{index:02d}.png',
            'flat': 'art/{set_id}/flats/{index:02d}.png',
            'prop': 'art/{set_id}/props/{slot}.png',
            'kit_sheet': 'sheets/{set_id}-kit.png',
            'tiling_sheet': 'sheets/{set_id}-tiling.png',
            'mob_atlas': 'mobs/{set_id}/{role}_{variant}.png',
            'props3d_root': 'props3d/',
        },
        'seam_behavior': {
            'walls': ('All eight wall tiles are RGB 128x128 and seamless on both axes. Opposite '
                      'edge rows and columns are exactly equal. Tiles 07 and 08 are landmark '
                      'accent panels; each wraps independently and the pair is an authored '
                      'adjacent motif, not a continuous split image.'),
            'flats': ('All four flats are RGB 64x64 and seamless on both axes. Opposite edge '
                      'rows and columns are exactly equal.'),
            'props': ('All props are RGBA 96x128 cut-outs with at least three transparent '
                      'pixels on every edge and feet/bases at the bottom. They are not tiled '
                      'and have no opaque rectangular backdrop.'),
        },
        'selection': {
            'notes': ('Suggestions only. Codex owns seeded selection and native integration. Use '
                      'one kit as a whole-run or whole-tier identity; do not mix kits per room. '
                      'Keep walls 07 and 08 together.'),
            'suggested_cycle': list(K.SET_IDS),
            'suggested_seed_use': ('Derive the set from the run seed as a separate choice from '
                                   'map layout, so the same layout can be replayed with a different kit.'),
        },
        'floor_variation': {
            'notes': ('Metadata only; Codex implements any variation. Flats 01-04 are a complete '
                      'floor/ceiling set and should not be mixed with another kit.'),
            'rules': ['flats/01 is the primary floor.',
                      'flats/02 is the utility or service floor for plant rooms, trenches and back-of-house.',
                      'flats/03 is the ordinary ceiling.',
                      'flats/04 is the lit or fixture ceiling; it is never a floor.',
                      'Vary floors by room function, not by per-tile random substitution.'],
        },
        'integration_status': {
            'native_loader': ('The reviewed rogue/environments.py PACK_IDS tuple and catalogue '
                              'length check currently name the three previously reviewed sets. '
                              'Codex must add these IDs and MOB/3D wiring before native loading.'),
            'roles_preserved': ['service_lamp', 'cable_shrine', 'directory_sign',
                                'latchwing', 'relay_choir'],
            'engine_changed': False,
        },
        'sets': [],
    }
    for sid in K.SET_IDS:
        meta = K.SETS[sid]
        doc['sets'].append({
            'id': sid, 'name': meta['name'], 'description': meta['description'],
            'palette': K.PALETTES[sid],
            'landmark': meta['landmark'],
            'props': meta['props'],
            'gameplay_notes': meta['gameplay_notes'],
            'impossible_detail': meta['impossible_detail'],
            'verticality': meta['verticality'],
            'wall_roles': list(K.WALL_ROLES),
            'flat_roles': list(K.FLAT_ROLES),
            'seam_behavior': {
                'walls_01_08': 'seamless both axes; exact opposite-edge equality',
                'flats_01_04': 'seamless both axes; exact opposite-edge equality',
                'props': 'RGBA cut-out, transparent margin, bottom anchored, not tiled',
            },
            'palette_note': ('Colours are separated by hue and value across the three sets. '
                             'They are not guaranteed to survive Freedoom palette conversion '
                             'without review; Codex must perform the native palette check.'),
        })
    _write_json(out / 'environments.json', doc)
    return doc


def write_layouts(out, seed):
    _write_json(out / 'vertical_layouts.json', L.document(seed))
    (out / 'LAYOUTS.md').write_text(L.markdown(seed))


def write_music(out):
    return MU.write_profiles(out)


def write_credits(out):
    text = '''# Credits and license

License: **GPL-2.0-or-later** for the source, metadata, generated PNG art,
OBJ/MTL meshes and contact sheets in this folder. The rest of Null Run retains
its own licenses and notices; nothing here re-licenses existing game assets.

- Creative direction and project: Josiah Alan-Lee.
- Procedural code, bitmap art, mobs, 3D sources and music profile proposals:
  DeepSeek, for the 2026-10-31 tower environment job.
- Native integration, engine review, palette/render acceptance and PR
  publication: Codex.
- The 128 px wall, 64 px flat, 96x128 prop and 512x768 mob-atlas conventions
  follow the reviewed native Null Run kits; every pixel and triangle in this
  folder is newly generated by the scripts here.

No commercial Doom assets, no copied game models, no sampled textures, no
fonts inside the game assets, and no engine code are included.
'''
    (out / 'CREDITS.md').write_text(text)


def write_readme(out, seed):
    lines = [
        '# Null Run tower environment bank',
        '',
        'Three original tower environments for the null-run direction: **Ashbell Foundry**,',
        '**Boneglass Conservatory** and **Skyhotel Service Well**. Each kit is a coherent',
        'wall/flat/prop family, two signature mobs with A/B atlases, a 3D prop set, a',
        'vertical-layout design table and an adaptive music profile proposal.',
        '',
        f'Source seed: `{seed}`. License: **GPL-2.0-or-later** for this folder. No engine,',
        'map, running game or existing asset was modified.',
        '',
        '## The three environments',
        '',
        '| ID | Character | Landmark | Tower height | Signature mobs |',
        '| --- | --- | --- | --- | --- |',
        '| `ashbell_foundry` | Soot iron, firebrick, bronze, verdigris, furnace orange; casting bells and chain lifts in open shafts. | **The Ninth Bell** | 15.0 m / 6 levels | Chain Hound, Pouring Choir |',
        '| `boneglass_conservatory` | Bone-white tile, black peat, pale fungus, root cages and descending canopy; very creepy through silhouette and negative space. | **The Root Cage** | 15.0 m / 6 levels | Root Stilt, Hollow Nurse |',
        '| `skyhotel_service_well` | Blue-grey night, rain glass, dirty amber, staggered balconies around a deep service atrium. | **The 33rd Floor Lift** | 18.0 m / 7 levels | Night Porter, Call-Bell Choir |',
        '',
        'The three layouts are deliberately different: foundry is a central casting shaft with',
        'chain galleries; conservatory is a glasshouse atrium with organic planter shelves;',
        'skyhotel is an orthogonal, staggered room stack around a service well.',
        '',
        '## Folder contents',
        '',
        '```',
        'art/<env>/walls/01..08.png       128x128 RGB, seamless both axes',
        'art/<env>/flats/01..04.png       64x64 RGB, seamless both axes',
        'art/<env>/props/*.png            96x128 RGBA: service_lamp, cable_shrine, directory_sign',
        'mobs/<env>/<role>_A.png          512x768 RGBA atlas',
        'mobs/<env>/<role>_B.png          second structural variant',
        'props3d/<env>/*.obj,*.mtl,*.png  3 setting props per environment',
        'props3d/shared/*                  stair_flight, stair_landing, guardrail',
        'sheets/*                         kit, tiling, mob, 3D and overview contact sheets',
        'environments.json                nullrun-environment-kit-1 contract',
        'encounters.json                  nullrun-environment-mobs-1 contract',
        'props3d.json                     3D bounds, triangles, textures, collision proxies',
        'vertical_layouts.json / LAYOUTS.md  physical tower design tables',
        'music_profiles/*.json            adaptive composer profile proposals',
        'manifest.json                    SHA256 of generated files and source modules',
        '```',
        '',
        'Wall roles are `01 primary`, `02 relief/panel`, `03 structural`, `04 service hardware`,',
        '`05 shutter/window`, `06 wayfinding/accent`, `07 landmark A`, `08 landmark B`. Flat',
        'roles are `01 primary floor`, `02 utility floor`, `03 ordinary ceiling`, `04 lit ceiling`.',
        '',
        '## Generate',
        '',
        '```sh',
        'cd /home/echevarian/dev/shared/deepseek/nullrun-tower-environments-20261031',
        'PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python generate.py --out . --seed 20261031',
        '```',
        '',
        'A fresh folder receives the 45 art PNGs, 12 mob atlases, 12 OBJ/MTL/texture sets,',
        '15 contact sheets, all JSON/Markdown contracts and `manifest.json`.',
        'The generator uses local `random.Random` / NumPy generators and stable hashes only.',
        '',
        '## 3D kit',
        '',
        'Coordinates are **Z-up, metres**, with the requested conversion **1 m = 64 Doom units**.',
        'Each mesh is a simple UV-mapped OBJ with an adjacent 256x256 procedural texture and an',
        'MTL that references it through `map_Kd`. Meshes are under 5000 triangles each; the JSON',
        'records mesh-derived bounds, triangle/vertex counts, UV ranges and simple collision',
        'proxies. UVs follow the standard OBJ convention (V=0 at the bottom of the map_Kd image).',
        'The shared stair uses eight 12-unit risers (1.5 m) and a landing; two flights',
        'plus a landing make one 3.0 m storey. glTF was omitted rather than growing a new export',
        'framework, as the brief permits.',
        '',
        'The 3D sheets are software orthographic previews (flat-shaded, painter-sorted), not',
        'engine renders. They are included so silhouettes from above and below can be inspected.',
        'No prop is a plain recoloured box: every silhouette has a distinct primary mass and at',
        'least one asymmetric feature (cage, bell, spout, rose, wheel, stepped shelf).',
        '',
        '## Mobs',
        '',
        'Each environment has two identities. A and B are structural variants (extra legs, split',
        'heads, different crown/muzzle/tail or coat/case construction), not recolours. All atlases',
        'are 512x768 RGBA, four columns by six rows, rows `idle/walk/warn/attack/hurt/death`;',
        'frame 23 is a visible corpse. Tells and counterplay are in `encounters.json`.',
        '',
        'The six designs use the existing `latchwing` (class 15 CYBR) and `relay_choir` (class 16',
        'PAIN) adapter roles. **All proposed vertical AI is labelled `PROPOSED, NOT IMPLEMENTED`.**',
        'No working game AI, new actor ID or new projectile mechanic is claimed.',
        '',
        '## Vertical layouts',
        '',
        '`vertical_layouts.json` and `LAYOUTS.md` give the lower/middle/upper routes, an explicit',
        'stair and lift alternative, fall recovery, safe spawn, readable return path, arena/perch',
        'spacing and room-over-room uses. Each tower physically gains height: 15 m, 15 m and 18 m',
        'of real walkable floor levels, not a single tall ceiling. Required routes use stairs and',
        'static lift landings; no mandatory jumps, precision platforming or unseen hits are',
        'specified for the first pass. Native step height (16 units / 0.25 m), native',
        'player clearance/headroom (96 units / 1.5 m) and mesh collision needs are listed separately.',
        '',
        '## Music',
        '',
        '`music_profiles/*.json` are **proposals only: not rendered, not auditioned, not loaded**.',
        'They mirror the existing composer schema field-for-field. The host `PROFILE_NAMES` tuple',
        'must be extended by Codex before the existing composer can load them. There are no',
        'rendered audio files in this kit.',
        '',
        '## Integration notes (metadata only)',
        '',
        '- The reviewed native loader currently names the three earlier kit IDs; add these IDs',
        '  before loading. Keep one kit per whole run or tier; do not mix kits per room.',
        '- Keep walls 07 and 08 adjacent; use flats 01 as primary floor and 04 only as a lit ceiling.',
        '- All props remain the existing `service_lamp`, `cable_shrine`, `directory_sign` roles.',
        '- The mob atlases and 3D meshes are art/source proposals, not engine-loaded assets.',
        '- Every 3D mesh has an honest bounds entry; collision proxies are proposals and must be',
        '  converted to native sectors or source-port collision by Codex.',
        '- Bitmap props include small semi-transparent base shadows (alpha 45-62). The native',
        '  patch path treats any nonzero alpha as opaque, so Codex may threshold or drop them.',
        '',
        '## Visual review', '',
        'The 15 contact sheets in `sheets/` were reviewed locally with the image viewer available',
        'in this run: kit families, 2x2 seam proofs, mob atlases, 3D front/top/bottom previews and',
        'the overview. This is a readability/silhouette review of generated previews, not a native',
        'engine render. Codex must still walk the levels at 640x400 and check palette conversion.',
        '',
        '## Honest limitations',
        '',
        '- Not rendered in the native Doom/Null Run renderer and not quantised to `PLAYPAL`.',
        '  Palette conversion may shift colours; Codex must do the native visual/palette check.',
        '- Contact sheets use nearest-neighbour (bitmaps) or software flat shading (3D); they are',
        '  not a substitute for walking the level at native resolution.',
        '- Music profiles are written proposals only; no audio was rendered or heard.',
        '- Vertical mob behaviour is proposed only; none of it is implemented.',
        '- Checks prove structural properties, not artistic acceptance.',
        '- No engine, map, running game, existing asset or other agent output was modified.',
        '',
        '## Generate and check',
        '',
        '```sh',
        'PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python generate.py --out . --seed 20261031',
        'PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python checks.py',
        'PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python make_manifest.py',
        'PYTHONDONTWRITEBYTECODE=1 /home/echevarian/miniconda3/envs/hydrapy/bin/python checks.py',
        '```',
        '',
    ]
    (out / 'README.md').write_text('\n'.join(lines))


def write_overview(out):
    from PIL import Image, ImageDraw, ImageFont
    try:
        title_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 21)
        small_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 11)
        body_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)
    except Exception:
        title_font = small_font = body_font = ImageFont.load_default()

    def wrap(text, width):
        words, lines, line = text.split(), [], ''
        for word in words:
            if len(line) + len(word) + 1 > width:
                lines.append(line)
                line = word
            else:
                line = (line + ' ' + word).strip()
        if line:
            lines.append(line)
        return lines

    W, H = 1500, 850
    sheet = Image.new('RGB', (W, H), (18, 20, 24))
    pen = ImageDraw.Draw(sheet)
    pen.text((24, 16), 'Null Run tower environment bank - overview', font=title_font,
             fill=(240, 234, 220))
    for i, sid in enumerate(K.SET_IDS):
        x0 = 24 + i * 492
        meta = K.SETS[sid]
        pen.text((x0, 54), meta['name'], font=title_font, fill=(238, 214, 150))
        pen.text((x0, 82), f'{meta["verticality"]["height_m"]:.1f} m / '
                 f'{meta["verticality"]["levels"]} levels', font=small_font, fill=(190, 200, 198))
        wall = Image.open(out / 'art' / sid / 'walls' / '07.png').resize((300, 300), Image.NEAREST)
        sheet.paste(wall, (x0, 106))
        pen.text((x0, 410), 'landmark wall 07', font=small_font, fill=(200, 206, 204))
        prop = Image.open(out / 'art' / sid / 'props' / 'directory_sign.png')
        bg = Image.new('RGBA', (150, 200), (44, 48, 54, 255))
        bg.alpha_composite(prop, (27, 36))
        sheet.paste(bg.convert('RGB'), (x0 + 320, 106))
        pen.text((x0 + 320, 310), 'directory_sign', font=small_font, fill=(200, 206, 204))
        pen.text((x0 + 320, 330), 'tower prop kit:', font=small_font, fill=(160, 170, 168))
        for k, pid in enumerate(T.BUILDERS[sid]):
            pen.text((x0 + 320, 346 + k * 15), f'- {pid}', font=small_font,
                     fill=(196, 202, 200))
        pen.text((x0, 436), meta['landmark']['name'], font=title_font, fill=(236, 218, 162))
        y = 468
        for line in wrap(meta['description'], 60)[:4]:
            pen.text((x0, y), line, font=body_font, fill=(184, 190, 188))
            y += 16
        # idle frame strip at native 64 px per cell: 4 frames = 256 x 64
        atlas = Image.open(out / 'mobs' / sid / 'latchwing_A.png').crop((0, 0, 512, 128))
        bg2 = Image.new('RGBA', atlas.size, (44, 48, 54, 255))
        bg2.alpha_composite(atlas)
        sheet.paste(bg2.convert('RGB').resize((470, 118), Image.LANCZOS), (x0, y + 8))
        pen.text((x0, y + 128), 'latchwing A: idle frames 0-3', font=small_font,
                 fill=(200, 206, 204))
        y += 150
        for role in K.MOB_ROLES:
            m = K.MOBS[sid][role]
            pen.text((x0, y), f'{role}: {m["name"]}', font=small_font, fill=(214, 196, 150))
            y += 16
        pen.text((x0, y + 4), 'music: ' + MU.PROFILES[sid]['title'] + ' (proposal)',
                 font=small_font, fill=(186, 196, 194))
    pen.text((24, H - 30), 'Bitmap tiles are nearest-neighbour previews. 3D and music proposals are '
             'separate; see README.md and LAYOUTS.md.', font=small_font, fill=(150, 158, 158))
    sheet.save(out / 'sheets' / 'overview.png')


def _source_files():
    base = Path(__file__).resolve().parent
    names = ['generate.py', 'kit_common.py', 'kit_art.py', 'kit_mobs.py', 'kit_3d.py',
             'kit_layouts.py', 'kit_music.py', 'make_manifest.py', 'checks.py']
    out = []
    for name in names:
        path = base / name
        if path.is_file():
            data = path.read_bytes()
            out.append({'path': name, 'sha256': hashlib.sha256(data).hexdigest(),
                        'bytes': len(data)})
    return out


def build_manifest(root):
    root = Path(root)
    files = []
    for path in sorted(root.rglob('*'), key=lambda p: p.relative_to(root).as_posix()):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        parts = rel.parts
        if any(part.startswith('_repro') or part == '__pycache__' or part.startswith('.check-tmp')
               for part in parts):
            continue
        if rel.as_posix() in ('manifest.json', 'checks.json', 'VALIDATION.md'):
            continue
        if path.suffix.lower() not in ('.json', '.md', '.png', '.obj', '.mtl'):
            continue
        data = path.read_bytes()
        files.append({'path': rel.as_posix(), 'sha256': hashlib.sha256(data).hexdigest(),
                      'bytes': len(data)})
    bundle = hashlib.sha256(''.join(f"{f['path']} {f['sha256']}\n" for f in files).encode()).hexdigest()
    sources = _source_files()
    source_bundle = hashlib.sha256(''.join(f"{f['path']} {f['sha256']}\n" for f in sources).encode()).hexdigest()
    return {
        'format': 'nullrun-tower-manifest-1',
        'source_seed': DEFAULT_SEED,
        'license': K.LICENSE,
        'algorithm': 'sha256',
        'scope': ('Generated content: metadata, bitmap art, mob atlases, 3D OBJ/MTL/textures, '
                  'sheets and documents, relative to the output root. Excludes manifest.json, '
                  'checks.json, VALIDATION.md and temporary folders. Source modules are hashed '
                  'separately so a fresh output folder produces the same manifest.'),
        'seeds': {
            'art': DEFAULT_SEED, 'mobs': DEFAULT_SEED, 'props3d': DEFAULT_SEED,
            'layouts': DEFAULT_SEED, 'music': DEFAULT_SEED,
            'derivation': 'sha256-based asset_seed(seed, set, kind, index); no Python hash()',
        },
        'file_count': len(files), 'total_bytes': sum(f['bytes'] for f in files),
        'artifact_bundle_sha256': bundle,
        'source_count': len(sources), 'source_bundle_sha256': source_bundle,
        'files': files, 'sources': sources,
    }


def write_manifest(out, seed):
    # keep the documented seed in the manifest generator-independent of argparse
    data = build_manifest(out)
    data['source_seed'] = int(seed)
    data['seeds'] = {k: int(seed) for k in ('art', 'mobs', 'props3d', 'layouts', 'music')}
    data['seeds']['derivation'] = 'sha256-based asset_seed(seed, set, kind, index); no Python hash()'
    _write_json(out / 'manifest.json', data)
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--out', default='.', help='output folder (default: current folder)')
    parser.add_argument('--seed', type=int, default=DEFAULT_SEED, help='stable source seed')
    args = parser.parse_args(argv)
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    seed = int(args.seed)
    write_art(out, seed)
    write_mobs(out, seed)
    write_environments(out, seed)
    props_doc = T.build_all(out, seed)
    _write_json(out / 'props3d.json', props_doc)
    write_layouts(out, seed)
    write_music(out)
    write_credits(out)
    write_readme(out, seed)
    write_overview(out)
    data = write_manifest(out, seed)
    print(f'wrote {data["file_count"]} files ({data["total_bytes"]} bytes) to {out}')
    print(f'manifest bundle {data["artifact_bundle_sha256"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
