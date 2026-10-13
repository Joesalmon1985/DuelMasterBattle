"""Era assignment rules (owner, 13 Oct 2026), generated from the content graph so every new entity is checked automatically."""
from __future__ import annotations

from wizard_rts import tech
from wizard_rts.content import graph
from wizard_rts.world import HybridWorld


def test_content_graph_static_checks_are_clean():
    assert graph.check() == []


def test_every_openra_entity_is_available_by_historic():
    ents = graph.entities()
    late = [k for k, e in ents.items() if e["game"] == "openra" and e["era"] > 1]
    assert late == []
    cards = graph.generated_cards()
    for cid, c in cards.items():
        for e in c["entities"]:
            if ents[e]["game"] == "openra":
                assert c["era"] <= 1, (cid, e)


def test_mindustry_units_never_precede_dystopian_and_industry_never_precedes_modern():
    ents = graph.entities()
    cards = graph.generated_cards()
    for cid, c in cards.items():
        for e in c["entities"]:
            if ents[e]["game"] == "mindustry" and ents[e]["type"] == "unit":
                assert c["era"] >= 3, (cid, e)
            if ents[e]["game"] == "mindustry":
                assert c["era"] >= 2, (cid, e)


def test_widelands_production_is_all_prehistoric():
    cards = graph.generated_cards()
    ents = graph.entities()
    for cid, c in cards.items():
        if any(ents[e]["game"] == "widelands" for e in c["entities"]):
            assert c["era"] == 0, cid


def test_gated_worlds_draft_v2_by_default_and_legacy_is_explicit():
    w = HybridWorld(507, profile="campaign")
    assert w.cardset == "v2" and w.draft_v2 and not w.legacy_draft
    assert HybridWorld(507, profile="test_showcase").__dict__.get("draft_v2") is None
    old = HybridWorld(507, profile="campaign", legacy_draft=True)
    assert old.__dict__.get("draft_v2") is None and tech.gated(old)
