"""Production journey helpers for construction and combat slices."""

from __future__ import annotations

from typing import Any

from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.testing.visual_sim.authority import observe_authority
from sim.dmb.testing.visual_sim.runner import advance_once, dispatch, wait_once


def _neighbours(board: dict, node_id: str) -> list[str]:
    out: list[str] = []
    nodes = board.get("nodes") or {}
    node = nodes.get(node_id) if isinstance(nodes, dict) else None
    if isinstance(node, dict):
        exits = node.get("exits") or {}
        if isinstance(exits, dict):
            out.extend(str(k) for k in exits.keys())
    edges = board.get("edges") or board.get("links") or []
    for e in edges:
        if isinstance(e, (list, tuple)) and len(e) >= 2:
            a, b = str(e[0]), str(e[1])
            if a == node_id:
                out.append(b)
            elif b == node_id:
                out.append(a)
    return sorted(set(out))


def run_slice_b_construction(seed: int = 507, *, max_waits: int = 200, advance_s: int = 45) -> dict[str, Any]:
    """PRODUCTION_JOURNEY: Wait until a construction order commits via production path."""
    sim = load_fixture("FX-MVP", seed=seed)
    for i in range(advance_s):
        advance_once(sim, seq=i + 1)
    committed = None
    for i in range(max_waits):
        wait_once(sim, press_id=f"sliceb-w{i}")
        for oid, order in (sim.state.orders or {}).items():
            if str(order.get("status")) == "committed" and str(order.get("action")) in {
                "road",
                "settlement",
                "city",
                "legacy_upgrade",
            }:
                committed = {"id": oid, **dict(order)}
                break
        if committed:
            break
        # Keep industry ticking so carts/orders can complete.
        if i % 5 == 4:
            advance_once(sim, seq=advance_s + i + 1)
    authority = observe_authority(sim)
    return {
        "sim": sim,
        "authority": authority,
        "committed_order": committed,
        "scenario_class": "PRODUCTION_JOURNEY",
        "ok": committed is not None,
    }


def run_slice_a_combat(seed: int = 507, *, advance_s: int = 120, max_waits: int = 80) -> dict[str, Any]:
    """PRODUCTION_JOURNEY: industry → Wait contact → OpenBattleLease/CloseBattleLease.

    OpenBattleLease is a production command that does not advance strategic turns.
    Call it as soon as a PENDING battle exists so the next Wait cannot offscreen it.
    """
    sim = load_fixture("FX-MVP", seed=seed)
    for i in range(advance_s):
        advance_once(sim, seq=i + 1)
    authority_mid = observe_authority(sim)
    battle_seen = None
    lease_opened = None
    lease_closed = None
    offscreen_resolved: list[str] = []

    for i in range(max_waits):
        wait_once(sim, press_id=f"slicea-w{i}")
        for bid, battle in list((sim.state.battles or {}).items()):
            st = str(battle.get("state") or "")
            if st in {"wipe", "resolved", "COMPLETE", "complete"} or battle.get("outcome"):
                offscreen_resolved.append(bid)
            if st not in {"PENDING", "LOCAL", "ACTIVE", "OFFSCREEN", "READY"}:
                continue
            battle_seen = {
                "id": bid,
                "node_id": battle.get("node_id"),
                "state": st,
                "participants": list(battle.get("participants") or []),
                "prefer_local": battle.get("prefer_local"),
            }
            if lease_opened is not None:
                continue
            # Production lease open — no turn advance.
            reply = dispatch(sim, "OpenBattleLease", {"battle_id": bid}, cmd_id=f"cmd:lease-open-{i}")
            lease_opened = {
                "battle_id": bid,
                "status": reply.status,
                "code": getattr(reply, "code", None),
                "payload": getattr(reply, "payload", None),
            }
            if reply.status != "ACCEPTED":
                continue
            payload = reply.payload if isinstance(reply.payload, dict) else {}
            lease = payload.get("lease") if isinstance(payload.get("lease"), dict) else {}
            lid = lease.get("lease_id") or battle.get("lease_id") or battle.get("local_lease_id")
            if not lid:
                continue
            close = dispatch(
                sim,
                "CloseBattleLease",
                {"lease_id": lid, "battle_id": bid},
                cmd_id=f"cmd:lease-close-{i}",
            )
            lease_closed = {"battle_id": bid, "status": close.status, "lease_id": lid, "code": getattr(close, "code", None)}
            break
        if lease_opened and lease_closed and lease_opened.get("status") == "ACCEPTED":
            break

    authority = observe_authority(sim)
    attended_ok = bool(
        lease_opened
        and lease_closed
        and lease_opened.get("status") == "ACCEPTED"
        and lease_closed.get("status") == "ACCEPTED"
    )
    strategic_ok = bool(battle_seen or offscreen_resolved or authority["counts"]["battles"] > 0)
    return {
        "sim": sim,
        "authority": authority,
        "authority_mid": authority_mid,
        "battle_seen": battle_seen,
        "lease_opened": lease_opened,
        "lease_closed": lease_closed,
        "offscreen_resolved": offscreen_resolved,
        "scenario_class": "PRODUCTION_JOURNEY",
        "attended_ok": attended_ok,
        "strategic_ok": strategic_ok,
        "ok": attended_ok,
    }
