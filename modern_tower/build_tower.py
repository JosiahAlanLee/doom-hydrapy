# SPDX-License-Identifier: GPL-2.0-or-later
"""Original isolated UDMF tower: native stairs plus real stacked solid floors."""
from pathlib import Path
import argparse
from collections import defaultdict
import hashlib,json,math,struct,zipfile

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--art-root',type=Path,default=ROOT.parent/'assets/environments/art/drowned_records')
parser.add_argument('--output',type=Path,default=ROOT.parent/'runtime/tower-map')
args=parser.parse_args()
ART=args.art_root
for group,count in [('walls',8),('flats',4)]:
    for i in range(1,count+1):
        if not (ART/group/f'{i:02}.png').is_file():parser.error(f'missing tile: {ART/group}/{i:02}.png')
OUT=args.output;OUT.mkdir(parents=True,exist_ok=False)
TILE=64;SIZE=16;STAIR=16;CEILING=1024

def block(kind,fields):
    def value(v):
        if isinstance(v,bool):return str(v).lower()
        return json.dumps(v)
    return kind+' { '+ ' '.join(f'{k} = {value(v)};' for k,v in fields.items())+' }\n'

def wad(lumps):
    raw=bytearray();directory=[]
    for name,data in lumps:
        directory.append(struct.pack('<II8s',12+len(raw),len(data),name.encode().ljust(8,b'\0')));raw.extend(data)
    return struct.pack('<4sII',b'PWAD',len(lumps),12+len(raw))+raw+b''.join(directory)

# Geometry groups share the same set of physically solid slab surfaces.
cells={};groups={};routes=[]
for y in range(SIZE):
    for x in range(SIZE):
        floor=-64 if 5<=x<=10 and 5<=y<=10 else 0
        slabs=set()
        if y==12 and 2<=x<=13:slabs.update((160,480))
        if y==1 and 2<=x<=13:slabs.add(320)
        if x==8 and 2<=y<=11:slabs.add(320)
        if x==8 and 8<=y<=11:slabs.update((160,480))
        if y==8 and 4<=x<=11:slabs.update((160,320,480))
        if x==2 and 2<=y<=11:
            floor=(y-1)*STAIR
            slabs.add(320+(y-1)*STAIR)
        if x==13 and 2<=y<=11:floor=160+(12-y)*STAIR
        key=tuple(sorted(slabs))
        if key and key not in groups:groups[key]=len(groups)+1
        cells[x,y]={'floor':floor,'slabs':key,'tag':groups.get(key,0)}

verts=[];vert_ids={};sides=[];lines=[];edges={};sectors=[]
def vertex(x,y):
    key=(x,y)
    if key not in vert_ids:vert_ids[key]=len(verts);verts.append(key)
    return vert_ids[key]
def add_sector(corners,floor,ceiling,tag=0,control=None):
    sector=len(sectors);sectors.append(dict(heightfloor=floor,heightceiling=ceiling,
        texturefloor='TF01',textureceiling='TF02',lightlevel=180,id=tag))
    for i,a in enumerate(corners):
        b=corners[(i+1)%len(corners)];va,vb=vertex(*a),vertex(*b)
        side=len(sides);sides.append(dict(sector=sector,texturetop='TW02',texturebottom='TW03',texturemiddle='TW01'))
        if (vb,va) in edges:
            line=lines[edges[vb,va]];line['sideback']=side;line['twosided']=True;line['blocking']=False
            sides[line['sidefront']]['texturemiddle']='-';sides[side]['texturemiddle']='-'
        else:
            line=dict(v1=va,v2=vb,sidefront=side,blocking=True)
            if control is not None and i==0:
                line.update(special=160,arg0=control,arg1=1,arg2=0,arg3=255,arg4=0)
            edges[va,vb]=len(lines);lines.append(line)
    return sector

for (x,y),cell in cells.items():
    x0,y0=x*TILE,y*TILE
    add_sector([(x0,y0),(x0,y0+TILE),(x0+TILE,y0+TILE),(x0+TILE,y0)],cell['floor'],CEILING,cell['tag'])
for slabs,tag in groups.items():
    for i,height in enumerate(slabs):
        x=2048+tag*96;y=2048+i*96
        add_sector([(x,y),(x,y+32),(x+32,y+32),(x+32,y)],height-8,height,control=tag)
things=[dict(x=160,y=96,height=0,angle=90,type=1,skill1=True,skill2=True,skill3=True,skill4=True,skill5=True,single=True),
        dict(x=352,y=800,height=480,angle=0,type=2015,skill1=True,skill2=True,skill3=True,skill4=True,skill5=True,single=True)]
text='namespace = "zdoom";\n'
text+=''.join(block('vertex',dict(x=x,y=y)) for x,y in verts)
text+=''.join(block('sector',s) for s in sectors)
text+=''.join(block('sidedef',s) for s in sides)
text+=''.join(block('linedef',l) for l in lines)
text+=''.join(block('thing',t) for t in things)
mapdata=wad([('MAP01',b''),('TEXTMAP',text.encode()),('ENDMAP',b'')])

zscript='''version "4.10"
class NullTowerProbe : EventHandler
{
    int stage;
    int ticks;
    bool reported;
    int lastPose;
    int lastPitch;
    override void WorldTick()
    {
        if (!playeringame[0] || players[0].mo == null) return;
        let p = players[0].mo;
        if (CVar.GetCVar("nr_camera_test").GetBool()) p.Pitch = CVar.GetCVar("nr_pitch").GetInt();
        int pose = CVar.GetCVar("nr_pose").GetInt();
        if (pose > 0 && CVar.GetCVar("nr_camera_test").GetBool())
        {
            if (lastPose != pose)
            {
                // Camera-only placements after the collision climb completes.
                // These do not contribute to the walk-through proof.
                if (pose == 1) p.SetOrigin((352,224,0), false);
                else p.SetOrigin((352,800,480), false);
                lastPose=pose;
            }
            p.Vel=(0,0,0);p.Angle=pose==1 ? 90 : 270;
            if (lastPitch != int(p.Pitch))
            {
                Console.Printf("NULLTOWER_CAMERA pose=%d pitch=%f x=%f y=%f z=%f",pose,p.Pitch,p.Pos.X,p.Pos.Y,p.Pos.Z);
                lastPitch=int(p.Pitch);
            }
            return;
        }
        if (!CVar.GetCVar("nr_probe").GetBool()) return;
        ticks++;
        Vector3 goal;
        switch(stage)
        {
            case 0: goal=(160,800,160); break;
            case 1: goal=(864,800,160); break;
            case 2: goal=(864,96,320); break;
            case 3: goal=(160,96,320); break;
            case 4: goal=(160,800,480); break;
            default: goal=(352,800,480); break;
        }
        if (stage >= 6)
        {
            p.Vel=(0,0,p.Vel.Z);p.Angle=270;
            if (!reported)
            {
                Console.Printf("NULLTOWER_DONE x=%f y=%f z=%f ticks=%d",p.Pos.X,p.Pos.Y,p.Pos.Z,ticks);
                reported=true;
            }
            return;
        }
        double dx=goal.X-p.Pos.X,dy=goal.Y-p.Pos.Y;
        double distance=sqrt(dx*dx+dy*dy);
        if (distance<7 && abs(p.Pos.Z-goal.Z)<2)
        {
            Console.Printf("NULLTOWER_LANDING stage=%d x=%f y=%f z=%f",stage,p.Pos.X,p.Pos.Y,p.Pos.Z);
            stage++;p.Vel=(0,0,p.Vel.Z);
            return;
        }
        if (distance>0.01)
        {
            p.Vel=(dx/distance*4,dy/distance*4,p.Vel.Z);
            p.Angle=atan2(dy,dx);
        }
        if (ticks%70==0)Console.Printf("NULLTOWER_TICK stage=%d x=%f y=%f z=%f pitch=%f",stage,p.Pos.X,p.Pos.Y,p.Pos.Z,p.Pitch);
    }
}
'''
mapinfo='''gameinfo { AddEventHandlers = "NullTowerProbe" }
map MAP01 "NULL RUN / Tower geometry trial"
{
    levelnum = 1
    sky1 = "SKY3"
    nointermission
}
'''
cvarinfo='server bool nr_probe = false;\nserver bool nr_camera_test = false;\nserver int nr_pose = 0;\nserver int nr_pitch = 0;\n'
files={'maps/MAP01.wad':mapdata,'ZSCRIPT':zscript.encode(),'MAPINFO':mapinfo.encode(),'CVARINFO':cvarinfo.encode()}
for i in range(1,9):files[f'textures/TW{i:02}.png']=(ART/'walls'/f'{i:02}.png').read_bytes()
for i in range(1,5):files[f'flats/TF{i:02}.png']=(ART/'flats'/f'{i:02}.png').read_bytes()
with zipfile.ZipFile(OUT/'nullrun-tower-proof.pk3','w',zipfile.ZIP_DEFLATED) as z:
    for name,data in sorted(files.items()):
        entry=zipfile.ZipInfo(name,(2026,10,31,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;z.writestr(entry,data)
manifest={'purpose':'Isolated UZDoom native freelook/3D-floor/stair feasibility test; not a port of Null Run enemy/music code',
 'source_art':'Existing original Null Run Drowned Records bank, placeholders pending DeepSeek tower batch',
 'seed':0,'tile':TILE,'ceiling':CEILING,'step':STAIR,'player_clearance':56,
 'climb_landings':[160,320,480],'metres_at_64_units_per_metre':7.5,
 'sectors':len(sectors),'solid_3d_slabs':sum(len(k) for k in groups),'groups':{str(v):list(k) for k,v in groups.items()},
 'same_xy_multiple_solid_surfaces':list(cells[8,8]['slabs']),
 'walkthrough_route':[[160,96,0],[160,800,160],[864,800,160],[864,96,320],[160,96,320],[160,800,480],[352,800,480]],
 'files':{n:hashlib.sha256(d).hexdigest() for n,d in sorted(files.items())},
 'pk3_sha256':hashlib.sha256((OUT/'nullrun-tower-proof.pk3').read_bytes()).hexdigest()}
assert manifest['same_xy_multiple_solid_surfaces']==[160,320,480]
assert 0 < STAIR <= 24
for cell in cells.values():
    surfaces=[cell['floor'],*cell['slabs']]
    assert all(upper-8-lower >= 56 for lower,upper in zip(surfaces,surfaces[1:]))
    assert CEILING-surfaces[-1] >= 56
(OUT/'geometry.json').write_text(json.dumps(manifest,indent=2)+'\n')
(OUT/'TEXTMAP').write_text(text)
print(json.dumps({k:v for k,v in manifest.items() if k not in ['files','groups']},indent=2))
