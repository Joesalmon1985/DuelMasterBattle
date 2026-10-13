"""ai_plus.card_step: the plus AI builds what its drafted cards unlock (plan v2 5.3, first v2 probes showed 35% of unlocked entities never built)."""
from wizard_rts import ai_plus, construction as con, tech
from wizard_rts.content import graph
from wizard_rts.economy import produce
from wizard_rts.world import HybridWorld


def test_card_step_places_one_unbuilt_drafted_building_of_its_tribe():
    w = HybridWorld(507, profile="developer")
    w.ai_enabled = False
    w.cardset = "v2"
    tribe = w.faction_info["Red"]["tribe"]
    cheap = [cid for cid, c in sorted(graph.generated_cards().items())
             if c["entities"][0].startswith("wl:") and c["tribe"] == tribe and set(con.build_spec(c["entities"][0])["cost"]) <= {"log", "plank", "granite"}
             and "mine" not in c["entities"][0]]
    assert cheap, "no cheap building card for this tribe"
    card = cheap[0]
    assert tech.grant(w, "Red", card)["status"] == "ok"
    wh = con.faction_warehouse(w, "Red")
    for good in ("log", "plank", "granite"):
        produce(w, wh["id"], good, 40)
    kinds = [e for e in graph.generated_cards()[card]["entities"]]
    before = {b["id"] for b in w.buildings.values()}
    assert ai_plus.card_step(w, "Red", wh) is True
    new = [b for b in w.buildings.values() if b["id"] not in before and b["faction_name"] == "Red"]
    assert len(new) == 1 and new[0]["kind"] in kinds and new[0].get("constructing")
    assert [e for e in w.events if e["kind"] == "ai_build" and e.get("why") == "drafted"]


def test_card_step_does_nothing_without_cards_or_with_other_tribes_buildings():
    w = HybridWorld(507, profile="developer")
    w.ai_enabled = False
    w.cardset = "v2"
    wh = con.faction_warehouse(w, "Red")
    assert ai_plus.card_step(w, "Red", wh) is False
    tribe = w.faction_info["Red"]["tribe"]
    other = next(cid for cid, c in sorted(graph.generated_cards().items()) if c["tribe"] and c["tribe"] != tribe)
    tech.grant(w, "Red", other)
    produce(w, wh["id"], "log", 40)
    assert ai_plus.card_step(w, "Red", wh) is False  # a card for another tribe's building cannot be used
