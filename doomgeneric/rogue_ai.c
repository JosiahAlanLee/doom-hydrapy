// SPDX-License-Identifier: GPL-2.0-or-later
#include <stdio.h>
#include <stdlib.h>
#include "p_local.h"
#include "doomstat.h"
#include "z_zone.h"
#include "tables.h"
#include "rogue_ai.h"
#include "rogue_boss.h"

static int variant(mobj_t *actor) {
 return actor ? ((actor->spawnpoint.options >> 8) & 7) : 0;
}
static int roll(mobj_t *actor) {return (actor->spawnpoint.options >> 11) & 15;}

void Rogue_Apply(mobj_t *actor, mapthing_t *thing) {
 int v=(thing->options>>8)&7, r=(thing->options>>11)&15;
 // An ordinary WAD, pickup or unsupported actor never receives modifiers.
 if(!getenv("DOOM_ROGUE_FLOORS") || v<1 || v>6 || !(actor->flags&MF_COUNTKILL))return;
 if((v==1 && actor->type!=MT_POSSESSED) || (v==2 && actor->type!=MT_SERGEANT)
    || (v==3 && actor->type!=MT_TROOP) || (v==4 && actor->type!=MT_HEAD)
    || (v==5 && actor->type!=MT_BRUISER) || (v==6 && actor->type!=MT_KNIGHT))return;
 mobjinfo_t *info=Z_Malloc(sizeof(*info),PU_LEVEL,0);
 *info=*actor->info;actor->info=info;
 int hp[7]={100,65+r*2,140+r*3,90+r*2,45+r*2,50+r,100+r*2};
 int speed[7]={100,140+r*3,55+r*2,90+r,115+r*2,75+r,65+r};
 info->spawnhealth=info->spawnhealth*hp[v]/100;
 info->speed=info->speed*speed[v]/100;
 if(info->speed<1)info->speed=1;
 info->height=(v==2 || v>=5?96:88)*FRACUNIT;
 info->mass=info->mass*(v==2?3:1);
 info->painchance=v==2?40:info->painchance;
 actor->health=info->spawnhealth;actor->height=info->height;
 actor->reactiontime=v==1?0:actor->reactiontime;
 // Preserve a readable silhouette; native spectre fuzz hid too much detail.
 Rogue_Visual(actor);
 if(v>=5)Rogue_BossRegister(actor);
}

void Rogue_Visual(mobj_t *actor) {
 if(!getenv("DOOM_ROGUE_FLOORS") || variant(actor)!=4 || actor->health<=0)return;
 actor->frame=actor->state->frame|FF_FULLBRIGHT;
 if((actor->state->frame&FF_FRAMEMASK)==0)
  actor->frame=((leveltime/4+roll(actor))&1)|FF_FULLBRIGHT;
}

int Rogue_Damage(mobj_t *actor,int damage) {
 int v=variant(actor),r=actor?roll(actor):0;
 if(v<1 || v>6 || !getenv("DOOM_ROGUE_FLOORS"))return damage;
 int percent[7]={100,75+r,115+r*2,80+r,85+r,50+r,45+r};
 return (damage*percent[v]+99)/100;
}

void Rogue_Projectile(mobj_t *source,mobj_t *missile) {
 int v=variant(source),r=source?roll(source):0;
 if(!getenv("DOOM_ROGUE_FLOORS") || v<1 || v>6)return;
 // Fixed-size per-type/variant caches avoid allocating on every projectile.
 static mobjinfo_t cache[NUMMOBJTYPES][6][16];
 static unsigned char ready[NUMMOBJTYPES][6][16];
 mobjinfo_t *info=&cache[missile->type][v-1][r];
 if(!ready[missile->type][v-1][r]) {
  *info=mobjinfo[missile->type];
  info->damage=Rogue_Damage(source,info->damage);
  info->speed=info->speed*(v==3?85+r:v==4?110+r:100)/100;
  ready[missile->type][v-1][r]=1;
 }
 missile->info=info;
}

int Rogue_Fan(mobj_t *actor) {
 if(!getenv("DOOM_ROGUE_FLOORS") || variant(actor)!=3 || !actor->target)return 0;
 for(int side=-1;side<=1;side+=2) {
  mobj_t *shot=P_SpawnMissile(actor,actor->target,MT_TROOPSHOT);
  shot->angle+=(side<0 ? -(ANG45/6) : ANG45/6);
  unsigned fine=shot->angle>>ANGLETOFINESHIFT;
  shot->momx=FixedMul(shot->info->speed,finecosine[fine]);
  shot->momy=FixedMul(shot->info->speed,finesine[fine]);
 }
 return 1;
}

void Rogue_Report(FILE *out) {
 int count=0;fprintf(out,"MOBS [");
 for(thinker_t *t=thinkercap.next;t!=&thinkercap;t=t->next) {
  if(t->function.acp1!=(actionf_p1)P_MobjThinker)continue;
  mobj_t *m=(mobj_t*)t;
  if(!(m->flags&(MF_COUNTKILL|MF_MISSILE)))continue;
  if(count++)fprintf(out,",");
  fprintf(out,"{\"class\":%d,\"roll\":%d,\"type\":%d,\"health\":%d,\"spawnhealth\":%d,\"speed\":%d,\"base_speed\":%d,\"height\":%d,\"shadow\":%s,\"luminous\":%s,\"x\":%d,\"y\":%d,\"missile\":%s,\"source_class\":%d,\"angle\":%.3f}",
   variant(m),roll(m),m->info->doomednum,m->health,m->info->spawnhealth,m->info->speed,mobjinfo[m->type].speed,m->height/FRACUNIT,m->flags&MF_SHADOW?"true":"false",m->frame&FF_FULLBRIGHT?"true":"false",m->x/FRACUNIT,m->y/FRACUNIT,m->flags&MF_MISSILE?"true":"false",m->flags&MF_MISSILE?variant(m->target):0,m->angle*(360.0/4294967296.0));
 }
 fprintf(out,"]\n");fflush(out);
}
