// SPDX-License-Identifier: GPL-2.0-or-later
// New native interpretations of the user's Gloamwood encounter descriptions.
#include <stdlib.h>
#include "p_local.h"
#include "doomstat.h"
#include "r_main.h"
#include "r_state.h"
#include "d_event.h"
#include "rogue_ai.h"
#include "rogue_creature.h"
#include "rogue_strobe.h"
#include "rogue_argon.h"

enum { SHAMBLE, WARNING, LUNGE, GRIP, STAGGER };
static mobj_t *holder;
static int grip_started,escape_ticks,damage_due,immunity_until,shriek_until;

void Rogue_CreatureReset(void) {
 holder=NULL;grip_started=escape_ticks=damage_due=immunity_until=shriek_until=0;
}

static fixed_t distance(mobj_t *a,mobj_t *b) {
 return P_AproxDistance(a->x-b->x,a->y-b->y);
}

static int watched(mobj_t *actor,mobj_t *p) {
 if(distance(actor,p)>1536*FRACUNIT)return 0;
 angle_t d=R_PointToAngle2(p->x,p->y,actor->x,actor->y)-p->angle;
 if(d>ANG180)d=0-d;
 return d<=ANG45 && P_CheckSight(p,actor);
}

static void stop(mobj_t *actor) {actor->momx=actor->momy=0;}

static void release_grip(void) {
 if(holder && holder->health>0) {
  holder->rogue_phase=STAGGER;holder->rogue_until=leveltime+TICRATE;
  holder->info->speed=4;stop(holder);
 }
 holder=NULL;escape_ticks=0;immunity_until=leveltime+3*TICRATE;
}

static int valid_grip(player_t *p) {
 return holder && holder->health>0 && p->mo && p->health>0 &&
        distance(holder,p->mo)<=96*FRACUNIT && P_CheckSight(holder,p->mo);
}

void Rogue_PlayerFilter(player_t *p) {
 if(!getenv("DOOM_ROGUE_FLOORS"))return;
 if(holder && (!valid_grip(p) || leveltime-grip_started>=4*TICRATE))release_grip();
 // Turning, firing, use, pause and the automap always remain available.
 if(holder) {
  escape_ticks=(p->cmd.buttons&BT_USE)?escape_ticks+1:0;
  if(escape_ticks>=25)release_grip();
  else {
   p->cmd.forwardmove/=4;p->cmd.sidemove/=4;
   p->mo->momx/=2;p->mo->momy/=2;
  }
 }
 if(p->health>0 && p->mo && leveltime<shriek_until) {
  p->cmd.forwardmove=p->cmd.sidemove=0;
  p->mo->momx/=2;p->mo->momy/=2;
 }
}

int Rogue_CreatureThink(mobj_t *actor) {
 int kind=Rogue_Class(actor);
 if((kind!=7 && kind!=8) || actor->health<=0)return 0;
 player_t *player=&players[consoleplayer];mobj_t *p=player->mo;
 if(!p || player->health<=0) {
  if(holder==actor)release_grip();
  stop(actor);return 1;
 }
 if(kind==7) {
  int seen=watched(actor,p) && Rogue_StrobeIlluminated(actor);
  if(seen)actor->rogue_awake=1;
  int was_frozen=actor->rogue_frozen;
  actor->rogue_frozen=seen || !actor->rogue_awake;
  if(actor->rogue_frozen) {stop(actor);return 1;}
  actor->target=p;
  // The native chaser avoids reversing its previous direction. Start a resumed
  // hunt with DI_NODIR (the private p_enemy.c enum's value 8), not a stale east.
  if(was_frozen) {actor->movedir=8;actor->movecount=0;}
  if(actor->state==&states[actor->info->spawnstate] || actor->state==&states[S_SKEL_STND2])
   P_SetMobjState(actor,actor->info->seestate);
  return 0;
 }
 int visible=distance(actor,p)<=448*FRACUNIT && P_CheckSight(actor,p);
 if(actor->rogue_phase==GRIP) {
  if(holder!=actor)return 0;
  if(!valid_grip(player) || leveltime-grip_started>=4*TICRATE)release_grip();
  else if(leveltime>=damage_due) {
   damage_due=leveltime+TICRATE;
   P_DamageMobj(p,actor,actor,4);
  }
  stop(actor);return 1;
 }
 if(actor->rogue_phase==STAGGER) {
  if(leveltime<actor->rogue_until) {stop(actor);return 1;}
  actor->rogue_phase=SHAMBLE;
 }
 if(actor->rogue_phase==WARNING) {
  if(leveltime<actor->rogue_until) {stop(actor);return 1;}
  // The warning can be dodged by breaking line of sight or leaving its range.
  if(visible)shriek_until=leveltime+12;
  actor->rogue_phase=LUNGE;actor->rogue_until=leveltime+TICRATE;
  actor->target=p;actor->movedir=8;actor->movecount=0;actor->info->speed=12;
  P_SetMobjState(actor,actor->info->seestate);
 }
 if(actor->rogue_phase==LUNGE) {
  if(!holder && leveltime>=immunity_until && visible && distance(actor,p)<72*FRACUNIT) {
   holder=actor;grip_started=leveltime;escape_ticks=0;damage_due=leveltime+TICRATE;
   actor->rogue_phase=GRIP;stop(actor);return 1;
  }
  if(leveltime>=actor->rogue_until)actor->rogue_phase=SHAMBLE;
 }
 if(actor->rogue_phase==SHAMBLE && visible && leveltime>=actor->rogue_cooldown) {
  actor->rogue_phase=WARNING;actor->rogue_until=leveltime+28;
  actor->rogue_cooldown=leveltime+6*TICRATE;stop(actor);return 1;
 }
 actor->info->speed=actor->rogue_phase==LUNGE?12:4;
 if(visible) {
  actor->target=p;
  if(actor->state==&states[actor->info->spawnstate] || actor->state==&states[S_CPOS_STND2]) {
   actor->movedir=8;actor->movecount=0;
   P_SetMobjState(actor,actor->info->seestate);
  }
 }
 return 0;
}

void Rogue_CreatureVisual(mobj_t *actor) {
 int kind=Rogue_Class(actor);
 if(actor->health<=0)return;
 if(kind==7) {
  if(!actor->rogue_awake)actor->rogue_pose=24;
  else if(!actor->rogue_frozen) {
   int frame=actor->state->frame&FF_FRAMEMASK;
   actor->rogue_pose=(frame>=6 && frame<=8)?25:20+((leveltime/4)&3);
  }
  actor->frame=actor->rogue_pose;
 } else if(kind==8 && actor->rogue_phase!=SHAMBLE) {
  actor->frame=19+actor->rogue_phase;
 }
 // A map-only PWAD may intentionally omit our extra pose patches. Its native
 // state frame remains valid; encounter behavior must not crash the renderer.
 if((kind==7 || kind==8) && (actor->frame&FF_FRAMEMASK)>=sprites[actor->sprite].numframes)
  actor->frame=actor->state->frame;
}

void Rogue_CreatureHurt(mobj_t *actor) {
 Rogue_ArgonHurt(actor);
 int kind=Rogue_Class(actor);
 if(kind==7)actor->rogue_awake=1;
 if(kind==8) {
  if(holder==actor)release_grip();
  actor->rogue_phase=STAGGER;actor->rogue_until=leveltime+TICRATE;
 }
}

void Rogue_CreatureRemove(mobj_t *actor) {
 if(holder==actor) {holder=NULL;escape_ticks=0;immunity_until=leveltime+3*TICRATE;}
}

void Rogue_CreatureJSON(FILE *out,mobj_t *actor) {
 int kind=Rogue_Class(actor);
 if(kind==7 || kind==8)
  fprintf(out,",\"awake\":%s,\"frozen\":%s,\"pose\":%d,\"creature_phase\":%d",
   actor->rogue_awake?"true":"false",actor->rogue_frozen?"true":"false",actor->frame&FF_FRAMEMASK,actor->rogue_phase);
}

void Rogue_CreatureStatus(FILE *out) {
 int observed=0,hunting=0,warnings=0;
 if(getenv("DOOM_ROGUE_FLOORS"))for(thinker_t *t=thinkercap.next;t!=&thinkercap;t=t->next) {
  if(t->function.acp1!=(actionf_p1)P_MobjThinker)continue;
  mobj_t *actor=(mobj_t*)t;if(actor->health<=0)continue;
  int kind=Rogue_Class(actor);
  if(kind==7 && actor->rogue_awake) {if(actor->rogue_frozen)observed++;else hunting++;}
  if(kind==8 && actor->rogue_phase==WARNING)warnings++;
 }
 fprintf(out,"{\"watched\":%d,\"hunting\":%d,\"shriek_warning\":%d,\"effect\":%s,\"escape_ticks\":%d,\"remaining_ticks\":%d}",
 observed,hunting,warnings,holder?"\"grip\"":leveltime<shriek_until?"\"shriek\"":"null",escape_ticks,
 holder?4*TICRATE-(leveltime-grip_started):leveltime<shriek_until?shriek_until-leveltime:0);
}
