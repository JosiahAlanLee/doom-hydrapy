# SPDX-License-Identifier: GPL-2.0-or-later
"""Shared, deterministic definitions for the Null Run tower environment bank.

No engine code, no sampled art.  Every colour, name, description and seed in
this module is original to this kit.  The 128/64/96 pixel slots and the
latchwing / relay_choir adapter roles follow the reviewed native conventions.
"""
from __future__ import annotations

import hashlib
import math
import random

DEFAULT_SEED = 20261031
LICENSE = 'GPL-2.0-or-later'
WALL_ROLES = (
    'primary wall', 'relief / panel', 'structural material', 'service hardware',
    'shutter / window', 'wayfinding / accent', 'landmark A', 'landmark B',
)
FLAT_ROLES = ('primary floor', 'utility floor', 'ordinary ceiling', 'lit ceiling')
PROP_SLOTS = ('service_lamp', 'cable_shrine', 'directory_sign')
MOB_ROLES = ('latchwing', 'relay_choir')
STATES = ('idle', 'walk', 'warn', 'attack', 'hurt', 'death')

SET_IDS = ('ashbell_foundry', 'boneglass_conservatory', 'skyhotel_service_well')

# Palettes are deliberately separated in hue and value so that a palette
# conversion cannot turn all three settings into one grey material family.
# Bellfoundry: warm soot / bronze / furnace orange with verdigris.
# Conservatory: bone white / peat / lichen / bruise purple.
# Skyhotel: blue-grey night / dirty amber / maroon / rain teal.
PALETTES = {
    'ashbell_foundry': {
        'soot': '#14161A', 'iron': '#2B2D31', 'iron_light': '#4A4D52',
        'ash': '#8E8B84', 'firebrick': '#B2755D', 'brick_dark': '#6E4436',
        'bronze': '#A66A2A', 'bronze_light': '#D29A4A',
        'verdigris': '#3F7F70', 'verdigris_light': '#6FAE97',
        'furnace': '#E0662A', 'furnace_light': '#FFB05A',
        'bone': '#D8CBB4', 'rust': '#7A3E28',
    },
    'boneglass_conservatory': {
        'bone': '#E4DFCF', 'chalk': '#CFC9B8', 'pale': '#F0ECDD',
        'lichen': '#8FA27E', 'moss': '#5C7057', 'peat': '#211D19',
        'root': '#5B4A39', 'root_light': '#8A745B', 'wet': '#47645A',
        'bruise': '#6B5A70', 'fungus': '#D7E4C4', 'glow': '#EAF6D8',
        'tin': '#7C8B82', 'iron': '#3A3B36',
    },
    'skyhotel_service_well': {
        'night': '#25313E', 'night_dark': '#161E27', 'blue': '#3E5265',
        'blue_light': '#6E8397', 'rain': '#8FA6B4', 'teal': '#47706F',
        'teal_dark': '#2C4A4C', 'amber': '#D99B3F', 'amber_light': '#F2C878',
        'maroon': '#6B3A40', 'maroon_dark': '#46262B', 'brass': '#A8834A',
        'linen': '#C7C1B1', 'carpet': '#3D4C4A',
    },
}

SETS = {
    'ashbell_foundry': {
        'name': 'ASHBELL FOUNDRY',
        'short': 'Foundry',
        'description': (
            'A vertical bell foundry inside a dead furnace stack: riveted soot iron, '
            'pale firebrick arches, oxidised bronze and verdigris chain galleries. '
            'Casting bells hang in open shafts beside black furnace mouths, and a '
            'counterweighted lift cage links suspended maintenance balconies. The '
            'building is a working machine that has been left running without anyone '
            'to pour. Every ascent is physical: stairs, ladders and a chain lift move '
            'through real floor openings, never a painted backdrop.'),
        'landmark': {
            'name': 'The Ninth Bell',
            'description': (
                'A cracked ninth casting bell hangs from a crown gimbal in the open '
                'lift shaft, flanked by a bronze cage and a counterweight chain. The '
                'bell crown and the lift cage are authored as adjacent landmark '
                'panels; the bell is the thing the whole tower is arranged around.'),
            'walls': [7, 8],
        },
        'props': {
            'service_lamp': {
                'display_name': 'Crucible Ladle Lamp',
                'description': (
                    'A three-legged iron hook stand holding a bronze ladle cup of '
                    'standing furnace light, with a short chain, ash tray and a '
                    'heat-scorched shade. Small freestanding floor fixture.'),
                'silhouette': 'tripod, curved hook, deep cup; reads as a ladle, not a box.',
            },
            'cable_shrine': {
                'display_name': 'Chain Boss Shrine',
                'description': (
                    'A squat cast-iron chain drum with a coiled chain mound, a hanging '
                    'hook and counterweight, three bronze studs and a grease pot. '
                    'Freestanding foundry utility object.'),
                'silhouette': 'low drum with an asymmetric chain coil and a hanging hook.',
            },
            'directory_sign': {
                'display_name': 'Bell Order Board',
                'description': (
                    'A two-post cast frame carrying a tilted soot board with three '
                    'bell-shaped order plaques of different sizes, a bronze direction '
                    'arrow and a top chain. Landmark wayfinding object with solid feet.'),
                'silhouette': 'tall A-frame with three hanging bell plaques.',
            },
        },
        'gameplay_notes': (
            'Cosmetic material and architecture guidance only. The kit makes no '
            'collision, light, AI or audio claim. Warm furnace accents are sparse so '
            'bright binding rings and projectiles stay legible. Use one kit per run.'),
        'impossible_detail': (
            'The ninth bell has a casting seam on both faces and no clapper; the lift '
            'counterweight rises when the cage is empty. Visual fiction only.'),
        'verticality': {
            'levels': 6, 'storey_m': 3.0, 'height_m': 15.0,
            'primary_route': 'stair and chain lift',
            'open_volume': 'central casting shaft through levels 1-5',
            'fall_recovery': 'staged chain galleries and a sand bed at the pit',
        },
    },
    'boneglass_conservatory': {
        'name': 'BONEGLASS CONSERVATORY',
        'short': 'Conservatory',
        'description': (
            'An abandoned indoor woodland nursery grown past its glass: bone-white '
            'tiled walls, black peat beds, pale fungal trees, root cages and watering '
            'gantries under a dead glasshouse roof. Vegetation descends from the floors '
            'above in long curtains, and every growth chamber is empty in a way that '
            'looks recently vacated. Unease is carried by silhouette and negative '
            'space rather than gore: a pale trunk where a person should be, a cage of '
            'roots around nothing, a watering arm still pointing at a dry bed.'),
        'landmark': {
            'name': 'The Root Cage',
            'description': (
                'A hanging cage woven from white roots around a black vertical void, '
                'suspended beneath the descending canopy. The paired landmark panels '
                'are the cage (07) and the canopy curtain with its growth lamps (08). '
                'The cage is empty; the roots continue upward past the frame.'),
            'walls': [7, 8],
        },
        'props': {
            'service_lamp': {
                'display_name': 'Glow Pod Nursery Lamp',
                'description': (
                    'A curved root stem rising from a mossy ceramic pot, ending in a '
                    'drooping translucent seed pod with a pale fungal glow, a copper '
                    'tag and loose tendrils. Small organic floor fixture.'),
                'silhouette': 'single curved stem and a hanging pod; no straight post.',
            },
            'cable_shrine': {
                'display_name': 'Root-Bound Standpipe',
                'description': (
                    'A verdigris watering standpipe with a cross tap, a wide watering '
                    'rose and a pressure bulb, half swallowed by white roots and a '
                    'black peat mound. Freestanding nursery utility object.'),
                'silhouette': 'cross-shaped pipe, round rose, irregular root mass.',
            },
            'directory_sign': {
                'display_name': 'Seed Index Cradle',
                'description': (
                    'A leaning bone trellis lectern with a shallow black seed tray, '
                    'three hanging seed labels and root-wrapped legs. Landmark indexing '
                    'object with a solid base.'),
                'silhouette': 'slanted trellis with a cradle of tags, not a flat board.',
            },
        },
        'gameplay_notes': (
            'Cosmetic material and architecture guidance only. Pale surfaces are kept '
            'mid-value so bright binding rings remain visible; no bloom, fog volume or '
            'animated growth is implied. Use one kit per run.'),
        'impossible_detail': (
            'The root cage has no entrance and its shadow falls upward onto the canopy. '
            'The watering rose drips into a bed that is already full. Visual fiction.'),
        'verticality': {
            'levels': 6, 'storey_m': 3.0, 'height_m': 15.0,
            'primary_route': 'root stair and counterweight gantry',
            'open_volume': 'glasshouse atrium through levels 2-5',
            'fall_recovery': 'soft peat beds and staggered planter shelves',
        },
    },
    'skyhotel_service_well': {
        'name': 'SKYHOTEL SERVICE WELL',
        'short': 'Skyhotel',
        'description': (
            'The back-of-house innards of a late-night observation hotel: staggered '
            'room balconies around a deep service atrium, luggage dumbwaiters, rain-'
            'streaked glass, blue-grey night and dirty amber signs. Guest floors are '
            'readable as stacked rectangles while the service core cuts a separate '
            'vertical route through them. The architecture is deliberately orthogonal '
            'and staggered, not radial: landings step around corners, balconies '
            'overhang one another, and the lift is the only warm thing in the shaft.'),
        'landmark': {
            'name': 'The 33rd Floor Lift',
            'description': (
                'A brass service lift with one door panel ajar on amber light and an '
                'indicator that carries a floor mark which does not exist. The paired '
                'landmark panels are the lift door (07) and a cutaway of the staggered '
                'balcony atrium with the hanging luggage cage (08).'),
            'walls': [7, 8],
        },
        'props': {
            'service_lamp': {
                'display_name': 'Floor-Call Sconce',
                'description': (
                    'A brass floor lamp on a stable foot, with a rectangular amber '
                    'shade, a rain hood and a hanging luggage tag. Small freestanding '
                    'hotel fixture.'),
                'silhouette': 'slim post, broad rectangular shade, hanging tag.',
            },
            'cable_shrine': {
                'display_name': 'Dumbwaiter Winch Head',
                'description': (
                    'A squat brass and steel luggage winch with a large spoked wheel, '
                    'a cable spool, a hanging suitcase and a three-button call plate. '
                    'Freestanding service utility object.'),
                'silhouette': 'low body dominated by one big wheel and a hanging case.',
            },
            'directory_sign': {
                'display_name': 'Staggered Floor Directory',
                'description': (
                    'A tall brass-framed directory with three staggered miniature '
                    'balcony shelves, amber floor ticks, a large direction arrow and '
                    'a rain hood. Landmark wayfinding object with two solid legs.'),
                'silhouette': 'stepped three-shelf frame under a projecting hood.',
            },
        },
        'gameplay_notes': (
            'Cosmetic material and architecture guidance only. Blue-grey surfaces and '
            'dirty amber signage keep the value range away from binding-ring colours. '
            'No live reflections, rain physics or light animation is claimed.'),
        'impossible_detail': (
            'The lift indicator shows a floor between 32 and 33; the directory has the '
            'same floor twice with different arrows. Visual fiction, not a secret door.'),
        'verticality': {
            'levels': 7, 'storey_m': 3.0, 'height_m': 18.0,
            'primary_route': 'fire stair and service lift',
            'open_volume': 'staggered service atrium through levels 1-6',
            'fall_recovery': 'balcony setbacks, linen chute shelves and a laundry net',
        },
    },
}

# Six mob identities.  The two right-hand fields are the only adapter-facing
# behaviour families: existing latchwing and relay_choir.  Any vertical motion
# text below is a *proposal* and is marked unimplemented.
MOBS = {
    'ashbell_foundry': {
        'latchwing': {
            'id': 'chain_hound',
            'name': 'CHAIN HOUND',
            'description': (
                'A low cast-iron bell hound: a banded drum body carried on four chain-'
                'link legs with hook feet, a bell-shaped muzzle with a loose clapper, '
                'and a counterweight tail. It reads first as foundry debris, then as '
                'an animal when the chain legs take a step.'),
            'variant_a': (
                'Four chain legs, one bell muzzle, a short counterweight tail and a '
                'mane of five hanging links.'),
            'variant_b': (
                'Six chain legs, a split two-cup muzzle, a longer tail with two '
                'counterweights and a heavier bronze brow.'),
            'tells': (
                'The chain legs coil and shorten while the clapper draws back and the '
                'muzzle cup glows furnace orange. The whole body lowers before the dash.'),
            'counterplay': (
                'The dash is locked to the direction of the lowered muzzle. Sidestep '
                'or break line of sight; do not back away in the same lane. Its flank '
                'is open during the coil.'),
            'vertical_proposal': (
                'Proposed only, not implemented: drop from a maintenance balcony to a '
                'lower gantry when the quarry is directly below, then require a full '
                'recovery pause. It cannot climb chain or ladder geometry and cannot '
                'cross a gap wider than one native tile.'),
        },
        'relay_choir': {
            'id': 'pouring_choir',
            'name': 'POURING CHOIR',
            'description': (
                'An anchored casting mould that has grown three crucible lips: a '
                'stack of soot-black flasks bound in bronze, with a vertical seam, '
                'three glowing pour vents and a tapping bar. It swivels on a cast '
                'base instead of walking and pours a slow three-part fan.'),
            'variant_a': (
                'Tall three-flask stack with lips at three heights and a narrow base.'),
            'variant_b': (
                'Wide cauldron body with three lips around one rim and a heavy '
                'counterweighted tapping arm.'),
            'tells': (
                'The three vents brighten in sequence, the tapping bar lifts and '
                'three molten beads form on the lips before they extend outward.'),
            'counterplay': (
                'It is anchored and turns slowly. Strafe around cover rather than '
                'retreating down its lane; the fan is slow enough to walk out of at '
                'middle range. Do not stand under a lip while it is bright.'),
            'vertical_proposal': (
                'Proposed only, not implemented: its three pour streams could arc to '
                'one lower balcony and one upper rail, but that requires new '
                'projectile pitch and line-of-fire checks. Keep it floor-anchored in '
                'the first pass.'),
        },
    },
    'boneglass_conservatory': {
        'latchwing': {
            'id': 'root_stilt',
            'name': 'ROOT STILT',
            'description': (
                'A tall, thin nursery silhouette on two bone-white root stilts. Its '
                'torso is a cage of pale ribs around a dark hollow; its head is a '
                'drooping fungal bell with a vertical slit, and its arms are loose '
                'root tendrils. It moves with a slow, deliberate step that is worse '
                'than a run.'),
            'variant_a': (
                'Two long stilts, a narrow rib cage and one drooping bell head.'),
            'variant_b': (
                'Three stilts, a wider split bell head and a skirt of short root '
                'tendrils around the hollow torso.'),
            'tells': (
                'Both stilts lock straight and the rib cage flares; the head slit '
                'opens to a dark vertical line and the tendril arms go still. The '
                'step is telegraphed by a forward lean that holds for four frames.'),
            'counterplay': (
                'The stride is a locked-direction lunge. Step out of the lane and '
                'use a growth chamber or root cage as cover; its turning is poor.'),
            'vertical_proposal': (
                'Proposed only, not implemented: step down one storey of planter '
                'shelves and refuse drops above two storeys. It cannot climb polished '
                'glass or jump gaps. Requires new ledge query and landing checks.'),
        },
        'relay_choir': {
            'id': 'hollow_nurse',
            'name': 'HOLLOW NURSE',
            'description': (
                'A rooted hanging pod cluster around a pale vertical stalk. Three '
                'fungal bells hang from the crown, and the central bell carries a '
                'blank, almost-human face-shaped hollow. It does not walk; it turns '
                'in its root socket and breathes a slow three-part spore fan.'),
            'variant_a': (
                'Three separate hanging bells around a narrow blank central pod.'),
            'variant_b': (
                'One broad central bell with two smaller side pods and a curtain of '
                'root tendrils over the face hollow.'),
            'tells': (
                'The three bells inflate, their slits open and a pale glow rises '
                'inside the central hollow; loose spores gather at the rims.'),
            'counterplay': (
                'Anchored and slow to reorient. Fight from an angle, use a pillar to '
                'break the fan, and leave before the bells fully inflate if possible.'),
            'vertical_proposal': (
                'Proposed only, not implemented: the spore fan could drift downward '
                'through a floor opening. That needs volumetric projectile handling; '
                'the first pass keeps the fan on one level.'),
        },
    },
    'skyhotel_service_well': {
        'latchwing': {
            'id': 'night_porter',
            'name': 'NIGHT PORTER',
            'description': (
                'A tall bellhop silhouette assembled from hotel service: a long '
                'maroon coat split into two stiff coat-tail legs, a brass-buttoned '
                'torso, a suitcase forearm and a peaked cap pulled over a blank face. '
                'It stands too upright and leans in only when it has decided.'),
            'variant_a': (
                'One suitcase forearm, two coat-tail legs and a straight peaked cap.'),
            'variant_b': (
                'Two cases at different heights, a longer split coat and a tilted '
                'cap with a brass bell badge.'),
            'tells': (
                'The cap tilts, the suitcase seam opens on a dark gap and the coat '
                'tails lock together. Amber light gathers under the case before the '
                'lunge.'),
            'counterplay': (
                'The porter commits to a straight service-corridor dash. Sidestep '
                'through a door bay or around a luggage winch; it cannot turn mid-run.'),
            'vertical_proposal': (
                'Proposed only, not implemented: use the service lift as a same-shaft '
                'chase, waiting for the car instead of teleporting. It cannot climb '
                'the outside of the lift or cross the atrium void. New lift-state AI '
                'and navigation links would be required.'),
        },
        'relay_choir': {
            'id': 'call_bell_choir',
            'name': 'CALL-BELL CHOIR',
            'description': (
                'An anchored luggage trolley fused with three brass call bells and a '
                'tall room-number paddle. Amber bulbs sit under the bells; the trolley '
                'shudders and rings a slow three-part fan of resonance instead of '
                'moving. The wheels twitch but never roll.'),
            'variant_a': (
                'Low luggage cart with three bells in a row and one upright paddle.'),
            'variant_b': (
                'Tall stacked luggage with three bells at different heights and a '
                'bent, split paddle.'),
            'tells': (
                'One bell after another rises on its stalk, the three amber bulbs '
                'brighten and the paddle turns to face the player before the fan.'),
            'counterplay': (
                'Anchored, slow to track and blocked by the central shaft corner. '
                'Break the line of the three bells, then close from the side.'),
            'vertical_proposal': (
                'Proposed only, not implemented: the resonance fan could pass through '
                'a balcony opening to a lower landing. That needs vertical hit tests; '
                'the first pass keeps it on one level.'),
        },
    },
}

FORBIDDEN_GENERIC_BOXES = (
    'No prop is a plain upright box with a different palette: every silhouette '
    'has a distinct primary mass and at least one asymmetric feature.')


def hx(value):
    value = value.lstrip('#')
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def C(set_id, name):
    return hx(PALETTES[set_id][name])


def mix(a, b, t):
    t = max(0.0, min(1.0, float(t)))
    return tuple(int(round(a[i] * (1 - t) + b[i] * t)) for i in range(3))


def shade(color, factor):
    if factor >= 1:
        return tuple(min(255, int(round(c * factor))) for c in color)
    return tuple(max(0, int(round(c * factor))) for c in color)


def asset_seed(seed, set_index, kind_index, index):
    """Stable per-asset seed; no Python hash(), no global RNG."""
    payload = f'{int(seed)}:{int(set_index)}:{int(kind_index)}:{int(index)}'
    return int.from_bytes(hashlib.sha256(payload.encode()).digest()[:8], 'big')


def seed_rng(*parts):
    return random.Random(asset_seed(*parts))


def clamp_byte(v):
    return max(0, min(255, int(round(v))))


def stable_json(data):
    import json
    return json.dumps(data, indent=2, sort_keys=False, ensure_ascii=True) + '\n'
