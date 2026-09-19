#!/usr/bin/env python3
"""Validate authored dialogue sources (C13 / T094)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIALOGUE = ROOT / "godot_project" / "content" / "source" / "dialogue"

PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")
UNKNOWN_FACT_RE = re.compile(r"\b(TODO|TBD|UNKNOWN_FACT|lorem ipsum)\b", re.I)


def load_bank() -> list[dict]:
    path = DIALOGUE / "mvp_bank.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return list(data.get("lines") or data.get("entries") or [])
    return list(data)


def validate_bank(lines: list[dict]) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    texts = Counter()
    ids = Counter()
    invalidation_ids = []
    for line in lines:
        lid = str(line.get("id") or "")
        text = str(line.get("text") or "")
        if not lid:
            errors.append("line missing id")
            continue
        ids[lid] += 1
        if not text.strip():
            errors.append(f"{lid}: empty text")
        if not line.get("fallback"):
            errors.append(f"{lid}: missing fallback")
        if UNKNOWN_FACT_RE.search(text):
            errors.append(f"{lid}: unknown/placeholder fact language")
        for var in PLACEHOLDER_RE.findall(text):
            declared = (line.get("variables") or {}) if isinstance(line.get("variables"), dict) else {}
            # Allow known_name style without full schema when fallback exists.
            if var not in declared and var not in {"speaker_name"}:
                errors.append(f"{lid}: undeclared variable {{{var}}}")
        texts[text] += 1
        if line.get("priority") == "invalidation" or lid.startswith("dialogue.invalid."):
            invalidation_ids.append(lid)

    for lid, count in ids.items():
        if count > 1:
            errors.append(f"duplicate id {lid}")
    padding = [t for t, c in texts.items() if c > 1]
    for t in padding:
        warnings.append(f"duplicate padding text flagged: {t[:60]!r} x{texts[t]}")

    required_invalidations = {
        "dialogue.invalid.missing_cause",
        "dialogue.invalid.dead_speaker",
        "dialogue.invalid.destroyed_site",
        "dialogue.invalid.wrong_era",
        "dialogue.invalid.unknown_fact",
        "dialogue.invalid.quest_complete",
        "dialogue.invalid.softlock_recovery",
    }
    missing_inv = required_invalidations - set(invalidation_ids)
    for mid in sorted(missing_inv):
        errors.append(f"missing invalidation line {mid}")

    return {
        "ok": not errors,
        "line_count": len(lines),
        "unique_texts": len(texts),
        "errors": errors,
        "warnings": warnings,
        "invalidation_count": len(invalidation_ids),
        "meets_mvp_minimum": len(lines) >= 300 and len(texts) >= 300,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = validate_bank(load_bank())
    if not report["meets_mvp_minimum"]:
        report["ok"] = False
        report["errors"].append("MVP bank must have ≥300 unique useful lines")
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        status = "PASS" if report["ok"] else "FAIL"
        print(f"validate_dialogue: {status} lines={report['line_count']} unique={report['unique_texts']}")
        for err in report["errors"]:
            print(f"  ERROR: {err}")
        for warn in report["warnings"][:10]:
            print(f"  WARN: {warn}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
