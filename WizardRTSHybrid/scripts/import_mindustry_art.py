#!/usr/bin/env python3
"""Import Mindustry (v146, pinned in sources/manifest.json) sprites for the blocks and units the hybrid simulates.

Licence: the pinned repository's only licence file is the top-level GPL-3.0 LICENSE, which covers the whole tree including
core/assets-raw (no per-directory asset notices exist at the pin; checked 12 Oct 2026). This project is GPL-3.0-or-later compatible.
Each sprite is the upstream layers composited once (a drill's base + rotator + top; a unit's legs + base + body) into a PNG under
godot_project/client/hybrid/art/mindustry/, recorded in the art catalogue with the upstream paths. Needs the sparse checkout to include
core/assets-raw/sprites/blocks/ (`git -C external/mindustry sparse-checkout add /core/assets-raw/sprites/blocks/`).
Run: python3 scripts/import_mindustry_art.py
"""
from __future__ import annotations
import sys as _sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from wizard_rts import freeze_guard  # noqa: E402  (content is frozen: D33)
freeze_guard.require_unfreeze(__file__)

import json
from pathlib import Path

from PIL import Image

HYB = Path(__file__).resolve().parents[1]
SRC = HYB / "external" / "mindustry" / "core" / "assets-raw" / "sprites"
ART = HYB.parent / "godot_project" / "client" / "hybrid" / "art"
OUT = ART / "mindustry"
CAT = ART / "catalogue.json"
LICENSE = "GPL-3.0 (Anuken/Mindustry v146, repository LICENSE covers core/assets-raw; no separate asset terms at the pin)"
BLOCKS = {  # hybrid kind -> layers bottom to top (relative to sprites/blocks)
    "mechanical_drill": ["drills/mechanical-drill.png", "drills/mechanical-drill-rotator.png", "drills/mechanical-drill-top.png"],
    "pneumatic_drill": ["drills/pneumatic-drill.png", "drills/pneumatic-drill-rotator.png", "drills/pneumatic-drill-top.png"],
    "silicon_smelter": ["production/silicon-smelter.png", "production/silicon-smelter-top.png"],
    "graphite_press": ["production/graphite-press.png"],
    "power_node": ["power/power-node.png"],
    "combustion_generator": ["power/combustion-generator.png", "power/combustion-generator-top.png"],
    "solar_panel": ["power/solar-panel.png"],
    "solar_panel_large": ["power/solar-panel-large.png"],
    "battery": ["power/battery.png", "power/battery-top.png"],
    "ground_factory": ["units/ground-factory.png", "units/factory-out-3.png", "units/factory-top-3.png"],
    "conveyor": ["distribution/conveyors/conveyor-0-0.png"],
}
UNITS = {"dagger": ["dagger-leg.png", "dagger-base.png", "dagger.png"], "crawler": ["crawler-leg.png", "crawler-base.png", "crawler.png"],
         "nova": ["nova-leg.png", "nova-base.png", "nova.png"]}


def compose(paths: list[Path]) -> Image.Image | None:
    layers = [Image.open(p).convert("RGBA") for p in paths if p.exists()]
    if not layers:
        return None
    w = max(i.width for i in layers)
    h = max(i.height for i in layers)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for i in layers:
        out.alpha_composite(i, ((w - i.width) // 2, (h - i.height) // 2))
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    items, missing = [], []
    for kind, layers in BLOCKS.items():
        found = [SRC / "blocks" / p for p in layers if (SRC / "blocks" / p).exists()]
        im = compose(found)
        if im is None:
            missing.append(kind)
            continue
        im.save(OUT / f"{kind}.png")
        items.append({"id": f"mindustry.block.{kind}", "status": "imported", "game": "mindustry", "license": LICENSE,
                      "source": ", ".join(str(p.relative_to(SRC.parents[1])) for p in found), "godot": f"res://client/hybrid/art/mindustry/{kind}.png",
                      "mode": "sheet", "width": im.width, "height": im.height, "frames": 1, "columns": 1, "rows": 1, "fps": 0})
    for unit, layers in UNITS.items():
        found = [SRC / "units" / p for p in layers if (SRC / "units" / p).exists()]
        im = compose(found)
        if im is None:
            missing.append(unit)
            continue
        im.save(OUT / f"unit_{unit}.png")
        items.append({"id": f"mindustry.unit.{unit}", "status": "imported", "game": "mindustry", "license": LICENSE,
                      "source": ", ".join(str(p.relative_to(SRC.parents[1])) for p in found), "godot": f"res://client/hybrid/art/mindustry/unit_{unit}.png",
                      "mode": "sheet", "width": im.width, "height": im.height, "frames": 1, "columns": 1, "rows": 1, "fps": 0, "faces": "up"})
    cat = json.loads(CAT.read_text(encoding="utf-8"))
    by_id = {i["id"]: i for i in cat["items"]}
    by_id.update({i["id"]: i for i in items})
    cat["items"] = sorted(by_id.values(), key=lambda i: i["id"])
    CAT.write_text(json.dumps(cat, indent=1), encoding="utf-8")
    print("imported", [i["id"] for i in items], "missing", missing)


if __name__ == "__main__":
    main()
