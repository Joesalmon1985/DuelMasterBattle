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
export DMB_FIXTURE="FX-LONG-WORLD"
export DMB_SEED="${DMB_SEED:-507}"
export DMB_SAVE_SLOT="${DMB_SAVE_SLOT:-g05_long_world}"
RESOLUTION="${DMB_RESOLUTION:-450x800}"
if [[ "${1:-}" == "--resolution" ]]; then RESOLUTION="${2:?--resolution requires WxH}"; fi
echo "G05 FX-LONG-WORLD observer seed=$DMB_SEED resolution=$RESOLUTION"
echo "Dev controls: Pause / 1x / 10x / 50x · run turns · Follow major events"
echo "Headless soak: python3 tools/run_long_world.py --max-turns 300"
exec "$GODOT_BIN" --path "$ROOT/godot_project" --resolution "$RESOLUTION" \
  res://client/scenes/g05_shell.tscn
