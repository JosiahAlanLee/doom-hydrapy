# SPDX-License-Identifier: GPL-3.0-or-later
"""Reviewed Argon GLSL kernels adapted to HydraPy texture-op functions."""
from pathlib import Path
import re
from hydrapy import add_op,Op,Input


def body(filename):
    source=(Path(__file__).with_name('shaders')/filename).read_text()
    code=source.split('void main() {',1)[1].rsplit('}',1)[0]
    for name,value in {'v_uv':'_st','u_world':'_tex','u_resolution':'resolution','u_strength':'cueStrength','u_progress':'cueProgress','u_active':'1.0'}.items():
        code=re.sub(r'\b'+name+r'\b',value,code)
    code=re.sub(r'fragColor\s*=\s*([^;]+);\s*return\s*;',r'return \1;',code)
    code=re.sub(r'fragColor\s*=\s*([^;]+);',r'return \1;',code)
    assert 'fragColor' not in code and 'u_' not in code
    return code


for name,filename in [('nullRunQuietCue','acoustic_stillness.frag'),('nullRunSurveyorCue','surveyor_bracket.frag')]:
    add_op(Op(name,'texture',[Input('cueStrength','float',0.,scalar=True),Input('cueProgress','float',0.,scalar=True)],
              glsl=body(filename),identity=('cueStrength',0.)))
