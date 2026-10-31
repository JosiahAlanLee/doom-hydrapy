// SPDX-License-Identifier: GPL-3.0-or-later
// Native encounters with forgiving shield rules and physical 3D navigation.
class NRMonster : Actor {
 int Kind,Roll,BossIndex,MaxHP,Phase,EndsAt,Cooldown,AttackCount,DeadAt,NextMelee;
 bool Awake,Frozen; double AimYaw,AimPitch; Vector3 LastPoint;
 Default {Radius 20; Height 72; Health 100; Mass 100; MaxStepHeight 24; Scale .65;
  +SOLID +SHOOTABLE +ISMONSTER +COUNTKILL +CANPASS}
 States {Spawn: TNT1 A -1; Stop; Death: TNT1 A -1; Stop;}
 override void BeginPlay() {
  Super.BeginPlay();Kind=args[0];Roll=args[1];BossIndex=args[2]-1;
  if(Kind<1 || Kind>16) {Destroy();return;}
  switch(Kind) {
   case 1: health=20*(65+Roll*2)/100;break;
   case 2: health=150*(140+Roll*3)/100;break;
   case 3: health=60*(90+Roll*2)/100;break;
   case 4: health=400*(45+Roll*2)/100;break;
   case 5: health=1000*(50+Roll)/100;break;
   case 6: health=500*(100+Roll*2)/100;break;
   case 7: health=300*(45+Roll*2)/100;break;
   case 8: health=70*(200+Roll*2)/100;break;
   case 9: health=600*(95+Roll)/100;break;
   case 10: health=500*(180+Roll*2)/100;break;
   case 11: health=85+Roll;break;
   case 12: health=110+Roll;break;
   case 13: health=90+Roll;break;
   case 14: health=65+Roll;break;
   case 15: health=70+Roll;break;
   case 16: health=105+Roll;break;
  }
  if(BossIndex>=0)health=(Kind==5?180:Kind==6?160:Kind==9?190:170)*(90+Roll*2)/100;
  MaxHP=health;LastPoint=Pos;Visual();
 }
 Name SpriteName() {
  switch(Kind) {
   case 1:return 'POSS';case 2:return 'SARG';case 3:return 'TROO';case 4:return 'HEAD';
   case 5:return 'BOSS';case 6:return 'BOS2';case 7:return 'SKEL';case 8:return 'CPOS';
   case 9:return 'FATT';case 10:return 'BSPI';case 11:return 'SPOS';case 12:return 'SSWV';
   case 13:return 'VILE';case 14:return 'SKUL';case 15:return 'CYBR';default:return 'PAIN';
  }
 }
 void Visual() {
  sprite=GetSpriteIndex(SpriteName());
  if(health<=0) {frame=20+min(3,(level.time-DeadAt)/6);return;}
  if(Kind==7) {frame=!Awake?24:Frozen?24:20+(level.time/4)%4;return;}
  if(Kind==8 && Phase>0) {frame=19+Phase;return;}
  // The six original sprite banks use Doom's compact walk/attack/death
  // sequence. Their attack art starts at E, not the atlas row used below.
  if(Kind<=6) {
   frame=!Awake?0:Phase==2 || Phase==3?4+(level.time/6)%2:Phase==4?(Kind==4?4:6):(level.time/6)%4;
   return;
  }
  int row=!Awake?0:Phase==2?2:Phase==3?3:Phase==4?4:1;
  if(Kind==13 && row==1)row=0;
  frame=row*4+(level.time/6)%4;
 }
 void StopXY() {Vel=(0,0,Vel.Z);}
 override int TakeSpecialDamage(Actor inflictor,Actor source,int damage,Name type,int flags,double angle) {
  let h=NRDirector.Get();
  if(h && BossIndex>=0 && BossIndex<h.Bosses.Size()) {
   let b=h.Bosses[BossIndex];
   if(health>0 && damage>0 && damage<1000) {
    b.LastHitUntil=level.time+7;
    if(!b.Exposed()) {
     if(Kind==9 && source && source.player)b.Proof=true;
     b.Blocked++;damage=max(1,(damage*60+99)/100);
    } else damage=max(1,damage*150/100);
   }
  }
  if(h && source && source.player && damage>0 && damage<1000)damage=damage*(100+20*h.Ranks[2])/100;
  Awake=true;
  if(Kind==8 && h && h.Holder==self)h.ReleaseGrip();
  if(Kind>=8) {Phase=4;EndsAt=level.time+(Kind==8?35:10);Cooldown=level.time+45;StopXY();}
  return Super.TakeSpecialDamage(inflictor,source,damage,type,flags,angle);
 }
 override void Die(Actor source,Actor inflictor,int flags,Name type) {
  DeadAt=level.time;Super.Die(source,inflictor,flags,type);
  bSOLID=false;bNOGRAVITY=false;Height=16;StopXY();
  let h=NRDirector.Get();if(h && h.Holder==self)h.ReleaseGrip();Visual();
  if(BossIndex>=0) {Actor.Spawn('ShellBox',Pos);Actor.Spawn('Medikit',Pos);}
  else if(Kind==1) {let clip=Actor.Spawn('Clip',Pos);if(clip)clip.bDROPPED=true;}
 }
 void Shot(Actor p,Name type,double spread=0,bool lock=false) {
  target=p;
  let shot=A_SpawnProjectile(type,32,0,spread);
  if(!shot)return;
  if(lock) {
   shot.Angle=AimYaw+spread;
   double speed=shot.Speed;
   shot.Vel=(speed*cos(AimPitch)*cos(shot.Angle),speed*cos(AimPitch)*sin(shot.Angle),-speed*sin(AimPitch));
  }
  let spore=NRSpore(shot);
  if(spore) {spore.tracer=p;spore.Seeker=Kind==14;spore.EndsAt=level.time+(Kind==14?175:210);if(Kind==14)spore.Speed=10;}
 }
 void BossAttack(Actor p,NRBoss b) {
  b.Attacks++;b.LastBurst=1;
  if(Kind!=9 && Kind!=10)Shot(p,'BaronBall',0,Kind==5);
  if(Kind==5) {b.EchoDue=level.time+18;b.EchoAngle=AimYaw;b.EchoPitch=AimPitch;}
  else if(Kind==6 && (p.player.cmd.buttons&BT_ATTACK)) {Shot(p,'BaronBall',-15);Shot(p,'BaronBall',15);b.LastBurst=3;}
  else if(Kind==9 || Kind==10) {
   // Replace the first central shot by the symmetric pair.
   b.LastBurst=2;Shot(p,'BaronBall',Kind==9?-5.625:-22.5);Shot(p,'BaronBall',Kind==9?5.625:22.5);
  }
 }
 override void Tick() {
  Super.Tick();
  let h=NRDirector.Get();
  if(!h)return;
  if(health<=0) {Visual();return;}
  let p=players[0].mo;
  h.Fold(self,LastPoint);LastPoint=Pos;StopXY();
  if(!p || p.health<=0) {Visual();return;}
  double range=Distance2D(p);bool sight=range<=1536 && CheckSight(p);
  target=p;
  if(BossIndex>=0 && BossIndex<h.Bosses.Size()) {
   let b=h.Bosses[BossIndex];double homeDistance=(Pos.XY-b.Home.XY).Length();
   if(b.HomeActor && homeDistance>b.ArenaRadius)b.Returning=true;
   if(b.Returning && b.HomeActor) {
    if(homeDistance<96) {b.Returning=false;Cooldown=level.time+35;}
    else {Phase=1;h.Navigate(self,b.HomeActor,2.5);Visual();return;}
   }
   bool quietCharge=Kind==6 && !b.Exposed() && b.OnRing(p) && !(p.player.cmd.buttons&BT_ATTACK);
   if(level.time<b.StaggerUntil || quietCharge) {
    Phase=4;EndsAt=level.time+1;Cooldown=max(Cooldown,level.time+18);StopXY();Visual();return;
   }
  }
  if(Kind==7) {
   bool seen=h.Watched(p,self) && h.Illuminated(self);
   if(seen)Awake=true;Frozen=seen || !Awake;
   if(!Frozen) {
    if(range<64 && abs(p.Pos.Z-Pos.Z)<56 && sight && level.time>=NextMelee) {p.DamageMobj(self,self,4,'NRMelee');NextMelee=level.time+35;}
    else h.Navigate(self,p,3.5);
   }
   Visual();return;
  }
  if(Kind==8) {ReDead(h,p,range,sight);Visual();return;}
  if(!Awake) {
   if(!sight || (Kind==13 && range>192)) {Visual();return;}
   Awake=true;Phase=1;
  }
  if(Kind==15 && Phase==3) {
   if(level.time>=EndsAt)Phase=1;
   else if(range<=50 && abs(p.Pos.Z-Pos.Z)<64 && sight) {p.DamageMobj(self,self,10,'NRDash');Phase=1;}
   else if(!TryMove(Pos.XY+(cos(AimYaw)*14,sin(AimYaw)*14),0))Phase=1;
   Visual();return;
  }
  if(Phase==4 || Phase==3) {if(level.time<EndsAt) {Visual();return;}Phase=1;}
  if(Phase==2) {
   if(level.time<EndsAt) {Visual();return;}
   AttackCount++;
   if(BossIndex>=0 && BossIndex<h.Bosses.Size())BossAttack(p,h.Bosses[BossIndex]);
   else if(Kind==11 || Kind==1)LineAttack(AimYaw,1536,AimPitch,Kind==11?9:5,'NRShot','BulletPuff');
   else if(Kind==12 && range<=320 && sight)p.DamageMobj(self,self,8,'NRArc');
   else if(Kind==13 && range<=128 && sight)p.DamageMobj(self,self,12,'NRDoor');
   else if(Kind==2 && range<=72 && abs(p.Pos.Z-Pos.Z)<56 && sight)p.DamageMobj(self,self,12,'NRMelee');
   else if(Kind==15) {Phase=3;EndsAt=level.time+24;Cooldown=level.time+140;Visual();return;}
   else if(Kind==16) {Shot(p,'NRSpore',-7.5,true);Shot(p,'NRSpore',0,true);Shot(p,'NRSpore',7.5,true);}
   else if(Kind==14)Shot(p,'NRSpore');
   else if(Kind==3)Shot(p,'DoomImpBall');
   else if(Kind==4)Shot(p,'CacodemonBall');
   Phase=3;EndsAt=level.time+10;Cooldown=level.time+(Kind==13?105:140);Visual();return;
  }
  double reach=Kind==11?1400:Kind==12?256:Kind==13?192:Kind==15?320:Kind==2?64:1200;
  if(sight && range<=reach && level.time>=Cooldown) {
   Phase=2;EndsAt=level.time+(Kind==12?30:Kind==13?21:Kind==15?28:35);
   AimYaw=atan2(p.Pos.Y-Pos.Y,p.Pos.X-Pos.X);AimPitch=-atan2(p.Pos.Z+40-(Pos.Z+32),max(1.,range));Angle=AimYaw;
  } else if(Kind!=13 && Kind!=16)h.Navigate(self,p,Kind==2?1.5:Kind==12?2.:Kind==11?1.:2.);
  Visual();
 }
 void ReDead(NRDirector h,Actor p,double range,bool sight) {
  bool visible=range<=448 && sight;
  if(Phase==3) {
   if(h.Holder!=self) {Phase=4;EndsAt=level.time+35;return;}
   if(!h.ValidGrip() || level.time-h.GripAt>=140)h.ReleaseGrip();
   else if(level.time>=h.GripDamageAt) {p.DamageMobj(self,self,4,'NRGrip');h.GripDamageAt=level.time+35;}
   return;
  }
  if(Phase==4) {if(level.time<EndsAt)return;Phase=0;}
  if(Phase==1) {
   if(level.time<EndsAt)return;
   if(visible)h.ShriekUntil=level.time+12;
   Phase=2;EndsAt=level.time+35;
  }
  if(Phase==2) {
   if(!h.Holder && level.time>=h.ImmunityUntil && visible && range<72 && abs(p.Pos.Z-Pos.Z)<56) {
    h.Holder=self;h.GripAt=level.time;h.GripDamageAt=level.time+35;h.EscapeTicks=0;Phase=3;return;
   }
   if(level.time>=EndsAt)Phase=0;
  }
  if(Phase==0 && visible && level.time>=Cooldown) {Awake=true;Phase=1;EndsAt=level.time+28;Cooldown=level.time+210;return;}
  if(visible || Awake)h.Navigate(self,p,Phase==2?4.:1.3);
 }
 clearscope String JSON() {
  return String.Format("{\"class\":%d,\"health\":%d,\"max_health\":%d,\"x\":%.4f,\"y\":%.4f,\"z\":%.4f,\"angle\":%.4f,\"awake\":%s,\"frozen\":%s,\"phase\":%d,\"attack_count\":%d,\"warning_ticks\":%d,\"boss_index\":%d}",Kind,health,MaxHP,Pos.X,Pos.Y,Pos.Z,Angle,Awake?"true":"false",Frozen?"true":"false",Phase,AttackCount,Phase==2?max(0,EndsAt-level.time):0,BossIndex);
 }
}
