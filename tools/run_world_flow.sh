#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/tools/find_godot.sh"
cd "$ROOT"
"$GODOT" --headless --path godot_project --script res://client/tests/run_world_flow.gd "$@"
