#!/usr/bin/env bash
# Run one headed script with full output: scripts/run_headed_one.sh <script.gd> [ENV=VAL ...]  (sim profile/env from the arguments)
set -uo pipefail
HYB="$(cd "$(dirname "$0")/.." && pwd)"; REPO="$(dirname "$HYB")"
GODOT="${GODOT:-$HOME/godot451/Godot_v4.5.1-stable_linux.x86_64}"
script="$1"; shift
port=$(python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1])")
(cd "$HYB" && env "$@" HYBRID_SIM_PORT=$port python3 -u -m wizard_rts.server >/tmp/hybrid_sim_$port.log 2>&1 & echo $! > /tmp/hybrid_sim_$port.pid)
for _i in $(seq 1 60); do grep -q HYBRID_SIM_READY /tmp/hybrid_sim_$port.log 2>/dev/null && break; sleep 1; done
env "$@" HYBRID_SIM_PORT=$port timeout "${TIMEOUT:-600}" "$GODOT" --path "$REPO/godot_project" --rendering-method forward_plus --script "res://client/tests/$script" 2>&1
kill "$(cat /tmp/hybrid_sim_$port.pid)" 2>/dev/null
