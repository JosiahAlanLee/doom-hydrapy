# SPDX-License-Identifier: GPL-2.0-or-later
"""Argon's flashbulb-Hollow concept: a marked native sector study."""
import struct
from rogue.inhabitants import options

STROBES = {'strobe': {'name':'FLUORESCENT HOLLOW / THE GLOAMWOOD',
                     'rule':'It moves when the tube fails. Real shots pin it for six tics while you watch. Retreat to the lit alcove.'}}


def study(seed):
    from rogue.maps import Floor, distances
    if isinstance(seed,bool) or not isinstance(seed,int) or not 0<=seed<=0xffffffff: raise ValueError('Unsigned seed required')
    cells={(x,y) for x in range(2,7) for y in range(2,9)}
    cells|={(x,y) for x in range(7,19) for y in range(4,7)}
    cells-={(9,4),(12,6),(15,4)}
    profiles={p:dict(floor=0,height=160,light=208,wall='STONE2',flat='FLAT5_4',ceiling='CEIL5_1',tag=1401 if p[0]>=7 else 0,shape='strobe-hall') for p in cells}
    start,exit_cell=(5,5),(18,5);profiles[exit_cell]['tag']=0
    parent=distances(cells,start);route=[exit_cell]
    while route[-1]!=start:route.append(parent[route[-1]])
    route.reverse();px,py=5*128+64,5*128+64;mx,my=13*128+64,5*128+64
    things=[(px,py,0,1,7),(mx,my,180,66,options('hollow',seed%16)),
            (px+40,py,0,2001,7),(px,py,0,2048,7),(px,py,0,2049,7),
            (px,py,0,2018,7),(3*128+64,3*128+64,0,2012,7)]
    return Floor(1,cells,[(2,2,6,8)],start,exit_cell,route,things,
                 ('STUDY / FLUORESCENT HOLLOW','STONE2','FLAT5_4','CEIL5_1',208),
                 {'rooms':[{'shape':'strobe-hall'}],'max_step':0,'strobe':{'bpm':120,'duty_percent':38,'tag':1401}},
                 profiles,[{'kind':'hollow','roll':seed%16,'x':mx,'y':my}])


def metadata(floor):
    s=floor.architecture['strobe']
    return 'RSTROBE',struct.pack('<4s4i',b'RST1',floor.number,s['bpm'],s['duty_percent'],s['tag'])
