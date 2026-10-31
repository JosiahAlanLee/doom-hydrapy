# Null Run 004 — Gloamwood creatures and two more book demons

This iteration adds original Doom interpretations of the user's Hollow and
Stone ReDead, plus Probator and Jurisiel from *Pseudomonarchia Escalationum*.
They use new procedural billboard sprites, native combat, collision and sight.
The Minecraft geometry, textures and sounds were unavailable and are not ported.
Recovered add-on README descriptions supply the two creatures' encounter rules.

## The Hollow

A motionless split tree holds a pale face inside its chest, with bark ribs,
finger roots and red fibres. Seeing it wakes it. It freezes while its centre is
inside the player's 90-degree view and has native line of sight, within 1536
map units. Solid walls block that gaze. When unwatched, it folds into a low
crawl and follows the player with melee attacks. Looking back freezes its
current deployment/stride/strike pose as well as its movement and attack timer.
It can be damaged normally, including while frozen. Its collision stays tall
while crawling; this is not a crouching collision exploit.

## Stone ReDead

A gaunt figure wears a cracked stone mask. Within sight and 448 map units, it
raises its mask for a 0.8-second warning, then lunges. Breaking sight or leaving
range before the warning ends avoids the brief movement stun. At close range,
its lunge can grip the player. This is a bounded close-range tether with slowed
movement, not the Bedrock model's attached follow animation.

Turning, firing, use, pause and the automap remain available. Hold **F** for
about 0.7 seconds or hurt it to break free. A grip lasts at most four seconds,
with four damage per second through normal Doom damage/armor rules; its first
damage occurs after one second. Escape/hurt staggers the attacker. Releases
give three seconds of grip immunity, and each shriek has a six-second cooldown.
Only one creature may hold the player. Distance, lost sight, death, removal and
level reset also release the grip. Pausing freezes its simulation clock.

## Probator and Jurisiel

The campaign now selects two different demons from a four-demon bank for floors
three and five. All four have individual binding studies. Source forms/bindings
and the critical actual effects are paraphrased in `rogue/bosses.py`, with a
pinned book source link. These combat rules are new interpretations:

| Demon | Binding | Attack |
| --- | --- | --- |
| Probator | Hit the sealed shield to record proof, then stand on the ring and tap F | A closely spaced projectile pair |
| Jurisiel | Enter the amber A ring, then cross into the cyan B ring | A diverging pair framing a passage |

Holding F before Probator records proof does not acknowledge it automatically.
Jurisiel requires A before B; remaining on B does not reopen the shield after
expiry. Both use the existing eight-second damage windows and defeat-to-exit
rule. A missing binding marker in an external PWAD leaves a boss damageable.

## Play and implementation

Choose a **NEXT RUN** study, then **RETRY**. Hollow/ReDead studies are clear
galleries with one creature, cover, and shotgun supplies at the start. Take a
step to pick them up. Campaigns add one Hollow per floor and one Stone ReDead
on floors two through five, beyond the safe starting area.

Existing class/roll bits are preserved. Class marker 7 plus one of four unused
native actor types identifies the new classes, leaving THING options signed
16-bit compatible. Per-instance state is compiled only into the IPC build.
Sight/collision are native; read-only status queries expose pose/effect progress.
Map-only PWADs without the extra art safely fall back to native sprite frames.
The full art namespace contains original standing/crawl/warning/grip/death poses
and new seal flats. Ordinary maps outside roguelike mode retain base behavior.

### Material refinement

The creature art now uses worn bark, bone, stone, cloth and tarnished metal,
with broad shaded planes, narrow bevels and sparse seeded chips. Five shades
per source material keep generation bounded and preserve large readable shapes
under the green-vector filter. All six Gloamwood/book forms share this finish.
ReDead's grip pose crouches its mask near the first-person camera's height.
Sprite dimensions, frame assignments and native movement/combat code are unchanged.

Run the native checks with `FREEDOOM_WAD=/path/to/freedoom2.wad python -m unittest
-v test_rogue test_bosses test_gloamwood`. Tests use real keys, weapon hits,
movement, sight and exit transitions; they do not set health or force bindings.
Browser audio, mouse look and save/resume remain outside this iteration.
