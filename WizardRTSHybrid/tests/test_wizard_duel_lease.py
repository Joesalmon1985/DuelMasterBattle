"""B.2: story Ward Duel leases: the 3x3 tier, the lease shape the board adapter reads, and Python's verification of what Godot reports."""
import copy
import json

import pytest

from wizard_rts import narrative
from wizard_rts.duel import ward
from wizard_rts.narrative import duel_lease, wizard
from wizard_rts.world import HybridWorld


@pytest.fixture()
def world():
    w = HybridWorld(507, profile="campaign")
    narrative.enable(w)
    wizard.learn(w, [0, 1, 6], weave_size=3)
    return w


def combatants(rec):
    enc = rec["encounter"]
    def mk(d):
        return ward.Combatant(id=d["id"], weave_size=d["weave_size"], attack_pool=list(d["attack_pool"]), ward_size=d["ward_size"], ward_pool=list(d["ward_pool"]),
                              allow_repeats=d["allow_repeats"], max_casts=d["max_casts"], fixed_ward=list(d.get("fixed_ward", [])), bot_logic=d["bot_logic"] if "bot_logic" in d else "candidate_filter")
    return mk(enc["player_combatant"]), mk(enc["enemy_combatant"])


def play(rec, *, win=True):
    """Play the lease on the Python core (the same rules the board runs) and build the report Godot would send."""
    player, enemy = combatants(rec)
    duel = ward.WardDuel(player, enemy, seed=rec["bot_seed"])
    solver = ward.WeaveBot(player, enemy, seed=1)
    history = []
    while not duel.done:
        attack = solver.make_guess() if win else [wizard.palette()[0]] * player.weave_size
        r = duel.cast(attack)
        solver.register_feedback(attack, r["fracture"], r["echo"])
        history.append({"pattern": list(attack), "fracture": r["fracture"], "echo": r["echo"], "broke": r["broken"]})
    outcome = {"human_win": "victory", "bot_win": "defeat", "draw": "stalemate"}[duel.result["outcome"]]
    return {"outcome": outcome, "player_casts": len(history), "enemy_casts": len(duel.enemy_history), "history": history, "enemy_ward": list(duel.enemy_ward),
            "player_ward": list(duel.player_ward)}


def test_the_tiers_exist_and_the_lease_has_the_hazard_lease_shape(world):
    from sim.dmb.adventure.duels import load_duel_progression

    tiers = {t["id"]: t for t in load_duel_progression()["progression"]}
    assert tiers["duel.tutorial_3x3"]["slot_count"] == 3 and tiers["duel.tutorial_3x3"]["colour_count"] == 3 and tiers["duel.tutorial_3x3"]["max_casts"] == 8
    r = duel_lease.begin(world, "opponent.teacher_hidden", purpose="hidden_ward")
    assert r["status"] == "started"
    rec = r["payload"]["duel"]
    for k in ("id", "kind", "encounter", "bot_seed", "checkpoint", "pause_token", "state"):
        assert k in rec
    enc = rec["encounter"]
    assert enc["player_combatant"]["weave_size"] == 3 and enc["player_combatant"]["attack_pool"] == [0, 1, 6]
    assert enc["enemy_combatant"]["ward_size"] == 3 and enc["enemy_combatant"]["bot_logic"] == "candidate_filter"
    assert r["payload"]["public"]["duel_id"] == rec["id"]
    assert duel_lease.begin(world, "opponent.teacher_hidden", purpose="x")["reason"] == "duel_open"
    assert world.dmb.clock["pause_tokens"]  # game time stops while the board is open


def test_the_told_ward_lease_has_exactly_that_ward(world):
    rec = duel_lease.begin(world, "opponent.teacher_told", purpose="told_ward", fixed_ward=[1, 6, 1])["payload"]["duel"]
    assert rec["encounter"]["enemy_combatant"]["fixed_ward"] == [1, 6, 1]
    assert duel_lease.expected_enemy_ward(rec) == [1, 6, 1]


def test_a_truthful_won_duel_resolves_won_and_releases_the_pause(world):
    rec = duel_lease.begin(world, "opponent.teacher_hidden", purpose="hidden_ward")["payload"]["duel"]
    report = play(rec, win=True)
    assert report["outcome"] == "victory" and report["history"][-1]["broke"]
    out = duel_lease.resolve(world, rec["id"], report)
    assert out["status"] == "resolved" and out["outcome"] == "won" and out["verified"]
    assert not world.dmb.clock["pause_tokens"] and rec["state"] == "RESOLVED"
    assert wizard.wiz(world)["duels"]["won"] == 1 and wizard.wiz(world)["duels"]["attempts"][0]["purpose"] == "hidden_ward"
    assert duel_lease.resolve(world, rec["id"], report)["status"] == "idempotent"  # a duplicate report changes nothing
    assert wizard.wiz(world)["duels"]["won"] == 1


def test_a_lost_duel_is_recorded_and_a_new_attempt_has_a_new_seed(world):
    rec = duel_lease.begin(world, "opponent.teacher_hidden", purpose="hidden_ward")["payload"]["duel"]
    report = play(rec, win=False)
    out = duel_lease.resolve(world, rec["id"], report)
    assert out["status"] == "resolved" and out["outcome"] in ("lost", "draw")
    again = duel_lease.begin(world, "opponent.teacher_hidden", purpose="hidden_ward")["payload"]["duel"]
    assert again["attempt"] == 2 and again["bot_seed"] != rec["bot_seed"]


@pytest.mark.parametrize("tamper,why", [
    (lambda r: r.update(enemy_ward=[0, 0, 0]), "enemy_ward_mismatch"),
    (lambda r: r["history"][0].update(fracture=r["history"][0]["fracture"] + 1), "feedback_mismatch"),
    (lambda r: r["history"][0].update(pattern=[9, 9, 9]), "illegal_cast"),
    (lambda r: r.update(player_casts=r["player_casts"] + 3), "cast_count"),
    (lambda r: (r["history"].clear(), r.update(player_casts=0, outcome="victory", enemy_casts=1)), "victory_unearned"),
])
def test_a_report_that_cannot_be_true_is_rejected_and_voids_the_lease(world, tamper, why):
    rec = duel_lease.begin(world, "opponent.teacher_hidden", purpose="hidden_ward")["payload"]["duel"]
    report = copy.deepcopy(play(rec, win=True))
    tamper(report)
    out = duel_lease.resolve(world, rec["id"], report)
    assert out["status"] == "rejected" and out["detail"] == why
    assert rec["state"] == "VOIDED" and not world.dmb.clock["pause_tokens"]
    assert wizard.wiz(world)["duels"]["won"] == 0 and not wizard.wiz(world)["duels"]["attempts"]


def test_checkpoints_never_reroll_the_secret_and_abandon_releases(world):
    rec = duel_lease.begin(world, "opponent.teacher_hidden", purpose="hidden_ward")["payload"]["duel"]
    assert duel_lease.checkpoint(world, rec["id"], {"secret": [1, 6, 0], "player_casts": 1})["status"] == "saved"
    assert duel_lease.checkpoint(world, rec["id"], {"secret": [0, 0, 0]})["reason"] == "secret_reroll_forbidden"
    assert rec["checkpoint"]["secret"] == [1, 6, 0] and rec["checkpoint"]["player_casts"] == 1
    assert duel_lease.abandon(world)["closed"] and not world.dmb.clock["pause_tokens"] and rec["state"] == "VOIDED"
    assert duel_lease.abandon(world)["closed"] is False
