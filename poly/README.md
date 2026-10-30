# Freedoom polyphonic stream (GPL-2.0-or-later)

Build with Rack SDK 2: `make RACK_DIR=/absolute/path/Rack-SDK`.
Build the optional JACK1 isolation shim with
`gcc -shared -fPIC ipc_namespace.c -ldl -o ipc_namespace.so`.
The take script installs this plugin only in each private capture's Rack user folder.

Stream consumes Gorgon RUN on input 0, a diagnostic 32 PPQN clock on input 1,
and absolute time on input 66 (Gorgon Z × 24 seconds/volt). The score encodes a
linear time ramp in Z; the sequencer coasts on Rack's sample clock during the last
row's hold and re-anchors on the next pattern. It does not count clock pulses as
authoritative time: phase corrections can produce extra or missing pulse edges.

Each route has pitch/gate/velocity outputs at 3*r + 0/1/2. Gate-loopback inputs
2+r count real cable edges one sample later. Audio-return inputs 34+r mix the
installed synths. Outputs 96/97 are stereo, and 98 is a 1 Hz sync gate. The same
sync pulse appears as a small square in the video. Physical voice allocation
reserves a low-gate interval; it never steals a held note. Unused high voice
channels are retired one second after note-off to reduce CPU work.

The memory-mapped proof file begins with eight float64 fields: timeline seconds,
sample-clock seconds, clock edges, emitted note-ons, note-offs, observed gate
edges, audio frames, run state. Each source note has eight float64 fields:
scheduled time, emitted sample-clock time, observed gate time (-1 if absent),
audio frame, route, voice, original MIDI note, normalized velocity. All note IDs
remain those of the source, including in the short smoke excerpts.

CZish's independent poly output is mixed with per-note MIDI velocity. Vastish and
OTIS receive poly velocity CV directly. Volume/expression/pan controllers apply
at the mixer. Pitch-bend sensitivity follows RPN 0, and sustain defers melodic
note-offs. Mod wheel is substituted by a restrained 5 Hz pitch vibrato. Drum notes
retain their identities and relative pitches around eight substitute sample roots.
The generated one-shot samples are original synthesis, not id Software recordings.
Vastish's six preset parameter arrays are from DSP_Emulation, BSD-3-Clause; see
../LICENSE-DSP_Emulation-BSD3.txt. No General MIDI soundfont is claimed.

The shim gives this process group its own SysV shared-memory registry/lock keys
by XORing non-private IPC keys. It exists because the workstation's JACK1 registry
has stale occupied server slots. It does not remove or alter those records, change
system packages, or replace the system JACK libraries. Each capture runs alone.

Set Rack's worker count to four only inside this private Rack process. The rig
uses a 2048-sample buffer at 48 kHz; audiovisual timing is measured after capture.
