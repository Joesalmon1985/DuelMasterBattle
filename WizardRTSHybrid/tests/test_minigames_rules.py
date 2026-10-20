"""The village minigames' engines (wizard_rts/minigames): every registered engine plays itself to the end under a seeded RNG without an illegal
move or a stuck state, is deterministic from its seed, and keeps its state JSON-clean; then the exact rule cases of each game."""
from __future__ import annotations

import json
import random

import pytest

from wizard_rts.minigames import base, catalogue


def play_out(game: str, seed: int, policy=None, cap: int = 2000) -> dict:
    """Self-play: the human seat takes `policy(state, actions, rng)` (default: a random legal action), the bots their own moves."""
    eng = catalogue.engine(game)
    st = eng.new(seed, {**(catalogue.entry(game) or {}).get("opts", {}), **catalogue.skin_for(catalogue.entry(game) or {}), "host": "them"})
    rng = random.Random(seed)
    for _ in range(cap):
        if st["over"]:
            break
        acts = eng.actions(st, 0)
        if acts:
            a = policy(st, acts, rng) if policy else rng.choice(acts)
            eng.act(st, 0, a)
            continue
        moved = False
        for seat in range(1, len(st["seats"])):
            if eng.actions(st, seat):
                eng.act(st, seat, eng.bot(st, seat, base.rng(st, f"bot:{seat}")))
                moved = True
                break
        assert moved, f"{game}: nobody can move and the game is not over (seed {seed})"
    assert st["over"], f"{game}: not over after {cap} moves (seed {seed})"
    return st


@pytest.mark.parametrize("game", sorted(catalogue.ENGINES))
def test_every_engine_plays_out_and_is_deterministic(game):
    a = play_out(game, 11)
    b = play_out(game, 11)
    assert a == b, f"{game}: two plays of seed 11 differ"
    assert a["result"] in base.RESULTS
    json.dumps(a)  # JSON-clean (saved with the world, sent to a client)
    for seed in (1, 2, 3):
        st = play_out(game, seed)
        v = catalogue.engine(game).view(st, 0)
        assert v["over"] and v["result"] == st["result"] and "areas" in v and "actions" in v
        json.dumps(v)


@pytest.mark.parametrize("game", sorted(catalogue.ENGINES))
def test_illegal_actions_are_refused(game):
    eng = catalogue.engine(game)
    st = eng.new(5, {**(catalogue.entry(game) or {}).get("opts", {}), "host": "them"})
    with pytest.raises(base.Illegal):
        eng.act(st, 0, {"id": "no_such_action"})
    acts = eng.actions(st, 0)
    if acts:  # a wrong seat never moves for the human
        with pytest.raises(base.Illegal):
            eng.act(st, len(st["seats"]) + 3, acts[0])


def test_catalogue_entries_are_complete():
    for g in catalogue.entries():
        for key in ("id", "game", "title", "host", "offer", "intro", "lines"):
            assert key in g, (g.get("id"), key)
        for k in ("win", "lose", "draw", "quit", "again"):
            assert g["lines"].get(k), (g["id"], k)
        assert catalogue._hosts(g), g["id"]
    assert len({g["id"] for g in catalogue.entries()}) == len(catalogue.entries())
    for gid in catalogue.ENGINES:
        assert catalogue.entry(gid) is not None, gid


# ------------------------------------------------------------------ rock paper scissors

def test_rps_ring_and_best_of_five():
    from wizard_rts.minigames import rps

    st = rps.new(3, {"signs": ["Flame", "Vine", "Frost"], "target": 3, "host": "the mentor"})
    assert st["names"] == ["Flame", "Vine", "Frost"]
    # the ring in the mentor's words: Flame (0) burns Vine (1), Vine (1) drinks Frost (2), Frost (2) kills Flame (0); a sign never beats itself
    assert rps.beats(0, 1) and rps.beats(1, 2) and rps.beats(2, 0)
    assert not rps.beats(1, 0) and not rps.beats(2, 1) and not rps.beats(0, 2)
    assert not any(rps.beats(i, i) for i in range(3))
    # every round is scored by the ring, and the game ends at the target
    for seed in range(1, 6):
        st = play_out("rps", seed)
        assert max(st["score"]) == 3 and st["result"] in ("win", "lose")
        assert len(st["rounds"]) == st["moves"]
        you = sum(1 for m, t in st["rounds"] if rps.beats(m, t))
        them = sum(1 for m, t in st["rounds"] if rps.beats(t, m))
        assert st["score"] == [you, them]
        assert st["result"] == ("win" if you == 3 else "lose")
