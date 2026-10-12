"""Genuine Widelands maps translated to the square grid: terrain, heights, resources and start positions come from the files.

Level A/B/C: the translation is checked against the source files; the live world on each map is run for a few minutes.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ["HYBRID_AI"] = "0"

import pytest  # noqa: E402

from wizard_rts import terrain as T, wl_map  # noqa: E402
from wizard_rts.workers import find_path  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402

MAPS = wl_map.available()


def test_two_six_player_maps_are_shipped_with_their_credits() -> None:
    assert set(MAPS) == {"The_Big_Lake", "Egyptian_Mandala_v1.2"}
    for name in MAPS:
        g = wl_map.load(name)
        assert g.meta["author"] and g.meta["source"].startswith("widelands/widelands") and "translation" in g.meta
        assert len(g.starts) == 6 and g.meta["generator"] == "widelands_map"


def test_translation_matches_the_source_files() -> None:
    root = wl_map.MAPS / "The_Big_Lake.wmf"
    data = (root / "binary" / "heights").read_bytes()
    g = wl_map.load("The_Big_Lake")
    assert (g.w, g.h) == (192, 192)
    # heights are copied node for node (after the two-byte version and, in version 2, one byte of maximum difference)
    version = int.from_bytes(data[:2], "little")
    offset = 2 + (1 if version >= 2 else 0)
    assert bytes(g.height) == data[offset:offset + 192 * 192]
    # the start positions are those of the file
    assert g.meta["all_starts"][0] == [57, 47] and g.meta["all_starts"][5] == [28, 128]
    # a big lake: water bodies exist, the largest is a real lake, and fish live in it
    s = g.summary()
    assert s["largest_water"] > 12000 and s["resources"]["fish"] > 50000
    assert s["resources"]["coal"] > 10000 and s["resources"]["iron"] > 5000 and s["resources"]["gold"] > 1000 and s["resources"]["stones"] > 3000
    # resources only sit where Widelands allows them: ore in mountains, fish in water
    for i in range(g.w * g.h):
        kind = g.res_kind[i]
        if kind in (T.RES_COAL, T.RES_IRON, T.RES_GOLD, T.RES_STONES):
            assert g.cls[i] == T.MINEABLE
        if kind == T.RES_FISH:
            assert g.cls[i] == T.WATER


def test_unknown_map_and_too_few_starts_are_refused() -> None:
    with pytest.raises(FileNotFoundError):
        wl_map.load("No_Such_Map")
    with pytest.raises(ValueError):
        wl_map.load("The_Big_Lake", players=7)


@pytest.mark.parametrize("name", MAPS)
def test_world_runs_on_a_widelands_map(name: str) -> None:
    w = HybridWorld(507, map_size="wmf:" + name)
    t = w.terrain
    caps = [(b["tx"], b["ty"]) for b in w.buildings.values() if b["kind"] == "warehouse"]
    assert len(caps) == 6 and all(t.ground(*c) and t.build_cap_name(*c).startswith("big") for c in caps)
    for other in caps[1:]:
        assert find_path(w, caps[0], other, limit=400, max_nodes=600_000) is not None  # the six homelands are joined by land
    assert not w.layout_notes, w.layout_notes
    for tree in w.trees.values():
        assert t.class_at(tree["tx"], tree["ty"]) == T.ARABLE
    for i in range(240):  # four game minutes of the full economy
        w.advance(1000, i + 1, snapshot=False)
    assert w.stats["deliver"] > 0 and w.stats.get("made_log", 0) > 0 and w.stats.get("made_granite", 0) > 0


def test_same_map_same_seed_same_state() -> None:
    def run() -> str:
        w = HybridWorld(11, map_size="wmf:The_Big_Lake")
        for i in range(60):
            w.advance(1000, i + 1, snapshot=False)
        return w.state_hash()

    assert run() == run()
