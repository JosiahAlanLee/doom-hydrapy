# SPDX-License-Identifier: GPL-2.0-or-later
"""Fine screens for the tick-locked Doom source (1080p target)."""
from hydrapy import add_op, Op, Input
# A strictly increasing 4x6 coverage ramp; values fit exactly in GLSL float.
patterns=[' '*24, ' '*9+'##'+' '*13, ' '*5+'##'+' '*6+'##'+' '*9,
          '    '+' ## '+'####'+' ## '+'    '+'    ',
          '#  #'+' ## '+'####'+' ## '+'#  #'+' ## ',
          '# # '+'####'+'# # '+'####'+'# # '+'####',
          '####'+'### '+'####'+' ###'+'####'+'####', '#' *24]
bits=[sum((c!=' ')*(1<<i) for i,c in enumerate(p)) for p in patterns]
code='''
// Match glyph aspect to output pixels; double horizontal HUD resolution.
float cols=(_st.y<0.16 || _st.y>0.84)?320.0:columns;
vec2 cells=vec2(cols,cols*0.375);
vec2 uv=(floor(_st*cells)+0.5)/cells;
vec2 d=vec2(1.0/320.0,1.0/200.0);
vec3 col=texture2D(_tex,uv).rgb;
vec3 avg=(texture2D(_tex,uv+vec2(d.x,0)).rgb+texture2D(_tex,uv-vec2(d.x,0)).rgb+
 texture2D(_tex,uv+vec2(0,d.y)).rgb+texture2D(_tex,uv-vec2(0,d.y)).rgb)*.25;
vec3 sharp=clamp(col+(col-avg)*.65,0.,1.);
float lum=dot(sharp,vec3(.2126,.7152,.0722));
float level=floor(clamp(pow(lum,.72),0.,.999)*8.);
float bits=0.;
'''+''.join(f'if(level=={i}.) bits={v}.;\n' for i,v in enumerate(bits))+'''
vec2 p=floor(fract(_st*cells)*vec2(4.,6.));
float bit=mod(floor(bits/exp2(p.x+4.*p.y)),2.);
vec3 hue=mix(vec3(.1,.95,.62),sharp/(max(max(sharp.r,sharp.g),sharp.b)+.001),.55);
vec3 base=texture2D(_tex,_st).rgb;
return vec4(base*.32+hue*bit*.78,1.);
'''
add_op(Op('doomLegibleAscii','texture',[Input('columns','float',240)],glsl=code))
add_op(Op('doomLegiblePrint','texture',[],glsl='''
// Incoming texture is already nearest-neighbour expanded by the source chain.
vec3 col=texture2D(_tex,_st).rgb;
float lum=dot(col,vec3(.2126,.7152,.0722));
vec2 p=fract(_st*vec2(480.,300.))-.5;
float dotInk=1.-smoothstep(sqrt(lum)*.63-.08,sqrt(lum)*.63+.08,length(p));
vec3 ink=vec3(1.,.82,.59);
return vec4(mix(col*ink,ink*dotInk,.38),1.);
'''))
