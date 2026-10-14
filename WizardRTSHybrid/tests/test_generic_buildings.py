"""The Lua importer and the data-driven building path."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wizard_rts import wl_defs  # noqa: E402
from wizard_rts.programs_data import BUILDING_PROGRAMS  # noqa: E402

HYBRID = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, HYBRID / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    # The importers refuse to run while the roster is frozen (D33); this test only reads their parsing helpers, so unfreeze for the import alone.
    with mock.patch.dict(os.environ, {"DMB_UNFREEZE": "1", "DMB_UNFREEZE_REASON": "unit test of parsing helpers"}):
        spec.loader.exec_module(module)
    return module


def test_lua_durations_and_ware_names() -> None:
    imp = _load_script("import_widelands_programs")
    assert imp.duration_ms("23s400ms") == 23_400
    assert imp.duration_ms("1m5s") == 65_000
    assert imp.duration_ms("8m20s") == 500_000
    assert imp.duration_ms("500ms") == 500
    assert imp.ware("barbarians_bread") == "bread" and imp.ware("planks") == "plank"
    assert imp.wares("log:2 plank") == {"log": 2, "plank": 1}
    assert imp.wares("barbarians_bread,fish,meat") == {"|": ["bread", "fish", "meat"]}


def test_importer_found_the_catalogue() -> None:
    d = wl_defs.defs()
    assert len(d["buildings"]) >= 230 and len(d["workers"]) >= 150 and len(d["wares"]) >= 120
    assert d["errors"] == []
    assert len(wl_defs.runnable_names()) >= 100
    # attributes come from register.lua
    assert "ripe_wheat" in d["immovables"]["wheatfield_ripe"]["attributes"]
    assert "tree_sapling" in d["immovables"]["beech_summer_sapling"]["attributes"]


def _totals(program) -> tuple[int, dict, dict]:
    ms, eaten, made = 0, {}, {}
    for cmd, args in program:
        if cmd in ("sleep", "animate"):
            ms += args["ms"]
        elif cmd == "consume":
            for g, n in args.items():
                eaten[g] = eaten.get(g, 0) + n
        elif cmd == "produce":
            for g, n in args.items():
                made[g] = made.get(g, 0) + n
    return ms, eaten, made


def test_hand_transcribed_programs_agree_with_the_imported_lua() -> None:
    pairs = {"processor": "empire_sawmill", "smithy": "barbarians_ax_workshop", "bakery": "barbarians_bakery", "smelter": "barbarians_smelting_works"}
    for kind, name in pairs.items():
        generic = wl_defs.building_spec(name)["programs"]["main"]
        hand = BUILDING_PROGRAMS[kind]
        if kind == "smithy":  # the hand version keeps only produce_ax; the import has three ax programmes
            generic = wl_defs.building_spec(name)["programs"]["produce_ax"]
        if kind == "smelter":
            generic = wl_defs.building_spec(name)["programs"]["smelt_iron"]
        gms, geat, gmade = _totals(generic)
        hms, heat, hmade = _totals(hand)
        assert (gms, geat, gmade) == (hms, heat, hmade), (kind, (gms, geat, gmade), (hms, heat, hmade))


def test_a_sample_of_imported_buildings_runs_in_the_bench() -> None:
    bench = _load_script("verify_generic_buildings").bench
    for name in (
        "barbarians_lumberjacks_hut", "barbarians_farm", "barbarians_hunters_hut", "barbarians_quarry",
        "barbarians_coalmine", "barbarians_smelting_works", "empire_sawmill", "empire_brewery", "atlanteans_bakery",
        "frisians_hunters_house",
    ):
        if name not in wl_defs.defs()["buildings"] or not wl_defs.defs()["buildings"][name].get("runnable"):
            continue
        result = bench(name, 15)
        assert result["passed"], result


def test_imported_buildings_can_be_built_and_cost_their_source_buildcost() -> None:
    from wizard_rts import construction as con
    from wizard_rts.world import HybridWorld

    menu = con.full_menu()
    assert "wl:empire_lumberjacks_house" in menu and len(menu) > 100
    w = HybridWorld()
    w.ai_enabled = False
    wh = next(b for b in w.buildings.values() if b["kind"] == "warehouse" and b["faction_name"] == "Red")
    res = None
    for dx in range(4, 14):
        res = w.build("Red", "wl:empire_lumberjacks_house", wh["tx"] + dx, wh["ty"] + 9)
        if res["status"] == "ok":
            break
    assert res["status"] == "ok", res
    site = w.buildings[res["id"]]
    assert site["constructing"]["cost"] == menu["wl:empire_lumberjacks_house"]["cost"] == wl_defs.defs()["buildings"]["empire_lumberjacks_house"]["buildcost"]
