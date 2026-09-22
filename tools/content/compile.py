#!/usr/bin/env python3
"""Compile dialogue sources into an immutable content pack (C13 / T094).

Production pack = top-level dialogue only (normal + rockfall + invalidation).
Archived shortage/aspect banks remain under archive/ for history/tests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "godot_project" / "content" / "source" / "dialogue"
COMPILED = ROOT / "godot_project" / "content" / "compiled" / "dialogue"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.content.validate import load_bank, validate_bank  # noqa: E402


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = compile_dialogue()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        status = "PASS" if result["ok"] else "FAIL"
        print(f"compile_dialogue: {status}")
        if result["ok"]:
            print(
                f"  hash={result['manifest']['content_hash'][:12]} "
                f"lines={result['manifest']['line_count']} "
                f"archive={result['manifest']['archive_line_count']}"
            )
        else:
            for err in result.get("validate", {}).get("errors", []):
                print(f"  ERROR: {err}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
