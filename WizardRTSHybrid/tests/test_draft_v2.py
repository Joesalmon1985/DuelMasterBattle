"""Plan v2 section 5: one seven-round draft phase per era, passing ring, default picks, leftover rule, splits, bonus hands."""
import pytest

from wizard_rts import draft, tech, vp
from wizard_rts.world import HybridWorld

SEED = 507


def world(draft_v2=True):
    w = HybridWorld(SEED, profile="campaign", legacy_draft=True)
    w.ai_enabled = False
    w.draft_v2 = draft_v2
    w._seq = 0
    return w


def run(w, seconds):
    for _ in range(int(seconds)):
        w._seq += 1
        w.advance(1000, w._seq, snapshot=False)


def total_cards(w):
    return sum(len(p) for p in draft.state(w)["packs"].values())


def test_phase_opens_with_a_pack_per_faction():
    w = world()
    run(w, 2)
    st = draft.state(w)
    assert st["era"] == 0 and st["round"] == 0
    assert len(st["ring"]) == 6
    for f in st["ring"]:
        assert 1 <= len(st["packs"][f]) <= draft.PACK_SIZE
        assert w.tech[f]["offers"] == sorted(w.tech[f]["offers"], key=lambda c: (tech.cards()[c]["era"], c))
        assert set(w.tech[f]["offers"]) <= set(st["packs"][f])


def test_pick_removes_card_and_passes_rest_on_the_six_minute_mark():
    w = world()
    run(w, 2)
    st = draft.state(w)
    f0, f1 = st["ring"][0], st["ring"][1]
    pack0 = list(st["packs"][f0])
    card = w.tech[f0]["offers"][0]
    assert tech.draft(w, f0, card)["status"] == "ok"
    assert card in w.tech[f0]["cards"] and card not in st["packs"][f0]
    assert w.tech[f0]["offers"] == []  # one pick per round
    assert tech.draft(w, f0, pack0[1])["status"] == "rejected"
    run(w, 6 * 60)
    assert st["round"] == 1
    # era 0 passes to the next seat: f1 now holds what f0 left, minus f0's pick, minus f1's own default pick from its own pack
    assert card not in st["packs"][f1]
    assert set(st["packs"][f1]) <= set(pack0) - {card}


def test_seven_rounds_exhaust_the_packs_and_every_faction_holds_seven(big_catalogue):
    w = world()
    run(w, 7 * 6 * 60 + 5)
    st = draft.state(w)
    assert st["round"] == draft.ROUNDS
    assert all(not p for p in st["packs"].values())
    for f in st["ring"]:
        assert len(w.tech[f]["cards"]) == draft.ROUNDS
    assert st["default_picks"] == 6 * 7 and st["duplicated_cards"] == 0


def test_pick_times_are_six_minutes_apart():
    w = world()
    run(w, 2)
    first = [e for e in w.events if e["kind"] == "draft_round"]
    run(w, 6 * 60)
    rounds = [e for e in w.events if e["kind"] == "draft_round"]
    assert len(first) == 1 and len(rounds) == 2


def leftover_world(vps):
    w = world()
    run(w, 2)
    st = draft.state(w)
    for f, v in vps.items():
        pass
    return w, st


def test_leftover_rule_gives_pack_to_factions_with_8_vp_and_removes_it_from_others(monkeypatch):
    w = world()
    run(w, 2)
    st = draft.state(w)
    ring = st["ring"]
    hi, lo = ring[0], ring[1]
    monkeypatch.setattr(vp, "totals", lambda world: {f: (8 if f == hi else 7) for f in world.faction_info})
    hi_pack, lo_pack = list(st["packs"][hi]), list(st["packs"][lo])
    before_hi, before_lo = list(w.tech[hi]["cards"]), list(w.tech[lo]["cards"])
    draft.end_era(w)
    assert set(w.tech[hi]["cards"]) == set(before_hi) | set(hi_pack)
    assert w.tech[lo]["cards"] == before_lo
    ev = [e for e in w.events if e["kind"] == "draft_leftovers"][-1]
    assert ev["awarded"][hi] == sorted(hi_pack) or set(ev["awarded"][hi]) == set(hi_pack)
    assert lo in ev["lost"] and set(ev["lost"][lo]) == set(lo_pack)
    assert all(not p for p in st["packs"].values())


def test_early_vp_era_end_keeps_drafted_cards_and_starts_a_new_phase(monkeypatch):
    w = world()
    run(w, 2)
    f = draft.state(w)["ring"][0]
    tech.draft(w, f, w.tech[f]["offers"][0])
    kept = list(w.tech[f]["cards"])
    assert vp.advance_era(w, "test")
    run(w, 2)
    st = draft.state(w)
    assert st["era"] == 1 and st["round"] == 0 and st["phases"] == 2
    assert set(kept) <= set(w.tech[f]["cards"])


def test_era_end_is_debounced_and_uses_current_vp(monkeypatch):
    w = world()
    run(w, 2)
    f = draft.state(w)["ring"][0]
    monkeypatch.setattr(vp, "totals", lambda world: {n: (10 if n == f else 1) for n in world.faction_info})
    run(w, 30)
    assert w.era_index == 0  # not yet held for 60 s
    run(w, 40)
    assert w.era_index == 1
    assert w.era["log"][-1]["reason"] == "vp_threshold"


def test_split_inherits_pack_only_if_parent_has_not_picked():
    w = world()
    run(w, 2)
    st = draft.state(w)
    parent = st["ring"][2]
    pack = list(st["packs"][parent])
    w.tech["Child-A"] = {**tech.new_state(), "cards": list(w.tech[parent]["cards"])}
    draft.on_split(w, parent, "Child-A")
    assert st["ring"][3] == "Child-A"
    assert st["packs"]["Child-A"] == pack and st["packs"][parent] == []
    # a parent that already picked: the child waits, then is dealt from the reserve next round
    p2 = st["ring"][0]
    tech.draft(w, p2, w.tech[p2]["offers"][0])
    w.tech["Child-B"] = {**tech.new_state(), "cards": []}
    draft.on_split(w, p2, "Child-B")
    assert st["packs"]["Child-B"] == []
    run(w, 6 * 60)
    assert len(st["packs"]["Child-B"]) > 0 or not st["reserve"]


def test_collapse_discards_the_held_pack():
    w = world()
    run(w, 2)
    st = draft.state(w)
    f = st["ring"][4]
    draft.on_collapse(w, f)
    assert f not in st["ring"] and f not in st["packs"]
    run(w, 6 * 60)
    assert st["round"] == 1  # the ring carries on with five seats


@pytest.fixture
def big_catalogue(monkeypatch):
    """120 cards in each era, so packs are dealt without copies and a reserve deck exists (the real catalogue comes with the content graph)."""
    cards = {}
    for era in range(4):
        for i in range(120):
            cid = f"t.e{era}.{i:03}"
            cards[cid] = {"id": cid, "name": cid, "era": era, "summary": "", "kinds": [], "units": [], "wl_patterns": [], "requires_cards": [], "requires_working": []}
    monkeypatch.setattr(tech, "cards", lambda: cards)
    return cards


def test_bonus_hand_comes_from_the_reserve_and_never_touches_packs(big_catalogue):
    w = world()
    f_bonus = "Red"
    w.bonus_hook = lambda world, f: f == f_bonus
    run(w, 2)
    st = draft.state(w)
    assert f_bonus in st["bonus"] and len(st["bonus"][f_bonus]) == draft.BONUS_HAND
    packs_before = {f: list(p) for f, p in st["packs"].items()}
    hand = list(st["bonus"][f_bonus])
    assert set(hand).isdisjoint(set().union(*[set(p) for p in packs_before.values()]))
    offers = w.tech[f_bonus]["offers"]
    assert set(hand) <= set(offers)
    pick = hand[0]
    assert tech.draft(w, f_bonus, pick)["status"] == "ok"
    assert {f: list(p) for f, p in st["packs"].items()} == packs_before  # no pack lost a card
    assert f_bonus not in st["bonus"]
    assert set(w.tech[f_bonus]["offers"]) == set(st["packs"][f_bonus])  # the normal pick is still open


@pytest.mark.parametrize("era", [0, 1, 2, 3])
def test_dealing_invariants_across_seeds(era, big_catalogue):
    for seed in range(20):
        w = HybridWorld(seed, profile="campaign", legacy_draft=True)
        w.ai_enabled = False
        w.draft_v2 = True
        draft.deal(w, era)
        st = draft.state(w)
        for f, pack in st["packs"].items():
            assert len(pack) == len(set(pack)) <= draft.PACK_SIZE
            assert len(pack) == draft.PACK_SIZE, "a dead or short pack"
            assert sum(tech.cards()[c]["era"] == era for c in pack) >= 5
        assert len({c for p in st["packs"].values() for c in p}) == 6 * draft.PACK_SIZE  # no card is dealt twice in a phase


class StubClock(dict):
    pass


class Stub:
    """Just enough world for the draft engine, so thousands of phases can be played in seconds."""

    def __init__(self, seed, n, era, rng):
        self.seed = seed
        self.profile = "campaign"
        self.faction_info = {f"F{i}": {} for i in range(n)}
        self.tech = {f: tech.new_state() for f in self.faction_info}
        self.dmb = type("D", (), {"clock": StubClock(game_ms=0)})()
        self.events = []
        self.era_index = era
        self.cardset = "v2"
        self.draft_v2 = True
        self.history = {"faction": {}}
        self.buildings, self.stocks, self.stats = {}, {}, {}  # the paper rule looks for a scriptorium and paper


@pytest.mark.parametrize("batch", range(4))
def test_thousand_phases_conserve_cards_and_never_stall(batch):
    import random

    rng = random.Random(batch)
    for k in range(250):
        n = rng.randint(3, 8)
        era = rng.randint(0, 3)
        w = Stub(batch * 1000 + k, n, era, rng)
        pool = tech.pool(w)
        # some cards are already held from earlier eras
        for f in w.faction_info:
            w.tech[f]["cards"] = rng.sample(sorted(c for c, v in pool.items() if v["era"] < era), min(3, sum(v["era"] < era for v in pool.values())))
        draft.deal(w, era)
        st = draft.state(w)
        dealt = [c for p in st["packs"].values() for c in p]
        assert len(dealt) == len(set(dealt))  # no copies while the pool is big enough
        picked = []
        for r in range(draft.ROUNDS):
            assert all(st["packs"][f] for f in st["ring"]), "dead pack"
            for f in st["ring"]:
                if rng.random() < 0.7 and w.tech[f]["offers"]:
                    c = rng.choice(w.tech[f]["offers"])
                    assert tech.draft(w, f, c)["status"] == "ok"
                    picked.append(c)
            w.dmb.clock["game_ms"] += draft.ROUND_MS
            draft.quantum(w)
        assert st["round"] == draft.ROUNDS
        assert all(not p for p in st["packs"].values())
        held_new = [c for f in w.faction_info for c in w.tech[f]["cards"] if c in set(dealt)]
        assert sorted(held_new) == sorted(set(held_new)) and set(held_new) <= set(dealt)
        for f in st["ring"]:
            assert len([c for c in w.tech[f]["cards"] if c in set(dealt)]) == draft.ROUNDS
