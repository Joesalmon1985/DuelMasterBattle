#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/tools/find_godot.sh"
cd "$ROOT"
"$GODOT" --headless --path godot_project --script res://sim/tools/check_scripts.gd
"$GODOT" --headless --path godot_project --script res://sim/tools/run_tests.gd "$@"
