# Vertical-layout design tables

Proposal only. No engine sectors, collision or navigation are changed by this kit.

Conversion: 1 m = 64 Doom units; native map tiles are 128 units. Native step height is 16 units (0.25 m); native player clearance/headroom is 96 units (1.5 m); the mesh stair uses 12-unit risers.

## ASHBELL FOUNDRY (`ashbell_foundry`)

Height: **15.0 m** (960 Doom units), 6 walkable levels at 3.0 m pitch.

| Level | z (m) | z (Doom u) |
| --- | --- | --- |
| F0 casting pit | 0.0 | 0 |
| F1 maintenance gantry | 3.0 | 192 |
| F2 furnace throat | 6.0 | 384 |
| F3 lift landing / bell waist | 9.0 | 576 |
| F4 bell shoulder | 12.0 | 768 |
| F5 crown gallery / summit | 15.0 | 960 |

**Landmark:** The Ninth Bell - The cracked ninth bell hangs in the central casting shaft between F3 and F5. Its crown gimbal is the F4 sightline; the cage is the F3 landmark. The bell is visible from the F0 pit through an open chain well, but cannot be reached by jumping.

**Lower route:** F0 sand pit -> west casting aisle -> furnace chest cover -> two-flight stair to F1. The F0 ceiling is open to the chain well above the sand bed; the player sees the bell but the route is the stair.

**Middle route:** F1 maintenance gantry -> chain-lift landing -> F2 furnace throat -> stair to F3. The F2 gantry crosses the flue on a 2.0 m bridge with guardrails; the lift cage passes beside it, not through it.

**Upper route:** F3 lift landing -> F4 crown gimbal gallery -> F5 crown gallery. The last storey is a switchback stair around the bell crown; the summit is a real 15.0 m floor overlooking the whole shaft.

**Stair alternative:** Every storey has a complete two-flight stair: 8 risers at 0.1875 m (12 Doom units), a 1.8 m landing, then 8 more risers. The stair is never blocked by the lift.

**Lift alternative:** The chain lift is an explicit second route: a static cage mesh proposal plus a chain-and-counterweight landmark. In the first pass it is a fixed platform at each landing, not a moving lift; the stair is the guaranteed route.

**Fall recovery:** The central casting shaft is open from F1 to F4. A dropped object or player lands on the F0 sand bed, which is a 0.35 m soft mound, not a kill plane. Return: From the F0 sand bed, the west aisle leads back to the F0 stair in under 20 m. No one-way drop is on the required route.

**Safe spawn:** A sealed sand-pit entry behind the furnace chest, with two exits and the bell visible overhead as a bearing. Clearance: at least 6 native 128-unit tiles (12 m at 64 u/m) from the first encounter.

**Return path:** Every level carries the same bearings: wall 07 bell/landmark is on the shaft side, wall 08 lift/cage is on the stair side. From any gallery the stair head is visible within one room length.

**Arena/perch spacing:** arena [8.0, 8.0] m, perch spacing [3.5, 5.0] m, headroom 1.5 m.

**Room-over-room:**
- F0, F1: F1 maintenance gantries bridge over the F0 sand pit and furnace aisle.
- F1, F2: F2 furnace throat sits above the F1 gantry; its flue passes through the floor beside the stair.
- F3, F4, F5: The bell shaft is a true three-storey void; F4 and F5 walkable galleries overhang the F3 landing.

**Tower proof:** 15.0 m physical gain; two 1.5 m stair flights plus a 1.5 m landing per storey; the chain lift is a second independent route from F0 to F5. Not faked by: no single tall ceiling, no camera tilt, no non-walkable decorative gantry; every named level has a walkable floor.

**First-pass constraints:** unavoidable jumps=False, required gap=0.0 m, precision platforming=False, unseen hits=False.

**Mesh collision needs:** stair steps as walkable step surfaces; landing deck as walkable platform; guardrails as 1.1 m barriers; bell/cage as overhead and shell proxies.

## BONEGLASS CONSERVATORY (`boneglass_conservatory`)

Height: **15.0 m** (960 Doom units), 6 walkable levels at 3.0 m pitch.

| Level | z (m) | z (Doom u) |
| --- | --- | --- |
| F0 peat floor | 0.0 | 0 |
| F1 nursery beds | 3.0 | 192 |
| F2 watering gantry | 6.0 | 384 |
| F3 root cage | 9.0 | 576 |
| F4 canopy walk | 12.0 | 768 |
| F5 lantern roof / summit | 15.0 | 960 |

**Landmark:** The Root Cage - The empty root cage hangs through the atrium from the F4 canopy to the F3 landing, suspended over a black void. The descending canopy above it is the F4-F5 ceiling; the growth lamps are the safe bearings.

**Lower route:** F0 peat floor -> dry gravel aisle -> growth chamber cover -> root stair to F1. The F0 ceiling is the open nursery floor above; beds are visible through root gaps, but the route is the stair.

**Middle route:** F1 nursery beds -> watering gantry arch -> F2 gantry walk -> root stair to F3. The F2 gantry crosses over the beds on a 2.0 m bridge with rails.

**Upper route:** F3 root cage landing -> F4 canopy walk -> F5 lantern roof. The last flight is a switchback through hanging roots; the summit is a real 15.0 m glasshouse lantern floor.

**Stair alternative:** A continuous root-wrapped spiral stair uses the same 8-riser flights and 1.8 m landings; the root texture is cosmetic over the shared stair geometry.

**Lift alternative:** A counterweighted watering gantry platform links F1, F2 and F4. It is a slow open platform, not a jump; the stair remains the guaranteed route. Delivered as a static landing proposal; moving platform behaviour is unimplemented.

**Fall recovery:** The glasshouse atrium is open from F1 to F4. Soft peat beds at F0 and planter shelves at F1/F2 catch a fall. Return: F0 peat beds connect to the root stair within 18 m; no one-way drop is required to progress.

**Safe spawn:** A dry gravel entry between two peat beds, under the first planter shelf, with the root stair visible to the left and a growth chamber as cover. Clearance: at least 6 native tiles (12 m at 64 u/m) from the first encounter.

**Return path:** The pale growth lamps and the descending root curtain are visible from every level. Wall 07 (root cage) faces the atrium; wall 08 (canopy) faces the stair. The stair head is always within one room.

**Arena/perch spacing:** arena [7.0, 7.0] m, perch spacing [3.0, 4.5] m, headroom 1.5 m.

**Room-over-room:**
- F0, F1: F1 nursery beds sit over the F0 peat floor; roots and glass panels show the room above.
- F1, F2: The F2 watering gantry crosses over the F1 beds; roses and drip lines hang into the room below.
- F3, F4, F5: The root cage void is a three-storey open volume; the F4 canopy walk and F5 lantern roof overhang it.

**Tower proof:** 15.0 m physical gain; a spiral root stair from F0 to F5 plus a counterweight gantry from F1 to F4; the two routes are independent after F1. Not faked by: the glasshouse atrium is a real multi-storey void; every named level has a walkable bed, walk or gallery.

**First-pass constraints:** unavoidable jumps=False, required gap=0.0 m, precision platforming=False, unseen hits=False.

**Mesh collision needs:** root stair as walkable steps; gantry beam as overhead clearance; planter and cage as solid proxies; growth chambers as solid cover.

## SKYHOTEL SERVICE WELL (`skyhotel_service_well`)

Height: **18.0 m** (1152 Doom units), 7 walkable levels at 3.0 m pitch.

| Level | z (m) | z (Doom u) |
| --- | --- | --- |
| B1 laundry / service basement | 0.0 | 0 |
| F1 linen service | 3.0 | 192 |
| F2 service well | 6.0 | 384 |
| F3 first guest balcony | 9.0 | 576 |
| F4 second guest balcony | 12.0 | 768 |
| F5 third guest balcony | 15.0 | 960 |
| F6 observation deck / summit | 18.0 | 1152 |

**Landmark:** The 33rd Floor Lift - The brass service lift opens on an amber gap at F2 and F3, with an impossible indicator mark. The F3 landing faces the atrium cutaway; the F6 observation deck looks down the whole 18 m well.

**Lower route:** B1 laundry -> service corridor -> dumbwaiter winch cover -> fire stair to F1. The laundry net and linen chute shelves are visible below the open service well but the route is the stair.

**Middle route:** F1 linen service -> F2 service well -> service lift landing -> F3 first guest balcony. The F2 landing is a real floor around the open well, with guardrails on every unrailed edge.

**Upper route:** F3 -> F4 -> F5 guest balconies are staggered around the atrium; the fire stair switchbacks at the service core and reaches F6. The observation deck is a real 18.0 m floor with a guarded view down the well.

**Stair alternative:** A fire stair with the same two-flight rhythm runs the full height. Its landings are offset around the service core, so it reads as a different spatial experience from the straight foundry stair.

**Lift alternative:** The service lift is an explicit second route from B1 to F6. The delivered mesh is a static car/shaft proposal; the moving car and call logic are unimplemented, so the fire stair is guaranteed.

**Fall recovery:** The service atrium is open from F1 to F6. Guest balconies are set back 2.0 m from the void edge and have 1.1 m guardrails. Return: The B1 laundry net connects to the fire stair within 22 m; no required route uses an unguarded drop.

**Safe spawn:** A laundry entry behind a linen cart, with the fire stair visible through a service door and the lift indicator as a second bearing. Clearance: at least 6 native tiles (12 m at 64 u/m) from the first encounter.

**Return path:** Amber floor ticks and the repeated room-number paddle mark the fire stair on every balcony. Wall 07 (lift) faces the service core; wall 08 (atrium) faces the void. The stair is never more than one balcony bay away.

**Arena/perch spacing:** arena [9.0, 7.0] m, perch spacing [3.0, 4.0] m, headroom 1.5 m.

**Room-over-room:**
- B1, F1: F1 linen service rooms sit directly over B1 laundry and the chute shelves.
- F1, F2: F2 service-well roof covers the F1 linen store while the atrium opens beside it.
- F3, F4, F5: Staggered guest balconies overhang one another around the void, each a real 3.0 m floor pitch; F6 observation deck caps the well.

**Tower proof:** 18.0 m physical gain; a fire stair from B1 to F6 plus a service lift from B1 to F6; both are independent. Guest balconies are stacked at real 3.0 m floor pitches around the atrium void.. Not faked by: no tall painted atrium; the service well is an open shaft with walkable balconies at each level and real room-over-room floors.

**First-pass constraints:** unavoidable jumps=False, required gap=0.0 m, precision platforming=False, unseen hits=False.

**Mesh collision needs:** fire stair as walkable steps; balcony floor at 0.16 m above level; guardrails as 1.1 m barriers; lift car shell and dumbwaiter as solid proxies.

## Honest limits

- These are design tables, not map geometry. Codex must build sectors, steps, lifts, collision and navigation.
- The lift alternatives are static landmark meshes in this kit; moving lift and call logic are unimplemented.
- Fall damage, enemy placement, line-of-fire and performance are engine-owned and untested here.
