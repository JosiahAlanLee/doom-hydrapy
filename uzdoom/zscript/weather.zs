// SPDX-License-Identifier: GPL-3.0-or-later
// Physical distance fog plus a bounded, cosmetic native particle field.
class NRWeather : Object {
 Array<int> Sectors; int Density,Visibility,Emitted; uint WeatherRng; Color Tint;
 bool Enabled; TextureID Mist;
 play void Load() {
  int id=Wads.FindLump(String.Format("NRWX%02d",level.levelnum));if(id<0)return;
  Array<String> lines;Wads.ReadLump(id).Split(lines,"\n",TOK_SKIPEMPTY);if(lines.Size()!=3)return;
  Array<String> head,col,ids;lines[0].Split(head," ",TOK_SKIPEMPTY);lines[1].Split(col," ",TOK_SKIPEMPTY);lines[2].Split(ids," ",TOK_SKIPEMPTY);
  if(head.Size()!=3 || col.Size()!=3 || ids.Size()>4096)return;
  Density=head[0].ToInt();Visibility=head[1].ToInt();WeatherRng=uint(head[2].ToDouble());
  if(Density<1 || Density>256 || Visibility<128 || Visibility>1024)return;
  Tint=Color(clamp(col[0].ToInt(),0,255),clamp(col[1].ToInt(),0,255),clamp(col[2].ToInt(),0,255));
  for(int i=0;i<ids.Size();i++){int n=ids[i].ToInt();if(n<0 || n>=level.Sectors.Size()){Sectors.Clear();return;}Sectors.Push(n);}
  Mist=TexMan.CheckForTexture("NRMIST",TexMan.Type_Any);SetEnabled(true);
 }
 clearscope bool Contains(Sector s) {
  if(!Enabled || !s)return false;
  for(int i=0;i<Sectors.Size();i++)if(Sectors[i]==s.Index())return true;
  return false;
 }
 play void SetEnabled(bool on) {
  Enabled=on && Sectors.Size()>0;
  for(int i=0;i<Sectors.Size();i++) {let s=level.Sectors[Sectors[i]];s.SetFade(Enabled?Tint:0);s.SetFogDensity(Enabled?Density:0);}
 }
 play uint Next() {WeatherRng=WeatherRng*1664525+1013904223;return WeatherRng;}
 play void Tick(Actor p) {
  if(!Enabled || !p || p.health<=0 || level.time%3 || !Contains(p.CurSector))return;
  // At most 2 * ceil(105/3) = 70 living particles, independent of frame rate.
  // Private PRNG avoids perturbing the game's combat random stream.
  for(int i=0;i<2;i++) {
   double a=Next()%360,r=48+Next()%464;
   Vector2 xy=p.Pos.XY+(cos(a)*r,sin(a)*r);let s=level.PointInSector(xy);
   if(!Contains(s) || !level.IsPointInLevel((xy.X,xy.Y,p.Pos.Z+24)))continue;
   double bottom=s.FloorPlane.ZatPoint(xy)+12,top=min(s.CeilingPlane.ZatPoint(xy)-12,bottom+144);
   if(top<=bottom)continue;
   double z=bottom+(Next()%1000)/1000.*(top-bottom);
   double windX=.20+.04*sin(level.time*.5),windY=.08*cos(level.time*.31);
   p.A_SpawnParticleEx(Color(170,184,194),Mist,STYLE_Translucent,SPF_FADE_IN_OUT|SPF_NODYNAMICLIGHTING,105,56,0,
    xy.X-p.Pos.X,xy.Y-p.Pos.Y,z-p.Pos.Z,windX,windY,.025,0,0,0,.14,.004,.05,0,0,0,.004);
   Emitted++;
  }
 }
 clearscope String JSON(Actor p) {
  return String.Format("{\"enabled\":%s,\"in_fog\":%s,\"density\":%d,\"visibility_range\":%d,\"sectors\":%d,\"emitted\":%d,\"particle_bound\":70}",Enabled?"true":"false",p && Contains(p.CurSector)?"true":"false",Density,Visibility,Sectors.Size(),Emitted);
 }
}
