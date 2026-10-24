"""The combined age gate (docs/PLAN_GOD_WORLD_PANDEMIC.md stage 6; D56; the brief's P22 to P24): an age advances only when one faction stands
at ten points AND the age's campaign is won, in either order; a lost campaign pauses the run and the retry resumes it from the age's checkpoint
with a new crisis seed; responders are manufactured at the bases under recorded contracts on the shared clock, one turn every twenty seconds;
the economy-only switch keeps the strategic regression; saves mid-campaign replay exactly."""

from __future__ import annotations

import json

from wizard_rts.god_world import ages, rules
from wizard_rts.god_world.pandemic import rules as R
from wizard_rts.god_world.world import GodWorld


def _running(seed=0, pandemic=True, ops=False):
    w = GodWorld(seed=seed, map_name="Egyptian_Mandala_v1.2")
    w.local_ops_enabled = ops
    w.pandemic_enabled = pandemic
    seq = [0]

    def step(ms=1000):
        seq[0] += 1
        w.advance(ms, seq[0], snapshot=False)

    while w.phase == "SETUP":
        step()
    return w, step


def _finish_campaign(w, step, result: str):
    """Drive the age's campaign to the asked result by the rules (not by editing the result): cure every family, or exhaust the player deck."""
    st = w.pandemic["state"]
    if result == "won":
        for f in R.FAMILIES:
            st["families"][f]["cured"] = True
        R._check_won(st)
    else:
        st["player_deck"] = []
    while w.pandemic["state"]["result"] is None:
        step()
    step()  # the world closes the campaign on its next quantum


def test_p22_the_age_waits_for_the_campaign_when_the_economy_qualifies_first_and_for_the_economy_when_the_campaign_wins_first():
    w, step = _running(0)
    assert w.pandemic is not None and w.pandemic["epoch"] == 1
    assert len(w.history["pandemic_contracts"]) == 6
    # the economy first: ten points, the age does not move
    f = w.fids[0]
    for v in w.faction_villages(f):
        v["level"] = 2
    while w.vp(f) < rules.vp_target():
        node = next(n for n in sorted(w.board.nodes) if w.node_free(n) and w.board.node_hexes[n])
        w._create_village(f, node, level=2, status="operational")
    w.pending_completions.append({"kind": "city", "faction": f, "village": w.faction_villages(f)[0]["id"]})
    w._drain_completions()
    assert w.economic_qualified is not None and w.economic_qualified["faction"] == f
    assert w.age == 1 and w.phase == "RUNNING"
    for _ in range(30):
        step()
    assert w.age == 1
    # then the campaign is won: the age advances with the recorded economic cause
    _finish_campaign(w, step, "won")
    assert w.age == 2 and w.history["age_winners"][-1]["winner"] == f  # the boundary resets the flag for the next age
    assert w.history["pandemic"][-1]["result"] == "won" and w.history["pandemic"][-1]["age"] == 1
    # the other order: the campaign first, then the economy
    while w.phase != "RUNNING":
        step()
    assert w.pandemic is not None and w.pandemic["epoch"] == 2 and w.pandemic["state"]["result"] is None
    _finish_campaign(w, step, "won")
    assert w.pandemic_won and w.age == 2 and w.economic_qualified is None
    f2 = w.fids[1]
    for v in w.faction_villages(f2):
        v["level"] = 2
    while w.vp(f2) < rules.vp_target():
        node = next(n for n in sorted(w.board.nodes) if w.node_free(n) and w.board.node_hexes[n])
        w._create_village(f2, node, level=2, status="operational")
    w.pending_completions.append({"kind": "city", "faction": f2, "village": w.faction_villages(f2)[0]["id"]})
    w._drain_completions()
    assert w.age == 3 and w.history["age_winners"][-1]["winner"] == f2


def test_p23_a_loss_pauses_the_run_and_the_retry_resumes_from_the_checkpoint_with_a_new_crisis_seed():
    w, step = _running(1)
    seed0 = int(w.pandemic["seed"])
    bases0 = dict(w.pandemic["bases"])
    _finish_campaign(w, step, "lost")
    assert w.paused and w.pandemic_lost is not None and w.pandemic_lost["reason"] == "player_deck_exhausted"
    ms = w.game_ms
    for _ in range(5):
        step()
    assert w.game_ms == ms  # paused: nothing moves
    assert w.history["pandemic"][-1]["result"] == "lost"
    r = w.retry_pandemic()
    assert r["status"] == "ok" and r["retries"] == 1
    assert not w.paused and w.pandemic_lost is None and w.pandemic["state"]["result"] is None
    assert int(w.pandemic["seed"]) != seed0 and w.pandemic["bases"] == bases0 and w.pandemic["retries"] == 1
    for _ in range(3):
        step()
    assert w.game_ms > ms
    assert w.retry_pandemic()["status"] == "rejected"


def test_p24_turns_run_on_the_shared_clock_every_twenty_seconds_and_saves_mid_campaign_replay_exactly():
    w, step = _running(2)
    camp = w.pandemic
    cadence = rules.timing("pandemic_turn")
    assert cadence == 20000
    t0 = int(camp["started_ms"])
    turns_before = int(camp["state"]["turn_count"])
    while w.game_ms < t0 + cadence * 3 + 500:
        step()
    assert int(w.pandemic["state"]["turn_count"]) == turns_before + 3
    assert all(int(t["game_ms"]) in (t0 + cadence, t0 + 2 * cadence, t0 + 3 * cadence) for t in w.pandemic["turns"][-3:])
    # responders were manufactured at the bases under contract, each a little after the last
    cs = w.history["pandemic_contracts"]
    assert [c["role"] for c in cs] == list(R.ROLES)
    assert all(cs[i]["ready_ms"] < cs[i + 1]["ready_ms"] for i in range(5))
    assert all(c["village"] for c in cs)
    # a save mid-campaign replays exactly
    saved = json.loads(json.dumps(w.to_dict()))
    w2 = GodWorld.from_dict(saved)
    seq = [5000]
    for _ in range(cadence // 1000 * 4):
        seq[0] += 1
        w.advance(1000, seq[0], snapshot=False)
        w2.advance(1000, seq[0], snapshot=False)
    assert w2.pandemic["state"] == w.pandemic["state"]
    assert w2.pandemic["turns"] == w.pandemic["turns"]


def test_the_economy_only_switch_keeps_the_strategic_regression_and_the_campaign_off():
    w, step = _running(3, pandemic=False)
    assert w.pandemic is None and w.gate_open()
    f = w.fids[0]
    for v in w.faction_villages(f):
        v["level"] = 2
    while w.vp(f) < rules.vp_target():
        node = next(n for n in sorted(w.board.nodes) if w.node_free(n) and w.board.node_hexes[n])
        w._create_village(f, node, level=2, status="operational")
    w.pending_completions.append({"kind": "city", "faction": f, "village": w.faction_villages(f)[0]["id"]})
    w._drain_completions()
    assert w.age == 2 and w.economic_qualified is None
    # the campaign never touched the strategic ledger: the conservation identity holds and no hand changed by the contracts
    w.check()
    assert "pandemic_contracts" not in w.history or not w.history["pandemic_contracts"]


def test_the_campaign_never_moves_the_strategic_game():
    """With the same seed, the strategic history is identical with the campaign on and off until the gate itself differs (P12/P18 of the earlier
    plans, extended): the responders and formations are presentation and rules of their own, never grants, trades or roads."""
    a, step_a = _running(4, pandemic=True)
    b, step_b = _running(4, pandemic=False)
    for _ in range(240):
        step_a()
        step_b()
    assert a.age == b.age == 1
    assert a.ledger.to_dict() == b.ledger.to_dict()
    assert sorted(a.roads) == sorted(b.roads) and {k: v["status"] for k, v in a.villages.items()} == {k: v["status"] for k, v in b.villages.items()}
    assert a.counters == b.counters
