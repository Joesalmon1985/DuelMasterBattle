#!/usr/bin/env bash
set -euo pipefail
echo "Cleaning stale DuelMasterBattle Godot processes..."
pkill -f 'Godot.*DuelMasterBattle' 2>/dev/null || true
pkill -f 'Godot.*godot_project' 2>/dev/null || true
sleep 1
echo "Remaining:"
pgrep -af '[Gg]odot' || echo "(none)"
