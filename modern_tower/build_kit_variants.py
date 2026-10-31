# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path
import argparse
import hashlib,json,re,struct,zipfile
parser=argparse.ArgumentParser(description='Adapt an original environment kit to isolated native UZDoom tower previews')
parser.add_argument('--kit',type=Path,required=True)
parser.add_argument('--base-map',type=Path,required=True,help='Directory produced by build_tower.py')
parser.add_argument('--output',type=Path,required=True,help='Fresh output directory')
args=parser.parse_args()
bank=args.kit.resolve();mapdir=args.base_map.resolve();base=mapdir/'nullrun-tower-proof.pk3'
if not (bank/'props3d.json').is_file() or not base.is_file() or not (mapdir/'TEXTMAP').is_file():
 parser.error('kit or base-map inputs are incomplete')
output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
props=json.loads((bank/'props3d.json').read_text())

def block(kind,fields):return kind+' { '+ ' '.join(f'{k} = {str(v).lower() if isinstance(v,bool) else json.dumps(v)};' for k,v in fields.items())+' }\n'
def wad(lumps):
 raw=bytearray();directory=[]
 for name,data in lumps:
  directory.append(struct.pack('<II8s',12+len(raw),len(data),name.encode().ljust(8,b'\0')));raw.extend(data)
 return struct.pack('<4sII',b'PWAD',len(lumps),12+len(raw))+raw+b''.join(directory)

for env,entry in props['sets'].items():
 if not re.fullmatch(r'[a-z][a-z0-9_]{0,63}',env):raise ValueError('Invalid environment id')
 if len(entry['props'])!=3:raise ValueError('This gallery expects three props per environment')
 out=output/env;out.mkdir()
 with zipfile.ZipFile(base) as z:files={n:z.read(n) for n in z.namelist()}
 text=(mapdir/'TEXTMAP').read_text()
 modeldefs=[];classes=[];editors=[];records=[]
 for i,row in enumerate(entry['props']):
  actor=f'NRTowerProp{i:02}';typ=15000+i
  for kind in ['obj','mtl','texture']:
   name=row[kind];path=(bank/name).resolve()
   if not path.is_relative_to(bank):raise ValueError('Asset path escapes kit')
   files[name]=path.read_bytes()
  obj=Path(row['obj']);texture=Path(row['texture'])
  # UZDoom's OBJ loader treats usemtl as a texture name rather than reading
  # map_Kd from an external MTL. Preserve the source and adapt only this copy.
  objtext=re.sub(r'(?m)^usemtl\s+.*$', 'usemtl '+row['texture'], files[row['obj']].decode())
  converted=[]
  for line in objtext.splitlines():
   fields=line.split()
   if fields and fields[0] in ('v','vn'):
    x,y,z=map(float,fields[1:4])
    # The bank is Z-up; the source-port OBJ model space is Y-up.
    line=f'{fields[0]} {x:.6f} {z:.6f} {-y:.6f}'
   converted.append(line)
  files[row['obj']]=('\n'.join(converted)+'\n').encode()
  modeldefs.append(f'''Model {actor} {{
 Path "{obj.parent.as_posix()}"
 Model 0 "{obj.name}"
 Skin 0 "{texture.name}"
 Scale 64 64 64
 FrameIndex COLU A 0 0
}}
''')
  classes.append(f'''class {actor} : Actor {{
 Default {{ Radius 32; Height 128; +NOGRAVITY +NOBLOCKMAP }}
 States {{ Spawn: COLU A -1; Stop; }}
}}
''')
  editors.append(f'{typ} = {actor}\n')
  x,y=[(352,416),(544,512),(736,640)][i]
  text+=block('thing',dict(x=x,y=y,height=0,angle=0,type=typ,skill1=True,skill2=True,skill3=True,skill4=True,skill5=True,single=True))
  records.append(dict(id=row['id'],actor=actor,position=[x,y,0],source_mesh_sha256=hashlib.sha256((bank/row['obj']).read_bytes()).hexdigest(),adapted_mesh_sha256=hashlib.sha256(files[row['obj']]).hexdigest(),axes='bank Z-up to engine Y-up: x,z,-y',collision='visual only; proxy not integrated'))
 for i in range(1,9):files[f'textures/TW{i:02}.png']=(bank/'art'/env/'walls'/f'{i:02}.png').read_bytes()
 for i in range(1,5):files[f'flats/TF{i:02}.png']=(bank/'art'/env/'flats'/f'{i:02}.png').read_bytes()
 files['ZSCRIPT']+=('\n'+''.join(classes)).encode()
 files['MODELDEF']='\n'.join(modeldefs).encode()
 files['MAPINFO']=files['MAPINFO'].replace(b'"NULL RUN / Tower geometry trial"',json.dumps('NULL RUN / '+entry['name']).encode())
 files['MAPINFO']+=('\nDoomEdNums { '+ ' '.join(editors)+' }\n').encode()
 files['maps/MAP01.wad']=wad([('MAP01',b''),('TEXTMAP',text.encode()),('ENDMAP',b'')])
 files['CREDITS.txt']=(bank/'CREDITS.md').read_bytes()+b'\nTower and native model adapter: Codex for Josiah Alan-Lee. External engine: UZDoom 5.0.3; external base art/weapons: Freedoom.\n'
 with zipfile.ZipFile(out/'nullrun-tower-proof.pk3','w',zipfile.ZIP_DEFLATED) as z:
  for name,data in sorted(files.items()):
   info=zipfile.ZipInfo(name,(2026,10,31,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data)
 (out/'models.json').write_text(json.dumps({'environment':env,'models':records,'bank_manifest_sha256':hashlib.sha256((bank/'manifest.json').read_bytes()).hexdigest()},indent=2)+'\n')
 print(env,len(files),'entries;',len(records),'native static model actors')
