"""Summarise era-bar study runs (plan v2 5.6 / P12): when did eras end, how, and what the leftover rule distributed.

    python3 scripts/era_study_report.py NAME=DIR [NAME=DIR ...] > docs/evidence/p12_era_study/summary.md
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path


def main() -> int:
    print("# Era-bar study (draft v2, plus AIs, war mode)\n")
    print("| configuration | games | eras reached (final era per game) | transition minutes (VP / stall guard) | early-ending phases (before round 7) | leftover cards awarded / lost per transition | mean top VP at end |")
    print("| --- | ---: | --- | --- | --- | --- | --- |")
    for arg in sys.argv[1:]:
        name, d = arg.split("=", 1)
        d = Path(d).expanduser()
        try:
            doc = json.loads((d / "summary.json").read_text())
        except OSError:
            print(f"| {name} | (not finished) | | | | | |")
            continue
        games = doc["games"]
        finals = [g["era"] for g in games]
        trans = []
        for g in games:
            for e in g["era_log"]:
                trans.append(f"{round(e['game_ms'] / 60000)}{'' if e['reason'] == 'vp_threshold' else 's'}")
        awarded = lost = n = early = 0
        for line in (d / "events.jsonl").read_text().splitlines() if (d / "events.jsonl").exists() else []:
            e = json.loads(line)
            if e.get("kind") == "draft_leftovers":
                n += 1
                awarded += sum(len(v) for v in e.get("awarded", {}).values()) if isinstance(e.get("awarded"), dict) else 0
                lost += sum(len(v) for v in e.get("lost", {}).values()) if isinstance(e.get("lost"), dict) else 0
                early += 1
        top = sum(max(g["vp"].values()) for g in games) / max(1, len(games))
        print(f"| {name} | {len(games)} | {finals} | {', '.join(trans)} | {early} | {awarded}/{lost} over {n} | {top:.1f} |")
    print("\nTransition minutes suffixed `s` ended by the 75-minute stall guard. `events.jsonl` keeps only the tournament's major events, so leftover counts are lower bounds when `draft_leftovers` is not in that list.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
