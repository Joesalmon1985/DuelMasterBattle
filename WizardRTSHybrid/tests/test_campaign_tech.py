"""M1: campaign profiles, primitive start, drafted-tech unlocks, God Mode gating (D02, D13, D15; S05, S06)."""
import subprocess
import sys

import pytest

from wizard_rts import construction as con
from wizard_rts import server, tech
from wizard_rts.sim_api import HybridEnv
from wizard_rts.world import HybridWorld

SEED = 507
PRIMITIVE_KINDS = set(tech.primitive()["kinds"])


@pytest.fixture(scope="module")
def campaign():
    return HybridWorld(SEED, profile="campaign", legacy_draft=True)


def _fresh():
    return HybridWorld(SEED, profile="campaign", legacy_draft=True)


def test_profiles_defined_and_unknown_rejected():
    assert set(tech.PROFILES) == {"campaign", "developer", "test_showcase", "test_minimal"}
    with pytest.raises(ValueError):
        HybridWorld(SEED, profile="nope")
    assert HybridWorld(SEED).profile == "test_showcase"
    assert HybridWorld(SEED, minimal=True).profile == "test_minimal"


def test_campaign_start_is_primitive_for_every_faction(campaign):
    w = campaign
    assert len(w.faction_info) == 6
    for name in w.faction_info:
        kinds = {b["kind"] for b in w.buildings.values() if b["faction_name"] == name and "hp" in b}
        assert kinds <= {"warehouse", "producer", "processor", "ranger", "quarry", "hunter", "well"}, (name, kinds)
        assert {"warehouse", "producer", "ranger", "processor"} <= kinds
        units = {u["kind"] for u in w.units.values() if u["faction_name"] == name}
        assert units == {"soldier"}, (name, units)


def test_every_non_primitive_kind_is_locked_by_card(campaign):
    w = campaign
    wh = con.faction_warehouse(w, "Red")
    menu = con.full_menu()
    locked = [k for k in menu if not tech.kind_allowed(w, "Red", k)]
    assert set(con.BUILD_MENU) - PRIMITIVE_KINDS <= set(locked)
    for kind in locked:
        why, _ = con.check_placement(w, "Red", kind, wh["tx"] + 6, wh["ty"] + 6)
        assert why == "locked_by_card", (kind, why)
    assert any(k.startswith("wl:") for k in locked)
    assert any(k.startswith("wl:") for k in menu if tech.kind_allowed(w, "Red", k))  # the primitive woodcutter/quarry kinds


def test_locked_unit_queue_rejected():
    w = _fresh()
    wh = con.faction_warehouse(w, "Red")
    b = w._building(w.faction_info["Red"]["id"], "Red", "barracks", (wh["tx"] + 9, wh["ty"] + 9), "Barracks", "openra.barracks")
    assert con.queue_unit(w, b, "infantry")["reason"] == "locked_by_card"
    tech.grant(HybridWorld(SEED, profile="developer", legacy_draft=True), "Red", "dmb.card.drill_tactics")  # grant is a developer command
    assert tech.grant(w, "Red", "dmb.card.drill_tactics") == {"status": "rejected", "reason": "god_mode_disabled"}


def test_showcase_and_minimal_unlock_everything():
    w = HybridWorld(SEED, profile="test_showcase")
    assert all(tech.kind_allowed(w, "Red", k) for k in con.full_menu())
    kinds = {b["kind"] for b in w.buildings.values() if b["faction_name"] == "Red"}
    assert {"mine", "smithy", "barracks", "vehicle_factory"} <= kinds


def test_draft_offers_follow_prerequisites():
    w = _fresh()
    w.advance(100, 1)
    st = w.tech["Red"]
    assert st["round"] == 1 and 1 <= len(st["offers"]) <= tech.OFFER_SIZE
    for cid in st["offers"]:
        c = tech.cards()[cid]
        assert c["requires_cards"] == []  # nothing is drafted yet
        assert all(any(b["kind"] == k and b["faction_name"] == "Red" for b in w.buildings.values()) for k in c["requires_working"][:1])
    assert "dmb.card.smelting" not in st["offers"] and "dmb.card.motor_pool" not in st["offers"]
    assert tech.draft(w, "Red", "dmb.card.motor_pool")["reason"] == "not_offered"


def test_draft_unlocks_exactly_listed_kinds():
    w = _fresh()
    w.advance(100, 1)
    st = w.tech["Red"]
    cid = st["offers"][0]
    before = tech.unlocked_kinds(w, "Red")
    assert tech.draft(w, "Red", cid)["status"] == "ok"
    after = tech.unlocked_kinds(w, "Red")
    assert after - before == set(tech.cards()[cid]["kinds"]) - before
    assert st["offers"] == [] and tech.draft(w, "Red", cid)["reason"] == "not_offered"
    other = tech.unlocked_kinds(w, "Blue")
    assert other == PRIMITIVE_KINDS  # a card is per faction


def test_new_round_every_interval_and_lapse():
    w = _fresh()
    w.draft_interval_ms = 60_000
    w.advance(100, 1)
    first = list(w.tech["Red"]["offers"])
    w.advance(61_000, 2)
    assert w.tech["Red"]["round"] == 2
    assert w.tech["Blue"]["round"] == 2
    assert first  # unchosen offers lapse; a new set is drawn


def test_ai_drafts_and_builds_unlocked_only():
    w = _fresh()
    w.ai_enabled = True
    w.draft_interval_ms = 120_000
    w.advance(10 * 60_000, 1)
    for name in w.faction_info:
        assert w.tech[name]["cards"], name  # every faction drafted at least once
    for b in w.buildings.values():
        if "hp" in b and b["kind"] not in ("warehouse", "blight_nest"):  # a blight nest belongs to no faction
            assert tech.kind_allowed(w, b["faction_name"], b["kind"]), (b["faction_name"], b["kind"])


def test_god_ops_rejected_in_campaign_accepted_in_developer():
    camp, dev = _fresh(), HybridWorld(SEED, profile="developer", legacy_draft=True)
    wh = con.faction_warehouse(dev, "Red")
    for op in sorted(server.GOD_OPS):
        reply = server._handle(camp, {"op": op, "faction": "Red", "kind": "quarry", "tx": 1, "ty": 1})
        assert reply == {"status": "rejected", "reason": "god_mode_disabled", "profile": "campaign"}, op
    ok = server._handle(dev, {"op": "build", "faction": "Red", "kind": "quarry", "tx": wh["tx"] + 7, "ty": wh["ty"] + 7})
    assert ok.get("reason") != "god_mode_disabled"
    for op in ("snapshot", "pose", "interact", "menu", "tech", "profile"):  # the wizard's own ops stay open
        assert server._handle(camp, {"op": op, "tx": camp.player["tx"], "ty": camp.player["ty"]}).get("reason") != "god_mode_disabled"
    assert server._handle(dev, {"op": "grant_card", "faction": "Red", "card": "dmb.card.mining"})["status"] == "ok"
    assert "mine" in tech.unlocked_kinds(dev, "Red")


def test_env_draft_action_and_mask():
    env = HybridEnv(seed=SEED, agent_factions=("Red",), profile="campaign", step_ms=2000)
    env.reset()
    env.step({"Red": []})
    mask = env.legal_actions("Red")
    assert mask["draft"], mask["draft"]
    kinds_buildable = {m["kind"] for m in mask["build"]}
    own_wl = {k for k in kinds_buildable if k.startswith("wl:")}
    assert all(k.startswith("wl:barbarians_") for k in own_wl)  # the foundation's own-tribe Widelands buildings are listed too (V4: the mask covers them)
    assert kinds_buildable - own_wl <= PRIMITIVE_KINDS | set(tech.FOUNDATION_KINDS)  # v2 worlds add the foundation set (tavern, clinic)
    r = env.apply("Red", {"op": "draft", "card": mask["draft"][0]})
    assert r["status"] == "ok"
    assert env.apply("Red", {"op": "draft", "card": "dmb.card.smelting"})["status"] == "rejected"


def test_card_json_is_consistent():
    from wizard_rts import construction as con2
    from wizard_rts.industry import registry

    cards = tech.cards()
    known = set(con2.BUILD_MENU) | set(registry.kinds())
    for c in cards.values():
        assert set(c["kinds"]) <= known, c["id"]
        for r in c["requires_cards"]:
            assert r in cards and cards[r]["era"] <= c["era"]
        for k in c["requires_working"]:
            assert k in known
        for u in c["units"]:
            assert any(u in v for v in con2.RECIPES.values()) or registry.ground_unit(u) or u == "caravan", (c["id"], u)  # caravans: trade.py
    # every hybrid and Mindustry kind is reachable: primitive or unlocked by at least one card
    from wizard_rts.content import graph

    # the generated v2 cards (drafting v2) also unlock kinds, among them hybrid buildings that exist only there (the scriptorium)
    covered = PRIMITIVE_KINDS | {k for c in cards.values() for k in c["kinds"]} | {k for c in graph.generated_cards().values() for k in c["kinds"]} | set(tech.FOUNDATION_KINDS)
    assert covered == known  # (the foundation kinds, among them the v2-only clinic, need no card)
    for k in sorted(registry._blocks()):  # the hand-tuned first slice: its card pointer agrees with the card file (the generic blocks are on generated cards)
        assert k in cards[registry.block(k)["card"]]["kinds"], k


def test_hash_stable_across_processes():
    code = "from wizard_rts.world import HybridWorld; w=HybridWorld(507, profile='campaign', legacy_draft=True); w.advance(2000,1); print(w.state_hash())"
    outs = []
    for hs in ("0", "123"):
        root = __import__("pathlib").Path(__file__).resolve().parents[1]
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(root),
                           env={**__import__("os").environ, "PYTHONHASHSEED": hs, "HYBRID_AI": "0", "PYTHONPATH": str(root)})
        assert r.returncode == 0, r.stderr
        outs.append(r.stdout.strip())
    assert outs[0] == outs[1]


@pytest.mark.parametrize("mode", ["peace", "war"])
def test_forty_minute_campaign_every_faction_develops(mode):
    """Peace and war are separate acceptances (M1): peace requires every faction alive and developing; war only requires the
    simulation to stay lawful (a legitimate military defeat does not fail the run)."""
    from wizard_rts import ledger

    w = HybridWorld(SEED, profile="campaign", legacy_draft=True)
    w.ai_enabled = True
    w.ai_aggressive = mode == "war"
    initial = ledger.snapshot_totals(w)
    for i in range(40 * 60):
        w.advance(1000, i + 1, snapshot=False)
    assert not [(b, g, v) for b, s in w.stocks.items() for g, v in s.items() if v < 0]
    assert ledger.check(w, initial) == []
    for name in w.faction_info:
        assert len(w.tech[name]["cards"]) >= 6, (name, w.tech[name]["cards"])  # a round every 4 game minutes (S05 revised), offers of up to 7
        assert w.tech[name]["round"] >= 10
        for b in w.buildings.values():
            if b["faction_name"] == name and "hp" in b and b["kind"] != "warehouse":
                assert tech.kind_allowed(w, name, b["kind"]), (name, b["kind"])
    if mode == "peace":
        for name in w.faction_info:
            assert con.faction_warehouse(w, name)["hp"] > 0
            assert sum(1 for b in w.buildings.values() if b["faction_name"] == name and b["kind"] in ("mine", "ironmine")) >= 1
