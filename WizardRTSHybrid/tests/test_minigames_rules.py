"""The village minigames' engines (wizard_rts/minigames): every registered engine plays itself to the end under a seeded RNG without an illegal
move or a stuck state, is deterministic from its seed, and keeps its state JSON-clean; then the exact rule cases of each game."""
from __future__ import annotations

import json
import random

import pytest

from wizard_rts.minigames import base, catalogue


CAPS = {"rummikub": 8000}  # a random human at the tally board ends turns rarely: the game is long but it ends


def play_out(game: str, seed: int, policy=None, cap: int = 2000) -> dict:
    """Self-play: the human seat takes `policy(state, actions, rng)` (default: a random legal action), the bots their own moves."""
    cap = max(cap, CAPS.get(game, 0))
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


# ------------------------------------------------------------------ M1: the quick games

def test_nim_misere_strategy_never_loses_from_a_winning_position():
    from wizard_rts.minigames import nim

    assert not nim._losing((1, 1, 0), 3)  # whatever the mover takes, the other takes the last carrot and loses
    assert nim._losing((1, 0, 0), 3)  # forced to take the last carrot
    # the mother, moving second, wins every game against a player who always takes one from the first non-empty row
    for seed in range(6):
        st = play_out("nim", seed, policy=lambda s, acts, r: next(a for a in acts if a["n"] == 1))
        assert st["result"] == "lose", seed

    def best(s, acts, r):
        for a in acts:
            nxt = list(s["rows"])
            nxt[a["row"]] -= a["n"]
            if nim._losing(tuple(nxt), s["take_max"]):
                return a
        return acts[0]

    st = play_out("nim", 1, policy=best)
    assert st["result"] == ("win" if not nim._losing((3, 5, 7), 3) else "lose")


def test_pairs_matching_and_the_turn_rules():
    from wizard_rts.minigames import pairs

    st = pairs.new(4, {"pairs": 8, "host": "mother"})
    assert len(st["tiles"]) == 16 and all(st["tiles"].count(t) == 2 for t in st["tiles"])
    twin = next(j for j in range(1, 16) if st["tiles"][j] == st["tiles"][0])
    other = next(j for j in range(1, 16) if st["tiles"][j] != st["tiles"][0])
    pairs.act(st, 0, {"id": "flip:0"})
    assert st["pending"] == 0 and st["turn"] == 0
    pairs.act(st, 0, {"id": "flip:%d" % twin})
    assert st["score"] == [1, 0] and st["turn"] == 0 and st["taken"][0] == 0 and st["taken"][twin] == 0  # a pair keeps the turn
    pairs.act(st, 0, {"id": "flip:%d" % other})
    other2 = next(j for j in range(16) if st["taken"][j] < 0 and j != other and st["tiles"][j] != st["tiles"][other])
    pairs.act(st, 0, {"id": "flip:%d" % other2})
    assert st["turn"] == 1 and st["score"] == [1, 0] and st["taken"][other] < 0  # a miss gives the turn away
    with pytest.raises(base.Illegal):
        pairs.act(st, 1, {"id": "flip:0"})  # a taken swatch cannot be turned again
    st = play_out("pairs", 2)
    assert sum(st["score"]) == 8 and all(t >= 0 for t in st["taken"])


def test_memory_always_one_new_object_and_a_repeat_ends_it():
    from wizard_rts.minigames import memory

    st = memory.new(9, {"start": 3, "max": 8, "host": "forester"})
    assert len(st["shown"]) == 3
    memory.act(st, 0, {"id": "next"})
    for n in range(4, 9):
        assert len(st["shown"]) == n and len(set(st["shown"])) == n
        newest = st["order"][n - 1]
        assert newest in st["shown"] and set(st["shown"]) - {newest} == set(st["order"][: n - 1])
        memory.act(st, 0, {"id": "pick:%d" % newest, "pick": newest})
        if st["over"]:
            break
    assert st["over"] and st["result"] == "win" and st["passed"] == 5
    st = memory.new(9, {"start": 3, "max": 8, "host": "forester"})
    memory.act(st, 0, {"id": "next"})
    old = st["order"][0]
    memory.act(st, 0, {"id": "pick:%d" % old, "pick": old})
    assert st["over"] and st["result"] == "lose" and st["passed"] == 0


def test_reaction_scores_from_the_answer_and_the_time():
    from wizard_rts.minigames import reaction

    st = reaction.new(3, {"rounds": 4, "host": "hunter"})
    reaction.act(st, 0, {"id": "next"})
    for _ in range(4):
        same = st["current"] == st["previous"]
        reaction.act(st, 0, {"id": "same" if same else "different", "ms": 400})
        if st["over"]:
            break
    assert st["over"] and st["score"] == 8 and st["result"] == "win"
    st = reaction.new(3, {"rounds": 4, "host": "hunter"})
    reaction.act(st, 0, {"id": "next"})
    same = st["current"] == st["previous"]
    reaction.act(st, 0, {"id": "same" if same else "different", "ms": 4000})
    assert st["score"] == 1  # right but slow
    same = st["current"] == st["previous"]
    reaction.act(st, 0, {"id": "different" if same else "same", "ms": 100})
    assert st["score"] == 1  # wrong: nothing


def test_roulette_bets_and_payouts():
    from wizard_rts.minigames import roulette

    assert roulette.colour_of(0) == "green" and roulette.colour_of(1) == "red" and roulette.colour_of(2) == "black"
    assert roulette.wins("red", 1) and not roulette.wins("red", 2) and not roulette.wins("red", 0)
    assert roulette.wins("odd", 3) and roulette.wins("even", 4) and not roulette.wins("even", 0)
    assert roulette.wins("low", 18) and roulette.wins("high", 19) and roulette.wins("dozen2", 13) and roulette.wins("dozen3", 36)
    assert roulette.wins("num:17", 17) and not roulette.wins("num:17", 18)
    assert roulette.payout("red") == 1 and roulette.payout("dozen1") == 2 and roulette.payout("num:0") == 35
    st = roulette.new(5, {"stake": 20, "spins": 3, "host": "carrier"})
    roulette.act(st, 0, {"id": "bet:red", "bet": "red"})
    assert st["pebbles"] == (21 if roulette.wins("red", st["last"]) else 19)
    st = play_out("roulette", 4)
    assert st["spun"] <= st["spins"] and st["pebbles"] >= 0


def test_blackjack_totals_dealer_rule_and_payouts():
    from wizard_rts.minigames import blackjack

    assert blackjack.total(["As", "Kd"]) == (21, True)
    assert blackjack.total(["As", "9d", "5c"]) == (15, False)
    assert blackjack.total(["Th", "Jd", "2c"]) == (22, False)
    assert blackjack.total(["As", "Ad", "9c"]) == (21, True)
    st = blackjack.new(2, {"stake": 10, "hands": 3, "host": "sawyer"})
    blackjack.act(st, 0, {"id": "deal"})
    assert st["pebbles"] == 8 and len(st["player"][0]) == 2 and len(st["dealer"]) == 2
    # rigged settlements: the dealer stands on a soft seventeen and draws on sixteen
    st["phase"] = "play"
    st["player"] = [["Ts", "9d"]]
    st["bets"] = [2]
    st["dealer"] = ["As", "6d"]
    st["deck"] = ["2c"] * 20
    st["pebbles"] = 8
    blackjack._settle(st)
    assert blackjack.total(st["dealer"])[0] == 17 and st["pebbles"] == 12  # 19 beats 17: the bet back and as much again
    st["phase"] = "play"
    st["player"] = [["Ts", "9d"]]
    st["bets"] = [2]
    st["dealer"] = ["7s", "9d"]
    st["deck"] = ["5c"] * 20
    st["pebbles"] = 8
    blackjack._settle(st)
    assert blackjack.total(st["dealer"])[0] == 21 and st["pebbles"] == 8  # 21 beats 19: nothing back
    st = play_out("blackjack", 7)
    assert st["hand_no"] <= st["hands"]


def test_yahtzee_categories_and_the_upper_bonus():
    from wizard_rts.minigames import yahtzee as y

    assert y.score_of("ones", [1, 1, 2, 3, 1]) == 3 and y.score_of("sixes", [6, 6, 6, 6, 6]) == 30
    assert y.score_of("three_kind", [2, 2, 2, 5, 6]) == 17 and y.score_of("three_kind", [2, 2, 3, 5, 6]) == 0
    assert y.score_of("four_kind", [4, 4, 4, 4, 1]) == 17 and y.score_of("full_house", [3, 3, 5, 5, 5]) == 25 and y.score_of("full_house", [3, 3, 3, 3, 5]) == 0
    assert y.score_of("small_straight", [1, 2, 3, 4, 6]) == 30 and y.score_of("small_straight", [2, 3, 4, 5, 5]) == 30 and y.score_of("small_straight", [1, 2, 3, 5, 6]) == 0
    assert y.score_of("large_straight", [2, 3, 4, 5, 6]) == 40 and y.score_of("large_straight", [1, 2, 3, 4, 6]) == 0
    assert y.score_of("yahtzee", [5, 5, 5, 5, 5]) == 50 and y.score_of("yahtzee", [5, 5, 5, 5, 4]) == 0
    assert y.score_of("chance", [1, 2, 3, 4, 5]) == 15
    assert y.totals({"ones": 3, "twos": 6, "threes": 9, "fours": 12, "fives": 15, "sixes": 18})["bonus"] == 35
    assert y.totals({"ones": 3, "twos": 6, "threes": 9, "fours": 12, "fives": 15, "sixes": 17})["bonus"] == 0
    st = play_out("yahtzee", 3)
    assert all(len(s) == 13 for s in st["sheets"])
    st = y.new(1, {"host": "mason"})
    assert [a["id"] for a in y.actions(st, 0)] == ["roll"]
    y.act(st, 0, {"id": "roll"})
    assert st["rolls"] == 1 and all(1 <= d <= 6 for d in st["dice"])
    y.act(st, 0, {"id": "hold:0", "die": 0})
    kept = st["dice"][0]
    y.act(st, 0, {"id": "roll"})
    assert st["dice"][0] == kept and st["rolls"] == 2


# ------------------------------------------------------------------ M2: push-your-luck and tiles

def test_cantstop_three_runners_and_the_bust():
    from wizard_rts.minigames import cantstop as cs

    st = cs.new(1, {"host": "lumberjack"})
    st["dice"] = [1, 2, 3, 4]
    st["phase"] = "choose"
    opts = cs._options(st, 0)
    sums = sorted(tuple(o["cols"]) for o in opts)
    assert (3, 7) in sums and (4, 6) in sums and (5, 5) in sums  # 1+2/3+4, 1+3/2+4, 1+4/2+3
    # three runners placed: a pairing that fits none of them is no option, and a throw with none busts
    st["runners"] = {"2": 1, "3": 1, "12": 1}
    st["dice"] = [4, 4, 4, 4]  # 8 and 8 only
    assert cs._options(st, 0) == []
    # a bust clears the runners and gives the turn away (forced through act by rigging the throw)
    st2 = cs.new(2, {"host": "lumberjack"})
    st2["runners"] = {"2": 1, "3": 1, "12": 1}
    st2["phase"] = "roll"
    orig = base.rng
    try:
        base.rng = lambda s, p="": _Fixed([4, 4, 4, 4])
        cs.act(st2, 0, {"id": "roll"})
    finally:
        base.rng = orig
    assert st2["runners"] == {} and st2["turn"] == 1 and st2["phase"] == "roll"
    # banking writes the runners and claims a topped column
    st3 = cs.new(3, {"host": "lumberjack"})
    st3["runners"] = {"2": 3, "7": 4}
    st3["phase"] = "decide"
    cs.act(st3, 0, {"id": "stop"})
    assert st3["positions"][0]["2"] == 3 and st3["claimed"]["2"] == 0 and st3["positions"][0]["7"] == 4 and st3["turn"] == 1
    st = play_out("cantstop", 5)
    assert sum(1 for s in st["claimed"].values() if s == (0 if st["result"] == "win" else 1)) >= 3


class _Fixed:
    def __init__(self, values):
        self.values = list(values)

    def randint(self, a, b):
        return self.values.pop(0)

    def random(self):
        return 0.0

    def choice(self, seq):
        return seq[0]


def test_rummikub_melds_opening_and_the_end():
    from wizard_rts.minigames import rummikub as rk

    run = [rk.tile_id(0, 3, 0), rk.tile_id(0, 4, 0), rk.tile_id(0, 5, 1)]
    assert rk.is_meld(run) and rk.points(run) == 12
    assert not rk.is_meld([rk.tile_id(0, 3, 0), rk.tile_id(0, 5, 0), rk.tile_id(0, 6, 0)])  # a gap
    assert not rk.is_meld([rk.tile_id(0, 3, 0), rk.tile_id(0, 3, 1), rk.tile_id(0, 4, 0)])  # a doubled number
    group = [rk.tile_id(0, 9, 0), rk.tile_id(1, 9, 0), rk.tile_id(2, 9, 0)]
    assert rk.is_meld(group) and rk.is_meld(group + [rk.tile_id(3, 9, 1)])
    assert not rk.is_meld(group + [rk.tile_id(0, 9, 1)])  # two of a colour in a set
    assert not rk.is_meld(group[:2])
    st = rk.new(4, {"host": "keeper"})
    assert len(st["racks"][0]) == 14 and len(st["racks"][1]) == 14 and len(st["pool"]) == 104 - 28
    # a short opening comes back: lay 12 points, end the turn, the tallies are on the rack again and one more was drawn
    st["racks"][0] = run + [rk.tile_id(2, 1, 0)]
    for t in run:
        rk.act(st, 0, {"id": f"select:{t}", "tile": t})
    assert [a["id"] for a in rk.actions(st, 0) if a["id"] == "lay"]
    rk.act(st, 0, {"id": "lay"})
    assert st["board"] == [sorted(run, key=rk.parse)] and st["laid_points"] == 12
    rk.act(st, 0, {"id": "end"})
    assert st["board"] == [] and set(run) <= set(st["racks"][0]) and len(st["racks"][0]) == 5 and not st["opened"][0] and st["turn"] == 1
    # the full game ends with an empty rack or a dry pool
    for seed in (1, 2):
        st = play_out("rummikub", seed, policy=_rummikub_policy)
        assert st["over"] and (not st["racks"][0] or not st["racks"][1] or st["passes"] >= 2)


def _rummikub_policy(state, acts, rng):
    """A human who plays like the keeper: pick a meld worth laying, select it tile by tile, lay it; else end the turn."""
    from wizard_rts.minigames import rummikub as rk

    ids = {a["id"] for a in acts}
    opened = state["opened"][0] or state["laid_points"] >= rk.OPENING
    melds = sorted(rk._melds_in(state["racks"][0]), key=lambda m: (-len(m), -rk.points(m)))
    total = sum(rk.points(m) for m in melds)
    want = next((m for m in melds if opened or total >= rk.OPENING), None)
    if want is None:
        if state["selected"]:
            t = state["selected"][0]
            return {"id": f"select:{t}", "tile": t}
        return {"id": "end"}
    stray = [t for t in state["selected"] if t not in want]
    if stray:
        return {"id": f"select:{stray[0]}", "tile": stray[0]}
    missing = [t for t in want if t not in state["selected"]]
    if missing:
        return {"id": f"select:{missing[0]}", "tile": missing[0]}
    assert "lay" in ids
    return {"id": "lay"}


def test_slide_every_board_is_solvable_and_exits_need_the_right_gate():
    from wizard_rts.minigames import slide

    for seed in range(1, 13):
        st = slide.new(seed, {"size": 6, "blocks": 6, "host": "mason"})
        assert st["total"] >= 3 and st["par"] >= st["total"] and len(st["solution"]) == st["par"]
        # an exit through the wrong colour's gate is never legal
        for b in st["blocks"]:
            for d in slide.DIRS:
                if slide.legal_move(st, b, d) == "exit":
                    outside = [(x + slide.DIRS[d][0], y + slide.DIRS[d][1]) for x, y in slide._cells(b)]
                    outside = [c for c in outside if not slide._inside(st, c)]
                    assert outside and all(c in slide._exit_cells(st, int(b["colour"])) for c in outside)
        # the recorded solution (the construction undone) clears the board in exactly par moves
        for block, d in st["solution"]:
            assert not st["over"]
            slide.act(st, 0, {"id": "move", "block": block, "dir": d})
        assert st["over"] and st["result"] == "win" and st["moves"] == st["par"], seed
    st = play_out("slide", 3)
    assert st["result"] in ("win", "lose")


# ------------------------------------------------------------------ M3: trick-taking and betting

def test_poker_ranking_every_category_kickers_and_ties():
    from wizard_rts.minigames import cards as C

    hands = {
        "straight flush": ["9s", "8s", "7s", "6s", "5s"], "four of a kind": ["Ks", "Kh", "Kd", "Kc", "2s"], "full house": ["3s", "3h", "3d", "9c", "9s"],
        "flush": ["As", "Ts", "7s", "4s", "2s"], "straight": ["As", "2h", "3d", "4c", "5s"], "three of a kind": ["7s", "7h", "7d", "Kc", "2s"],
        "two pair": ["Js", "Jh", "4d", "4c", "As"], "pair": ["Qs", "Qh", "9d", "5c", "2s"], "high card": ["As", "Jh", "9d", "5c", "2s"],
    }
    order = ["straight flush", "four of a kind", "full house", "flush", "straight", "three of a kind", "two pair", "pair", "high card"]
    ranks = [C.rank5(hands[k]) for k in order]
    assert ranks == sorted(ranks, reverse=True) and len(set(r[0] for r in ranks)) == 9
    assert C.rank5(["As", "2h", "3d", "4c", "5s"])[1] == 5  # the wheel is a five-high straight
    assert C.rank5(["Ts", "Jh", "Qd", "Kc", "As"]) > C.rank5(["9s", "Th", "Jd", "Qc", "Ks"])
    assert C.rank5(["Qs", "Qh", "9d", "5c", "2s"]) > C.rank5(["Qd", "Qc", "8d", "5h", "2h"])  # the kicker decides
    assert C.rank5(["Qs", "Qh", "9d", "5c", "2s"]) == C.rank5(["Qd", "Qc", "9h", "5h", "2h"])  # a tie
    assert C.rank5(["Ks", "Kh", "Kd", "2c", "2s"]) > C.rank5(["Qs", "Qh", "Qd", "Ac", "As"])  # the trips rank the full house
    assert C.best_of(["As", "Ks", "Qs", "Js", "Ts", "2d", "3c"])[0] == 8  # the royal among seven
    assert C.category_name(C.rank5(hands["two pair"])) == "two pair"


def test_tricks_follow_suit_and_the_winner():
    from wizard_rts.minigames import tricks

    hand = ["2s", "9s", "Kh", "3d"]
    assert tricks.legal(hand, [[1, "7s"]], "d") == ["2s", "9s"]
    assert tricks.legal(hand, [[1, "7c"]], "d") == hand
    assert tricks.winner([[0, "7s"], [1, "9s"], [2, "Ah"]], "d") == 1  # highest of the led suit
    assert tricks.winner([[0, "7s"], [1, "9s"], [2, "2d"]], "d") == 2  # a trump
    assert tricks.winner([[0, "7s"], [1, "3d"], [2, "2d"]], "d") == 1  # the higher trump
    assert tricks.bot_trumps(["2s", "3s", "4s", "Ah", "Kd"]) == "s"


def test_whist_knock_out_and_the_dogs_life():
    from wizard_rts.minigames import whist

    st = whist.new(5, {"players": 3, "start": 7, "host": "contestant", "partners": ["another contestant"]})
    assert st["size"] == 7 and all(len(h) == 7 for h in st["hands"]) and st["phase"] == "play" and st["trump"] in "shdc"
    # a hand where seat 2 takes nothing: the first time a dog's life, the second time out
    st["taken"] = [4, 3, 0]
    st["hands"] = [[], [], []]
    whist._hand_over(st)
    assert st["dog"][2] and st["dog_used"][2] and st["alive"][2] and st["size"] == 6 and st["chooser"] == 0 and st["phase"] == "choose"
    assert len(st["hands"][2]) == 1 and len(st["hands"][0]) == 6
    whist.act(st, 0, {"id": "trumps:h", "suit": "h"})
    assert st["trump"] == "h" and st["phase"] == "play"
    st["taken"] = [3, 3, 0]
    st["hands"] = [[], [], []]
    whist._hand_over(st)
    assert not st["alive"][2] and st["size"] == 5
    # the apprentice knocked out ends it
    st["taken"] = [0, 5, 0]
    st["hands"] = [[], [], []]
    st["dog_used"][0] = True
    whist._hand_over(st)
    assert st["over"] and st["result"] == "lose"
    for seed in (1, 2, 3):
        st = play_out("whist", seed)
        assert st["result"] in ("win", "lose")


def test_ohhell_hook_and_exact_scoring():
    from wizard_rts.minigames import ohhell

    st = ohhell.new(2, {"players": 3, "hands": [3, 2, 1], "host": "rollkeeper", "partners": ["a contestant"]})
    assert st["hand_no"] == 1 and all(len(h) == 3 for h in st["hands"]) and st["phase"] == "bid"
    d = st["dealer"]
    first = st["current"]
    assert first == (d + 1) % 3
    # the dealer may not make the bids come out even
    st["bids"] = [None, None, None]
    st["bids"][(d + 1) % 3] = 1
    st["bids"][(d + 2) % 3] = 1
    st["current"] = d
    legal = [a["bid"] for a in ohhell.actions(st, d)]
    assert 1 not in legal and set(legal) == {0, 2, 3}
    # the score: exact bids score ten plus the bid, anything else nothing
    st2 = ohhell.new(2, {"players": 3, "hands": [1], "host": "rollkeeper", "partners": ["a contestant"]})
    st2["bids"] = [1, 0, 0]
    st2["phase"] = "play"
    st2["hands"] = [["As"], ["2s"], ["3s"]]
    st2["trump"] = "h"
    st2["leader"] = st2["current"] = 0
    for seat, c in ((0, "As"), (1, "2s"), (2, "3s")):
        ohhell.act(st2, seat, {"id": f"play:{c}", "card": c})
    assert st2["over"] and st2["score"] == [11, 10, 10] and st2["result"] == "win"
    st = play_out("ohhell", 4)
    assert st["hand_no"] == 7 and st["result"] in ("win", "lose", "draw")


def test_betting_round_check_bet_call_raise_fold():
    from wizard_rts.minigames import betting

    st = {"stacks": [20, 20], "pot": 0, "chips": "pebbles"}
    betting.start(st, 0, 2, max_raises=2)
    assert [o["id"] for o in betting.options(st, 0)] == ["check", "bet"] and betting.options(st, 1) == []
    betting.apply(st, 0, "bet")
    assert st["pot"] == 2 and st["stacks"][0] == 18 and st["bet"]["to_call"][1] == 2 and st["bet"]["current"] == 1
    assert [o["id"] for o in betting.options(st, 1)] == ["call", "raise", "fold"]
    betting.apply(st, 1, "raise")
    assert st["pot"] == 6 and st["stacks"][1] == 16 and st["bet"]["to_call"][0] == 2 and st["bet"]["raises"] == 1
    betting.apply(st, 0, "call")
    assert st["bet"]["done"] and st["pot"] == 8 and st["bet"]["folded"] is None
    betting.settle(st, 1)
    assert st["stacks"] == [16, 24] and st["pot"] == 0
    betting.start(st, 1, 2)
    betting.apply(st, 1, "check")
    betting.apply(st, 0, "check")
    assert st["bet"]["done"]
    betting.start(st, 0, 2)
    betting.apply(st, 0, "bet")
    betting.apply(st, 1, "fold")
    assert st["bet"]["done"] and st["bet"]["folded"] == 1
    # an all-in short of the bet: the extra comes back
    st = {"stacks": [10, 1], "pot": 0, "chips": "pebbles"}
    betting.start(st, 0, 4)
    betting.apply(st, 0, "bet")
    betting.apply(st, 1, "call")
    assert st["bet"]["done"] and st["pot"] == 2 and st["stacks"] == [9, 0]


def test_draw_poker_and_holdem_play_out_and_settle_every_pebble():
    from wizard_rts.minigames import draw_poker, holdem

    for game, mod in (("draw_poker", draw_poker), ("holdem", holdem)):
        for seed in (1, 2, 3, 4):
            st = play_out(game, seed)
            assert st["pot"] == 0 and sum(st["stacks"]) == 2 * st["stake"], (game, seed, st["stacks"], st["pot"])
            assert st["hand_no"] <= st["hands"]
    st = draw_poker.new(3, {"stake": 20, "hands": 2, "host": "hunter"})
    draw_poker.act(st, 0, {"id": "deal"})
    assert st["pot"] == 2 and st["phase"] == "bet1" and len(st["cards"][0]) == 5
    st = holdem.new(3, {"stake": 30, "hands": 2, "host": "carrier"})
    holdem.act(st, 0, {"id": "deal"})
    assert st["pot"] == 3 and st["phase"] == "bet" and len(st["hole"][0]) == 2 and st["board"] == []
