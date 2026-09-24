#!/usr/bin/env python3
"""Content corpus / dependency / gameplay coverage validation (C14 / T141)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "godot_project" / "content" / "source"
TRACKING = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking" / "content_coverage"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.content.compile import _collect_quest_templates, compile_baseline_dialogue  # noqa: E402
from tools.content.quality_report import build_report, write_report  # noqa: E402
from tools.content.validate import load_bank, validate_dialogue_integrity  # noqa: E402

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
DUNGEONS = ("cave", "mine", "sluice", "temple", "bunker", "industrial", "alien", "machine")


def _recipe_count() -> int:
    path = SOURCE / "recipes" / "full.json"
    if not path.is_file():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        return len(data.get("recipes") or data.get("items") or [])
    return 0


def _tech_count() -> int:
    total = 0
    tech = SOURCE / "technology"
    if not tech.is_dir():
        return 0
    for path in tech.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            total += len(data)
        elif isinstance(data, dict):
            total += len(data.get("technologies") or data.get("tech") or data.get("items") or [data])
    return total


def validate_corpus() -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    templates = _collect_quest_templates()
    # Count G08 family templates (exclude village_production legacy).
    by_family: dict[str, int] = {f: 0 for f in QUEST_FAMILIES}
    for t in templates:
        fam = str(t.get("family") or "")
        if fam in by_family:
            by_family[fam] += 1
        # Dangling checks
        for route in ("world_resolved_route", "invalid_target_route", "dead_target_route", "displaced_target_route"):
            if route not in t and fam in by_family:
                errors.append(f"{t.get('id')}: missing {route}")
        solutions = t.get("solutions") or []
        if fam in by_family and len(solutions) < 2:
            errors.append(f"{t.get('id')}: need ≥2 solutions")
        # Softlock: required item recovery must exist for G08 families
        if fam in by_family and "required_item_recovery" not in t:
            errors.append(f"{t.get('id')}: missing required_item_recovery")

    for fam, count in by_family.items():
        if count < 2:
            errors.append(f"family {fam}: need 2 templates, have {count}")

    dungeons_found = []
    for name in DUNGEONS:
        layout = SOURCE / "dungeons" / name / "layout.json"
        puzzle = SOURCE / "dungeons" / name / "puzzle.json"
        if not layout.is_file() or not puzzle.is_file():
            errors.append(f"dungeon {name}: missing layout/puzzle")
            continue
        dungeons_found.append(name)
        pz = json.loads(puzzle.read_text(encoding="utf-8"))
        if not pz.get("solution_trace") or not pz.get("recovery_trace"):
            errors.append(f"dungeon {name}: incomplete solution/recovery trace")
        if pz.get("hidden_secret_readable_by_rivals"):
            errors.append(f"dungeon {name}: rivals must not read hidden secrets")

    rivals_dir = SOURCE / "rivals"
    rivals = list(rivals_dir.glob("*.json")) if rivals_dir.is_dir() else []
    if len(rivals) < 4:
        errors.append(f"rivals: need 4, have {len(rivals)}")
    for path in rivals:
        r = json.loads(path.read_text(encoding="utf-8"))
        if r.get("reads_hidden_secrets"):
            errors.append(f"{r.get('id')}: must not read hidden secrets")

    dialogue = load_bank(include_baseline=True)
    integrity = validate_dialogue_integrity(dialogue)
    if not integrity["ok"]:
        errors.extend(integrity["errors"])
    if integrity["line_count"] < 1200:
        errors.append(f"dialogue lines {integrity['line_count']} < 1200")

    recipes = _recipe_count()
    if recipes < 240:
        warnings.append(f"recipes {recipes} < 240 (catalogue may still be loading)")

    tech = _tech_count()
    if tech < 24:
        warnings.append(f"tech defs {tech} < 24")

    assets = ROOT / "godot_project" / "content" / "asset_manifest.json"
    if not assets.is_file():
        errors.append("missing asset_manifest.json")
    else:
        am = json.loads(assets.read_text(encoding="utf-8"))
        if am.get("missing_assets"):
            errors.append(f"missing assets: {am['missing_assets']}")

    unreviewed = list(integrity.get("warnings") or [])[:50]

    report = {
        "schema_version": 1,
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "counts": {
            "recipes": recipes,
            "tech": tech,
            "quests_by_family": by_family,
            "quest_templates_total": len(templates),
            "dungeons": len(dungeons_found),
            "rivals": len(rivals),
            "dialogue_lines": integrity["line_count"],
        },
        "unreviewed_items": unreviewed,
        "integrity": {
            "missing_semantic_ids": integrity.get("missing_semantic_ids"),
            "repetitive_phrase_count": integrity.get("repetitive_phrase_count"),
        },
    }
    return report


def write_coverage(report: dict[str, Any] | None = None) -> Path:
    report = report or validate_corpus()
    TRACKING.mkdir(parents=True, exist_ok=True)
    path = TRACKING / "coverage_report.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md = TRACKING / "coverage_report.md"
    lines = [
        "# Content coverage report (T141)",
        "",
        f"**Status:** `{'PASS' if report['ok'] else 'FAIL'}`",
        "",
        f"- Recipes: {report['counts']['recipes']}",
        f"- Tech: {report['counts']['tech']}",
        f"- Quests by family: {report['counts']['quests_by_family']}",
        f"- Dungeons: {report['counts']['dungeons']}/8",
        f"- Rivals: {report['counts']['rivals']}/4",
        f"- Dialogue: {report['counts']['dialogue_lines']}",
        "",
        "## Unreviewed / warnings (separate from errors)",
        "",
    ]
    for item in report.get("unreviewed_items") or []:
        lines.append(f"- {item}")
    for w in report.get("warnings") or []:
        lines.append(f"- warning: {w}")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_report(build_report())
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compile-baseline", action="store_true")
    args = parser.parse_args(argv)
    if args.compile_baseline:
        compiled = compile_baseline_dialogue()
        if not compiled.get("ok"):
            print("compile_baseline: FAIL")
            for e in (compiled.get("validate") or {}).get("errors") or []:
                print(f"  ERROR: {e}")
            return 1
    report = validate_corpus()
    if args.write:
        write_coverage(report)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        status = "PASS" if report["ok"] else "FAIL"
        print(f"validate_content: {status} dialogue={report['counts']['dialogue_lines']} "
              f"quests={report['counts']['quests_by_family']} dungeons={report['counts']['dungeons']} "
              f"rivals={report['counts']['rivals']}")
        for err in report["errors"]:
            print(f"  ERROR: {err}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
