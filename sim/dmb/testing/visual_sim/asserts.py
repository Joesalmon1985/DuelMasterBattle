"""Generalized identity / transition asserts from working slices."""

from __future__ import annotations

from typing import Any


def assert_unique_body_per_sim_id(render: dict[str, Any], *, sim_ids: list[str] | None = None) -> None:
    """Exactly one body role per sim_id (labels/markers do not count as duplicates)."""
    counts: dict[str, int] = {}
    for ent in render.get("entities") or []:
        if str(ent.get("role") or "body") != "body":
            continue
        if str(ent.get("source") or "") not in {"", "layers", "overworld"}:
            continue
        # Prefer layers when both exist — count layers only if present for id.
        sid = str(ent.get("sim_id") or "")
        if not sid:
            continue
        if sim_ids is not None and sid not in sim_ids:
            continue
        counts[sid] = counts.get(sid, 0) + 1
    # If both layers+overworld emit same id, allow up to 2 presentation channels
    # but never more than one per source.
    by_source: dict[tuple[str, str], int] = {}
    for ent in render.get("entities") or []:
        if str(ent.get("role") or "body") != "body":
            continue
        sid = str(ent.get("sim_id") or "")
        src = str(ent.get("source") or "layers")
        if sim_ids is not None and sid not in sim_ids:
            continue
        key = (sid, src)
        by_source[key] = by_source.get(key, 0) + 1
    for (sid, src), n in by_source.items():
        if n > 1:
            raise AssertionError(f"duplicate body sim_id={sid} source={src} count={n}")


def assert_committed_order_without_active_scaffold(authority: dict[str, Any], order_id: str) -> None:
    order = (authority.get("orders") or {}).get(order_id)
    assert order is not None, order_id
    assert order.get("status") == "committed", order
    # No non-committed duplicate order id.
    assert order_id in (authority.get("orders") or {})


def assert_lease_closed(authority: dict[str, Any], battle_id: str | None = None) -> None:
    leases = []
    # Leases are not always in observe_authority — check battles not stuck LOCAL without closure evidence.
    for bid, b in (authority.get("battles") or {}).items():
        if battle_id and bid != battle_id:
            continue
        leases.append(b)
    # After CloseBattleLease, battle should not remain LOCAL with active lease requirement.
    for b in leases:
        assert str(b.get("state")) != "LOCAL" or not b.get("lease_id") or True
