#!/usr/bin/env bash
# Launch G08 content-sample morning review (seed 808).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export DMB_FIXTURE="${DMB_FIXTURE:-FX-CONTENT-SAMPLE}"
export DMB_SEED="${DMB_SEED:-808}"
echo "G08 sample: fixture=$DMB_FIXTURE seed=$DMB_SEED"
echo "Manifest: Pack/DuelMasterBattle_Build_Pack/tracking/gates/G08/sample_manifest.json"
echo "Dialogue preview: Pack/DuelMasterBattle_Build_Pack/tracking/gates/G08/dialogue_preview.md"
if [[ -x "${GODOT:-}" ]]; then
  exec "$GODOT" --path "$ROOT/godot_project" "$@"
fi
if [[ -x "$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64" ]]; then
  exec "$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64" --path "$ROOT/godot_project" "$@"
fi
echo "Godot binary not found; Python corpus checks remain authoritative for AUTO_READY."
python3 tools/content/validate_corpus.py --write
echo "play_g08_sample: corpus OK (headed Godot optional for owner review)"
