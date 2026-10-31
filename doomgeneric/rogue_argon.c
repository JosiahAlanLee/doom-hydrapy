// SPDX-License-Identifier: GPL-2.0-or-later
// Argon's four creatures use native sight, collision, damage and projectiles.
#include <stdlib.h>
#include "p_local.h"
#include "doomstat.h"
#include "r_main.h"
#include "r_state.h"
#include "tables.h"
#include "rogue_ai.h"
#include "rogue_argon.h"

enum { IDLE, HUNT, WARNING, ATTACK, HURT };
static const char *names[4]={"surveyor","wire_shambler","threshold_mimic","vore_spindle"};
void A_Chase(mobj_t *actor);
void P_ExplodeMissile(mobj_t *actor);

static int kind(mobj_t *a) {int k=Rogue_Class(a);return k>=11 && k<=14?k:0;}
static fixed_t distance(mobj_t *a,mobj_t *b) {return P_AproxDistance(a->x-b->x,a->y-b->y);}
static void stop(mobj_t *a) {a->momx=a->momy=a->momz=0;}

int Rogue_ArgonThink(mobj_t *a) {
 if((a->flags&MF_MISSILE) && a->target && kind(a->target)==14 && a->rogue_until>0) {
  if(leveltime>=a->rogue_until) {P_ExplodeMissile(a);return 1;}
  if(a->tracer && a->tracer->health>0 && !(leveltime&3)) {
   angle_t exact=R_PointToAngle2(a->x,a->y,a->tracer->x,a->tracer->y);
   angle_t turn=ANG45/8;
   if(exact-a->angle>ANG180) {
    a->angle-=turn;if(exact-a->angle<ANG180)a->angle=exact;
   } else {
    a->angle+=turn;if(exact-a->angle>ANG180)a->angle=exact;
   }
   unsigned fine=a->angle>>ANGLETOFINESHIFT;
   a->momx=FixedMul(a->info->speed,finecosine[fine]);
   a->momy=FixedMul(a->info->speed,finesine[fine]);
   int steps=distance(a,a->tracer)/a->info->speed;if(steps<1)steps=1;
   fixed_t slope=(a->tracer->z+40*FRACUNIT-a->z)/steps;
   if(slope<a->momz)a->momz-=FRACUNIT/8;else a->momz+=FRACUNIT/8;
  }
  return 0;
 }
 int k=kind(a);if(!k || a->health<=0)return 0;
 player_t *player=&players[consoleplayer];mobj_t *p=player->mo;
 stop(a);
 if(!p || player->health<=0)return 1;
 fixed_t range=distance(a,p);
 int visible=range<=1536*FRACUNIT && P_CheckSight(a,p);
 if(!a->rogue_awake) {
  if(!visible || (k==13 && range>192*FRACUNIT))return 1;
  a->rogue_awake=1;a->rogue_phase=HUNT;a->target=p;a->movedir=8;a->movecount=0;
 }
 a->target=p;
 if(k==14) {
  // Hang low enough to remain visible with classic Doom's fixed camera.
  fixed_t z=a->floorz+24*FRACUNIT;
  if(z+a->height>a->ceilingz)z=a->ceilingz-a->height;
  a->z=z<a->floorz?a->floorz:z;
 }
 if(a->rogue_phase==HURT || a->rogue_phase==ATTACK) {
  if(leveltime<a->rogue_until)return 1;
  a->rogue_phase=HUNT;
 }
 if(a->rogue_phase==WARNING) {
  if(leveltime<a->rogue_until)return 1;
  a->rogue_attack_count++;
  if(k==11) {
   // Aim is fixed at the beginning of the warning: sidesteps really work.
   P_LineAttack(a,a->rogue_aim,1536*FRACUNIT,a->rogue_slope,9);
  } else if(k==12) {
   if(visible && range<=320*FRACUNIT)P_DamageMobj(p,a,a,8);
  } else if(k==13) {
   if(visible && range<=128*FRACUNIT)P_DamageMobj(p,a,a,12);
  } else {
   mobj_t *shot=P_SpawnMissile(a,p,MT_TROOPSHOT);
   if(shot)shot->tracer=p;
  }
  a->rogue_phase=ATTACK;a->rogue_until=leveltime+10;
  a->rogue_cooldown=leveltime+(k==13?105:140);
  return 1;
 }
 fixed_t reach=(k==11?1400:k==12?256:k==13?192:1200)*FRACUNIT;
 if(visible && range<=reach && leveltime>=a->rogue_cooldown) {
  a->rogue_phase=WARNING;a->rogue_until=leveltime+(k==11?35:k==12?30:k==13?21:35);
  a->rogue_aim=R_PointToAngle2(a->x,a->y,p->x,p->y);
  a->rogue_slope=P_AimLineAttack(a,a->rogue_aim,1536*FRACUNIT);
  a->angle=a->rogue_aim;return 1;
 }
 // The false door remains anchored. The others use Doom's wall-aware chaser;
 // their native melee/missile states are disabled in their private info record.
 if(k!=13 && leveltime%3==0)A_Chase(a);
 return 1;
}

void Rogue_ArgonHurt(mobj_t *a) {
 if(!kind(a))return;
 a->rogue_awake=1;a->rogue_phase=HURT;a->rogue_until=leveltime+10;
 a->rogue_cooldown=leveltime+45;stop(a);
}

void Rogue_ArgonVisual(mobj_t *a) {
 if(!kind(a))return;
 int frame;
 if(a->health<=0) {
  a->flags&=~(MF_NOGRAVITY|MF_FLOAT);
  if(!a->rogue_dead_started)a->rogue_dead_started=leveltime;
  int age=(leveltime-a->rogue_dead_started)/6;if(age>3)age=3;
  frame=20+age;
 } else {
  int row=!a->rogue_awake?0:a->rogue_phase==WARNING?2:a->rogue_phase==ATTACK?3:a->rogue_phase==HURT?4:1;
  if(Rogue_Class(a)==13 && row==1)row=0;
  frame=row*4+((leveltime/6)&3);
 }
 int sprite=states[mobjinfo[a->type].spawnstate].sprite;
 if(frame<sprites[sprite].numframes) {a->sprite=sprite;a->frame=frame;}
 // Map-only fixtures may deliberately retain the original small sprite set.
 else {a->sprite=a->state->sprite;a->frame=a->state->frame;}
}

void Rogue_ArgonJSON(FILE *out,mobj_t *a) {
 int k=kind(a);if(!k)return;
 int left=a->rogue_phase==WARNING?a->rogue_until-leveltime:0;
 fprintf(out,",\"argon_kind\":\"%s\",\"awake\":%s,\"argon_phase\":%d,\"warning_ticks\":%d,\"attack_count\":%d",
  names[k-11],a->rogue_awake?"true":"false",a->rogue_phase,left>0?left:0,a->rogue_attack_count);
}

void Rogue_ArgonStatus(FILE *out) {
 int counts[4]={0},warning=0,cue=0;
 if(getenv("DOOM_ROGUE_FLOORS"))for(thinker_t *t=thinkercap.next;t!=&thinkercap;t=t->next) {
  if(t->function.acp1!=(actionf_p1)P_MobjThinker)continue;
  mobj_t *a=(mobj_t*)t;int k=kind(a);if(!k || a->health<=0)continue;
  counts[k-11]++;if(a->rogue_phase==WARNING) {warning++;if(!cue)cue=k;}
 }
 const char *text=cue==11?"SURVEYOR / STEP SIDEWAYS":cue==12?"BALLAST HUSK / FIND COVER":cue==13?"FALSE DOOR / STAND BACK":cue==14?"SPINDLE / SPORE CHARGING":NULL;
 fprintf(out,"{\"surveyor\":%d,\"wire_shambler\":%d,\"threshold_mimic\":%d,\"vore_spindle\":%d,\"warnings\":%d,\"cue\":",counts[0],counts[1],counts[2],counts[3],warning);
 if(text)fprintf(out,"\"%s\"",text);else fprintf(out,"null");fprintf(out,"}");
}
