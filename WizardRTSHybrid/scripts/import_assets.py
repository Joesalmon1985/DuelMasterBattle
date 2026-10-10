"""Copy a declared set of Widelands and OpenRA sprites into the Godot project.

The finished game reads the copied files, not the source checkouts. OpenRA
frames are extracted with the pinned engine's Utility ``--extract`` and
``--png`` commands. A missing required sprite stays out of the catalogue
instead of being replaced with a rectangle.
"""

from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HYBRID = ROOT / "WizardRTSHybrid"
WIDELANDS = HYBRID / "external" / "widelands"
OPENRA = HYBRID / "external" / "openra"
ART = ROOT / "godot_project" / "client" / "hybrid" / "art"
EXTRACT = HYBRID / "runtime" / "asset_extract"
DOTNET = Path(r"C:\Program Files\dotnet\dotnet.exe")
UTILITY = OPENRA / "bin" / "OpenRA.Utility.dll"

WIDELANDS_COMMIT = "47c5cae8c6cb080e4bf86163a3873bd0847bc0e4"
OPENRA_COMMIT = "e7e9e4ad"
WL_LICENSE = "GPL-2.0-or-later"
RA_NOTE = (
    "Extracted from the pinned OpenRA RA content packages with OpenRA.Utility. "
    "Use was permitted for this project. The OpenRA engine is GPL-3.0-or-later. "
    "The original Red Alert artwork is not relicensed by this copy."
)


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        handle.read(16)
        width, height = struct.unpack(">II", handle.read(8))
    return width, height


def git_head(repo: Path, fallback: str) -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return out.strip()
    except (OSError, subprocess.CalledProcessError):
        return fallback


def copy_file(src: Path, dest: Path) -> None:
    if not src.is_file():
        raise FileNotFoundError(src)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def wl(rel: str) -> Path:
    return WIDELANDS / rel


def sheet(
    item_id: str,
    src_rel: str,
    dest_name: str,
    *,
    columns: int,
    rows: int,
    frames: int,
    hotspot: list[int],
    scale: int,
    fps: int = 0,
    source_note: str,
) -> dict:
    src = wl(src_rel)
    dest = ART / "widelands" / dest_name
    copy_file(src, dest)
    width, height = png_size(dest)
    return {
        "id": item_id,
        "status": "imported",
        "game": "widelands",
        "license": WL_LICENSE,
        "source": src_rel.replace("\\", "/"),
        "source_note": source_note,
        "godot": f"res://client/hybrid/art/widelands/{dest_name}",
        "mode": "sheet",
        "width": width,
        "height": height,
        "columns": columns,
        "rows": rows,
        "frames": frames,
        "hotspot": hotspot,
        "scale": scale,
        "fps": fps,
    }


def run_utility(args: list[str]) -> None:
    env = os.environ.copy()
    env["ENGINE_DIR"] = str(OPENRA)
    EXTRACT.mkdir(parents=True, exist_ok=True)
    subprocess.check_call(
        [str(DOTNET), str(UTILITY), "ra", *args],
        cwd=EXTRACT,
        env=env,
    )


def extract_openra(names: list[str]) -> None:
    missing = [name for name in names if not (EXTRACT / name).is_file()]
    if not missing:
        return
    if not UTILITY.is_file() or not DOTNET.is_file():
        raise FileNotFoundError("OpenRA.Utility or dotnet is not available")
    run_utility(["--extract", *missing])
    pending = []
    for name in missing:
        if name.endswith(".pal"):
            continue
        stem = Path(name).stem
        if not (EXTRACT / f"{stem}-0000.png").is_file():
            pending.append(name)
    if pending:
        for name in pending:
            run_utility(["--png", name, "temperat.pal", "--noshadow"])


def copy_openra_frame(stem: str, index: int, dest_name: str) -> Path:
    src = EXTRACT / f"{stem}-{index:04d}.png"
    dest = ART / "openra" / dest_name
    copy_file(src, dest)
    return dest


def sequence_item(
    item_id: str,
    stem: str,
    indexes: list[int],
    *,
    hotspot: list[int],
    scale: int,
    fps: int,
    facings: int,
    length: int,
    source_file: str,
    extra: dict | None = None,
) -> dict:
    copied = []
    for index in indexes:
        name = f"{stem}-{index:04d}.png"
        copy_openra_frame(stem, index, name)
        copied.append(f"res://client/hybrid/art/openra/{name}")
    item = {
        "id": item_id,
        "status": "imported",
        "game": "openra",
        "license": RA_NOTE,
        "source": source_file,
        "source_note": "mods/ra sequence, converted by OpenRA.Utility --png and temperat.pal",
        "godot": copied[0],
        "frames_godot": copied,
        "mode": "sequence",
        "frame_indexes": indexes,
        "facings": facings,
        "length": length,
        "hotspot": hotspot,
        "scale": scale,
        "fps": fps,
        "prefix": stem,
    }
    if extra:
        item.update(extra)
    return item


def main() -> None:
    if ART.exists():
        shutil.rmtree(ART)
    ART.mkdir(parents=True)
    widelands_commit = git_head(WIDELANDS, WIDELANDS_COMMIT)
    openra_commit = git_head(OPENRA, OPENRA_COMMIT)
    items: list[dict] = []

    items.append(
        sheet(
            "widelands.meadow1",
            "data/world/terrains/summer/meadow1/idle.png",
            "meadow1.png",
            columns=1,
            rows=1,
            frames=1,
            hotspot=[0, 0],
            scale=1,
            source_note="data/world/terrains/summer/meadow1",
        )
    )
    items.append(
        sheet(
            "widelands.meadow2",
            "data/world/terrains/summer/meadow2/idle.png",
            "meadow2.png",
            columns=1,
            rows=1,
            frames=1,
            hotspot=[0, 0],
            scale=1,
            source_note="data/world/terrains/summer/meadow2",
        )
    )
    items.append(
        sheet(
            "widelands.meadow3",
            "data/world/terrains/summer/meadow3/idle.png",
            "meadow3.png",
            columns=1,
            rows=1,
            frames=1,
            hotspot=[0, 0],
            scale=1,
            source_note="data/world/terrains/summer/meadow3",
        )
    )
    items.append(
        sheet(
            "widelands.road",
            "data/tribes/initialization/barbarians/images/roadt_normal_00.png",
            "road.png",
            columns=1,
            rows=1,
            frames=1,
            hotspot=[34, 5],
            scale=1,
            source_note="barbarians road texture roadt_normal_00.png",
        )
    )
    items.append(
        sheet(
            "widelands.lumberjack",
            "data/tribes/buildings/productionsites/barbarians/lumberjacks_hut/idle_00.png",
            "lumberjack.png",
            columns=1,
            rows=1,
            frames=1,
            hotspot=[43, 45],
            scale=2,
            source_note="barbarians_lumberjacks_hut animations.idle hotspot {43,45}",
        )
    )
    items.append(
        sheet(
            "widelands.sawmill",
            "data/tribes/buildings/productionsites/empire/sawmill/idle_1.png",
            "sawmill.png",
            columns=1,
            rows=1,
            frames=1,
            hotspot=[48, 62],
            scale=2,
            source_note="empire_sawmill spritesheets.idle. This pin has no barbarian sawmill.",
        )
    )
    items.append(
        sheet(
            "widelands.warehouse",
            "data/tribes/buildings/warehouses/barbarians/warehouse/idle_1.png",
            "warehouse.png",
            columns=1,
            rows=1,
            frames=1,
            hotspot=[60, 78],
            scale=2,
            source_note="barbarians_warehouse spritesheets.idle hotspot {60,78}",
        )
    )
    items.append(
        sheet(
            "widelands.coalmine",
            "data/tribes/buildings/productionsites/barbarians/coalmine/idle_00.png",
            "coalmine.png",
            columns=1,
            rows=1,
            frames=1,
            hotspot=[21, 36],
            scale=2,
            source_note="barbarians_coalmine animations.idle hotspot {21,36}",
        )
    )
    items.append(
        sheet(
            "widelands.tavern",
            "data/tribes/buildings/productionsites/barbarians/tavern/idle_00.png",
            "tavern.png",
            columns=1,
            rows=1,
            frames=1,
            hotspot=[57, 88],
            scale=2,
            source_note="barbarians_tavern animations.idle hotspot {57,88}",
        )
    )
    items.append(
        sheet(
            "widelands.farm",
            "data/tribes/buildings/productionsites/barbarians/farm/idle_1.png",
            "farm.png",
            columns=4,
            rows=5,
            frames=20,
            hotspot=[69, 76],
            scale=2,
            fps=8,
            source_note="barbarians_farm spritesheets.idle frames 20, columns 4, rows 5",
        )
    )
    items.append(
        sheet(
            "widelands.beech",
            "data/world/immovables/trees/beech/mature/mature_1.png",
            "beech.png",
            columns=2,
            rows=2,
            frames=4,
            hotspot=[18, 48],
            scale=2,
            fps=8,
            source_note="beech_summer_mature spritesheets.idle",
        )
    )
    items.append(
        sheet(
            "widelands.rocks",
            "data/world/immovables/rocks/greenland/1/rocks1.png",
            "rocks.png",
            columns=1,
            rows=1,
            frames=1,
            hotspot=[39, 82],
            scale=2,
            source_note="greenland_rocks1 animations.idle hotspot {39,82}",
        )
    )
    items.append(
        sheet(
            "widelands.carrier",
            "data/tribes/workers/barbarians/carrier/walk_e_1.png",
            "carrier_e.png",
            columns=3,
            rows=4,
            frames=10,
            hotspot=[6, 16],
            scale=4,
            fps=10,
            source_note="barbarians_carrier walk directional sheet, east",
        )
    )
    for facing in ("ne", "nw", "se", "sw", "w"):
        items.append(
            sheet(
                f"widelands.carrier.{facing}",
                f"data/tribes/workers/barbarians/carrier/walk_{facing}_1.png",
                f"carrier_{facing}.png",
                columns=3,
                rows=4,
                frames=10,
                hotspot=[6, 16],
                scale=4,
                fps=10,
                source_note=f"barbarians_carrier walk_{facing}",
            )
        )
    items.append(
        sheet(
            "widelands.soldier",
            "data/tribes/workers/barbarians/soldier/idle_1.png",
            "soldier.png",
            columns=4,
            rows=5,
            frames=20,
            hotspot=[6, 29],
            scale=4,
            fps=5,
            source_note="barbarians_soldier spritesheets.idle",
        )
    )

    extract_openra(
        [
            "temperat.pal",
            "barr.shp",
            "weap.shp",
            "proc.shp",
            "3tnk.shp",
            "e1.shp",
            "gun.shp",
            "gunmake.shp",
            "120mm.shp",
            "piff.shp",
            "veh-hit3.shp",
        ]
    )
    items.append(
        sequence_item(
            "openra.barracks",
            "barr",
            list(range(10)),
            hotspot=[24, 44],
            scale=3,
            fps=5,
            facings=1,
            length=10,
            source_file="barr.shp sequence barr.idle Length 10",
        )
    )
    items.append(
        sequence_item(
            "openra.weap",
            "weap",
            [0, 1],
            hotspot=[36, 44],
            scale=3,
            fps=2,
            facings=1,
            length=2,
            source_file="weap.shp sequence weap.idle and damaged-idle",
        )
    )
    items.append(
        sequence_item(
            "openra.proc",
            "proc",
            [0, 1],
            hotspot=[36, 66],
            scale=3,
            fps=2,
            facings=1,
            length=2,
            source_file="proc.shp sequence proc.idle",
        )
    )
    items.append(
        sequence_item(
            "openra.3tnk",
            "3tnk",
            list(range(32)),
            hotspot=[18, 32],
            scale=3,
            fps=8,
            facings=32,
            length=1,
            source_file="3tnk.shp sequence 3tnk.idle Facings 32",
            extra={"facing_count": 32},
        )
    )
    items.append(
        sequence_item(
            "openra.e1",
            "e1",
            list(range(8)) + list(range(16, 64)),
            hotspot=[25, 36],
            scale=3,
            fps=10,
            facings=8,
            length=6,
            source_file="e1.shp stand Facings 8 and run Start 16 Length 6 Facings 8",
            extra={"stand_start": 0, "run_start": 16, "run_length": 6, "run_facings": 8},
        )
    )
    items.append(
        sequence_item(
            "openra.gun",
            "gun",
            list(range(32)),
            hotspot=[12, 22],
            scale=3,
            fps=0,
            facings=32,
            length=1,
            source_file="gun.shp turret Facings 32. idle body is gunmake.shp",
        )
    )
    if (EXTRACT / "gunmake-0000.png").is_file():
        items.append(
            sequence_item(
                "openra.gun_base",
                "gunmake",
                [0],
                hotspot=[24, 24],
                scale=2,
                fps=0,
                facings=1,
                length=1,
                source_file="gunmake.shp",
            )
        )
    if (EXTRACT / "120mm-0000.png").is_file():
        items.append(
            sequence_item(
                "openra.120mm",
                "120mm",
                [0],
                hotspot=[8, 8],
                scale=2,
                fps=0,
                facings=1,
                length=1,
                source_file="120mm.shp",
            )
        )
    if (EXTRACT / "piff-0000.png").is_file():
        piff_indexes = [i for i in range(8) if (EXTRACT / f"piff-{i:04d}.png").is_file()]
        items.append(
            sequence_item(
                "openra.piff",
                "piff",
                piff_indexes,
                hotspot=[16, 16],
                scale=2,
                fps=12,
                facings=1,
                length=len(piff_indexes),
                source_file="piff.shp sequence explosion.piff",
            )
        )
    if (EXTRACT / "veh-hit3-0000.png").is_file():
        boom = [i for i in range(8) if (EXTRACT / f"veh-hit3-{i:04d}.png").is_file()]
        items.append(
            sequence_item(
                "openra.explosion",
                "veh-hit3",
                boom,
                hotspot=[24, 24],
                scale=2,
                fps=12,
                facings=1,
                length=len(boom),
                source_file="veh-hit3.shp sequence explosion.small_explosion",
            )
        )

    required = [
        "widelands.lumberjack",
        "widelands.warehouse",
        "widelands.coalmine",
        "widelands.tavern",
        "widelands.farm",
        "widelands.sawmill",
        "widelands.road",
        "widelands.carrier",
        "widelands.beech",
        "openra.barracks",
        "openra.e1",
        "openra.3tnk",
        "openra.weap",
    ]
    present = {item["id"] for item in items if item["status"] == "imported"}
    missing = [item_id for item_id in required if item_id not in present]
    catalogue = {
        "widelands_commit": widelands_commit,
        "openra_commit": openra_commit,
        "display_scale_note": (
            "Terrain is 1:1 with the 64px tile. Widelands buildings and trees use scale 2 "
            "so their authored hotspots stay the ground contact. Workers use scale 4 so a "
            "carrier frame sits near the wizard's height. OpenRA sprites use scale 2, "
            "except the 24px gun turret at scale 3."
        ),
        "items": items,
        "required": required,
        "missing_required": missing,
    }
    dest = ART / "catalogue.json"
    dest.write_text(json.dumps(catalogue, indent=2), encoding="utf-8")
    print(f"ASSET_IMPORT items={len(items)} missing={missing}")
    if missing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
