"""Plan v2 5.3: paper and the scriptorium give a bonus hand from a reserve deck, never taking from circulating packs, and the ware books balance."""
from wizard_rts import draft, ledger, tech
from wizard_rts.economy import produce
from wizard_rts.world import HybridWorld


def world():
    w = HybridWorld(507, profile="developer")
    w.ai_enabled = False
    w.cardset, w.draft_v2 = "v2", True
    w._seq = 0
    return w


def run(w, s):
    for _ in range(int(s)):
        w._seq += 1
        w.advance(1000, w._seq, snapshot=False)


def give_scriptorium(w, faction="Red"):
    from wizard_rts.content import graph

    card = next(cid for cid, c in sorted(graph.generated_cards().items()) if "scriptorium" in c["entities"])
    assert tech.grant(w, faction, card)["status"] == "ok"
    home = next(b for b in w.buildings.values() if b["faction_name"] == faction and b["kind"] == "warehouse")
    placed = None
    for dx in range(6, 30):
        for dy in range(6, 30):
            r = w.build(faction, "scriptorium", home["tx"] + dx, home["ty"] + dy)
            if r["status"] == "ok":
                placed = r["id"]
                break
        if placed:
            break
    assert placed, "no site for the scriptorium"
    b = w.buildings[placed]
    b.pop("constructing", None)
    b["operational"] = True
    b["hp"] = b["max_hp"]
    return home["id"], placed


def test_scriptorium_turns_plank_and_water_into_paper():
    w = world()
    wh, sid = give_scriptorium(w)
    produce(w, sid, "plank", 2)
    produce(w, sid, "water", 2)
    run(w, 150)
    assert w.stats.get("made_paper", 0) >= 2 and w.stats.get("consumed_plank", 0) >= 2


def test_bonus_hand_needs_scriptorium_and_paper_and_consumes_two_sheets():
    w = world()
    run(w, 2)
    st = draft.state(w)
    assert "Red" not in st["bonus"]
    wh, sid = give_scriptorium(w)
    produce(w, wh, "paper", 3)
    before = ledger.snapshot_totals(w)
    run(w, 6 * 60 + 2)  # round 2 opens
    assert "Red" in st["bonus"] and len(st["bonus"]["Red"]) == draft.BONUS_HAND
    packs_before = {f: list(p) for f, p in st["packs"].items()}
    hand = list(st["bonus"]["Red"])
    # first the normal pick, then the bonus pick
    assert tech.draft(w, "Red", next(c for c in w.tech["Red"]["offers"] if c in st["packs"]["Red"]))["status"] == "ok"
    assert {f: list(p) for f, p in st["packs"].items() if f != "Red"} == {f: p for f, p in packs_before.items() if f != "Red"}
    assert tech.draft(w, "Red", hand[0])["status"] == "ok"
    assert w.stocks[wh]["paper"] == 1 and w.stats["consumed_paper"] == 2
    assert not ledger.check(w, before)  # the ware books balance
    assert "Red" not in st["bonus"]
    # with one sheet left no new hand is dealt next round
    run(w, 6 * 60)
    assert "Red" not in st["bonus"]


def test_bonus_pick_is_rejected_if_the_paper_is_gone():
    w = world()
    run(w, 2)
    wh, sid = give_scriptorium(w)
    produce(w, wh, "paper", 2)
    run(w, 6 * 60 + 2)
    hand = list(draft.state(w)["bonus"]["Red"])
    w.stocks[wh]["paper"] = 0
    tech.draft(w, "Red", w.tech["Red"]["offers"][0])
    assert tech.draft(w, "Red", hand[0])["reason"] == "no_paper"
