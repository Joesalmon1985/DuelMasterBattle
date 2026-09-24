#!/usr/bin/env python3
"""Content quality / coverage report (C13 / T133).

Reports missing coverage across quest families, dungeons, rivals, dialogue,
recipes and assets without mutating packs.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "godot_project" / "content" / "source"
COMPILED = ROOT / "godot_project" / "content" / "compiled"
TRACKING = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking" / "content_coverage"

QUEST_FAMILIES = (
    "shortage",
    "transport",
    "catastrophe",
    "diplomacy",
    "military",
    "personal",
    "discovery",
    "conflict",
)
DUNGEON_LAYOUTS = (
    "cave",
    "mine",
    "sluice",
    "temple",
    "bunker",
    "industrial",
    "alien",
    "machine",
)
ERAS = ("prehistoric", "historic", "modern", "future")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _quest_templates() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    quests_root = SOURCE / "quests"
    if not quests_root.is_dir():
        return out
    for family in QUEST_FAMILIES:
        family_dir = quests_root / family
        if not family_dir.is_dir():
            continue
        for path in sorted(family_dir.glob("*.json")):
            data = _load_json(path)
            data["_path"] = str(path.relative_to(ROOT))
            data["_family_dir"] = family
            out.append(data)
    return out


def _dungeons() -> list[str]:
    found = []
    dungeons = SOURCE / "dungeons"
    for name in DUNGEON_LAYOUTS:
        layout = dungeons / name / "layout.json"
        if layout.is_file():
            found.append(name)
    return found


def _rivals() -> list[str]:
    rivals_dir = SOURCE / "rivals"
    if not rivals_dir.is_dir():
        return []
    return sorted(p.stem for p in rivals_dir.glob("*.json"))


def _dialogue_lines(*, include_baseline: bool = True) -> list[dict[str, Any]]:
    from tools.content.validate import load_bank

    return load_bank(include_archive=False, include_baseline=include_baseline)


def build_report() -> dict[str, Any]:
    quests = _quest_templates()
    by_family: Counter[str] = Counter()
    for q in quests:
        fam = str(q.get("family") or q.get("_family_dir") or "unknown")
        by_family[fam] += 1

    missing_families = [f for f in QUEST_FAMILIES if by_family.get(f, 0) < 2]
    dungeons = _dungeons()
    missing_dungeons = [d for d in DUNGEON_LAYOUTS if d not in dungeons]
    rivals = _rivals()
    dialogue = _dialogue_lines()
    eras_covered = sorted({str(l.get("era_id") or "all") for l in dialogue})

    recipes_path = SOURCE / "recipes" / "full.json"
    recipe_count = 0
    if recipes_path.is_file():
        recipes = _load_json(recipes_path)
        if isinstance(recipes, list):
            recipe_count = len(recipes)
        elif isinstance(recipes, dict):
            recipe_count = len(recipes.get("recipes") or recipes.get("items") or [])

    asset_manifest = ROOT / "godot_project" / "content" / "asset_manifest.json"
    assets_ok = asset_manifest.is_file()
    missing_assets: list[str] = []
    if assets_ok:
        am = _load_json(asset_manifest)
        missing_assets = list(am.get("missing_assets") or [])

    gaps = []
    if missing_families:
        gaps.append({"kind": "quest_family", "missing": missing_families})
    if missing_dungeons:
        gaps.append({"kind": "dungeon", "missing": missing_dungeons})
    if len(rivals) < 4:
        gaps.append({"kind": "rivals", "have": rivals, "need": 4})
    if len(dialogue) < 1200:
        gaps.append({"kind": "dialogue", "have": len(dialogue), "need": 1200})
    if recipe_count < 240:
        gaps.append({"kind": "recipes", "have": recipe_count, "need": 240})
    if missing_assets:
        gaps.append({"kind": "assets", "missing": missing_assets})

    report = {
        "schema_version": 1,
        "ok": not gaps,
        "quests": {
            "count": len(quests),
            "by_family": dict(by_family),
            "target_per_family": 2,
            "missing_families": missing_families,
        },
        "dungeons": {"count": len(dungeons), "ids": dungeons, "missing": missing_dungeons},
        "rivals": {"count": len(rivals), "ids": rivals},
        "dialogue": {
            "line_count": len(dialogue),
            "eras_seen": eras_covered,
            "target": 1200,
        },
        "recipes": {"count": recipe_count, "target": 240},
        "assets": {"manifest_present": assets_ok, "missing": missing_assets},
        "gaps": gaps,
        "compiled_manifest_present": (COMPILED / "manifest.json").is_file()
        or (COMPILED / "dialogue" / "manifest.json").is_file(),
    }
    return report


def write_report(report: dict[str, Any] | None = None) -> Path:
    report = report or build_report()
    TRACKING.mkdir(parents=True, exist_ok=True)
    path = TRACKING / "quality_report.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md = TRACKING / "quality_report.md"
    lines = [
        "# Content quality report",
        "",
        f"**Status:** `{'PASS' if report['ok'] else 'GAPS'}`",
        "",
        f"- Quests: {report['quests']['count']} (by family: {report['quests']['by_family']})",
        f"- Dungeons: {report['dungeons']['count']} / 8",
        f"- Rivals: {report['rivals']['count']} / 4",
        f"- Dialogue lines: {report['dialogue']['line_count']} / 1200",
        f"- Recipes: {report['recipes']['count']} / 240",
        "",
    ]
    if report["gaps"]:
        lines.append("## Gaps")
        for gap in report["gaps"]:
            lines.append(f"- `{gap}`")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true", help="Write tracking/content_coverage/")
    args = parser.parse_args(argv)
    report = build_report()
    if args.write:
        write_report(report)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        status = "PASS" if report["ok"] else "GAPS"
        print(
            f"quality_report: {status} quests={report['quests']['count']} "
            f"dungeons={report['dungeons']['count']} rivals={report['rivals']['count']} "
            f"dialogue={report['dialogue']['line_count']} recipes={report['recipes']['count']}"
        )
        for gap in report["gaps"]:
            print(f"  GAP: {gap}")
    # Report tool itself succeeds even with gaps; validators enforce floors elsewhere.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
