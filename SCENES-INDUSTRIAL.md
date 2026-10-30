# Industrial Doom treatments

The four treatment drafts and `doom_math_ops.py` arrived in Josiah's Downloads at 16:01 on 2026-10-30. Source metadata credits Argon and Codex; engine attribution remains id Software/doomgeneric, game data Freedoom. Codex preserved the inputs, recorded their SHA256s in `../pvx-industrial-20261030/new-doom-scenes-provenance.json`, repaired `Fn1` imports to `hydrapy.signals`, tested the copies and integrated them with the existing locked demo source.

| Minute | Treatment | 1080p p95, 180 measured frames |
|---|---|---:|
| 1 | Column melt and shear | 2.90 ms |
| 2 | Circular disk and HUD ring | 3.01 ms |
| 3 | Green/red vector edges | 2.89 ms |
| 4 | Red/cyan pseudo-depth relief | 2.99 ms |

Six-second GPU scene checks passed for all four; all four contact sheets were visually inspected. The combined live-performance patch imports, prewarms every scene shader and draws at 1080p with the frozen capture runtime. Timing includes the source engine. These are short checks, not final-video acceptance; the actual take must still be measured and reviewed.

Industrial `performance.py` derives kick/snare decay signals from the exact accepted note schedule, and beat phase from each composition's actual tempo. It uses a single locked Doom source shared by the four effects; it does not instantiate the standalone scene files' looped test engines. Demos switch at 0/60/120/180 seconds. The final scene stays for the short effect tail. A separate 1 Hz sync marker is added after the artistic effects.

The supplied mathematical labels describe visual inspirations. These operators are screen-space image effects: the edge map uses central differences rather than a full 3×3 Sobel kernel; color/viewport-based disparity is a pseudo-depth heuristic, not recovered game geometry; the tanh disk remap is not a proof of hyperbolic conformality. The sequential sine/cosine shear component is area-preserving in isolation, but the combined column melt/shear image warp is not asserted to preserve area. The column hash is inspired by Doom's wipe, not a port of its random table.

The newly supplied `doom_barnette_choreographer.py` was not integrated: this take explicitly performs Freedoom DEMO1–4, while that draft changes live gameplay input and introduces an unreviewed telemetry path. Its original remains untouched in Downloads.
