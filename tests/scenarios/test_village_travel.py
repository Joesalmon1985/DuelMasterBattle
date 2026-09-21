"""G05 topology travel: FX-VILLAGE exits are real adjacent nodes."""

from __future__ import annotations

from sim.dmb.core.world import CommandEnvelope
from sim.dmb.testing.fixtures import load_fixture


def test_fx_village_topology_travel_round_trip() -> None:
    sim = load_fixture("FX-VILLAGE", seed=507)
    home = "node:35"
    node = sim.state.board["nodes"][home]
    exits = node.get("exits") or {}
    assert isinstance(exits, dict) and exits, "home settlement must expose Travel exits"
    dest = next(iter(exits))
    assert dest in sim.state.board["nodes"]
    assert dest in (sim.state.board.get("topology") or {}).get("adjacency", {}).get(home, [])
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
    mara = sim.state.board["fx_village"]["mara_id"]
    factory = sim.state.board["fx_village"]["factory_id"]
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
    assert sim.state.board["fx_village"]["mara_id"] == mara
    assert sim.state.board["fx_village"]["factory_id"] == factory


def test_player_building_observation_differs_for_quiet_factory() -> None:
    from sim.dmb.industry.projection import IndustryProjection

    sim = load_fixture("FX-VILLAGE-QUEST", seed=507)
    fx = sim.state.board["fx_village"]
    proj = IndustryProjection(sim.state)
    quiet = proj.player_building_observation(fx["factory_id"])
    working = proj.player_building_observation(fx["factory_work_id"])
    assert quiet["observe_far"]
    assert working["observe_far"]
    assert quiet["observe_far"] != working["observe_far"]
    assert "quiet" in quiet["observe_far"].lower() or "waiting" in quiet["observe_far"].lower() or "short" in quiet["observe_far"].lower()
