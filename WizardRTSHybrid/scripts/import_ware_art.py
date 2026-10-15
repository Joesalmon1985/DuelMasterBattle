"""Merge the Widelands ware icons, the burning-building sheet and the ashes into the art catalogue.

Wares: data/tribes/wares/<ware>/idle_1.png (the in-world carried picture). The simulation names the sawmill output `plank`,
Widelands calls the ware directory `planks`; ALIASES maps the few such differences.
Burning building: data/tribes/immovables/destroyed_building (10 frames, 90x76, hotspot 43,60), then data/tribes/immovables/ashes.
Run: python3 scripts/import_ware_art.py   (needs the sparse checkout to include /data/tribes/wares/ and /data/tribes/immovables/)
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
ALIASES = {"plank": "planks", "bread": "bread_barbarians"}


def main() -> None:
    defs = json.loads((HYB / "wizard_rts" / "data" / "widelands_defs.json").read_text(encoding="utf-8"))
    names = sorted(set(defs["wares"]) | set(ALIASES))
    new, missing = [], []
    for ware in names:
        folder = ALIASES.get(ware, ware)
        rel = next((r for r in (f"data/tribes/wares/{folder}/idle_1.png", f"data/tribes/wares/{folder}/idle.png") if ia.wl(r).exists()), "")
        if not rel:
            missing.append(ware)
            continue
        w, h = ia.png_size(ia.wl(rel))
        new.append(
            ia.sheet(
                f"widelands.ware.{ware}", rel, f"ware_{ware}.png",
                columns=1, rows=1, frames=1, hotspot=[w // 2, h // 2], scale=2, fps=0,
                source_note=f"{folder} ware animations.idle",
            )
        )
    new.append(
        ia.sheet(
            "widelands.destroyed_building", "data/tribes/immovables/destroyed_building/idle_1.png", "destroyed_building.png",
            columns=10, rows=1, frames=10, hotspot=[43, 60], scale=2, fps=10,
            source_note="destroyed_building spritesheets.idle (burning, 10 frames at 10 fps)",
        )
    )
    new.append(
        ia.sheet(
            "widelands.ashes", "data/tribes/immovables/ashes/idle_1.png", "ashes.png",
            columns=1, rows=1, frames=1, hotspot=[43, 60], scale=2, fps=0,
            source_note="ashes animations.idle",
        )
    )
    ids = {i["id"] for i in new}
    cat = json.loads(CAT.read_text(encoding="utf-8"))
    cat["items"] = [i for i in cat["items"] if i["id"] not in ids] + new
    CAT.write_text(json.dumps(cat, indent=1), encoding="utf-8")
    print(f"ware art: {len(new)} items merged, no sprite for: {missing}")


if __name__ == "__main__":
    main()
