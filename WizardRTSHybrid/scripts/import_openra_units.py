#!/usr/bin/env python3
"""Import the OpenRA (Red Alert) art for the era roster added on 12 Oct 2026, from the player's own content (never committed whole).

Readable here (conquer.mix, unencrypted): vehicles JEEP 1TNK 2TNK 3TNK 4TNK ARTY APC V2RL STNK and the defences FTUR TSLA PBOX.
Vehicles are 32 classic facings; where the sequence has a turret (frames 32-63, mods/ra/sequences/vehicles.yaml) the turret frame of
the same facing is composited over the body, so a tank shows its gun. Buildings take their idle frame (and damaged frame).

Encrypted archives (13 Oct 2026): the infantry E2 E3 (hires.mix), SHOK (expand/hires1.mix) and the Aftermath tanks TTNK CTNK
(expand/expand2.mix) have the Westwood encrypted header. mix_crypto.py now derives the Blowfish key (RSA-wrapped, pure Python), so they
are imported for real. The hybrid Prehistoric actors still get an honest ALIAS entry: the closest imported picture, recorded as `status: alias_placeholder` with `alias_of`, so the coverage report
never counts them as their own art. Run: python3 scripts/import_openra_units.py [path/to/conquer.mix]
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from PIL import Image

HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB / "scripts"))
import mix_read  # noqa: E402
import shp_td  # noqa: E402

ART = HYB.parent / "godot_project" / "client" / "hybrid" / "art"
CAT = ART / "catalogue.json"
MIX = "/home/joe/Videos/.config/openra/Content/ra/v2/conquer.mix"
LICENSE = ("Extracted from the player's own Red Alert content with the OpenRA package format. Use was permitted for this project. "
           "The OpenRA engine is GPL-3.0-or-later. The original Red Alert artwork is not relicensed by this copy.")
CELL = 64.0 / 24.0
VEHICLES = {"jeep": True, "1tnk": True, "2tnk": True, "3tnk": True, "4tnk": True, "arty": False, "apc": False, "v2rl": False, "stnk": False}
BUILDINGS = {"ftur": (0, 1), "tsla": (0, 10), "pbox": (0, 1)}
INFANTRY = {"e2": "hires.mix", "e3": "hires.mix", "shok": "expand/hires1.mix"}  # stand Facings 8 + run Start 16 Length 6 Facings 8 (sequences/infantry.yaml)
ENCRYPTED_TANKS = {"ttnk": "expand/expand2.mix", "ctnk": "expand/expand2.mix"}  # idle Facings 32 (the Tesla coil "spinner" 32-63 is a separate animation, not yet imported)
ALIASES = {  # unit without readable art -> (picture it borrows, why)
    "dmb.clubman": ("widelands.soldier", "Prehistoric clubman: hybrid actor, drawn with the Widelands soldier"),
    "dmb.spearman": ("widelands.soldier", "Prehistoric spearman: hybrid actor, drawn with the Widelands soldier"),
    "dmb.slinger": ("widelands.soldier", "Prehistoric slinger: hybrid actor, drawn with the Widelands soldier"),
    "dmb.caravan": ("widelands.carrier", "Trade caravan: hybrid unit, drawn with the Widelands carrier"),
    "dmb.settlers": ("widelands.carrier", "Settlers' wagon: hybrid founder, drawn with the Widelands carrier"),
    "dmb.war_lodge": ("widelands.barbarians_barracks", "War lodge: hybrid Prehistoric building, drawn with the Widelands barbarian barracks"),
}


def rgba(raw: bytes, w: int, h: int, palette: list[int]) -> Image.Image:
    im = Image.frombytes("P", (w, h), raw)
    im.putpalette(palette)
    out = im.convert("RGBA")
    px = out.load()
    for y in range(h):
        for x in range(w):
            if raw[y * w + x] == 0:
                px[x, y] = (0, 0, 0, 0)
    return out


def main() -> None:
    mix = mix_read.Mix(sys.argv[1] if len(sys.argv) > 1 else MIX)
    palette = Image.open(ART / "openra" / "weap-0000.png").getpalette()
    items = []
    for name, turret in VEHICLES.items():
        w, h, frames = shp_td.read_shp(mix.read(name.upper() + ".SHP"))
        paths = []
        for f in range(32):
            im = rgba(frames[f], w, h, palette)
            if turret and len(frames) >= 64:
                im.alpha_composite(rgba(frames[32 + f], w, h, palette))
            p = ART / "openra" / f"{name}-{f:04d}.png"
            im.save(p)
            paths.append(f"res://client/hybrid/art/openra/{name}-{f:04d}.png")
        items.append({"id": f"openra.{name}", "status": "imported", "game": "openra", "license": LICENSE,
                      "source": f"{name}.shp idle Facings 32" + (" + turret Start 32 composited per facing" if turret else ""),
                      "source_note": "mods/ra/sequences/vehicles.yaml, decoded from conquer.mix with the temperat palette", "godot": paths[0],
                      "frames_godot": paths, "mode": "sequence", "frame_indexes": list(range(32)), "facings": 32, "length": 1,
                      "hotspot": [w // 2, int(h * 0.85)], "scale": 3 if w <= 36 else CELL, "fps": 0, "prefix": name})
    for name, (idle, damaged) in BUILDINGS.items():
        w, h, frames = shp_td.read_shp(mix.read(name.upper() + ".SHP"))
        paths = []
        for f in (idle, damaged):
            f = min(f, len(frames) - 1)
            rgba(frames[f], w, h, palette).save(ART / "openra" / f"{name}-{f:04d}.png")
            paths.append(f"res://client/hybrid/art/openra/{name}-{f:04d}.png")
        items.append({"id": f"openra.{name}", "status": "imported", "game": "openra", "license": LICENSE, "source": f"{name}.shp idle {idle}, damaged {damaged}",
                      "source_note": "mods/ra/sequences/structures.yaml, decoded from conquer.mix with the temperat palette", "godot": paths[0],
                      "frames_godot": paths, "mode": "sequence", "frame_indexes": [idle, min(damaged, len(frames) - 1)], "facings": 1, "length": 1,
                      "hotspot": [0, 0], "scale": CELL, "fps": 0, "prefix": name, "footprint_cells": [w // 24, h // 24], "damaged_frame": min(damaged, len(frames) - 1)})
    content = Path(sys.argv[1] if len(sys.argv) > 1 else MIX).parent
    for name, pkg in INFANTRY.items():
        w, h, frames = shp_td.read_shp(mix_read.Mix(content / pkg).read(name.upper() + ".SHP"))
        order = list(range(8)) + list(range(16, 64))
        paths = []
        for f in order:  # files keep the sequence's own frame numbers: hybrid_art.gd reads run_start + facing * length + tick
            rgba(frames[f], w, h, palette).save(ART / "openra" / f"{name}-{f:04d}.png")
            paths.append(f"res://client/hybrid/art/openra/{name}-{f:04d}.png")
        items.append({"id": f"openra.{name}", "status": "imported", "game": "openra", "license": LICENSE.replace("conquer.mix", pkg),
                      "source": f"{name}.shp stand Facings 8 and run Start 16 Length 6 Facings 8", "source_note": f"mods/ra/sequences/infantry.yaml, decoded from {pkg} (encrypted header, mix_crypto.py) with the temperat palette",
                      "godot": paths[0], "frames_godot": paths, "mode": "sequence", "frame_indexes": order, "facings": 8, "length": 6,
                      "hotspot": [w // 2, int(h * 0.85)], "scale": 3, "fps": 10, "prefix": name, "stand_start": 0, "run_start": 16, "run_length": 6, "run_facings": 8})
    for name, pkg in ENCRYPTED_TANKS.items():
        w, h, frames = shp_td.read_shp(mix_read.Mix(content / pkg).read(name.upper() + ".SHP"))
        paths = []
        for f in range(32):
            rgba(frames[f], w, h, palette).save(ART / "openra" / f"{name}-{f:04d}.png")
            paths.append(f"res://client/hybrid/art/openra/{name}-{f:04d}.png")
        items.append({"id": f"openra.{name}", "status": "imported", "game": "openra", "license": LICENSE, "source": f"{name}.shp idle Facings 32",
                      "source_note": f"mods/ra/sequences/vehicles.yaml, decoded from {pkg} (encrypted header, mix_crypto.py) with the temperat palette", "godot": paths[0],
                      "frames_godot": paths, "mode": "sequence", "frame_indexes": list(range(32)), "facings": 32, "length": 1,
                      "hotspot": [w // 2, int(h * 0.85)], "scale": 3 if w <= 36 else CELL, "fps": 0, "prefix": name})
    cat = json.loads(CAT.read_text(encoding="utf-8"))
    by_id = {i["id"]: i for i in cat["items"]}
    for i in items:  # a re-import keeps the placement an earlier, hand-checked import chose (the 3TNK hotspot and scale)
        old = by_id.get(i["id"])
        if old is not None:
            i["hotspot"], i["scale"] = old.get("hotspot", i["hotspot"]), old.get("scale", i["scale"])
        by_id[i["id"]] = i
    for alias, (src, why) in ALIASES.items():
        base = by_id.get(src)
        if base is None:
            print("no picture for alias", alias, "<-", src)
            continue
        a = copy.deepcopy(base)
        a.update(id=alias, status="alias_placeholder", alias_of=src, source_note=why)
        by_id[alias] = a
    cat["items"] = sorted(by_id.values(), key=lambda i: i["id"])
    CAT.write_text(json.dumps(cat, indent=1), encoding="utf-8")
    print("imported", [i["id"] for i in items], "aliases", sorted(ALIASES))


if __name__ == "__main__":
    main()
