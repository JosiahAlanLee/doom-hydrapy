// SPDX-License-Identifier: GPL-2.0-or-later
// Scope this capture's JACK1 SysV registry/lock without changing any old registry.
#define _GNU_SOURCE
#include <dlfcn.h>
#include <sys/ipc.h>
#include <sys/shm.h>
#include <sys/sem.h>
int shmget(key_t key,size_t size,int flags){
 static int (*real)(key_t,size_t,int);
 if(!real) real=dlsym(RTLD_NEXT,"shmget");
 return real(key==IPC_PRIVATE?key:key^0x44504f4c,size,flags);
}
int semget(key_t key,int count,int flags){
 static int (*real)(key_t,int,int);
 if(!real) real=dlsym(RTLD_NEXT,"semget");
 return real(key==IPC_PRIVATE?key:key^0x44504f4c,count,flags);
}
