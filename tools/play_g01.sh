#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/tools/find_godot.sh"
cd "$ROOT"
exec "$GODOT" --path godot_project "res://client/scenes/g01_shell.tscn" "$@"
