#!/usr/bin/env python3
"""Offline content authoring batch builder (C13 / T133).

Accepts 25–50-line structured authoring batches, tracks provenance/schema/hash,
and refuses to mutate the compiled manifest when validation fails.
No paid API or runtime credentials required.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BATCH_DIR = ROOT / "godot_project" / "content" / "source" / "batches"
COMPILED_MANIFEST = ROOT / "godot_project" / "content" / "compiled" / "manifest.json"
SCHEMA_VERSION = 1
VALIDATOR_VERSION = "content.batch.v1"
MIN_LINES = 25
MAX_LINES = 50

ALLOWED_EFFECT_KINDS = {
    "quest_accept",
    "quest_complete",
    "quest_fail",
    "grant_item",
    "set_flag",
    "clear_cause",
    "open_route",
    "dialogue_advance",
    "boulder_quest_accept",
    "noop",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _digest(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _load_prior_manifest() -> dict[str, Any] | None:
    if not COMPILED_MANIFEST.is_file():
        return None
    return json.loads(COMPILED_MANIFEST.read_text(encoding="utf-8"))


def validate_batch(batch: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if int(batch.get("schema_version") or 0) != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    batch_id = str(batch.get("id") or "").strip()
    if not batch_id:
        errors.append("batch missing id")
    lines = list(batch.get("lines") or [])
    if not (MIN_LINES <= len(lines) <= MAX_LINES):
        errors.append(f"batch must contain {MIN_LINES}-{MAX_LINES} lines, got {len(lines)}")
    seen_ids: set[str] = set()
    for i, line in enumerate(lines):
        lid = str(line.get("id") or "").strip()
        text = str(line.get("text") or "").strip()
        if not lid:
            errors.append(f"line[{i}] missing id")
            continue
        if lid in seen_ids:
            errors.append(f"duplicate line id {lid}")
        seen_ids.add(lid)
        if not text:
            errors.append(f"{lid}: empty text")
        if not line.get("fallback"):
            errors.append(f"{lid}: missing fallback")
        for choice in line.get("choices") or []:
            effects = choice.get("effects") or []
            if not effects and not choice.get("next"):
                errors.append(f"{lid}/{choice.get('id')}: choice has no outcome")
            for effect in effects:
                kind = str(effect.get("kind") or "")
                if kind and kind not in ALLOWED_EFFECT_KINDS:
                    errors.append(f"{lid}: unsupported effect kind {kind!r}")
                if effect.get("fact") == "UNKNOWN_FACT":
                    errors.append(f"{lid}: unknown fact blocked")
        for var in (line.get("variables") or {}):
            if not isinstance(var, str):
                errors.append(f"{lid}: variable keys must be strings")
    if not batch.get("provenance"):
        warnings.append("missing provenance block")
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "line_count": len(lines),
        "batch_id": batch_id,
    }


def make_batch(
    *,
    batch_id: str,
    lines: list[dict[str, Any]],
    templates: list[str] | None = None,
    profiles: list[str] | None = None,
    roles: list[str] | None = None,
    facts: dict[str, Any] | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Build a GenerationBatch record and optionally persist it under source/batches."""
    prior = _load_prior_manifest()
    batch = {
        "schema_version": SCHEMA_VERSION,
        "id": batch_id,
        "requested_templates": list(templates or []),
        "requested_profiles": list(profiles or []),
        "requested_roles": list(roles or []),
        "known_facts": dict(facts or {}),
        "allowed_vocabulary": ["settlement", "route", "cause", "rival", "era"],
        "allowed_effects": sorted(ALLOWED_EFFECT_KINDS),
        "expected_output_schema": "dialogue_line.v1",
        "maximum_lines": MAX_LINES,
        "minimum_lines": MIN_LINES,
        "validator_version": VALIDATOR_VERSION,
        "provenance": {
            "authored_at": _now(),
            "authoring_mode": "file",
            "api_dependency": False,
            "credentials": None,
        },
        "lines": lines,
    }
    report = validate_batch(batch)
    result = {
        "ok": report["ok"],
        "validate": report,
        "batch": batch,
        "content_hash": _digest(batch) if report["ok"] else None,
        "prior_manifest_intact": True,
        "prior_manifest_hash": (prior or {}).get("content_hash"),
    }
    if not report["ok"]:
        # Failed batch must leave prior compiled manifest untouched.
        result["written"] = False
        return result
    if write:
        BATCH_DIR.mkdir(parents=True, exist_ok=True)
        out = BATCH_DIR / f"{batch_id}.json"
        payload = dict(batch)
        payload["content_hash"] = result["content_hash"]
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        result["path"] = str(out.relative_to(ROOT))
        result["written"] = True
    return result


def _demo_lines(n: int = 30) -> list[dict[str, Any]]:
    lines = []
    for i in range(n):
        lines.append(
            {
                "schema_version": 1,
                "id": f"dialogue.batch.demo.{i:03d}",
                "scope": "normal",
                "speaker_role": "worker",
                "era_id": "prehistoric" if i % 2 == 0 else "historic",
                "text": f"Authoring sample line {i}: the settlement still needs careful hands.",
                "fallback": "They nod.",
                "choices": [
                    {
                        "id": f"ack_{i}",
                        "label": "Understood",
                        "effects": [{"kind": "noop", "effect_id": f"effect.batch.demo.{i}"}],
                    }
                ],
                "priority": "authored",
            }
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", default="batch.demo.g08")
    parser.add_argument("--from-file", type=Path, help="Load batch JSON instead of demo lines")
    parser.add_argument("--demo", action="store_true", help="Write a valid 30-line demo batch")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.from_file:
        data = json.loads(args.from_file.read_text(encoding="utf-8"))
        result = make_batch(
            batch_id=str(data.get("id") or args.id),
            lines=list(data.get("lines") or []),
            templates=list(data.get("requested_templates") or []),
            profiles=list(data.get("requested_profiles") or []),
            roles=list(data.get("requested_roles") or []),
            facts=dict(data.get("known_facts") or {}),
            write=not args.dry_run,
        )
    elif args.demo:
        result = make_batch(batch_id=args.id, lines=_demo_lines(30), write=not args.dry_run)
    else:
        parser.error("provide --demo or --from-file")
        return 2

    if args.json:
        printable = {k: v for k, v in result.items() if k != "batch"}
        printable["batch_id"] = result["batch"]["id"]
        printable["line_count"] = len(result["batch"]["lines"])
        print(json.dumps(printable, indent=2))
    else:
        status = "PASS" if result["ok"] else "FAIL"
        print(f"make_batch: {status} id={result['batch']['id']} lines={len(result['batch']['lines'])}")
        for err in result["validate"]["errors"]:
            print(f"  ERROR: {err}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
