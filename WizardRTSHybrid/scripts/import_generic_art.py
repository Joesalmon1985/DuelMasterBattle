"""Add art for newly runnable Widelands buildings and workers without rebuilding the whole art folder.

import_assets.py wipes and rebuilds godot_project/client/hybrid/art (and needs the OpenRA content packages, which only the
Windows machine has). After widelands_defs.json gains runnable buildings, this script imports just the missing generic sprites
(`generic_items()`) and merges them into catalogue.json. Run: python3 scripts/import_generic_art.py
"""
from __future__ import annotations
import sys as _sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from wizard_rts import freeze_guard  # noqa: E402  (content is frozen: D33)
freeze_guard.require_unfreeze(__file__)

import importlib.util
import json
import sys
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("import_assets", HYB / "scripts" / "import_assets.py")
ia = importlib.util.module_from_spec(spec)
sys.modules["import_assets"] = ia
spec.loader.exec_module(ia)
CAT = ia.ART / "catalogue.json"


def main() -> None:
    cat = json.loads(CAT.read_text(encoding="utf-8"))
    have = {i["id"] for i in cat["items"]}
    missing_sources = 0
    new = []
    for item in ia.generic_items():
        if item["id"] not in have:
            new.append(item)
    cat["items"].extend(new)
    CAT.write_text(json.dumps(cat, indent=1), encoding="utf-8")
    print(f"generic art: {len(new)} new items merged ({len(cat['items'])} total)")


if __name__ == "__main__":
    main()
