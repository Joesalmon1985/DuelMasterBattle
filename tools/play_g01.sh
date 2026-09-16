#!/usr/bin/env bash
# G01 playable launcher for a fresh terminal (native Linux Godot 4.4.1).
# Discovers the binary without requiring a pre-set $GODOT.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

resolve_godot() {
  if [[ -n "${GODOT:-}" && -x "${GODOT}" ]]; then
    printf '%s\n' "$GODOT"
    return 0
  fi
  local candidates=(
    "$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64"
    "$HOME/Downloads/Godot_v4.4.1-stable_linux.x86_64"
    "/usr/local/bin/godot"
  )
  local c
  for c in "${candidates[@]}"; do
    if [[ -x "$c" ]]; then
      printf '%s\n' "$c"
      return 0
    fi
  done
  if command -v godot4 >/dev/null 2>&1; then
    command -v godot4
    return 0
  fi
  if command -v godot >/dev/null 2>&1; then
    command -v godot
    return 0
  fi
  echo "ERROR: Godot 4.4.1 executable not found. Install/pin it or set GODOT=/path/to/Godot_v4.4.1-stable_linux.x86_64" >&2
  return 1
}

GODOT_BIN="$(resolve_godot)"
export GODOT="$GODOT_BIN"
echo "Using Godot: $GODOT_BIN"

SCENE="res://client/scenes/main_menu.tscn"
if [[ "${1:-}" == "--direct" ]]; then
  SCENE="res://client/scenes/g01_shell.tscn"
  shift
fi

# Optional Intel discrete-GPU quirk workaround (does not change system drivers).
export DRI_PRIME="${DRI_PRIME:-0}"

exec "$GODOT_BIN" --path "$ROOT/godot_project" --resolution 1280x720 "$SCENE" "$@"
