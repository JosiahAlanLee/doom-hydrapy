// SPDX-License-Identifier: GPL-2.0-or-later
'use strict';
const $=id=>document.getElementById(id);
const token=document.querySelector('meta[name="run-token"]').content;
const controls=new Set(['KeyW','KeyA','KeyS','KeyD','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','KeyQ','KeyE','Space','ControlLeft','KeyF','ShiftLeft','ShiftRight','Tab','Digit1','Digit2','Digit3','Digit4','Digit5','Digit6','Digit7']);
let owner=null,playing=false,keys=new Set(),sending=false,lastState=null,busy=false;
async function post(path,data){
  const r=await fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-Run-Token':token},body:JSON.stringify(data)});
  const result=await r.json();if(!r.ok)throw new Error(result.error||'Connection failed.');return result;
}
function notice(text){$('notice').textContent=text;}
function overlay(label,title,text,button){
  $('overlay-label').textContent=label;$('overlay-title').textContent=title;$('overlay-text').textContent=text;
  $('play').replaceChildren(document.createTextNode(button));$('overlay').classList.remove('hidden');
}
function setPlaying(value){playing=value;document.body.classList.toggle('playing',value);if(value)$('overlay').classList.add('hidden');}
async function play(){
  if(busy)return;
  if(lastState?.dead||lastState?.won){await newRun(false);return;}
  try{owner=(await post('control',{})).owner;keys.clear();setPlaying(true);$('viewport').focus();notice('Find the bright floor tile. Your next floor keeps your health and weapons.');}
  catch(e){notice(e.message);}
}
async function pause(){
  const wasOwner=owner;setPlaying(false);keys.clear();owner=null;
  if(wasOwner){try{await post('input',{owner:wasOwner,keys:[],paused:true});}catch(e){notice(e.message);}}
  if(!lastState?.dead&&!lastState?.won)overlay('TAKE A BREATH','The run is paused.','Your position is waiting for you.','RESUME THE RUN ↗');
}
async function send(){
  if(!owner||!playing||sending)return;sending=true;
  try{await post('input',{owner,keys:[...keys]});}
  catch(e){notice(e.message);setPlaying(false);owner=null;keys.clear();overlay('CONTROLS RELEASED','Click to reconnect.',e.message,'TAKE THE CONTROLS ↗');}
  finally{sending=false;}
}
async function newRun(random){
  if(busy)return;
  const seed=random?crypto.getRandomValues(new Uint32Array(1))[0]:Number($('seed').value);
  if(!Number.isInteger(seed)||seed<0||seed>4294967295){notice('Use a whole-number seed from 0 to 4294967295.');return;}
  busy=true;$('new').disabled=$('retry').disabled=$('play').disabled=true;
  const currentOwner=owner;setPlaying(false);keys.clear();
  try{
    const state=await post('new',{seed,owner:currentOwner});owner=null;lastState=state;$('seed').value=seed;
    overlay('A NEW ARRANGEMENT','Same engine. New trouble.','Five connected floors. One life.','ENTER THE RUN ↗');
    notice('Run generated. Click Enter the Run when you’re ready.');
  }catch(e){notice(e.message);}
  finally{busy=false;$('new').disabled=$('retry').disabled=$('play').disabled=false;}
}
$('play').addEventListener('click',play);$('pause').addEventListener('click',pause);
$('new').addEventListener('click',()=>newRun(true));$('retry').addEventListener('click',()=>newRun(false));
$('viewport').addEventListener('click',()=>{if(playing)$('viewport').focus();});
document.addEventListener('keydown',e=>{
  if(e.target instanceof HTMLInputElement||e.target instanceof HTMLSelectElement)return;
  if(e.code==='Escape'){e.preventDefault();pause();return;}
  if(playing&&controls.has(e.code)){e.preventDefault();if(!keys.has(e.code)){keys.add(e.code);send();}}
});
document.addEventListener('keyup',e=>{if(controls.has(e.code)){if(playing)e.preventDefault();keys.delete(e.code);send();}});
window.addEventListener('blur',()=>{if(playing)pause();});
document.addEventListener('visibilitychange',()=>{if(document.hidden&&playing)pause();});
window.addEventListener('pagehide',()=>{if(owner)fetch('/api/input',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json','X-Run-Token':token},body:JSON.stringify({owner,keys:[],paused:true})});});
setInterval(send,120);

async function stateLoop(){
  try{
    const r=await fetch('/api/state');if(!r.ok)throw new Error('Server unavailable.');lastState=await r.json();
    const s=lastState;$('connection').textContent=s.error?'ENGINE ERROR':'ENGINE ONLINE';
    $('floor').textContent=s.floor_name;$('run-id').textContent='SEED '+s.seed;
    $('health').innerHTML=Number(s.health)+'<span>%</span>';$('armor').innerHTML=Number(s.armor)+'<span>%</span>';
    $('kills').innerHTML=Number(s.kills)+'<span>/ '+Number(s.total_kills)+'</span>';
    $('mode').textContent=s.dead?'RUN ENDED':s.won?'CLEARED':s.paused?'PAUSED':'LIVE / 35 HZ';
    $('status').textContent=s.dead?'The dungeon keeps what it takes.':s.won?'All five floors cleared.':s.paused?'Waiting for the next step.':'Floor '+s.map+' of '+s.floors+' · '+Math.floor(s.level_tics/35)+' seconds';
    if(s.dead||s.won||s.error){setPlaying(false);owner=null;keys.clear();
      overlay(s.won?'YOU FOUND A WAY OUT':s.error?'ENGINE PAUSED':'ONE LIFE. SPENT.',s.won?'The descent is complete.':s.error?'Something stopped the run.':'The labyrinth wins this time.',s.error||'Replay this seed, or start somewhere stranger.',s.error?'RETRY THE RUN ↻':'REPLAY THIS SEED ↻');
    }
  }catch(e){$('connection').textContent='RECONNECTING';notice(e.message);}
  setTimeout(stateLoop,300);
}

// The engine stays at its native tic rate. Treatments run in the browser's GL
// pipeline; turning one off restores the same unmodified game image.
const canvas=$('game'),gl=canvas.getContext('webgl',{alpha:false,antialias:false});
let drawImage;
if(gl){
  const vertex='attribute vec2 p;varying vec2 uv;void main(){uv=(p+1.)*.5;gl_Position=vec4(p,0.,1.);}';
  const fragment=`precision mediump float;varying vec2 uv;uniform sampler2D img;uniform float mode;uniform vec2 px;
  float lum(vec3 c){return dot(c,vec3(.299,.587,.114));}
  void main(){vec2 v=vec2(uv.x,1.-uv.y);vec3 c=texture2D(img,v).rgb;float l=lum(c);
    if(mode>.5&&mode<1.5){float s=.9+.1*sin(v.y*1256.);c=vec3(.18,1.,.43)*l*s;}
    else if(mode>1.5&&mode<2.5){float x=lum(texture2D(img,v+vec2(px.x,0.)).rgb);float y=lum(texture2D(img,v+vec2(0.,px.y)).rgb);float edge=clamp(length(vec2(l-x,l-y))*5.,0.,1.);c=mix(vec3(.91,.92,.84),vec3(.04,.09,.07),max(edge,(1.-l)*.3));}
    else if(mode>2.5){float q=floor(l*3.99)/3.;c=mix(vec3(.08,.12,.13),vec3(.91,.93,.78),q);}
    gl_FragColor=vec4(c,1.);}`;
  function shader(type,source){const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw new Error(gl.getShaderInfoLog(s));return s;}
  const program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,vertex));gl.attachShader(program,shader(gl.FRAGMENT_SHADER,fragment));gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw new Error(gl.getProgramInfoLog(program));gl.useProgram(program);
  const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),gl.STATIC_DRAW);
  const loc=gl.getAttribLocation(program,'p');gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,2,gl.FLOAT,false,0,0);
  const texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,texture);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.NEAREST);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.NEAREST);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
  const mode=gl.getUniformLocation(program,'mode');gl.uniform2f(gl.getUniformLocation(program,'px'),1/640,1/400);
  drawImage=image=>{gl.texImage2D(gl.TEXTURE_2D,0,gl.RGB,gl.RGB,gl.UNSIGNED_BYTE,image);gl.uniform1f(mode,Number($('filter').value));gl.drawArrays(gl.TRIANGLE_STRIP,0,4);};
}else{
  // A browser that refuses WebGL still gets playable raw video.
  const fallback=document.createElement('canvas');fallback.width=640;fallback.height=400;canvas.replaceWith(fallback);
  const ctx=fallback.getContext('2d');drawImage=image=>ctx.drawImage(image,0,0);$('filter').disabled=true;
}
async function frameLoop(){
  const start=performance.now();
  try{const r=await fetch('/api/frame');if(r.ok){const bitmap=await createImageBitmap(await r.blob());drawImage(bitmap);bitmap.close();}}
  catch(e){/* state poll reports connection failures */}
  setTimeout(frameLoop,Math.max(0,1000/30-(performance.now()-start)));
}
stateLoop();frameLoop();
