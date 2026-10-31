# SPDX-License-Identifier: GPL-2.0-or-later
"""Seeded UPKEEP kiosks. The native engine owns money, stock and effects."""
import random
import struct

TYPE = 15999
PERKS = 5


def place(floors, seed):
    from rogue.maps import TILE, distances
    for f in floors:
        occupied = {(t[0]//TILE, t[1]//TILE) for t in f.things}
        blocked = {tuple(p['cell']) for p in f.architecture.get('props', []) if p.get('solid')}
        candidates = []
        for cell in sorted(f.cells - occupied - set(f.route)):
            profile = f.profiles.get(cell, {})
            distance = abs(cell[0]-f.start[0])+abs(cell[1]-f.start[1])
            if not 1 <= distance <= 3 or profile.get('height', 0) < 128:
                continue
            if profile.get('tag') or profile.get('special') or cell == f.exit:
                continue
            remaining = f.cells - blocked - {cell}
            if len(distances(remaining, f.start)) != len(remaining):
                continue
            # A clear neighbouring tile at the same walkable height is needed
            # to use the solid machine, not just a connected route around it.
            neighbours = [(cell[0]+dx, cell[1]+dy) for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]]
            if not any(p in remaining and abs(f.profiles[p].get('floor',0)-profile.get('floor',0)) <= 24 for p in neighbours):
                continue
            candidates.append((distance, cell))
        if not candidates:
            raise ValueError(f'No safe vending location on floor {f.number}')
        _, cell = min(candidates)
        x,y = (p*TILE+TILE//2 for p in cell)
        order = list(range(PERKS))
        random.Random((seed << 8) ^ f.number ^ 0x55504B454550).shuffle(order)
        f.things.append((x,y,0,TYPE,7))
        f.profiles[cell]['light'] = max(208, f.profiles[cell].get('light',0))
        f.architecture['vending'] = dict(id=f.number, cell=list(cell), x=x, y=y, order=order)


def metadata(floors, seed):
    entries = []
    for f in floors:
        v = f.architecture.get('vending')
        if v:
            entries.append(struct.pack('<HHhh5B3x', f.number, v['id'], v['x'], v['y'], *v['order']))
    return 'RVEND', struct.pack('<4sIHH', b'RVN1', seed, len(entries), 0) + b''.join(entries)


def picture(spent=False):
    """Original binary-alpha cabinet art; no antialiasing in Doom patches."""
    from PIL import Image, ImageDraw
    from rogue.hud import font
    im = Image.new('RGBA', (80,112)); d = ImageDraw.Draw(im)
    dark=(16,24,29); steel=(43,59,66); edge=(116,140,145)
    amber=(131,103,70) if spent else (230,165,87)
    d.polygon([(9,6),(63,6),(72,13),(72,106),(10,106)], fill=dark, outline=edge)
    d.polygon([(63,6),(72,13),(72,106),(63,100)],fill=steel,outline=edge)
    d.rectangle((13,10,59,26), fill=amber)
    d.text((16,12),'UPKEEP',font=font(11),fill=dark)
    d.rectangle((14,31,57,72),fill=(8,14,18),outline=steel)
    for y in (39,51,63):
        for x in (23,38,51):
            d.rectangle((x-3,y-4,x+3,y+3),fill=steel,outline=(77,99,104))
        d.line((16,y+6,55,y+6),fill=steel)
    d.rectangle((17,80,52,91),fill=(6,10,14),outline=edge)
    d.line((21,84,47,84),fill=steel if spent else amber,width=2)
    d.rectangle((58,34,61,55),fill=amber)
    d.rectangle((15,106,23,110),fill=steel);d.rectangle((56,106,64,110),fill=steel)
    return im


def sprite_lumps(assets):
    import numpy as np
    from PIL import Image, ImageDraw
    from rogue.creatures import wad_lumps, patch
    palette = np.frombuffer(dict(wad_lumps(assets))['PLAYPAL'][:768],dtype=np.uint8).reshape(256,3)
    # Art pixels become world units in the native renderer. Encode a human-
    # sized cabinet with crisp pixels instead of a double-height billboard.
    glyphs={'U':('101','101','101','101','111'),'P':('110','101','110','100','100'),
            'K':('101','110','100','110','101'),'E':('111','100','110','100','111')}
    result=[]
    for name,spent in [('VENDA0',False),('VENDB0',True)]:
        image=picture(spent).resize((48,72),Image.Resampling.NEAREST)
        d=ImageDraw.Draw(image);d.rectangle((8,7,35,16),fill=(131,103,70) if spent else (230,165,87))
        # Draw the tiny sign at its final resolution so scaling cannot eat the
        # letter strokes. Six original 3x5 glyphs fit the cabinet fascia.
        for i,char in enumerate('UPKEEP'):
            for y,row in enumerate(glyphs[char]):
                for x,bit in enumerate(row):
                    if bit=='1':d.point((10+i*4+x,9+y),fill=(16,24,29))
        result.append((name,patch(image,palette)))
    return result
