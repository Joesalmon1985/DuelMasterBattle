#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/tools/find_godot.sh"
cd "$ROOT"
"$GODOT" --path godot_project --resolution 720x1280 --script res://client/tools/capture_adventure_qa.gd -- --screenshot-mode
echo "screenshots -> qa/screenshots/adventure"
