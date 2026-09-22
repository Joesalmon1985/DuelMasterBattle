#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
resolve_godot() {
  if [[ -n "${GODOT:-}" && -x "${GODOT}" ]]; then printf '%s\n' "$GODOT"; return; fi
  for candidate in \
    "$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64" \
    "$HOME/Downloads/Godot_v4.4.1-stable_linux.x86_64" \
    "/usr/local/bin/godot"; do
    if [[ -x "$candidate" ]]; then printf '%s\n' "$candidate"; return; fi
  done
  command -v godot4 || command -v godot
}
GODOT_BIN="$(resolve_godot)"
export GODOT="$GODOT_BIN"
export DMB_FIXTURE="FX-MVP"
export DMB_SEED="${DMB_SEED:-507}"
export DMB_SAVE_SLOT="${DMB_SAVE_SLOT:-mvp}"
RESOLUTION="${DMB_RESOLUTION:-450x800}"
echo "FX-MVP seed=$DMB_SEED resolution=$RESOLUTION (normal Prehistoric sandbox)"
exec "$GODOT_BIN" --path "$ROOT/godot_project" --resolution "$RESOLUTION" \
  res://client/scenes/g05_shell.tscn
