#!/usr/bin/env bash
# Ubuntu launcher: starts the simulator, waits for it, then opens Godot straight into God Mode or Wizard Mode.
#   scripts/launch_hybrid.sh god                 # God Mode
#   scripts/launch_hybrid.sh wizard              # Wizard Mode
#   HYBRID_SEED=11 HYBRID_MAP=small scripts/launch_hybrid.sh god     # another seed / map size (small, standard, large)
#   GODOT=/path/to/godot overrides the executable. God Mode has 1x..16x clock buttons.
# G switches modes at any time; the world, terrain, buildings, units and the wizard stay the same (one simulator).
set -euo pipefail
MODE="${1:-god}"
HYB="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(dirname "$HYB")"
GODOT="${GODOT:-$HOME/godot451/Godot_v4.5.1-stable_linux.x86_64}"
PORT="${HYBRID_SIM_PORT:-8765}"
export HYBRID_SIM_PORT="$PORT" HYBRID_START_MODE="$MODE"
cd "$HYB"
python3 -m wizard_rts.server > /tmp/hybrid_sim.log 2>&1 &
SIM=$!
trap 'kill $SIM 2>/dev/null' EXIT
for i in $(seq 1 60); do grep -q HYBRID_SIM_READY /tmp/hybrid_sim.log 2>/dev/null && break; sleep 1; done
grep -q HYBRID_SIM_READY /tmp/hybrid_sim.log || { echo "simulator did not start; see /tmp/hybrid_sim.log" >&2; exit 1; }
"$GODOT" --path "$REPO/godot_project" --rendering-method forward_plus res://client/scenes/hybrid_world.tscn
