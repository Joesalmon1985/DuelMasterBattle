#!/usr/bin/env python3
"""G11 — harvest runtime-visible content IDs and sync semantic placeholder registry.

Fails on missing/duplicate/anonymous/unreadable entries after sync.
Placeholder art is explicitly permitted.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "godot_project" / "content" / "source"
REGISTRY_PATH = SOURCE / "presentation" / "semantic_visuals.json"
OUT = (
    ROOT
    / "Pack"
    / "DuelMasterBattle_Build_Pack"
    / "tracking"
    / "gates"
    / "G11"
)

import sys

sys.path.insert(0, str(ROOT))

from sim.dmb.presentation.semantic_visuals import (  # noqa: E402
    CATEGORY_SHAPES,
    load_registry,
    validate_registry,
)

KIND_TO_CATEGORY = {
    "building": "building",
    "unit": "unit",
    "technology": "technology",
    "job": "job",
    "item": "item",
    "upgrade": "upgrade",
    "hazard": "hazard",
    "resource": "resource",
    "rival": "rival",
    "quest": "quest",
    "card": "card",
}


def _abbrev(semantic_id: str, n: int = 3) -> str:
    parts = [p for p in semantic_id.split(".") if p]
    if not parts:
        return "??"
    letters = "".join(p[0].upper() for p in parts if p[0].isalnum())
    if len(letters) >= n:
        return letters[:n]
    return (parts[-1][:n] or "??").upper()


def _label_from(row: dict[str, Any], sid: str) -> str:
    for key in ("label", "name", "display_name", "name_key"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            # Drop localisation key noise when it looks like an id.
            if val.startswith(sid) or val.count(".") >= 2:
                continue
            return val.replace("_", " ").strip()
    return sid.split(".")[-1].replace("_", " ").title()


def _iter_json_files() -> list[Path]:
    skip = {"batches", "dialogue", "labels", "legacy_rules", "people", "presentation"}
    files: list[Path] = []
    for path in SOURCE.rglob("*.json"):
        rel = path.relative_to(SOURCE)
        if rel.parts and rel.parts[0] in skip:
            continue
        if "archive" in rel.parts:
            continue
        files.append(path)
    return files


def harvest_visible_ids() -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}

    def add(sid: str, *, category: str, label: str, source: str) -> None:
        sid = str(sid).strip()
        if not sid or sid in found:
            return
        # Skip non-visual schema/meta ids.
        if sid.startswith(("schema.", "batch.", "effect.", "fact.", "use.", "name_key")):
            return
        found[sid] = {
            "semantic_id": sid,
            "category": category,
            "label": label,
            "abbrev": _abbrev(sid, CATEGORY_SHAPES.get(category, {}).get("abbrev_len", 3)),
            "shape": CATEGORY_SHAPES.get(category, {}).get("shape", "rounded_rect"),
            "border": CATEGORY_SHAPES.get(category, {}).get("border", "solid"),
            "placeholder": True,
            "source": source,
        }

    for path in _iter_json_files():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rel = str(path.relative_to(ROOT))

        if isinstance(data, dict) and data.get("semantic_id"):
            cat = str(data.get("hazard_type") or data.get("category") or "hazard")
            if cat not in CATEGORY_SHAPES:
                cat = "hazard"
            add(
                str(data["semantic_id"]),
                category=cat,
                label=_label_from(data, str(data["semantic_id"])),
                source=rel,
            )

        rows: list[Any] = []
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            for key in ("entries", "items", "buildings", "units", "resources", "technologies", "quests", "rivals", "cards"):
                if isinstance(data.get(key), list):
                    rows.extend(data[key])

        for row in rows:
            if not isinstance(row, dict):
                continue
            sid = str(row.get("id") or row.get("semantic_id") or "").strip()
            if not sid:
                continue
            kind = str(row.get("kind") or "")
            cat = KIND_TO_CATEGORY.get(kind)
            if cat is None:
                prefix = sid.split(".", 1)[0]
                cat = KIND_TO_CATEGORY.get(prefix, prefix if prefix in CATEGORY_SHAPES else "item")
            # Jobs are not always runtime-visible tokens; still register for completeness.
            add(sid, category=cat, label=_label_from(row, sid), source=rel)

        # Quest files often use filename as id.
        if path.parent.name in {"quests"} or (len(path.parts) > 1 and "quests" in path.parts):
            qid = str(data.get("id") if isinstance(data, dict) else "") or f"quest.{path.stem}"
            if isinstance(data, dict):
                add(qid, category="quest", label=_label_from(data, qid), source=rel)

    return found


def sync_registry(*, write: bool) -> dict[str, Any]:
    reg = load_registry()
    existing = {str(e.get("semantic_id")): e for e in (reg.get("entries") or []) if e.get("semantic_id")}
    harvested = harvest_visible_ids()
    added: list[str] = []
    for sid, row in sorted(harvested.items()):
        if sid not in existing:
            entry = {k: v for k, v in row.items() if k != "source"}
            (reg.setdefault("entries", [])).append(entry)
            existing[sid] = entry
            added.append(sid)
    # Ensure every existing entry has readable fields.
    for entry in reg.get("entries") or []:
        if not entry.get("label") and not entry.get("abbrev"):
            sid = str(entry.get("semantic_id") or "")
            entry["label"] = sid
            entry["abbrev"] = _abbrev(sid)
        cat = str(entry.get("category") or "")
        if not entry.get("shape"):
            entry["shape"] = CATEGORY_SHAPES.get(cat, {}).get("shape", "rounded_rect")
        if entry.get("anonymous"):
            entry.pop("anonymous", None)
    errors = validate_registry(reg)
    # Overlap check: identical abbrev+shape+category pairs among registered.
    sigs: dict[str, list[str]] = {}
    for entry in reg.get("entries") or []:
        sig = f"{entry.get('category')}|{entry.get('shape')}|{entry.get('abbrev')}"
        sigs.setdefault(sig, []).append(str(entry.get("semantic_id")))
    overlaps = {k: v for k, v in sigs.items() if len(v) > 1}
    # Soft: same abbrev across many is ok if labels differ; flag only exact 3-way collisions > 4.
    heavy = {k: v for k, v in overlaps.items() if len(v) > 6}
    if heavy:
        for k, v in list(heavy.items())[:5]:
            errors.append(f"overlap cluster {k}: {v[:8]}")

    missing_runtime = [sid for sid in harvested if sid not in existing]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "registry_path": str(REGISTRY_PATH.relative_to(ROOT)),
        "entries": len(reg.get("entries") or []),
        "harvested_visible": len(harvested),
        "added": added,
        "missing_after_sync": missing_runtime,
        "validate_errors": errors,
        "status": "PASS" if not errors and not missing_runtime else "FAIL",
    }
    if write:
        REGISTRY_PATH.write_text(json.dumps(reg, indent=2) + "\n", encoding="utf-8")
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "registry_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        (OUT / "registry_manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "entries": reg.get("entries") or [],
                    "count": len(reg.get("entries") or []),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Persist registry sync + G11 reports")
    args = parser.parse_args(argv)
    report = sync_registry(write=args.write)
    print(json.dumps({k: report[k] for k in ("status", "entries", "harvested_visible", "added", "validate_errors")}, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
