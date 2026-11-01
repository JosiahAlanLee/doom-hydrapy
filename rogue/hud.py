# SPDX-License-Identifier: GPL-2.0-or-later
"""Null Run's own signage and instruments; no original Doom status graphics."""
from functools import lru_cache
from pathlib import Path
from PIL import ImageDraw,ImageFont

FONT=Path(__file__).resolve().parents[1]/'assets/fonts/DepartureMono-Regular.otf'
INK=(221,220,204);MUTED=(134,153,159);AMBER=(230,165,87);DANGER=(237,119,102)
PANEL=(16,24,29);LINE=(65,86,93)
WEAPONS=['HANDS','SIDEARM','SCATTER','ROTARY','ROCKET','PLASMA','CELL CANNON','SAW','DOUBLE']
AMMO=[None,0,1,0,3,2,2,None,1]

@lru_cache(maxsize=4)
def font(size=11):return ImageFont.truetype(str(FONT),size)

def text(draw,xy,value,colour=INK,size=11):
    draw.text(xy,str(value),font=font(size),fill=colour)

def bar(draw,x,y,width,value,colour):
    draw.rectangle((x,y,x+width,y+2),fill=(39,51,56))
    value=max(0,min(float(value or 0),100))
    if value:draw.rectangle((x,y,x+round(width*value/100),y+2),fill=colour)

def decorate(image,state):
    """Paint the same instrument panel over native and browser game frames."""
    image=image.copy();d=ImageDraw.Draw(image)
    health=int(state.get('health',0));armour=int(state.get('armor',0))
    weapon=min(max(int(state.get('weapon',0)),0),len(WEAPONS)-1)
    ammo=state.get('ammo',[0,0,0,0]);slot=AMMO[weapon]
    rounds='--' if slot is None else str(ammo[slot])
    d.rectangle((0,0,639,22),fill=PANEL)
    d.line((0,22,639,22),fill=LINE)
    text(d,(12,5),'NULL RUN',AMBER)
    text(d,(80,5),' / '+state.get('floor_name','THRESHOLD'),INK)
    upkeep=state.get('vending') or {}
    if upkeep.get('active'):text(d,(436,5),f"SCRAP {upkeep['credits']:03}",AMBER)
    direction=['E','NE','N','NW','W','SW','S','SE'][round(float(state.get('angle',0))/45)%8]
    text(d,(540,5),f"{state.get('map',1):02}/{state.get('floors',7):02}  {direction}",MUTED)
    vendor=upkeep.get('vendor') or {}
    cue=(state.get('argon') or {}).get('cue')
    if vendor.get('near') and not upkeep.get('menu_open'):
        cue='UPKEEP / DISPENSED THIS FLOOR' if vendor.get('spent') else 'F / RIGHT CLICK : UPKEEP'
    if cue:
        width=round(d.textlength(cue,font=font()))
        x=max(10,(640-width)//2)
        d.rectangle((x-8,30,x+width+8,49),fill=(44,34,24))
        text(d,(x,34),cue,AMBER)
    pair=state.get('bosses') or []
    if pair and not state.get('paused',False):
        d.rectangle((8,54,631,86),fill=PANEL)
        text(d,(14,57),' / '.join(b['name']+' '+b['phase'].upper() for b in pair),MUTED)
        current=state.get('boss') or {}
        rules={5:'Ring: tap F twice; release between taps.',6:'Ring: stay still without firing for 2s.',
               9:'Shoot its shield, then ring + F.',10:'Cross its amber A ring, then its cyan B ring.'}
        if current.get('phase')=='bound':
            hint='BOTH BOUND / EXIT OPEN' if all(b['phase']=='bound' for b in pair) else 'THE OTHER DEMON STILL HOLDS THE EXIT'
        else:hint=current.get('name','')+' / '+rules.get(current.get('class'),'')+'  [8s opening]'
        text(d,(14,72),hint,AMBER)
    # Four tiny marks preserve an unobstructed centre instead of a large reticle.
    for a,b in [((315,194),(317,194)),((323,194),(325,194)),((320,189),(320,191)),((320,197),(320,199))]:
        d.line((a,b),fill=(180,188,178))
    d.rectangle((0,353,639,399),fill=PANEL)
    d.line((0,353,639,353),fill=LINE)
    for x in (169,301,419):d.line((x,362,x,390),fill=LINE)
    cap=upkeep.get('max_health',100)
    text(d,(12,359),f'HEALTH /{cap}' if cap>100 else 'HEALTH',MUTED);text(d,(12,372),max(0,health),DANGER if health<25 else INK,22)
    bar(d,75,389,75,100*health/max(1,cap),DANGER if health<25 else AMBER)
    text(d,(184,359),'ARMOUR',MUTED);text(d,(184,377),max(0,armour),INK)
    bar(d,233,389,52,armour,(129,174,187))
    text(d,(316,359),'AMMO',MUTED);text(d,(316,372),rounds,INK,22)
    text(d,(434,359),WEAPONS[weapon],AMBER)
    text(d,(434,377),f"{state.get('kills',0):02}/{state.get('total_kills',0):02} | CACHE {state.get('secrets',0):02}",MUTED)
    return image


SHOP_ROWS=tuple((46,121+i*61,593,176+i*61) for i in range(3))


def shop_overlay(image,state,error=None):
    d=ImageDraw.Draw(image);upkeep=state['vending']
    d.rectangle((28,48,611,337),fill=PANEL,outline=LINE)
    d.line((28,48,132,48),fill=AMBER,width=3)
    text(d,(46,61),'UPKEEP / NO REFUNDS',AMBER,22)
    text(d,(46,95),f"SCRAP {upkeep['credits']:03}  /  ONE PURCHASE PER FLOOR  /  RUN PAUSED",MUTED)
    for i,offer in enumerate(upkeep['vendor']['offers']):
        x,y,r,b=SHOP_ROWS[i];available=offer['cost']<=upkeep['credits']
        colour=INK if available else MUTED
        d.rectangle((x,y,r,b),outline=AMBER if available else LINE)
        text(d,(x+10,y+6),f"{i+1}  {offer['title']} / {offer['rank']+1}",colour)
        text(d,(r-94,y+6),f"{offer['cost']:02} SCRAP",AMBER if available else MUTED)
        text(d,(x+10,y+29),offer['description'],colour)
    text(d,(46,312),error or '1-3 or CLICK choose  /  ESC leave without buying',DANGER if error else MUTED)
    return image

CREDIT_LINES=[
    ('A GAME BY','JOSIAH ALAN-LEE + COLLABORATORS'),
    ('DIRECTION / BESTIARY','JOSIAH ALAN-LEE'),
    ('NATIVE ENGINE','id SOFTWARE / DOOMGENERIC / CHOCOLATE DOOM'),
    ('BASE ART / WEAPONS','THE FREEDOOM PROJECT'),
    ('STRANGE CREATURES','ARGON / ORIGINAL CONCEPTS + PROCEDURAL SKETCHES'),
    ('CONTENT ASSISTANCE','DEEPSEEK / FLOOR, SCORE + PROCEDURAL ART KIT'),
    ('INTEGRATION','CODEX + CLAUDE / ENGINE, HYDRAPY + GORGON WORK'),
    ('TYPEFACE','DEPARTURE MONO / HELENA ZHANG / SIL OFL 1.1'),
]

def overlay(image,state,credits=False,error=None,loading=False,mouse_sensitivity=3.):
    d=ImageDraw.Draw(image)
    d.rectangle((28,48,611,337),fill=PANEL,outline=LINE,width=1)
    d.line((28,48,132,48),fill=AMBER,width=3)
    if credits:
        text(d,(46,61),'PEOPLE / SOURCES',AMBER,22)
        for i,(label,value) in enumerate(CREDIT_LINES):
            y=99+i*25;text(d,(46,y),label,MUTED);text(d,(190,y),value,INK)
        text(d,(46,312),'C back   /   ENTER resume',MUTED)
        return image
    title='NULL RUN'
    subtitle='YOUR POSITION IS WAITING.'
    if state.get('dead'):title='RUN ENDED';subtitle='R retries this seed. N opens another arrangement.'
    elif state.get('won'):title='EXIT FOUND';subtitle='You made it through. R repeats; N starts again.'
    if loading:subtitle='ARRANGING THE NEXT RUN...'
    if error:subtitle='RUN PAUSED / '+str(error)[:56]
    text(d,(46,67),title,INK,22);text(d,(46,105),subtitle,AMBER)
    if state.get('bosses'):text(d,(46,126),' + '.join(b['name'] for b in state['bosses'])+' / BOTH MUST FALL',MUTED)
    for i,line in enumerate(['WASD move / MOUSE or arrows turn','CLICK or SPACE fire / RIGHT CLICK or F use','SHIFT run / TAB map / 1-7 weapons',
                             'ENTER or CLICK resume / ESC releases + pauses','R retry / N new seed / C credits',f'[ / ] mouse sensitivity {mouse_sensitivity:g}']):
        text(d,(46,149+i*28),line,INK if i<3 else MUTED)
    return image
