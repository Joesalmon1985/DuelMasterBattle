#!/usr/bin/env python3
"""Separate body and turret layers for the Red Alert vehicles that have a turret (plan v2 8.3 item 2: independent turrets).

The first vehicle importer composited the turret over the body for each of the 32 facings. This adds the two layers as their own files,
`<actor>-body-NNNN.png` and `<actor>-turret-NNNN.png`, and a `layers` entry on the catalogue item so the client can aim the turret at the
unit's target while the hull faces its heading. The composited files are kept, so a client without turret data draws exactly what it did before.
Run: python3 scripts/import_openra_layers.py [path/to/conquer.mix]
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
import import_openra_units as iu  # noqa: E402
import mix_read  # noqa: E402
import shp_td  # noqa: E402
from PIL import Image  # noqa: E402

ACTORS = [k for k, has_turret in iu.VEHICLES.items() if has_turret]


def main() -> None:
    mix = mix_read.Mix(sys.argv[1] if len(sys.argv) > 1 else iu.MIX)
    palette = Image.open(iu.ART / "openra" / "weap-0000.png").getpalette()
    cat = json.loads(iu.CAT.read_text(encoding="utf-8"))
    by_id = {i["id"]: i for i in cat["items"]}
    for name in ACTORS:
        w, h, frames = shp_td.read_shp(mix.read(name.upper() + ".SHP"))
        if len(frames) < 64:
            continue
        for f in range(32):
            iu.rgba(frames[f], w, h, palette).save(iu.ART / "openra" / f"{name}-body-{f:04d}.png")
            iu.rgba(frames[32 + f], w, h, palette).save(iu.ART / "openra" / f"{name}-turret-{f:04d}.png")
        by_id[f"openra.{name}"]["layers"] = {"body_prefix": f"{name}-body", "turret_prefix": f"{name}-turret", "facings": 32,
                                             "note": "turret frames Start 32 Facings 32 (mods/ra/sequences/vehicles.yaml); the composited files remain"}
    cat["items"] = sorted(by_id.values(), key=lambda i: i["id"])
    iu.CAT.write_text(json.dumps(cat, indent=1), encoding="utf-8")
    print("layered", ACTORS)


if __name__ == "__main__":
    main()
