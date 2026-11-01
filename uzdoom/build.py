# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a reproducible seven-floor 3D Null Run campaign from original content."""
from pathlib import Path
from collections import defaultdict
import argparse
import hashlib
import io
import json
import math
import random
import re
import struct
import zipfile

from PIL import Image,ImageDraw,ImageFont,PngImagePlugin
import numpy as np
from rogue.maps import generate,map_lumps
from rogue.threshold_assets import apply_identity
from rogue.environments import apply,PACK_IDS,describe
from rogue.architecture import study,cellpoint,flats as arch_flats
from rogue.bosses import is_boss_thing
from rogue.creatures import FAMILIES,creature,sprite_lumps,wad_lumps
from rogue.vending import place,picture as cabinet
from uzdoom.models import actor_id,artwork as model_artwork,doom_ed_numbers,installation_artwork
from uzdoom.openworld.campaign import add_floor,IDS
from uzdoom.openworld.selection import choose as floor_choices
from uzdoom.art_sections import add_room as add_art_room,artwork as signal_artwork
from uzdoom.weapons import artwork as weapon_artwork,remaining_assets
from uzdoom.weather import PRESETS as WEATHER_PRESETS,configure as configure_weather,lump as weather_lump,mist_texture

ROOT=Path(__file__).resolve().parents[1]
BANK=ROOT/'assets/tower'
NEW_PACKS=('ashbell_foundry','boneglass_conservatory','skyhotel_service_well')
PACKS=PACK_IDS+NEW_PACKS
KINDS={3004:1,3002:2,3001:3,3005:4,3003:5,69:6,66:7,65:8,67:9,68:10,9:11,84:12,64:13,3006:14,71:16}
SPRITES={1:'POSS',2:'SARG',3:'TROO',4:'HEAD',5:'BOSS',6:'BOS2',7:'SKEL',8:'CPOS',9:'FATT',10:'BSPI',11:'SPOS',12:'SSWV',13:'VILE',14:'SKUL',15:'CYBR',16:'PAIN'}


def block(kind,fields):
    return kind+' { '+' '.join(f'{k} = {str(v).lower() if isinstance(v,bool) else json.dumps(v)};' for k,v in fields.items())+' }\n'


def wad(lumps):
    raw=bytearray();directory=[]
    for name,data in lumps:
        directory.append(struct.pack('<II8s',12+len(raw),len(data),name.encode().ljust(8,b'\0')));raw.extend(data)
    return struct.pack('<4sII',b'PWAD',len(lumps),12+len(raw))+raw+b''.join(directory)


def png(image,offset=False):
    out=io.BytesIO();info=PngImagePlugin.PngInfo()
    if offset:info.add(b'grAb',struct.pack('>ii',image.width//2,image.height))
    image.save(out,format='PNG',pnginfo=info)
    return out.getvalue()


class Map:
    def __init__(self,number):
        self.number=number;self.vertices=[];self.vertex_ids={};self.edges={};self.lines=[];self.sides=[];self.sectors=[]
        self.things=[];self.nodes=[];self.meta=[];self.seams=[];self.gates=[];self.surface_index={}

    def vertex(self,p):
        if p not in self.vertex_ids:self.vertex_ids[p]=len(self.vertices);self.vertices.append(p)
        return self.vertex_ids[p]

    def rectangle(self,x,y,size,floor,ceiling,wall='EWALL02',flat='EFLAT01',roof='EFLAT03',light=176,tag=0,control=None,special=0):
        sector=len(self.sectors)
        self.sectors.append(dict(heightfloor=floor,heightceiling=ceiling,texturefloor=flat,textureceiling=roof,lightlevel=light,id=tag,special=special))
        corners=[(x,y),(x,y+size),(x+size,y+size),(x+size,y)]
        for i,a in enumerate(corners):
            b=corners[(i+1)%4];va,vb=self.vertex(a),self.vertex(b)
            side=len(self.sides);self.sides.append(dict(sector=sector,texturetop=wall,texturebottom=wall,texturemiddle=wall))
            if (vb,va) in self.edges:
                line=self.lines[self.edges[vb,va]];line.update(sideback=side,twosided=True,blocking=False)
                self.sides[line['sidefront']]['texturemiddle']='-';self.sides[side]['texturemiddle']='-'
            else:
                line=dict(v1=va,v2=vb,sidefront=side,blocking=True)
                if control is not None and i==0:line.update(special=160,arg0=control,arg1=1,arg2=0,arg3=255,arg4=0)
                self.edges[va,vb]=len(self.lines);self.lines.append(line)
        return sector

    def thing(self,x,y,type,angle=0,z=0,args=()):
        row=dict(x=x,y=y,height=z,angle=int(round(angle))%360,type=type,skill1=True,skill2=True,skill3=True,skill4=True,skill5=True,single=True)
        row.update({f'arg{i}':v for i,v in enumerate(args)})
        self.things.append(row)

    def surface(self,x,y,z,sector,tile):
        index=len(self.nodes);self.nodes.append(dict(x=x,y=y,z=z,sector=sector,tile=tile,edges=set()))
        self.surface_index.setdefault((x,y),[]).append(index)

    def grid(self,f,offset=(0,0),base=0):
        ox,oy=offset
        dynamic={p for p,r in f.profiles.items() if r.get('tag') in (1301,1302)}
        sectors={}
        for x,y in sorted(f.cells|dynamic):
            p=f.profiles.get((x,y),{});z=base+p.get('floor',0)
            height=p.get('height',128) if (x,y) in f.cells else 0
            wall=p.get('wall','EWALL02');flat=p.get('flat','EFLAT01');roof=p.get('ceiling','EFLAT03')
            # Existing reserved seal art remains a native floor texture.
            for b in f.bosses:
                if (x,y)==tuple(b['binding_cell']):flat='RSEAL'+str(b['class'])
                if (x,y)==tuple(b.get('secondary_cell',(-1,-1))):flat='RSEAL10B'
            special=1024 if p.get('special')==9 else 0
            sec=self.rectangle(ox+x*128,oy+y*128,128,z,z+height,wall,flat,roof,p.get('light',176),p.get('tag',0),special=special)
            sectors[x,y]=sec
            self.surface(ox+x*128+64,oy+y*128+64,z,sec,128)
        return sectors

    def seam(self,row,offset=(0,0),base=0):
        ox,oy=offset
        self.seams.append(dict(id=row['id'],sx=ox+row['sx'],sy=oy+row['sy'],sz=base,dx=ox+row['dx'],dy=oy+row['dy'],dz=base,axis=row['axis'],sign=row['sign'],turns=row['turns'],width=row['width']))

    def gate(self,id,source,target,label,bosses=False,swaps=0,mutations=0,next_level=False):
        self.gates.append(dict(id=id,source=list(source),target=list(target),bosses=bosses,swaps=swaps,mutations=mutations,next_level=next_level,label=label))
        self.thing(source[0],source[1],16500,z=source[2]-self.floor_at(source[0],source[1]),args=(id,))

    def floor_at(self,x,y):
        # Called for authored gate/prop coordinates on a known physical cell.
        if hasattr(self,'open_geometry'):
            from uzdoom.openworld.nrlib import point_in_poly
            for poly,z in self.open_geometry:
                if point_in_poly(x,y,poly):return z
        candidates=[n for n in self.nodes if abs(n['x']-x)<=n['tile']/2 and abs(n['y']-y)<=n['tile']/2]
        if not candidates:raise ValueError('No gate floor')
        return min(n['z'] for n in candidates)

    def nav(self):
        for i,n in enumerate(self.nodes):
            if n.get('custom'):continue
            for dx,dy in [(n['tile'],0),(-n['tile'],0),(0,n['tile']),(0,-n['tile'])]:
                for j in self.surface_index.get((n['x']+dx,n['y']+dy),[]):
                    o=self.nodes[j]
                    if abs(o['z']-n['z'])<=24:n['edges'].add(j)
        for seam in self.seams:
            a=min(range(len(self.nodes)),key=lambda i:(self.nodes[i]['x']-seam['sx'])**2+(self.nodes[i]['y']-seam['sy'])**2+4*(self.nodes[i]['z']-seam['sz'])**2)
            b=min(range(len(self.nodes)),key=lambda i:(self.nodes[i]['x']-seam['dx'])**2+(self.nodes[i]['y']-seam['dy'])**2+4*(self.nodes[i]['z']-seam['dz'])**2)
            self.nodes[a]['edges'].add(b)
        for n in self.nodes:
            self.meta.append('N '+' '.join(map(str,(n['x'],n['y'],n['z'],n['sector'])))+' '+','.join(map(str,sorted(n['edges']))))

    def bytes(self):
        text='namespace = "zdoom";\n'
        text+=''.join(block('vertex',dict(x=x,y=y)) for x,y in self.vertices)
        for name,items in [('sector',self.sectors),('sidedef',self.sides),('linedef',self.lines),('thing',self.things)]:
            text+=''.join(block(name,item) for item in items)
        return wad([(f'MAP{self.number:02}',b''),('TEXTMAP',text.encode()),('ENDMAP',b'')])

    def data(self):
        self.nav()
        for s in self.seams:self.meta.append('S '+' '.join(str(s[k]) for k in ('id','sx','sy','sz','dx','dy','dz','axis','sign','turns','width')))
        for g in self.gates:self.meta.append('G '+' '.join(map(str,[g['id'],*g['source'],*g['target'],int(g['bosses']),g['swaps'],g['mutations'],int(g['next_level'])]))+' '+g['label'].replace(' ','_'))
        return ('\n'.join(self.meta)+'\n').encode()


def tower(m,base):
    groups={};cells={}
    for y in range(16):
        for x in range(16):
            depth=max(0,min(x-4,11-x,y-4,11-y))
            floor=-16*depth;slabs=set()
            if y==12 and 2<=x<=13:slabs.update((160,480))
            if y==1 and 2<=x<=13:slabs.add(320)
            if x==8 and 2<=y<=11:slabs.add(320)
            if x==8 and 8<=y<=11:slabs.update((160,480))
            if y==8 and 4<=x<=11:slabs.update((160,320,480))
            if x==2 and 2<=y<=11:floor=(y-1)*16;slabs.add(320+(y-1)*16)
            if x==13 and 2<=y<=11:floor=160+(12-y)*16
            key=tuple(sorted(slabs))
            if key and key not in groups:groups[key]=2000+len(groups)
            cells[x,y]=(floor,key)
            sector=m.rectangle(12000+x*64,y*64,64,base+floor,base+1024,tag=groups.get(key,0))
            for z in (floor,*key):m.surface(12000+x*64+32,y*64+32,base+z,sector,64)
    for key,tag in groups.items():
        for i,height in enumerate(key):m.rectangle(14000+(tag-2000)*48,14000+i*48,32,base+height-8,base+height,control=tag)
    # Optional relief supplies and threats on genuinely elevated surfaces.
    for x,y,z,kind in [(12352,800,160,2012),(12544,96,320,2008),(12544,800,480,2011)]:m.thing(x,y,kind,z=z)
    for x,y,z,k in [(12864,800,160,11),(12544,96,320,7),(12544,800,480,15)]:m.thing(x,y,16000,z=z,args=(k,0,0))
    return [(12160,96,base),(12160,800,base+160),(12864,800,base+160),(12864,96,base+320),(12160,96,base+320),(12160,800,base+480),(12352,800,base+480)]


def kind(thing):
    flag=(thing[4]>>8)&7
    if flag and flag<7:return flag
    if flag==7 and thing[3]==69:return 15
    return KINDS.get(thing[3],0)


def make_maps(seed,pack,open_worlds=True,floor_plan=None):
    floors=apply_identity([generate(seed,n) for n in range(1,8)],seed)
    # Preserve current reviewed layouts and encounter placements. Art selection
    # is separate from the old selector, so this does not alter native runs.
    apply(floors,seed);place(floors,seed)
    floor_plan=floor_plan or floor_choices(seed,IDS)
    result=[];manifests=[]
    for f in floors:
        m=Map(f.number);base=(f.number-1)*512
        world=add_floor(m,f.number,seed,base,f.bosses,f.architecture['vending']['order'],floor_plan[f.number-1]) if open_worlds else None
        if not world:m.grid(f,base=base)
        for t in ([] if world else f.things):
            x,y,angle,type,options=t
            if type in KINDS:
                k=kind(t);boss=next((i+1 for i,b in enumerate(f.bosses) if tuple(b['cell'])==(x//128,y//128) and b['class']==k),0)
                title=f.bosses[boss-1]['name'] if boss else None
                m.thing(x,y,actor_id(k,title),angle,args=(k,(options>>11)&15,boss))
            elif type in (86,85,2028):m.thing(x,y,17000+(86,85,2028).index(type),angle)
            else:m.thing(x,y,type,angle)
        for b in f.bosses:
            rules={5:'On its marked F seal, press F twice, releasing between presses.',
                   6:'On its marked F seal, stand still and release fire for one second.',
                   9:'Hit its shield once, then use F on its marked seal. Holding F while entering also works.',
                   10:'Enter its amber A seal, then its cyan B seal.'}
            b['game_rule']=rules[b['class']]+' Break the shield for twelve seconds and 150% damage. Shielded hits still deal 60% damage.'
            if not world:
                ring=cellpoint(b['binding_cell']);other=cellpoint(b.get('secondary_cell',b['binding_cell']))
                m.meta.append('B '+' '.join(map(str,[b['class'],*ring,base+f.profiles[tuple(b['binding_cell'])].get('floor',0),*other,base+f.profiles[tuple(b.get('secondary_cell',b['binding_cell']))].get('floor',0)]))+' '+b['name'])
        if world:
            for b,original in zip(world['bosses'],f.bosses):b['game_rule']=original['game_rule']
        v=world['vending'] if world else f.architecture['vending']
        if not world:m.meta.append('V '+' '.join(map(str,[v['x'],v['y'],base+f.profiles[tuple(v['cell'])].get('floor',0),*v['order']])))
        puzzle_kind=('corridor','pillar','memory')[(f.number-1)%3];puzzle=study(seed,puzzle_kind)
        # The far room is the way out of Unreliable Memory. The first mutation
        # is required before that door works, so the effect is encountered.
        if puzzle_kind=='memory':puzzle.exit=(24,14)
        annex=m.grid(puzzle,(6000,0),base)
        for s in puzzle.architecture['seams']:m.seam(s,(6000,0),base)
        for c in puzzle.architecture['changes']:
            a=next(p for p,v in puzzle.profiles.items() if v.get('tag')==c['a'])
            b=next(p for p,v in puzzle.profiles.items() if v.get('tag')==c['b'])
            ax,ay=cellpoint(a);bx,by=cellpoint(b)
            m.meta.append('C '+' '.join(map(str,[c['id'],annex[a],annex[b],c['height'],c['delay'],6000+ax,ay,6000+bx,by,base])))
        source=tuple(world['exit']) if world else (*cellpoint(f.exit),base+f.profiles[f.exit].get('floor',0))
        start=cellpoint(puzzle.start);entry=(6000+start[0],start[1],base)
        end=cellpoint(puzzle.exit);end=(6000+end[0],end[1],base)
        path=tower(m,base)
        art_room=add_art_room(m,base)
        m.gate(1,source,entry,'SERVICE_ANNEX',bosses=True)
        m.gate(2,(entry[0]-64,entry[1],base),source,'RETURN_TO_OFFICE')
        m.gate(3,end,path[0],'UPPER_SERVICE_STAIR',swaps=4 if puzzle_kind=='pillar' else 1 if puzzle_kind=='corridor' else 0,mutations=int(puzzle_kind=='memory'))
        m.gate(4,(path[0][0]-48,path[0][1],base),end,'RETURN_TO_ANNEX')
        m.gate(5,path[-1],path[-1],'NEXT_FLOOR' if f.number<7 else 'TOWER_EXIT',bosses=True,next_level=True)
        m.meta.append(f'P {puzzle.architecture["kind"]} {base}')
        # Long lit stretches and irregular ballast failures apply in the
        # uncanny annex, rather than introducing a periodic BPM strobe.
        annex_sectors=sorted({n['sector'] for n in m.nodes if 6000<n['x']<11000})
        m.meta.append('L '+','.join(map(str,annex_sectors)))
        result.append(m)
        title=world['title'].upper() if world else pack.replace('_',' ').upper()
        manifests.append(dict(number=f.number,name=f'{title} / {f.number:02}',office=f.bosses[0].get('source_office'),base_altitude=base,
                              start=world['start'] if world else f.start,exit=world['exit'] if world else f.exit,bosses=world['bosses'] if world else f.bosses,vending=v,puzzle=puzzle_kind,
                              tower_route=path,seams=m.seams,gates=m.gates,sectors=len(m.sectors),nodes=len(m.nodes),open_world=world,art_room=art_room))
    return result,manifests


def artwork(wad_path,seed,pack):
    files={};native=pack in PACK_IDS
    art=ROOT/'assets/environments/art'/pack if native else BANK/'art'/pack
    for group,prefix,count in [('walls','EWALL',8),('flats','EFLAT',4)]:
        for i in range(1,count+1):files[f'{"textures" if group=="walls" else "flats"}/{prefix}{i:02}.png']=(art/group/f'{i:02}.png').read_bytes()
    for family,role in FAMILIES.items():
        for frame in range(26):
            if role in ('latchwing','relay_choir'):
                if native:
                    from rogue.environments import draw_mob
                    image=draw_mob(pack,role,seed,frame)
                else:
                    variant='AB'[(seed+('latchwing','relay_choir').index(role))&1]
                    with Image.open(BANK/'mobs'/pack/f'{role}_{variant}.png') as src:
                        fr=min(frame,23);image=src.crop((fr%4*128,fr//4*128,fr%4*128+128,fr//4*128+128)).convert('RGBA')
            elif native and role in ('service_lamp','cable_shrine','directory_sign'):
                from rogue.environments import picture
                image=picture(pack,'props',role)
            else:image=creature(role,seed,frame)
            files[f'sprites/{family}{chr(65+frame)}0.png']=png(image,True)
    # Reuse the native cabinet's final-resolution lettering, encoded patches
    # alongside PNG sprites in a tiny resource WAD.
    from rogue.vending import sprite_lumps as cabinets
    files['upkeep.wad']=wad([('S_START',b''),*cabinets(wad_path),('S_END',b'')])
    palette=np.frombuffer(dict(wad_lumps(wad_path))['PLAYPAL'][:768],dtype=np.uint8).reshape(256,3)
    bank=sprite_lumps(wad_path,seed,pack if native else None)
    wanted={f'RSEAL{k}' for k in (5,6,9,10)}|{'RSEAL10B'}|{f'NFLAT{i:02}' for i in range(1,5)}
    for name,data in [*bank,*arch_flats(wad_path)]:
        if name in wanted or name in ('RARCHFL','RARCHCL'):
            files[f'flats/{name}.png']=png(Image.fromarray(palette[np.frombuffer(data,dtype=np.uint8).reshape(64,64)]))
    gate=Image.new('RGBA',(48,72));d=ImageDraw.Draw(gate)
    d.rectangle((9,3,39,69),fill=(16,24,29),outline=(134,153,159),width=2)
    d.polygon([(24,12),(13,28),(19,28),(19,44),(29,44),(29,28),(35,28)],fill=(230,165,87))
    d.rectangle((15,51,33,55),fill=(86,226,216));files['sprites/NGATA0.png']=png(gate,True)
    label_font=ImageFont.truetype(str(ROOT/'assets/fonts/DepartureMono-Regular.otf'),12)
    small_font=ImageFont.truetype(str(ROOT/'assets/fonts/DepartureMono-Regular.otf'),9)
    for frame,(label,colour) in enumerate([('F',(230,165,87)),('A',(230,165,87)),('B',(86,226,216)),('OPEN',(235,231,206)),('DONE',(100,122,127))]):
        icon=Image.new('RGBA',(96,48));pen=ImageDraw.Draw(icon)
        pen.polygon([(48,1),(90,23),(48,46),(6,23)],fill=(13,22,28,220),outline=(*colour,255),width=2)
        pen.text((48,23),label,font=label_font,anchor='mm',fill=(*colour,255))
        files[f'sprites/NSLM{chr(65+frame)}0.png']=png(icon,True)
    for frame,(label,colour) in enumerate([('SHIELD 60%',(230,165,87)),('EXPOSED',(86,226,216)),('HIT',(246,239,210))]):
        icon=Image.new('RGBA',(96,24));pen=ImageDraw.Draw(icon)
        pen.rectangle((1,1,94,22),fill=(13,22,28,230),outline=(*colour,255))
        pen.text((48,12),label,font=small_font,anchor='mm',fill=(*colour,255))
        files[f'sprites/NSHB{chr(65+frame)}0.png']=png(icon,True)
    modeldefs=[];classes=[]
    for i,role in enumerate(('service_lamp','cable_shrine','directory_sign')):
        cls=f'NRProp{i}';family={'service_lamp':'TLP2','cable_shrine':'TLMP','directory_sign':'COLU'}[role]
        if native:
            classes.append(f'class {cls} : Actor {{ Default {{ Radius 20; Height 72; +SOLID }} States {{ Spawn: {family} A -1; Stop; }} }}')
        else:
            row=json.loads((BANK/'props3d.json').read_text())['sets'][pack]['props'][i]
            for key in ('obj','mtl','texture'):files[row[key]]=(BANK/row[key]).read_bytes()
            text=re.sub(r'(?m)^usemtl\s+.*$', 'usemtl '+row['texture'], files[row['obj']].decode())
            converted=[]
            for line in text.splitlines():
                fields=line.split()
                if fields and fields[0] in ('v','vn'):
                    x,y,z=map(float,fields[1:4]);line=f'{fields[0]} {x:.6f} {z:.6f} {-y:.6f}'
                converted.append(line)
            files[row['obj']]=('\n'.join(converted)+'\n').encode()
            obj=Path(row['obj']);tex=Path(row['texture'])
            modeldefs.append(f'Model {cls} {{ Path "{obj.parent.as_posix()}" Model 0 "{obj.name}" Skin 0 "{tex.name}" Scale 64 64 64 FrameIndex COLU A 0 0 }}')
            classes.append(f'class {cls} : Actor {{ Default {{ Radius 24; Height 96; +SOLID }} States {{ Spawn: COLU A -1; Stop; }} }}')
    files['MODELDEF']='\n'.join(modeldefs).encode();files['uzdoom/props.zs']='\n'.join(classes).encode()
    actor_files,definitions,actor_classes,numbers=model_artwork(ROOT/'assets/actors3d')
    files.update(actor_files);files['MODELDEF']+=('\n'+definitions+'\n').encode()
    prop_files,definitions2,prop_classes=installation_artwork(ROOT/'assets/installations')
    files.update(prop_files);files['MODELDEF']+=('\n'+definitions2+'\n').encode()
    files['uzdoom/models.zs']=(actor_classes+'\n'+prop_classes+'\n').encode()
    signal_files,signal_defs=signal_artwork(seed,png)
    files.update(signal_files);files['MODELDEF']+=('\n'+signal_defs+'\n').encode()
    files.update(weapon_artwork(ROOT/'assets/weapons',png))
    files['asset-audit.json']=json.dumps(remaining_assets(),indent=2).encode()
    for frame in range(7):files[f'sprites/NRMA{chr(65+frame)}0.png']=png(Image.new('RGBA',(1,1)),True)
    for p in (ROOT/'assets/openworld').glob('*.png'):
        files[('flats/' if p.stem.startswith(('NRFLOOR','NRMOSS','NRWATER','NRVOID','NRGLOW','NRGLASS')) else 'textures/')+p.name]=p.read_bytes()
    return files


def build(seed,assets,output,pack=None,open_worlds=True,*,floor_plan=None,recent_openers=(),weather='off'):
    if type(seed) is not int or not 0<=seed<=0xffffffff:raise ValueError('Unsigned 32-bit seed required')
    pack=pack or PACKS[seed%len(PACKS)]
    if pack not in PACKS:raise ValueError('Unknown environment')
    if weather not in WEATHER_PRESETS:raise ValueError('Unknown weather preset')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    floor_plan=floor_plan or floor_choices(seed,IDS,recent_openers)
    if len(floor_plan)!=7 or any(p['floor']!=i+1 or p['archetype'] not in IDS or type(p['seed']) is not int or not 0<=p['seed']<=0xffffffff for i,p in enumerate(floor_plan)):raise ValueError('Invalid saved floor plan')
    maps,floors=make_maps(seed,pack,open_worlds,floor_plan);files=artwork(assets,seed,pack)
    if weather!='off':files['graphics/NRMIST.png']=png(mist_texture())
    files['ZSCRIPT']=b'version "4.10"\n#include "uzdoom/runtime.zs"\n#include "uzdoom/props.zs"\n#include "uzdoom/models.zs"\n#include "uzdoom/signals.zs"\n'
    for source in (ROOT/'uzdoom/zscript').glob('*.zs'):files['uzdoom/'+source.name]=source.read_bytes()
    model_numbers=doom_ed_numbers()
    info='gameinfo { AddEventHandlers = "NRDirector" PlayerClasses = "NRPlayer" }\nDoomEdNums { 16000 = NRMonster 15999 = NRVendor 16500 = NRGate 17000 = NRProp0 17001 = NRProp1 17002 = NRProp2 18200 = NRSignal0 18201 = NRSignal1 18202 = NRSignal2 18210 = NRArtConsole '+model_numbers+' }\n'
    for m,f in zip(maps,floors):
        profile=configure_weather(m,f.get('open_world'),weather,seed)
        f['weather']=profile
        if profile:files[f'NRWX{m.number:02}']=weather_lump(profile)
        files[f'maps/MAP{m.number:02}.wad']=m.bytes();files[f'NRMAP{m.number:02}']=m.data()
        info+=f'map MAP{m.number:02} "NULL RUN / {pack.replace("_"," ").upper()} / {m.number:02}" {{ levelnum = {m.number} next = "MAP{m.number+1:02}" sky1 = "SKY3" nointermission allowjump nocrouch }}\n'
    files['MAPINFO']=info.encode();files['CVARINFO']=b'server bool nr_flicker = true;\n'
    files['CREDITS.txt']=(ROOT/'LICENSE').read_bytes()+b'\nNull Run by Josiah Alan-Lee and collaborators. UZDoom backend/bridge: Codex. Original creatures/concepts: Argon and Josiah; environment art/composer: DeepSeek with reviewed adapters. Base game content: Freedoom (BSD). Typeface: Departure Mono (SIL OFL). Engine: UZDoom (GPL-3.0-or-later), supplied separately.\n'
    with zipfile.ZipFile(output/'nullrun.pk3','w',zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(files.items()):
            entry=zipfile.ZipInfo(name,(2026,10,31,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;z.writestr(entry,data)
    environment=describe(pack) if pack in PACK_IDS else next(e for e in json.loads((BANK/'environments.json').read_text())['sets'] if e['id']==pack)
    manifest=dict(format='nullrun-uzdoom-1',seed=seed,mode='campaign',identity='threshold',environment=environment,floor_plan=floor_plan,weather=weather,
                  floors=floors,sha256=hashlib.sha256((output/'nullrun.pk3').read_bytes()).hexdigest())
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--seed',type=int,default=20261031)
    parser.add_argument('--assets',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--environment',choices=PACKS)
    parser.add_argument('--legacy-layouts',action='store_true',help='Retain office layouts for focused mechanics regression checks')
    parser.add_argument('--weather',choices=WEATHER_PRESETS,default='off',help='Optional cistern fog/particles; default is off')
    a=parser.parse_args();m=build(a.seed,a.assets,a.output,a.environment,not a.legacy_layouts,weather=a.weather);print(a.output,m['sha256'])
