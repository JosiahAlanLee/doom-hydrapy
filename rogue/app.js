// SPDX-License-Identifier: GPL-2.0-or-later
'use strict';
const $=id=>document.getElementById(id);
const token=document.querySelector('meta[name="run-token"]').content;
const controls=new Set(['KeyW','KeyA','KeyS','KeyD','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','KeyQ','KeyE','Space','ControlLeft','KeyF','ShiftLeft','ShiftRight','Tab','Digit1','Digit2','Digit3','Digit4','Digit5','Digit6','Digit7']);
let owner=null,playing=false,keys=new Set(),sending=false,lastState=null,busy=false,seenRevision=null;
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
    const state=await post('new',{seed,owner:currentOwner,mode:$('run-mode').value});owner=null;lastState=state;$('seed').value=seed;
    overlay('A NEW ARRANGEMENT','The night shift begins.',state.mode==='campaign'?'Seven tiers. Two demons hold each exit.':state.study_rule||'Find the marked ring. Open the passage.','ENTER THE RUN ↗');
    notice('Run generated. Click Enter the Run when you’re ready.');
  }catch(e){notice(e.message);}
  finally{busy=false;$('new').disabled=$('retry').disabled=$('play').disabled=false;}
}
$('play').addEventListener('click',play);$('pause').addEventListener('click',pause);
$('new').addEventListener('click',()=>newRun(true));$('retry').addEventListener('click',()=>newRun(false));
$('credits-panel').addEventListener('toggle',()=>{if($('credits-panel').open&&playing)pause();});
for(const id of ['seed','run-mode'])$(id).addEventListener('focus',()=>{if(playing)pause();});
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
    if(seenRevision!==s.revision){seenRevision=s.revision;$('run-mode').value=s.mode;$('seed').value=s.seed;}
    $('run-length').textContent=s.mode==='campaign'?'SEVEN TIERS / ONE LIFE':s.study_family==='architecture'?'ARCHITECTURE STUDY. WATCH YOUR WAY BACK.':s.study_rule?'GLOAMWOOD STUDY. ONE LIFE.':'BINDING STUDY. ONE LIFE.';
    $('floor').textContent=(s.office?s.office.name+' / ':'')+s.floor_name;$('run-id').textContent='SEED '+s.seed;
    $('health').innerHTML=Number(s.health)+'<span>%</span>';$('armor').innerHTML=Number(s.armor)+'<span>%</span>';
    $('kills').innerHTML=Number(s.kills)+'<span>/ '+Number(s.total_kills)+'</span>';
    $('mode').textContent=s.dead?'RUN ENDED':s.won?'CLEARED':s.paused?'PAUSED':'EXPLORING';
    $('status').textContent=s.dead?'The dungeon keeps what it takes.':s.won?'All seven tiers cleared.':s.paused?'Waiting for the next step.':'Tier '+s.map+' of '+s.floors+' · '+Math.floor(s.level_tics/35)+' seconds';
    if(s.won&&s.mode!=='campaign')$('status').textContent='You found the way out. Study complete.';
    const b=s.boss;$('boss-panel').hidden=!b;
    if(b){
      const pair=s.bosses||[b],exitOpen=pair.every(d=>d.phase==='bound');
      $('boss-roster').textContent=pair.map(d=>d.name+' / '+d.phase.toUpperCase()).join(' · ');
      $('boss-panel').dataset.phase=b.phase;$('boss-name').textContent=b.name;
      $('boss-phase').textContent=b.phase==='bound'?(exitOpen?'BOUND / EXIT OPEN':'BOUND / OTHER DEMON REMAINS'):b.phase==='exposed'?'EXPOSED / '+(b.open_ticks/35).toFixed(1)+'s':'SEALED / BINDING REQUIRED';
      $('boss-health').textContent=b.health+' / '+b.max_health+' HEALTH';$('boss-hp').max=b.max_health;$('boss-hp').value=b.health;
      const maximum=b.class===6?70:2;
      $('boss-binding').max=maximum;$('boss-binding').value=b.phase==='exposed'?maximum:b.class===5?b.stamps:b.class===6?b.still_ticks:b.class===9?Number(b.proof):b.gate_stage;
      $('boss-progress').textContent=b.phase==='bound'?(exitOpen?'EXIT UNLOCKED':'OTHER DEMON REMAINS'):b.phase==='exposed'?'STRIKE NOW':b.class===5?'PRESENTATIONS / '+b.stamps+' OF 2':b.class===6?'QUIET / '+Math.round(b.still_ticks/70*100)+'%':b.class===9?(b.proof?'PROOF RECORDED / RETURN TO RING':'PROOF REQUIRED / HIT THE SHIELD'):(b.gate_stage?'A ACCEPTED / CROSS INTO B':'ENTER THE AMBER A RING');
      $('boss-rule').textContent=b.phase==='bound'?(exitOpen?'The exit will now let you pass.':'Bind and defeat the other demon to open the exit.'):b.phase==='exposed'?'The seal is open. Hurt the demon before it closes.':(b.on_seal?'ON THE RING. ':'FIND THE GLOWING RING. ')+s.boss_rule;
    }
    const c=s.creatures||{},gripped=c.effect==='grip',warning=c.shriek_warning>0;
    $('creature-panel').hidden=!(s.study_family==='creature'||c.watched||c.hunting||c.effect||warning);
    $('creature-panel').dataset.danger=gripped||warning?'yes':'no';
    $('grip-escape').hidden=!gripped;$('grip-escape').value=c.escape_ticks||0;
    $('creature-name').textContent=gripped?'BREAK THE GRIP':c.effect==='shriek'?'STONE REDEAD / SHRIEK':warning?'STONE REDEAD / TAKE COVER':c.hunting?'THE HOLLOW / MOVING':c.watched?'THE HOLLOW / WATCHED':s.mode==='redead'?'STONE REDEAD':'THE HOLLOW';
    $('creature-rule').textContent=gripped?'Hold F until the bar fills, or hurt the creature. You can still turn and fire.':c.effect==='shriek'?'Movement will return shortly. You can still turn and fire.':warning?'Its mask is raised. Break line of sight before the shriek lands.':c.hunting?'Something is crawling while you look away.':c.watched?'You are holding it still. It will move when you look away.':s.study_rule||'Watch the split tree. Look away and it crawls.';
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
    else if(mode>2.5&&mode<3.5){float q=floor(l*3.99)/3.;c=mix(vec3(.08,.12,.13),vec3(.91,.93,.78),q);}
    // Argon's doomSobelVectorScope kernel, adapted by Codex for this standalone
    // browser. Central differences and red/amber hazard isolation are retained;
    // the capture scene's feedback and tracker modulation are not reproduced.
    else if(mode>3.5){
      vec3 wl=vec3(.2126,.7152,.0722);
      vec3 cx1=texture2D(img,v+vec2(px.x,0.)).rgb,cx0=texture2D(img,v-vec2(px.x,0.)).rgb;
      vec3 cy1=texture2D(img,v+vec2(0.,px.y)).rgb,cy0=texture2D(img,v-vec2(0.,px.y)).rgb;
      float gx=dot(cx1-cx0,wl),gy=dot(cy1-cy0,wl),l0=dot(c,wl);
      float grad=clamp(length(vec2(gx,gy))*2.4*2.2,0.,1.);
      float wall=abs(gx)/(abs(gx)+abs(gy)+.0001);
      float red=clamp(c.r-max(c.g,c.b)*.85,0.,1.);
      float muzzle=clamp((l0-.62)*2.5,0.,1.)*clamp(c.r-c.b,0.,1.);
      float haz=clamp((red*1.8+muzzle*1.5)*1.4,0.,1.);
      c=vec3(grad*(.12+.25*(1.-wall))+haz*.98,grad*(.85+.15*wall)+haz*.36,grad*(.45+.5*wall)+haz*.14)+c*.35*.35;
      c=clamp(c*(.82+.18*sin(v.y*200.*6.2831853)),0.,1.);
    }
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
