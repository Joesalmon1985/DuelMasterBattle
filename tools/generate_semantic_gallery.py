#!/usr/bin/env python3
"""T162 — generate semantic placeholder gallery catalogue (montages + index)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sim.dmb.presentation.semantic_visuals import load_registry, resolve_visual  # noqa: E402

OUT = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking" / "gates" / "G11"


def main() -> int:
    reg = load_registry()
    entries = reg.get("entries") or []
    gallery = []
    by_cat: dict[str, list[str]] = {}
    for row in entries:
        sid = str(row.get("semantic_id") or "")
        desc = resolve_visual(sid, reg)
        gallery.append(
            {
                "semantic_id": sid,
                "category": desc.get("category"),
                "label": desc.get("label"),
                "abbrev": desc.get("abbrev"),
                "shape": desc.get("shape"),
                "border": desc.get("border"),
                "registered": desc.get("registered"),
            }
        )
        by_cat.setdefault(str(desc.get("category")), []).append(sid)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "gallery").mkdir(parents=True, exist_ok=True)
    index = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(gallery),
        "categories": {k: len(v) for k, v in sorted(by_cat.items())},
        "entries": gallery,
        "notes": (
            "Catalogue index for owner review. Headed Godot gallery frames may be "
            "attached later; semantic descriptors are the objective completeness proof."
        ),
    }
    (OUT / "gallery" / "catalogue_index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    # Lightweight textual montage for morning review without inventing PNGs.
    lines = ["# Semantic placeholder catalogue", "", f"Entries: {len(gallery)}", ""]
    for cat, sids in sorted(by_cat.items()):
        lines.append(f"## {cat} ({len(sids)})")
        for sid in sids[:40]:
            desc = resolve_visual(sid, reg)
            lines.append(f"- `{sid}` — {desc.get('abbrev')} / {desc.get('shape')} — {desc.get('label')}")
        if len(sids) > 40:
            lines.append(f"- … {len(sids) - 40} more")
        lines.append("")
    (OUT / "gallery" / "catalogue_montage.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"status": "PASS", "count": len(gallery), "out": str((OUT / 'gallery').relative_to(ROOT))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
