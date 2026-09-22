"""T091 retained DmbBattleSim progression: feedback, rival, overflow, era binding."""

from __future__ import annotations

from sim.dmb.adventure.duels import (
    encounter_for_tier,
    load_duel_progression,
    resolve_progression_request,
    rival_legal_candidates,
    score_feedback,
)
from sim.dmb.adventure.mastermind import score_guess as mastermind_score


def test_aabc_vs_abad_feedback() -> None:
    # A=0 B=1 C=2 D=3 — C10 oracle: 1 exact, 2 colour-only.
    secret = [0, 0, 1, 2]  # AABC
    guess = [0, 1, 0, 3]  # ABAD
    exact, colour_only = score_feedback(secret, guess)
    assert (exact, colour_only) == (1, 2)
    assert mastermind_score(secret, guess) == (1, 2)


def test_rival_has_no_secret_read_shortcut() -> None:
    secret = [0, 1, 2, 3]
    history = [{"guess": [0, 0, 0, 0], "exact": 1, "colour_only": 0}]
    # Pass the real secret; filter must ignore it and only use feedback.
    candidates = rival_legal_candidates(
        slot_count=4,
        colour_count=4,
        allow_repeats=True,
        history=history,
        opponent_secret=secret,
    )
    assert secret in candidates
    # A candidate that would only win via secret-read (wrong exact count) is excluded.
    assert [1, 1, 1, 1] not in candidates
    # Every survivor must reproduce the observed feedback against itself as secret.
    for cand in candidates:
        assert score_feedback(cand, [0, 0, 0, 0]) == (1, 0)


def test_cap_overflow_uses_authored_reward() -> None:
    rules = load_duel_progression()
    out = resolve_progression_request(slot_count=9, colour_count=12, progression=rules)
    assert out["overflow"] is True
    assert out["slot_count"] == 6
    assert out["colour_count"] == 8
    assert out["reward"]["id"] == "reward.duel_overflow_chronicle"
    ok = resolve_progression_request(slot_count=4, colour_count=6, progression=rules)
    assert ok["overflow"] is False


def test_era_selects_authored_tier_only() -> None:
    pre = encounter_for_tier(era="prehistoric")
    fut = encounter_for_tier(era="futuristic")
    # Prehistoric stays baseline 4/6; futuristic uses authored tier_2 6/8.
    assert pre["slot_count"] == 4
    assert pre["colour_count"] == 6
    assert pre["progression_id"] == "duel.tier_0"
    assert fut["slot_count"] == 6
    assert fut["colour_count"] == 8
    assert fut["progression_id"] == "duel.tier_2"
    # Same era twice is stable — no silent drift.
    again = encounter_for_tier(era="prehistoric")
    assert again["slot_count"] == pre["slot_count"]
    assert again["colour_count"] == pre["colour_count"]
    assert again["engine"] if False else again.get("progression_id") == pre["progression_id"]
    # Engine remains DmbBattleSim config shape (not Mastermind production).
    assert "player_combatant" in pre
    assert pre["enemy_combatant"]["bot_logic"] == "candidate_filter"
