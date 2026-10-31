# Seven tiers into the abyss

The campaign descends through seven office regions. Each tier contains two
distinct handoff demons from Josiah Alan-Lee's *Pseudomonarchia Escalationum*.
Both must be bound and defeated before that tier's exit opens. Death ends the
run; health, weapons and ammunition carry between tiers. The seventh exit wins.

| Tier | Office | First demon | Second demon |
| --- | --- | --- | --- |
| 1 | Foras | Repetiel (01) | Scriptorax (04) |
| 2 | Vassago | Calmor (12) | Redacth (14) |
| 3 | Gremory | Promissor (23) | Consenth (24) |
| 4 | Bune | Jurisiel (34) | Margor (35) |
| 5 | Orobas | Absentiel (45) | Exceptor (46) |
| 6 | Paimon | Choraz (15) | Posthum (56) |
| 7 | Bael | Probator (16) | Velaroth (26) |

This allocation belongs to the game. Every selected handoff touches its tier's
office in the book's graph. It retains the four previously implemented demons
and leaves seven handoff demons for later encounters: Solaciel, Novaroth,
Culpax, Instantor, Severion, Viridon and Quarteroth. Office spirits identify
the regions; the fourteen handoff demons are the current boss encounters.

## Implemented encounter families

Each demon has its own actor, shield state, binding rings, health and death
state. The current art and combat use four shared families. Fourteen unique
visual designs and fourteen bespoke attack/binding systems remain future work.
The newly assigned combat rules are game interpretations of the book.

| Binding family | Demons using it | Player action |
| --- | --- | --- |
| Repetition | Repetiel, Promissor, Margor, Exceptor | On its ring, tap F twice, releasing between taps. |
| Quiet | Calmor, Choraz, Velaroth | Remain still on its ring without firing for two seconds. |
| Proof | Scriptorax, Absentiel, Probator | Hit its sealed shield, then stand on its ring and tap F. |
| Passage | Redacth, Consenth, Jurisiel, Posthum | Enter its amber A ring, then cross into its cyan B ring. |

Each successful binding exposes that demon for eight seconds. The rings affect
only their assigned demon, including when two encounters use the same family.
The campaign HUD shows both demons and the currently selected binding rule.
The existing Argon and Gloamwood enemies remain in the ordinary encounter pool.
The Threshold edition adds Latchwing and Relay Choir, its authored opening,
materials, props, Departure Mono typography and custom HUD. Its original eight
opening encounters remain; Repetiel and Scriptorax occupy additional free
route tiles with their own bindings and supplies. Tiers five through seven
combine all six Argon/Threshold families. See [THRESHOLD_INTEGRATION.md](THRESHOLD_INTEGRATION.md).

`rogue/demons.json` retains each selected demon's original appearance, binding
and critical `actual_effect` together. It records the catalogue URL, revision
and blob hash. Source: [book catalogue at cbd7012](https://github.com/JosiahAlanLee/Codex-Intervallorum/blob/cbd7012714197c638931b500922936727efdf64f/books/03_escalationum/manuscript/catalogue.json).
`rogue/bosses.py` holds the allocation and shared combat-family mapping.

## Native implementation

`RBOSSES` is bounded, map-scoped PWAD metadata matching each identity to an
ordinary map actor by class and spawn position. Each encounter owns separate
sector tags; malformed metadata falls back to the existing family behavior.
No runtime teleport, damage, spawn or gate-unlock command is added.

Campaign progression opts out of Doom II's MAP06 narrative finale and reaches
MAP07 normally. Ordinary Doom retains its finale. The manifest format is now
`doom-rogue-6`; identical seeds from older formats describe different runs.

## Play and verify

Use the native Studio patch `rogue/campaign_live.py` as described in
[ARGON_CAMPAIGN.md](ARGON_CAMPAIGN.md). Mouse movement turns, left click fires,
right click uses, and Escape releases the pointer and pauses. The click that
captures the pointer does not fire. Brackets adjust and save sensitivity.
The existing lightweight Rack ambience preset is unchanged.

Build and run the complete checks with the Freedoom 2 IWAD:

```sh
make -C doomgeneric -f Makefile.ipc -j4
FREEDOOM_WAD=/absolute/path/to/freedoom2.wad python -m unittest -v \
  test_rogue test_bosses test_gloamwood test_architecture test_strobe \
  test_desktop_controls test_argon_native test_native_playability \
  test_threshold_native test_threshold_content
FREEDOOM_WAD=/absolute/path/to/freedoom2.wad python test_ipc.py
```

The Studio replacement tests additionally need HydraPy importable. They use its
real `ResourceStage` with fixture devices to check successful replacement,
renderer-validation failure and activation rollback. They also check that a
fresh, hardware-disarmed Studio activates software play on its first live
frame after validation. Native engine tests
exercise all seven pairs, two independent demons sharing one family, real
weapon damage, the locked exit after one death, and traversal through MAP06 to
victory on MAP07. The route fixture removes combat actors and pickups so the
progression check is independent of combat balance. Target GPU, physical input
and audio performance still require a live run on the render PC.
