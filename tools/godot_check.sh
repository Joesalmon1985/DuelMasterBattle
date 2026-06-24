#!/usr/bin/env bash
set -euo pipefail
echo "=== Godot processes (project-scoped) ==="
pgrep -af 'Godot.*DuelMasterBattle' || true
pgrep -af 'Godot.*godot_project' || true
echo "=== All Godot processes (inspect only) ==="
pgrep -af '[Gg]odot' || echo "(none)"
