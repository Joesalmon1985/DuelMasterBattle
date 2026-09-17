#!/usr/bin/env bash
# Capture G02 cart departure/arrival frames and assemble a short webm.
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
OUT="$ROOT/Pack/DuelMasterBattle_Build_Pack/tracking/gates/G02/recordings"
mkdir -p "$OUT"
# Godot may linger after SceneTree.quit when the sidecar restarts; bound wall time.
set +e
timeout 55 "$GODOT_BIN" --path "$ROOT/godot_project" --resolution 450x800 \
  --script res://client/tests/run_g02_cart_journey_demo.gd
code=$?
set -e
# 124 = timeout after successful frame dump is acceptable.
if [[ "$code" -ne 0 && "$code" -ne 124 ]]; then
  exit "$code"
fi
# Assemble a short silent webm from captured frames when ffmpeg is available.
if command -v ffmpeg >/dev/null 2>&1; then
  ls -1 "$OUT"/depart_*.png "$OUT"/crossing.png "$OUT"/arrive_*.png "$OUT"/final.png > "$OUT/frames.txt" || true
  TMP="$OUT/_seq"
  rm -rf "$TMP"
  mkdir -p "$TMP"
  i=0
  for f in "$OUT"/depart_*.png "$OUT"/crossing.png "$OUT"/arrive_*.png "$OUT"/final.png; do
    [[ -f "$f" ]] || continue
    ffmpeg -y -i "$f" -vf "format=yuv420p" "$TMP/frame_$(printf '%03d' "$i").png" >/dev/null 2>&1
    i=$((i + 1))
  done
  if [[ "$i" -gt 0 ]]; then
    ffmpeg -y -framerate 2 -i "$TMP/frame_%03d.png" \
      -c:v libvpx -pix_fmt yuv420p -b:v 800k -an "$OUT/cart_journey.webm" \
      && echo "G02_JOURNEY_RECORDING $OUT/cart_journey.webm" \
      || echo "G02_JOURNEY_FRAMES_ONLY (ffmpeg encode failed) $OUT"
  fi
  rm -rf "$TMP"
else
  echo "G02_JOURNEY_FRAMES_ONLY (ffmpeg not installed) $OUT"
fi
ls -la "$OUT" | head -30
