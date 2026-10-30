// SPDX-License-Identifier: GPL-2.0-or-later
#define _POSIX_C_SOURCE 200809L
#include "doomgeneric.h"
#include "doomtype.h"
#include "doomstat.h"
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
 if(DG_ExternalClock)singletics=true;
 doomgeneric_Create(argc,argv);
 fprintf(reply,"READY %d %llu\n",gametic,(unsigned long long)frames);fflush(reply);
 char line[128];
 while(1){
  if(!DG_ExternalClock){fd_set fds;FD_ZERO(&fds);FD_SET(0,&fds);struct timeval timeout={0,0};
   if(select(1,&fds,NULL,NULL,&timeout)==0){doomgeneric_Tick();continue;}
  }
  if(!fgets(line,sizeof(line),stdin))break;
  unsigned n,k;int down;
  if(sscanf(line,"STEP %u",&n)==1 && n<=35000){
   for(unsigned i=0;i<n;i++){virtual_ms=1000+(++clock_tics)*1000/35;doomgeneric_Tick();}
  } else if(sscanf(line,"KEY %d %u",&down,&k)==2 && k<=255 && head-tail<1024){queue[head%1024].down=!!down;queue[head++%1024].key=k;}
  else if(!strncmp(line,"QUIT",4))break;
  else {fprintf(reply,"ERROR\n");fflush(reply);continue;}
  fprintf(reply,"OK %d %llu\n",gametic,(unsigned long long)frames);fflush(reply);
 }
 return 0;
}
