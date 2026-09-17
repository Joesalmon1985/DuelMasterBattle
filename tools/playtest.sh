#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "DuelMasterBattle Linux playtest"
echo "1. Play G03 directly (450x800)"
echo "2. Play G02 directly (450x800)"
echo "3. Play G01 directly"
echo "4. Run G03 automated checks"
echo "5. Run all implemented gates G01-G03"
echo "0. Exit"
read -r -p "Select: " choice
case "$choice" in
  1) exec bash tools/play_g03.sh ;;
  2) exec bash tools/play_g02.sh --direct ;;
  3) exec bash tools/play_g01.sh --direct ;;
  4) exec python3 tools/check.py --gate G03 ;;
  5)
    python3 tools/check.py --gate G01
    python3 tools/check.py --gate G02
    python3 tools/check.py --gate G03
    ;;
  0) exit 0 ;;
  *) echo "Invalid choice"; exit 2 ;;
esac
