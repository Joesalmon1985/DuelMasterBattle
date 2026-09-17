"""T042 observations and legal candidate generation."""

from __future__ import annotations

import pytest

from sim.dmb.ai.interface import NoOpBrain
from sim.dmb.ai.legal import LegalActionGenerator
from sim.dmb.ai.observation import ObservationBuilder
from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError, WorldId
from sim.dmb.technology.draft import DraftService
from sim.dmb.core.rng import RngBank


def _world() -> WorldState:
    state = WorldState(world_id=WorldId("world:t042"), ids=IdAllocator(WorldId("world:t042")))
    state.factions = {
        "faction:1": {"id": "faction:1", "relations": {}},
        "faction:2": {"id": "faction:2", "relations": {}},
    }
    state.settlements["settlement:1"] = {
        "id": "settlement:1",
        "faction_id": "faction:1",
        "node_id": "node:1",
        "store_id": "store:1",
        "tier": "settlement",
        "operational": True,
    }
    state.stocks["store:1"] = {"catan": {"timber": {"available": 0, "reserved": 0, "escrow": 0}}}
    state.player = {
        "node_id": "node:1",
        "private_conversation": "SECRET_WIZARD_CHAT",
        "inventory_secret": ["wand"],
        "position": [0, 0],
    }
    state.units["unit:enemy"] = {
        "id": "unit:enemy",
        "faction_id": "faction:2",
        "node_id": "node:2",
        "publicly_observed": True,
        "public_strength": 3,
        "private_orders": "ATTACK_PLAN_SECRET",
        "health": 99,
    }
    state.units["unit:hidden"] = {
        "id": "unit:hidden",
        "faction_id": "faction:2",
        "node_id": "node:9",
        "publicly_observed": False,
        "private_orders": "HIDDEN",
    }
    state.world_version = 1
    return state


def test_hides_wizard_and_private_enemy_fields() -> None:
    state = _world()
    obs = ObservationBuilder(state).build("faction:1", "seat")
    blob = str(obs)
    assert "SECRET_WIZARD_CHAT" not in blob
    assert "wand" not in blob
    assert "ATTACK_PLAN_SECRET" not in blob
    assert "HIDDEN" not in blob
    assert obs["masks"]["wizard_private_excluded"] is True
    enemy_ids = {e["id"] for e in obs["observed"]["enemies"]}
    assert "unit:enemy" in enemy_ids
    assert "unit:hidden" not in enemy_ids
    assert "private_orders" not in obs["observed"]["enemies"][0]


def test_all_candidates_validate_and_noop_when_stuck() -> None:
    state = _world()
    obs = ObservationBuilder(state).build("faction:1", "seat")
    gen = LegalActionGenerator(state)
    cands = gen.enumerate(obs, "seat")
    assert any(c["action_kind"] == "noop" for c in cands)
    for cand in cands:
        assert gen.validate_candidate(obs, cand)
    brain = NoOpBrain()
    assert brain.choose(obs, cands).startswith("noop:")


def test_stale_candidate_cannot_partially_mutate() -> None:
    state = _world()
    obs = ObservationBuilder(state).build("faction:1", "seat")
    gen = LegalActionGenerator(state)
    cands = gen.enumerate(obs, "seat")
    noop = next(c for c in cands if c["action_kind"] == "noop")
    # Bump world version → stale.
    state.world_version = 99
    obs_stale = dict(obs)
    before_commitments = list(state.factions["faction:1"].get("commitments", []))
    with pytest.raises(TypeValidationError, match="stale"):
        gen.commit(obs_stale, noop)
    assert state.factions["faction:1"].get("commitments", []) == before_commitments
    # Fresh observation can commit no-op.
    fresh = ObservationBuilder(state).build("faction:1", "seat")
    fresh_cands = gen.enumerate(fresh, "noop" if False else "seat")
    fresh_noop = next(c for c in fresh_cands if c["action_kind"] == "noop")
    record = gen.commit(fresh, fresh_noop)
    assert record["status"] == "accepted"


def test_tech_pick_candidates_from_hand() -> None:
    state = _world()
    state.rng = RngBank(streams={"tech_draft": {"seed": 1, "version": 1, "draws": 0}}).to_dict()
    DraftService(state).deal("prehistoric", ["faction:1", "faction:2"])
    obs = ObservationBuilder(state).build("faction:1", "technology")
    assert len(obs["own"]["hand"]) == 7
    gen = LegalActionGenerator(state)
    cands = gen.enumerate(obs, "technology")
    picks = [c for c in cands if c["action_kind"] == "tech_pick"]
    assert len(picks) == 7
    assert all(gen.validate_candidate(obs, c) for c in picks)
