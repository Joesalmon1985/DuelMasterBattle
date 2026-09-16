#!/usr/bin/env bash
# G01 playtest launcher — normal Godot client (main menu).
# Menu path: press "G01 FX-CLOCK  (Python-backed runtime playtest)"
# Direct shell: bash tools/play_g01.sh --direct
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/tools/find_godot.sh"
cd "$ROOT"
SCENE="res://client/scenes/main_menu.tscn"
if [[ "${1:-}" == "--direct" ]]; then
  SCENE="res://client/scenes/g01_shell.tscn"
  shift
fi
# Prefer the pinned 4.4.1 binary from toolchain / find_godot.sh
exec "$GODOT" --path godot_project --resolution 1280x720 "$SCENE" "$@"
