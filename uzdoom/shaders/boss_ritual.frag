// SPDX-License-Identifier: GPL-3.0-or-later
// Argon ritual-feedback concept, adapted to native12-second/one-second rules.
// One fetch; no UV displacement or full-image tint. HUD and aiming stay exact.
void main() {
    vec4 original=texture2D(u_world,v_uv);
    if (!(u_strength>0.0 && u_strength<=1.0) || !(u_family>=1.0 && u_family<=4.0) ||
        !(u_progress>=0.0 && u_progress<=1.0) || !(u_open>=0.0 && u_open<=1.0) || abs(u_family-floor(u_family+.5))>.0001) {fragColor=original;return;}
    vec2 pixel=vec2(v_uv.x*640.0,(1.0-v_uv.y)*400.0);
    if(pixel.y<88.0 || pixel.y>=328.0 || (abs(v_uv.x-.5)<=.1 && abs(v_uv.y-.5)<=.1)) {fragColor=original;return;}
    float mask=0.0;vec3 colour=vec3(.86,.68,.28);int family=int(floor(u_family+.5));
    bool side=pixel.x>=12.0 && pixel.x<18.0 || pixel.x>=622.0 && pixel.x<628.0;
    if(u_open>0.0) {
        float position=(304.0-pixel.y)/8.0;
        if(side && position>=0.0 && position<24.0 && fract(position)<.72) {
            mask=1.0;colour=floor(position)<ceil(u_open*24.0)?vec3(.42,.84,.87):vec3(.23,.28,.29);
        }
    } else if(family==1) {
        float position=(pixel.y-160.0)/28.0;
        if(side && position>=0.0 && position<2.0 && fract(position)<.3) {
            mask=1.0;colour=floor(position)<floor(u_progress*2.0+.01)?vec3(.45,.84,.88):vec3(.80,.61,.28);
        }
    } else if(family==2) {
        if(side && pixel.y>=112.0 && pixel.y<304.0) {mask=1.0;colour=(304.0-pixel.y)/192.0<=u_progress?vec3(.74,.83,.88):vec3(.28,.32,.35);}
    } else if(family==3) {
        bool rail=abs(pixel.x-52.0)<2.0 || abs(pixel.x-588.0)<2.0;
        if(rail && pixel.y>=144.0 && pixel.y<280.0 && (u_progress<.5 || abs(pixel.y-212.0)>12.0)) {
            mask=1.0;colour=u_progress>=.5?vec3(.43,.85,.88):vec3(.86,.68,.28);
        }
    } else {
        // A/B status marks; actual world directions remain in the compact HUD.
        if(side && pixel.y>=152.0 && pixel.y<160.0) {mask=1.0;colour=u_progress>=.5?vec3(.92,.73,.33):vec3(.46,.39,.25);}
        if(side && pixel.y>=184.0 && pixel.y<192.0) {mask=1.0;colour=u_progress>=.5?vec3(.43,.85,.88):vec3(.25,.34,.35);}
    }
    fragColor=vec4(mix(original.rgb,colour,mask*u_strength),original.a);
}
