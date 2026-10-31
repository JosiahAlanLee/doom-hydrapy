// SPDX-License-Identifier: GPL-2.0-or-later
// Single-player run economy. RVEND is opt-in; unmarked WADs keep vanilla rules.
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include "p_local.h"
#include "doomstat.h"
#include "r_main.h"
#include "w_wad.h"
#include "z_zone.h"
#include "rogue_vending.h"

#define FLOORS 7
#define PERKS 5
#define RANKS 2
enum {HEALTH, LINING, DAMAGE, AMMO, SPEED};
typedef struct {int map,id,x,y,order[PERKS],bought,kills,secrets;} vendor_t;
static vendor_t vendors[FLOORS];
static int loaded, count, invalid, current_valid, menu, ranks[PERKS];
static int scrap=6, earned, spent;
static const char *names[PERKS]={"DEEP LUNGS","COMPOSITE LINING","HOT LOADS","AMMO BINS","RUNNER COILS"};
static const char *details[PERKS]={"+25 health cap; restore up to 25 health.","Take 10% less damage per rank.","Deal 20% more weapon damage per rank.","+50% ammo capacity per rank; small refill.","Move 10% faster per rank; turning unchanged."};
extern int maxammo[NUMAMMO];

static int u16(const unsigned char *p) {return p[0]|p[1]<<8;}
static int s16(const unsigned char *p) {return (short)u16(p);}
static vendor_t *current(void) {
 if(!current_valid)return NULL;
 for(int i=0;i<count;i++)if(vendors[i].map==gamemap)return &vendors[i];
 return NULL;
}
static mobj_t *cabinet(vendor_t *v) {
 if(!v || gamestate!=GS_LEVEL)return NULL;
 for(thinker_t *t=thinkercap.next;t!=&thinkercap;t=t->next) {
  if(t->function.acp1!=(actionf_p1)P_MobjThinker)continue;
  mobj_t *m=(mobj_t*)t;
  if(m->type==MT_VENDING && m->x==v->x*FRACUNIT && m->y==v->y*FRACUNIT)return m;
 }
 return NULL;
}
static int alive(player_t *p) {return p==&players[consoleplayer] && gamestate==GS_LEVEL && p->mo && p->health>0 && p->playerstate==PST_LIVE;}
static int nearby(player_t *p, mobj_t *m) {
 if(!m || !alive(p))return 0;
 int64_t dx=(int64_t)m->x-p->mo->x,dy=(int64_t)m->y-p->mo->y;
 if(llabs(dx)>96*FRACUNIT || llabs(dy)>96*FRACUNIT || llabs((int64_t)m->z-p->mo->z)>24*FRACUNIT)return 0;
 if(dx*dx+dy*dy>(int64_t)(96*FRACUNIT)*(96*FRACUNIT))return 0;
 angle_t a=R_PointToAngle2(p->mo->x,p->mo->y,m->x,m->y)-p->mo->angle;
 if(a>ANG45 && a<(angle_t)(0-ANG45))return 0;
 return P_CheckSight(p->mo,m);
}
static int offers(vendor_t *v,int *out) {
 int n=0;
 if(v)for(int i=0;i<PERKS && n<3;i++)if(ranks[v->order[i]]<RANKS)out[n++]=v->order[i];
 return n;
}
static int cost(vendor_t *v,int perk) {return 6+3*ranks[perk]+v->map-1;}
static void ammo_caps(player_t *p) {
 if(!current() || p!=&players[consoleplayer])return;
 for(int i=0;i<NUMAMMO;i++)p->maxammo[i]=maxammo[i]*(p->backpack?2:1)*(100+50*ranks[AMMO])/100;
}

void Rogue_VendingLoad(void) {
 menu=0;current_valid=0;
 if(!getenv("DOOM_ROGUE_FLOORS"))return;
 if(!loaded) {
  loaded=1;
  int lump=W_CheckNumForName("RVEND");if(lump<0)return;
  int length=W_LumpLength(lump);
  if(length<12 || length>12+FLOORS*16) {invalid=1;return;}
  const unsigned char *p=W_CacheLumpNum(lump,PU_CACHE);
  int n=u16(p+8);
  if(memcmp(p,"RVN1",4) || n<1 || n>FLOORS || u16(p+10) || length!=12+n*16) {invalid=1;return;}
  for(int i=0;i<n;i++) {
   const unsigned char *b=p+12+i*16;
   vendor_t *v=&vendors[i];
   v->map=u16(b);v->id=u16(b+2);v->x=s16(b+4);v->y=s16(b+6);
   int mask=0;
   if(v->map<1 || v->map>FLOORS || v->id<1 || abs(v->x)>32760 || abs(v->y)>32760 || b[13] || b[14] || b[15]) {invalid=1;return;}
   for(int j=0;j<i;j++)if(vendors[j].map==v->map || vendors[j].id==v->id) {invalid=1;return;}
   for(int j=0;j<PERKS;j++) {
    int perk=b[8+j];
    if(perk>=PERKS || (mask&(1<<perk))) {invalid=1;return;}
    mask|=1<<perk;v->order[j]=perk;
   }
  }
  count=n;
 }
 if(invalid)return;
 current_valid=1;
 vendor_t *v=current();int machines=0;
 for(thinker_t *t=thinkercap.next;t!=&thinkercap;t=t->next)
  if(t->function.acp1==(actionf_p1)P_MobjThinker && ((mobj_t*)t)->type==MT_VENDING)machines++;
 if(!v || machines!=1 || !cabinet(v)) {current_valid=0;return;}
 ammo_caps(&players[consoleplayer]);
}

void Rogue_VendingTick(void) {
 vendor_t *v=current();if(!v || (gamestate!=GS_LEVEL && gamestate!=GS_INTERMISSION))return;
 player_t *p=&players[consoleplayer];
 int reward=0;
 if(p->killcount>v->kills) {reward+=p->killcount-v->kills;v->kills=p->killcount;}
 if(p->secretcount>v->secrets) {reward+=3*(p->secretcount-v->secrets);v->secrets=p->secretcount;}
 earned+=reward;scrap+=reward;if(scrap>999)scrap=999;
 if(gamestate!=GS_LEVEL) {menu=0;return;}
 ammo_caps(p);
 mobj_t *m=cabinet(v);
 if(m && v->bought && m->state!=&states[S_VENDOR_SPENT])P_SetMobjState(m,S_VENDOR_SPENT);
 if(menu && !nearby(p,m))menu=0;
}
int Rogue_VendingUse(player_t *p) {
 vendor_t *v=current();
 if(!v || !nearby(p,cabinet(v)))return 0;
 if(!v->bought)menu=1;
 return 1;
}
void Rogue_VendingClose(void) {menu=0;}
void Rogue_VendingBuy(FILE *out,unsigned id,unsigned slot) {
 vendor_t *v=current();player_t *p=&players[consoleplayer];int stock[3];
 const char *error=NULL;int n=offers(v,stock);
 if(!v || !menu || id!=(unsigned)v->id || !nearby(p,cabinet(v)))error="Machine is not open.";
 else if(v->bought)error="Already dispensed on this floor.";
 else if(slot>=(unsigned)n)error="Unknown offer.";
 else if(scrap<cost(v,stock[slot]))error="Not enough scrap.";
 if(error) {fprintf(out,"VEND {\"ok\":false,\"error\":\"%s\"}\n",error);fflush(out);return;}
 int perk=stock[slot],price=cost(v,perk);
 scrap-=price;spent+=price;ranks[perk]++;v->bought=1;menu=0;
 if(perk==HEALTH && p->health<Rogue_HealthCap(p,MAXHEALTH)) {
  p->health+=25;
  if(p->health>Rogue_HealthCap(p,MAXHEALTH))p->health=Rogue_HealthCap(p,MAXHEALTH);
  p->mo->health=p->health;
 }
 ammo_caps(p);
 if(perk==AMMO) {
  const int refill[NUMAMMO]={30,8,30,2};
  for(int i=0;i<NUMAMMO;i++) {
   p->ammo[i]+=refill[i];if(p->ammo[i]>p->maxammo[i])p->ammo[i]=p->maxammo[i];
  }
 }
 mobj_t *m=cabinet(v);if(m)P_SetMobjState(m,S_VENDOR_SPENT);
 fprintf(out,"VEND {\"ok\":true,\"perk\":%d,\"rank\":%d,\"cost\":%d}\n",perk,ranks[perk],price);fflush(out);
}
int Rogue_HealthCap(player_t *p,int base) {return base+(current() && p==&players[consoleplayer]?25*ranks[HEALTH]:0);}
int Rogue_MoveScale(player_t *p,int thrust) {return current() && p==&players[consoleplayer]?thrust*(100+10*ranks[SPEED])/100:thrust;}
int Rogue_UpgradeDamage(mobj_t *target,mobj_t *source,int damage) {
 if(!current() || damage<=0 || damage>=1000)return damage;
 if(source && source->player==&players[consoleplayer] && !target->player)damage=damage*(100+20*ranks[DAMAGE])/100;
 if(target->player==&players[consoleplayer])damage=(damage*(100-10*ranks[LINING])+99)/100;
 return damage;
}
void Rogue_VendingJSON(FILE *out) {
 vendor_t *v=current();player_t *p=&players[consoleplayer];
 if(!v) {fprintf(out,"{\"active\":false,\"invalid\":%s}",invalid?"true":"false");return;}
 fprintf(out,"{\"active\":true,\"credits\":%d,\"earned\":%d,\"spent\":%d,\"menu_open\":%s,\"max_health\":%d,\"damage_percent\":%d,\"incoming_percent\":%d,\"move_percent\":%d,\"ammo_percent\":%d,\"ammo_caps\":[%d,%d,%d,%d],\"perks\":[",
 scrap,earned,spent,menu?"true":"false",Rogue_HealthCap(p,MAXHEALTH),100+20*ranks[DAMAGE],100-10*ranks[LINING],100+10*ranks[SPEED],100+50*ranks[AMMO],p->maxammo[0],p->maxammo[1],p->maxammo[2],p->maxammo[3]);
 for(int i=0;i<PERKS;i++)fprintf(out,"%s{\"id\":%d,\"name\":\"%s\",\"rank\":%d,\"max_rank\":%d}",i?",":"",i,names[i],ranks[i],RANKS);
 fprintf(out,"],\"vendor\":{\"id\":%d,\"near\":%s,\"spent\":%s,\"x\":%d,\"y\":%d,\"offers\":[",v->id,nearby(p,cabinet(v))?"true":"false",v->bought?"true":"false",v->x,v->y);
 int stock[3],n=offers(v,stock);
 for(int i=0;i<n;i++) {
  int k=stock[i];
  fprintf(out,"%s{\"id\":%d,\"title\":\"%s\",\"description\":\"%s\",\"cost\":%d,\"rank\":%d,\"max_rank\":%d}",i?",":"",k,names[k],details[k],cost(v,k),ranks[k],RANKS);
 }
 fprintf(out,"]}}");
}
