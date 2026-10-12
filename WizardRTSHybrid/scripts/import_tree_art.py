"""Add the other Widelands summer tree species to the art catalogue without touching anything else.

import_assets.py rebuilds the whole art folder (and needs the OpenRA content packages, which only the Windows machine has),
so this script merges just the species sheets into catalogue.json. Run: python3 scripts/import_tree_art.py
"""
from __future__ import annotations

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
    new = ia.species_items()
    ids = {i["id"] for i in new}
    cat["items"] = [i for i in cat["items"] if i["id"] not in ids] + new
    CAT.write_text(json.dumps(cat, indent=1), encoding="utf-8")
    print(f"tree species art: {len(new)} items merged into {CAT}")


if __name__ == "__main__":
    main()
