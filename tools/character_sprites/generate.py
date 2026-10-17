"""python -m character_sprites.generate [--only id,...]: build every sheet into godot_project/assets/characters and write characters.json."""
from __future__ import annotations

import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

from . import build as B
from . import clips as clipmod
from . import hair as hairmod
from . import palettes as P
from .outfits_db import OUTFITS

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "godot_project" / "assets" / "characters"


def _clipset(name: str) -> list[str]:
    return clipmod.CLIPS_FULL if name == "full" else clipmod.CLIPS_CIVIL


def _outfit_job(args):
    oid, = args
    o = OUTFITS[oid]
    cs = _clipset(o["clips"])
    img = B.build_outfit(o["spec"], o["body"], cs)
    img.save(OUT / "outfits" / f"{oid}.png", optimize=True)
    B.build_portrait(o["spec"], o["body"]).save(OUT / "outfits" / f"{oid}_p.png", optimize=True)
    return oid


def _hair_job(args):
    kind, style, body = args
    img = B.build_hair(kind, style, body, clipmod.CLIPS_FULL)
    img.save(OUT / "hair" / f"{kind}_{body}_{style}.png", optimize=True)
    B.build_hair_portrait(kind, style, body).save(OUT / "hair" / f"{kind}_{body}_{style}_p.png", optimize=True)
    return (kind, style, body)


def main(argv: list[str]) -> None:
    only = None
    if "--only" in argv:
        only = set(argv[argv.index("--only") + 1].split(","))
    (OUT / "outfits").mkdir(parents=True, exist_ok=True)
    (OUT / "hair").mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    jobs = [(oid,) for oid in OUTFITS if only is None or oid in only]
    hair_jobs = []
    if only is None:
        bodies = {"adult": hairmod.HAIR_STYLES, "child": ["short", "swept", "ponytail", "bun", "spiky", "curly", "bob", "braid"]}
        for body, styles in bodies.items():
            for st in styles:
                if st != "bald":
                    hair_jobs.append(("hair", st, body))
        for st in hairmod.BEARD_STYLES:
            if st != "none":
                hair_jobs.append(("beard", st, "adult"))
    with Pool() as pool:
        for r in pool.imap_unordered(_outfit_job, jobs):
            print("outfit", r, f"{time.time() - t0:.0f}s", flush=True)
        for r in pool.imap_unordered(_hair_job, hair_jobs):
            print("hair", r, f"{time.time() - t0:.0f}s", flush=True)
    write_manifest()


def write_manifest() -> None:
    from .build import LAYER_BANDS, PORTRAIT, PORTRAIT_POSES
    from .rig import CELL_H, CELL_W
    data = {
        "version": 1,
        "cell": [CELL_W, CELL_H],
        "portrait": {"size": PORTRAIT, "poses": [n for n, _ in PORTRAIT_POSES]},
        "bands": LAYER_BANDS,
        "views": clipmod.VIEWS,
        "clips": B.clip_table(clipmod.CLIPS_FULL),
        "clip_sets": {"civil": clipmod.CLIPS_CIVIL, "full": clipmod.CLIPS_FULL},
        "fps": {"idle": 3, "walk": 9, "talk": 8, "hurt": 8, "die": 7, "surprise": 6, "work": 5, "cast": 8, "celebrate": 7, "revive": 6},
        "loop": {"idle": True, "walk": True, "talk": True, "hurt": False, "die": False, "surprise": False, "work": True, "cast": False, "celebrate": True},
        "outfits": {k: {"body": v["body"], "clips": v["clips"], "hairs": v["hairs"], "beards": v["beards"], "pal": {a: (list(b) if isinstance(b, tuple) else b) for a, b in v["pal"].items()},
                        "magic": list(v["spec"].get("magic", (150, 220, 255)))} for k, v in OUTFITS.items()},
        "hair_styles": {"adult": [s for s in hairmod.HAIR_STYLES if s != "bald"], "child": ["short", "swept", "ponytail", "bun", "spiky", "curly", "bob", "braid"]},
        "beard_styles": [s for s in hairmod.BEARD_STYLES if s != "none"],
        "skin": [list(c) for c in P.SKIN], "skin_weights": P.SKIN_W,
        "hair": [list(c) for c in P.HAIR], "hair_weights": P.HAIR_W,
        "tribes": {k: [[list(c) for c in tri] for tri in v] for k, v in P.TRIBES.items()},
        "wizard_sets": [[list(c) for c in s] for s in P.WIZARD_SETS],
        "named": {k: {a: (list(b) if isinstance(b, tuple) else ({x: list(y) for x, y in b.items()} if isinstance(b, dict) else b)) for a, b in v.items()} for k, v in P.NAMED.items()},
        "jobs": P.JOBS, "soldiers": P.SOLDIER_BY_TRIBE, "openra": P.OPENRA, "dmb": P.DMB,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "characters.json").write_text(json.dumps(data, indent=1, sort_keys=True))
    print("manifest written", OUT / "characters.json")


if __name__ == "__main__":
    main(sys.argv[1:])
