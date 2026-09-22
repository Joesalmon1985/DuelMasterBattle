"""Headless long-run harness for FX-LONG-WORLD (Wait + AdvanceGame only)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sim.dmb.core.commands import CommandEnvelope
from sim.dmb.core.world import WorldSim

MAJOR_EVENT_KINDS = (
    "ROAD_BUILT",
    "SETTLEMENT_FOUNDED",
    "CITY_UPGRADED",
    "UNIT_PRODUCED",
    "BATTLE_STARTED",
    "BATTLE_ENDED",
    "CART_DEPARTED",
    "CART_DELIVERED",
    "FORMATION_MOVED",
    "FORMATION_CREATED",
    "CASUALTY",
    "HAZARD_PLACED",
    "OUTBREAK",
)


def _env(sim: WorldSim, command_id: str, kind: str, payload: dict[str, Any]) -> CommandEnvelope:
    return CommandEnvelope(
        protocol_version=1,
        session_id="local",
        world_id=sim.state.world_id,
        command_id=command_id,
        expected_world_version=sim.state.world_version,
        kind=kind,
        payload=payload,
    )


def _built_roads(state) -> dict[str, Any]:
    return {
        rid: dict(road)
        for rid, road in (state.roads or {}).items()
        if road.get("status") == "built"
    }


def _live_settlements(state) -> dict[str, Any]:
    return {
        sid: dict(s)
        for sid, s in (state.settlements or {}).items()
        if not s.get("staging")
    }


def _active_cubes(state) -> dict[str, Any]:
    cubes = ((state.hazards or {}).get("catastrophe") or {}).get("cubes") or {}
    return {cid: dict(c) for cid, c in cubes.items() if c.get("active", True)}


def snapshot_world(state) -> dict[str, Any]:
    settlements = _live_settlements(state)
    return {
        "turn": int((state.clock or {}).get("turn") or 0),
        "game_ms": int((state.clock or {}).get("game_ms") or 0),
        "roads": sorted(_built_roads(state)),
        "settlements": sorted(settlements),
        "cities": sorted(sid for sid, s in settlements.items() if str(s.get("tier") or "") == "city"),
        "settlement_tiers": {sid: str(s.get("tier") or "settlement") for sid, s in settlements.items()},
        "units": {
            uid: {
                "status": str(u.get("status") or ""),
                "alive": bool(u.get("alive", True)),
                "definition_id": str(u.get("definition_id") or ""),
                "faction_id": str(u.get("faction_id") or ""),
                "node_id": str(u.get("node_id") or ""),
            }
            for uid, u in sorted((state.units or {}).items())
        },
        "battles": {
            bid: {
                "state": str(b.get("state") or ""),
                "node_id": str(b.get("node_id") or ""),
            }
            for bid, b in sorted((state.battles or {}).items())
        },
        "carts": {
            cid: {
                "status": str(c.get("status") or ""),
                "node": str(c.get("current_node") or c.get("node_id") or ""),
            }
            for cid, c in sorted((state.carts or {}).items())
        },
        "formations": {
            fid: {
                "node_id": str(f.get("node_id") or f.get("current_node") or ""),
                "faction_id": str(f.get("faction_id") or ""),
            }
            for fid, f in sorted((state.formations or {}).items())
        },
        "hazards": sorted(_active_cubes(state)),
    }


def diff_snapshots(before: dict[str, Any], after: dict[str, Any], *, turn: int) -> list[dict[str, Any]]:
    """Derive major long-run events from authoritative state diffs (no fakes)."""
    events: list[dict[str, Any]] = []

    for rid in set(after["roads"]) - set(before["roads"]):
        events.append({"kind": "ROAD_BUILT", "turn": turn, "road_id": rid})

    for sid in set(after["settlements"]) - set(before["settlements"]):
        events.append({"kind": "SETTLEMENT_FOUNDED", "turn": turn, "settlement_id": sid})

    for sid, tier in after["settlement_tiers"].items():
        prev = before["settlement_tiers"].get(sid)
        if prev and prev != "city" and tier == "city":
            events.append({"kind": "CITY_UPGRADED", "turn": turn, "settlement_id": sid})
        elif sid not in before["settlement_tiers"] and tier == "city":
            events.append({"kind": "CITY_UPGRADED", "turn": turn, "settlement_id": sid})

    for uid, urec in after["units"].items():
        if uid not in before["units"]:
            events.append(
                {
                    "kind": "UNIT_PRODUCED",
                    "turn": turn,
                    "unit_id": uid,
                    "definition_id": urec.get("definition_id"),
                    "faction_id": urec.get("faction_id"),
                }
            )
        else:
            prev = before["units"][uid]
            was_alive = prev.get("alive", prev.get("status") != "dead")
            now_alive = urec.get("alive", urec.get("status") != "dead")
            if was_alive and not now_alive:
                events.append({"kind": "CASUALTY", "turn": turn, "unit_id": uid})

    for fid in set(after["formations"]) - set(before["formations"]):
        events.append(
            {
                "kind": "FORMATION_CREATED",
                "turn": turn,
                "formation_id": fid,
                "node_id": (after["formations"].get(fid) or {}).get("node_id"),
                "faction_id": (after["formations"].get(fid) or {}).get("faction_id"),
            }
        )

    for bid, brec in after["battles"].items():
        prev = before["battles"].get(bid)
        cur_state = str(brec.get("state") or "")
        prev_state = str(prev.get("state") or "") if prev else ""
        active_states = {"PENDING", "ACTIVE", "OFFSCREEN", "LOCAL", "READY"}
        ended_states = {"wipe", "victory", "stalemate", "withdrawal", "ENDED", "CLOSED"}
        if prev is None or (prev_state not in active_states and cur_state in active_states):
            if cur_state in active_states:
                events.append(
                    {
                        "kind": "BATTLE_STARTED",
                        "turn": turn,
                        "battle_id": bid,
                        "node_id": brec.get("node_id"),
                    }
                )
        if prev and prev_state in active_states and cur_state in ended_states:
            events.append(
                {
                    "kind": "BATTLE_ENDED",
                    "turn": turn,
                    "battle_id": bid,
                    "node_id": brec.get("node_id"),
                    "outcome": cur_state,
                }
            )

    for cid, crec in after["carts"].items():
        prev = before["carts"].get(cid) or {}
        status = str(crec.get("status") or "")
        prev_status = str(prev.get("status") or "")
        if status in {"en_route", "assigned", "loaded"} and prev_status not in {
            "en_route",
            "assigned",
            "loaded",
        }:
            events.append({"kind": "CART_DEPARTED", "turn": turn, "cart_id": cid, "node": crec.get("node")})
        if status in {"delivered", "arrived"} and prev_status not in {"delivered", "arrived"}:
            if prev_status in {"en_route", "assigned", "loaded", "blocked"}:
                events.append(
                    {"kind": "CART_DELIVERED", "turn": turn, "cart_id": cid, "node": crec.get("node")}
                )

    for fid, frec in after["formations"].items():
        prev = before["formations"].get(fid)
        if prev and str(prev.get("node_id") or "") != str(frec.get("node_id") or ""):
            events.append(
                {
                    "kind": "FORMATION_MOVED",
                    "turn": turn,
                    "formation_id": fid,
                    "from": prev.get("node_id"),
                    "to": frec.get("node_id"),
                }
            )

    for hid in set(after["hazards"]) - set(before["hazards"]):
        events.append({"kind": "HAZARD_PLACED", "turn": turn, "cube_id": hid})

    return events


def run_long_world(
    sim: WorldSim,
    *,
    max_turns: int = 300,
    advance_game_quanta_per_wait: int = 5,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Advance via Wait + AdvanceGame only; return (report, major_events)."""
    node_id = str((sim.state.player or {}).get("node_id") or "")
    start_snap = snapshot_world(sim.state)
    events: list[dict[str, Any]] = []
    checkpoints: dict[str, dict[str, Any]] = {"turn_000_start": deepcopy(start_snap)}
    first_seen: dict[str, int] = {}
    seq = 0
    clock_seq = 0
    prev = start_snap

    for i in range(max_turns):
        seq += 1
        wait = sim.dispatch(
            _env(
                sim,
                f"long-wait-{seq}",
                "Wait",
                {"current_node": node_id, "press_id": f"long-press-{seq}"},
            )
        )
        if wait.status != "ACCEPTED":
            break

        for _ in range(max(0, int(advance_game_quanta_per_wait))):
            clock_seq += 1
            adv = sim.dispatch(
                _env(
                    sim,
                    f"long-adv-{clock_seq}",
                    "AdvanceGame",
                    {"delta_ms": 100, "clock_sequence": clock_seq},
                )
            )
            if adv.status != "ACCEPTED":
                break

        node_id = str((sim.state.player or {}).get("node_id") or node_id)
        cur = snapshot_world(sim.state)
        turn = int(cur["turn"])
        batch = diff_snapshots(prev, cur, turn=turn)
        for ev in batch:
            events.append(ev)
            kind = str(ev["kind"])
            if kind not in first_seen:
                first_seen[kind] = turn
                key = {
                    "ROAD_BUILT": "first_road_built",
                    "SETTLEMENT_FOUNDED": "first_new_settlement",
                    "UNIT_PRODUCED": "first_unit_produced",
                    "FORMATION_MOVED": "first_formation_move",
                    "BATTLE_STARTED": "first_battle_start",
                }.get(kind)
                if key and key not in checkpoints:
                    checkpoints[key] = deepcopy(cur)
        prev = cur

        if wait.interrupt:
            break

    end_snap = snapshot_world(sim.state)
    checkpoints["final_state"] = deepcopy(end_snap)

    def _count(kind: str) -> int:
        return sum(1 for e in events if e.get("kind") == kind)

    units_by_faction: dict[str, int] = {}
    for ev in events:
        if ev.get("kind") != "UNIT_PRODUCED":
            continue
        fac = str(ev.get("faction_id") or "?")
        units_by_faction[fac] = units_by_faction.get(fac, 0) + 1

    stagnation: list[str] = []
    if _count("ROAD_BUILT") == 0 and _count("SETTLEMENT_FOUNDED") == 0:
        stagnation.append("no_expansion_builds")
    if _count("UNIT_PRODUCED") == 0:
        stagnation.append("no_units_produced")
    if _count("FORMATION_MOVED") == 0:
        stagnation.append("no_formation_moves")
    if _count("BATTLE_STARTED") == 0:
        stagnation.append("no_battles")
    if _count("CART_DEPARTED") == 0 and _count("CART_DELIVERED") == 0:
        stagnation.append("no_cart_activity")

    report: dict[str, Any] = {
        "seed": (sim.state.board.get("g05") or {}).get("seed"),
        "fixture": "FX-LONG-WORLD",
        "mode": (sim.state.board.get("g05") or {}).get("mode"),
        "world_turns": int(end_snap["turn"]) - int(start_snap["turn"]),
        "max_turns": max_turns,
        "game_ms_start": start_snap["game_ms"],
        "game_ms_end": end_snap["game_ms"],
        "settlements_start": len(start_snap["settlements"]),
        "settlements_end": len(end_snap["settlements"]),
        "cities_start": len(start_snap["cities"]),
        "cities_end": len(end_snap["cities"]),
        "roads_start": len(start_snap["roads"]),
        "roads_end": len(end_snap["roads"]),
        "units_start": len(start_snap["units"]),
        "units_end": len(end_snap["units"]),
        "counts": {kind: _count(kind) for kind in MAJOR_EVENT_KINDS},
        "units_produced_by_faction": units_by_faction,
        "first_seen": first_seen,
        "stagnation": stagnation,
        "checkpoints": {k: {"turn": v.get("turn"), "roads": len(v.get("roads") or []), "settlements": len(v.get("settlements") or []), "units": len(v.get("units") or [])} for k, v in checkpoints.items()},
        "checkpoint_snapshots": checkpoints,
        "major_events": events,
    }
    return report, events


def major_event_fingerprint(events: list[dict[str, Any]]) -> list[tuple]:
    """Stable fingerprint of major outcomes for determinism checks."""
    out = []
    for ev in events:
        kind = str(ev.get("kind"))
        if kind not in MAJOR_EVENT_KINDS:
            continue
        row = [kind, int(ev.get("turn") or 0)]
        for key in (
            "road_id",
            "settlement_id",
            "unit_id",
            "battle_id",
            "cart_id",
            "formation_id",
            "cube_id",
            "from",
            "to",
            "node",
            "node_id",
            "definition_id",
            "faction_id",
        ):
            if key in ev:
                row.append(str(ev.get(key)))
        out.append(tuple(row))
    return out
