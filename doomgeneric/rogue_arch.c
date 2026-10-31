// SPDX-License-Identifier: GPL-2.0-or-later
// Bounded map-authored illusions. No runtime mutation commands are exposed.
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include "p_local.h"
#include "doomstat.h"
#include "r_main.h"
#include "tables.h"
#include "w_wad.h"
#include "z_zone.h"
#include "rogue_arch.h"

typedef struct {int id,sx,sy,dx,dy,axis,sign,turns,width,reserved;} seam_t;
typedef struct {int id,a,b,height,delay,phase,seen,unseen;fixed_t bounds[2][4];} change_t;
static struct {
 int active,kind,nseams,nchanges,swaps,blocked,mutations,last_seam,invalid,have_last;
 fixed_t last_x,last_y;
 seam_t seams[16];change_t changes[8];
} arch;

void Rogue_ArchReset(void) {memset(&arch,0,sizeof(arch));}
static int word(const unsigned char *p) {
 return (int32_t)((uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24);
}
static int sector_tag(int tag) {
 int found=-1;
 for(int i=0;i<numsectors;i++)if(sectors[i].tag==tag) {if(found>=0)return -1;found=i;}
 return found;
}
static int rectangle(int index,fixed_t *b) {
 sector_t *s=&sectors[index];if(s->linecount!=4)return 0;
 b[0]=b[1]=INT_MAX;b[2]=b[3]=INT_MIN;
 for(int i=0;i<4;i++) {
  line_t *line=s->lines[i];if(line->dx && line->dy)return 0;
  vertex_t *v[2]={line->v1,line->v2};
  for(int j=0;j<2;j++) {
   if(v[j]->x<b[0])b[0]=v[j]->x;
   if(v[j]->y<b[1])b[1]=v[j]->y;
   if(v[j]->x>b[2])b[2]=v[j]->x;
   if(v[j]->y>b[3])b[3]=v[j]->y;
  }
 }
 return (int64_t)b[2]-b[0]==128*FRACUNIT && (int64_t)b[3]-b[1]==128*FRACUNIT;
}

void Rogue_ArchLoad(void) {
 Rogue_ArchReset();if(!getenv("DOOM_ROGUE_FLOORS"))return;
 int lump=W_CheckNumForName("RARCH");if(lump<0)return;
 int length=W_LumpLength(lump);if(length<20) {arch.invalid=1;return;}
 const unsigned char *p=W_CacheLumpNum(lump,PU_CACHE);
 int map=word(p+4),kind=word(p+8),ns=word(p+12),nc=word(p+16);
 if(memcmp(p,"RAR1",4) || map<1 || map>99 || kind<1 || kind>3 || ns<0 || ns>16 || nc<0 || nc>8 || length!=20+ns*40+nc*20) {arch.invalid=1;return;}
 if(map!=gamemap)return;
 arch.kind=kind;arch.nseams=ns;arch.nchanges=nc;p+=20;
 for(int i=0;i<ns;i++,p+=40) {
  seam_t *s=&arch.seams[i];
  *s=(seam_t){word(p),word(p+4),word(p+8),word(p+12),word(p+16),word(p+20),word(p+24),word(p+28),word(p+32),word(p+36)};
  if(s->id<1 || llabs((int64_t)s->sx)>32760 || llabs((int64_t)s->sy)>32760 || llabs((int64_t)s->dx)>32760 || llabs((int64_t)s->dy)>32760 ||
     s->axis<0 || s->axis>1 || (s->sign!=1 && s->sign!=-1) || s->turns<0 || s->turns>3 || s->width<16 || s->width>512 || s->reserved) {arch.invalid=1;return;}
 }
 for(int i=0;i<nc;i++,p+=20) {
  change_t *c=&arch.changes[i];c->id=word(p);int a=word(p+4),b=word(p+8);
  c->height=word(p+12);c->delay=word(p+16);c->a=sector_tag(a);c->b=sector_tag(b);
  if(c->id<1 || c->a<0 || c->b<0 || c->a==c->b || c->height<64 || c->height>1024 || c->delay<4 || c->delay>350 ||
     !rectangle(c->a,c->bounds[0]) || !rectangle(c->b,c->bounds[1])) {arch.invalid=1;return;}
  sector_t *sa=&sectors[c->a],*sb=&sectors[c->b];
  int ha=(sa->ceilingheight-sa->floorheight)/FRACUNIT,hb=(sb->ceilingheight-sb->floorheight)/FRACUNIT;
  if(!((ha==c->height && hb==0)||(hb==c->height && ha==0))) {arch.invalid=1;return;}
  c->phase=hb>0;
 }
 arch.active=1;
}

static void rotate(int64_t x,int64_t y,int turns,int64_t *rx,int64_t *ry) {
 switch(turns) {
  case 0:*rx=x;*ry=y;break;
  case 1:*rx=-y;*ry=x;break;
  case 2:*rx=-x;*ry=-y;break;
  default:*rx=y;*ry=-x;break;
 }
}
static int watched(const fixed_t *b,mobj_t *p) {
 // Conservatively treat the whole padded box as visible, even behind a wall.
 // This protects edges of closed sectors, whose centres fail native sight.
 int64_t dx=((int64_t)b[0]+b[2])/2-p->x,dy=((int64_t)b[1]+b[3])/2-p->y;
 int64_t radius=((int64_t)b[2]-b[0]+b[3]-b[1])/2+64*FRACUNIT;
 unsigned a=p->angle>>ANGLETOFINESHIFT;
 int64_t forward=(dx*finecosine[a]+dy*finesine[a])/FRACUNIT;
 int64_t side=(-dx*finesine[a]+dy*finecosine[a])/FRACUNIT;
 if(llabs(dx)+llabs(dy)<256*FRACUNIT)return 1;
 return forward>=-radius && llabs(side)<=forward+2*radius;
}
static int occupied(const fixed_t *b) {
 for(thinker_t *t=thinkercap.next;t!=&thinkercap;t=t->next) {
  if(t->function.acp1!=(actionf_p1)P_MobjThinker)continue;
  mobj_t *m=(mobj_t*)t;
  if(!(m->flags&(MF_SOLID|MF_SHOOTABLE|MF_SPECIAL|MF_MISSILE)))continue;
  int64_t r=(int64_t)m->radius+16*FRACUNIT;
  if(m->x+r>=b[0] && m->x-r<=b[2] && m->y+r>=b[1] && m->y-r<=b[3])return 1;
 }
 return 0;
}

void Rogue_ArchTick(void) {
 if(!arch.active || gamestate!=GS_LEVEL)return;
 player_t *player=&players[consoleplayer];mobj_t *m=player->mo;
 if(!m || player->health<=0)return;
 if(arch.have_last && llabs((int64_t)m->x-arch.last_x)+llabs((int64_t)m->y-arch.last_y)<=64*FRACUNIT) {
  for(int i=0;i<arch.nseams;i++) {
   seam_t *s=&arch.seams[i];
   int64_t sx=(int64_t)s->sx*FRACUNIT,sy=(int64_t)s->sy*FRACUNIT;
   int64_t before=((s->axis?arch.last_y:arch.last_x)-(s->axis?sy:sx))*s->sign;
   int64_t after=((s->axis?m->y:m->x)-(s->axis?sy:sx))*s->sign;
   int64_t lateral=s->axis?(int64_t)m->x-sx:(int64_t)m->y-sy;
   if(before>=0 || after<0 || llabs(lateral)>(int64_t)s->width*FRACUNIT)continue;
   int64_t x,y,vx,vy;rotate((int64_t)m->x-sx,(int64_t)m->y-sy,s->turns,&x,&y);
   x+=(int64_t)s->dx*FRACUNIT;y+=(int64_t)s->dy*FRACUNIT;
   if(x<INT_MIN || x>INT_MAX || y<INT_MIN || y>INT_MAX) {arch.blocked++;break;}
   fixed_t old_z=m->z;
   if(!P_RogueRelocate(m,(fixed_t)x,(fixed_t)y,m->z-m->floorz)) {arch.blocked++;break;}
   rotate(m->momx,m->momy,s->turns,&vx,&vy);m->momx=vx;m->momy=vy;
   m->angle+=(angle_t)s->turns*ANG90;player->viewz+=m->z-old_z;
   arch.swaps++;arch.last_seam=s->id;break;
  }
 }
 arch.last_x=m->x;arch.last_y=m->y;arch.have_last=1;
 for(int i=0;i<arch.nchanges;i++) {
  change_t *c=&arch.changes[i];
  if(watched(c->bounds[0],m)||watched(c->bounds[1],m)) {c->seen=1;c->unseen=0;continue;}
  if(!c->seen || occupied(c->bounds[0]) || occupied(c->bounds[1])) {c->unseen=0;continue;}
  if(++c->unseen<c->delay)continue;
  c->phase=!c->phase;c->seen=0;c->unseen=0;
  sectors[c->a].ceilingheight=sectors[c->a].floorheight+(c->phase?0:c->height*FRACUNIT);
  sectors[c->b].ceilingheight=sectors[c->b].floorheight+(c->phase?c->height*FRACUNIT:0);
  P_ChangeSector(&sectors[c->a],false);P_ChangeSector(&sectors[c->b],false);arch.mutations++;
 }
}

void Rogue_ArchJSON(FILE *out) {
 fprintf(out,"{\"active\":%s,\"kind\":%d,\"swaps\":%d,\"blocked\":%d,\"last_seam\":%d,\"mutations\":%d,\"invalid\":%s,\"phases\":[",
 arch.active?"true":"false",arch.kind,arch.swaps,arch.blocked,arch.last_seam,arch.mutations,arch.invalid?"true":"false");
 for(int i=0;i<arch.nchanges;i++)fprintf(out,"%s%d",i?",":"",arch.changes[i].phase);
 fprintf(out,"]}");
}
