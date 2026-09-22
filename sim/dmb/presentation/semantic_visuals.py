"""Semantic visual registry — placeholder graphics with explicit identity.

Used by runtime presentation and G11 catalogue validation. Placeholder art is
explicitly permitted for the overnight G06→G12 run; anonymous blobs are not.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY = (
    ROOT
    / "godot_project"
    / "content"
    / "source"
    / "presentation"
    / "semantic_visuals.json"
)

# Category → default shape grammar (must remain distinguishable in greyscale).
CATEGORY_SHAPES: dict[str, dict[str, Any]] = {
    "building": {"shape": "rect", "border": "solid", "abbrev_len": 3},
    "upgrade": {"shape": "rect", "border": "double", "abbrev_len": 2},
    "technology": {"shape": "hex", "border": "solid", "abbrev_len": 3},
    "resource": {"shape": "circle", "border": "dotted", "abbrev_len": 2},
    "unit": {"shape": "triangle", "border": "solid", "abbrev_len": 2},
    "hazard": {"shape": "diamond", "border": "solid", "abbrev_len": 2},
    "catastrophe": {"shape": "diamond", "border": "double", "abbrev_len": 2},
    "item": {"shape": "rounded_rect", "border": "solid", "abbrev_len": 3},
    "quest_item": {"shape": "rounded_rect", "border": "dashed", "abbrev_len": 3},
    "relic": {"shape": "star", "border": "solid", "abbrev_len": 2},
    "card": {"shape": "portrait_rect", "border": "solid", "abbrev_len": 3},
    "pollution": {"shape": "blob", "border": "dotted", "abbrev_len": 2},
    "alien": {"shape": "oval", "border": "solid", "abbrev_len": 2},
    "machine": {"shape": "gear", "border": "solid", "abbrev_len": 2},
    "nuclear": {"shape": "trefoil", "border": "solid", "abbrev_len": 2},
}


def load_registry(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_REGISTRY
    if not p.is_file():
        return {"schema_version": 1, "entries": []}
    return json.loads(p.read_text(encoding="utf-8"))


def index_by_id(registry: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    reg = registry if registry is not None else load_registry()
    out: dict[str, dict[str, Any]] = {}
    for row in reg.get("entries") or []:
        sid = str(row.get("semantic_id") or "")
        if sid:
            out[sid] = dict(row)
    return out


def validate_registry(registry: dict[str, Any] | None = None) -> list[str]:
    """Return list of error strings (empty => ok)."""
    reg = registry if registry is not None else load_registry()
    errors: list[str] = []
    seen: set[str] = set()
    for i, row in enumerate(reg.get("entries") or []):
        sid = str(row.get("semantic_id") or "").strip()
        if not sid:
            errors.append(f"entry[{i}]: missing semantic_id")
            continue
        if sid in seen:
            errors.append(f"duplicate semantic_id: {sid}")
        seen.add(sid)
        cat = str(row.get("category") or "")
        if cat not in CATEGORY_SHAPES and not row.get("allow_unknown_category"):
            errors.append(f"{sid}: unknown category {cat!r}")
        label = str(row.get("label") or "").strip()
        abbrev = str(row.get("abbrev") or "").strip()
        if not label and not abbrev:
            errors.append(f"{sid}: needs label or abbrev for readability")
        if row.get("anonymous"):
            errors.append(f"{sid}: anonymous placeholders are forbidden")
        shape = str(row.get("shape") or CATEGORY_SHAPES.get(cat, {}).get("shape") or "")
        if not shape:
            errors.append(f"{sid}: missing shape")
    return errors


def resolve_visual(semantic_id: str, registry: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a draw descriptor for Godot / reports."""
    idx = index_by_id(registry)
    row = idx.get(semantic_id)
    if row is None:
        # Explicit unknown — still identifiable, not an anonymous blob.
        parts = semantic_id.split(".")
        cat = parts[0] if parts else "item"
        shape_meta = CATEGORY_SHAPES.get(cat, {"shape": "rounded_rect", "abbrev_len": 3})
        abbrev = "".join(p[0].upper() for p in parts if p)[: max(2, shape_meta.get("abbrev_len", 3))]
        return {
            "semantic_id": semantic_id,
            "category": cat,
            "label": semantic_id,
            "abbrev": abbrev or "??",
            "shape": shape_meta.get("shape", "rounded_rect"),
            "border": shape_meta.get("border", "dashed"),
            "registered": False,
            "placeholder": True,
        }
    cat = str(row.get("category") or "item")
    shape_meta = CATEGORY_SHAPES.get(cat, {})
    return {
        "semantic_id": semantic_id,
        "category": cat,
        "label": str(row.get("label") or semantic_id),
        "abbrev": str(row.get("abbrev") or ""),
        "shape": str(row.get("shape") or shape_meta.get("shape") or "rounded_rect"),
        "border": str(row.get("border") or shape_meta.get("border") or "solid"),
        "pattern": str(row.get("pattern") or ""),
        "badge": str(row.get("badge") or ""),
        "faction_tint": bool(row.get("faction_tint", False)),
        "registered": True,
        "placeholder": bool(row.get("placeholder", True)),
        "asset_path": str(row.get("asset_path") or ""),
    }
