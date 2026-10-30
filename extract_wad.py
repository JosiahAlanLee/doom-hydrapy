# SPDX-License-Identifier: GPL-2.0-or-later
"""Extract only music/demo lumps; preserve Freedoom bytes exactly."""
import argparse, hashlib, json, struct
from pathlib import Path

def extract(wad, output):
    data=Path(wad).read_bytes();magic,n,offset=struct.unpack_from('<4sII',data)
    if magic not in (b'IWAD',b'PWAD'): raise ValueError('not a WAD')
    output=Path(output);output.mkdir(parents=True,exist_ok=True);manifest=[]
    for i in range(n):
        pos,size,name=struct.unpack_from('<II8s',data,offset+16*i)
        name=name.rstrip(b'\0').decode('ascii');chunk=data[pos:pos+size]
        if name.startswith('D_') or name.startswith('DEMO'):
            ext='mid' if chunk.startswith(b'MThd') else 'mus' if chunk.startswith(b'MUS\x1a') else 'lmp'
            target=output/f'{name}.{ext}';target.write_bytes(chunk)
            manifest.append(dict(lump=name,file=target.name,size=size,sha256=hashlib.sha256(chunk).hexdigest()))
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('wad');p.add_argument('output');a=p.parse_args();extract(a.wad,a.output)
