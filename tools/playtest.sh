#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "DuelMasterBattle Linux playtest"
echo "1. Play G04 battle (450x800)"
echo "2. Play G04 hazard (450x800)"
echo "3. Play G03 directly (450x800)"
echo "4. Play G02 directly (450x800)"
echo "5. Play G01 directly"
echo "6. Run G04 automated checks"
echo "7. Run all implemented gates G01-G04"
echo "0. Exit"
read -r -p "Select: " choice
case "$choice" in
  1) exec bash tools/play_g04_battle.sh ;;
  2) exec bash tools/play_g04_hazard.sh ;;
  3) exec bash tools/play_g03.sh ;;
  4) exec bash tools/play_g02.sh --direct ;;
  5) exec bash tools/play_g01.sh --direct ;;
  6) exec python3 tools/check.py --gate G04 ;;
  7)
    python3 tools/check.py --gate G01
    python3 tools/check.py --gate G02
    python3 tools/check.py --gate G03
    python3 tools/check.py --gate G04
    ;;
  0) exit 0 ;;
  *) echo "Invalid choice"; exit 2 ;;
esac
