"""Strategic formation movement and withdrawal (C07 / T061).

Active-faction disengaged formations travel ≤2 edges per activation.
No real-time strategic travel. Withdrawal marks intent without an immediate move.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from sim.dmb.military.formations import FormationDirector
from sim.dmb.military.units import MilitaryService

MAX_EDGES_PER_ACTIVATION = 2


def _exit_destinations(node: Mapping[str, Any]) -> list[str]:
    exits = node.get("exits", [])
    if isinstance(exits, dict):
        return [str(k) for k in exits.keys()]
    return [str(item) for item in exits]


def _neighbours(board: Mapping[str, Any], node_id: str) -> list[str]:
    nodes = board.get("nodes") or {}
    node = nodes.get(node_id) or {}
    return _exit_destinations(node)


def _hostile_at_node(state: Any, node_id: str, faction_id: str) -> bool:
    """True if a living enemy unit or hostile settlement occupies the node."""
    for unit in (getattr(state, "units", {}) or {}).values():
        if not unit.get("alive", True):
            continue
        if str(unit.get("node_id")) != node_id:
            continue
        if str(unit.get("faction_id")) != faction_id:
            return True
    for settlement in (getattr(state, "settlements", {}) or {}).values():
        if str(settlement.get("node_id")) != node_id:
            continue
        owner = str(settlement.get("faction_id") or "")
        if owner and owner != faction_id:
            return True
    for battle in (getattr(state, "battles", {}) or {}).values():
        if str(battle.get("node_id")) != node_id:
            continue
        if battle.get("state") in {"ACTIVE", "LOCAL", "OFFSCREEN", "STALEMATE"}:
            participants = battle.get("factions") or battle.get("participant_factions") or []
            if faction_id in participants or any(
                str(p) != faction_id for p in participants
            ):
                # Entering a node with an ongoing battle is hostility.
                return True
    return False


def _friendly_neighbour(state: Any, node_id: str, faction_id: str) -> str | None:
    for neigh in sorted(_neighbours(state.board, node_id)):
        # Friendly = owned settlement or no hostile presence and passable.
        owned = False
        for settlement in (getattr(state, "settlements", {}) or {}).values():
            if str(settlement.get("node_id")) == neigh and str(settlement.get("faction_id")) == faction_id:
                owned = True
                break
        if owned or not _hostile_at_node(state, neigh, faction_id):
            # Prefer owned; still allow empty passable adjacent.
            if owned:
                return neigh
    # Fallback: any non-hostile neighbour.
    for neigh in sorted(_neighbours(state.board, node_id)):
        if not _hostile_at_node(state, neigh, faction_id):
            return neigh
    return None


class StrategicMovement:
    """FormationDirector movement surface: activate path and mark withdrawal."""

    def __init__(self, world_state: Any):
        self.state = world_state
        self.formations = FormationDirector(world_state)
        self.military = MilitaryService(world_state)

    def legal_objectives(self, formation_id: str, *, active_faction_id: str) -> list[dict[str, Any]]:
        formation = self.formations.get(formation_id)
        if str(formation.get("faction_id")) != active_faction_id:
            return []
        if formation.get("engagement_id"):
            return []
        turn = int(self.state.clock.get("turn", 0))
        if formation.get("movement_spent_turn") == turn:
            return []
        start = str(formation.get("node_id"))
        out: list[dict[str, Any]] = []
        # BFS up to 2 edges; stop expanding through hostility.
        frontier = [(start, [])]
        seen = {start}
        while frontier:
            node, path = frontier.pop(0)
            if 0 < len(path) <= MAX_EDGES_PER_ACTIVATION:
                out.append(
                    {
                        "node_id": node,
                        "path": list(path),
                        "edges": len(path),
                        "stopped_on_hostility": _hostile_at_node(self.state, node, active_faction_id),
                    }
                )
            if len(path) >= MAX_EDGES_PER_ACTIVATION:
                continue
            if path and _hostile_at_node(self.state, node, active_faction_id):
                # Stop on first hostility — do not expand further.
                continue
            for neigh in sorted(_neighbours(self.state.board, node)):
                if neigh in seen:
                    continue
                seen.add(neigh)
                frontier.append((neigh, path + [neigh]))
        return out

    def activate(
        self,
        formation_id: str,
        path: Sequence[str],
        *,
        active_faction_id: str,
        turn: int | None = None,
    ) -> dict[str, Any]:
        """Move along path ≤2 edges; stop on first hostility; record turn receipt."""
        formation = self.formations.get(formation_id)
        if str(formation.get("faction_id")) != active_faction_id:
            raise ValueError("inactive faction cannot move")
        if formation.get("engagement_id"):
            raise ValueError("engaged formation cannot strategically travel")
        turn_n = int(self.state.clock.get("turn", 0) if turn is None else turn)
        if formation.get("movement_spent_turn") == turn_n:
            raise ValueError("formation already spent movement this turn")
        if len(path) > MAX_EDGES_PER_ACTIVATION:
            raise ValueError("path exceeds two edges")
        if not path:
            formation["movement_spent_turn"] = turn_n
            return {"formation_id": formation_id, "node_id": formation["node_id"], "path": [], "stopped": False}

        current = str(formation["node_id"])
        travelled: list[str] = []
        stopped = False
        for step in path:
            step_s = str(step)
            if step_s not in _neighbours(self.state.board, current):
                raise ValueError(f"illegal edge {current}->{step_s}")
            # Units produced this turn at current node cannot change node until later activation.
            movable = []
            for uid in list(formation.get("unit_ids") or []):
                unit = self.state.units.get(uid)
                if unit is None or not unit.get("alive", True):
                    continue
                spawned_turn = unit.get("spawned_turn")
                if spawned_turn is not None and int(spawned_turn) == turn_n and str(unit.get("node_id")) == current:
                    # New unit stays; does not block formation travel of older members.
                    continue
                movable.append(uid)
            current = step_s
            travelled.append(step_s)
            for uid in movable:
                self.state.units[uid]["node_id"] = current
            formation["node_id"] = current
            if _hostile_at_node(self.state, current, active_faction_id):
                stopped = True
                formation["engagement_id"] = formation.get("engagement_id") or f"pending:{current}"
                break
        formation["path"] = list(travelled)
        formation["movement_spent_turn"] = turn_n
        # Withdrawal resolution: if withdrawing and target reached or blocked, clear/re-engage.
        if formation.get("withdrawal_status") == "pending":
            target = formation.get("withdrawal_target")
            if target and current == target:
                formation["withdrawal_status"] = "complete"
                formation["withdrawal_target"] = None
            elif target and _hostile_at_node(self.state, str(target), active_faction_id):
                formation["withdrawal_status"] = "blocked"
                formation["engagement_id"] = formation.get("engagement_id") or f"reengage:{current}"
        return {
            "formation_id": formation_id,
            "node_id": current,
            "path": travelled,
            "stopped": stopped,
            "movement_spent_turn": turn_n,
        }

    def mark_withdrawal(
        self,
        formation_id: str,
        *,
        entry_effective_health: int | None = None,
    ) -> dict[str, Any]:
        """Below 25% entry health + friendly neighbour → intent only, no immediate move."""
        formation = self.formations.get(formation_id)
        strength = self.formations.strength(formation_id)
        entry = int(entry_effective_health if entry_effective_health is not None else formation.get("entry_strength") or strength)
        if entry <= 0:
            formation["withdrawal_status"] = "none"
            return {"status": "none", "reason": "no_entry_strength"}
        if strength * 4 > entry:  # not below 25%
            formation["withdrawal_status"] = "none"
            return {"status": "none", "reason": "above_threshold", "strength": strength, "entry": entry}
        faction_id = str(formation["faction_id"])
        node_id = str(formation["node_id"])
        target = _friendly_neighbour(self.state, node_id, faction_id)
        if target is None:
            formation["withdrawal_status"] = "fight_on"
            formation["withdrawal_target"] = None
            return {"status": "fight_on", "reason": "no_retreat_path"}
        formation["withdrawal_target"] = target
        formation["withdrawal_status"] = "pending"
        # Cease previous attack / clear engagement intent for next activation retreat.
        formation["objective"] = "withdraw"
        return {
            "status": "pending",
            "withdrawal_target": target,
            "node_id": node_id,
            "immediate_move": False,
        }

    def revalidate_withdrawal(self, formation_id: str) -> dict[str, Any]:
        """If retreat node blocked, re-engage; else keep pending for next activation."""
        formation = self.formations.get(formation_id)
        if formation.get("withdrawal_status") != "pending":
            return {"status": formation.get("withdrawal_status")}
        target = formation.get("withdrawal_target")
        faction_id = str(formation["faction_id"])
        if target is None:
            formation["withdrawal_status"] = "fight_on"
            return {"status": "fight_on"}
        if _hostile_at_node(self.state, str(target), faction_id):
            formation["withdrawal_status"] = "blocked"
            formation["engagement_id"] = formation.get("engagement_id") or f"reengage:{formation['node_id']}"
            formation["objective"] = "reengage"
            return {"status": "blocked", "reengage": True}
        # Still legal — no immediate move.
        return {"status": "pending", "withdrawal_target": target, "immediate_move": False}


# C07 names FormationDirector for movement API; expose aliases on the movement module.
FormationMovement = StrategicMovement
