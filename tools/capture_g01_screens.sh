#!/usr/bin/env bash
# Capture G01 screenshots at required viewports using the real playable shell.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
GODOT_BIN="${GODOT:-}"
if [[ -z "$GODOT_BIN" || ! -x "$GODOT_BIN" ]]; then
  GODOT_BIN="$("$ROOT/tools/play_g01.sh" 2>/dev/null | true)"
fi
# Resolve the same way play_g01 does without launching.
resolve_godot() {
  if [[ -n "${GODOT:-}" && -x "${GODOT}" ]]; then printf '%s\n' "$GODOT"; return 0; fi
  local c
  for c in \
    "$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64" \
    "$HOME/Downloads/Godot_v4.4.1-stable_linux.x86_64" \
    "/usr/local/bin/godot"; do
    [[ -x "$c" ]] && { printf '%s\n' "$c"; return 0; }
  done
  command -v godot4 2>/dev/null || command -v godot 2>/dev/null || return 1
}
GODOT_BIN="$(resolve_godot)"
export DRI_PRIME="${DRI_PRIME:-0}"
OUT="$ROOT/Pack/DuelMasterBattle_Build_Pack/tracking/gates/G01"
mkdir -p "$OUT"
for RES in 450x800 720x1280 1280x720; do
  echo "Capturing $RES ..."
  "$GODOT_BIN" --path "$ROOT/godot_project" --resolution "$RES" \
    --script res://client/tests/run_g01_capture.gd
done
# If desktop clamps portrait height, alias the captured file to the packet name.
if [[ -f "$OUT/screenshot_720x1011.png" && ! -f "$OUT/screenshot_720x1280.png" ]]; then
  cp -f "$OUT/screenshot_720x1011.png" "$OUT/screenshot_720x1280.png"
fi
if [[ -f "$OUT/screenshot_720x1280.png" ]]; then
  cp -f "$OUT/screenshot_720x1280.png" "$OUT/screenshot_wizard.png"
elif [[ -f "$OUT/screenshot_720x1011.png" ]]; then
  cp -f "$OUT/screenshot_720x1011.png" "$OUT/screenshot_720x1280.png"
  cp -f "$OUT/screenshot_720x1011.png" "$OUT/screenshot_wizard.png"
fi
echo "G01_CAPTURE_BATCH_OK"
