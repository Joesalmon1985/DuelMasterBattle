"""Assemble the small, committable evidence set for docs/PLAYTEST_FIXES.md from the headed test shots.

    python3 scripts/make_evidence.py <shots_dir> [forestry_shots_dir]

Writes docs/evidence/playtest_v03/: before/after composites built from the real art files, a GIF of a loaded carrier walking
(16 consecutive rendered frames), and the selected headed screenshots (downscaled). The "before" pictures are rebuilt from the same
catalogue entries the first playtest used (the generic tree picture for every stage; the war factory base frame without its door).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HYB = Path(__file__).resolve().parents[1]
ART = HYB.parent / "godot_project" / "client" / "hybrid" / "art"
OUT = HYB / "docs" / "evidence" / "playtest_v03"


def label(im: Image.Image, text: str) -> Image.Image:
    out = Image.new("RGBA", (im.width, im.height + 18), (20, 20, 24, 255))
    out.paste(im, (0, 18))
    ImageDraw.Draw(out).text((4, 3), text, fill=(235, 235, 235, 255))
    return out


def sheet_frame(path: Path, frames: int, columns: int, rows: int, scale: float) -> Image.Image:
    im = Image.open(path).convert("RGBA")
    fw, fh = im.width // columns, im.height // rows
    f = im.crop((0, 0, fw, fh))
    return f.resize((int(fw * scale), int(fh * scale)), Image.NEAREST)


def trees() -> None:
    w = ART / "widelands"
    generic = sheet_frame(w / "beech.png", 4, 2, 2, 1.5)
    stages = [sheet_frame(w / f"beech_{s}.png", 4, 2, 2, 1.5) for s in ("sapling", "pole", "mature", "old")]
    stages.append(Image.open(w / "fallentree.png").convert("RGBA").resize((87, 52), Image.NEAREST))
    names = ["sapling", "pole", "mature", "old", "felled"]
    height = max(i.height for i in stages + [generic]) + 20
    sheet = Image.new("RGBA", (5 * 150, 2 * (height + 20)), (70, 110, 55, 255))
    d = ImageDraw.Draw(sheet)
    for k, (st, nm) in enumerate(zip(stages, names)):
        sheet.alpha_composite(generic, (k * 150 + 10, height - generic.height + 20))
        sheet.alpha_composite(st, (k * 150 + 10, height + 20 + height - st.height + 20))
        d.text((k * 150 + 10, 4), "before: " + nm, fill=(255, 255, 255, 255))
        d.text((k * 150 + 10, height + 24), "after: " + nm, fill=(255, 255, 255, 255))
    sheet.convert("RGB").save(OUT / "trees_before_after.png")


def war_factory() -> None:
    o = ART / "openra"
    scale = 64 / 24 * 1.5
    base = Image.open(o / "weap-0000.png").convert("RGBA")
    door = Image.open(o / "weap-top-0000.png").convert("RGBA")
    after = base.copy()
    after.alpha_composite(door)
    pair = []
    for im in (base, after):
        bg = Image.new("RGBA", im.size, (80, 120, 60, 255))
        bg.alpha_composite(im)
        pair.append(bg.resize((int(im.width * scale), int(im.height * scale)), Image.NEAREST))
    sheet = Image.new("RGB", (pair[0].width * 2 + 30, pair[0].height + 24), (20, 20, 24))
    d = ImageDraw.Draw(sheet)
    sheet.paste(pair[0].convert("RGB"), (10, 20))
    sheet.paste(pair[1].convert("RGB"), (pair[0].width + 20, 20))
    d.text((10, 4), "before: base frame only (black bay)", fill=(255, 255, 255))
    d.text((pair[0].width + 20, 4), "after: base + door overlay (weap3.shp)", fill=(255, 255, 255))
    sheet.save(OUT / "war_factory_before_after.png")


def gif(shots: Path) -> None:
    frames = sorted((shots / "motion").glob("frame_*.png"))
    if not frames:
        return
    ims = [Image.open(f).convert("RGB") for f in frames]
    w, h = ims[0].size
    box = (w // 2 - 260, h // 2 - 200, w // 2 + 260, h // 2 + 200)
    ims = [i.crop(box) for i in ims]
    ims[0].save(OUT / "carrier_walking.gif", save_all=True, append_images=ims[1:], duration=90, loop=0, optimize=True)


def shots(src: Path, forestry: Path | None) -> None:
    pick = {
        "weap_idle_door_closed.png": "war_factory_in_game.png", "carrier_with_ware.png": "carrier_with_ware.png", "building_burning.png": "building_burning.png",
        "02_far_tree_description.png": "wizard_far_tree_description.png", "03_near_tree_choices.png": "wizard_near_tree_fire_choice.png",
        "04_tree_burned.png": "wizard_tree_burned.png", "01_wizard_labels.png": "wizard_labels.png", "04_command_centre_deployed.png": "mcv_command_centre_deployed.png",
        "03_mcv_at_site.png": "mcv_at_site.png",
    }
    for a, b in pick.items():
        f = src / a
        if f.exists():
            Image.open(f).convert("RGB").save(OUT / b.replace(".png", ".jpg"), quality=82)
    if forestry:
        for a, b in {"03_chopping.png": "forestry_1_chopping.jpg", "04_tree_felled.png": "forestry_2_felled.jpg", "08_sapling.png": "forestry_3_sapling.jpg", "09_pole.png": "forestry_4_pole.jpg"}.items():
            f = forestry / a
            if f.exists():
                Image.open(f).convert("RGB").save(OUT / b, quality=82)


def main() -> None:
    src = Path(sys.argv[1])
    forestry = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    OUT.mkdir(parents=True, exist_ok=True)
    trees()
    war_factory()
    gif(src)
    shots(src, forestry)
    print("evidence in", OUT, sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
