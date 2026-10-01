"""Generalized identity / transition asserts from working slices."""

from __future__ import annotations

from typing import Any


def assert_unique_body_per_sim_id(render: dict[str, Any], *, sim_ids: list[str] | None = None) -> None:
    """Exactly one node-backed body per sim_id (labels/controls/registered do not count)."""
    counts: dict[str, int] = {}
    for ent in render.get("entities") or []:
        if str(ent.get("role") or "") != "body":
            continue
        if str(ent.get("observation") or "") == "dict_only_no_node":
            continue
        if ent.get("node_backed") is False:
            continue
        sid = str(ent.get("sim_id") or "")
        if not sid:
            continue
        if sim_ids is not None and sid not in sim_ids:
            continue
        counts[sid] = counts.get(sid, 0) + 1
    for sid, n in counts.items():
        if n > 1:
            raise AssertionError(f"duplicate body sim_id={sid} count={n}")
    if sim_ids:
        for sid in sim_ids:
            if counts.get(sid, 0) != 1:
                raise AssertionError(f"expected exactly one body for sim_id={sid} got {counts.get(sid, 0)}")


def assert_committed_order_without_active_scaffold(
    authority: dict[str, Any],
    render: dict[str, Any],
    order_id: str,
) -> None:
    """Authority says committed AND render has no construction scaffold body for that order."""
    order = (authority.get("orders") or {}).get(order_id)
    if order is None:
        raise AssertionError(f"missing order {order_id}")
    if order.get("status") != "committed":
        raise AssertionError(f"order {order_id} status={order.get('status')}")
    scaffolds = [
        e
        for e in (render.get("entities") or [])
        if str(e.get("sim_id")) == order_id
        and str(e.get("role")) == "body"
        and str(e.get("sim_kind")) == "construction"
        and bool(e.get("node_backed", False))
        and bool(e.get("visible_in_tree", False))
    ]
    if scaffolds:
        raise AssertionError(f"stale scaffold still rendered for {order_id}: {scaffolds}")


def assert_lease_closed(authority: dict[str, Any], battle_id: str | None = None) -> None:
    """Battle must not remain LOCAL with an active lease after CloseBattleLease."""
    leases = authority.get("leases") or {}
    for bid, b in (authority.get("battles") or {}).items():
        if battle_id and bid != battle_id:
            continue
        state = str(b.get("state") or "")
        lease_id = b.get("lease_id")
        if state == "LOCAL" and lease_id:
            lease = leases.get(str(lease_id)) or {}
            if str(lease.get("state") or "") == "ACTIVE":
                raise AssertionError(f"battle {bid} still LOCAL with ACTIVE lease {lease_id}")
        if lease_id:
            lease = leases.get(str(lease_id)) or {}
            if str(lease.get("state") or "") == "ACTIVE" and state not in {"LOCAL", "ACTIVE", "PENDING"}:
                # Closed battles should not keep ACTIVE leases.
                raise AssertionError(f"stale ACTIVE lease {lease_id} for battle {bid} state={state}")
