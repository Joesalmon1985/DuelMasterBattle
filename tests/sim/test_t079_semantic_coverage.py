"""T079 complete semantic observation/action coverage."""

from __future__ import annotations

from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.narrative.knowledge import reveal, KnowledgeFact
from sim.dmb.narrative.semantic import HIDDEN_PLAYER_KEYS, REQUIRED_KINDS, SemanticResolver


def _world() -> WorldState:
    state = WorldState(world_id=WorldId("world:t079"), ids=IdAllocator(WorldId("world:t079")))
    state.player = {"node_id": "node:v", "position": [5.0, 5.0]}
    state.world_version = 3
    state.people["person:1"] = {
        "id": "person:1",
        "name": "SecretName",
        "alive": True,
        "node_id": "node:v",
        "grid": [5.0, 5.0],
        "role": "worker",
    }
    state.buildings["building:1"] = {
        "id": "building:1",
        "definition_id": "building.factory",
        "label": "Mill",
        "node_id": "node:v",
        "grid": [6.0, 5.0],
        "active": True,
        "stocks": {"ore": 99},
        "production_rate": 12.5,
    }
    state.units["unit:1"] = {
        "id": "unit:1",
        "faction_id": "faction:red",
        "archetype": "skirmisher",
        "node_id": "node:v",
        "position": [5.0, 6.0],
        "current_health": 10,
        "max_health": 40,
        "status": "active",
        "army_strength": 9001,
    }
    state.carts["cart:1"] = {
        "id": "cart:1",
        "node_id": "node:v",
        "grid": [4.0, 5.0],
        "active": True,
        "label": "Timber cart",
    }
    state.roads["road:1"] = {
        "id": "road:1",
        "node_id": "node:v",
        "midpoint": [7.0, 5.0],
        "label": "Lane",
        "from": "node:v",
        "to": "node:w",
    }
    state.items["item:1"] = {
        "id": "item:1",
        "kind": "item",
        "node_id": "node:v",
        "grid": [5.0, 4.0],
        "label": "Key",
        "active": True,
        "secret_inventory": True,
    }
    state.board = {
        "mechanisms": {
            "mech:1": {
                "id": "mech:1",
                "node_id": "node:v",
                "grid": [6.0, 6.0],
                "label": "Sluice lever",
                "active": True,
            }
        },
        "entrances": {
            "entrance:1": {
                "id": "entrance:1",
                "node_id": "node:v",
                "grid": [3.0, 5.0],
                "label": "Sluice door",
                "dungeon_id": "dungeon.sluice",
                "active": True,
            }
        },
    }
    state.hazards = {
        "catastrophe": {
            "cubes": {
                "cube:1": {
                    "id": "cube:1",
                    "hex_id": "hex:1",
                    "active": True,
                    "position": [5.0, 7.0],
                }
            }
        }
    }
    state.board["hex_anchors"] = {"hex:1": {"grid": [5.0, 7.0]}}
    state.board["fx_hazard"] = {"hex_labels": {"hex:1": "Hazard hex:1"}}
    return state


def test_every_required_kind_can_be_selected() -> None:
    state = _world()
    resolver = SemanticResolver(state)
    assert resolver.kinds_supported() == REQUIRED_KINDS
    ids = {
        "person": "person:1",
        "building": "building:1",
        "unit": "unit:1",
        "cart": "cart:1",
        "road": "road:1",
        "item": "item:1",
        "mechanism": "mech:1",
        "entrance": "entrance:1",
        "hazard": "cube:1",
    }
    poses = {"wizard": [5.0, 5.0]}
    for kind, eid in ids.items():
        poses[eid] = list(
            state.people.get(eid, {}).get("grid")
            or state.buildings.get(eid, {}).get("grid")
            or state.units.get(eid, {}).get("position")
            or state.carts.get(eid, {}).get("grid")
            or state.roads.get(eid, {}).get("midpoint")
            or state.items.get(eid, {}).get("grid")
            or state.board["mechanisms"].get(eid, {}).get("grid")
            or state.board["entrances"].get(eid, {}).get("grid")
            or [5.0, 7.0]
        )
        selected = resolver.select(eid, local_poses=poses)
        assert selected["ok"] is True, kind
        assert selected["kind"] == kind
        assert selected["targetable"] is True
        actions = [a["id"] for a in selected["actions"]]
        assert "observe" in actions


def test_unknown_identity_remains_targetable() -> None:
    state = _world()
    resolver = SemanticResolver(state)
    # No knowledge reveal — name stays hidden.
    selected = resolver.select("person:1", local_poses={"wizard": [5.0, 5.0], "person:1": [5.0, 5.0]})
    assert selected["ok"] is True
    assert selected["unknown_identity"] is True
    assert selected["targetable"] is True
    assert selected["label"] == "Person"
    assert "SecretName" not in selected["label"]


def test_stale_entity_refreshes_feedback() -> None:
    state = _world()
    resolver = SemanticResolver(state)
    stale = resolver.select("person:1", expected_world_version=1)
    assert stale["ok"] is False
    assert stale["refresh"] is True
    assert stale["reason"] == "stale_world"
    missing = resolver.select("person:missing")
    assert missing["ok"] is False
    assert missing["refresh"] is True
    assert missing["reason"] == "missing_entity"


def test_hidden_economy_army_facts_excluded() -> None:
    state = _world()
    resolver = SemanticResolver(state)
    view = resolver.player_view(
        "building:1",
        local_poses={"wizard": [6.0, 5.0], "building:1": [6.0, 5.0]},
    )
    for key in HIDDEN_PLAYER_KEYS:
        assert key not in view
    unit_view = resolver.inspect(
        "unit:1",
        local_poses={"wizard": [5.0, 6.0], "unit:1": [5.0, 6.0]},
    )
    assert "army_strength" not in unit_view
    assert "production_rate" not in unit_view
    # Description may mention public health, not army_strength.
    assert "9001" not in unit_view.get("description", "")


def test_contextual_actions_by_kind() -> None:
    state = _world()
    resolver = SemanticResolver(state)
    near = {"wizard": [5.0, 5.0], "person:1": [5.0, 5.0], "mech:1": [5.0, 5.0], "item:1": [5.0, 5.0], "entrance:1": [5.0, 5.0]}
    assert "talk" in [a["id"] for a in resolver.available_actions("person:1", local_poses=near)]
    assert "use" in [a["id"] for a in resolver.available_actions("mech:1", local_poses=near)]
    assert "take" in [a["id"] for a in resolver.available_actions("item:1", local_poses=near)]
    assert "enter" in [a["id"] for a in resolver.available_actions("entrance:1", local_poses=near)]
    # Distant → observe only.
    far = {"wizard": [0.0, 0.0], "person:1": [20.0, 20.0]}
    assert [a["id"] for a in resolver.available_actions("person:1", local_poses=far)] == ["observe"]


def test_observation_learns_without_leaking_prior_name() -> None:
    state = _world()
    resolver = SemanticResolver(state)
    before = resolver.label("person:1")
    assert before == "Person"
    reveal(state, "person:1", KnowledgeFact("person:1", "met", role="worker"), role="worker")
    state.knowledge["person:1"]["name"] = "Ada"
    assert resolver.label("person:1") == "Ada"
