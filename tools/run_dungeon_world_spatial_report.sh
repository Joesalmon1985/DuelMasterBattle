#!/usr/bin/env bash
# Headless spatial metrics dump for the dungeon-world fixture.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/tools/find_godot.sh"
cd "$ROOT"
"$GODOT" --headless --path godot_project --script res://client/tests/run_dungeon_world_spatial_report.gd "$@"
