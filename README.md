# Doom → HydraPy (local prototype, GPL-2.0-or-later)

Real Doom engine, not a clone: id Software's released source, maintained through
[doomgeneric](https://github.com/ozkl/doomgeneric). The supplied brief's ozkriff URL
was unavailable. See LICENSE, README.TXT and README.upstream.md for upstream credits.
Game assets are from [Freedoom 0.13.0](https://github.com/freedoom/freedoom/releases/tag/v0.13.0),
BSD licensed. No commercial WAD or original Doom music is included.

**Playable generative mode:** [Null Run](SEVEN_TIERS.md) descends through seven
seeded office tiers with two book demons per tier, inventory carryover and one
life. Four shared binding/combat families support the fourteen allocated demons.
The [integrated Threshold edition](THRESHOLD_INTEGRATION.md) preserves its custom
GUI, authored opening, environmental art, and Latchwing/Relay Choir encounters.
The [native campaign](ARGON_CAMPAIGN.md) includes all four Argon enemies, captured
mouse turn/fire/use, retry/new seed and lightweight Rack ambience. Use
`rogue/campaign_live.py` in HydraPy Studio. The [browser preview](ROGUELIKE.md)
is available with `python -m rogue.server --wad /path/to/freedoom2.wad` after
building the engine. The timed performance/capture path below remains separate.

[The Gloamwood iteration](GLOAMWOOD.md) adds a watched/crawling Hollow, Stone
ReDead's telegraphed shriek and escapable grip, two more book demons, and
individual encounter studies. These use original procedural art. The current
campaign allocation extends the four book encounters across all seven tiers.

[Surveyor optics](SURVEYOR_OPTICS.md) provides an opt-in HydraPy operator driven
by the native warning countdown, with exact RAW/HUD preservation and no rear radar.

[Book-boss encounters](BOSSES.md) add Repetiel and Calmor on seeded campaign
floors, with distinct binding rules, shield windows and native attacks. Choose a
binding study in the browser to practice either encounter directly.

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
For this demo adapter, use seconds = beat * 60 / bpm at the transport origin.
The separate native-play patch and live VCV integration are described in
[NATIVE-PLAY.md](NATIVE-PLAY.md).

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
queues pressed/released byte key codes, TURN D queues bounded relative mouse
turn (-4096..4096) for one tic, QUIT exits. Commands are acknowledged.
The 1024-event input queue preserves event order. The free-running engine steps
between commands. The external clock uses rational 35 Hz time and single-tic engine
mode. Wall-clock transition wipes are skipped in locked mode.

Frame mmap: 64-byte little-endian header, then 640×400 BGRA8 bytes, top to bottom.
Offsets: 0 magic DHF1, 4 uint32 width, 8 uint32 height, 16 uint64 frame count,
24 uint64 gametic, 32 uint64 publication sequence. Writer sets sequence odd while
publishing and even afterward. Reader retries copies spanning a publication.
The supplied reader assumes coherent x86-64 memory; do not treat this as a portable
cross-architecture atomic ABI. Alpha is filled to 255 by the client.

## Polyphonic live take

The complete four-minute take is in the sibling output folder
`doom-hydrapy-20261030/take/`: H.264/AAC MP4, 24-bit stereo WAV, report,
completion.json, SHA256SUMS, instrument mapping, gate audit and final-video review sheets.
This branch adds a separate polyphonic path, as approved for this project:

* `compile_music.py`: MIDI → timed note/controller events, including tempo maps,
  sustain, RPN pitch-bend sensitivity, velocity, volume, expression and pan.
* `poly/`: optional GPL Rack sequencer/mixer. Eighteen installed synth instances
  play all 5,857 notes in a single simultaneous live pass; no note reduction or
  multiple stem passes. Gate-loopback inputs audit physical cable edges.
* Gorgon's six audio lanes stay muted. Its transport drives the visual scene lane,
  Doom's 35 Hz tics and an absolute-time Z automation ramp feeding the sequencer.
  The raw clock pulse is diagnostic only, since counting edges accumulated errors.
* CZish uses its eight-voice single-line mode, Vastish uses native eight-voice
  programs, and OTIS Sampler uses polyphonic original drum samples. Spoon Bender
  adds stereo echo/space. Detailed timbre substitutions and capacities are delivered.
* All four complete Phase 1 compositions play: D_INTRO, D_BUNNY, D_INTER and D_E3M2.
  Credits: Korp (based on Tyler "Picklehammer" Pantella), Goji, Stratos, and
  Lola "BlueWorrior" Harvey respectively. Exact titles/times are in the report.
* Demos switch at 0, 7, 70 and 145 seconds: Phase 1 DEMO1/E1M6, Phase 2
  DEMO2/MAP10, Phase 1 DEMO3/E3M9 and Phase 2 DEMO4/MAP23. There is no demo loop.
  Terminal, print, scan and feedback treatments change once per minute.

`performance.py` is the optional GPL Studio patch. It reads `DOOM_TAKE_ROOT`
and keeps all engine code in child processes. `setup_take.py` builds the private
rig and validated visual-clock score. `run_capture.sh smoke` records the rapid
switch excerpt; `run_capture.sh poly` records 240 seconds. Build the C engine,
Rack plugin and namespace shim first. Python take dependencies are numpy, mido
and soundfile. These scripts use the workstation's frozen HydraPy/Gorgon copies
and Rack installation; paths are explicit in the scripts and report.

`test_music.py` verifies tempo changes, sustain, RPN bends, all source pitches,
velocities/timings and non-stealing allocation. `finalize_take.py` verifies the
live gate proof, muxes the take with a measured clock/offset correction, fully
decodes it, and extracts final-video sheets. Visual inspection is a separate
required signoff. `analyze_sync.py` measures paired 1 Hz optical/audio gates.
All official music lumps in the selected release are MIDI; a MUS parser is not
implemented in this branch. Original download URLs and hashes remain in PROVENANCE.json.

The synths are documented substitutes, not General MIDI replicas. Per-instance
voice retirement one second after note-off bounds substitute release tails;
it does not shorten held MIDI notes or drop attacks. Mod wheel maps to restrained
5 Hz pitch vibrato. The music finishes at 226.6 s, followed by effect decay and a
quiet game-only tail. This timed take does not map live keyboard/game events
into its score; native play uses its own window controller.

See poly/README.md for the sequencer ABI, private JACK namespace and buffer setup.
No host repository was changed; the optional integration stays in this standalone repository.

## Architectural studies

See [ARCHITECTURE.md](ARCHITECTURE.md) for the silent corridor seam, five-corner
pillar loop and unseen passage mutations. Choose a study under Next Run, then Retry.

## Native desktop play

[Native play](NATIVE-PLAY.md) adds the fluorescent Hollow study, direct picture-window controls and a reference Studio patch for live HydraPy/VCV use. RAW is the default; F3 cycles the optional GPU treatments.
