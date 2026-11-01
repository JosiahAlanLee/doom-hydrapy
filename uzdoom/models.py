# SPDX-License-Identifier: GPL-3.0-or-later
"""Pack reviewed, same-topology OBJ poses as native MD3 morph frames.

Worker originals stay Z-up. MD3 uses native Z-up coordinates; the OBJ loader's
Y-up conversion is intentionally not applied here. UV seams get separate
vertices so a shared position can retain different atlas coordinates/normals.
"""
from pathlib import Path
import math
import struct
import json

BOSSES = ('absentiel','calmor','choraz','consenth','exceptor','jurisiel','margor',
          'posthum','probator','promissor','redacth','repetiel','scriptorax','velaroth')
MOBS = {7:'hollow',8:'reded',11:'surveyor',14:'vore'}
KEYS = BOSSES + tuple(MOBS.values())


def doom_ed_numbers():
    return ' '.join([*(f'{18000+i} = NRMesh{key.title()}' for i,key in enumerate(KEYS)),
                     *(f'{18100+i} = NRInstallation{i}' for i in range(3))])


def actor_id(kind, title=None):
    key = title.lower() if title else MOBS.get(kind)
    return 18000 + KEYS.index(key) if key in KEYS else 16000


def obj(path):
    vertices=[];uv=[];triangles=[]
    for line in path.read_text().splitlines():
        f=line.split()
        if not f:continue
        if f[0]=='v':vertices.append(tuple(map(float,f[1:4])))
        elif f[0]=='vt':uv.append(tuple(map(float,f[1:3])))
        elif f[0]=='f':
            face=[]
            for item in f[1:]:
                p=item.split('/');v=int(p[0]);t=int(p[1])
                face.append((v-1 if v>0 else len(vertices)+v,t-1 if t>0 else len(uv)+t))
            for i in range(1,len(face)-1):triangles.append((face[0],face[i],face[i+1]))
    if not vertices or not triangles or len(triangles)>1200:raise ValueError('Invalid model budget')
    if not all(math.isfinite(v) for row in vertices+uv for v in row):raise ValueError('Nonfinite model')
    for tri in triangles:
        for v,t in tri:
            if not 0<=v<len(vertices) or not 0<=t<len(uv):raise ValueError('Invalid OBJ index')
    return vertices,uv,triangles


def md3(poses, skin, scale=72):
    """One surface, morph frames, flat normals and explicit atlas seams."""
    parsed=[obj(p) for p in poses]
    vertices,uv,faces=parsed[0]
    if any(len(v)!=len(vertices) or u!=uv or f!=faces for v,u,f in parsed[1:]):
        raise ValueError('Pose topology or UV order changed')
    # A per-triangle vertex keeps hard-edged Quake-era faces hard, including
    # where the source reused its positions across differently oriented faces.
    corners=[corner for tri in faces for corner in tri]
    count=len(corners);frames=len(poses)
    if count>4096:raise ValueError('MD3 surface vertex budget')
    tris=b''.join(struct.pack('<3i',i,i+1,i+2) for i in range(0,count,3))
    shaders=struct.pack('<64si',skin.encode(),0)
    sts=b''.join(struct.pack('<2f',uv[t][0],1-uv[t][1]) for v,t in corners)
    packed=[];frame_headers=[]
    for path,(vs,_,_) in zip(poses,parsed):
        points=[tuple(c*scale for c in v) for v in vs]
        minimum=[min(p[i] for p in points) for i in range(3)]
        maximum=[max(p[i] for p in points) for i in range(3)]
        radius=max(math.sqrt(sum(c*c for c in p)) for p in points)
        frame_headers.append(struct.pack('<10f16s',*minimum,*maximum,0,0,0,radius,path.stem.encode()[:15]))
        for tri in faces:
            a,b,c=[points[v] for v,t in tri]
            u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
            n=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
            length=math.sqrt(sum(x*x for x in n))
            n=tuple(x/length for x in n) if length>1e-10 else (0,0,1)
            lat=round(math.atan2(n[1],n[0])*256/(2*math.pi))&255
            lng=round(math.acos(max(-1,min(1,n[2])))*256/(2*math.pi))&255
            for vi,ti in tri:
                q=tuple(round(c*64) for c in points[vi])
                if any(not -32768<=c<=32767 for c in q):raise ValueError('MD3 coordinate overflow')
                packed.append(struct.pack('<3hBB',*q,lng,lat))
    xyzn=b''.join(packed)
    ot=108;os=ot+len(tris);ost=os+len(shaders);ox=ost+len(sts);end=ox+len(xyzn)
    surface=struct.pack('<4s64s10i',b'IDP3',b'nullrun',0,frames,1,count,len(faces),ot,os,ost,ox,end)+tris+shaders+sts+xyzn
    of=108;tags=of+56*frames;surf=tags
    header=struct.pack('<4si64s9i',b'IDP3',15,b'nullrun',0,frames,0,1,0,of,tags,surf,surf+len(surface))
    return header+b''.join(frame_headers)+surface


def artwork(root):
    files={};definitions=[];classes=[];numbers=[]
    for i,key in enumerate(KEYS):
        folder=Path(root)/key
        moves=('move','neutral') if key in BOSSES else ('locomotion_a','locomotion_b')
        poses=[folder/f'{key}_{pose}.obj' for pose in ('neutral',*moves,'warning','attack','hurt','death')]
        prefix='models/actors/'+key;skin=key+'_atlas.png';cls='NRMesh'+key.title()
        files[prefix+'/'+key+'.md3']=md3(poses,prefix+'/'+skin)
        files[prefix+'/'+skin]=(folder/skin).read_bytes()
        frames=' '.join(f'FrameIndex NRMA {chr(65+n)} 0 {n}' for n in range(7))
        definitions.append(f'Model {cls} {{ Path "{prefix}" Model 0 "{key}.md3" Skin 0 "{skin}" Scale 1 1 1 AngleOffset -90 {frames} }}')
        classes.append(f'class {cls} : NRMeshMonster {{ }}')
        numbers.append(f'{18000+i} = {cls}')
    return files,'\n'.join(definitions),'\n'.join(classes),' '.join(numbers)


def installation_specs(root):
    rows=json.loads((Path(root)/'manifest.json').read_text())['props']
    result=[]
    for i,(key,row) in enumerate(sorted(rows.items())):
        row=dict(row);row.update(key=key,type=18100+i)
        # Conservatively contain the whole art mesh in a physical cylinder.
        bounds=[max(abs(row['bounds_min'][j]),abs(row['bounds_max'][j])) for j in range(2)]
        row['radius']=math.ceil(math.hypot(*bounds)*32)
        row['height']=math.ceil(row['height_m']*32)
        result.append(row)
    return result


def installation_artwork(root):
    root=Path(root);files={};definitions=[];classes=[]
    for i,row in enumerate(installation_specs(root)):
        key=row['key'];folder=root/key;prefix='models/installations/'+key;skin=key+'_atlas.png'
        files[prefix+'/'+key+'.md3']=md3([folder/(key+'.obj')],prefix+'/'+skin,32)
        files[prefix+'/'+skin]=(folder/skin).read_bytes()
        cls=f'NRInstallation{i}'
        definitions.append(f'Model {cls} {{ Path "{prefix}" Model 0 "{key}.md3" Skin 0 "{skin}" Scale 1 1 1 AngleOffset -90 FrameIndex NRMA A 0 0 }}')
        classes.append(f'class {cls} : Actor {{ Default {{ Radius {row["radius"]}; Height {row["height"]}; +SOLID +NOGRAVITY }} States {{ Spawn: NRMA A -1; Stop; }} }}')
    return files,'\n'.join(definitions),'\n'.join(classes)
