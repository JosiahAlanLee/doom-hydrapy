# Null Run / Threshold — integration checkpoint

This is a draft checkpoint requested by Josiah so another chat can combine its engine fixes with this work. Further engine edits are held at this snapshot. The opening/content/UI work is implemented and tested as described below; the new soundtrack has been written and validated, but has not been rendered, auditioned or connected to a live game.

## Source and ownership

- Repository: https://github.com/JosiahAlanLee/doom-hydrapy
- Branch: `codex/threshold-identity`.
- Render-PC worktree: `/home/echevarian/dev/shared/codex/doom-hydrapy-threshold`.
- Job, diagnostics and test logs: `/home/echevarian/dev/shared/codex/nullrun-threshold-20261031`.
- Starting commit: `2940845b3c00dd3c6f083dd18cfa2572bbe56e5b`, the previous native Argon campaign from PR8. PR8 is merged; observed main was `8a5485e4794cf6727c707f9b80e7f40cbdb03f1d` when this checkpoint was prepared. The branch was not rebased over the other chat's engine work.
- The renderer repair and clean-display interface are separate commits, followed by a content/UI checkpoint commit. Exact hashes are attached to the delivered copy and recorded in the job's `checkpoint-commits.json`.

Read `/home/echevarian/dev/AGENTS.md` and `shared/CLAIMS.md` before continuing. Use a separate owned worktree for integration. Preserve this worktree's committed snapshot, worker originals, older preview services, the user's Rack Pro instance and other agents' files. No messages have been sent to the other chat.

## Engine overlap: review these six files first

1. `doomgeneric/r_plane.c`: fixes a confirmed memory-corruption path. The original128-visplane allowance was exceeded while entering the new atrium; `R_CheckPlane` allocated without a bounds check. A recorded-input debugger reproduction reached a segfault in `R_StoreWallRange` after the visplane pointer was corrupted. The `DOOM_ROGUE` build now has a bounded2048-plane allowance; both `R_FindPlane` and `R_CheckPlane` check before allocation. Ordinary build allowance stays128. This is the first, independently selectable commit. Reproduction inputs/backtraces are in the job's `native-debug/`.
2. `doomgeneric/d_main.c`: `DOOM_CLEAN_HUD` requests full view size11 on its first display and suppresses the engine's old text HUD. Scope is the `DOOM_ROGUE` build and that explicit per-process option.
3. `doomgeneric/st_stuff.c`: hides the original status graphics for that option while retaining `ST_doPaletteStuff`. Skipping the whole status drawer initially produced a black world because palette updates were lost; the corrected path preserves them, including automap behavior. This and the previous file belong to the clean-display commit.
4. `client.py`: adds optional `clean_hud=False`, sets/clears the child environment explicitly, writes the view-size preference when enabled, and retains exit status/unexpected-response/log-tail details in engine failures. Existing direct Doom callers keep the default display. This is included with the clean-display commit.
5. `doomgeneric/rogue_ai.c`: registers Latchwing and Relay Choir, private actor definitions and the slow Relay projectile info. These changes belong to the content commit.
6. `doomgeneric/rogue_argon.c`: implements the two new attacks, expands status reporting and uses a separate sprite bank for Latchwing. These changes belong to the content commit.

The new actor reservations matter when reconciling other enemy work:

| Family | Native type | Map flag | Runtime class | Sprite bank |
| --- | --- | --- | --- | --- |
| Latchwing |69 / MT_KNIGHT|7|15|CYBR|
| Relay Choir |71 / MT_PAIN|7|16|PAIN|
| Existing Calmor |69 / MT_KNIGHT|6|6|BOS2|

Latchwing intentionally shares an archetype number with Calmor but has a different signed variant flag. It renders through CYBR so Calmor's BOS2 art remains distinct. Tests now identify marked actors by type **and** flag; a new native regression verifies that a Calmor boss and Latchwing coexist. Do not classify bosses by native type alone.

Latchwing warns28tics, then dashes in a locked direction for at most24tics at14units/tic, using real wall collision and a single10damage contact hit. Sidestepping works. Relay Choir stays anchored, warns35tics and releases three slow native collision-tested spores at a7.5degree spread; they expire after six seconds. The four earlier Argon families retain their behaviors.

## Content and interface in the checkpoint

- An original authored opening floor replaces floor1 in the new identity mode: foyer, looping service atrium, Dry Stack landmark, pump/relay works, return route and optional cache. Geometry is fixed; seeds vary creature rolls, lighting trim and loot. Floors2–5 retain the existing procedural layouts with the new material/prop kit.
- The optional cache has a real native secret sector at cell(31,10). The native test walks into it and verifies one counted secret. All five floors are traversed with ordinary keys in a combat-free geometry fixture that retains solid props and pickups.
- Two new creature families, two variants each,24frames each; six128x128 wall textures, four64x64 flats and three environmental props. Contact sheets were visually reviewed. Final native-palette review of all newly integrated material/creature views is still pending.
- `rogue/threshold_assets.py` assembles the WAD adapters, preserves the source PNAMES/TEXTURE1 namespace, inserts generated materials and props, and moves one prop for adequate headroom. Props avoid authored routes and boss binding tiles. `campaign(..., identity=False)` retains the existing programmatic interface; the native player and browser entrypoint opt into the new identity.
- The native HUD replaces the old face/status bar with health, armour, selected weapon/ammo, kills, cache count, heading and floor. C opens credits from native play; the pause/death/end panels use the new typography. The browser shell also has a new layout, starts in raw view and hides the study/treatment selectors. Its final browser visual review is pending.
- Departure Mono1.500 by Helena Zhang is bundled unmodified with its full SIL OFL1.1 license and source/hash. `CREDITS.md`, asset licenses and original procedural sources preserve the contribution trail.

## DeepSeek delivery and music status

One worker completed: `20261030-230205-deepseek-nullrun-threshold-content`. Its original output is `/home/echevarian/dev/shared/deepseek/nullrun-threshold-20261031/`; the requester preserved it in `JOB/worker-copy-v1/`. Original generators and their checks are also in `assets/threshold/provenance/`. `runtime-manifest.json` hashes the integrated asset layout separately from the original worker manifest. Recorded API balance change was $0.13, measured to cent precision.

The original score is `assets/threshold/score.json`:144BPM,72bars,nine8bar patterns, six monophonic lanes, finite120seconds. Three40second acts are named `threshold-foyer`, `works-descent`, `return-escape`. Its SHA256 is `4585084d135754d79cef3eace708af7655ef3c643b90de2e24835044b9ca45de`.

Codex independently validated it with the frozen HydraPy validator, checked its120second chain and lack of overlapping lane gates; receipt: `JOB/independent-score-validation.json`. The worker's patch plan is an intention document. **No new Rack patch, audio take, soundtrack audition, final film or live score deployment exists for this experiment.** The earlier minimal ambient preset and its successful live check belong to PR8 and are separate work.

Important routing notes for whoever continues the music:

- Prefer two PVX instances (polyphonic lead/counterline and mono bass), lightweight oscillator/noise percussion, and restrained clean Spoon Bender. Keep Rack headless and measure actual load/xruns before deployment.
- PVX input2 is **external audio**, not velocity. Inputs are pitch0, gate1, external2, cutoff-CV3, resonance-CV4. Routing velocity pulses into external audio would introduce the wrong signal. Use a VCA for velocity.
- Gorgon bridge outputs velocity3, gates11 and pitch12 as six-channel poly signals. Individual gates are4–7,18,19. Sum poly audio explicitly where the next module is mono. Fundamental ADSR's gate is input4; VCA-1 is CV0/audio1.
- The frozen Gorgon launcher refuses unrelated running Rack instances; do not close the user's Rack Pro to bypass that check. The prior owned `nullrun-argon-pvx-20261031/campaign_service.py` is a working isolated-process example, but this new score would need Studio/CV readiness before Rack. Headless Rack needs its input kept open and fresh private state so a previous failed launch cannot create a hidden recovery dialog.
- Official weekend pricing is off-peak; the Claude-owned delegate still uses a daily-only guard. Do not edit that shared script. No further model workers are needed for this kit.

## Validation and remaining work

Native build passed. The new five-test enemy group and four-test content group passed separately; the checkpoint includes an additional Calmor/Latchwing coexistence test. The final full-suite result and exact commands are appended to the delivered handoff after it finishes. The first full run exposed two type-only test assumptions, corrected with flag-aware checks and the explicit native coexistence regression.

Early native HUD/pause/credits images were reviewed, and the clean display preserved real movement, firing and inventory state. New sprites/materials were reviewed in contact sheets. This is a **draft integration checkpoint**, not a final visual/audio acceptance.

Remaining: reconcile the other chat's engine edits; review all new assets in the native palette and final GPU window; visually verify browser/native panels; build and smoke-test the small score rig; verify the complete120second music under real game load; freeze a new runtime and deliver a playable build. Any requested videos stay on the render machine and go to `/media/echevarian/Expansion/TV Shows/Project Footage/` for Jellyfin. No new video has been made or copied to the Mac. The previous PR8 service had stopped after its window was closed; this checkpoint has not restarted it.

## Checkpoint verification receipt

Final native suite: **69 tests passed**, including the Calmor/Latchwing coexistence regression, real secret detection and a full five-floor key-driven traversal.

Command: `FREEDOOM_WAD=/path/to/freedoom2.wad python -m unittest test_rogue test_bosses test_gloamwood test_architecture test_strobe test_desktop_controls test_argon_native test_threshold_native test_threshold_content -v`. Log: `JOB/tests-checkpoint-final.log`.

Renderer repair commit: `7c54472e8a1bb020c008b6ef9223e26177734314`.

Clean-display interface commit: `c609fc614fce0e6b39627491200de9494821528c`.
