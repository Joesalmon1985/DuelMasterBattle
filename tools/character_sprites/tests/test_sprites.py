"""Sprite generator tests.  Run from the repository root:  python3 -m pytest tools/character_sprites/tests -q"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from character_sprites import build as B  # noqa: E402
from character_sprites import clips as C  # noqa: E402
from character_sprites import palettes as P  # noqa: E402
from character_sprites.outfits import draw_outfit  # noqa: E402
from character_sprites.outfits_db import OUTFITS  # noqa: E402
from character_sprites.raster import Frame, render  # noqa: E402
from character_sprites.rig import CELL_H, CELL_W, Figure  # noqa: E402

OUT = ROOT / "godot_project" / "assets" / "characters"
DEFS = ROOT / "WizardRTSHybrid" / "wizard_rts" / "data" / "widelands_defs.json"
RULES = ROOT / "WizardRTSHybrid" / "wizard_rts" / "data" / "openra_rules.json"


def _frame(oid: str, clip: str, i: int, view: str):
    o = OUTFITS[oid]
    f = B.fig_for(clip, i, view, o["body"], o["spec"].get("pose_mod"))
    draw_outfit(f, o["spec"])
    return render(f.prims, Frame(CELL_W, CELL_H))


@pytest.mark.parametrize("oid", sorted(OUTFITS))
def test_outfit_renders_and_layers_never_overlap(oid):
    for clip, i in (("idle", 0), ("walk", 2), ("talk", 1)):
        for view in C.VIEWS:
            out = _frame(oid, clip, i, view)
            alphas = [out[k][..., 3] > 0 for k in B.LAYER_BANDS]
            total = sum(a.astype(int) for a in alphas)
            assert total.max() <= 1, f"{oid} {clip} {view}: a pixel is owned by two layers"
            assert total.sum() > 150, f"{oid} {clip} {view}: almost nothing was drawn"
            ys, xs = np.nonzero(total)
            assert xs.min() >= 0 and xs.max() < CELL_W and ys.max() < CELL_H


def test_every_clip_fits_the_cell_for_a_full_set_outfit():
    for clip in C.CLIPS_FULL:
        for i in range(C.FRAMES[clip]):
            for view in C.VIEWS:
                out = _frame("wizard", clip, i, view)
                solid = out["_solid"]
                assert solid.any(), f"{clip}{i} {view} is empty"
                ys, xs = np.nonzero(solid)
                # nothing may be cut by the cell border (the dead body lies on the ground inside the cell)
                assert xs.min() > 0 and xs.max() < CELL_W - 1, f"{clip}{i} {view} touches the side of the cell"
                assert ys.min() >= 0 and ys.max() < CELL_H, f"{clip}{i} {view} leaves the cell vertically"


def test_walk_cycle_moves_the_legs_and_idle_is_subtle():
    walk = [b"".join(_frame("farmer", "walk", i, "side")[k].tobytes() for k in B.LAYER_BANDS) for i in range(6)]
    assert len(set(walk)) == 6, "every walking frame is different (legs swap in front / behind)"
    idle = [_frame("farmer", "idle", i, "down")["_solid"] for i in range(4)]
    base = idle[0]
    for k in range(1, 4):
        assert int((idle[k] != base).sum()) < 60, "idle motion must stay small"


def test_talking_changes_the_mouth_and_the_gesture():
    frames = [_frame("elder", "talk", i, "down") for i in range(6)]
    details = {f["detail"].tobytes() for f in frames}
    assert len(details) >= 4, "the talk loop shows several mouth shapes"


def test_generation_is_deterministic():
    a = B.build_outfit(OUTFITS["baker"]["spec"], "adult", C.CLIPS_CIVIL)
    b = B.build_outfit(OUTFITS["baker"]["spec"], "adult", C.CLIPS_CIVIL)
    assert a.tobytes() == b.tobytes()


def test_clip_set_is_a_prefix_so_hair_sheets_fit_every_outfit():
    assert C.CLIPS_FULL[: len(C.CLIPS_CIVIL)] == C.CLIPS_CIVIL


@pytest.mark.skipif(not DEFS.exists(), reason="simulation data not present")
def test_every_widelands_worker_is_a_known_person_or_animal():
    defs = json.loads(DEFS.read_text())["workers"]
    tribes = ("barbarians", "empire", "atlanteans", "frisians", "amazons")
    unknown = []
    for name in defs:
        job = name
        for t in tribes:
            if job.startswith(t + "_"):
                job = job[len(t) + 1:]
        if job == "soldier" or job in P.JOBS or job in P.ANIMAL_JOBS:
            continue
        unknown.append(name)
    assert not unknown, f"workers without an outfit: {unknown}"


@pytest.mark.skipif(not RULES.exists(), reason="simulation data not present")
def test_every_infantry_actor_has_an_outfit():
    actors = json.loads(RULES.read_text())["actors"]
    foot = [k for k, v in actors.items() if v.get("mobile") and v.get("locomotor") == "foot"]
    missing = [k for k in foot if k not in P.OPENRA and k != "dog"]
    assert not missing, f"infantry without an outfit: {missing}"


def test_palette_and_named_tables_point_at_real_outfits():
    for job, outfit in P.JOBS.items():
        assert outfit in OUTFITS, (job, outfit)
    for name, spec in P.NAMED.items():
        assert spec["outfit"] in OUTFITS, (name, spec)
    for table in (P.OPENRA, P.DMB, P.SOLDIER_BY_TRIBE):
        for k, v in table.items():
            assert v in OUTFITS, (k, v)


@pytest.mark.skipif(not (OUT / "characters.json").exists(), reason="sheets not generated")
def test_generated_assets_match_the_manifest():
    data = json.loads((OUT / "characters.json").read_text())
    cols = {s: sum(C.FRAMES[c] for c in cs) for s, cs in data["clip_sets"].items()}
    for oid, o in data["outfits"].items():
        im = Image.open(OUT / "outfits" / f"{oid}.png")
        assert im.size == (cols[o["clips"]] * CELL_W, CELL_H * 3 * len(B.LAYER_BANDS)), oid
        assert (OUT / "outfits" / f"{oid}_p.png").exists(), oid
        for h in o["hairs"]:
            if h != "bald":
                assert (OUT / "hair" / f"hair_{o['body']}_{h}.png").exists(), (oid, h)
        for b in o["beards"]:
            if b != "none":
                assert (OUT / "hair" / f"beard_adult_{b}.png").exists(), (oid, b)
