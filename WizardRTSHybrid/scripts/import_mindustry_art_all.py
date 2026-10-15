#!/usr/bin/env python3
"""Import the Mindustry v146 sprites of EVERY simulated block and unit (owner programme 13 Oct 2026, section 9).

For each block (wizard_rts.industry.blocks.specs) the sprite files named after it are located under core/assets-raw/sprites (blocks/**, units/**) and
 * composed once into a static picture `mindustry/<kind>.png` (bottom -> base -> rotator -> top), and
 * kept as separate animatable PARTS `mindustry/<kind>__<part>.png` with their roles (`base`, `rotator` spins while the machine works, `top`, `liquid` tint,
   `weapon` for units, `heat` glow), so the client can spin a drill, light a smelter or turn a turret independently of its base.
Units: base/leg/cell/weapon parts under `mindustry/unit_<name>*.png`, legs and weapons as parts. Conveyor belts are imported as their four animation frames.
The catalogue entry records every upstream file; `parts` lists the part files and their animation roles.
Licence: GPL-3.0 (Anuken/Mindustry v146, no separate asset notice at the pin). Run: python3 scripts/import_mindustry_art_all.py
"""
from __future__ import annotations
import sys as _sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from wizard_rts import freeze_guard  # noqa: E402  (content is frozen: D33)
freeze_guard.require_unfreeze(__file__)

import json
import sys
from pathlib import Path

from PIL import Image

HYB = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HYB), str(HYB.parent)]
SRC = HYB / "external" / "mindustry" / "core" / "assets-raw" / "sprites"
ART = HYB.parent / "godot_project" / "client" / "hybrid" / "art"
OUT = ART / "mindustry"
CAT = ART / "catalogue.json"
LICENSE = "GPL-3.0 (Anuken/Mindustry v146, repository LICENSE covers core/assets-raw; no separate asset terms at the pin)"
ROLE = {"-bottom": "bottom", "-rotator": "rotator", "-top": "top", "-liquid": "liquid", "-heat": "heat", "-glow": "glow", "-base": "base", "-turret": "turret",
        "-weapon": "weapon", "-wire": "wire", "-arrow": "arrow", "-end": "end", "-bridge": "bridge", "-mid": "mid"}
ORDER = ["bottom", "base", "main", "liquid", "rotator", "turret", "wire", "top", "weapon", "glow", "heat"]


def index(root: Path) -> dict[str, list[Path]]:
    out: dict[str, list[Path]] = {}
    for p in sorted(root.rglob("*.png")):
        out.setdefault(p.stem, []).append(p)
    return out


def parts_for(name: str, idx: dict[str, list[Path]]) -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    if name in idx:
        found.append(("main", idx[name][0]))
    for suffix, role in ROLE.items():
        for key in (name + suffix, name + suffix + "-0"):
            if key in idx:
                found.append((role, idx[key][0]))
                break
    return found


def compose(paths: list[Path]) -> Image.Image | None:
    layers = [Image.open(p).convert("RGBA") for p in paths]
    if not layers:
        return None
    w, h = max(i.width for i in layers), max(i.height for i in layers)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for i in layers:
        out.alpha_composite(i, ((w - i.width) // 2, (h - i.height) // 2))
    return out


def main() -> int:
    from wizard_rts.industry import blocks as B
    from wizard_rts.industry import units as U

    OUT.mkdir(parents=True, exist_ok=True)
    bidx, uidx = index(SRC / "blocks"), index(SRC / "units")
    items, missing = [], []
    for kind, spec in sorted(B.specs().items()):
        if kind.startswith("mdy:hy_"):
            continue
        name = spec["id"]
        parts = parts_for(name, bidx)
        if not parts and spec["class"] in ("Wall",):
            parts = parts_for(name.replace("-large", ""), bidx)
        if not parts:  # a few blocks keep their picture under a prefixed name (salvo-*, scrap-wall-* variants)
            near = sorted(k for k in bidx if k.startswith(name + "-") and not k.endswith(("-heat", "-glow")))
            if not near and name.startswith("scrap-wall"):
                near = sorted(k for k in bidx if k.startswith("scrap-wall"))[:1]
            if near:
                parts = [("main", bidx[near[0]][0])]
        if not parts:
            missing.append(kind)
            continue
        parts.sort(key=lambda rp: ORDER.index(rp[0]) if rp[0] in ORDER else 5)
        snake = kind[4:]
        im = compose([p for _r, p in parts if _r not in ("heat", "glow")] or [p for _r, p in parts])
        im.save(OUT / f"{snake}.png")
        rec_parts = []
        for role, p in parts:
            pim = Image.open(p).convert("RGBA")
            fn = f"{snake}__{role}.png"
            pim.save(OUT / fn)
            rec_parts.append({"role": role, "file": f"res://client/hybrid/art/mindustry/{fn}", "anim": {"rotator": "spin_when_working", "liquid": "tint_by_fill", "heat": "glow_when_working",
                                                                                                         "glow": "glow_when_working", "turret": "aim", "weapon": "aim"}.get(role, "none")})
        items.append({"id": f"mindustry.block.{snake}", "status": "imported", "game": "mindustry", "license": LICENSE, "source": ", ".join(str(p.relative_to(SRC.parents[1])) for _r, p in parts),
                      "godot": f"res://client/hybrid/art/mindustry/{snake}.png", "mode": "sheet", "width": im.width, "height": im.height, "frames": 1, "columns": 1, "rows": 1, "fps": 0,
                      "parts": rec_parts, "role": spec["role"], "size": spec["size"]})
    for name in U.unit_list():
        parts = parts_for(name, uidx)
        legs = [p for key, ps in uidx.items() for p in ps if key.startswith(name + "-leg")]
        weapons = []
        for w in B.full()["units"][name]["weapons"]:
            wn = w.get("name")
            if wn and wn in uidx:
                weapons.append(("weapon", uidx[wn][0]))
            elif wn and wn in uidx.keys():
                pass
        if not parts and not legs:
            missing.append("unit:" + name)
            continue
        snake = name.replace("-", "_")
        base_paths = [p for _r, p in parts if _r in ("base", "bottom")] + [p for _r, p in parts if _r == "main"] + [p for _r, p in parts if _r == "top"]
        im = compose([*legs[:1], *base_paths]) or compose([p for _r, p in parts])
        im.save(OUT / f"unit_{snake}.png")
        rec = []
        for role, p in [*parts, *weapons] + [("leg", q) for q in legs[:2]]:
            fn = f"unit_{snake}__{role}_{p.stem}.png"
            Image.open(p).convert("RGBA").save(OUT / fn)
            rec.append({"role": role, "file": f"res://client/hybrid/art/mindustry/{fn}", "anim": {"weapon": "aim", "leg": "walk"}.get(role, "none")})
        items.append({"id": f"mindustry.unit.{snake}", "status": "imported", "game": "mindustry", "license": LICENSE, "source": ", ".join(str(p.relative_to(SRC.parents[1])) for _r, p in parts) or "legs",
                      "godot": f"res://client/hybrid/art/mindustry/unit_{snake}.png", "mode": "sheet", "width": im.width, "height": im.height, "frames": 1, "columns": 1, "rows": 1, "fps": 0,
                      "faces": "up", "parts": rec})
    # conveyors: the four animation frames of the belt
    for belt, base in (("conveyor", "conveyor"), ("titanium_conveyor", "titanium-conveyor"), ("armored_conveyor", "armored-conveyor")):
        frames = [bidx[f"{base}-0-{i}"][0] for i in range(4) if f"{base}-0-{i}" in bidx]
        if len(frames) == 4:
            sheet = Image.new("RGBA", (frames[0].stat().st_size and Image.open(frames[0]).width * 4, Image.open(frames[0]).height), (0, 0, 0, 0))
            fw = Image.open(frames[0]).width
            for i, f in enumerate(frames):
                sheet.alpha_composite(Image.open(f).convert("RGBA"), (i * fw, 0))
            sheet.save(OUT / f"{belt}_anim.png")
            items.append({"id": f"mindustry.belt.{belt}", "status": "imported", "game": "mindustry", "license": LICENSE, "source": ", ".join(str(f.relative_to(SRC.parents[1])) for f in frames),
                          "godot": f"res://client/hybrid/art/mindustry/{belt}_anim.png", "mode": "sheet", "width": sheet.width, "height": sheet.height, "frames": 4, "columns": 4, "rows": 1, "fps": 8})
    cat = json.loads(CAT.read_text(encoding="utf-8"))
    by_id = {i["id"]: i for i in cat["items"]}
    by_id.update({i["id"]: i for i in items})
    cat["items"] = sorted(by_id.values(), key=lambda i: i["id"])
    CAT.write_text(json.dumps(cat, indent=1), encoding="utf-8")
    print(f"imported {len(items)} entries; no sprite found for {len(missing)}: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
