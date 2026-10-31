// SPDX-License-Identifier: GPL-3.0-or-later
// Test-only instrumentation: retain both authored bosses and their real seals.
class NRBossEncounterFixture : StaticEventHandler {
 override void OnRegister() {SetOrder(-100);}
 void Place(Actor p,Vector3 q,double yaw=0) {
  p.SetOrigin(q,false);p.FindFloorCeiling();p.ClearInterpolation();p.Vel=(0,0,0);p.Angle=yaw;p.Pitch=0;
 }
 override void NetworkProcess(ConsoleEvent e) {
  if(e.Name!="nr_boss_encounter")return;
  let h=NRDirector.Get();let p=players[0].mo;if(!h || !p || h.Bosses.Size()!=2)return;
  int code=e.Args[0];bool okay=true;String detail="";
  if(code==0) {
   for(int i=0;i<h.Mobs.Size();i++)if(h.Mobs[i] && h.Mobs[i].BossIndex<0)h.Mobs[i].Destroy();
   p.health=1000;p.player.health=1000;
   for(int i=0;i<2;i++) {
    let b=h.Bosses[i];b.Mob.Cooldown=level.time+100000;b.Mob.Awake=false;
    okay=okay && b.MaxHP<=240 && b.MaxHP>=140 && b.Mob.Pos==b.Home;
   }
   okay=okay && h.Bosses[0].Kind==5 && h.Bosses[1].Kind==9;
  } else if(code==1 || code==3) {
   let b=h.Bosses[code==1?0:1];Vector2 d=b.Home.XY-b.Seal.XY;
   Place(p,b.Seal,atan2(d.Y,d.X));
  } else if(code==2) {
   let b=h.Bosses[1];int before=b.Mob.health;b.Mob.DamageMobj(p,p,20,'NRTest');
   okay=b.Proof && before-b.Mob.health==12;
   detail=String.Format("shield_hit=%d proof=%s",before-b.Mob.health,b.Proof?"true":"false");
  } else if(code==4) {
   let b=h.Bosses[0];b.OpenUntil=0;int before=b.Mob.health;b.Mob.DamageMobj(p,p,20,'NRTest');int shield=before-b.Mob.health;
   b.Expose();before=b.Mob.health;b.Mob.DamageMobj(p,p,20,'NRTest');int opened=before-b.Mob.health;
   okay=shield==12 && opened==30;
   detail=String.Format("sealed=%d exposed=%d from20",shield,opened);
  } else if(code==5) {
   let b=h.Bosses[0];Place(p,(576,3520,0));
   Place(b.Mob,(1597,1900,0));b.OpenUntil=0;b.StaggerUntil=0;b.Mob.Awake=true;
  } else if(code==6) {
   let b=h.Bosses[0];b.OpenUntil=0;int hits=0;
   while(!b.Bound() && hits<30) {b.Mob.DamageMobj(p,p,20,'NRTest');hits++;}
   okay=b.Bound() && hits<=20;detail=String.Format("ordinary_shield_hits_to_finish=%d",hits);
  } else if(code==7) {
   int seals=0,badges=0;let it=ThinkerIterator.Create('NRSealMarker');
   while(it.Next())seals++;it=ThinkerIterator.Create('NRBossBadge');while(it.Next())badges++;
   okay=seals==2 && badges==2;detail=String.Format("seals=%d badges=%d",seals,badges);
  }
  Console.Printf("NRRECEIPT {\"fixture\":\"encounter\",\"case\":%d,\"ok\":%s,\"detail\":\"%s\"}",code,okay?"true":"false",detail);
 }
}
