#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3 || command -v python)"
fi

echo "Visual playtest review — FX-MVP g05_shell (DMB_PLAYTEST_REVIEW=1)"
exec "$PY" "$ROOT/tools/windows_playtest.py" play-visual-playtest
