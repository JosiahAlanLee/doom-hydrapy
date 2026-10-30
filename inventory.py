# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parent;out=r.parent/'doom-hydrapy-20261030';plugins=out.parent/'gorgon-r3b-20261030/take/rack-user/plugins-lin-x64'
items=[]
capacities=dict(CZishLab='8 independent voices in single-line mode; paired-line modes have 4',VastishLab='8 voices, mono stereo-pair output',OtisLab='OTIS Sampler: 16 mono / 8 stereo at engineMode 0; Kit: 8 retriggerable slots',SeanceLab='sums poly input to mono; spectral effect, not a voice allocator',SpoonBenderLab='stereo effect; not a MIDI voice allocator',GorgonBridge='6 tracker lanes; master transport and clock')
for slug,capacity in capacities.items():
    p=plugins/slug;meta=json.loads((p/'plugin.json').read_text());binary=p/'plugin.so'
    items.append(dict(slug=slug,version=meta['version'],capacity=capacity,plugin_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),path=str(binary)))
(out/'poly/inventory.json').write_text(json.dumps(items,indent=2)+'\n')
print('Inventoried',len(items),'installed plugin binaries')
