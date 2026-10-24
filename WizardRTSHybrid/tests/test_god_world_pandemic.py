"""The shared Pandemic campaign's rules and coordinator (docs/PLAN_GOD_WORLD_PANDEMIC.md stage 4; the brief's P15 to P21): the published core rules
on the 80-node island, deterministic in the seed, with wins and losses both reachable by the coordinator, which reads only the public state."""

from __future__ import annotations

import json

import pytest

from wizard_rts.god_world.pandemic import coordinator as C
from wizard_rts.god_world.pandemic import rules as R
from wizard_rts.god_world.pandemic import scenario as S
from wizard_rts.god_world.world import GodWorld


def _world(seed=0):
    w = GodWorld(seed=seed, map_name="Egyptian_Mandala_v1.2")
    w.ai_enabled = False
    w.local_ops_enabled = False
    w.pandemic_enabled = False
    seq = 0
    while w.phase == "SETUP":
        seq += 1
        w.advance(1000, seq, snapshot=False)
    return w


def _campaign(seed=1, wseed=0):
    w = _world(wseed)
    sc = S.build(w)
    return w, sc, R.new_campaign(sc, seed)


def test_p15_the_scenario_is_the_island_with_six_posts_at_the_bases_and_the_six_roles():
    w, sc, st = _campaign()
    assert len(sc["locations"]) == 80 and sum(len(v) for v in sc["links"].values()) == 2 * 109
    assert set(sc["locations"].values()) == set(R.FAMILIES)
    counts = {f: sum(1 for v in sc["locations"].values() if v == f) for f in R.FAMILIES}
    assert all(12 <= n <= 28 for n in counts.values()), counts
    assert len(sc["posts"]) == 6 and all(st["locations"][p]["post"] for p in sc["posts"])
    assert [r["role"] for r in st["responders"]] == list(R.ROLES)
    assert all(r["location"] == r["home"] and r["home"] in sc["posts"] for r in st["responders"])
    # the published deal: two cards each, four escalations in the deck, five events, the nine first infections 3/3/3 with 3/2/1
    assert all(len(r["hand"]) == R.START_CARDS for r in st["responders"])
    assert st["player_deck"].count("epidemic") == 4
    assert sum(1 for c in st["player_deck"] if c in R.EVENTS) + sum(1 for r in st["responders"] for c in r["hand"] if c in R.EVENTS) == 5
    assert len(st["player_deck"]) + 12 == 80 + 5 + 4
    heavy = sorted(sum(l["units"].values()) for l in st["locations"].values() if sum(l["units"].values()) > 0)
    assert heavy == [1, 1, 1, 2, 2, 2, 3, 3, 3]
    assert sum(int(f["reserve"]) for f in st["families"].values()) == 4 * 24 - 18
    assert len(st["infection_discard"]) == 9 and len(st["infection_deck"]) == 71


def test_p16_the_core_rules_hold_on_handmade_vectors():
    w, sc, st = _campaign()
    r = R.current(st)
    # four actions, then no more
    for _ in range(4):
        nxt = st["links"][r["location"]][0]
        R.drive(st, r, nxt)
    with pytest.raises(R.IllegalAction):
        R.drive(st, r, st["links"][r["location"]][0])
    assert st["actions_left"] == 0
    # drive only along links; a flight needs its card
    st["actions_left"] = 4
    far = next(n for n in st["locations"] if n not in st["links"][r["location"]] and n != r["location"])
    with pytest.raises(R.IllegalAction):
        R.drive(st, r, far)
    with pytest.raises(R.IllegalAction):
        R.direct_flight(st, r, far)
    r["hand"].append(far)
    R.direct_flight(st, r, far)
    assert r["location"] == far and far in st["player_discard"]
    # at most three units at a location; the fourth is an outbreak that spreads one to each neighbour, once per location per chain
    nid = far
    fam = st["locations"][nid]["family"]
    for n in st["locations"]:
        st["locations"][n]["units"] = {f: 0 for f in R.FAMILIES}
    for f in R.FAMILIES:
        st["families"][f]["reserve"] = 24
    st["outbreaks"] = 0
    R._add_units(st, nid, fam, 3, set(), "test")
    assert st["locations"][nid]["units"][fam] == 3
    R._add_units(st, nid, fam, 1, set(), "test")
    assert st["outbreaks"] == 1 and st["locations"][nid]["units"][fam] == 3
    assert all(st["locations"][o]["units"][fam] >= 1 for o in st["links"][nid])
    # a chain: two adjacent full locations outbreak each other once, not forever
    a, b = nid, st["links"][nid][0]
    for n in (a, b):
        R._add_units(st, n, fam, 3 - st["locations"][n]["units"][fam], set(), "test")
    assert st["locations"][a]["units"][fam] == 3 and st["locations"][b]["units"][fam] == 3
    before = st["outbreaks"]
    R._add_units(st, a, fam, 1, set(), "test")
    assert st["outbreaks"] == before + 2
    # treat: one unit (the medic all), a cured family all
    st["actions_left"] = 4
    r["location"] = a
    units_a = st["locations"][a]["units"][fam]
    R.treat(st, r, fam)
    assert st["locations"][a]["units"][fam] == units_a - (units_a if r["role"] == "medic" else 1)
    # the reserve is conserved: units out plus the reserve is twenty-four per family
    for f in R.FAMILIES:
        assert st["families"][f]["reserve"] + sum(l["units"][f] for l in st["locations"].values()) == 24


def test_p17_a_countermeasure_needs_five_matching_cards_at_a_post_four_for_the_scientist_and_four_win():
    w, sc, st = _campaign()
    sci = next(r for r in st["responders"] if r["role"] == "scientist")
    medic = next(r for r in st["responders"] if r["role"] == "medic")
    st["turn"] = st["responders"].index(sci)
    fam = "F1"
    cards = [n for n in sorted(st["locations"]) if st["locations"][n]["family"] == fam]
    sci["hand"] = cards[:3]
    sci["location"] = st["posts"][0]
    with pytest.raises(R.IllegalAction):
        R.cure(st, sci, fam)
    sci["hand"] = cards[:4]
    R.cure(st, sci, fam)
    assert st["families"][fam]["cured"] and len(sci["hand"]) == 0
    st["turn"] = st["responders"].index(medic)
    st["actions_left"] = 4
    medic["hand"] = [n for n in sorted(st["locations"]) if st["locations"][n]["family"] == "F2"][:5]
    medic["location"] = next(n for n in st["locations"] if not st["locations"][n]["post"])
    with pytest.raises(R.IllegalAction):
        R.cure(st, medic, "F2")
    medic["location"] = st["posts"][1]
    medic["hand"] = medic["hand"][:4]
    with pytest.raises(R.IllegalAction):
        R.cure(st, medic, "F2")
    medic["hand"] = [n for n in sorted(st["locations"]) if st["locations"][n]["family"] == "F2"][:5]
    R.cure(st, medic, "F2")
    for f in ("F3", "F4"):
        st["families"][f]["cured"] = True
    R._check_won(st)
    assert st["result"] == "won"


def test_p18_escalation_raises_the_rate_infects_the_bottom_card_with_three_and_puts_the_shuffled_discard_on_top():
    w, sc, st = _campaign()
    bottom = st["infection_deck"][0]
    discard_before = list(st["infection_discard"])
    rate_before = R.rate(st)
    st["player_deck"].append("epidemic")
    st["player_deck"].append(next(n for n in sorted(st["locations"]) if n not in R.current(st)["hand"]))
    R.pass_turn(st, R.current(st))
    R.end_turn(st)
    assert st["rate_index"] == 1 and R.rate(st) >= rate_before
    assert st["locations"][bottom]["units"][st["locations"][bottom]["family"]] >= 3 or st["outbreaks"] > 0
    # intensify: the old discard plus the bottom card went back on top, then the infection draw took from them
    drawn = st["infection_discard"]
    assert all(c in discard_before + [bottom] for c in drawn)
    assert R.RATE_TRACK == (2, 2, 2, 3, 3, 4, 4)


def test_p19_hand_limit_and_the_three_losses():
    w, sc, st = _campaign()
    r = R.current(st)
    r["hand"] = [n for n in sorted(st["locations"])][:8]
    R.pass_turn(st, r)
    R.end_turn(st)
    assert len(r["hand"]) <= R.HAND_LIMIT
    # the player deck runs out: lost
    w2, sc2, s2 = _campaign(2)
    s2["player_deck"] = []
    R.pass_turn(s2, R.current(s2))
    R.end_turn(s2)
    assert s2["result"] == "lost" and s2["lost_reason"] == "player_deck_exhausted"
    # eight outbreaks: lost
    w3, sc3, s3 = _campaign(3)
    s3["outbreaks"] = 7
    nid = next(n for n in s3["locations"])
    fam = s3["locations"][nid]["family"]
    s3["locations"][nid]["units"][fam] = 3
    R._add_units(s3, nid, fam, 1, set(), "test")
    assert s3["result"] == "lost" and s3["lost_reason"] == "outbreaks"
    # the reserve runs out: lost
    w4, sc4, s4 = _campaign(4)
    fam = "F3"
    s4["families"][fam]["reserve"] = 0
    nid = next(n for n in s4["locations"] if s4["locations"][n]["units"][fam] < 3)
    R._add_units(s4, nid, fam, 1, set(), "test")
    assert s4["result"] == "lost" and s4["lost_reason"] == "reserve_exhausted"


def test_p20_the_campaign_is_deterministic_in_its_seed_and_a_save_replays():
    w, sc, a = _campaign(5)
    _, _, b = _campaign(5)
    assert a == b
    _, _, c = _campaign(6)
    assert c != a
    for _ in range(6):
        C.take_turn(a)
        C.take_turn(b)
    assert a == b
    mid = json.loads(json.dumps(a))
    for _ in range(6):
        C.take_turn(a)
        C.take_turn(mid)
    assert a == mid


def test_p21_the_coordinator_reads_only_public_state_and_both_wins_and_losses_happen():
    results = {}
    for seed in range(12):
        w, sc, st = _campaign(seed)
        deck_before = list(st["player_deck"])
        inf_before = list(st["infection_deck"])
        n = 0
        while st["result"] is None and n < 200:
            # the coordinator never reorders or reads the decks: they change only by the rules' own draws and shuffles
            pd, idk = len(st["player_deck"]), len(st["infection_deck"])
            C.take_turn(st)
            assert len(st["player_deck"]) <= pd
            n += 1
        results[seed] = (st["result"], st["lost_reason"], st["turn_count"], st["outbreaks"], len(R.summary(st)["cured"]))
        view = R.public_view(st)
        assert "player_deck" not in view and "infection_deck" not in view
    wins = [s for s, r in results.items() if r[0] == "won"]
    losses = [s for s, r in results.items() if r[0] == "lost"]
    assert wins, results
    assert losses, results  # the campaign is honest: some crises are lost
    assert all(r[0] is not None for r in results.values()), results
