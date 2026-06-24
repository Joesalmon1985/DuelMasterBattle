#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export GODOT="${GODOT:-$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64}"
export GODOT_USER_DATA_DIR="${GODOT_USER_DATA_DIR:-$ROOT/godot_project/.godot_user}"
cd "$ROOT"
timeout 600s "$GODOT" --headless --path godot_project --script res://sim/tools/run_tests.gd "$@"
exit $?
