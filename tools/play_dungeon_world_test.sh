#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source "$ROOT/tools/find_godot.sh"

export DMB_FIXTURE="FX-DUNGEON-WORLD"
export DMB_SEED="${DMB_SEED:-507}"
RESOLUTION="${DMB_RESOLUTION:-450x800}"
if [[ "${1:-}" == "--resolution" ]]; then
  RESOLUTION="${2:?--resolution requires WxH}"
  shift 2 || true
fi

echo "Dungeon World Spatial Test seed=$DMB_SEED resolution=$RESOLUTION"
echo "Disposable fixture — does not write the campaign adventure.save"
exec "$GODOT" --path "$ROOT/godot_project" --resolution "$RESOLUTION" \
  res://client/scenes/dungeon_world_test.tscn "$@"
