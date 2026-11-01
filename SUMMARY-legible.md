# Doom legibility, 2026-10-30
Branch: codex/doom-legible, based on codex/doom-poly-take; no push.
Terminal: 240 columns, 320 in HUD bands; monotonic 4x6 density ramp, unsharp contrast, source hue and 32% image bed.
Print: 480x300 fine dot screen with 62% image bed; source remains nearest-neighbour expanded from Doom raster.
Reuse: import legible_ops; source.doomLegibleAscii(240) / source.doomLegiblePrint(); performance.py and standalone scenes updated.
Full-demo edge correlation, old -> new: terminal 0.3371 -> 0.7391; print 0.8468 -> 0.8821.
Metric: luminance edges after 4x reduction + sigma 1.5 blur, one sample/second over all 240 seconds.
1080p livecost, 180 frames after 30 warmups, engine+upload+GPU finish: terminal p95 2.30 ms; print 2.27 ms.
Offline render uses original recorded slots + tic trace, same scene/demo schedule; original scan/feedback frames retained.
Audio WAV unchanged; encoded AAC payload identical; original sync-square region retained, no timing shift.
Delivery: ../doom-hydrapy-20261030/take/doom-freedoom-poly-legible-1080p.mp4; SHA256SUMS-legible and doom-legible-before-after.jpg.
Verification: doom-legible-verification.json, doom-legible-livecost.json; analysis-legible/tic-checks.json.
Looked at corridor, enemy close-up, door, pickups and HUD comparisons plus final MP4 terminal/print frames; no listening review.
Reproduce: make -C doomgeneric -f Makefile.ipc; hydrapy Python render_legible.py then benchmark_legible.py (no active captures).
