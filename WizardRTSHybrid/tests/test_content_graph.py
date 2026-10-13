"""Plan v2 section 4: the content graph and generated cards are consistent with the registries and really gate placement."""
import pytest

from wizard_rts import construction as con
from wizard_rts import draft, tech
from wizard_rts.content import graph
from wizard_rts.world import HybridWorld


def test_static_checks_are_clean():
    assert graph.check() == []


def test_every_card_unlocks_one_or_two_existing_entities_and_not_every_card_two():
    cards = graph.generated_cards()
    sizes = {len(c["entities"]) for c in cards.values()}
    assert sizes == {1, 2}
    assert sum(len(c["entities"]) == 1 for c in cards.values()) > 0.5 * len(cards)


def test_every_non_foundation_building_and_unit_is_on_exactly_one_card():
    ents = graph.entities()
    onboard = [e for c in graph.generated_cards().values() for e in c["entities"]]
    assert len(onboard) == len(set(onboard))
    assert set(onboard) == {k for k, e in ents.items() if not e["foundation"]}


def test_foundation_lets_a_faction_feed_itself_and_found_settlements():
    w = HybridWorld(507, profile="campaign")
    w.cardset = "v2"
    w.ai_enabled = False
    assert tech.unit_allowed(w, "Red", "settlers")
    assert tech.kind_allowed(w, "Red", "tavern")
    assert tech.kind_allowed(w, "Red", "quarry")
    assert not tech.kind_allowed(w, "Red", "barracks")


def test_drafting_a_generated_card_unlocks_exactly_its_entities():
    w = HybridWorld(507, profile="campaign")
    w.ai_enabled = False
    w.cardset = "v2"
    w.draft_v2 = True
    w._seq = 0
    for _ in range(3):
        w._seq += 1
        w.advance(1000, w._seq, snapshot=False)
    f = draft.state(w)["ring"][0]
    pack = draft.state(w)["packs"][f]
    assert len(pack) == draft.PACK_SIZE and all(c.startswith("gen.") for c in pack[:5])
    pair = next((c for c in pack if len(tech.lookup()[c]["entities"]) == 2), None) or pack[0]
    card = tech.lookup()[pair]
    before = {e for e in card["entities"] if (e.startswith("unit:") and tech.unit_allowed(w, f, e[5:])) or (not e.startswith("unit:") and tech.kind_allowed(w, f, e))}
    assert not before
    assert tech.draft(w, f, pair)["status"] == "ok"
    for e in card["entities"]:
        assert tech.unit_allowed(w, f, e[5:]) if e.startswith("unit:") else tech.kind_allowed(w, f, e)
    # a sibling building of the same name pattern stays locked: unlocking is exact, not by substring
    others = [k for k in graph.entities() if k.startswith("wl:") and k not in card["entities"] and not graph.entities()[k]["foundation"]]
    assert all(not tech.kind_allowed(w, f, k) for k in others if k not in tech._exact_wl(w, f))


def test_old_draft_ignores_generated_cards():
    w = HybridWorld(507, profile="campaign")
    w.ai_enabled = False
    assert all(not c.startswith("gen.") for c in tech.draftable(w, "Red"))
