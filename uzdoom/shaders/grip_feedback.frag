// SPDX-License-Identifier: GPL-3.0-or-later
// Argon ReDead warning/cage concept; active grip is distinct from escape0.
void main() {
    vec4 original=texture2D(u_world,v_uv);
    if (!(u_strength>0.0 && u_strength<=1.0) || !(u_progress>=0.0 && u_progress<=1.0) ||
        !(u_open>=0.0 && u_open<=1.0) || !(u_grip>=0.0 && u_grip<=1.0)) {fragColor=original;return;}
    vec2 pixel=vec2(v_uv.x*640.0,(1.0-v_uv.y)*400.0);
    if(pixel.y<88.0 || pixel.y>=328.0 || (abs(v_uv.x-.5)<=.1 && abs(v_uv.y-.5)<=.1)) {fragColor=original;return;}
    float mask=0.0;vec3 colour=vec3(.82,.65,.36);
    if(u_grip>.5) {
        if((pixel.x<64.0 || pixel.x>=576.0) && pixel.y>=104.0 && pixel.y<312.0 && mod(pixel.x,16.0)<3.0) {
            mask=.65;colour=mix(vec3(.63,.43,.34),vec3(.52,.81,.78),u_progress);
        }
        float position=(304.0-pixel.y)/7.0;
        bool rail=pixel.x>=80.0 && pixel.x<85.0 || pixel.x>=555.0 && pixel.x<560.0;
        if(rail && position>=0.0 && position<28.0 && fract(position)<.7) {
            mask=1.0;colour=floor(position)<floor(u_progress*28.0+.5)?vec3(.53,.86,.83):vec3(.48,.32,.27);
        }
    } else {
        float offset=mix(18.0,0.0,u_open);
        bool left=pixel.x>=48.0 && pixel.x<96.0;
        bool right=pixel.x>=544.0 && pixel.x<592.0;
        float dx=left?96.0-pixel.x:pixel.x-544.0;
        if((left || right) && abs(abs(pixel.y-208.0)-(dx*.8+offset))<2.0 && dx>=0.0) {mask=1.0;colour=mix(vec3(.82,.65,.36),vec3(.91,.54,.31),u_open);}
    }
    fragColor=vec4(mix(original.rgb,colour,mask*u_strength),original.a);
}
