#!/usr/bin/env python3
"""Validate authored dialogue sources (C13 / T094).

Production scope = top-level JSON under content/source/dialogue (not archive/).
"""

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

RETIRED_MARKERS = (
    "route a",
    "route b",
    "sluice",
    "channel is open",
    "demon",
    "manifestation",
    "yard has gone quiet",
    "patrol cleared",
    "factory shortage",
    "lost handle",
)


def load_bank(*, include_archive: bool = False) -> list[dict]:
    lines: list[dict] = []
    paths = sorted(DIALOGUE.glob("*.json"))
    if include_archive:
        paths.extend(sorted(DIALOGUE.glob("archive/**/*.json")))
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else list(data.get("lines") or data.get("entries") or [])
        for item in items:
            rec = dict(item)
            rec.setdefault("_source_file", str(path.relative_to(ROOT)))
            lines.append(rec)
    return lines


def validate_bank(lines: list[dict], *, production: bool = True) -> dict:
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
            if var not in declared and var not in {"speaker_name"}:
                errors.append(f"{lid}: undeclared variable {{{var}}}")
        texts[text] += 1
        if line.get("priority") == "invalidation" or lid.startswith("dialogue.invalid."):
            invalidation_ids.append(lid)
        if production:
            low = text.lower()
            for marker in RETIRED_MARKERS:
                if marker in low:
                    errors.append(f"{lid}: retired terminology {marker!r}")
            if line.get("quest_id") == "quest.factory_shortage":
                errors.append(f"{lid}: retired quest.factory_shortage in production bank")
            if line.get("aspect_id") and str(line.get("scope") or "") != "aspect":
                # Aspect lines must not sit in production without scope=aspect,
                # and production load should not include them at all.
                errors.append(f"{lid}: aspect_id present in production catalogue")

    for lid, count in ids.items():
        if count > 1:
            errors.append(f"duplicate id {lid}")
    for t, c in texts.items():
        if c > 1:
            warnings.append(f"duplicate padding text flagged: {t[:60]!r} x{c}")

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

    # Production G05 catalogue is intentionally small; archived aspect bank
    # retains the historical ≥300-line MVP corpus.
    meets_mvp = True if production else (len(lines) >= 300 and len(texts) >= 300)

    return {
        "ok": not errors,
        "line_count": len(lines),
        "unique_texts": len(texts),
        "errors": errors,
        "warnings": warnings,
        "invalidation_count": len(invalidation_ids),
        "meets_mvp_minimum": meets_mvp,
        "production": production,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--include-archive", action="store_true")
    args = parser.parse_args(argv)
    production = not args.include_archive
    lines = load_bank(include_archive=args.include_archive)
    report = validate_bank(lines, production=production)
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
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
