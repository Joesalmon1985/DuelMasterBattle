#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/tools/find_godot.sh"
cd "$ROOT"
# Real wall-clock playtest (~20 s). Runs headed so input routing matches a device.
"$GODOT" --path godot_project --resolution 720x1280 --script res://client/tools/realtime_playtest.gd "$@"
