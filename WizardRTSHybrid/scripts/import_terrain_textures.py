"""Copy the Widelands terrain textures used by the generator into the Godot project.

Source: external/widelands/data/world/terrains/<world>/<name>/idle.png (water: water_00.png).
GPL-2.0-or-later, Widelands Development Team (art licences: see docs/LICENSES.md).
Writes godot_project/client/hybrid/art/terrain/<terrain>.png and index.json.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from wizard_rts import mapgen, terrain as T  # noqa: E402

WL = ROOT / "external/widelands/data/world/terrains"
OUT = ROOT.parent / "godot_project/client/hybrid/art/terrain"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    defs = T.defs()["terrains"]
    index = {}
    for name in mapgen.PALETTE:
        d = defs[name]
        folder = WL / d["world"] / d["dir"]
        src = folder / ("water_00.png" if d["is"] == "water" else "idle.png")
        if not src.exists():
            print("missing", src)
            return 1
        shutil.copyfile(src, OUT / f"{name}.png")
        if d["is"] == "water":  # all animation frames (Widelands water_00..31, 14 fps)
            frames = sorted(folder.glob("water_??.png"))
            (OUT / "water").mkdir(exist_ok=True)
            for i, f in enumerate(frames):
                shutil.copyfile(f, OUT / "water" / f"{name}_{i:02d}.png")
            index_frames = len(frames)
        index[name] = {"file": f"{name}.png", "is": d["is"], "source": str(src.relative_to(ROOT / "external/widelands"))}
        if d["is"] == "water":
            index[name]["frames"] = index_frames
    (OUT / "index.json").write_text(json.dumps({"widelands_commit": T.defs()["source"]["commit"], "terrains": index}, indent=1))
    print(f"{len(index)} textures -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
