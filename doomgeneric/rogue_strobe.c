// SPDX-License-Identifier: GPL-2.0-or-later
// Argon's strobe-Hollow concept, implemented on the authoritative native tic.
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "p_local.h"
#include "doomstat.h"
#include "w_wad.h"
#include "z_zone.h"
#include "rogue_strobe.h"

static struct {int active,invalid,bpm,duty,tag,flash_until,shots,flicker,tic,lit,flash,offset,phase,irregular,level;} strobe;
static int view_flicker=1;
static int word(const unsigned char *p) {
 return (int32_t)((uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24);
}
void Rogue_StrobeReset(void) {
 memset(&strobe,0,sizeof(strobe));strobe.flicker=view_flicker;
}
void Rogue_StrobeLoad(void) {
 Rogue_StrobeReset();if(!getenv("DOOM_ROGUE_FLOORS"))return;
 int lump=W_CheckNumForName("RSTROBE");if(lump<0)return;
 if(W_LumpLength(lump)!=20) {strobe.invalid=1;return;}
 const unsigned char *p=W_CacheLumpNum(lump,PU_CACHE);
 int map=word(p+4),bpm=word(p+8),duty=word(p+12),tag=word(p+16);
 if(memcmp(p,"RST1",4) || map<1 || map>99 || bpm<60 || bpm>160 || duty<15 || duty>60 || tag<1 || tag>32767) {strobe.invalid=1;return;}
 if(map!=gamemap)return;
 int found=0;for(int i=0;i<numsectors;i++)if(sectors[i].tag==tag)found++;
 if(!found) {strobe.invalid=1;return;}
 strobe.active=1;strobe.bpm=bpm;strobe.duty=duty;strobe.tag=tag;
 const char *style=getenv("DOOM_STROBE_STYLE");
 strobe.irregular=style && !strcmp(style,"irregular");
 Rogue_StrobeTick();
}
static int level_at(int tic) {
 if(strobe.irregular) {
  // Long lit stretches, then two brief ballast failures at irregular offsets.
  // Pure integer time/hash evaluation keeps gaze checks and rendering identical.
  uint32_t h=((uint32_t)(tic/140)+1U)*0x9e3779b9U;
  h^=h>>16;h*=0x85ebca6bU;h^=h>>13;
  int r=tic%140-(12+(int)(h%92));
  int first=1+(int)((h>>8)%3),second=5+(int)((h>>15)%3);
  int duration=2+(int)((h>>21)%5),low=28+(int)((h>>10)&31);
  if((r>=0 && r<first) || (r>=second && r<second+duration))return low;
  if(r>=0 && r<13)return 172+(int)((h>>3)%25);
  return 208;
 }
 // Integer arithmetic: 35 native tics/s; no render-frame or browser clock.
 int phase=(int)(((int64_t)tic*strobe.bpm+strobe.offset)%(60*TICRATE));
 return phase<strobe.duty*60*TICRATE/100?208:40;
}
void Rogue_StrobeShot(player_t *player) {
 if(!getenv("DOOM_ROGUE_FLOORS") || player!=&players[consoleplayer] || player->health<=0)return;
 strobe.shots++;strobe.flash_until=leveltime+6;
}
int Rogue_StrobeIlluminated(mobj_t *actor) {
 if(!strobe.active || !actor->subsector || actor->subsector->sector->tag!=strobe.tag)return 1;
 return level_at(leveltime)>=73 || leveltime<strobe.flash_until;
}
void Rogue_StrobeTick(void) {
 strobe.tic=leveltime;strobe.flash=leveltime<strobe.flash_until;
 strobe.level=strobe.active?level_at(leveltime):208;
 strobe.lit=strobe.level>=73;
 strobe.phase=(int)(((int64_t)leveltime*strobe.bpm+strobe.offset)%(60*TICRATE));
 if(strobe.active)for(int i=0;i<numsectors;i++)if(sectors[i].tag==strobe.tag)
  sectors[i].lightlevel=(!view_flicker || strobe.flash)?208:strobe.level;
}
void Rogue_StrobeView(int enabled) {view_flicker=enabled;strobe.flicker=enabled;Rogue_StrobeTick();}
void Rogue_StrobeSync(int phase) {
 if(!strobe.active || phase<0 || phase>=60*TICRATE)return;
 int current=(int)(((int64_t)leveltime*strobe.bpm)%(60*TICRATE));
 strobe.offset=(phase-current+60*TICRATE)%(60*TICRATE);Rogue_StrobeTick();
}
void Rogue_StrobeJSON(FILE *out) {
 int remaining=strobe.flash_until-strobe.tic;
 fprintf(out,"{\"active\":%s,\"invalid\":%s,\"bpm\":%d,\"tic\":%d,\"lit\":%s,\"muzzle\":%s,\"muzzle_ticks\":%d,\"shots\":%d,\"flicker\":%s,\"phase\":%.6f,\"style\":\"%s\",\"illumination\":%.6f}",
 strobe.active?"true":"false",strobe.invalid?"true":"false",strobe.bpm,strobe.tic,strobe.lit?"true":"false",strobe.flash?"true":"false",
 remaining>0?remaining:0,strobe.shots,view_flicker?"true":"false",strobe.phase/(60.0*TICRATE),strobe.irregular?"irregular":"bpm",strobe.level/208.0);
}
