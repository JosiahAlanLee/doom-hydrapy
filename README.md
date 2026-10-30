# Doom → HydraPy (local prototype, GPL-2.0-or-later)

Real Doom engine, not a clone: id Software's released source, maintained through
[doomgeneric](https://github.com/ozkl/doomgeneric). The supplied brief's ozkriff URL
was unavailable. See LICENSE, README.TXT and README.upstream.md for upstream credits.
Game assets are from [Freedoom 0.13.0](https://github.com/freedoom/freedoom/releases/tag/v0.13.0),
BSD licensed. No commercial WAD or original Doom music is included.

Everything here, including the optional plugin, stays in this standalone GPL repo.
Neither HydraPy nor Gorgon was changed. The engine communicates through stdin/stdout
and a private mmap file; no engine library is loaded into either host. This layout
implements the requested boundary; it is not a legal determination about plugin licensing.

## Build and test

```
make -C doomgeneric -f Makefile.ipc -j8
export FREEDOOM_WAD=/absolute/path/to/freedoom2.wad
python test_ipc.py
```

Requires Linux little-endian x86-64, GCC, make, Python and NumPy. The optional
plugin needs HydraPy's FrameSource/add_op API and its GL renderer. No install step
or changes to HydraPy are required; put this repository on PYTHONPATH.

```
from client import Doom
from ops_doom import doom
engine = Doom(wad_path, demo='demo1', loop_seconds=60)
doom(engine).halftone(5).out()
# close engine when the patch/session ends
engine.close()
```

`doom(engine)` returns a normal chain backed by a dynamically uploaded FrameSource.
Coordinates sample texel centres for crisp default filtering. Four build(ctx) scenes
are under scenes/, with an optional bitmap ASCII texture operator registered via
HydraPy.add_op. Scene source time is renderer seconds, 35 game tics per second.
For a tracker beat clock use seconds = beat * 60 / bpm at the transport origin;
transport integration and live Rack capture have NOT been completed.

`Doom(..., demo=None)` starts a playable level; `key(code, down)` queues input.
`LaneKeys.update(fire, pitch, move, use)` maps held tracker signals to fire,
left/right, forward and use. This adapter is caller driven; it has not been wired
into Studio's tracker callbacks. Demo playback ignores live movement commands.
`locked=False` enables wall-clock free running. Game audio is disabled upstream;
Freedoom music is extracted separately, not played by this engine.

A demo process exits at demo end. Set loop_seconds shorter than its length to replay
a fixed segment by restarting, deterministically. Example scenes use the FIRST 60
SECONDS of DEMO1, not a continuous four-minute recording. Negative renderer prewarm
times hold frame zero. Backward seeks restart/replay; interactive input history is
not replayed, so deterministic seeking is supported for demos only.

## IPC v1

Launch with DOOM_FRAME=/private/path and DOOM_LOCKED=1 for external tics.
stdout is reserved for protocol; engine messages go to stderr. READY/OK replies
contain absolute game tic and frame counter. Initialization consumes two game tics;
the client records that as its origin. STEP N advances N tics (0..35000), KEY D K
queues pressed/released byte key codes, QUIT exits. Commands are acknowledged.
The 1024-event input queue preserves event order. The free-running engine steps
between commands. The external clock uses rational 35 Hz time and single-tic engine
mode. Wall-clock transition wipes are skipped in locked mode.

Frame mmap: 64-byte little-endian header, then 640×400 BGRA8 bytes, top to bottom.
Offsets: 0 magic DHF1, 4 uint32 width, 8 uint32 height, 16 uint64 frame count,
24 uint64 gametic, 32 uint64 publication sequence. Writer sets sequence odd while
publishing and even afterward. Reader retries copies spanning a publication.
The supplied reader assumes coherent x86-64 memory; do not treat this as a portable
cross-architecture atomic ABI. Alpha is filled to 255 by the client.

## Music and remaining work

extract_wad.py extracts unmodified MIDI/MUS/demo lumps and per-lump SHA256s.
The official release contains MIDI music. Output manifests, complete Freedoom
credits, both WAD hashes and music audits accompany this prototype outside git.
No validated tracker scores or Rack soundtrack are delivered: every audited track
exceeds six concurrent notes (lowest Phase 2 count: seven), and some change tempo.
A six-monophonic-lane reduction would alter the composition. Decide whether to
allow multiple six-lane stem passes, a wider/polyphonic rig, or explicit reductions.
Then select 3–4 credited pieces and implement timing/voice mapping with roundtrip
note-event comparison. Score validation alone cannot prove a faithful conversion.

No four-minute simultaneous MP4/WAV proof take, held-frame/xrun figures, Studio
keyboard integration, game-event output, or Gorgon prewarm validation is claimed.
Eight-second scenecheck videos use the checker's test audio, NOT Freedoom/Rack.
