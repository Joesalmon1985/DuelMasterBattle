#!/usr/bin/env python3
"""Compile content sources into immutable packs (C13 / T094 / T133).

Dialogue: production pack = top-level dialogue only (normal + rockfall +
invalidation). Archived shortage/aspect banks remain under archive/.

General packs: quests/batches/rivals/dungeons compile into compiled/manifest.json
only after validation; a failed compile leaves the prior manifest intact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "godot_project" / "content" / "source" / "dialogue"
COMPILED = ROOT / "godot_project" / "content" / "compiled" / "dialogue"
COMPILED_ROOT = ROOT / "godot_project" / "content" / "compiled"
CONTENT_MANIFEST = COMPILED_ROOT / "manifest.json"
QUESTS_SOURCE = ROOT / "godot_project" / "content" / "source" / "quests"
BATCHES_SOURCE = ROOT / "godot_project" / "content" / "source" / "batches"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.content.validate import load_bank, validate_bank, validate_dialogue_integrity  # noqa: E402


def _digest(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(path.parent), delete=False, suffix=".tmp"
    ) as tmp:
        tmp.write(json.dumps(payload, indent=2) + "\n")
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def compile_dialogue() -> dict:
    lines = load_bank(include_archive=False)
    report = validate_bank(lines, production=True)
    if not report["ok"]:
        return {"ok": False, "validate": report}

    COMPILED.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "pack_id": "dialogue.g05_production",
        "line_count": len(lines),
        "lines": lines,
        "provenance": {
            "source": "godot_project/content/source/dialogue/*.json",
            "archived": "godot_project/content/source/dialogue/archive/",
            "validator": "tools.content.validate",
            "scopes": ["normal", "rockfall", "soldier"],
        },
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    payload["content_hash"] = digest
    out = COMPILED / "mvp_pack.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    # Keep a historical archive pack for tooling that still wants the old corpus.
    archive_lines = load_bank(include_archive=True)
    archive_payload = {
        "schema_version": 1,
        "pack_id": "dialogue.archive_full",
        "line_count": len(archive_lines),
        "lines": archive_lines,
    }
    archive_raw = json.dumps(archive_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    archive_payload["content_hash"] = hashlib.sha256(archive_raw).hexdigest()
    (COMPILED / "archive_full_pack.json").write_text(
        json.dumps(archive_payload, indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "active_pack": "mvp_pack.json",
        "content_hash": digest,
        "line_count": len(lines),
        "archive_pack": "archive_full_pack.json",
        "archive_line_count": len(archive_lines),
        "production_scopes": ["normal", "rockfall", "soldier"],
    }
    (COMPILED / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "validate": report, "manifest": manifest, "path": str(out)}


def compile_baseline_dialogue() -> dict:
    """Compile G08 baseline dialogue (≥1200 lines) into an immutable pack."""
    lines = load_bank(include_baseline=True)
    # Production top-level + baseline; integrity on full set.
    report = validate_dialogue_integrity(lines)
    if report["line_count"] < 1200:
        report["ok"] = False
        report["errors"].append("baseline bank must have ≥1200 useful lines")
    if not report["ok"]:
        return {"ok": False, "validate": report}

    COMPILED.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "pack_id": "dialogue.g08_baseline",
        "line_count": len(lines),
        "lines": lines,
        "provenance": {
            "source": "godot_project/content/source/dialogue/**/*.json",
            "baseline": "godot_project/content/source/dialogue/baseline/",
            "validator": "tools.content.validate.validate_dialogue_integrity",
        },
    }
    digest = _digest({k: v for k, v in payload.items() if k != "lines"})
    # Hash includes lines for immutability.
    payload["content_hash"] = _digest(payload)
    out = COMPILED / "baseline_pack.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    # Update dialogue manifest with baseline pointer without disturbing active_pack.
    manifest_path = COMPILED / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {"active_pack": "mvp_pack.json"}
    manifest["baseline_pack"] = "baseline_pack.json"
    manifest["baseline_line_count"] = len(lines)
    manifest["baseline_content_hash"] = payload["content_hash"]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "validate": report, "manifest": manifest, "path": str(out), "content_hash": payload["content_hash"]}


def _collect_quest_templates() -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []
    if not QUESTS_SOURCE.is_dir():
        return templates
    for path in sorted(QUESTS_SOURCE.glob("*/*.json")):
        if path.name.startswith("_"):
            continue
        if "archive" in path.parts:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "id" not in data:
            continue
        rec = dict(data)
        rec["_source"] = str(path.relative_to(ROOT))
        templates.append(rec)
    return templates


def validate_content_pack(templates: list[dict[str, Any]], batches: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    for tpl in templates:
        tid = str(tpl.get("id") or "")
        if not tid:
            errors.append("quest template missing id")
            continue
        solutions = list(tpl.get("solutions") or [])
        if len(solutions) < 2:
            errors.append(f"{tid}: need ≥2 solutions")
        for key in ("world_resolved_route", "invalid_target_route"):
            if key not in tpl:
                errors.append(f"{tid}: missing {key}")
        statuses = set(tpl.get("statuses") or [])
        for required in ("completed", "resolved_by_world", "failed_with_consequence"):
            if required not in statuses:
                errors.append(f"{tid}: missing status {required}")
    for batch in batches:
        from tools.content.make_batch import validate_batch

        report = validate_batch(batch)
        if not report["ok"]:
            errors.extend(f"batch {batch.get('id')}: {e}" for e in report["errors"])
    return {"ok": not errors, "errors": errors}


def compile_content_pack(*, include_dialogue: bool = True) -> dict[str, Any]:
    """Validate then atomically switch compiled/manifest.json."""
    prior = None
    prior_hash = None
    if CONTENT_MANIFEST.is_file():
        prior = json.loads(CONTENT_MANIFEST.read_text(encoding="utf-8"))
        prior_hash = prior.get("content_hash")

    templates = _collect_quest_templates()
    batches: list[dict[str, Any]] = []
    if BATCHES_SOURCE.is_dir():
        for path in sorted(BATCHES_SOURCE.glob("*.json")):
            batches.append(json.loads(path.read_text(encoding="utf-8")))

    report = validate_content_pack(templates, batches)
    if not report["ok"]:
        return {
            "ok": False,
            "validate": report,
            "prior_manifest_intact": True,
            "prior_manifest_hash": prior_hash,
            "written": False,
        }

    dialogue_result = None
    if include_dialogue:
        dialogue_result = compile_dialogue()
        if not dialogue_result.get("ok"):
            return {
                "ok": False,
                "validate": dialogue_result.get("validate"),
                "prior_manifest_intact": True,
                "prior_manifest_hash": prior_hash,
                "written": False,
                "dialogue": dialogue_result,
            }

    rivals_dir = ROOT / "godot_project" / "content" / "source" / "rivals"
    rivals = []
    if rivals_dir.is_dir():
        for path in sorted(rivals_dir.glob("*.json")):
            rivals.append(json.loads(path.read_text(encoding="utf-8")))

    dungeons_dir = ROOT / "godot_project" / "content" / "source" / "dungeons"
    dungeons = []
    if dungeons_dir.is_dir():
        for layout in sorted(dungeons_dir.glob("*/layout.json")):
            dungeons.append(json.loads(layout.read_text(encoding="utf-8")))

    payload = {
        "schema_version": 1,
        "pack_id": "content.g08_baseline",
        "quests": [{"id": t["id"], "family": t.get("family"), "source": t.get("_source")} for t in templates],
        "quest_count": len(templates),
        "batches": [{"id": b.get("id"), "hash": b.get("content_hash")} for b in batches],
        "rivals": [{"id": r.get("id")} for r in rivals],
        "dungeons": [{"id": d.get("id")} for d in dungeons],
        "dialogue_manifest": (dialogue_result or {}).get("manifest"),
        "provenance": {
            "validator": "tools.content.compile",
            "api_dependency": False,
        },
    }
    payload["content_hash"] = _digest(payload)
    _atomic_write_json(CONTENT_MANIFEST, payload)
    pack_dir = COMPILED_ROOT / "packs"
    pack_dir.mkdir(parents=True, exist_ok=True)
    pack_path = pack_dir / f"{payload['content_hash'][:16]}.json"
    _atomic_write_json(pack_path, payload)
    return {
        "ok": True,
        "validate": report,
        "manifest": payload,
        "path": str(CONTENT_MANIFEST),
        "prior_manifest_hash": prior_hash,
        "written": True,
        "dialogue": dialogue_result,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--pack",
        choices=("dialogue", "content", "baseline", "all"),
        default="dialogue",
        help="dialogue (default, T094 compat), content, baseline, or all",
    )
    args = parser.parse_args(argv)
    if args.pack == "dialogue":
        result = compile_dialogue()
        label = "compile_dialogue"
    elif args.pack == "baseline":
        result = compile_baseline_dialogue()
        label = "compile_baseline"
    elif args.pack == "content":
        result = compile_content_pack(include_dialogue=False)
        label = "compile_content"
    else:
        dialogue = compile_dialogue()
        baseline = compile_baseline_dialogue()
        content = compile_content_pack(include_dialogue=False)
        result = {
            "ok": dialogue.get("ok") and baseline.get("ok") and content.get("ok"),
            "validate": {
                "errors": (
                    list((dialogue.get("validate") or {}).get("errors") or [])
                    + list((baseline.get("validate") or {}).get("errors") or [])
                    + list((content.get("validate") or {}).get("errors") or [])
                )
            },
            "manifest": content.get("manifest"),
            "dialogue": dialogue,
            "baseline": baseline,
        }
        label = "compile_all"

    if args.json:
        printable = {k: v for k, v in result.items() if k not in {"dialogue"}}
        if result.get("dialogue"):
            printable["dialogue_ok"] = result["dialogue"].get("ok")
        print(json.dumps(printable, indent=2, default=str))
    else:
        status = "PASS" if result["ok"] else "FAIL"
        print(f"{label}: {status}")
        if result["ok"]:
            manifest = result.get("manifest") or {}
            digest = str(manifest.get("content_hash") or "")[:12]
            if args.pack == "dialogue":
                print(
                    f"  hash={digest} "
                    f"lines={manifest.get('line_count')} "
                    f"archive={manifest.get('archive_line_count')}"
                )
            else:
                print(
                    f"  hash={digest} quests={manifest.get('quest_count')} "
                    f"rivals={len(manifest.get('rivals') or [])} "
                    f"dungeons={len(manifest.get('dungeons') or [])}"
                )
        else:
            for err in result.get("validate", {}).get("errors", []):
                print(f"  ERROR: {err}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
