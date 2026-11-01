# SPDX-License-Identifier: GPL-3.0-or-later
"""Original DeepSeek weapon art, using the engine's existing weapon actions.

TEXTURES gives the640x400 artwork a320x200 logical sprite size. The native
weapon layer's resting Y=32 is cancelled by the32-unit logical top offset.
No damage, ammo, fire cadence, selection or player inventory changes here.
"""
import io
import json
from pathlib import Path
from PIL import Image

LABELS=('FATHOM HOOK','REGISTRAR','TRANSIT-12','COMPTROLLER','PLUMB BOMBARD',
        'AETHOMETER','HYMNODYNE','FATHOM HOOK','TRANSIT-12')
# Each string lists worker frame indices for native sprite letters A onward.
BODIES={'PUNG':('melee','03457'),'SAWG':('melee','4507'),
        'PISG':('sidearm','0345'),'SHTG':('scattergun','0675'),
        'SHT2':('scattergun','04567625'),'CHGG':('repeater','0345'),
        'MISG':('launcher','0345'),'PLSG':('projector','04'),'BFGG':('heavy','03')}
FLASHES={'PISF':('sidearm',(3,3)), 'SHTF':('scattergun',(0,0)),
         'CHGF':('repeater',(0,3)), 'MISF':('launcher',(3,3,3,3)),
         'PLSF':('projector',(0,0)), 'BFGF':('heavy',(3,3))}
PICKUPS={'CSAW':'melee','PIST':'sidearm','SHOT':'scattergun','SGN2':'scattergun',
         'MGUN':'repeater','LAUN':'launcher','PLAS':'projector','BFUG':'heavy'}


def sprite(name,path,pickup=False):
    width,height=(96,64) if pickup else (640,400)
    left,top=(48,64) if pickup else (0,64)
    return (f'Sprite {name}, {width}, {height} {{\n XScale 2\n YScale 2\n'
            f' Offset {left}, {top}\n Patch "{path}", 0, 0\n}}\n')


def artwork(root,png):
    root=Path(root);manifest=json.loads((root/'manifest.json').read_text())
    slots={s['slot']:s for s in manifest['slots']};files={};definitions=[];mapping=[]
    def body(slot,index):
        path=slots[slot]['frames'][index]['file'];dest='graphics/original-weapons/'+path
        files[dest]=(root/path).read_bytes();return dest
    for prefix,(slot,indices) in BODIES.items():
        for i,index in enumerate(indices):
            name=prefix+chr(65+i)+'0';path=body(slot,int(index))
            definitions.append(sprite(name,path));mapping.append(dict(sprite=name,source=path,role='body'))
    for prefix,(slot,target_frames) in FLASHES.items():
        for i,target_frame in enumerate(target_frames):
            source=slots[slot]['flashes'][min(i,1)];frame=slots[slot]['frames'][target_frame]
            # Some native guns fire from their ready frame. Move the separate
            # generated flash to that frame's actual muzzle before packing it.
            dx=round(frame['muzzle_world'][0]-source['muzzle_world'][0]);dy=round(frame['muzzle_world'][1]-source['muzzle_world'][1])
            with Image.open(root/source['file']) as im:
                out=Image.new('RGBA',(640,400));out.alpha_composite(im.convert('RGBA'),dest=(dx,dy))
            path=f'graphics/original-weapons/adapted/{prefix}{chr(65+i)}.png';files[path]=png(out)
            name=prefix+chr(65+i)+'0';definitions.append(sprite(name,path));mapping.append(dict(sprite=name,source=source['file'],shift=[dx,dy],role='flash'))
    # The double-scatter gun stores flash states I/J in its body sprite family.
    for i in range(2):
        path=f'graphics/original-weapons/adapted/SHTF{chr(65+i)}.png'
        definitions.append(sprite('SHT2'+chr(73+i)+'0',path))
        mapping.append(dict(sprite='SHT2'+chr(73+i)+'0',source=path,role='flash'))
    for prefix,slot in PICKUPS.items():
        path=slots[slot]['icon']['file'];dest='graphics/original-weapons/'+path
        files[dest]=(root/path).read_bytes();definitions.append(sprite(prefix+'A0',dest,True));mapping.append(dict(sprite=prefix+'A0',source=path,role='pickup'))
    files['TEXTURES']='\n'.join(definitions).encode()
    files['original-weapon-mapping.json']=json.dumps(mapping,indent=2).encode()
    return files


def remaining_assets():
    return dict(weapon_art='Original DeepSeek-generated weapons, hands, flashes and weapon pickups; native classic actions retained.',
                original='Procedural environment walls/flats, creature banks and model art, signal exhibition, upgrade/gate art, Departure Mono HUD.',
                remaining_freedoom=['IWAD palette and base game definitions/dependencies','Ammo, health, armour and powerup pickup sprites',
                                    'Projectile, impact, blood and explosion sprites','Sound effects (native SFX disabled in the live adaptive-audio setup)',
                                    'Fallback/menu/intermission assets and SKY3 where used'],
                note='An art replacement pass, not a standalone IWAD. Freedoom credit and licence remain required. Remaining list is a conservative dependency audit, not proof of every runtime lookup.')
