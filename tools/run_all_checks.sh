#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/tools/find_godot.sh"
cd "$ROOT"
"$ROOT/tools/run_godot_tests.sh"
"$ROOT/tools/run_godot_ui_smoke.sh"
"$ROOT/tools/run_adventure_flow.sh"
"$ROOT/tools/run_dungeon_flow.sh"
"$ROOT/tools/run_dungeon_p3.sh"
"$ROOT/tools/run_realtime_playtest.sh"
