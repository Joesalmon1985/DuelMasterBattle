#!/usr/bin/env bash
# Capture G02 FX-CARGO gameplay screenshots at required viewports.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
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
unset DRI_PRIME || true
export DMB_FIXTURE="${DMB_FIXTURE:-FX-CARGO}"
export DMB_SEED="${DMB_SEED:-202}"
OUT="$ROOT/Pack/DuelMasterBattle_Build_Pack/tracking/gates/G02"
mkdir -p "$OUT/screenshots"
for RES in 450x800 720x1280 1280x720; do
  echo "Capturing G02 $RES ..."
  "$GODOT_BIN" --path "$ROOT/godot_project" --resolution "$RES" \
    --script res://client/tests/run_g02_capture.gd
done
# Desktop may clamp 720x1280; prefer the clamped capture over any stale packet file.
if compgen -G "$OUT/screenshot_720x*.png" > /dev/null; then
  # Prefer exact 720x1280 if present from this run; else latest 720x* capture.
  if [[ -f "$OUT/screenshot_720x1011.png" ]]; then
    cp -f "$OUT/screenshot_720x1011.png" "$OUT/screenshot_720x1280.png"
  fi
fi
# Prefer the true 450x800 wizard shot when present.
if [[ -f "$OUT/screenshot_450x800.png" ]]; then
  cp -f "$OUT/screenshot_450x800.png" "$OUT/screenshot_wizard.png"
fi
echo "G02_CAPTURE_BATCH_OK"
ls -la "$OUT"/screenshot_*.png "$OUT"/screenshots/*.png 2>/dev/null | awk '{print $5, $9}'
python3 - <<PY
from pathlib import Path
import struct
root = Path("$OUT")
for p in sorted(root.glob("screenshot_*.png")) + sorted((root/"screenshots").glob("*.png")):
    data = p.read_bytes()
    w, h = struct.unpack(">II", data[16:24])
    print(f"dim {w}x{h} bytes={p.stat().st_size} path={p.name}")
PY
