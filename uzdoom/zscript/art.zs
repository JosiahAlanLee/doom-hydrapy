// SPDX-License-Identifier: GPL-3.0-or-later
// Portable Argon signal concept; native occupancy-safe exhibition by Codex.
class NRSignal : Actor {
 Default { +NOGRAVITY }
 States { Spawn: NRMA A -1; Stop; }
}
class NRArtConsole : Actor {
 int ArtState; bool Reach;
 Default { Radius 20; Height 48; +SOLID }
 States { Spawn: NACN A -1; Stop; }
 bool InReach(Actor p) {
  return p && p.health>0 && Distance2D(p)<=96 && abs(Pos.Z-p.Pos.Z)<=24 &&
   abs(NRDirector.Delta(p.Angle,atan2(Pos.Y-p.Pos.Y,Pos.X-p.Pos.X)))<=65 && p.CheckSight(self);
 }
 void Tune() {
  ArtState=(ArtState+1)%3;frame=ArtState;
  let it=ThinkerIterator.Create('NRSignal');NRSignal a;
  while(a=NRSignal(it.Next()))if(a.args[0]==args[0])a.frame=ArtState;
 }
 clearscope String Hint() {return String.Format("F / TUNE ARCHIVE %d / FORM %d OF 3",args[0]+1,ArtState+1);}
}
