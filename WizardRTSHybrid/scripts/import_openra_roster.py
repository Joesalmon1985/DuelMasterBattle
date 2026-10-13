#!/usr/bin/env python3
"""Generic import of Red Alert unit art from the sequence YAML (plan v2 8.3 item 2): every infantry, vehicle, ship and aircraft actor
whose `idle` / `stand` sequence can be located in the player's own content packages.

For each actor: the first of `idle`, `stand` gives Filename (own or from Defaults), Start, Facings. A `turret` sequence with the same
facings is composited over the body (ships: turret facings are twice the body's, so body facing k takes turret frame 2k), exactly as the
earlier vehicle importer did; independent turret layers wait for a simulation-side turret angle. Infantry also keep the `run`
sequence (Start, Length). Existing hand-checked items are not overwritten (a re-import only adds). Files are named `<actor>-<frame>.png`
with the sequence's own frame numbers.

Run: python3 scripts/import_openra_roster.py [content dir]   (default ~/Videos/.config/openra/Content/ra/v2)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from PIL import Image

HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB / "scripts"))
import mix_read  # noqa: E402
import shp_td  # noqa: E402

ART = HYB.parent / "godot_project" / "client" / "hybrid" / "art"
CAT = ART / "catalogue.json"
SEQ = HYB / "external" / "openra" / "mods" / "ra" / "sequences"
RULES = HYB / "wizard_rts" / "data" / "openra_rules.json"
CELL = 64.0 / 24.0
LICENSE = ("Extracted from the player's own Red Alert content packages (read with mix_read.py, including the encrypted headers via mix_crypto.py). "
           "Use was permitted for this project. The OpenRA engine is GPL-3.0-or-later. The original Red Alert artwork is not relicensed by this copy.")
SKIP = {"ant", "zombie", "fireant", "scoutant", "warriorant", "harv", "mcv"}  # mission-only creatures; harvester (credits economy); mcv has its own importer


def parse_yaml(path: Path) -> dict[str, dict[str, dict[str, str]]]:
    out: dict[str, dict[str, dict[str, str]]] = {}
    actor = seq = None
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip("\t"))
        text = line.strip()
        if indent == 0 and text.endswith(":"):
            actor = text[:-1].lower()
            out[actor] = {}
            seq = None
        elif indent == 1 and actor and text.endswith(":"):
            seq = text[:-1]
            out[actor][seq] = {}
        elif indent == 2 and actor and seq is not None and ":" in text:
            k, v = text.split(":", 1)
            out[actor][seq][k.strip()] = v.strip()
    return out


def prop(seqs: dict, name: str, key: str, default: str | None = None) -> str | None:
    s = seqs.get(name, {})
    if key in s:
        return s[key]
    return seqs.get("Defaults", {}).get(key, default)


def package_index(content: Path) -> dict[str, mix_read.Mix]:
    return {str(p.relative_to(content)): mix_read.Mix(p) for p in sorted(content.rglob("*.mix")) if "cnc" not in p.parts}


def find(index: dict[str, mix_read.Mix], name: str) -> tuple[bytes, str] | None:
    for pkg, m in index.items():
        d = m.read(name.upper())
        if d:
            return d, pkg
    return None


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


def main() -> int:
    content = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / "Videos/.config/openra/Content/ra/v2")
    index = package_index(content)
    palette = Image.open(ART / "openra" / "weap-0000.png").getpalette()
    rules = json.loads(RULES.read_text())["actors"]
    cat = json.loads(CAT.read_text(encoding="utf-8"))
    by_id = {i["id"]: i for i in cat["items"]}
    seqs: dict = {}
    for f in ("infantry", "vehicles", "ships", "aircraft"):
        seqs.update(parse_yaml(SEQ / f"{f}.yaml"))
    added, skipped = [], {}
    for actor, r in sorted(rules.items()):
        if r.get("is_building") or actor in SKIP or r.get("queue") not in ("Infantry", "Vehicle", "Ship", "Aircraft"):
            continue
        item_id = f"openra.{actor}"
        if item_id in by_id and by_id[item_id].get("status") == "imported":
            continue
        s = seqs.get(actor)
        if not s:
            skipped[actor] = "no sequence"
            continue
        base = "idle" if "idle" in s else ("stand" if "stand" in s else None)
        fname = prop(s, base, "Filename") if base else None
        if not fname:
            skipped[actor] = "no idle/stand filename"
            continue
        got = find(index, fname)
        if got is None:
            skipped[actor] = f"{fname} not in any package"
            continue
        w, h, frames = shp_td.read_shp(got[0])
        facings = int(prop(s, base, "Facings", "1") or 1)
        facings = abs(facings)
        start = int(prop(s, base, "Start", "0") or 0)
        turret = None
        if "turret" in s:
            tf = prop(s, "turret", "Filename")
            tg = find(index, tf) if tf and tf != fname else None
            tw, th, tframes = shp_td.read_shp(tg[0]) if tg else (w, h, frames)
            tfac = abs(int(prop(s, "turret", "Facings", "1") or 1))
            tstart = int(prop(s, "turret", "Start", "0") or 0)
            if tfac >= facings and tfac % max(facings, 1) == 0 and tstart + tfac <= len(tframes):
                turret = (tw, th, tframes, tstart, tfac // max(facings, 1))
        order = list(range(start, start + facings)) if facings > 1 else [start]
        run = None
        if "run" in s and facings == 8:
            rs = int(prop(s, "run", "Start", "0") or 0)
            rl = int(prop(s, "run", "Length", "1") or 1)
            run = (rs, rl)
            order = list(range(start, start + 8)) + list(range(rs, rs + 8 * rl))
        if max(order) >= len(frames):
            skipped[actor] = f"frame {max(order)} beyond {len(frames)} in {fname}"
            continue
        paths = []
        for f in order:
            im = rgba(frames[f], w, h, palette)
            if turret and f < start + facings:
                tw, th, tframes, tstart, mult = turret
                t = rgba(tframes[tstart + (f - start) * mult], tw, th, palette)
                if (tw, th) == (w, h):
                    im.alpha_composite(t)
            im.save(ART / "openra" / f"{actor}-{f:04d}.png")
            paths.append(f"res://client/hybrid/art/openra/{actor}-{f:04d}.png")
        item = {"id": item_id, "status": "imported", "game": "openra", "license": LICENSE, "source": f"{fname} {base} Facings {facings} from {got[1]}",
                "source_note": f"mods/ra/sequences/*.yaml parsed by import_openra_roster.py; palette temperat", "godot": paths[0], "frames_godot": paths,
                "mode": "sequence", "frame_indexes": order, "facings": facings, "length": 1, "hotspot": [w // 2, int(h * 0.85)], "scale": 3 if w <= 36 else CELL,
                "fps": 0, "prefix": actor}
        if turret:
            item["source"] += " + turret composited"
        if run:
            item.update(length=run[1], fps=10, stand_start=0, run_start=run[0], run_length=run[1], run_facings=8, scale=3)
        by_id[item_id] = item
        added.append(actor)
    cat["items"] = sorted(by_id.values(), key=lambda i: i["id"])
    CAT.write_text(json.dumps(cat, indent=1), encoding="utf-8")
    out = HYB / "docs" / "evidence" / "assets"
    out.mkdir(parents=True, exist_ok=True)
    (out / "openra_roster_import.json").write_text(json.dumps({"imported": added, "not_imported": skipped}, indent=1, sort_keys=True))
    print("imported", len(added), added)
    print("not imported", skipped)
    return 0


if __name__ == "__main__":
    sys.exit(main())
