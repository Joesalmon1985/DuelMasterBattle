#!/usr/bin/env bash
# Print visual capture checklist and optionally launch Godot for manual screenshots.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

cat <<'EOF'
Visual capture checklist — see docs/VISUAL_CAPTURE.md

  1. Main menu
  2. Secret setup (player wizard + point headers)
  3. Magic picker open
  4. Enemy attacking (bot rows + skip)
  5. Human attacking
  6. Result screen

Capture at 1280x720 or 900x700 for consistency.
EOF

if [[ "${1:-}" == "--launch" ]]; then
  export GODOT="${GODOT:-$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64}"
  export GODOT_USER_DATA_DIR="${GODOT_USER_DATA_DIR:-$ROOT/godot_project/.godot_user}"
  exec "$GODOT" --path "$ROOT/godot_project"
fi
