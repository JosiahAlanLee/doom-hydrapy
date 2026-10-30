// SPDX-License-Identifier: GPL-2.0-or-later
#include <rack.hpp>
#include <sys/mman.h>
#include <fcntl.h>
#include <unistd.h>
#include <array>
#include <vector>
#include <cmath>
#include <cstring>
using namespace rack;
Plugin* pluginInstance;
constexpr int BANKS=32, VOICES=16;
struct Event {double t;int type,r,v;double note,vel;int id;};
struct Route {int voices=1; bool cz=false,drum=false;int root=60;float pan=.5f,vol=100/127.f,expression=1,bend=0,mod=0;};
struct Voice {float pitch=0,gate=0,vel=0;double released=-10;int id=0;bool seen=false;};
struct Stream:Module {
 std::vector<Event> events;std::vector<Route> routes;
 std::array<std::array<Voice,VOICES>,BANKS> voices{};
 size_t cursor=0;double elapsed=0,raw=0;uint64_t frames=0,clocks=0,on=0,off=0,seen=0;
 bool running=false,clockHigh=false,firstClock=true;double lastAbsolute=-1;
 double* proof=nullptr;size_t proofSize=0;int sourceNotes=0;
 // INPUTS: run, clock, 32 gate monitor banks, 32 audio return banks.
 // OUTPUTS: 32*(pitch,gate,velocity), stereo mix and optical/audio sync pulse.
 Stream(){config(0,3+BANKS*2,BANKS*3+3,0);configInput(66,"Gorgon absolute seconds: Z * 24");configInput(0,"Gorgon RUN");configInput(1,"Gorgon 32 PPQN at 120 BPM");
  for(int i=0;i<BANKS;i++){configInput(2+i,"Gate loopback "+std::to_string(i));configInput(2+BANKS+i,"Instrument return "+std::to_string(i));for(int j=0;j<3;j++) configOutput(i*3+j,std::to_string(i)+(j==0?" Pitch":j==1?" Gate":" Velocity"));}
  configOutput(BANKS*3,"Mix L");configOutput(BANKS*3+1,"Mix R");configOutput(BANKS*3+2,"1 Hz sync");}
 ~Stream(){if(proof)munmap(proof,proofSize);}
 void dataFromJson(json_t* root) override {
  settings::threadCount=4;
  const char* schedule=json_string_value(json_object_get(root,"schedule"));
  const char* stats=json_string_value(json_object_get(root,"proof"));
  if(!schedule||!stats)return;
  json_error_t error;json_t* doc=json_load_file(schedule,0,&error);if(!doc){WARN("schedule: %s",error.text);return;}
  json_t *rs=json_object_get(doc,"routes"),*es=json_object_get(doc,"events");size_t i;json_t* v;
  routes.clear();events.clear();
  json_array_foreach(rs,i,v){Route r;r.voices=int(json_integer_value(json_object_get(v,"voices")));const char* s=json_string_value(json_object_get(v,"instrument"));r.cz=s&&std::string(s)=="CZish";r.drum=s&&std::string(s)=="OtisSampler";if(r.drum){static const int roots[]={36,38,42,45,49,56,37,70};int family=int(json_integer_value(json_object_get(v,"family")));r.root=roots[std::clamp(family,0,7)];}routes.push_back(r);}
  if(routes.size()>BANKS){routes.clear();json_decref(doc);return;}
  json_array_foreach(es,i,v){auto d=[&](int k){return json_number_value(json_array_get(v,k));};events.push_back({d(0),int(d(1)),int(d(2)),int(d(3)),d(4),d(5),int(d(6))});}
  sourceNotes=int(json_integer_value(json_object_get(doc,"source_notes")));json_decref(doc);
  proofSize=64+size_t(sourceNotes)*64;
  int fd=open(stats,O_RDWR|O_CREAT|O_TRUNC,0600);
  if(fd>=0 && !ftruncate(fd,proofSize)){void* p=mmap(nullptr,proofSize,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);if(p!=MAP_FAILED){proof=(double*)p;std::memset(p,0,proofSize);for(int k=0;k<sourceNotes;k++)proof[8+k*8+2]=-1;}}
  if(fd>=0)close(fd);
 }
 void process(const ProcessArgs& args) override {
  bool run=inputs[0].getVoltage()>1;
  bool high=inputs[1].getVoltage()>1;
  if(run&&!running){elapsed=raw=0;frames=clocks=on=off=seen=0;cursor=0;firstClock=true;clockHigh=false;lastAbsolute=-1;for(auto& bank:voices)for(auto& v:bank)v=Voice();}
  if(run){
   if(high&&!clockHigh){clocks++;}
   double absolute=double(inputs[66].getVoltage())*24.;
   // Z is a linear absolute-time automation lane. During its last-row hold,
   // coast on Rack samples; the next pattern re-anchors without counting edges.
   if(std::abs(absolute-lastAbsolute)>1e-7){elapsed=absolute;lastAbsolute=absolute;}
   // Audit actual loopback edges, after Rack's cable propagation, not event counts alone.
   for(size_t r=0;r<routes.size();r++)for(int v=0;v<routes[r].voices;v++){
    auto& voice=voices[r][v];bool gate=inputs[2+r].getVoltage(v)>1;
    if(gate&&!voice.seen && voice.id>0){seen++;if(proof){double* p=proof+8+(voice.id-1)*8;p[2]=raw;}}
    voice.seen=gate;
   }
   while(cursor<events.size()&&events[cursor].t<=elapsed+1e-10){
    auto& e=events[cursor++];if(e.r<0||size_t(e.r)>=routes.size())continue;
    auto& r=routes[e.r];
    if(e.type==2){r.bend=e.note;continue;}
    if(e.type==3){if(e.v==7)r.vol=e.note/127.;if(e.v==11)r.expression=e.note/127.;if(e.v==10)r.pan=e.note/127.;if(e.v==1)r.mod=e.note/127.;continue;}
    if(e.v<0||e.v>=r.voices)continue;
    auto& v=voices[e.r][e.v];
    if(e.type==1){v.pitch=(e.note-r.root)/12.;v.vel=e.vel;v.gate=10;v.id=e.id;on++;
     if(proof){double* p=proof+8+(e.id-1)*8;p[0]=e.t;p[1]=raw;p[2]=-1;p[3]=double(frames);p[4]=e.r;p[5]=e.v;p[6]=e.note;p[7]=e.vel;}}
    else {v.gate=0;v.released=raw;off++;}
   }
  }
  clockHigh=high;running=run;
  double l=0,r=0;
  for(size_t bank=0;bank<routes.size();bank++){
   auto& route=routes[bank];int n=0;
   for(int i=0;i<route.voices;i++)if(voices[bank][i].gate>0 || (voices[bank][i].id && raw-voices[bank][i].released<1.))n=i+1;
   for(int port=0;port<3;port++)outputs[bank*3+port].setChannels(n);
   for(int i=0;i<n;i++){
    auto& v=voices[bank][i];float vib=route.mod*.25f*std::sin(2*M_PI*5*elapsed);
    outputs[bank*3].setVoltage(v.pitch+(route.bend+vib)/12.,i);
    outputs[bank*3+1].setVoltage(run?v.gate:0,i);
    outputs[bank*3+2].setVoltage(v.vel*10,i);
   }
   double value=0;
   if(route.cz){for(int i=0;i<n;i++)value+=inputs[2+BANKS+bank].getVoltage(i)*voices[bank][i].vel;}
   else value=inputs[2+BANKS+bank].getVoltageSum();
   value*=route.vol*route.expression*(route.drum?.35:.25);
   l+=value*std::sqrt(1-route.pan);r+=value*std::sqrt(route.pan);
  }
  outputs[BANKS*3].setVoltage(float(l));outputs[BANKS*3+1].setVoltage(float(r));
  outputs[BANKS*3+2].setVoltage(run&&std::fmod(elapsed,1.)<.05?10:0);
  if(proof){proof[0]=elapsed;proof[1]=raw;proof[2]=double(clocks);proof[3]=double(on);proof[4]=double(off);proof[5]=double(seen);proof[6]=double(frames);proof[7]=run?1:0;}
  if(run){elapsed+=args.sampleTime;raw+=args.sampleTime;frames++;}
 }
};
struct StreamWidget:ModuleWidget {StreamWidget(Stream* m){setModule(m);box.size=Vec(600,380);for(int i=0;i<67;i++)addInput(createInputCentered<PJ301MPort>(Vec(20+(i%20)*28,20+(i/20)*35),m,i));for(int i=0;i<99;i++)addOutput(createOutputCentered<PJ301MPort>(Vec(20+(i%20)*28,175+(i/20)*35),m,i));}};
Model* modelStream=createModel<Stream,StreamWidget>("Stream");
void init(Plugin* p){pluginInstance=p;p->addModel(modelStream);}
