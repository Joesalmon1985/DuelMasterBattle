"""The Python puzzle port (wizard_rts/puzzle) against what the real GDScript produced.

Fixture: tests/fixtures/puzzle_parity.json.gz, exported by `godot --headless --path godot_project --script
res://client/tests/export_puzzle_parity.gd -- <out.json>` (80 dungeons, 4 puzzles each, 4 action scripts each, 12 dungeon maps,
RNG probes). Regenerate it with that command when puzzle_gen.gd, puzzle_logic.gd or dungeon_map.gd change; the test also reruns
Godot when GODOT_PARITY=1 is set, so a stale fixture cannot hide a divergence.
"""
import gzip
import json
import os
import subprocess
from pathlib import Path

import pytest

from wizard_rts.puzzle import dungeon, gen, items, logic
from wizard_rts.puzzle.rng import GodotRng

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "puzzle_parity.json.gz"


@pytest.fixture(scope="module")
def data():
    if os.environ.get("GODOT_PARITY") == "1":
        godot = os.environ.get("GODOT", os.path.expanduser("~/godot451/Godot_v4.5.1-stable_linux.x86_64"))
        out = ROOT / "tests" / "fixtures" / "_fresh_parity.json"
        subprocess.run([godot, "--headless", "--path", str(ROOT.parent / "godot_project"), "--script", "res://client/tests/export_puzzle_parity.gd", "--", str(out)],
                       check=True, capture_output=True)
        return json.loads(out.read_text(encoding="utf-8"))
    with gzip.open(FIX, "rt", encoding="utf-8") as f:
        return json.load(f)


def test_godot_rng_matches(data):
    for probe in data["rng"]:
        r = GodotRng(probe["seed"])
        assert [r.randi() for _ in range(8)] == probe["randi"]
        r2 = GodotRng(probe["seed"])
        for name, (lo, hi) in (("range_0_1", (0, 1)), ("range_0_2", (0, 2)), ("range_1_3", (1, 3)), ("range_0_5", (0, 5)), ("range_0_8", (0, 8))):
            assert [r2.randi_range(lo, hi) for _ in range(8)] == probe[name], (probe["seed"], name)


def test_generated_puzzles_match_for_80_seeds(data):
    kinds = set()
    for e in data["puzzles"]:
        d = {k: v for k, v in e["dungeon"].items() if k != "puzzles"}
        mine = gen.generate(d)
        assert mine == e["dungeon"]["puzzles"], d["id"]
        kinds.update(p["type"] for p in mine)
        assert sum(1 for p in mine if p["type"] == "offerings") == 1  # always one dependency room
    assert kinds == set(gen.TEMPLATES)  # every template occurs in the sample


def test_logic_matches_step_by_step(data):
    steps = 0
    for e in data["puzzles"]:
        for p, tr in zip(e["dungeon"]["puzzles"], e["traces"]):
            for sc in tr["scripts"]:
                st = logic.fresh_state(p)
                assert st == sc["fresh"]
                for a, step in zip(sc["actions"], sc["steps"]):
                    r = logic.act(p, st, a, sc["ctx"])
                    assert json.loads(json.dumps(r)) == step["result"], (p["type"], a)
                    assert json.loads(json.dumps(st)) == step["state"], (p["type"], a)
                    steps += 1
    assert steps > 3000


def test_every_generated_puzzle_is_solvable_by_the_solution(data):
    for e in data["puzzles"]:
        for p in e["dungeon"]["puzzles"]:
            st = logic.fresh_state(p)
            ctx = {"items": ["clay_idol", "brass_gear", "tallow_candle", "mirror_shard", "black_seed", "grey_stone", "iron_key", "sigil_ash", "sigil_vale"], "spells": [0, 1, 6]}
            for a in logic.solution(p):
                logic.act(p, st, a, ctx)
            assert st["solved"], p["type"]


def test_dungeon_maps_match(data):
    by = {e["dungeon"]["id"]: e["dungeon"] for e in data["puzzles"]}
    for m in data["maps"]:
        d = by[m["dungeon_id"]]
        states = {}
        for p in d["puzzles"]:
            st = logic.fresh_state(p)
            st["solved"] = True
            states["%s/%s" % (d["id"], p["id"])] = st
        for mine, theirs in ((dungeon.area_for(d, {}, "node_1", [3, 4]), m["area"]), (dungeon.area_for(d, states, "node_1", [3, 4]), m["area_solved"])):
            mine = json.loads(json.dumps(mine))
            assert mine["rows"] == theirs["rows"] and mine["entities"] == theirs["entities"] and mine["name"] == theirs["name"]


def test_item_names_match_godot_capitalize():
    assert items.name_of("sigil_x12") == "Sigil of X 12"
    assert items.name_of("sigil_vale") == "Sigil of Vale"
    assert items.name_of("iron_key") == "Iron key"
    assert items.essence_name(1) == "Frost" and items.essence_name(99) == "?"
