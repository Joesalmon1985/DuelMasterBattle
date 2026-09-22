"""FX-ERA near-threshold Prehistoric checkpoint builder (T106).

Builds a legitimate production-backed board from FX-VILLAGE (seed 507 home
settlement / Rockfall), expands through ConstructionService road+settlement
orders (warehouse stock credited), and leaves one ready settlement order so
Wait → commit_delivered reaches 10 VP and triggers EraService.
"""

from __future__ import annotations

from typing import Any

from sim.dmb.construction.orders import ConstructionService
from sim.dmb.construction.placement import PlacementRules
from sim.dmb.construction.scoring import ScoreService
from sim.dmb.core.world import WorldSim
from sim.dmb.logistics.stock import StockLedger
from sim.dmb.world.board import HexBoard
from sim.dmb.world.boulder_quest import QUEST_INSTANCE_ID, get_rockfall

# Manual checkpoint uses G05 continuity seed (Rockfall @ node:35).
FX_ERA_SEED = 507
SETTLEMENT_GOODS = {"timber": 1, "brick": 1, "wool": 1, "grain": 1}
ROAD_GOODS = {"timber": 1, "brick": 1}


def _warehouse_store(settlement: dict[str, Any]) -> str:
    wh = str(settlement.get("warehouse_id") or "")
    return f"store:{wh}" if wh and not wh.startswith("store:") else wh


def _ensure_goods(ledger: StockLedger, store_id: str, goods: dict[str, int]) -> None:
    for good, qty in goods.items():
        have = ledger.available(store_id, good)
        if have < qty:
            ledger.credit(store_id, good, qty - have)


def _home_settlement(state: Any, faction_id: str) -> dict[str, Any]:
    preferred_node = str((state.player or {}).get("node_id") or "")
    homes = [
        s
        for s in state.settlements.values()
        if s.get("faction_id") == faction_id
        and s.get("warehouse_id")
        and not s.get("ruin_only")
    ]
    for s in homes:
        if s.get("node_id") == preferred_node:
            return s
    if not homes:
        raise RuntimeError(f"no warehouse settlement for {faction_id}")
    return homes[0]


def _expand_to_vp(
    state: Any,
    *,
    faction_id: str,
    target_vp: int,
    provenance: list[dict[str, Any]],
) -> None:
    """Legally road-expand and found settlements until target VP."""
    ledger = StockLedger(state)
    construction = ConstructionService(state, ledger=ledger)
    placement = PlacementRules(state)
    board = construction.placement._board() if construction.placement else HexBoard.from_dict(state.board["topology"])
    home = _home_settlement(state, faction_id)
    store = _warehouse_store(home)
    scores = ScoreService(state)
    safety = 0
    while scores.score(faction_id) < target_vp and safety < 80:
        safety += 1
        # Prefer an already-legal settle site.
        endpoints = placement._owned_road_endpoints(faction_id)
        settled = False
        for node in sorted(endpoints):
            ok, reason = placement.can_settle(faction_id, node)
            if not ok:
                continue
            _ensure_goods(ledger, store, SETTLEMENT_GOODS)
            order = construction.reserve_order(
                "settlement",
                faction_id=faction_id,
                store_id=store,
                target_node=node,
            )
            if order.get("status") != "ready":
                provenance.append(
                    {"action": "settlement_blocked", "node_id": node, "reason": order.get("reason")}
                )
                continue
            committed = construction.commit_delivered(str(order["id"]))
            provenance.append(
                {
                    "action": "settlement_founded",
                    "faction_id": faction_id,
                    "node_id": node,
                    "order_id": order.get("id"),
                    "settlement_id": ((committed.get("completion_receipt") or {}).get("result") or {}).get(
                        "settlement_id"
                    ),
                    "vp_after": scores.score(faction_id),
                }
            )
            settled = True
            break
        if settled:
            continue
        # Build a road from an owned endpoint into an empty neighbour.
        built_road = False
        for node in sorted(endpoints):
            for neigh in board.adjacent_nodes(node):
                ok, reason = placement.can_road(faction_id, node, neigh)
                if not ok:
                    continue
                _ensure_goods(ledger, store, ROAD_GOODS)
                order = construction.reserve_order(
                    "road",
                    faction_id=faction_id,
                    store_id=store,
                    target_edge=(node, neigh),
                )
                if order.get("status") != "ready":
                    continue
                construction.commit_delivered(str(order["id"]))
                provenance.append(
                    {
                        "action": "road_built",
                        "faction_id": faction_id,
                        "edge": [node, neigh],
                        "order_id": order.get("id"),
                    }
                )
                built_road = True
                break
            if built_road:
                break
        if not built_road:
            provenance.append({"action": "expand_stalled", "faction_id": faction_id, "vp": scores.score(faction_id)})
            break


def stage_ready_founding_order(
    state: Any,
    *,
    faction_id: str,
    provenance: list[dict[str, Any]],
) -> str | None:
    ledger = StockLedger(state)
    construction = ConstructionService(state, ledger=ledger)
    placement = PlacementRules(state)
    board = HexBoard.from_dict(state.board["topology"])
    home = _home_settlement(state, faction_id)
    store = _warehouse_store(home)
    # Ensure at least one legal settle site (may need one more road).
    for _ in range(12):
        endpoints = placement._owned_road_endpoints(faction_id)
        for node in sorted(endpoints):
            ok, _reason = placement.can_settle(faction_id, node)
            if not ok:
                continue
            _ensure_goods(ledger, store, SETTLEMENT_GOODS)
            order = construction.reserve_order(
                "settlement",
                faction_id=faction_id,
                store_id=store,
                target_node=node,
            )
            if order.get("status") == "ready":
                provenance.append(
                    {
                        "action": "ready_settlement_staged",
                        "faction_id": faction_id,
                        "node_id": node,
                        "order_id": order.get("id"),
                        "vp_before_commit": ScoreService(state).score(faction_id),
                    }
                )
                fx = state.board.setdefault("fx_era", {})
                fx["scoring_order_id"] = order.get("id")
                fx["scoring_node_id"] = node
                return str(order.get("id"))
        # Extend one road then retry.
        extended = False
        for node in sorted(endpoints):
            for neigh in board.adjacent_nodes(node):
                ok, _reason = placement.can_road(faction_id, node, neigh)
                if not ok:
                    continue
                _ensure_goods(ledger, store, ROAD_GOODS)
                order = construction.reserve_order(
                    "road",
                    faction_id=faction_id,
                    store_id=store,
                    target_edge=(node, neigh),
                )
                if order.get("status") != "ready":
                    continue
                construction.commit_delivered(str(order["id"]))
                provenance.append({"action": "road_built_for_ready", "edge": [node, neigh]})
                extended = True
                break
            if extended:
                break
        if not extended:
            break
    return None


def build_fx_era(sim: WorldSim, *, seed: int = FX_ERA_SEED) -> WorldSim:
    state = sim.state
    provenance: list[dict[str, Any]] = [
        {"action": "base_fixture", "name": "FX-VILLAGE/prehistoric", "seed": seed}
    ]

    winner = str((state.player or {}).get("faction_id") or "faction:2")
    loser = next((fid for fid in sorted(state.factions) if fid != winner), "faction:1")

    _expand_to_vp(state, faction_id=loser, target_vp=5, provenance=provenance)
    _expand_to_vp(state, faction_id=winner, target_vp=9, provenance=provenance)
    order_id = stage_ready_founding_order(state, faction_id=winner, provenance=provenance)

    state.clock["era"] = "prehistoric"
    state.board["era_id"] = "prehistoric"
    state.clock["started_faction_ids"] = sorted(state.factions)
    state.clock["sole_era_starter"] = False
    state.clock["scheduled_faction_ids"] = sorted(state.factions)
    state.clock["active_faction_id"] = winner

    knowledge = state.knowledge
    knowledge[winner] = dict(knowledge.get(winner) or {"known": True})
    for pid, person in state.people.items():
        if person.get("node_id") == "node:35":
            knowledge[pid] = dict(
                knowledge.get(pid) or {"known": True, "name": person.get("display_name")}
            )

    scores = ScoreService(state).scores()
    rock = get_rockfall(state)
    core_settlement = next(
        (
            s
            for s in state.settlements.values()
            if s.get("node_id") == "node:35" and s.get("faction_id") == winner
        ),
        None,
    )
    secondary = next(
        (
            s
            for s in state.settlements.values()
            if s.get("faction_id") == winner
            and s.get("node_id") != "node:35"
            and not s.get("ruin_only")
        ),
        None,
    )

    # Expected post-transition: player start becomes a Historic core; later founded
    # winner sites without top ranking remain Prehistoric legacy.
    expansion_legacy = next(
        (
            s
            for s in state.settlements.values()
            if s.get("faction_id") == winner
            and s.get("node_id") not in {"node:35", "node:27"}
            and not s.get("ruin_only")
        ),
        secondary,
    )

    state.board["fx_era"] = {
        "seed": seed,
        "fixture": "FX-ERA",
        "winner_faction_id": winner,
        "loser_faction_id": loser,
        "scores": scores,
        "scoring_order_id": order_id,
        "scoring_action": "Wait → commit ready settlement order",
        "expected_core_node_id": "node:35",
        "expected_core_settlement_id": (core_settlement or {}).get("id"),
        "expected_legacy_settlement_id": (expansion_legacy or {}).get("id"),
        "expected_legacy_node_id": (expansion_legacy or {}).get("node_id"),
        "known_person_ids": sorted(
            pid
            for pid, p in state.people.items()
            if p.get("node_id") == "node:35" and p.get("alive", True)
        )[:6],
        "rockfall_status": (rock or {}).get("status"),
        "quest_id": QUEST_INSTANCE_ID if QUEST_INSTANCE_ID in state.quests else None,
        "provenance": provenance,
        "checkpoint": "near_10_vp_ready_order",
        "collapse_expectation": f"{loser} collapses to ruins; {winner} survives",
    }
    g05 = state.board.setdefault("g05", {})
    g05["mode"] = "fx_era"
    g05["fixture"] = "FX-ERA"
    g05["seed"] = seed

    if scores.get(winner, 0) != 9:
        raise RuntimeError(f"FX-ERA winner VP expected 9, got {scores}")
    if not order_id:
        raise RuntimeError("FX-ERA ready scoring order missing")
    return sim


def load_fx_era(seed: int = FX_ERA_SEED) -> WorldSim:
    from sim.dmb.world.prehistoric_world import load_prehistoric_world

    sim = load_prehistoric_world(seed=seed)
    return build_fx_era(sim, seed=seed)
