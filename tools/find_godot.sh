#!/usr/bin/env bash
# Resolve a Godot 4 binary. Honours $GODOT; otherwise searches common locations.
# Usage:  source tools/find_godot.sh   (sets $GODOT)
if [[ -n "${GODOT:-}" && -x "$GODOT" ]]; then
  return 0 2>/dev/null || exit 0
fi
CANDIDATES=(
  "$HOME/Downloads/Godot_v4.5.1-stable_win64.exe/Godot_v4.5.1-stable_win64_console.exe"
  "$HOME/Downloads/Godot_v4.5.1-stable_win64_console.exe"
  "$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64"
  "/c/Program Files/Godot/Godot_v4.5.1-stable_win64_console.exe"
  "/Applications/Godot.app/Contents/MacOS/Godot"
)
for c in "${CANDIDATES[@]}"; do
  if [[ -x "$c" ]]; then
    export GODOT="$c"
    return 0 2>/dev/null || exit 0
  fi
done
for name in godot4 godot Godot; do
  if command -v "$name" >/dev/null 2>&1; then
    export GODOT="$(command -v "$name")"
    return 0 2>/dev/null || exit 0
  fi
done
echo "Godot 4 binary not found. Set GODOT=/path/to/godot" >&2
return 1 2>/dev/null || exit 1
