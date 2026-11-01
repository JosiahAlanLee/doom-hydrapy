// SPDX-License-Identifier: GPL-2.0-or-later
// Book forms/bindings by Josiah Alan-Lee; combat interpretation by Codex.
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include "p_local.h"
#include "doomstat.h"
#include "d_event.h"
#include "tables.h"
#include "w_wad.h"
#include "z_zone.h"
#include "rogue_boss.h"
#include "rogue_ai.h"

#define MAX_BOSSES 2

typedef struct {
 mobj_t *actor;
 int kind,maxhealth,open_until,stamps,still,last_use,last_stamp,echo_due,echoes,blocked,attacks,last_burst;
 angle_t echo_angle;
 fixed_t echo_z,last_x,last_y,seal_x,seal_y;
 int has_seal,has_secondary,proof,gate_stage,last_sector,tag,tag_b;
 fixed_t seal_b_x,seal_b_y;
 char name[24];
} boss_t;
static boss_t bosses[MAX_BOSSES];
static int count;
typedef struct {int x,y,tag,tag_b,kind;char name[24];} identity_t;
static identity_t identities[MAX_BOSSES];
static int identity_count;
static int enabled(void) {return getenv("DOOM_ROGUE_FLOORS")!=NULL;}
static int alive(const boss_t *b) {return enabled() && b->actor && b->actor->health>0;}
static int exposed(const boss_t *b) {return alive(b) && leveltime<b->open_until;}
static boss_t *lookup(mobj_t *actor) {
 if(!enabled())return NULL;
 for(int i=0;i<count;i++)if(bosses[i].actor==actor)return &bosses[i];
 return NULL;
}

void Rogue_BossReset(void) {
 memset(bosses,0,sizeof(bosses));memset(identities,0,sizeof(identities));count=identity_count=0;
}

static int word(const unsigned char *p) {return (short)((unsigned)p[0]|(unsigned)p[1]<<8);}
void Rogue_BossLoad(void) {
 if(!enabled())return;
 int lump=W_CheckNumForName("RBOSSES");if(lump<0)return;
 int length=W_LumpLength(lump);if(length<6 || length>6+32*36)return;
 const unsigned char *data=W_CacheLumpNum(lump,PU_CACHE);
 int records=word(data+4);
 if(memcmp(data,"NRB1",4) || records<0 || records>32 || length!=6+records*36)return;
 for(int i=0;i<records;i++) {
  const unsigned char *p=data+6+i*36;
  if(word(p)!=gamemap)continue;
  // Reject malformed metadata as a whole; fallback encounter rules stay usable.
  if(identity_count>=MAX_BOSSES) {identity_count=0;return;}
  identity_t value={word(p+2),word(p+4),word(p+6),word(p+8),word(p+10),{0}};
  if(value.tag<1 || value.tag_b<0 || (value.kind!=5 && value.kind!=6 && value.kind!=9 && value.kind!=10) ||
     (value.kind==10 && (!value.tag_b || value.tag_b==value.tag))) {identity_count=0;return;}
  int n=0;
  for(;n<23 && p[12+n];n++) {
   if(p[12+n]<'A' || p[12+n]>'Z') {identity_count=0;return;}
   value.name[n]=p[12+n];
  }
  if(!n || p[12+n]) {identity_count=0;return;}
  for(int j=0;j<identity_count;j++) {
   identity_t *other=&identities[j];
   if((other->x==value.x && other->y==value.y) || other->tag==value.tag ||
      other->tag_b==value.tag || (value.tag_b && (other->tag==value.tag_b || other->tag_b==value.tag_b))) {
    identity_count=0;return;
   }
  }
  identities[identity_count++]=value;
 }
}

static int find_seal(int tag,fixed_t *x,fixed_t *y) {
 int found=0;
 for(int i=0;i<numsectors;i++) {
  sector_t *sector=&sectors[i];
  if(sector->tag!=tag || !sector->linecount)continue;
  if(found)return 0; // Duplicate tags cannot bind an unrelated room.
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
  *x=minx+(maxx-minx)/2;*y=miny+(maxy-miny)/2;found=1;
 }
 return found;
}

void Rogue_BossRegister(mobj_t *actor) {
 int kind=Rogue_Class(actor);
 if(!enabled() || count>=MAX_BOSSES || (kind!=5 && kind!=6 && kind!=9 && kind!=10))return;
 boss_t *b=&bosses[count];
 b->actor=actor;b->kind=kind;b->maxhealth=actor->health;b->last_stamp=-100;
 b->tag=777+count*2;b->tag_b=b->tag+1;
 const char *name=kind==5?"REPETIEL":kind==6?"CALMOR":kind==9?"PROBATOR":"JURISIEL";
 for(int i=0;i<identity_count;i++) {
  identity_t *id=&identities[i];
  if(id->kind==kind && id->x==actor->x/FRACUNIT && id->y==actor->y/FRACUNIT) {
   name=id->name;b->tag=id->tag;b->tag_b=id->tag_b;break;
  }
 }
 memcpy(b->name,name,strlen(name)+1);
 b->has_seal=find_seal(b->tag,&b->seal_x,&b->seal_y);
 b->has_secondary=b->tag_b && find_seal(b->tag_b,&b->seal_b_x,&b->seal_b_y);
 if(kind==10 && !b->has_secondary)b->has_seal=0;
 // Malformed external PWADs must not create an unwinnable invulnerable boss.
 if(!b->has_seal)b->open_until=INT_MAX;
 count++;
}

static void spread(mobj_t *shot,angle_t angle,fixed_t momz) {
 shot->angle=angle;unsigned fine=angle>>ANGLETOFINESHIFT;
 shot->momx=FixedMul(shot->info->speed,finecosine[fine]);
 shot->momy=FixedMul(shot->info->speed,finesine[fine]);shot->momz=momz;
}

int Rogue_BossAttack(mobj_t *actor) {
 boss_t *b=lookup(actor);if(!b || !actor->target)return 0;
 b->attacks++;b->last_burst=1;
 mobj_t *shot=P_SpawnMissile(actor,actor->target,MT_BRUISERSHOT);
 if(b->kind==5) {
  b->echo_angle=shot->angle;b->echo_z=shot->momz;b->echo_due=leveltime+18;
 } else if(b->kind==6 && (players[consoleplayer].cmd.buttons&BT_ATTACK)) {
  b->last_burst=3;
  angle_t angle=shot->angle;fixed_t z=shot->momz;
  for(int side=-1;side<=1;side+=2) {
   mobj_t *other=P_SpawnMissile(actor,actor->target,MT_BRUISERSHOT);
   spread(other,angle+(side<0?-(ANG45/3):ANG45/3),z);
  }
 } else if(b->kind==9 || b->kind==10) {
  b->last_burst=2;
  angle_t angle=shot->angle;fixed_t z=shot->momz;
  angle_t width=b->kind==9?ANG45/8:ANG45/2;
  spread(shot,angle-width,z);
  mobj_t *other=P_SpawnMissile(actor,actor->target,MT_BRUISERSHOT);
  spread(other,angle+width,z);
 }
 return 1;
}

void Rogue_BossTick(void) {
 if(!enabled() || gamestate!=GS_LEVEL)return;
 player_t *player=&players[consoleplayer];mobj_t *p=player->mo;
 if(!p || player->health<=0)return;
 int sector=p->subsector->sector->tag;
 int use=!!(player->cmd.buttons&BT_USE);
 for(int i=0;i<count;i++) {
  boss_t *b=&bosses[i];if(!alive(b))continue;
  if(b->echo_due && leveltime>=b->echo_due) {
   if(b->actor->target) {
    mobj_t *shot=P_SpawnMissile(b->actor,b->actor->target,MT_BRUISERSHOT);
    spread(shot,b->echo_angle,b->echo_z);b->echoes++;
   }
   b->echo_due=0;
  }
  int on_seal=sector==b->tag;
  if(!exposed(b) && b->has_seal) {
   if(b->kind==5) {
    if(on_seal && use && !b->last_use && leveltime-b->last_stamp>=4) {
     b->last_stamp=leveltime;
     if(++b->stamps>=2) {b->open_until=leveltime+8*TICRATE;b->stamps=0;}
    }
   } else if(b->kind==6) {
    int still=abs(p->x-b->last_x)<FRACUNIT/4 && abs(p->y-b->last_y)<FRACUNIT/4;
    if(on_seal && still && !(player->cmd.buttons&BT_ATTACK))b->still++;
    else b->still=0;
    if(b->still>=2*TICRATE) {b->open_until=leveltime+8*TICRATE;b->still=0;}
   } else if(b->kind==9) {
    if(b->proof && on_seal && use && !b->last_use) {
     b->open_until=leveltime+8*TICRATE;b->proof=0;
    }
   } else {
    if(sector==b->tag && b->last_sector!=b->tag)b->gate_stage=1;
    if(sector==b->tag_b && b->last_sector!=b->tag_b && b->gate_stage==1) {
     b->open_until=leveltime+8*TICRATE;b->gate_stage=0;
    }
   }
  } else b->still=0;
  b->last_use=use;b->last_x=p->x;b->last_y=p->y;b->last_sector=sector;
 }
}

int Rogue_BossGuard(mobj_t *target,mobj_t *source) {
 boss_t *b=lookup(target);
 if(!b || !alive(b) || exposed(b))return 0;
 if(b->kind==9 && source==players[consoleplayer].mo)b->proof=1;
 b->blocked++;return 1;
}

int Rogue_ExitAllowed(void) {
 for(int i=0;i<count;i++)if(alive(&bosses[i]))return 0;
 return 1;
}

static void status(FILE *out,const boss_t *b) {
 player_t *p=&players[consoleplayer];
 int near=p->mo && p->mo->subsector->sector->tag==b->tag;
 fprintf(out,"{\"name\":\"%s\",\"class\":%d,\"health\":%d,\"max_health\":%d,\"phase\":\"%s\",\"on_seal\":%s,\"has_seal\":%s,\"stamps\":%d,\"still_ticks\":%d,\"open_ticks\":%d,\"echoes\":%d,\"blocked_hits\":%d,\"seal_x\":%d,\"seal_y\":%d,\"attacks\":%d,\"last_burst\":%d,\"proof\":%s,\"gate_stage\":%d,\"seal_b_x\":%d,\"seal_b_y\":%d}",
 b->name,b->kind,b->actor->health>0?b->actor->health:0,b->maxhealth,
 !alive(b)?"bound":exposed(b)?"exposed":"sealed",near?"true":"false",b->has_seal?"true":"false",b->stamps,b->still,
 exposed(b)?b->open_until-leveltime:0,b->echoes,b->blocked,b->seal_x/FRACUNIT,b->seal_y/FRACUNIT,b->attacks,b->last_burst,
 b->proof?"true":"false",b->gate_stage,b->seal_b_x/FRACUNIT,b->seal_b_y/FRACUNIT);
}

void Rogue_BossJSON(FILE *out) {
 if(!enabled() || !count) {fprintf(out,"null");return;}
 // Legacy single-encounter readers follow the ring being used, then the first
 // living demon. All identities and independent progress are also in bosses[].
 boss_t *selected=&bosses[0];int sector=players[consoleplayer].mo?players[consoleplayer].mo->subsector->sector->tag:0;
 for(int i=count-1;i>=0;i--)if(alive(&bosses[i]))selected=&bosses[i];
 for(int i=0;i<count;i++)if(sector==bosses[i].tag || (bosses[i].tag_b && sector==bosses[i].tag_b))selected=&bosses[i];
 status(out,selected);
}
void Rogue_BossesJSON(FILE *out) {
 fprintf(out,"[");
 if(enabled())for(int i=0;i<count;i++) {if(i)fprintf(out,",");status(out,&bosses[i]);}
 fprintf(out,"]");
}
