// SPDX-License-Identifier: GPL-2.0-or-later
#define _POSIX_C_SOURCE 200809L
#include "doomgeneric.h"
#include "i_video.h"
#include "doomtype.h"
#include "doomstat.h"
#include "g_game.h"
#include "rogue_ai.h"
#include "rogue_boss.h"
#include "rogue_creature.h"
#include "rogue_argon.h"
#include "rogue_arch.h"
#include "rogue_strobe.h"
#include "d_event.h"
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/select.h>
#include <stdlib.h>
extern boolean singletics;
int DG_ExternalClock;
static uint64_t virtual_ms=1000, frames, clock_tics;
static unsigned char *shared;
static FILE *reply;
static struct {int down; unsigned char key;} queue[1024];
static unsigned head, tail;
static int rogue_floors;
static int pending_turn;
static void tick(void) {
 if(pending_turn) {
  event_t event={ev_mouse,0,pending_turn,0,0};
  D_PostEvent(&event);pending_turn=0;
 }
 doomgeneric_Tick();
 Rogue_BossTick();
 // Generated campaigns continue through MAP06 without the commercial finale.
 // G_DoWorldDone retains the player's inventory and health normally.
 if(rogue_floors && gamestate==GS_INTERMISSION && gamemap<rogue_floors)
  G_WorldDone();
}
static void state(void) {
 player_t *p=&players[consoleplayer];
 fprintf(reply,"STATE {\"map\":%d,\"health\":%d,\"armor\":%d,\"weapon\":%d,\"ammo\":[%d,%d,%d,%d],\"kills\":%d,\"total_kills\":%d,\"items\":%d,\"secrets\":%d,\"x\":%.4f,\"y\":%.4f,\"angle\":%.4f,\"level_tics\":%d,\"tic\":%d,\"gamestate\":%d,\"dead\":%s,\"won\":%s,\"boss\":",
 gamemap,p->health,p->armorpoints,p->readyweapon,p->ammo[0],p->ammo[1],p->ammo[2],p->ammo[3],p->killcount,totalkills,p->itemcount,p->secretcount,
 p->mo ? p->mo->x/65536.0 : 0.0,p->mo ? p->mo->y/65536.0 : 0.0,p->mo ? p->mo->angle*(360.0/4294967296.0) : 0.0,
 leveltime,gametic,gamestate,p->playerstate==PST_DEAD?"true":"false",
 rogue_floors && gamestate==GS_INTERMISSION && gamemap>=rogue_floors?"true":"false");
 Rogue_BossJSON(reply);fprintf(reply,",\"bosses\":");Rogue_BossesJSON(reply);
 fprintf(reply,",\"creatures\":");Rogue_CreatureStatus(reply);
 fprintf(reply,",\"argon\":");Rogue_ArgonStatus(reply);
 fprintf(reply,",\"architecture\":");Rogue_ArchJSON(reply);
 fprintf(reply,",\"strobe\":");Rogue_StrobeJSON(reply);
 fprintf(reply,",\"motion\":{\"z\":%.4f,\"momx\":%.4f,\"momy\":%.4f,\"momz\":%.4f,\"view_z\":%.4f,\"reaction_time\":%d}",
 p->mo?p->mo->z/65536.0:0.0,p->mo?p->mo->momx/65536.0:0.0,p->mo?p->mo->momy/65536.0:0.0,
 p->mo?p->mo->momz/65536.0:0.0,p->viewz/65536.0,p->mo?p->mo->reactiontime:0);
 fprintf(reply,",\"video\":{\"native_width\":%d,\"native_height\":%d,\"output_width\":%d,\"output_height\":%d}}\n",
 SCREENWIDTH,SCREENHEIGHT,DOOMGENERIC_RESX,DOOMGENERIC_RESY);fflush(reply);
}
static uint64_t now(void) {struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t); return t.tv_sec*1000ULL+t.tv_nsec/1000000;}
void DG_Init(void) {
 const char *path=getenv("DOOM_FRAME");
 if (!path) {fprintf(stderr,"DOOM_FRAME required\n"); exit(2);}
 int fd=open(path,O_RDWR|O_CREAT|O_TRUNC,0600);
 size_t size=64+DOOMGENERIC_RESX*DOOMGENERIC_RESY*4;
 if(fd<0 || ftruncate(fd,size)) {perror("frame");exit(2);}
 shared=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);close(fd);
 if(shared==MAP_FAILED){perror("mmap");exit(2);}
 memset(shared,0,size);memcpy(shared,"DHF1",4);
 ((uint32_t*)shared)[1]=DOOMGENERIC_RESX;((uint32_t*)shared)[2]=DOOMGENERIC_RESY;
}
void DG_DrawFrame(void) {
 __atomic_add_fetch((uint64_t*)(shared+32),1,__ATOMIC_SEQ_CST);
 memcpy(shared+64,DG_ScreenBuffer,DOOMGENERIC_RESX*DOOMGENERIC_RESY*4);
 ((uint64_t*)shared)[2]=++frames; ((uint64_t*)shared)[3]=gametic;
 __atomic_add_fetch((uint64_t*)(shared+32),1,__ATOMIC_SEQ_CST);
}
void DG_SleepMs(uint32_t ms) {
 if(DG_ExternalClock) return;
 else {struct timespec t={ms/1000,(ms%1000)*1000000};nanosleep(&t,NULL);}
}
uint32_t DG_GetTicksMs(void){return DG_ExternalClock?virtual_ms:now();}
int DG_GetKey(int *down,unsigned char *key){if(head==tail)return 0; *down=queue[tail%1024].down;*key=queue[tail++%1024].key;return 1;}
void DG_SetWindowTitle(const char *title){(void)title;}
int main(int argc,char **argv){
 setvbuf(stdin,NULL,_IONBF,0);
 reply=fdopen(dup(STDOUT_FILENO),"w");dup2(STDERR_FILENO,STDOUT_FILENO);
 DG_ExternalClock=getenv("DOOM_LOCKED")!=NULL;
 const char *rogue=getenv("DOOM_ROGUE_FLOORS");
 if(rogue) {rogue_floors=atoi(rogue);if(rogue_floors<1 || rogue_floors>7)return 2;}
 if(DG_ExternalClock)singletics=true;
 doomgeneric_Create(argc,argv);
 fprintf(reply,"READY %d %llu\n",gametic,(unsigned long long)frames);fflush(reply);
 char line[128];
 while(1){
  if(!DG_ExternalClock){fd_set fds;FD_ZERO(&fds);FD_SET(0,&fds);struct timeval timeout={0,0};
   if(select(1,&fds,NULL,NULL,&timeout)==0){tick();continue;}
  }
  if(!fgets(line,sizeof(line),stdin))break;
  unsigned n,k;int down,turn;
  if(sscanf(line,"STEP %u",&n)==1 && n<=35000){
   for(unsigned i=0;i<n;i++){virtual_ms=1000+(++clock_tics)*1000/35;tick();}
  } else if(sscanf(line,"KEY %d %u",&down,&k)==2 && k<=255 && head-tail<1024){queue[head%1024].down=!!down;queue[head++%1024].key=k;}
  else if(sscanf(line,"TURN %d",&turn)==1 && turn>=-4096 && turn<=4096){
   pending_turn+=turn;
   if(pending_turn>4096)pending_turn=4096;
   if(pending_turn< -4096)pending_turn= -4096;
  }
  else if(!strcmp(line,"STROBE_VIEW 0\n"))Rogue_StrobeView(0);
  else if(!strcmp(line,"STROBE_VIEW 1\n"))Rogue_StrobeView(1);
  else if(sscanf(line,"STROBE_SYNC %u",&n)==1 && n<2100)Rogue_StrobeSync(n);
  else if(!strcmp(line,"STATE\n")){state();continue;}
  else if(!strcmp(line,"MOBS\n")){Rogue_Report(reply);continue;}
  else if(!strncmp(line,"QUIT",4))break;
  else {fprintf(reply,"ERROR\n");fflush(reply);continue;}
  fprintf(reply,"OK %d %llu\n",gametic,(unsigned long long)frames);fflush(reply);
 }
 return 0;
}
