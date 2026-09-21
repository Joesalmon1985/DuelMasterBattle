"""G05 topology travel on the full Prehistoric board."""

from __future__ import annotations

from sim.dmb.core.world import CommandEnvelope
from sim.dmb.testing.fixtures import load_fixture


def test_fx_village_topology_travel_round_trip() -> None:
    sim = load_fixture("FX-VILLAGE", seed=507)
    home = str(sim.state.board["g05"]["start_node_id"])
    node = sim.state.board["nodes"][home]
    exits = node.get("exits") or {}
    assert isinstance(exits, dict) and exits, "home settlement must expose Travel exits"
    dest = next(iter(exits))
    assert dest in sim.state.board["nodes"]
    turn0 = int(sim.state.clock.get("turn") or 0)
    r1 = sim.dispatch(
        CommandEnvelope(
            1,
            "local",
            sim.state.world_id,
            "travel-out",
            sim.state.world_version,
            "Travel",
            {"from_node": home, "to_node": dest},
        )
    )
    assert r1.status == "ACCEPTED"
    assert sim.state.player["node_id"] == dest
    assert int(sim.state.clock["turn"]) == turn0 + 1
    # IDs stable
    settlement_id = sim.state.board["g05"]["start_settlement_id"]
    r2 = sim.dispatch(
        CommandEnvelope(
            1,
            "local",
            sim.state.world_id,
            "travel-back",
            sim.state.world_version,
            "Travel",
            {"from_node": dest, "to_node": home},
        )
    )
    assert r2.status == "ACCEPTED"
    assert sim.state.player["node_id"] == home
    assert sim.state.board["g05"]["start_settlement_id"] == settlement_id


def test_player_building_observation_for_settlement_factory() -> None:
    from sim.dmb.industry.projection import IndustryProjection

    sim = load_fixture("FX-VILLAGE", seed=507)
    home = str(sim.state.board["g05"]["start_node_id"])
    factories = [
        b
        for b in sim.state.buildings.values()
        if b.get("node_id") == home and str(b.get("slot_kind")) == "factory" and b.get("active", True)
    ]
    assert factories
    proj = IndustryProjection(sim.state)
    obs = proj.player_building_observation(str(factories[0]["id"]))
    assert obs["observe_far"]
    assert "building:" not in obs.get("label", "")
