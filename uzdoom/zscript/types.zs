// SPDX-License-Identifier: GPL-3.0-or-later
class NRNav : Object {
 Vector3 Point; int SectorIndex; Array<int> Edges; int Cost;
}
class NRSeam : Object {
 int Id,Axis,Sign,Turns,Width; Vector3 Source,Destination;
}
class NRChange : Object {
 int Id,A,B,Height,Delay,Unseen; bool Seen,Phase; Vector3 Source,Destination;
}
class NRDoor : Object {
 int Id,Swaps,Mutations; bool NeedsBosses,NextLevel; Vector3 Source,Destination; String Label;
}
class NRBoss : Object {
 NRMonster Mob; int Kind,MaxHP,OpenUntil,Stamps,Still,LastStamp,Blocked,Attacks,Echoes,EchoDue,GateStage,LastSector,LastBurst;
 bool LastUse,Proof,Returning; Vector3 Seal,Other,LastPoint,Home; double EchoAngle,EchoPitch,ArenaRadius; String Title;
 Actor HomeActor; int StaggerUntil,LastHitUntil,OpenCount;
 clearscope bool Bound() {return !Mob || Mob.health<=0;}
 clearscope bool Exposed() {return !Bound() && level.time<OpenUntil;}
 clearscope String Phase() {return Bound()?"bound":Exposed()?"exposed":"sealed";}
 clearscope bool OnRing(Actor p,bool second=false) {
  Vector3 q=second?Other:Seal;
  return p && abs(p.Pos.X-q.X)<=72 && abs(p.Pos.Y-q.Y)<=72 && abs(p.Pos.Z-q.Z)<=24;
 }
 void Expose() {
  OpenUntil=level.time+420;StaggerUntil=level.time+35;OpenCount++;Stamps=0;Still=0;Proof=false;EchoDue=0;
 }
 clearscope String Hint(Actor p) {
  if(Bound())return "DEFEATED";
  if(Exposed())return "SHIELD BROKEN / FIRE";
  bool ring=OnRing(p);
  if(Kind==5)return ring?(Stamps?"1/2 / RELEASE F, THEN PRESS F AGAIN":"0/2 / PRESS F TWICE ON THIS SEAL"):"FIND ITS F SEAL / PRESS F TWICE";
  if(Kind==6)return ring?String.Format("HOLD STILL, RELEASE FIRE / %.1f OF 1.0 SEC",Still/35.):"FIND ITS F SEAL / STAND STILL FOR 1 SECOND";
  if(Kind==9)return Proof?(ring?"PROOF RECORDED / PRESS F NOW":"PROOF RECORDED / FIND ITS F SEAL"):"SHOOT ITS SHIELD ONCE TO RECORD PROOF";
  return GateStage?(OnRing(p,true)?"B REACHED / SHIELD OPENING":"A REGISTERED / ENTER ITS CYAN B SEAL"):"ENTER ITS AMBER A SEAL, THEN CYAN B";
 }
 clearscope String JSON(Actor p) {
  return String.Format("{\"name\":\"%s\",\"class\":%d,\"health\":%d,\"max_health\":%d,\"phase\":\"%s\",\"on_seal\":%s,\"on_secondary_seal\":%s,\"has_seal\":true,\"stamps\":%d,\"still_ticks\":%d,\"open_ticks\":%d,\"echoes\":%d,\"blocked_hits\":%d,\"seal_x\":%.2f,\"seal_y\":%.2f,\"seal_z\":%.2f,\"proof\":%s,\"gate_stage\":%d,\"seal_b_x\":%.2f,\"seal_b_y\":%.2f,\"seal_b_z\":%.2f,\"attacks\":%d,\"last_burst\":%d,\"hint\":\"%s\",\"shield_damage_percent\":60,\"exposed_damage_percent\":150,\"charge_ticks\":35,\"open_count\":%d,\"last_hit_ticks\":%d,\"returning\":%s}",
   Title,Kind,Bound()?0:Mob.health,MaxHP,Phase(),OnRing(p)?"true":"false",OnRing(p,true)?"true":"false",Stamps,Still,Exposed()?OpenUntil-level.time:0,Echoes,Blocked,Seal.X,Seal.Y,Seal.Z,Proof?"true":"false",GateStage,Other.X,Other.Y,Other.Z,Attacks,LastBurst,Hint(p),OpenCount,max(0,LastHitUntil-level.time),Returning?"true":"false");
 }
}
class NRBossHome : Actor {
 Default {Radius 1; Height 1; +NOGRAVITY +NOBLOCKMAP +NOSECTOR}
 States {Spawn: TNT1 A -1; Stop;}
}
class NRSealMarker : Actor {
 int BossIndex; bool Secondary;
 Default {Radius 1; Height 16; Scale .6; +NOGRAVITY +NOBLOCKMAP}
 States {Spawn: NSLM A -1 Bright; Stop;}
 override void Tick() {
  Super.Tick();let h=NRDirector.Get();if(!h || BossIndex>=h.Bosses.Size()) {Destroy();return;}
  let b=h.Bosses[BossIndex];frame=b.Bound()?4:b.Exposed()?3:b.Kind==10?(Secondary?2:1):0;
 }
}
class NRBossBadge : Actor {
 int BossIndex;
 Default {Radius 1; Height 16; Scale .7; +NOGRAVITY +NOBLOCKMAP}
 States {Spawn: NSHB A -1 Bright; Stop;}
 override void Tick() {
  Super.Tick();let h=NRDirector.Get();if(!h || BossIndex>=h.Bosses.Size()) {Destroy();return;}
  let b=h.Bosses[BossIndex];if(b.Bound()) {Destroy();return;}
  SetOrigin(b.Mob.Pos+(0,0,b.Mob.Height+12),false);frame=b.Exposed()?1:level.time<b.LastHitUntil?2:0;
 }
}
class NRVendor : Actor {
 Default {Radius 22; Height 72; +SOLID}
 States { Spawn: VEND A -1; Stop; }
}
class NRGate : Actor {
 Default {Radius 14; Height 72; +NOGRAVITY}
 States { Spawn: NGAT A -1; Stop; }
}
class NRPlayer : DoomPlayer {
 override void Tick() {
  Vector3 before=Pos;Super.Tick();
  let h=NRDirector.Get();if(h)h.Fold(self,before);
 }
 override int GetMaxHealth(bool withupgrades) const {
  let h=NRDirector.Get();return Super.GetMaxHealth(withupgrades)+(h?25*h.Ranks[0]:0);
 }
 override int TakeSpecialDamage(Actor inflictor,Actor source,int damage,Name type,int flags,double angle) {
  let h=NRDirector.Get();
  if(h && damage>0 && damage<1000)damage=(damage*(100-10*h.Ranks[1])+99)/100;
  return Super.TakeSpecialDamage(inflictor,source,damage,type,flags,angle);
 }
 override void PlayerThink() {
  let h=NRDirector.Get();
  if(h) {
   Speed=1.+.1*h.Ranks[4];
   if(h.Holder && h.Holder.health>0) {
    player.cmd.forwardmove/=4;player.cmd.sidemove/=4;Vel=(Vel.X*.5,Vel.Y*.5,Vel.Z);
   }
   if(level.time<h.ShriekUntil) {
    player.cmd.forwardmove=0;player.cmd.sidemove=0;Vel=(Vel.X*.5,Vel.Y*.5,Vel.Z);
   }
  }
  Super.PlayerThink();
 }
}
class NRSpore : DoomImpBall {
 int EndsAt; bool Seeker;
 Default {Speed 8; Damage 2; Radius 6; Height 8;}
 override void Tick() {
  Super.Tick();
  if(!bMISSILE)return;
  if(EndsAt>0 && level.time>=EndsAt) {ExplodeMissile();return;}
  if(Seeker && tracer && tracer.health>0 && level.time%4==0) {
   double goal=atan2(tracer.Pos.Y-Pos.Y,tracer.Pos.X-Pos.X);
   double delta=NRDirector.Delta(Angle,goal);Angle+=clamp(delta,-5.625,5.625);
   double slope=(tracer.Pos.Z+40-Pos.Z)/max(1.,Distance2D(tracer)/Speed);
   Vel=(Speed*cos(Angle),Speed*sin(Angle),Vel.Z+(slope<Vel.Z?-.125:.125));
  }
 }
}
