# Null Run 003 — two book demons as seeded encounters

Repetiel and Calmor are adapted from Josiah Alan-Lee's *Pseudomonarchia
Escalationum*. The source is the [Book III catalogue at the inspected commit](https://github.com/JosiahAlanLee/Codex-Intervallorum/blob/b789e03f30034bc8403f8a40aaf83842885aaad5/books/03_escalationum/manuscript/catalogue.json).
Their forms and bindings supply the themes; the combat rules below are new game
interpretations. No book artwork or apparatus drawing implementation is copied.
`rogue/bosses.py` retains a summary of each entry's critical actual effect with
the appearance and binding, rather than turning the catalogue into an unqualified
operating manual. It is an adaptation, not a claim that the book describes combat.

## Campaign and practice

Both appear once per five-floor campaign, on floors three and five. A seed-driven
shuffle selects their order, which repeats for the same seed. Health varies within
bounded ranges. Each encounter gets a reachable binding tile, preferably inside
a two-cell side alcove for cover, plus nearby supplies. The exit stays locked
while the boss is alive; binding opens a damage window, not an immediate victory.

In the browser, choose a **NEXT RUN** binding study and press **RETRY** or **NEW
RUN** to start beside that demon's ring. A study contains only that boss, with a
shotgun, shells and armor at the start; take a step to pick up the supplies. It
uses the same native boss mechanics, then ends at the ordinary exit. Studies
are separate from a campaign save and reset inventory like any new run.

| Demon | Book motif | Game binding | Custom attack |
| --- | --- | --- | --- |
| Repetiel | Two mouths on a return tube; repeated intake | On the marked ring, press F, release, then press F again. Holding F counts once. | A shot followed 18 tics later by an echo retaining its original direction and vertical velocity |
| Calmor | A softly lined bell demanding a calmer account | Stay on the ring without moving or firing for two seconds. Movement, knockback or attack input interrupts the charge. | One aimed shot while the player is quiet; a three-shot spread while the player is firing |

Each completed binding exposes the boss for eight seconds of simulation time.
Pausing the browser game also pauses that window. When it closes, repeat the
binding. The HUD shows name, health, shield phase, binding progress and remaining
exposure time. Original generated pixel sprites distinguish the return tube and
lined bell; native seal flats mark the ritual locations. These are billboard
sprites and modified Doom archetype state machines, not new 3D creature models.

## Native boundaries

Classes 5/6 use marked THING options. `rogue_boss.c` owns one encounter context per
level, reset before level memory is freed. It validates a tagged seal sector,
observes native use/attack/movement, gates incoming boss damage and level exits,
and schedules Repetiel's echo. A malformed external PWAD without a seal leaves
the boss damageable instead of trapping the player. Campaign generation places
exactly one marked boss on each encounter floor.

Boss state is additive JSON in `STATE`. There is no API to set health, teleport,
force a binding or grant victory. Native damage tests use actual weapons and
explicit test-only BFG/invulnerability pickups; production studies give shotgun
gear. Ordinary maps outside roguelike mode retain their original monster and
exit behavior. The full sprite and flat namespaces preserve unchanged Freedoom
assets, while adding original boss art/seals. Asset hashes remain in manifests;
keep Freedoom's license and credits with distributed WADs.

## Validation and limits

`FREEDOOM_WAD=/path/to/freedoom2.wad python -m unittest -v test_rogue test_bosses`
checks the base game plus seed selection, reachable bindings, isolated studies,
holding/repeating use, stillness and attack resets, vulnerability expiry, real
shield impacts, weapon-caused defeat, exit locks/releases, exact echo direction,
Calmor's panic spread and ordinary-map isolation. Existing `test_ipc.py` covers
the deterministic demo path. Test fixtures are not combat-balance signoff.

Audio, mouse look, perks and save/resume remain future work. Creature assets from
the user's Gloamwood project have not been ported: design notes are located, but
the actual world/addon is still in a separate conversation or on the tablet.
DeepSeek's separate modular art kit was generated from a generic brief, then
reproduced and visually reviewed independently. Its 24 combinations and four
pose studies are not integrated into these encounters. Book/game source and
Minecraft files were not included in that API job.
