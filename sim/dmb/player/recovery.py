"""Wizard safe-return recovery after non-victory duels (C10 / T092).

Chooses a return node without advancing World Turn or refreshing visit treatment
allowances. Priority: last surviving friendly settlement → nearest non-hostile
settlement → nearest catastrophe-free wilderness → least-affected node (ID ties).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.player.visits import VisitService

FRIENDLY_MIN = 0  # neutral-or-better wizard relation


def _relation(settlement: dict[str, Any]) -> int:
    return int(
        settlement.get("wizard_relation")
        if settlement.get("wizard_relation") is not None
        else settlement.get("relation_to_wizard", 0)
    )


def _node_distance(board: dict[str, Any], a: str, b: str) -> int:
    if a == b:
        return 0
    adj = board.get("adjacency") or {}
    # BFS on adjacency; fall back to large distance if disconnected.
    from collections import deque

    seen = {a}
    q = deque([(a, 0)])
    while q:
        node, dist = q.popleft()
        for nxt in adj.get(node) or []:
            nxt = str(nxt)
            if nxt in seen:
                continue
            if nxt == b:
                return dist + 1
            seen.add(nxt)
            q.append((nxt, dist + 1))
    # Hex axial fallback via shared board coordinates if present.
    axial = board.get("node_axial") or {}
    if a in axial and b in axial:
        ax, ay = axial[a]
        bx, by = axial[b]
        return abs(int(ax) - int(bx)) + abs(int(ay) - int(by))
    return 10_000 + abs(hash(a) % 1000 - hash(b) % 1000)


def _catastrophe_cube_count(state: WorldState, node_id: str) -> int:
    cubes = ((state.hazards or {}).get("catastrophe") or {}).get("cubes") or {}
    count = 0
    for cube in cubes.values():
        if not cube.get("active", True):
            continue
        if str(cube.get("node_id") or "") == node_id:
            count += 1
            continue
        hex_id = str(cube.get("hex_id") or "")
        touching = (state.board.get("node_hexes") or {}).get(node_id) or []
        if hex_id in touching:
            count += 1
    return count


@dataclass
class RecoveryService:
    state: WorldState

    def choose_return_node(self, *, from_node_id: str | None = None) -> dict[str, Any]:
        origin = str(
            from_node_id
            or (self.state.player or {}).get("node_id")
            or "node:1"
        )
        settlements = dict(self.state.settlements or {})
        board = self.state.board or {}

        def rank(node_id: str, bucket: int) -> tuple:
            return (bucket, _node_distance(board, origin, node_id), str(node_id))

        friendly: list[tuple] = []
        nonhostile: list[tuple] = []
        for sid, settlement in settlements.items():
            if settlement.get("alive") is False or settlement.get("destroyed"):
                continue
            node_id = str(settlement.get("node_id") or sid)
            rel = _relation(settlement)
            if rel >= FRIENDLY_MIN:
                # Prefer last_friendly marker when present.
                bucket = 0 if settlement.get("last_friendly") else 1
                friendly.append((rank(node_id, bucket), node_id, sid, "friendly"))
            elif rel > -50:  # not actively hostile
                nonhostile.append((rank(node_id, 0), node_id, sid, "nonhostile"))

        if friendly:
            friendly.sort()
            _r, node_id, sid, kind = friendly[0]
            return {"node_id": node_id, "settlement_id": sid, "kind": kind}

        if nonhostile:
            nonhostile.sort()
            _r, node_id, sid, kind = nonhostile[0]
            return {"node_id": node_id, "settlement_id": sid, "kind": kind}

        # Wilderness / least-affected nodes.
        nodes = list((board.get("nodes") or {}).keys()) or [origin]
        scored = []
        for node_id in nodes:
            cubes = _catastrophe_cube_count(self.state, str(node_id))
            scored.append(((cubes, _node_distance(board, origin, str(node_id)), str(node_id)), str(node_id)))
        scored.sort()
        node_id = scored[0][1]
        kind = "wilderness" if scored[0][0][0] == 0 else "least_affected"
        return {"node_id": node_id, "settlement_id": None, "kind": kind}

    def apply_return(
        self,
        *,
        from_node_id: str | None = None,
        command_id: str | None = None,
    ) -> dict[str, Any]:
        """Move player to safe node; no World Turn; no visit refresh."""
        receipt_id = command_id or f"recovery.return:{self.state.world_version}"
        receipts = self.state.command_receipts
        if receipt_id in receipts:
            return {"status": "idempotent", "receipt": dict(receipts[receipt_id])}

        turn_before = int(self.state.clock.get("turn") or 0)
        game_ms_before = int(self.state.clock.get("game_ms") or 0)
        choice = self.choose_return_node(from_node_id=from_node_id)
        self.state.player["node_id"] = choice["node_id"]
        self.state.player.setdefault("position", [0, 0])
        # Recovery arrival must not refresh treatment ledger.
        visit = VisitService(self.state).arrive(
            choice["node_id"],
            "recovery",
            turn_before,
        )
        assert int(self.state.clock.get("turn") or 0) == turn_before
        assert int(self.state.clock.get("game_ms") or 0) == game_ms_before
        receipt = {
            "receipt_id": receipt_id,
            "kind": "duel_recovery",
            "choice": choice,
            "visit": visit,
            "turn": turn_before,
            "game_ms": game_ms_before,
        }
        receipts[receipt_id] = receipt
        return {"status": "returned", "receipt": receipt, **choice}
