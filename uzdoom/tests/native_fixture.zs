// SPDX-License-Identifier: GPL-3.0-or-later
// This is packed ONLY by the test runner, never by the playable builder.
class NRFixture5 : NRMonster { Default { Args 5,0,1; } }
class NRFixture6 : NRMonster { Default { Args 6,0,1; } }
class NRFixture7 : NRMonster { Default { Args 7,0,0; } }
class NRFixture8 : NRMonster { Default { Args 8,0,0; } }
class NRFixture9 : NRMonster { Default { Args 9,0,1; } }
class NRFixture10 : NRMonster { Default { Args 10,0,1; } }
class NRFixture11 : NRMonster { Default { Args 11,0,0; } }
class NRFixture12 : NRMonster { Default { Args 12,0,0; } }
class NRFixture13 : NRMonster { Default { Args 13,0,0; } }
class NRFixture14 : NRMonster { Default { Args 14,0,0; } }
class NRFixture15 : NRMonster { Default { Args 15,0,0; } }
class NRFixture16 : NRMonster { Default { Args 16,0,0; } }
class NRFixtureBlocker : Actor { Default { Radius 60; Height 100; +SOLID +NOGRAVITY } States { Spawn: TNT1 A -1; Stop; } }

class NRFixture : StaticEventHandler {
 int TestId,StartAt,StairStage,PillarSeam; bool Started,Climbing; double SavedDistance,SavedYaw; NRMonster Subject; Actor Obstruction;
 override void OnRegister() {SetOrder(-100);}
 override void WorldLoaded(WorldEvent e) {if(!Started) {TestId=-1;PillarSeam=-1;Started=true;}}
 void Receipt(String tag,bool okay,String detail="") {
  Console.Printf("NRRECEIPT {\"fixture\":\"%s\",\"case\":%d,\"ok\":%s,\"detail\":\"%s\"}",tag,TestId,okay?"true":"false",detail);
 }
 void Place(Actor p,Vector3 point,double angle=0,double pitch=0) {
  p.SetOrigin(point,false);p.FindFloorCeiling();p.ClearInterpolation();p.Vel=(0,0,0);p.Angle=angle;p.Pitch=pitch;
 }
 void ClearMobs(NRDirector h) {
  if(h.Holder)h.ReleaseGrip();h.Holder=null;h.ShriekUntil=0;h.ImmunityUntil=0;
  let it=ThinkerIterator.Create('NRMonster');Actor a;
  while(a=Actor(it.Next()))a.Destroy();
  it=ThinkerIterator.Create('Actor');
  while(a=Actor(it.Next()))if(a.bMISSILE || a is 'Inventory' && !Inventory(a).Owner)a.Destroy();
  h.Mobs.Clear();h.Bosses.Clear();Subject=null;
  if(Obstruction) {Obstruction.Destroy();Obstruction=null;}
 }
 NRMonster Make(Class<Actor> type,Vector3 point,NRDirector h) {
  let m=NRMonster(Actor.Spawn(type,point));if(m)h.Mobs.Push(m);return m;
 }
 void Setup() {
  let h=NRDirector.Get();let p=players[0].mo;if(!h || !p)return;
  NRChange authored=TestId==22 && h.Changes.Size()>0?h.Changes[0]:null;
  Climbing=false;StairStage=0;ClearMobs(h);h.Changes.Clear();h.HaveLast=false;
  h.ShopOpen=false;h.Won=false;h.Swaps=0;h.InternalSwaps=0;h.Blocked=0;h.Mutations=0;
  p.health=100;p.player.health=100;p.player.damagecount=0;
  p.ClearInventory();p.GiveInventory('Pistol',1);p.GiveInventory('Clip',50);
  for(int i=0;i<5;i++)h.Ranks[i]=0;
  h.Bought[level.levelnum]=0;h.Credits=6;h.Earned=0;h.Spent=0;h.UpdateAmmo();
  h.PaidKills[level.levelnum]=level.killed_monsters;h.PaidSecrets[level.levelnum]=level.found_secrets;
  double base=(level.levelnum-1)*512;
  Place(p,(12352,224,base));StartAt=level.time;
  if(TestId==0 || TestId==1) {
   Place(h.Vendor,(12352,304,base));p.Angle=90;
   for(int i=0;i<5;i++)h.Stock[i]=i;
   if(TestId==0) {h.Stock[0]=3;h.Stock[3]=0;}
   else {p.health=90;p.player.health=90;}
  } else if(TestId==2) {
   h.Ranks[1]=2;p.DamageMobj(null,null,10,'NRFixture');
  } else if(TestId==3) {
   h.Ranks[3]=2;h.UpdateAmmo();p.GiveInventory('Backpack',1);h.UpdateAmmo();
  } else if(TestId==4) {
   Subject=Make('NRFixture7',(12608,224,base),h);SavedDistance=Subject.Distance2D(p);
  } else if(TestId==5) {
   Subject=Make('NRFixture8',(12448,224,base),h);
  } else if(TestId>=6 && TestId<=9) {
   Class<Actor> type=TestId==6?'NRFixture5':TestId==7?'NRFixture6':TestId==8?'NRFixture9':'NRFixture10';
   Subject=Make(type,(12736,224,base),h);Subject.BossIndex=0;Subject.Cooldown=level.time+10000;
   let b=new('NRBoss');b.Mob=Subject;b.Kind=Subject.Kind;b.MaxHP=Subject.MaxHP;b.Title="FIXTURE";
   b.Seal=p.Pos;b.Other=(12608,224,base);b.LastStamp=-100;b.LastPoint=p.Pos;h.Bosses.Push(b);
  } else if(TestId==10 || TestId==11) {
   let s=h.Seams[0];Vector3 q=s.Source+(s.Axis?0:-s.Sign*48,s.Axis?-s.Sign*48:0,0);
   Place(p,q,s.Axis?(s.Sign>0?90:270):(s.Sign>0?0:180),17);
   if(TestId==11)Obstruction=Actor.Spawn('NRFixtureBlocker',s.Destination);
  } else if(TestId==12) {
   Place(p,(12160,224,base));
   let c=new('NRChange');c.Source=(12480,224,base);c.Destination=(12736,224,base);c.Id=1;c.Delay=12;c.Height=192;
   c.A=h.Nodes[h.Nearest(c.Source)].SectorIndex;c.B=h.Nodes[h.Nearest(c.Destination)].SectorIndex;
   level.Sectors[c.A].MoveCeiling(10000,base+192,-1,-1,false);level.Sectors[c.B].MoveCeiling(10000,base,-1,-1,false);
   h.Changes.Push(c);
  } else if(TestId==13) {Place(p,(12160,96,base));Climbing=true;}
  else if(TestId==14) {
   h.Credits=44;h.Ranks[4]=1;Place(p,(12352,800,base+480));
  } else if(TestId>=15 && TestId<=20) {
   Class<Actor> type=TestId==15?'NRFixture11':TestId==16?'NRFixture12':TestId==17?'NRFixture13':TestId==18?'NRFixture14':TestId==19?'NRFixture15':'NRFixture16';
   Subject=Make(type,(12352+(TestId==17?96:256),224,base),h);
  } else if(TestId==21) {
   let s=h.Seams[PillarSeam];double yaw=s.Axis?(s.Sign>0?90:270):(s.Sign>0?0:180);
   Place(p,s.Source+(s.Axis?0:-s.Sign*48,s.Axis?-s.Sign*48:0,0),yaw,17);SavedYaw=yaw+s.Turns*90;
  } else if(TestId==22 && authored) {
   h.Changes.Push(authored);Place(p,(7344,1856,base));
  }
  Receipt("ready",true);
 }
 void Verify() {
  let h=NRDirector.Get();let p=players[0].mo;bool okay=false;String detail="";
  if(TestId==0)okay=h.Ranks[3]==1 && h.Credits==0 && h.Bought[level.levelnum]==1 && h.AmmoCap(0)==300 && p.FindInventory('Cell').MaxAmount==450;
  else if(TestId==1) {
   int before=p.health;okay=h.Ranks[0]==1 && p.GetMaxHealth(true)==125 && before==115;
   Actor other=p;let med=Inventory(Actor.Spawn('Medikit',p.Pos));med.CallTryPickup(other);
   int healed=p.health;okay=okay && healed==125;
   p.health=150;p.player.health=150;med=Inventory(Actor.Spawn('Medikit',p.Pos));med.CallTryPickup(other);med.Destroy();okay=okay && p.health==150;
   detail=String.Format("purchase=%d cap=%d native_medikit=%d / ",before,p.GetMaxHealth(true),healed);
  } else if(TestId==2)okay=p.health==92;
  else if(TestId==3)okay=h.AmmoCap(0)==800 && p.FindInventory('Clip').MaxAmount==800 && p.FindInventory('Cell').MaxAmount==1200;
  else if(TestId==4)okay=Subject && Subject.Awake && !Subject.Frozen && Subject.Distance2D(p)<SavedDistance-20;
  else if(TestId==5)okay=h.Holder==null && h.ImmunityUntil>level.time && Subject.health>0;
  else if(TestId>=6 && TestId<=9) {
   okay=h.Bosses[0].Exposed();
   if(okay) {Subject.DamageMobj(p,p,5000,'NRFixture');okay=h.Bosses[0].Bound() && !Subject.bSOLID;}
  } else if(TestId==10)okay=h.InternalSwaps>=2 && abs(p.Pitch-17)<.1;
  else if(TestId==11) {let s=h.Seams[0];okay=h.Blocked>0 && h.InternalSwaps==0 && ((s.Axis?p.Pos.Y:p.Pos.X)-(s.Axis?s.Source.Y:s.Source.X))*s.Sign<=0;}
  else if(TestId==12 || TestId==22) {
   let c=h.Changes[0];double base=(level.levelnum-1)*512;
   okay=h.Mutations==1 && abs(level.Sectors[c.A].CeilingPlane.ZatPoint(c.Source.XY)-base)<.1 && abs(level.Sectors[c.B].CeilingPlane.ZatPoint(c.Destination.XY)-base-192)<.1;
   bool fits=h.Relocate(p,c.Destination);bool blocked=!h.Relocate(p,c.Source);okay=okay && fits && blocked;
  } else if(TestId==13)okay=StairStage==6 && abs(p.Pos.Z-480)<.1;
  else if(TestId==14)okay=level.levelnum==7 && h.Won && h.Credits==44 && h.Ranks[4]==1;
  else if(TestId>=15 && TestId<=20) {
   okay=Subject && Subject.AttackCount>0;
   if(TestId==15 || TestId==16 || TestId==17 || TestId==19)okay=okay && p.health<100;
   if(TestId==18 || TestId==20) {
    int spores=0;let it=ThinkerIterator.Create('NRSpore');NRSpore s;
    while(s=NRSpore(it.Next()))if(s.bMISSILE && s.EndsAt>level.time && (TestId!=18 || s.Seeker && s.tracer==p))spores++;
    okay=okay && spores>=(TestId==20?3:1);
   }
  } else if(TestId==21) {
   okay=h.InternalSwaps==1 && abs(NRDirector.Delta(SavedYaw,p.Angle))<.1 && abs(p.Pitch-17)<.1 && (p.Pos.XY-h.Seams[PillarSeam].Destination.XY).Length()<160;
  }
  detail=detail .. String.Format("health=%d tic=%d phase=%d swaps=%d blocked=%d mutations=%d stair=%d",p.health,level.time,Subject?Subject.Phase:-1,h.InternalSwaps,h.Blocked,h.Mutations,StairStage);
  Receipt("check",okay,detail);
 }
 override void NetworkProcess(ConsoleEvent e) {
  if(e.Name!="nr_fixture")return;
  if(e.Args[0]==0) {TestId++;Setup();}
  else if(e.Args[0]==1)Verify();
  else if(e.Args[0]==2)Setup();
  else if(e.Args[0]==3) {TestId=21;PillarSeam++;Setup();}
  else if(e.Args[0]==4) {TestId=22;Setup();}
 }
 override void WorldTick() {
  if(!Climbing || !players[0].mo)return;
  let p=players[0].mo;Vector3 goal;
  switch(StairStage) {
   case 0:goal=(12160,800,160);break;case 1:goal=(12864,800,160);break;
   case 2:goal=(12864,96,320);break;case 3:goal=(12160,96,320);break;
   case 4:goal=(12160,800,480);break;default:goal=(12352,800,480);break;
  }
  Vector2 d=goal.XY-p.Pos.XY;double length=d.Length();
  if(length<7 && abs(p.Pos.Z-goal.Z)<2) {
   StairStage++;p.Vel=(0,0,p.Vel.Z);
   Console.Printf("NRSTAIR stage=%d z=%.4f tic=%d",StairStage,p.Pos.Z,level.time);
   if(StairStage==6) {Climbing=false;Receipt("climb_done",true);}
   return;
  }
  if(length>0) {p.Angle=atan2(d.Y,d.X);p.Vel=(4*d.X/length,4*d.Y/length,p.Vel.Z);}
 }
}
