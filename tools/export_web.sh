#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export GODOT="${GODOT:-$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64}"
cd "$ROOT"
cd "$ROOT/godot_project"
mkdir -p build/web
timeout 300s "$GODOT" --headless --export-release "Web" build/web/index.html
echo "Export complete: godot_project/build/web/index.html"
