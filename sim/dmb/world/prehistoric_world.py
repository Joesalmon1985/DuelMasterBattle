"""Full Prehistoric board world for G05 exploration (no active quests).

Generates the authoritative 19-hex / 54-node board, applies normal C04 setup,
installs settlement industry from catalogue recipes, and wires topology Travel
for every adjacency. Local areas are projected lazily via LocalProjectionService.
"""

from __future__ import annotations

from typing import Any

from sim.dmb.core.world import WorldSim, bootstrap_world
from sim.dmb.player.visits import VisitService
from sim.dmb.world.generation import BoardBuilder
from sim.dmb.world.industry_bootstrap import bootstrap_all_settlement_industry
from sim.dmb.world.setup import WorldSetupService
from sim.dmb.world.fx_village_world import wire_topology_travel


def _pick_start_settlement(plan, state) -> tuple[str, str, str]:
    """Prefer a multi-terrain core (richer local landscape); fall back to first core."""
    best = None
    best_score = -1
    for core in plan.cores:
        terrains = {str(plan.hex_terrain[h]) for h in plan.board.touching_hexes(core.node_id)}
        score = len(terrains)
        if "woodland" in terrains:
            score += 2
        if score > best_score:
            best_score = score
            best = core
    assert best is not None
    settlement = next(
        s
        for s in state.settlements.values()
        if s.get("node_id") == best.node_id and not s.get("staging")
    )
    return str(best.node_id), str(settlement["id"]), str(best.faction_id)


def load_prehistoric_world(seed: int = 507) -> WorldSim:
    """Authoritative Prehistoric world — entire board exists; no quest content."""
    sim = bootstrap_world(world_id="world:prehistoric", seed=seed)
    state = sim.state
    plan = BoardBuilder.generate(seed, 2)
    WorldSetupService(state).apply(plan)

    # Label settlements with distinct player-facing names.
    for settlement in state.settlements.values():
        if settlement.get("staging"):
            continue
        idx = int(settlement.get("core_index") or 0)
        faction = str(settlement.get("faction_id") or "")
        faction_n = faction.split(":")[-1] if ":" in faction else faction
        settlement["label"] = settlement.get("label") or f"Settlement {faction_n}-{idx + 1}"
        node_id = str(settlement.get("node_id") or "")
        if node_id:
            rec = state.board.setdefault("nodes", {}).setdefault(node_id, {"id": node_id})
            rec["label"] = settlement["label"]
            rec["settlement_id"] = settlement["id"]
            rec["faction_id"] = faction
            rec["area_id"] = f"area.{node_id.replace(':', '_')}"

    bootstrap_all_settlement_industry(sim)

    start_node, settlement_id, faction_id = _pick_start_settlement(plan, state)
    wire_topology_travel(state, plan.board, home_node_id=start_node)

    # Ensure every topology node has a board record + wilderness label.
    for nid in plan.board.nodes:
        nid = str(nid)
        rec = state.board.setdefault("nodes", {}).setdefault(nid, {"id": nid})
        rec.setdefault("id", nid)
        if not rec.get("label"):
            rec["label"] = "Wilderness"
        rec.setdefault("area_id", f"area.{nid.replace(':', '_')}")

    state.player = {
        "node_id": start_node,
        "area_id": str((state.board.get("nodes") or {}).get(start_node, {}).get("area_id") or "area.village"),
        "position": [24.0, 32.0],
        "facing": "up",
        "faction_id": faction_id,
    }
    VisitService(state).arrive(start_node, "travel", int(state.clock.get("turn") or 0))

    # Point IndustryProjection at the starting settlement's industry view.
    by_node = state.board.get("fx_industry_by_node") or {}
    if start_node in by_node:
        state.board["fx_industry"] = dict(by_node[start_node])

    state.board["era_id"] = "ancient"
    state.board["g05"] = {
        "mode": "full_prehistoric_world",
        "quest_enabled": False,
        "seed": seed,
        "start_node_id": start_node,
        "start_settlement_id": settlement_id,
        "start_faction_id": faction_id,
        "topology_hexes": len(plan.board.hexes),
        "topology_nodes": len(plan.board.nodes),
        "topology_edges": len(plan.board.edges),
    }
    # Compatibility shim for older read sites that still peek fx_village metadata.
    state.board["fx_village"] = {
        "seed": seed,
        "mode": "baseline",
        "quest_enabled": False,
        "node_id": start_node,
        "settlement_id": settlement_id,
        "faction_id": faction_id,
        "quest_id": None,
        "cause_id": None,
        "name": "Prehistoric World",
    }

    # Advance industry once so rates exist for the home settlement.
    try:
        sim.industry.advance_quanta(1)
    except Exception:
        pass
    return sim


def board_summary(sim: WorldSim) -> dict[str, Any]:
    """Compact summary for packets / tests."""
    state = sim.state
    board = state.board.get("topology") or {}
    settlements = [
        {
            "settlement_id": s["id"],
            "node_id": s.get("node_id"),
            "faction_id": s.get("faction_id"),
            "label": s.get("label"),
        }
        for s in state.settlements.values()
        if not s.get("staging")
    ]
    roads = [
        {"id": r["id"], "a": r.get("a"), "b": r.get("b"), "faction_id": r.get("faction_id"), "status": r.get("status")}
        for r in state.roads.values()
        if r.get("status") == "built"
    ]
    return {
        "seed": state.board.get("g05", {}).get("seed"),
        "hexes": len(board.get("hexes") or state.board.get("hex_terrain") or {}),
        "nodes": len(board.get("nodes") or state.board.get("node_hexes") or {}),
        "edges": len(board.get("edges") or []),
        "start_node_id": state.board.get("g05", {}).get("start_node_id"),
        "settlements": settlements,
        "roads": roads,
    }
