// SPDX-License-Identifier: GPL-3.0-or-later
class NRDirector : StaticEventHandler {
 Array<NRNav> Nodes; Array<NRSeam> Seams; Array<NRChange> Changes; Array<NRDoor> Doors;
 Array<NRBoss> Bosses; Array<NRMonster> Mobs; Array<int> LightSectors;
 NRVendor Vendor; NRMonster Holder;
 int Ranks[5],Stock[5],Bought[8],PaidKills[8],PaidSecrets[8],PreviousAmmo[4];
 int Credits,Earned,Spent,Kind,Base,Swaps,InternalSwaps,Blocked,LastSeam,Mutations,LightLevel,Shots,FlashUntil;
 int GripAt,GripDamageAt,EscapeTicks,ImmunityUntil,ShriekUntil,NavGoal,NavDue;
 bool Initialized,ShopOpen,Won,LastUse,HaveLast,Invalid,VendorNear;
 Vector3 LastPoint; String Error;
 ui int UIFrames;

 clearscope static NRDirector Get() {return NRDirector(StaticEventHandler.Find('NRDirector'));}
 clearscope static double Delta(double from,double to) {double d=(to-from)%360.;if(d>180)d-=360;if(d< -180)d+=360;return d;}
 clearscope static Vector2 Rotate(Vector2 v,int turns) {
  switch(turns%4) {case 1:return (-v.Y,v.X);case 2:return (-v.X,-v.Y);case 3:return (v.Y,-v.X);default:return v;}
 }
 void ResetRun() {
  for(int i=0;i<5;i++)Ranks[i]=0;
  for(int i=0;i<8;i++) {Bought[i]=0;PaidKills[i]=0;PaidSecrets[i]=0;}
  Credits=6;Earned=0;Spent=0;Won=false;Initialized=true;
 }
 override void NewGame() {ResetRun();}
 override void WorldLoaded(WorldEvent e) {
  if(!Initialized)ResetRun();
  Nodes.Clear();Seams.Clear();Changes.Clear();Doors.Clear();Bosses.Clear();Mobs.Clear();LightSectors.Clear();
  Vendor=null;Holder=null;ShopOpen=false;VendorNear=false;HaveLast=false;LastUse=false;Invalid=false;Error="";
  Swaps=0;InternalSwaps=0;Blocked=0;Mutations=0;LastSeam=0;NavGoal=-1;NavDue=0;LightLevel=208;
  int lump=Wads.FindLump(String.Format("NRMAP%02d",level.levelnum));
  if(lump<0) {Invalid=true;Error="Missing authored campaign data";return;}
  Array<String> lines;Wads.ReadLump(lump).Split(lines,"\n",TOK_SKIPEMPTY);
  for(int i=0;i<lines.Size();i++) {
   Array<String> p;lines[i].Split(p," ",TOK_SKIPEMPTY);
   if(p.Size()==0)continue;
   if(p[0]=="N" && p.Size()>=5 && Nodes.Size()<2048) {
    let n=new('NRNav');n.Point=(p[1].ToDouble(),p[2].ToDouble(),p[3].ToDouble());n.SectorIndex=p[4].ToInt();n.Cost=-1;
    if(p.Size()>5) {Array<String> edges;p[5].Split(edges,",",TOK_SKIPEMPTY);for(int j=0;j<edges.Size();j++)n.Edges.Push(edges[j].ToInt());}
    Nodes.Push(n);
   } else if(p[0]=="S" && p.Size()==12 && Seams.Size()<32) {
    let s=new('NRSeam');s.Id=p[1].ToInt();s.Source=(p[2].ToDouble(),p[3].ToDouble(),p[4].ToDouble());
    s.Destination=(p[5].ToDouble(),p[6].ToDouble(),p[7].ToDouble());s.Axis=p[8].ToInt();s.Sign=p[9].ToInt();s.Turns=p[10].ToInt();s.Width=p[11].ToInt();Seams.Push(s);
   } else if(p[0]=="B" && p.Size()==9 && Bosses.Size()<2) {
    let b=new('NRBoss');b.Kind=p[1].ToInt();b.Seal=(p[2].ToDouble(),p[3].ToDouble(),p[4].ToDouble());
    b.Other=(p[5].ToDouble(),p[6].ToDouble(),p[7].ToDouble());b.Title=p[8];b.LastStamp=-100;Bosses.Push(b);
   } else if(p[0]=="V" && p.Size()==9) {
    for(int j=0;j<5;j++)Stock[j]=p[4+j].ToInt();
   } else if(p[0]=="P" && p.Size()==3) {Kind=p[1].ToInt();Base=p[2].ToInt();}
   else if(p[0]=="G" && p.Size()==13 && Doors.Size()<16) {
    let g=new('NRDoor');g.Id=p[1].ToInt();g.Source=(p[2].ToDouble(),p[3].ToDouble(),p[4].ToDouble());
    g.Destination=(p[5].ToDouble(),p[6].ToDouble(),p[7].ToDouble());g.NeedsBosses=p[8].ToInt()!=0;g.Swaps=p[9].ToInt();g.Mutations=p[10].ToInt();g.NextLevel=p[11].ToInt()!=0;g.Label=p[12];g.Label.Substitute("_"," ");Doors.Push(g);
   } else if(p[0]=="C" && p.Size()==11 && Changes.Size()<8) {
    let c=new('NRChange');c.Id=p[1].ToInt();c.A=p[2].ToInt();c.B=p[3].ToInt();c.Height=p[4].ToInt();c.Delay=p[5].ToInt();
    c.Source=(p[6].ToDouble(),p[7].ToDouble(),p[10].ToDouble());c.Destination=(p[8].ToDouble(),p[9].ToDouble(),p[10].ToDouble());Changes.Push(c);
   } else if(p[0]=="L" && p.Size()==2) {
    Array<String> ids;p[1].Split(ids,",",TOK_SKIPEMPTY);for(int j=0;j<ids.Size();j++)LightSectors.Push(ids[j].ToInt());
   } else {Invalid=true;Error="Invalid authored map record";}
  }
  for(int i=0;i<Nodes.Size();i++) {
   let n=Nodes[i];
   if(n.SectorIndex<0 || n.SectorIndex>=level.Sectors.Size())Invalid=true;
   for(int j=0;j<n.Edges.Size();j++)if(n.Edges[j]<0 || n.Edges[j]>=Nodes.Size())Invalid=true;
  }
  for(int i=0;i<Changes.Size();i++)if(Changes[i].A<0 || Changes[i].B<0 || Changes[i].A>=level.Sectors.Size() || Changes[i].B>=level.Sectors.Size())Invalid=true;
  let it=ThinkerIterator.Create('NRMonster');NRMonster mob;
  while(mob=NRMonster(it.Next())) {
   Mobs.Push(mob);
   if(mob.BossIndex>=0 && mob.BossIndex<Bosses.Size()) {
    let b=Bosses[mob.BossIndex];b.Mob=mob;b.MaxHP=mob.MaxHP;b.Home=mob.Pos;
    b.HomeActor=Actor.Spawn('NRBossHome',mob.Pos);
    b.ArenaRadius=max(384.,max((b.Seal.XY-mob.Pos.XY).Length(),(b.Other.XY-mob.Pos.XY).Length())+160);
   }
  }
  it=ThinkerIterator.Create('NRVendor');Vendor=NRVendor(it.Next());
  for(int i=0;i<Bosses.Size();i++) {
   let b=Bosses[i];
   let marker=NRSealMarker(Actor.Spawn('NRSealMarker',b.Seal+(0,0,8)));if(marker)marker.BossIndex=i;
   if(b.Kind==10) {marker=NRSealMarker(Actor.Spawn('NRSealMarker',b.Other+(0,0,8)));if(marker) {marker.BossIndex=i;marker.Secondary=true;}}
   let badge=NRBossBadge(Actor.Spawn('NRBossBadge',b.Mob?b.Mob.Pos:b.Seal));if(badge)badge.BossIndex=i;
  }
  for(int i=0;i<5;i++)if(Stock[i]<0 || Stock[i]>4)Invalid=true;
  if(Nodes.Size()==0 || !Vendor || level.levelnum<1 || level.levelnum>7)Invalid=true;
  if(Invalid)Error="Invalid authored campaign metadata";
  for(int i=0;i<4;i++)PreviousAmmo[i]=AmmoAmount(i);
  UpdateAmmo();
 }
 clearscope int AmmoAmount(int slot) {
  let p=players[0].mo;if(!p)return 0;
  let item=p.FindInventory(AmmoClass(slot));return item?item.Amount:0;
 }
 clearscope static Class<Ammo> AmmoClass(int slot) {
  switch(slot) {case 0:return 'Clip';case 1:return 'Shell';case 2:return 'Cell';default:return 'RocketAmmo';}
 }
 clearscope int AmmoCap(int slot) {
  int base=slot==0?200:slot==1?50:slot==2?300:50;
  let p=players[0].mo;
  return base*(p && p.FindInventory('Backpack',true)?2:1)*(100+50*Ranks[3])/100;
 }
 void UpdateAmmo() {
  let p=players[0].mo;if(!p)return;
  for(int i=0;i<4;i++)p.SetAmmoCapacity(AmmoClass(i),AmmoCap(i));
 }
 bool Watched(Actor p,Actor m) {
  return p && m && p.Distance2D(m)<=1536 && abs(Delta(p.Angle,atan2(m.Pos.Y-p.Pos.Y,m.Pos.X-p.Pos.X)))<=45 && abs(p.Pitch)<65 && p.CheckSight(m);
 }
 clearscope bool Illuminated(Actor m) {
  for(int i=0;i<LightSectors.Size();i++)if(m.CurSector.Index()==LightSectors[i])return LightLevel>=73 || level.time<FlashUntil;
  return true;
 }
 clearscope bool Near(Actor p,Vector3 q,double range=96) {
  if(!p || p.health<=0 || abs(p.Pos.Z-q.Z)>24)return false;
  Vector2 d=q.XY-p.Pos.XY;
  return d.Length()<=range && abs(Delta(p.Angle,atan2(d.Y,d.X)))<=45;
 }
 clearscope bool NearVendor() {return VendorNear;}
 clearscope bool BossesBound() {for(int i=0;i<Bosses.Size();i++)if(!Bosses[i].Bound())return false;return true;}
 bool ValidGrip() {
  let p=players[0].mo;return Holder && Holder.health>0 && p && p.health>0 && Holder.Distance2D(p)<=96 && abs(Holder.Pos.Z-p.Pos.Z)<72 && Holder.CheckSight(p);
 }
 void ReleaseGrip() {
  if(Holder && Holder.health>0) {Holder.Phase=4;Holder.EndsAt=level.time+35;Holder.StopXY();}
  Holder=null;EscapeTicks=0;ImmunityUntil=level.time+105;
 }
 void BossTick(Actor p,bool use) {
  for(int i=0;i<Bosses.Size();i++) {
   let b=Bosses[i];if(b.Bound())continue;
   if(b.EchoDue && level.time>=b.EchoDue) {
    b.Mob.AimYaw=b.EchoAngle;b.Mob.AimPitch=b.EchoPitch;b.Mob.Shot(p,'BaronBall',0,true);b.EchoDue=0;b.Echoes++;
   }
   bool ring=b.OnRing(p),other=b.OnRing(p,true);
   int region=ring?1:other?2:0;
   if(!b.Exposed()) {
    if(b.Kind==5) {
     if(ring && use && !b.LastUse && level.time-b.LastStamp>=1) {
      b.LastStamp=level.time;b.Stamps++;
      if(b.Stamps>=2)b.Expose();
     }
    } else if(b.Kind==6) {
     bool still=(p.Pos.XY-b.LastPoint.XY).Length()<1.;
     b.Still=ring && still && !(p.player.cmd.buttons&BT_ATTACK)?b.Still+1:0;
     if(b.Still>=35)b.Expose();
    } else if(b.Kind==9) {
     if(b.Proof && ring && use)b.Expose();
    } else {
     if(region==1 && b.LastSector!=1)b.GateStage=1;
     if(region==2 && b.LastSector!=2 && b.GateStage==1) {b.Expose();b.GateStage=0;}
    }
   } else b.Still=0;
   b.LastUse=use;b.LastPoint=p.Pos;b.LastSector=region;
  }
 }
 bool Relocate(Actor p,Vector3 q) {
  Vector3 old=p.Pos;p.SetOrigin(q,false);p.FindFloorCeiling();
  bool okay=p.CheckPosition(p.Pos.XY) && p.Pos.Z>=p.FloorZ-.01 && p.Pos.Z+p.Height<=p.CeilingZ+.01;
  if(okay) {let [fit,blocker]=p.TestMobjZ();okay=fit;}
  if(!okay) {p.SetOrigin(old,false);p.FindFloorCeiling();return false;}
  p.ClearInterpolation();return true;
 }
 void Fold(Actor p,Vector3 before) {
  if(Invalid || !p || p.health<=0 || (p.Pos.XY-before.XY).Length()>64)return;
  for(int i=0;i<Seams.Size();i++) {
   let s=Seams[i];
   double a=((s.Axis?before.Y:before.X)-(s.Axis?s.Source.Y:s.Source.X))*s.Sign;
   double b=((s.Axis?p.Pos.Y:p.Pos.X)-(s.Axis?s.Source.Y:s.Source.X))*s.Sign;
   double lateral=s.Axis?p.Pos.X-s.Source.X:p.Pos.Y-s.Source.Y;
   if(a>=0 || b<0 || abs(lateral)>s.Width || abs(p.Pos.Z-s.Source.Z)>96)continue;
   Vector2 offset=Rotate(p.Pos.XY-s.Source.XY,s.Turns);
   Vector3 q=(s.Destination.X+offset.X,s.Destination.Y+offset.Y,s.Destination.Z+p.Pos.Z-s.Source.Z);
   Vector2 velocity=Rotate(p.Vel.XY,s.Turns);
   if(!Relocate(p,q)) {Relocate(p,before);p.Vel=(0,0,p.Vel.Z);Blocked++;return;}
   p.Angle+=s.Turns*90;p.Vel=(velocity.X,velocity.Y,p.Vel.Z);
   if(p.player) {Swaps++;InternalSwaps++;LastSeam=s.Id;}
   return;
  }
 }
 clearscope bool WatchedPoint(Actor p,Vector3 q) {
  Vector2 d=q.XY-p.Pos.XY;
  if(d.Length()<256)return true;
  if(abs(p.Pitch)>60)return false;
  double forward=d.X*cos(p.Angle)+d.Y*sin(p.Angle),side=-d.X*sin(p.Angle)+d.Y*cos(p.Angle);
  return forward>=-128 && abs(side)<=forward+256;
 }
 clearscope bool Occupied(Vector3 q) {
  let p=players[0].mo;if(p && abs(p.Pos.X-q.X)<96 && abs(p.Pos.Y-q.Y)<96)return true;
  let it=ThinkerIterator.Create('Actor');Actor a;
  while(a=Actor(it.Next()))if((a.bSOLID || a.bSPECIAL || a.bMISSILE) && abs(a.Pos.X-q.X)<64+a.Radius+16 && abs(a.Pos.Y-q.Y)<64+a.Radius+16)return true;
  return false;
 }
 void Mutate(Actor p) {
  for(int i=0;i<Changes.Size();i++) {
   let c=Changes[i];
   if(WatchedPoint(p,c.Source) || WatchedPoint(p,c.Destination)) {c.Seen=true;c.Unseen=0;continue;}
   if(!c.Seen || Occupied(c.Source) || Occupied(c.Destination)) {c.Unseen=0;continue;}
   c.Unseen++;if(c.Unseen<c.Delay)continue;
   let a=level.Sectors[c.A],b=level.Sectors[c.B];c.Phase=!c.Phase;c.Seen=false;c.Unseen=0;
   double za=c.Source.Z+(c.Phase?0:c.Height),zb=c.Destination.Z+(c.Phase?c.Height:0);
   a.MoveCeiling(10000,za,-1,c.Phase?-1:1,false);b.MoveCeiling(10000,zb,-1,c.Phase?1:-1,false);
   Mutations++;NavDue=0;
  }
 }
 int Nearest(Vector3 point) {
  int found=-1;double best=1e30;
  for(int i=0;i<Nodes.Size();i++) {
   Vector3 d=Nodes[i].Point-point;double score=d.X*d.X+d.Y*d.Y+4*d.Z*d.Z;
   if(score<best) {found=i;best=score;}
  }
  return found;
 }
 bool Walkable(int index) {
  let n=Nodes[index];let s=level.Sectors[n.SectorIndex];
  return s.CeilingPlane.ZatPoint(n.Point.XY)-n.Point.Z>=56;
 }
 void Navigation(Actor p) {
  int goal=Nearest(p.Pos);if(goal<0)return;
  if(goal==NavGoal && level.time<NavDue)return;
  NavGoal=goal;NavDue=level.time+7;
  for(int i=0;i<Nodes.Size();i++)Nodes[i].Cost=-1;
  Array<int> todo;todo.Push(goal);Nodes[goal].Cost=0;
  for(int i=0;i<todo.Size();i++) {
   let n=Nodes[todo[i]];
   for(int j=0;j<n.Edges.Size();j++) {
    int k=n.Edges[j];if(Nodes[k].Cost>=0 || !Walkable(k))continue;
    Nodes[k].Cost=n.Cost+1;todo.Push(k);
   }
  }
 }
 void Navigate(NRMonster m,Actor p,double speed) {
  if(Invalid || Nodes.Size()==0)return;
  Navigation(p);int at=Nearest(m.Pos);if(at<0)return;
  Vector3 goal=p.Pos;let n=Nodes[at];int next=-1,cost=n.Cost;
  if(cost>0 || !m.CheckSight(p)) {
   for(int i=0;i<n.Edges.Size();i++) {int e=n.Edges[i];if(Nodes[e].Cost>=0 && (cost<0 || Nodes[e].Cost<cost)) {next=e;cost=Nodes[e].Cost;}}
   if(next<0)return;
   goal=Nodes[next].Point;
   if((goal.XY-m.Pos.XY).Length()>192) {
    for(int i=0;i<Seams.Size();i++) {
     let s=Seams[i];if((s.Source.XY-n.Point.XY).Length()>96 || (s.Destination.XY-goal.XY).Length()>96)continue;
     goal=s.Source+(s.Axis?0:s.Sign*80,s.Axis?s.Sign*80:0,0);break;
    }
   }
  }
  Vector2 d=goal.XY-m.Pos.XY;double length=d.Length();if(length<1)return;
  Vector2 step=d*(min(speed,length)/length);double z=m.Pos.Z;m.Angle=atan2(d.Y,d.X);
  if(m.TryMove(m.Pos.XY+step,0)) {
   if(abs(m.FloorZ-z)<=24)m.SetZ(m.FloorZ);
  }
 }
 void UseDoor(Actor p) {
  for(int i=0;i<Doors.Size();i++) {
   let g=Doors[i];if(!Near(p,g.Source))continue;
   if((g.NeedsBosses && !BossesBound()) || InternalSwaps<g.Swaps || Mutations<g.Mutations)return;
   if(g.NextLevel) {if(level.levelnum==7)Won=true;else Exit_Normal(0);return;}
   if(Relocate(p,g.Destination)) {p.Vel=(0,0,p.Vel.Z);HaveLast=false;}
   return;
  }
 }
 clearscope String ArchitectureCue(Actor p) {
  for(int i=0;i<Doors.Size();i++) {
   let g=Doors[i];if(!Near(p,g.Source))continue;
   if(g.NeedsBosses && !BossesBound())return "TWO DEMONS HOLD THIS DOOR";
   if(InternalSwaps<g.Swaps)return "COUNT THE CORNERS / KEEP THE PILLAR LEFT";
   if(Mutations<g.Mutations)return "THE PASSAGES CHANGE WHEN YOU LOOK AWAY";
   return "F / " .. g.Label;
  }
  return "";
 }
 clearscope int Offer(int slot) {
  int n=0;for(int i=0;i<5;i++)if(Ranks[Stock[i]]<2) {if(n++==slot)return Stock[i];}return -1;
 }
 clearscope int Price(int perk) {return 6+level.levelnum-1+3*Ranks[perk];}
 clearscope static String PerkName(int id) {
  switch(id) {case 0:return "DEEP LUNGS";case 1:return "COMPOSITE LINING";case 2:return "HOT LOADS";case 3:return "AMMO BINS";default:return "RUNNER COILS";}
 }
 clearscope static String PerkText(int id) {
  switch(id) {case 0:return "+25 health cap; restore up to 25 health.";case 1:return "Take 10% less damage per rank.";case 2:return "Deal 20% more weapon damage per rank.";case 3:return "+50% ammo capacity per rank; small refill.";default:return "Move 10% faster per rank; turning unchanged.";}
 }
 void Buy(int slot) {
  String error="";int perk=Offer(slot),map=level.levelnum;
  if(Invalid || !ShopOpen || !NearVendor())error="Machine is not open.";
  else if(Bought[map])error="Already dispensed on this floor.";
  else if(slot<0 || slot>2 || perk<0)error="Unknown offer.";
  else if(Credits<Price(perk))error="Not enough scrap.";
  if(error!="") {Console.Printf("NRRECEIPT {\"ok\":false,\"error\":\"%s\"}",error);return;}
  int cost=Price(perk);Credits-=cost;Spent+=cost;Ranks[perk]++;Bought[map]=1;ShopOpen=false;
  let p=players[0].mo;
  if(perk==0 && p.health<100+25*Ranks[0]) {p.health=min(100+25*Ranks[0],p.health+25);p.player.health=p.health;}
  UpdateAmmo();
  if(perk==3) {p.GiveInventory('Clip',30);p.GiveInventory('Shell',8);p.GiveInventory('Cell',30);p.GiveInventory('RocketAmmo',2);}
  UpdateAmmo();Vendor.frame=1;
  Console.Printf("NRRECEIPT {\"ok\":true,\"perk\":%d,\"rank\":%d,\"cost\":%d}",perk,Ranks[perk],cost);
 }
 override void NetworkProcess(ConsoleEvent e) {
  if(e.Player!=0)return;
  if(e.Name=="nr_buy")Buy(e.Args[0]);
  else if(e.Name=="nr_close")ShopOpen=false;
  else if(e.Name=="nr_flicker")CVar.GetCVar('nr_flicker').SetBool(e.Args[0]!=0);
 }
 void LightTick() {
  uint h=(uint(level.time/140)+1)*0x9e3779b9;h^=h>>16;h*=0x85ebca6b;h^=h>>13;
  int r=level.time%140-(12+int(h%92));int first=1+int((h>>8)%3),second=5+int((h>>15)%3);
  int duration=2+int((h>>21)%5),low=28+int((h>>10)&31);
  LightLevel=((r>=0 && r<first) || (r>=second && r<second+duration))?low:r>=0 && r<13?172+int((h>>3)%25):208;
  bool steady=!CVar.GetCVar('nr_flicker').GetBool() || level.time<FlashUntil;
  for(int i=0;i<LightSectors.Size();i++)level.Sectors[LightSectors[i]].SetLightLevel(steady?208:LightLevel);
 }
 override void WorldTick() {
  if(Invalid || !playeringame[0] || !players[0].mo)return;
  let p=players[0].mo;VendorNear=Vendor && Near(p,Vendor.Pos) && p.CheckSight(Vendor);int map=level.levelnum;bool use=!!(p.player.cmd.buttons&BT_USE);
  int kills=level.killed_monsters,secrets=level.found_secrets,reward=0;
  if(kills>PaidKills[map]) {reward+=kills-PaidKills[map];PaidKills[map]=kills;}
  if(secrets>PaidSecrets[map]) {reward+=3*(secrets-PaidSecrets[map]);PaidSecrets[map]=secrets;}
  Earned+=reward;Credits=min(999,Credits+reward);UpdateAmmo();
  for(int i=0;i<4;i++) {int amount=AmmoAmount(i);if(amount<PreviousAmmo[i]) {Shots++;FlashUntil=level.time+6;}PreviousAmmo[i]=amount;}
  LightTick();
  if(p.health<=0) {if(Holder)ReleaseGrip();ShopOpen=false;return;}
  BossTick(p,use);Mutate(p);
  if(Holder) {
   if(!ValidGrip() || level.time-GripAt>=140)ReleaseGrip();
   else {EscapeTicks=use?EscapeTicks+1:0;if(EscapeTicks>=25)ReleaseGrip();}
  }
  if(use && !LastUse) {
   if(NearVendor()) {if(!Bought[map])ShopOpen=true;}
   else UseDoor(p);
  }
  LastUse=use;
  if(ShopOpen && !NearVendor())ShopOpen=false;
  if(Vendor)Vendor.frame=Bought[map]?1:0;
 }
 clearscope String VendingJSON() {
  int map=level.levelnum;
  String s=String.Format("{\"active\":true,\"credits\":%d,\"earned\":%d,\"spent\":%d,\"menu_open\":%s,\"max_health\":%d,\"damage_percent\":%d,\"incoming_percent\":%d,\"move_percent\":%d,\"ammo_percent\":%d,\"ammo_caps\":[%d,%d,%d,%d],\"perks\":[",Credits,Earned,Spent,ShopOpen?"true":"false",100+25*Ranks[0],100+20*Ranks[2],100-10*Ranks[1],100+10*Ranks[4],100+50*Ranks[3],AmmoCap(0),AmmoCap(1),AmmoCap(2),AmmoCap(3));
  for(int i=0;i<5;i++)s=s .. String.Format("%s{\"id\":%d,\"name\":\"%s\",\"rank\":%d,\"max_rank\":2}",i?",":"",i,PerkName(i),Ranks[i]);
  s=s .. String.Format("],\"vendor\":{\"id\":%d,\"near\":%s,\"spent\":%s,\"x\":%.2f,\"y\":%.2f,\"offers\":[",map,NearVendor()?"true":"false",Bought[map]?"true":"false",Vendor?Vendor.Pos.X:0,Vendor?Vendor.Pos.Y:0);
  for(int i=0;i<3;i++) {int k=Offer(i);if(k<0)break;s=s .. String.Format("%s{\"id\":%d,\"title\":\"%s\",\"description\":\"%s\",\"cost\":%d,\"rank\":%d,\"max_rank\":2}",i?",":"",k,PerkName(k),PerkText(k),Price(k),Ranks[k]);}
  return s .. "]}}";
 }
 clearscope String JSON() {
  let p=players[0].mo;if(!p)return "{}";
  String bossesText="[",mobsText="[";int selected=0,warnings=0,cue=0,watched=0,hunting=0,shriek=0;double best=1e30;
  for(int i=0;i<Bosses.Size();i++) {
   let b=Bosses[i];if(i)bossesText=bossesText .. ",";bossesText=bossesText .. b.JSON(p);
   if(b.Bound())continue;
   double distance=b.Mob.Distance2D(p),yaw=abs(Delta(p.Angle,atan2(b.Mob.Pos.Y-p.Pos.Y,b.Mob.Pos.X-p.Pos.X)));
   double score=(b.OnRing(p) || b.Kind==10 && b.OnRing(p,true))?-100000.+distance:(yaw<=35 && distance<1536)?distance:10000.+(b.Seal.XY-p.Pos.XY).Length();
   if(score<best) {selected=i;best=score;}
  }
  bossesText=bossesText .. "]";
  for(int i=0;i<Mobs.Size();i++) {
   let m=Mobs[i];if(!m)continue;
   if(mobsText!="[")mobsText=mobsText .. ",";mobsText=mobsText .. m.JSON();if(m.health<=0)continue;
   if(m.Kind==7 && m.Awake) {if(m.Frozen)watched++;else hunting++;}
   if(m.Kind==8 && m.Phase==1)shriek++;
   if(m.Kind!=7 && m.Kind!=8 && m.Phase==2) {warnings++;if(!cue)cue=m.Kind;}
  }
  mobsText=mobsText .. "]";
  String hint=cue==11?"SURVEYOR / STEP SIDEWAYS":cue==12?"BALLAST HUSK / FIND COVER":cue==13?"FALSE DOOR / STAND BACK":cue==14?"SPINDLE / SPORE CHARGING":cue==15?"LATCHWING / SIDESTEP THE DASH":cue==16?"RELAY CHOIR / FIND A GAP":"";
  if(hint=="")hint=ArchitectureCue(p);
  String effect=Holder?"\"grip\"":level.time<ShriekUntil?"\"shriek\"":"null";
  int weapon=1;let w=p.player.ReadyWeapon;
  if(w) {Name n=w.GetClassName();weapon=n=='Fist'?0:n=='Pistol'?1:n=='Shotgun'?2:n=='Chaingun'?3:n=='RocketLauncher'?4:n=='PlasmaRifle'?5:n=='BFG9000'?6:n=='Chainsaw'?7:n=='SuperShotgun'?8:1;}
  let armor=p.FindInventory('BasicArmor');
  String s=String.Format("{\"backend\":\"uzdoom\",\"map\":%d,\"health\":%d,\"armor\":%d,\"weapon\":%d,\"ammo\":[%d,%d,%d,%d],\"kills\":%d,\"total_kills\":%d,\"items\":%d,\"secrets\":%d,\"x\":%.4f,\"y\":%.4f,\"z\":%.4f,\"angle\":%.4f,\"pitch\":%.4f,\"level_tics\":%d,\"tic\":%d,\"dead\":%s,\"won\":%s,\"boss\":%s,\"bosses\":%s,\"mobs\":%s,",
   level.levelnum,p.health,armor?armor.Amount:0,weapon,AmmoAmount(0),AmmoAmount(1),AmmoAmount(2),AmmoAmount(3),level.killed_monsters,level.total_monsters,p.player.itemcount,level.found_secrets,p.Pos.X,p.Pos.Y,p.Pos.Z,p.Angle,p.Pitch,level.time,level.totaltime,p.health<=0?"true":"false",Won?"true":"false",Bosses.Size()?Bosses[selected].JSON(p):"null",bossesText,mobsText);
  s=s .. String.Format("\"creatures\":{\"watched\":%d,\"hunting\":%d,\"shriek_warning\":%d,\"effect\":%s,\"escape_ticks\":%d,\"remaining_ticks\":%d},\"argon\":{\"warnings\":%d,\"cue\":%s},",watched,hunting,shriek,effect,EscapeTicks,Holder?140-(level.time-GripAt):max(0,ShriekUntil-level.time),warnings,hint!=""?"\"" .. hint .. "\"":"null");
  s=s .. String.Format("\"architecture\":{\"active\":true,\"kind\":%d,\"swaps\":%d,\"blocked\":%d,\"last_seam\":%d,\"mutations\":%d,\"invalid\":%s},\"strobe\":{\"active\":true,\"style\":\"irregular\",\"lit\":%s,\"muzzle\":%s,\"shots\":%d,\"illumination\":%.4f},\"motion\":{\"z\":%.4f,\"momx\":%.4f,\"momy\":%.4f,\"momz\":%.4f},\"vending\":%s,\"error\":%s}",Kind,Swaps,Blocked,LastSeam,Mutations,Invalid?"true":"false",LightLevel>=73?"true":"false",level.time<FlashUntil?"true":"false",Shots,LightLevel/208.,p.Pos.Z,p.Vel.X,p.Vel.Y,p.Vel.Z,VendingJSON(),Invalid?"\"" .. Error .. "\"":"null");
  return s;
 }
 override void RenderOverlay(RenderEvent e) {
  // UZDoom 5.0.3 offscreen GL otherwise retains its startup buffer until the
  // first palette flash. A solid pass primes it without changing game state.
  // This single pixel is covered by the separate HydraPy instrument panel.
  Screen.Dim(0,1.0/255.0,0,0,1,1);
  UIFrames++;
  if(UIFrames%3==0 && players[0].mo)Console.Printf("NRSTATE %s",JSON());
 }
}
