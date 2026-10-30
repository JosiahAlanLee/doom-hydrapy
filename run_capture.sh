#!/bin/bash
set -euo pipefail
root=${DOOM_TAKE_ROOT:-/home/echevarian/dev/shared/codex/doom-hydrapy-20261030}
repo=/home/echevarian/dev/shared/codex/doom-hydrapy
previous=/home/echevarian/dev/shared/codex/gorgon-r3b-20261030
mode=${1:-smoke}
export PYTHONDONTWRITEBYTECODE=1
export LD_PRELOAD="$repo/poly/ipc_namespace.so"
export PYTHONPATH="$previous/Gorgon:$previous/runtime:$repo"
export DOOM_TAKE_ROOT="$root"
mkdir -p "$root/tmp"
export TMPDIR="$root/tmp"
if [[ $mode == smoke ]]; then
 export DOOM_SMOKE=1
 duration=14
else
 export DOOM_SMOKE=0
 duration=240
fi
extra_plugins=()
if [[ ${DOOM_INDUSTRIAL:-0} == 1 ]]; then
 : "${PVX_PLUGIN_DIR:?Set PVX_PLUGIN_DIR to the reviewed PVX build}"
 export DOOM_DATA_ROOT=/home/echevarian/dev/shared/codex/doom-hydrapy-20261030
 extra_plugins=(--plugin-dir "$PVX_PLUGIN_DIR")
fi
/home/echevarian/miniconda3/envs/hydrapy/bin/python -m gorgon --config "$root/$mode-rig.json" render "$root/$mode-score.json" --output "$root/$mode-capture" --jack-server doom_poly_20261030 --seconds "$duration" --warmup 4 --lead-blocks 2 --plugin-dir "$repo/poly" "${extra_plugins[@]}"
