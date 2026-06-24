#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export GODOT="${GODOT:-$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64}"
cd "$ROOT"
mkdir -p build/web
timeout 300s "$GODOT" --headless --path godot_project --export-release "Web" build/web/index.html
echo "Export complete: build/web/index.html"
