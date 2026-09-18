"""T065 unrestricted local destruction magic."""

from __future__ import annotations

from sim.dmb.construction.buildings import BuildingService
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.military.units import MilitaryService
from sim.dmb.player.magic import MagicService


def _world() -> WorldState:
    state = WorldState(world_id=WorldId("world:t065"))
    state.player["node_id"] = "n1"
    state.player["id"] = "wizard"
    return state


def test_any_allegiance_ordinary_targets() -> None:
    state = _world()
    mil = MilitaryService(state)
    magic = MagicService(state)
    friend = mil.spawn("unit.ancient.line", home_node_id="n1", faction_id="ally", era="prehistoric", factory_id="f")
    foe = mil.spawn("unit.ancient.line", home_node_id="n1", faction_id="enemy", era="prehistoric", factory_id="f")
    state.people["p1"] = {"id": "p1", "node_id": "n1", "alive": True, "role": "worker", "faction_id": "neutral"}
    state.carts["c1"] = {"id": "c1", "current_node": "n1", "alive": True, "cargo": {"ore": 3}, "faction_id": "enemy"}
    bsvc = BuildingService(state)
    # Minimal building record without definition file dependency.
    state.buildings["b1"] = {
        "id": "b1",
        "node_id": "n1",
        "status": "active",
        "health": 100,
        "max_health": 100,
        "definition_id": "building.factory",
        "faction_id": "ally",
    }
    for tid in (friend["id"], foe["id"], "p1", "c1"):
        out = magic.destroy(tid, command_id=f"cmd:{tid}")
        assert out["status"] in {"destroyed", "already_destroyed"}, out
    # Building via effect path using BuildingService.destroy
    out_b = magic.destroy("b1", command_id="cmd:b1")
    assert out_b["status"] in {"destroyed", "already_destroyed"} or out_b["result"]["status"] in {
        "destroyed",
        "idempotent",
    }
    assert state.units[friend["id"]]["alive"] is False
    assert state.carts["c1"]["cargo"] == {}
    assert state.tombstones["c1"]["lost_cargo"]["ore"] == 3


def test_remote_group_self_rival_reject() -> None:
    state = _world()
    mil = MilitaryService(state)
    magic = MagicService(state)
    remote = mil.spawn("unit.ancient.line", home_node_id="n9", faction_id="x", era="prehistoric", factory_id="f")
    assert magic.destroy(remote["id"])["status"] == "rejected"
    group = magic.destroy("group:army")
    assert group["status"] == "rejected"
    assert group.get("reason") == "group_target" or (group.get("validation") or {}).get("reason") == "group_target"
    assert magic.destroy("wizard")["status"] == "rejected"
    assert magic.destroy("rival:bob")["status"] == "rejected"


def test_idempotent_repeat_and_wizard_immune_path() -> None:
    state = _world()
    mil = MilitaryService(state)
    magic = MagicService(state)
    u = mil.spawn("unit.ancient.skirmisher", home_node_id="n1", faction_id="x", era="prehistoric", factory_id="f")
    first = magic.destroy(u["id"], command_id="cmd:same")
    second = magic.destroy(u["id"], command_id="cmd:same")
    assert first["status"] == "destroyed"
    assert second["status"] in {"idempotent", "destroyed"}
    assert second.get("result", {}).get("status") in {"idempotent", "already_destroyed", "destroyed"}
    # Wizard has no faction-combat damage path — units never target wizard id.
    from sim.dmb.military.math import choose_target

    assert (
        choose_target(
            {"id": "a", "faction_id": "x", "alive": True, "position": [0, 0], "range_tiles": 5},
            [{"id": "wizard", "faction_id": "player", "alive": True, "position": [1, 0], "current_health": 1, "is_wizard": True}],
        )
        is None
    )
