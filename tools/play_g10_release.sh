#!/usr/bin/env bash
# G10 Linux release launch helper (not a Windows certificate).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
GODOT="$("$ROOT/tools/find_godot.sh")"
exec "$GODOT" --path "$ROOT/godot_project" "$@"
