#!/usr/bin/env python3
"""Compile dialogue sources into an immutable content pack (C13 / T094)."""

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
    lines = load_bank()
    report = validate_bank(lines)
    if not report.get("meets_mvp_minimum"):
        report["ok"] = False
        report.setdefault("errors", []).append("MVP bank must have ≥300 unique useful lines")
    if not report["ok"]:
        return {"ok": False, "validate": report}

    COMPILED.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "pack_id": "dialogue.mvp",
        "line_count": len(lines),
        "lines": lines,
        "provenance": {
            "source": "godot_project/content/source/dialogue/mvp_bank.json",
            "validator": "tools.content.validate",
        },
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    payload["content_hash"] = digest
    out = COMPILED / "mvp_pack.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "active_pack": "mvp_pack.json",
        "content_hash": digest,
        "line_count": len(lines),
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
            print(f"  hash={result['manifest']['content_hash'][:12]} lines={result['manifest']['line_count']}")
        else:
            for err in result.get("validate", {}).get("errors", []):
                print(f"  ERROR: {err}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
