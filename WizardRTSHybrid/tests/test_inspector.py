"""God Mode inspector views (plan v2 8.6) are computed from the authoritative world and agree with what the engine then does."""
from wizard_rts import draft, inspector, server, tech, vp
from wizard_rts.content import graph
from wizard_rts.world import HybridWorld


def world(profile="developer"):
    w = HybridWorld(507, profile=profile)
    w.ai_enabled = False
    w.cardset, w.draft_v2 = "v2", True
    w._seq = 0
    for _ in range(3):
        w._seq += 1
        w.advance(1000, w._seq, snapshot=False)
    return w


def test_catalogue_lists_every_generated_card_with_art_status():
    w = world()
    cat = inspector.catalogue(w)
    assert cat["count"] == len(graph.generated_cards())
    by_entity = {e["id"]: e["art"] for c in cat["cards"] for e in c["entities"]}
    assert by_entity["unit:infantry"]["status"] == "imported"  # openra.e1
    assert by_entity["unit:shock_trooper"]["status"] == "imported"  # shok.shp, read through the decrypted hires1.mix
    assert by_entity["unit:clubman"]["status"] == "alias_placeholder"
    assert "unit:clubman" in cat["entities_without_real_art"]


def test_factions_view_counts_production_by_entity():
    w = world()
    f = draft.state(w)["ring"][0]
    card = w.tech[f]["offers"][0]
    assert tech.draft(w, f, card)["status"] == "ok"
    ent = tech.lookup()[card]["entities"][0]
    assert ent in {e["id"] for h in inspector.factions(w)[f]["cards"] for e in h["entities"]}
    assert ent in inspector.factions(w)[f]["unproduced"]
    w.note_produced(f, ent)
    w.note_produced(f, ent)
    rec = next(e for h in inspector.factions(w)[f]["cards"] for e in h["entities"] if e["id"] == ent)
    assert rec["produced"] == 2 and rec["first_ms"] is not None


def test_draft_view_predicts_the_leftover_rule(monkeypatch):
    w = world()
    ring = draft.state(w)["ring"]
    monkeypatch.setattr(vp, "totals", lambda world: {f: (9 if f == ring[0] else 2) for f in world.faction_info})
    view = inspector.draft_view(w)
    assert view["enabled"] and view["round"] == 1 and len(view["packs"]) == 6
    predicted = view["if_era_ended_now"]
    before = {f: list(w.tech[f]["cards"]) for f in ring}
    draft.end_era(w)
    ev = [e for e in w.events if e["kind"] == "draft_leftovers"][-1]
    assert {f: sorted(c) for f, c in predicted["awarded"].items()} == {f: sorted(c) for f, c in ev["awarded"].items()}
    assert {f: sorted(c) for f, c in predicted["lost"].items()} == {f: sorted(c) for f, c in ev["lost"].items()}
    assert all(set(w.tech[f]["cards"]) == set(before[f]) | set(ev["awarded"].get(f, [])) for f in ring)


def test_server_op_is_god_mode_only_and_read_only():
    dev = world("developer")
    reply = server._handle(dev, {"op": "inspect", "what": "draft"})
    assert reply["status"] == "ok" and reply["data"]["enabled"]
    assert server._handle(dev, {"op": "inspect", "what": "nope"})["status"] == "rejected"
    h_before = dev.state_hash()
    server._handle(dev, {"op": "inspect", "what": "catalogue"})
    server._handle(dev, {"op": "inspect", "what": "factions"})
    assert dev.state_hash() == h_before
    camp = world("campaign")
    assert server._handle(camp, {"op": "inspect", "what": "draft"})["reason"] == "god_mode_disabled"
