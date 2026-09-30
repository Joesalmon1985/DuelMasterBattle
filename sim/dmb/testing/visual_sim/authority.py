"""Layer 1 — authoritative WorldState observation (read-only)."""

from __future__ import annotations

from typing import Any

from sim.dmb.core.world import WorldSim


def observe_authority(sim: WorldSim) -> dict[str, Any]:
    """Snapshot kernel-relevant authoritative fields from the live WorldSim.

    Never builds expectations. Does not mutate state.
    """
    state = sim.state
    player = dict(state.player or {})
    formations = {
        fid: {
            "id": fid,
            "faction_id": f.get("faction_id"),
            "node_id": f.get("node_id"),
            "unit_ids": list(f.get("unit_ids") or f.get("members") or []),
            "status": f.get("status"),
            "objective": f.get("objective"),
        }
        for fid, f in (state.formations or {}).items()
    }
    units = {
        uid: {
            "id": uid,
            "faction_id": u.get("faction_id"),
            "person_id": u.get("person_id"),
            "node_id": u.get("node_id"),
            "formation_id": u.get("formation_id"),
            "archetype": u.get("archetype"),
            "hp": u.get("hp"),
            "alive": u.get("alive", True),
        }
        for uid, u in (state.units or {}).items()
    }
    orders = {
        oid: {
            "id": oid,
            "faction_id": o.get("faction_id"),
            "action": o.get("action"),
            "status": o.get("status"),
            "target_node": o.get("target_node"),
            "target_edge": o.get("target_edge"),
            "target_building": o.get("target_building"),
            "required_goods": dict(o.get("required_goods") or {}),
            "delivered": dict(o.get("delivered") or {}),
            "completion_receipt": o.get("completion_receipt"),
        }
        for oid, o in (state.orders or {}).items()
    }
    buildings = {
        bid: {
            "id": bid,
            "node_id": b.get("node_id"),
            "faction_id": b.get("faction_id"),
            "slot_kind": b.get("slot_kind"),
            "active": b.get("active", True),
            "status": b.get("status"),
            "settlement_id": b.get("settlement_id"),
        }
        for bid, b in (state.buildings or {}).items()
    }
    battles = {
        bid: {
            "id": bid,
            "node_id": b.get("node_id"),
            "state": b.get("state"),
            "participants": b.get("participants") or b.get("formation_ids") or b.get("sides"),
            "outcome": b.get("outcome") or b.get("result"),
        }
        for bid, b in (state.battles or {}).items()
    }
    roads = {
        rid: {"id": rid, "edge": r.get("edge") or r.get("nodes"), "faction_id": r.get("faction_id")}
        for rid, r in (state.roads or {}).items()
    }
    clock = dict(state.clock or {}) if isinstance(state.clock, dict) else {"value": state.clock}
    return {
        "layer": "authority",
        "world_id": state.world_id,
        "world_version": state.world_version,
        "rng": list(state.rng) if isinstance(state.rng, (list, tuple)) else state.rng,
        "player_node_id": player.get("node_id"),
        "player": player,
        "clock": clock,
        "counts": {
            "formations": len(formations),
            "units": len(units),
            "orders": len(orders),
            "buildings": len(buildings),
            "battles": len(battles),
            "roads": len(roads),
        },
        "formations": formations,
        "units": units,
        "orders": orders,
        "buildings": buildings,
        "battles": battles,
        "roads": roads,
        "research_keys": sorted((state.research or {}).keys()) if isinstance(state.research, dict) else [],
        "tech_draft_keys": sorted((state.tech_draft or {}).keys()) if isinstance(state.tech_draft, dict) else [],
        "diplomacy_keys": sorted((state.diplomacy or {}).keys()) if isinstance(state.diplomacy, dict) else [],
    }
