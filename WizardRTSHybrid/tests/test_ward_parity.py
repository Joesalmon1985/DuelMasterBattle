"""The Python Ward Duel core (wizard_rts/duel/ward.py) against the real GDScript (fixture exported by
client/tests/export_ward_parity.gd; GODOT_PARITY=1 re-exports it)."""
import gzip
import json
import os
import subprocess
from pathlib import Path

import pytest

from wizard_rts.duel import ward as W

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "ward_parity.json.gz"


@pytest.fixture(scope="module")
def data():
    if os.environ.get("GODOT_PARITY") == "1":
        godot = os.environ.get("GODOT", os.path.expanduser("~/godot451/Godot_v4.5.1-stable_linux.x86_64"))
        out = ROOT / "tests" / "fixtures" / "_fresh_ward.json"
        subprocess.run([godot, "--headless", "--path", str(ROOT.parent / "godot_project"), "--script", "res://client/tests/export_ward_parity.gd", "--", str(out)],
                       check=True, capture_output=True)
        d = json.loads(out.read_text(encoding="utf-8"))
        out.unlink()
        return d
    with gzip.open(FIX, "rt", encoding="utf-8") as f:
        return json.load(f)


def test_score_attack_and_guess_match(data):
    for e in data["feedback"]:
        assert json.loads(json.dumps(W.score_attack(e["ward"], e["attack"]))) == e["result"]
        if "guess" in e:
            assert list(W.score_guess(e["ward"], e["attack"])) == e["guess"]
    sizes = {(len(e["ward"]), len(e["attack"])) for e in data["feedback"]}
    assert any(a != b for a, b in sizes)  # unequal weave and ward sizes are covered


def test_match_results_match(data):
    outcomes = set()
    for e in data["results"]:
        r = W.compute_result(e["hs"], e["bs"], e["hc"], e["bc"], [tuple(x) for x in e["hg"]], [tuple(x) for x in e["bg"]], 12)
        assert r["outcome"] == e["outcome"]
        outcomes.add(r["outcome"])
    assert outcomes == {"human_win", "bot_win", "draw"}


def test_candidate_generation_matches(data):
    for c in data["codes"]:
        codes = W.generate_codes(c["pool"], c["slots"], c["repeats"])
        assert len(codes) == c["count"] and codes[:3] == c["first"] and codes[-3:] == c["last"]


def test_weave_bot_plays_identically_to_the_game(data):
    for b in data["bots"]:
        cm = b["combatant"]
        me = W.Combatant(id="bot", weave_size=cm["weave_size"], attack_pool=cm["attack_pool"], ward_size=cm["ward_size"], ward_pool=cm["ward_pool"],
                         allow_repeats=cm["allow_repeats"], bot_logic=cm["bot_logic"])
        bot = W.WeaveBot(me, me, b["seed"])
        ward = bot.generate_ward()
        assert ward == b["ward"], (b["cfg"], b["seed"])
        for rd in b["rounds"]:
            g = bot.make_guess()
            sc = W.score_attack(ward, g)
            bot.register_feedback(g, sc["fracture"], sc["echo"])
            assert g == rd["guess"] and len(bot.candidates) == rd["cands"], (b["cfg"], b["seed"])


def test_wardduel_never_leaks_the_enemy_ward_and_ends_by_the_rules():
    pool = [0, 1, 3, 4, 6, 9]
    p = W.Combatant(id="p", kind="player", weave_size=4, attack_pool=pool, ward_size=4, ward_pool=pool, max_casts=10)
    e = W.Combatant(id="e", weave_size=4, attack_pool=pool, ward_size=4, ward_pool=pool, max_casts=10)
    d = W.WardDuel(p, e, seed=11)
    assert d.cast([0, 1, 2, 3])["reason"] == "illegal_attack"  # 2 is not in the player's pool
    assert "enemy_ward" not in json.dumps(d.public_view()) and str(d.enemy_ward) not in json.dumps(d.public_view())
    n = 0
    while not d.done and n < 12:
        d.cast([pool[n % 6], pool[(n + 1) % 6], pool[(n + 2) % 6], pool[(n + 3) % 6]])
        n += 1
    assert d.done and d.result["outcome"] in ("human_win", "bot_win", "draw") and len(d.player_history) <= 10
    assert d.cast([0, 0, 0, 0]) == {"status": "finished"}
