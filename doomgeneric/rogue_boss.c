// SPDX-License-Identifier: GPL-2.0-or-later
// Book forms/bindings by Josiah Alan-Lee; combat interpretation by Codex.
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include "p_local.h"
#include "doomstat.h"
#include "d_event.h"
#include "tables.h"
#include "rogue_boss.h"

static struct {
 mobj_t *actor;
 int kind,maxhealth,open_until,stamps,still,last_use,last_stamp,echo_due,echoes,blocked,attacks,last_burst;
 angle_t echo_angle;
 fixed_t echo_z,last_x,last_y,seal_x,seal_y;
 int has_seal;
} boss;
static int active(void) {return getenv("DOOM_ROGUE_FLOORS") && boss.actor;}
static int alive(void) {return active() && boss.actor->health>0;}
static int exposed(void) {return alive() && leveltime<boss.open_until;}

void Rogue_BossReset(void) {memset(&boss,0,sizeof(boss));}

void Rogue_BossRegister(mobj_t *actor) {
 int kind=(actor->spawnpoint.options>>8)&7;
 if(!getenv("DOOM_ROGUE_FLOORS") || boss.actor || (kind!=5 && kind!=6))return;
 boss.actor=actor;boss.kind=kind;boss.maxhealth=actor->health;boss.last_stamp=-100;
 for(int i=0;i<numsectors;i++) {
  sector_t *sector=&sectors[i];
  if(sector->tag!=777)continue;
  fixed_t minx=INT_MAX,miny=INT_MAX,maxx=INT_MIN,maxy=INT_MIN;
  for(int j=0;j<sector->linecount;j++) {
   line_t *line=sector->lines[j];
   for(int k=0;k<2;k++) {
    vertex_t *v=k?line->v2:line->v1;
    if(v->x<minx)minx=v->x;
    if(v->x>maxx)maxx=v->x;
    if(v->y<miny)miny=v->y;
    if(v->y>maxy)maxy=v->y;
   }
  }
  boss.seal_x=minx+(maxx-minx)/2;boss.seal_y=miny+(maxy-miny)/2;boss.has_seal=1;break;
 }
 // Malformed external PWADs must not create an unwinnable invulnerable boss.
 if(!boss.has_seal)boss.open_until=INT_MAX;
}

static void spread(mobj_t *shot,angle_t angle,fixed_t momz) {
 shot->angle=angle;unsigned fine=angle>>ANGLETOFINESHIFT;
 shot->momx=FixedMul(shot->info->speed,finecosine[fine]);
 shot->momy=FixedMul(shot->info->speed,finesine[fine]);shot->momz=momz;
}

int Rogue_BossAttack(mobj_t *actor) {
 if(!active() || actor!=boss.actor || !actor->target)return 0;
 boss.attacks++;boss.last_burst=1;
 mobj_t *shot=P_SpawnMissile(actor,actor->target,MT_BRUISERSHOT);
 if(boss.kind==5) {
  boss.echo_angle=shot->angle;boss.echo_z=shot->momz;boss.echo_due=leveltime+18;
 } else if(players[consoleplayer].cmd.buttons&BT_ATTACK) {
  boss.last_burst=3;
  angle_t angle=shot->angle;fixed_t z=shot->momz;
  for(int side=-1;side<=1;side+=2) {
   mobj_t *other=P_SpawnMissile(actor,actor->target,MT_BRUISERSHOT);
   spread(other,angle+(side<0?-(ANG45/3):ANG45/3),z);
  }
 }
 return 1;
}

void Rogue_BossTick(void) {
 if(!active() || gamestate!=GS_LEVEL)return;
 player_t *player=&players[consoleplayer];mobj_t *p=player->mo;
 if(!p || player->health<=0 || !alive())return;
 if(boss.echo_due && leveltime>=boss.echo_due) {
  if(boss.actor->target) {
   mobj_t *shot=P_SpawnMissile(boss.actor,boss.actor->target,MT_BRUISERSHOT);
   spread(shot,boss.echo_angle,boss.echo_z);boss.echoes++;
  }
  boss.echo_due=0;
 }
 int on_seal=p->subsector->sector->tag==777;
 int use=!!(player->cmd.buttons&BT_USE);
 if(!exposed() && boss.has_seal) {
  if(boss.kind==5) {
   if(on_seal && use && !boss.last_use && leveltime-boss.last_stamp>=4) {
    boss.last_stamp=leveltime;
    if(++boss.stamps>=2) {boss.open_until=leveltime+8*TICRATE;boss.stamps=0;}
   }
  } else {
   int still=abs(p->x-boss.last_x)<FRACUNIT/4 && abs(p->y-boss.last_y)<FRACUNIT/4;
   if(on_seal && still && !(player->cmd.buttons&BT_ATTACK))boss.still++;
   else boss.still=0;
   if(boss.still>=2*TICRATE) {boss.open_until=leveltime+8*TICRATE;boss.still=0;}
  }
 } else boss.still=0;
 boss.last_use=use;boss.last_x=p->x;boss.last_y=p->y;
}

int Rogue_BossGuard(mobj_t *target) {
 if(!alive() || target!=boss.actor || exposed())return 0;
 boss.blocked++;return 1;
}

int Rogue_ExitAllowed(void) {return !alive();}

void Rogue_BossJSON(FILE *out) {
 if(!active()) {fprintf(out,"null");return;}
 player_t *p=&players[consoleplayer];
 int near=p->mo && p->mo->subsector->sector->tag==777;
 fprintf(out,"{\"name\":\"%s\",\"class\":%d,\"health\":%d,\"max_health\":%d,\"phase\":\"%s\",\"on_seal\":%s,\"has_seal\":%s,\"stamps\":%d,\"still_ticks\":%d,\"open_ticks\":%d,\"echoes\":%d,\"blocked_hits\":%d,\"seal_x\":%d,\"seal_y\":%d,\"attacks\":%d,\"last_burst\":%d}",
 boss.kind==5?"REPETIEL":"CALMOR",boss.kind,boss.actor->health>0?boss.actor->health:0,boss.maxhealth,
 !alive()?"bound":exposed()?"exposed":"sealed",near?"true":"false",boss.has_seal?"true":"false",boss.stamps,boss.still,
 exposed()?boss.open_until-leveltime:0,boss.echoes,boss.blocked,boss.seal_x/FRACUNIT,boss.seal_y/FRACUNIT,boss.attacks,boss.last_burst);
}
