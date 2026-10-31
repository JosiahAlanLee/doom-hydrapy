# SPDX-License-Identifier: GPL-2.0-or-later
"""GPU treatments adapted from Argon's green-line/strobe proposal."""
from hydrapy import Input,Op,add_op

add_op(Op('nullrunScreen','texture',[
    Input('light','float',1),Input('muzzle','float',0),
    Input('mode','float',1),Input('flicker','float',1),Input('music','float',0)],glsl='''
vec3 c=texture2D(_tex,_st).rgb;
// The status line and original Doom HUD remain readable through a blackout.
if(_st.y<0.16 || _st.y>0.94 || mode<0.5)return vec4(c,1.);
vec2 px=vec2(1./640.,1./400.);
vec3 wl=vec3(.2126,.7152,.0722);
float l=dot(c,wl);
float gx=dot(texture2D(_tex,_st+vec2(px.x,0.)).rgb-texture2D(_tex,_st-vec2(px.x,0.)).rgb,wl);
float gy=dot(texture2D(_tex,_st+vec2(0.,px.y)).rgb-texture2D(_tex,_st-vec2(0.,px.y)).rgb,wl);
float edge=clamp(length(vec2(gx,gy))*6.8*(1.+clamp(music*3.,0.,.35)),0.,1.);
vec2 fpx=_st*vec2(640.,400.);
float grid=clamp(step(mod(fpx.x,4.),1.)+step(mod(fpx.y,4.),1.),0.,1.)*edge;
float red=clamp(c.r-max(c.g,c.b)*.78,0.,1.);
float warm=clamp(c.r*.75-c.b*.35,0.,1.)*step(.20,l);
float vis=flicker>.5?clamp(light+muzzle*1.15,.04,1.):1.;
vec3 rgb=vec3(warm*.82+red*1.35+edge*.16+grid*.24,
              edge*.96+grid*.48+l*.28+red*.26,
              edge*.68+grid*.34+l*.14+red*.10)*vis;
rgb+=muzzle*edge*vec3(.65,.35,.04);
if(mode>1.5 && mode<2.5){
 vec2 cells=vec2(160.,80.);
 vec2 uv=(floor(_st*cells)+.5)/cells;
 float level=floor(clamp(pow(dot(texture2D(_tex,uv).rgb,wl),.72),0.,.999)*8.);
 // Eight ordered 4x6 dot densities, evaluated on the GPU.
 vec2 q=floor(fract(_st*cells)*vec2(4.,6.));
 float rank=mod(q.x*7.+q.y*3.,24.);
 float ink=step(rank,level*3.);
 rgb=c*.24+vec3(.12,.94,.63)*ink*vis;
}else if(mode>2.5){
 vec3 paper=vec3(.90,.82,.65),ink=vec3(.10,.13,.10);
 float tone=floor(clamp(l*1.4,0.,.999)*4.)/3.;
 rgb=mix(ink,paper,tone)*vis;
}
return vec4(clamp(rgb,0.,1.),1.);
'''))
