// SPDX-License-Identifier: GPL-3.0-or-later
// Opt-in bridge for one owned SDL2/OpenGL child. Never sends desktop events.
// SDL2 event field offsets are documented in SDL_events.h (zlib license);
// this Linux x86-64 subset is an independent ABI declaration, not SDL source.
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cerrno>
#include <deque>
#include <string>
#include <dlfcn.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

struct Event { alignas(8) unsigned char bytes[56]; };
static void *window;
static std::deque<Event> queue;
static std::string pending;
static int motion_x, motion_y;
static bool ready, eof;
static uint8_t *shared;
static size_t shared_size;
static uint64_t last_capture;

static bool active() {return std::getenv("NULLRUN_FRAME")!=nullptr;}
template<class T> static T symbol(const char *name) {
 void *p=dlsym(RTLD_NEXT,name);
 if(!p) {fprintf(stderr,"NRBRIDGE missing symbol %s\n",name);_exit(91);}
 return reinterpret_cast<T>(p);
}
template<class T> static T gl(const char *name) {return reinterpret_cast<T>(symbol<void*(*)(const char*)>("SDL_GL_GetProcAddress")(name));}
static void put32(Event &e,int offset,uint32_t v) {memcpy(e.bytes+offset,&v,4);}
static uint32_t get32(const Event &e,int offset) {uint32_t v;memcpy(&v,e.bytes+offset,4);return v;}
static uint64_t now() {timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec*1000000000ULL+t.tv_nsec;}
static uint32_t wid() {return window?symbol<uint32_t(*)(void*)>("SDL_GetWindowID")(window):0;}
static void initialize() {
 if(ready)return;
 ready=true;
 uint8_t version[3];symbol<void(*)(uint8_t*)>("SDL_GetVersion")(version);
 if(version[0]!=2 || sizeof(void*)!=8) {fprintf(stderr,"NRBRIDGE requires SDL2/Linux x86-64\n");_exit(92);}
 int flags=fcntl(STDIN_FILENO,F_GETFL,0);if(flags>=0)fcntl(STDIN_FILENO,F_SETFL,flags|O_NONBLOCK);
 setvbuf(stdout,nullptr,_IOLBF,0);
 fprintf(stderr,"NRBRIDGE SDL=%d.%d.%d private-input=true\n",version[0],version[1],version[2]);
}
static void enqueue_key(int down,int key) {
 Event e={};put32(e,0,down?0x300:0x301);put32(e,8,wid());e.bytes[12]=!!down;
 put32(e,16,symbol<int(*)(int)>("SDL_GetScancodeFromKey")(key));put32(e,20,key);queue.push_back(e);
}
static void command(const std::string &s) {
 int a,b;char extra;
 if(sscanf(s.c_str(),"KEY %d %d %c",&a,&b,&extra)==2 && (a==0 || a==1) && b>=0 && b<0x50000000)enqueue_key(a,b);
 else if(sscanf(s.c_str(),"MOVE %d %d %c",&a,&b,&extra)==2 && abs(a)<=4096 && abs(b)<=4096) {
  motion_x+=a;motion_y+=b;
  if(motion_x>8192)motion_x=8192;
  if(motion_x< -8192)motion_x= -8192;
  if(motion_y>8192)motion_y=8192;
  if(motion_y< -8192)motion_y= -8192;
 } else if(sscanf(s.c_str(),"BUTTON %d %d %c",&a,&b,&extra)==2 && (a==0 || a==1) && b>=1 && b<=3) {
  Event e={};put32(e,0,a?0x401:0x402);put32(e,8,wid());e.bytes[16]=b;e.bytes[17]=a;e.bytes[18]=1;queue.push_back(e);
 } else if(s=="QUIT") {Event e={};put32(e,0,0x100);queue.push_back(e);}
 else fprintf(stderr,"NRBRIDGE rejected command\n");
}
static void pump() {
 initialize();char buf[1024];
 for(int i=0;i<8;i++) {
  ssize_t n=read(STDIN_FILENO,buf,sizeof(buf));
  if(n==0) {if(!eof) {eof=true;command("QUIT");}break;}
  if(n<0) {if(errno==EAGAIN || errno==EINTR)break;command("QUIT");break;}
  pending.append(buf,n);
  if(pending.size()>8192 || queue.size()>1024) {fprintf(stderr,"NRBRIDGE input overflow\n");_exit(93);}
  size_t p;
  while((p=pending.find('\n'))!=std::string::npos) {command(pending.substr(0,p));pending.erase(0,p+1);}
 }
}
extern "C" void *SDL_CreateWindow(const char *title,int x,int y,int w,int h,uint32_t flags) {
 if(active()) {
  flags=(flags&~(uint32_t)(1|4|0x1000))|8;

 }
 window=symbol<void*(*)(const char*,int,int,int,int,uint32_t)>("SDL_CreateWindow")(title,x,y,w,h,flags);
 if(active())fprintf(stderr,"NRBRIDGE window=%p title=%s size=%dx%d\n",window,title?title:"",w,h);
 if(active() && window) {
  Event e={};put32(e,0,0x200);put32(e,8,wid());e.bytes[12]=12;queue.push_back(e);
 }
 return window;
}
extern "C" void SDL_ShowWindow(void *w) {if(!active())symbol<void(*)(void*)>("SDL_ShowWindow")(w);}
extern "C" void SDL_RaiseWindow(void *w) {if(!active())symbol<void(*)(void*)>("SDL_RaiseWindow")(w);}
extern "C" void SDL_RestoreWindow(void *w) {if(!active())symbol<void(*)(void*)>("SDL_RestoreWindow")(w);}
extern "C" int SDL_SetWindowFullscreen(void *w,uint32_t flags) {return active()?0:symbol<int(*)(void*,uint32_t)>("SDL_SetWindowFullscreen")(w,flags);}
extern "C" uint32_t SDL_GetWindowFlags(void *w) {
 uint32_t flags=symbol<uint32_t(*)(void*)>("SDL_GetWindowFlags")(w);
 return active()?(flags&~(uint32_t)(8|64))|4|0x200|0x400:flags;
}
extern "C" void *SDL_GetKeyboardFocus() {return active()?window:symbol<void*(*)()>("SDL_GetKeyboardFocus")();}
extern "C" void *SDL_GetMouseFocus() {return active()?window:symbol<void*(*)()>("SDL_GetMouseFocus")();}
extern "C" int SDL_SetRelativeMouseMode(int value) {return active()?0:symbol<int(*)(int)>("SDL_SetRelativeMouseMode")(value);}
extern "C" int SDL_CaptureMouse(int value) {return active()?0:symbol<int(*)(int)>("SDL_CaptureMouse")(value);}
extern "C" void SDL_SetWindowGrab(void *w,int value) {if(!active())symbol<void(*)(void*,int)>("SDL_SetWindowGrab")(w,value);}
extern "C" void SDL_WarpMouseInWindow(void *w,int x,int y) {if(!active())symbol<void(*)(void*,int,int)>("SDL_WarpMouseInWindow")(w,x,y);}
extern "C" int SDL_ShowCursor(int value) {return active()?1:symbol<int(*)(int)>("SDL_ShowCursor")(value);}
extern "C" uint32_t SDL_GetRelativeMouseState(int *x,int *y) {
 if(!active())return symbol<uint32_t(*)(int*,int*)>("SDL_GetRelativeMouseState")(x,y);
 pump();if(x)*x=motion_x;if(y)*y=motion_y;motion_x=motion_y=0;return 0;
}
extern "C" int SDL_PollEvent(Event *out) {
 if(!active())return symbol<int(*)(Event*)>("SDL_PollEvent")(out);
 pump();Event e;
 // Drain native window events; the hidden child never acquires physical input.
 while(symbol<int(*)(Event*)>("SDL_PollEvent")(&e)) {
  uint32_t type=get32(e,0);
  if((type==0x200 && e.bytes[12]==13) || (type>=0x300 && type<=0x403))continue;
  if(out)*out=e;
  return 1;
 }
 if(!queue.empty()) {if(out)*out=queue.front();queue.pop_front();return 1;}
 return 0;
}
extern "C" void SDL_GL_SwapWindow(void *w) {
 static unsigned swaps;
 if(active() && (swaps<5 || swaps==100 || swaps==900)) {
  fprintf(stderr,"NRBRIDGE swap=%u window=%p current=%p context=%p\n",swaps,w,symbol<void*(*)()>("SDL_GL_GetCurrentWindow")(),symbol<void*(*)()>("SDL_GL_GetCurrentContext")());
 }
 swaps++;
 if(active() && !getenv("NULLRUN_NO_CAPTURE")) {
  pump();int width=0,height=0;symbol<void(*)(void*,int*,int*)>("SDL_GL_GetDrawableSize")(w,&width,&height);

  uint64_t tick=now();
  if(width>0 && height>0 && width<=4096 && height<=2160 && tick-last_capture>=16000000ULL) {
   using Proc=void*(*)(const char*);auto proc=symbol<Proc>("SDL_GL_GetProcAddress");
   auto get=(void(*)(unsigned,int*))proc("glGetIntegerv");auto bind=(void(*)(unsigned,unsigned))proc("glBindFramebuffer");
   auto buffer=(void(*)(unsigned,unsigned))proc("glBindBuffer");auto readbuf=(void(*)(unsigned))proc("glReadBuffer");
   auto store=(void(*)(unsigned,int))proc("glPixelStorei");auto pixels=(void(*)(int,int,int,int,unsigned,unsigned,void*))proc("glReadPixels");
   if(!get || !bind || !buffer || !readbuf || !store || !pixels) {_exit(94);}
   size_t size=64+(size_t)width*height*4;
   if(!shared) {
    int fd=open(getenv("NULLRUN_FRAME"),O_CREAT|O_EXCL|O_RDWR,0600);
    if(fd<0 || ftruncate(fd,size)) {perror("NRBRIDGE frame");_exit(95);}
    shared=(uint8_t*)mmap(nullptr,size,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);close(fd);
    if(shared==MAP_FAILED)_exit(95);
    shared_size=size;memset(shared,0,64);memcpy(shared,"NRF1",4);
    ((uint32_t*)shared)[1]=width;((uint32_t*)shared)[2]=height;
    auto str=(const unsigned char*(*)(unsigned))proc("glGetString");fprintf(stderr,"NRBRIDGE renderer=%s size=%dx%d\n",str(0x1F01),width,height);
   }
   if(size!=shared_size) {_exit(96);}
   int fb,pbo,read,align,row;get(0x8CAA,&fb);get(0x88ED,&pbo);get(0x0C02,&read);get(0x0D05,&align);get(0x0D02,&row);
   if(((uint64_t*)shared)[2]==100) {int draw;get(0x8CA6,&draw);fprintf(stderr,"NRBRIDGE framebuffer read=%d draw=%d buffer=%x\n",fb,draw,read);}
   bind(0x8CA8,0);buffer(0x88EB,0);readbuf(0x0405);store(0x0D05,1);store(0x0D02,0);
   __atomic_add_fetch((uint64_t*)(shared+32),1,__ATOMIC_SEQ_CST);
   pixels(0,0,width,height,0x1908,0x1401,shared+64);
   ((uint64_t*)shared)[2]++;((uint64_t*)shared)[3]=tick;
   __atomic_add_fetch((uint64_t*)(shared+32),1,__ATOMIC_SEQ_CST);
   bind(0x8CA8,fb);buffer(0x88EB,pbo);readbuf(read);store(0x0D05,align);store(0x0D02,row);last_capture=tick;
  }
 }
 symbol<void(*)(void*)>("SDL_GL_SwapWindow")(w);
}
