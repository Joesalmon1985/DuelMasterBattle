"""G05 full-board LocalArea projection and Travel traversal."""

from __future__ import annotations

from collections import deque

from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.world.overworld_export import export_overworld_area
from sim.dmb.world.prehistoric_world import board_summary
from sim.dmb.world.projection import BASE_SIZE, LocalProjectionService


def test_prehistoric_board_topology() -> None:
    sim = load_fixture("FX-VILLAGE", seed=507)
    summary = board_summary(sim)
    assert summary["hexes"] == 19
    assert summary["nodes"] == 54
    assert summary["edges"] == 72
    assert len(summary["settlements"]) >= 2
    assert summary["start_node_id"]
    # G05 narrative: simple boulder quest (not the archived shortage scenario).
    assert sim.state.board.get("g05", {}).get("quest_enabled")
    assert (sim.state.board.get("g05") or {}).get("boulder_quest", {}).get("boulder_id") in {
        "rockfall:1",
        "boulder:1",
    } or (sim.state.board.get("g05") or {}).get("boulder_quest", {}).get("rockfall_id") == "rockfall:1"
    assert "quest.factory_shortage" not in (sim.state.quests or {})
    assert "cube:demon" not in ((sim.state.hazards or {}).get("catastrophe") or {}).get("cubes", {}) or not (
        ((sim.state.hazards or {}).get("catastrophe") or {}).get("cubes") or {}
    ).get("cube:demon", {}).get("active")


def test_all_nodes_same_local_area_size_and_exits() -> None:
    sim = load_fixture("FX-VILLAGE", seed=507)
    proj = LocalProjectionService(sim.state)
    topo = sim.state.board.get("topology") or {}
    from sim.dmb.world.board import HexBoard

    board = HexBoard.from_dict(topo)
    for nid in board.nodes:
        nid = str(nid)
        view = proj.project_node(nid)
        assert view["width"] == BASE_SIZE
        assert view["height"] == BASE_SIZE
        neighbours = set(board.adjacent_nodes(nid))
        exit_targets = {str(e.get("to_node") or e.get("to")) for e in view["exits"]}
        assert neighbours == exit_targets
        assert view.get("geography") is not None
        # Spawn / centre walkable
        cx, cy = view["centre"]
        assert 0 <= cx < BASE_SIZE and 0 <= cy < BASE_SIZE
        # No exit/building ID collisions
        ids = [e["id"] for e in view["exits"]]
        assert len(ids) == len(set(ids))
        bids = [b["id"] for b in view["buildings"]]
        assert len(bids) == len(set(bids))


def test_roads_vs_trails_agree_at_endpoints() -> None:
    sim = load_fixture("FX-VILLAGE", seed=507)
    proj = LocalProjectionService(sim.state)
    topo = sim.state.board.get("topology") or {}
    from sim.dmb.world.board import HexBoard

    board = HexBoard.from_dict(topo)
    for nid in board.nodes:
        nid = str(nid)
        view = proj.project_node(nid)
        for exit_rec in view["exits"]:
            other = str(exit_rec.get("to_node"))
            passage = str(exit_rec.get("passage"))
            other_view = proj.project_node(other)
            reverse = next(e for e in other_view["exits"] if str(e.get("to_node")) == nid)
            assert reverse.get("passage") == passage


def test_settlements_share_projector() -> None:
    sim = load_fixture("FX-VILLAGE", seed=507)
    proj = LocalProjectionService(sim.state)
    settlement_nodes = [
        str(s["node_id"])
        for s in sim.state.settlements.values()
        if not s.get("staging") and s.get("node_id")
    ]
    assert len(settlement_nodes) >= 2
    for nid in settlement_nodes:
        view = proj.project_node(nid)
        assert view["kind"] == "settlement"
        assert view["width"] == BASE_SIZE
        assert any(
            sim.state.buildings[b["id"]].get("slot_kind") == "centre" for b in view["buildings"]
        )


def test_graph_travel_reaches_all_54_nodes() -> None:
    from sim.dmb.core.world import CommandEnvelope

    sim = load_fixture("FX-VILLAGE", seed=507)
    start = str(sim.state.board["g05"]["start_node_id"])
    topo = sim.state.board.get("topology") or {}
    from sim.dmb.world.board import HexBoard

    board = HexBoard.from_dict(topo)
    proj = LocalProjectionService(sim.state)
    seen = {start}
    queue = deque([start])
    turns0 = int(sim.state.clock.get("turn") or 0)
    travels = 0
    seq = 0

    def travel(frm: str, to: str):
        nonlocal seq
        seq += 1
        return sim.dispatch(
            CommandEnvelope(
                1,
                "local",
                sim.state.world_id,
                f"travel-{seq}",
                sim.state.world_version,
                "Travel",
                {"from_node": frm, "to_node": to},
            )
        )

    while queue:
        nid = queue.popleft()
        view = proj.project_node(nid)
        # Ensure player stands on nid before walking its exits.
        if str(sim.state.player.get("node_id")) != nid:
            # Direct relocate for test harness — Travel still validates adjacency when used.
            sim.state.player["node_id"] = nid
        for exit_rec in view["exits"]:
            dest = str(exit_rec.get("to_node"))
            if dest in seen:
                continue
            if str(sim.state.player.get("node_id")) != nid:
                sim.state.player["node_id"] = nid
            from sim.dmb.world.boulder_quest import rockfall_blocks_travel, complete_move

            if rockfall_blocks_travel(sim.state, nid, dest):
                complete_move(sim.state)
            r = travel(nid, dest)
            assert r.status == "ACCEPTED", (nid, dest, r)
            travels += 1
            assert str(sim.state.player.get("node_id")) == dest
            seen.add(dest)
            queue.append(dest)
            back = travel(dest, nid)
            assert back.status == "ACCEPTED", (dest, nid, back)
            assert str(sim.state.player.get("node_id")) == nid
    assert len(seen) == 54
    assert travels >= 53
    assert int(sim.state.clock.get("turn") or 0) > turns0


def test_export_any_node_same_size() -> None:
    sim = load_fixture("FX-VILLAGE", seed=507)
    start = str(sim.state.board["g05"]["start_node_id"])
    area = export_overworld_area(sim.state, start)
    assert area["width"] == BASE_SIZE
    assert area["height"] == BASE_SIZE
    assert area.get("quest_id") in {"", None}
    # Wilderness neighbour
    dest = next(iter((sim.state.board["nodes"][start].get("exits") or {}).keys()))
    sim.state.player["node_id"] = dest
    area2 = export_overworld_area(sim.state, dest)
    assert area2["width"] == BASE_SIZE
    assert area2["height"] == BASE_SIZE
