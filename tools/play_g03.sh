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
export DMB_FIXTURE="FX-INDUSTRY"
export DMB_SEED="303"
RESOLUTION="${DMB_RESOLUTION:-450x800}"
if [[ "${1:-}" == "--resolution" ]]; then RESOLUTION="${2:?--resolution requires WxH}"; fi
echo "G03 FX-INDUSTRY seed=303 resolution=$RESOLUTION"
exec "$GODOT_BIN" --path "$ROOT/godot_project" --resolution "$RESOLUTION" \
  res://client/scenes/g03_shell.tscn
