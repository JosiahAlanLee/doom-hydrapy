# SPDX-License-Identifier: GPL-2.0-or-later
from hydrapy import add_op as register,Op,Input
register(Op('doomAscii','texture',[Input('columns','float',80)],glsl="""
vec2 cells=vec2(columns,columns*0.6);
vec2 uv=(floor(_st*cells)+0.5)/cells;
vec3 col=texture2D(_tex,uv).rgb;
float level=floor(clamp(dot(col,vec3(.2126,.7152,.0722)),0.0,.999)*8.0);
float bits=0.0;
if(level==0.0) bits=0.0;
if(level==1.0) bits=6684672.0;
if(level==2.0) bits=6686304.0;
if(level==3.0) bits=3840.0;
if(level==4.0) bits=28512.0;
if(level==5.0) bits=618345.0;
if(level==6.0) bits=390645.0;
if(level==7.0) bits=14802902.0;

vec2 p=floor(fract(_st*cells)*vec2(4.,6.));
float bit=mod(floor(bits/exp2(p.x+4.*p.y)),2.);
return vec4(vec3(.1,.95,.62)*bit,1.0);
"""))
