#!/usr/bin/env bash
# G02 FX-CARGO portrait launcher (native Linux Godot 4.4.1).
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
  echo "ERROR: Godot 4.4.1 executable not found." >&2
  return 1
}

GODOT_BIN="$(resolve_godot)"
export GODOT="$GODOT_BIN"
export DMB_FIXTURE="${DMB_FIXTURE:-FX-CARGO}"
export DMB_SEED="${DMB_SEED:-202}"
echo "Using Godot: $GODOT_BIN"
echo "Fixture: $DMB_FIXTURE seed=$DMB_SEED"

SCENE="res://client/scenes/main_menu.tscn"
RESOLUTION="450x800"
ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --direct)
      SCENE="res://client/scenes/g02_shell.tscn"
      shift
      ;;
    --landscape)
      RESOLUTION="1280x720"
      shift
      ;;
    --portrait)
      RESOLUTION="450x800"
      shift
      ;;
    --resolution)
      RESOLUTION="${2:?--resolution requires WxH}"
      shift 2
      ;;
    *)
      ARGS+=("$1")
      shift
      ;;
  esac
done

export DRI_PRIME="${DRI_PRIME:-0}"
echo "Resolution: $RESOLUTION (default portrait 450x800)"
exec "$GODOT_BIN" --path "$ROOT/godot_project" --resolution "$RESOLUTION" "$SCENE" "${ARGS[@]+"${ARGS[@]}"}"
