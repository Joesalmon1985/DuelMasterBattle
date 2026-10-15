#!/usr/bin/env python3
"""Import Red Alert BUILDING art with its states and construction animation (owner programme 13 Oct 2026, section 9).

For every building actor of the roster the sequence YAML (mods/ra/sequences/structures.yaml) names the sprite files and frame ranges:
  idle           the finished building (Start/Length: radar dishes, silos and turrets animate through several frames)
  damaged-idle   the same building at half health      critical-idle   nearly dead
  make           the construction animation (all frames of the make file)
  turret / damaged-turret  defence turrets turn through their facings; extra animated overlays (`active`, `idle-*`) are kept when they have several frames
The frames are decoded from the player's own Red Alert packages with the temperate palette. One catalogue item `openra.<actor>` per building gets a `states`
map {state: {files, fps}}; existing items keep their files and gain the states. Run: python3 scripts/import_openra_buildings.py [content dir]
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

HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB / "scripts"))
import import_openra_roster as R  # noqa: E402
import shp_td  # noqa: E402

ART, CAT, SEQ, RULES = R.ART, R.CAT, R.SEQ, R.RULES
STATES = {"idle": "idle", "damaged-idle": "damaged", "critical-idle": "critical", "make": "make", "turret": "turret", "damaged-turret": "damaged_turret", "active": "active",
          "damaged-active": "damaged_active", "idle-turret": "turret", "powerdown": "unpowered", "damaged-powerdown": "unpowered_damaged"}


def main() -> int:
    content = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / "Videos/.config/openra/Content/ra/v2")
    index = R.package_index(content)
    palette = R.Image.open(ART / "openra" / "weap-0000.png").getpalette()
    rules = json.loads(RULES.read_text())["actors"]
    cat = json.loads(CAT.read_text(encoding="utf-8"))
    by_id = {i["id"]: i for i in cat["items"]}
    seqs = R.parse_yaml(SEQ / "structures.yaml")
    done, skipped = [], {}
    cache: dict[str, tuple] = {}
    for actor, r in sorted(rules.items()):
        if not r.get("is_building"):
            continue
        s = seqs.get(actor)
        if not s:
            skipped[actor] = "no sequence"
            continue
        states: dict = {}
        for seq, name in STATES.items():
            if seq not in s:
                continue
            fname = R.prop(s, seq, "Filename")
            if not fname:
                continue
            if fname not in cache:
                got = R.find(index, fname)
                cache[fname] = (shp_td.read_shp(got[0]), got[1]) if got else None
            if cache[fname] is None:
                continue
            (w, h, frames), pkg = cache[fname]
            start = int(R.prop(s, seq, "Start", "0") or 0)
            length_s = R.prop(s, seq, "Length", "1") or "1"
            length = len(frames) - start if length_s == "*" else int(length_s)
            facings = abs(int(R.prop(s, seq, "Facings", "1") or 1))
            n = length if facings <= 1 else facings
            order = [f for f in range(start, start + n) if f < len(frames)]
            if not order:
                continue
            files = []
            for f in order:
                p = ART / "openra" / f"{actor}-b-{name}-{f:04d}.png"
                if not p.exists():
                    R.rgba(frames[f], w, h, palette).save(p)
                files.append(f"res://client/hybrid/art/openra/{p.name}")
            states[name] = {"files": files, "fps": 8 if (len(files) > 1 and facings <= 1 and name != "make") else (12 if name == "make" else 0), "facings": facings if facings > 1 else 1,
                            "source": f"{fname} {seq} Start {start} Length {length_s} from {pkg}", "width": w, "height": h}
        if "idle" not in states and "make" in states:  # defences without an idle picture: the finished building is the last frame of its construction animation
            m = states["make"]
            states["idle"] = {**m, "files": m["files"][-1:], "fps": 0}
        if "idle" not in states and "turret" in states:
            states["idle"] = {**states["turret"], "files": states["turret"]["files"][:1], "fps": 0}
        if "idle" not in states:
            skipped[actor] = "no idle frames in the packages"
            continue
        item = by_id.get(f"openra.{actor}") or {"id": f"openra.{actor}", "status": "imported", "game": "openra", "license": R.LICENSE, "source_note": "mods/ra/sequences/structures.yaml",
                                                "godot": states["idle"]["files"][0], "mode": "sheet", "width": states["idle"]["width"], "height": states["idle"]["height"], "frames": 1, "columns": 1,
                                                "rows": 1, "fps": 0, "hotspot": [states["idle"]["width"] // 2, int(states["idle"]["height"] * 0.85)], "scale": R.CELL}
        item["source"] = item.get("source") or states["idle"]["source"]
        item["states"] = states
        item["status"] = "imported"
        by_id[item["id"]] = item
        done.append(actor)
    FAKES = {"atef": "atek", "domf": "dome", "facf": "fact", "fapw": "apwr", "fixf": "fix", "fpwr": "powr", "mslf": "mslo", "pdof": "pdox", "syrf": "syrd", "tenf": "tent", "weaf": "weap", "spef": "spen"}
    for fake, real in FAKES.items():  # a fake building is drawn exactly like the real one (that is its purpose)
        src = by_id.get(f"openra.{real}")
        if src is not None and "states" in src and fake in rules:
            by_id[f"openra.{fake}"] = {**src, "id": f"openra.{fake}", "alias_of": f"openra.{real}", "source_note": f"a fake building uses the art of the {real} (mods/ra/sequences/fakes)"}
            done.append(fake)
            skipped.pop(fake, None)
    cat["items"] = sorted(by_id.values(), key=lambda i: i["id"])
    CAT.write_text(json.dumps(cat, indent=1), encoding="utf-8")
    out = HYB / "docs" / "evidence" / "assets"
    (out / "openra_building_import.json").write_text(json.dumps({"imported": done, "not_imported": skipped}, indent=1, sort_keys=True))
    print("imported", len(done), "not", skipped)
    return 0


if __name__ == "__main__":
    sys.exit(main())
