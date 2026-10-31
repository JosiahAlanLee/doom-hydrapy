// SPDX-License-Identifier: GPL-2.0-or-later
#include <stdio.h>
#include <stdlib.h>
#include "p_local.h"
#include "doomstat.h"
#include "z_zone.h"
#include "tables.h"
#include "rogue_ai.h"
#include "rogue_boss.h"
#include "rogue_creature.h"
#include "rogue_argon.h"

int Rogue_Class(mobj_t *actor) {
 if(!actor || !getenv("DOOM_ROGUE_FLOORS"))return 0;
 int flag=(actor->spawnpoint.options>>8)&7;
 mobjtype_t types[7]={MT_PLAYER,MT_POSSESSED,MT_SERGEANT,MT_TROOP,MT_HEAD,MT_BRUISER,MT_KNIGHT};
 if(flag>0 && flag<7)return actor->type==types[flag]?flag:0;
 if(flag!=7)return 0;
 switch(actor->type) {
  case MT_UNDEAD:return 7;
  case MT_CHAINGUY:return 8;
  case MT_FATSO:return 9;
  case MT_BABY:return 10;
  case MT_SHOTGUY:return 11;
  case MT_WOLFSS:return 12;
  case MT_VILE:return 13;
  case MT_SKULL:return 14;
  default:return 0;
 }
}
#define variant Rogue_Class
static int roll(mobj_t *actor) {return (actor->spawnpoint.options >> 11) & 15;}

void Rogue_Apply(mobj_t *actor, mapthing_t *thing) {
 int v=variant(actor), r=(thing->options>>11)&15;
 if(v>=11 && v<=14) {
  mobjinfo_t *info=Z_Malloc(sizeof(*info),PU_LEVEL,0);
  *info=*actor->info;actor->info=info;
  actor->flags|=MF_COUNTKILL;
  actor->flags&=~(MF_SHADOW|MF_SKULLFLY|MF_FLOAT|MF_NOGRAVITY);
  if(v==14)actor->flags|=MF_FLOAT|MF_NOGRAVITY;
  info->spawnhealth=(v==11?85:v==12?110:v==13?90:65)+r;
  info->speed=v==11?3:v==12?6:v==13?0:3;
  info->height=(v==13?96:80)*FRACUNIT;
  info->radius=(v==13?28:20)*FRACUNIT;
  info->missilestate=info->meleestate=S_NULL;
  info->deathstate=S_POSS_DIE1;info->xdeathstate=S_POSS_DIE1;info->painstate=S_POSS_PAIN;
  actor->radius=info->radius;actor->height=info->height;actor->health=info->spawnhealth;
  Rogue_Visual(actor);return;
 }
 // An ordinary WAD, pickup or unsupported actor never receives modifiers.
 if(v<1 || v>10 || !(actor->flags&MF_COUNTKILL))return;
 mobjinfo_t *info=Z_Malloc(sizeof(*info),PU_LEVEL,0);
 *info=*actor->info;actor->info=info;
 int hp[11]={100,65+r*2,140+r*3,90+r*2,45+r*2,50+r,100+r*2,45+r*2,200+r*2,95+r,180+r*2};
 int speed[11]={100,140+r*3,55+r*2,90+r,115+r*2,75+r,65+r,125+r,60,55+r,45+r};
 info->spawnhealth=info->spawnhealth*hp[v]/100;
 info->speed=info->speed*speed[v]/100;
 if(info->speed<1)info->speed=1;
 info->height=(v==7?104:v==2 || v>=5?96:88)*FRACUNIT;
 if(v>=7) {info->radius=(v==8?20:24)*FRACUNIT;actor->radius=info->radius;}
 info->mass=info->mass*(v==2?3:1);
 info->painchance=v==2?40:info->painchance;
 actor->health=info->spawnhealth;actor->height=info->height;
 actor->reactiontime=v==1?0:actor->reactiontime;
 if(v==7 || v==8) {
  info->missilestate=S_NULL;
  if(v==8)info->meleestate=S_NULL;
  actor->rogue_pose=v==7?24:0;
 }
 // Preserve a readable silhouette; native spectre fuzz hid too much detail.
 Rogue_Visual(actor);
 if(v==5 || v==6 || v>=9)Rogue_BossRegister(actor);
}

void Rogue_Visual(mobj_t *actor) {
 if(variant(actor)==4 && actor->health>0) {
  actor->frame=actor->state->frame|FF_FULLBRIGHT;
  if((actor->state->frame&FF_FRAMEMASK)==0)
   actor->frame=((leveltime/4+roll(actor))&1)|FF_FULLBRIGHT;
 }
 Rogue_CreatureVisual(actor);
 Rogue_ArgonVisual(actor);
}

int Rogue_Damage(mobj_t *actor,int damage) {
 int v=variant(actor),r=actor?roll(actor):0;
 if(v<1 || v>10)return damage;
 int percent[11]={100,75+r,115+r*2,80+r,85+r,50+r,45+r,25,100,40+r,35+r};
 return (damage*percent[v]+99)/100;
}

void Rogue_Projectile(mobj_t *source,mobj_t *missile) {
 int v=variant(source),r=source?roll(source):0;
 if(v==14) {
  static mobjinfo_t spore;static int ready;
  if(!ready) {spore=mobjinfo[MT_TROOPSHOT];spore.damage=3;spore.speed=10*FRACUNIT;ready=1;}
  missile->info=&spore;missile->rogue_until=leveltime+5*TICRATE;return;
 }
 if(v<1 || v>10)return;
 // Fixed-size per-type/variant caches avoid allocating on every projectile.
 static mobjinfo_t cache[NUMMOBJTYPES][10][16];
 static unsigned char ready[NUMMOBJTYPES][10][16];
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
  fprintf(out,"{\"class\":%d,\"roll\":%d,\"type\":%d,\"health\":%d,\"spawnhealth\":%d,\"speed\":%d,\"base_speed\":%d,\"height\":%d,\"shadow\":%s,\"luminous\":%s,\"x\":%d,\"y\":%d,\"missile\":%s,\"source_class\":%d,\"angle\":%.3f",
   variant(m),roll(m),m->info->doomednum,m->health,m->info->spawnhealth,m->info->speed,mobjinfo[m->type].speed,m->height/FRACUNIT,m->flags&MF_SHADOW?"true":"false",m->frame&FF_FULLBRIGHT?"true":"false",m->x/FRACUNIT,m->y/FRACUNIT,m->flags&MF_MISSILE?"true":"false",m->flags&MF_MISSILE?variant(m->target):0,m->angle*(360.0/4294967296.0));
  Rogue_CreatureJSON(out,m);Rogue_ArgonJSON(out,m);fprintf(out,"}");
 }
 fprintf(out,"]\n");fflush(out);
}
