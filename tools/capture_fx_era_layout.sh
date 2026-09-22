#!/usr/bin/env bash
# Capture FX-ERA layout screenshots at multiple resolutions (real Godot frames).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source "$ROOT/tools/find_godot.sh"
OUT="$ROOT/Pack/DuelMasterBattle_Build_Pack/tracking/gates/G06/layout_captures"
mkdir -p "$OUT"
export DMB_FIXTURE=FX-ERA
export DMB_SEED=507
export DMB_SAVE_SLOT=fx_era_layout_capture
for RES in 450x800 960x540 1280x720; do
  echo "=== capture $RES ==="
  timeout 90 "$GODOT" --path "$ROOT/godot_project" --resolution "$RES" \
    --script res://client/tests/run_fx_era_layout_capture_one.gd -- "$RES" "$OUT" \
    2>&1 | tee "/tmp/fx_era_capture_${RES}.log" | grep -E 'FX_ERA_CAPTURE_|ERROR|SCRIPT' || true
done
ls -la "$OUT"
