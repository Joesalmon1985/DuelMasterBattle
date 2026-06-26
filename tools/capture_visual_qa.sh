#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export GODOT="${GODOT:-$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64}"
export GODOT_USER_DATA_DIR="${GODOT_USER_DATA_DIR:-$ROOT/godot_project/.godot_user}"
cd "$ROOT"
ARGS=()
if [[ "${1:-}" == "--baseline" ]]; then
  ARGS+=(--baseline)
fi
"$GODOT" --path godot_project --resolution 720x1280 \
  --script res://client/tools/capture_visual_qa.gd "${ARGS[@]}"
python3 "$ROOT/tools/visual_qa_report.py"
exit 0
