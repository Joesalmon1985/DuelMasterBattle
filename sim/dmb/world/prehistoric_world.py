"""Full Prehistoric board world for G05 exploration + simple boulder quest.

Generates the authoritative 19-hex / 54-node board, applies normal C04 setup,
installs settlement industry from catalogue recipes, and wires topology Travel
for every adjacency. Local areas are projected lazily via LocalProjectionService.
Installs one persistent blocked-exit boulder quest at the starting settlement.
"""

from __future__ import annotations

from typing import Any

from sim.dmb.core.world import WorldSim, bootstrap_world
from sim.dmb.player.visits import VisitService
from sim.dmb.world.generation import BoardBuilder
from sim.dmb.world.industry_bootstrap import bootstrap_all_settlement_industry
from sim.dmb.world.setup import WorldSetupService
from sim.dmb.world.fx_village_world import wire_topology_travel


def _node_has_south_exit(state, node_id: str) -> bool:
    node = ((state.board or {}).get("nodes") or {}).get(node_id) or {}
    exits = node.get("exits") or {}
    if not isinstance(exits, dict):
        return False
    return any(str((link or {}).get("direction") or "") == "south" for link in exits.values())


def _settlement_for_node(state, node_id: str) -> dict:
    return next(
        s
        for s in state.settlements.values()
        if s.get("node_id") == node_id and not s.get("staging")
    )


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
    settlement = _settlement_for_node(state, best.node_id)
    return str(best.node_id), str(settlement["id"]), str(best.faction_id)


def _node_has_any_exit(state, node_id: str) -> bool:
    node = ((state.board or {}).get("nodes") or {}).get(node_id) or {}
    exits = node.get("exits") or {}
    return isinstance(exits, dict) and bool(exits)


def _ensure_boulder_start(plan, state, start_node: str, settlement_id: str, faction_id: str) -> tuple[str, str, str]:
    """Prefer a south exit for presentation; otherwise any core with a connected exit."""
    if _node_has_south_exit(state, start_node):
        return start_node, settlement_id, faction_id

    def _rank_core(core) -> tuple[int, str]:
        nid = str(core.node_id)
        terrains = {str(plan.hex_terrain[h]) for h in plan.board.touching_hexes(nid)}
        score = len(terrains) + (2 if "woodland" in terrains else 0)
        if _node_has_south_exit(state, nid):
            score += 100
        elif _node_has_any_exit(state, nid):
            score += 10
        return (score, nid)

    ranked = sorted(plan.cores, key=_rank_core, reverse=True)
    for core in ranked:
        nid = str(core.node_id)
        if not _node_has_any_exit(state, nid):
            continue
        settlement = _settlement_for_node(state, nid)
        return nid, str(settlement["id"]), str(core.faction_id)
    return start_node, settlement_id, faction_id


def _clear_settlement_catastrophe_cubes(state, plan) -> None:
    """Deactivate catastrophe cubes on hexes touched by operational settlements."""
    touching: set[str] = set()
    for settlement in state.settlements.values():
        if settlement.get("staging") or not settlement.get("operational", True):
            continue
        node_id = str(settlement.get("node_id") or "")
        if not node_id:
            continue
        touching.update(str(h) for h in plan.board.touching_hexes(node_id))
    if not touching:
        return
    cubes = ((state.hazards or {}).get("catastrophe") or {}).get("cubes") or {}
    board_cubes = state.board.setdefault("hazard_cubes", {})
    for cid, cube in list(cubes.items()):
        if str(cube.get("hex_id") or "") in touching:
            cube["active"] = False
            if cid in board_cubes:
                board_cubes[cid]["active"] = False
    state.board["hazard_hexes"] = [
        str(h) for h in (state.board.get("hazard_hexes") or []) if str(h) not in touching
    ]


def load_prehistoric_world(seed: int = 507) -> WorldSim:
    """Authoritative Prehistoric world — full board + one simple boulder quest."""
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

    # Keep distant catastrophe pressure, but never start with cubes on settlement
    # primary hexes — matches FX-VILLAGE and unblocks normal industry bootstrap.
    _clear_settlement_catastrophe_cubes(state, plan)

    bootstrap_all_settlement_industry(sim)

    start_node, settlement_id, faction_id = _pick_start_settlement(plan, state)
    wire_topology_travel(state, plan.board, home_node_id=start_node)
    start_node, settlement_id, faction_id = _ensure_boulder_start(
        plan, state, start_node, settlement_id, faction_id
    )
    if str((state.board.get("nodes") or {}).get(start_node, {}).get("id") or "") == start_node:
        # Re-label home if we re-homed after the initial wire pass.
        home = state.board["nodes"][start_node]
        home.setdefault("label", "Settlement")
        home.setdefault("area_id", "area.village")

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
    # Autonomous factions sit the World Turn roster (player is observer/wizard).
    faction_ids = sorted(
        {
            str(s.get("faction_id"))
            for s in state.settlements.values()
            if not s.get("staging") and s.get("faction_id")
        }
    )
    state.clock["scheduled_faction_ids"] = faction_ids or ["faction:1", "faction:2"]
    state.clock["active_faction_id"] = state.clock["scheduled_faction_ids"][0]
    state.clock["completed_seats"] = []
    state.clock["round_complete"] = False
    state.clock.setdefault("era", "prehistoric")
    state.clock.setdefault("era_id", "prehistoric")
    from sim.dmb.technology.draft import DraftService

    DraftService(state).deal("prehistoric", list(state.clock["scheduled_faction_ids"]))
    # Assign saved trained specialist policies when artifacts exist (P5 / R10).
    from sim.dmb.ai.policy import PolicyService

    trained = ["policy-im-build", "policy-im-trade", "policy-im-war"]
    pol = PolicyService(state)
    for idx, fid in enumerate(state.clock["scheduled_faction_ids"]):
        pol.assign_brain(fid, trained[idx % len(trained)])
    state.board["g05"] = {
        "mode": "full_prehistoric_world_boulder_quest",
        "quest_enabled": True,
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
        "mode": "boulder_quest",
        "quest_enabled": True,
        "node_id": start_node,
        "settlement_id": settlement_id,
        "faction_id": faction_id,
        "quest_id": None,
        "cause_id": None,
        "name": "Prehistoric World",
    }

    from sim.dmb.world.boulder_quest import install_boulder_quest

    install_boulder_quest(state, start_node_id=start_node)

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
