"""Local journey presentation leases for carts (and future actors).

Authoritative node crossings remain CartService / World Turn logistics.
These records only describe Game-Time local walks between portal anchors.

SyncPresentation is a finite, sequence-driven acknowledgement: each committed
edge is presented once (depart → hidden → enter → onward). Acknowledgements
persist full leg metadata so RequestView cannot restart a consumed phase.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sim.dmb.core.state import WorldState

# Cap pending visual transitions so rapid Wait cannot grow an unbounded queue.
MAX_PENDING_TRANSITIONS = 3

PHASE_IDLE = "idle"
PHASE_TO_EXIT = "to_exit"
PHASE_WAITING_EXIT = "waiting_exit"
PHASE_DEPARTING = "departing"
PHASE_HIDDEN = "hidden"
PHASE_ENTERING = "entering"
PHASE_TO_WAYPOINT = "to_waypoint"
PHASE_TO_DELIVERY = "to_delivery"
PHASE_UNLOADING = "unloading"
PHASE_BLOCKED = "blocked"

ALLOWED_PHASES = {
    PHASE_IDLE,
    PHASE_TO_EXIT,
    PHASE_WAITING_EXIT,
    PHASE_DEPARTING,
    PHASE_HIDDEN,
    PHASE_ENTERING,
    PHASE_TO_WAYPOINT,
    PHASE_TO_DELIVERY,
    PHASE_UNLOADING,
    PHASE_BLOCKED,
}


def presentation_root(state: WorldState) -> dict[str, Any]:
    board = state.board.setdefault("presentation", {})
    board.setdefault("journeys", {})
    board.setdefault("pending_transitions", {})
    return board


def _exit_link(state: WorldState, from_node: str, to_node: str) -> dict[str, Any]:
    node = (state.board.get("nodes") or {}).get(from_node) or {}
    exits = node.get("exits") or {}
    if isinstance(exits, dict) and to_node in exits:
        link = dict(exits[to_node])
        link.setdefault("to_node", to_node)
        return link
    return {}


def _grid_from_person(person: dict[str, Any] | None, default: list[float]) -> list[float]:
    if not isinstance(person, dict):
        return list(default)
    grid = person.get("grid") or person.get("position") or default
    if isinstance(grid, (list, tuple)) and len(grid) >= 2:
        return [float(grid[0]), float(grid[1])]
    return list(default)


def _hold_grid(link: dict[str, Any], fallback: list[float]) -> list[float]:
    hold = link.get("hold_position") or fallback
    return [float(hold[0]), float(hold[1])]


def _arrival_grid(link: dict[str, Any], fallback: list[float]) -> list[float]:
    arrival = link.get("arrival") or {}
    pos = arrival.get("position") or fallback
    return [float(pos[0]), float(pos[1])]


def _as_grid(value: Any, fallback: list[float]) -> list[float]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return [float(value[0]), float(value[1])]
    return list(fallback)


def _next_route_node(cart: dict[str, Any]) -> str | None:
    route = list(cart.get("route") or [])
    idx = int(cart.get("route_index", 0))
    if idx + 1 < len(route):
        return str(route[idx + 1])
    return None


def _delivery_grid(state: WorldState, fx: dict[str, Any]) -> list[float]:
    staging_id = str(fx.get("staging_person_id") or "person:staging")
    person = state.people.get(staging_id) or {}
    return _grid_from_person(person, [8.0, 4.0])


def _new_journey_id(state: WorldState, cart_id: str) -> str:
    seq = int((state.board.get("presentation") or {}).get("journey_seq", 0)) + 1
    state.board.setdefault("presentation", {})["journey_seq"] = seq
    return f"journey:{cart_id}:{seq}"


def _write_person_pose(state: WorldState, actor_id: str, journey: dict[str, Any]) -> None:
    person = state.people.get(actor_id)
    if not isinstance(person, dict):
        return
    person["presentation_phase"] = journey.get("phase")
    presenting = str(journey.get("presenting_node") or "")
    phase = str(journey.get("phase") or "")
    if phase == PHASE_HIDDEN or presenting == "":
        return
    pos = journey.get("local_pos")
    if isinstance(pos, (list, tuple)) and len(pos) >= 2:
        person["grid"] = [float(pos[0]), float(pos[1])]


def begin_cart_assignment_journey(state: WorldState, cart_id: str) -> dict[str, Any]:
    """After Start delivery: walk toward the exit for the next route node (no crossing yet)."""
    root = presentation_root(state)
    fx = state.board.get("fx_cargo") or {}
    cart = state.carts.get(cart_id) or {}
    person_id = str(fx.get("cart_person_id") or "person:cart")
    person = state.people.get(person_id) or {}
    current = str(cart.get("current_node") or person.get("node_id") or "")
    nxt = _next_route_node(cart)
    local_from = _grid_from_person(person, [6.0, 5.0])
    if not nxt:
        local_to = _delivery_grid(state, fx)
        journey = {
            "journey_id": _new_journey_id(state, cart_id),
            "actor_id": person_id,
            "cart_id": cart_id,
            "sequence": int(root.get("journey_seq", 0)),
            "phase": PHASE_TO_DELIVERY,
            "presenting_node": current,
            "from_node": current,
            "to_node": current,
            "exit_id": None,
            "hold_grid": local_to,
            "arrival_grid": local_to,
            "local_from": local_from,
            "local_to": local_to,
            "local_pos": list(local_from),
            "progress_ms": 0,
            "duration_ms": 3200,
            "game_ms_start": int(state.clock.get("game_ms", 0)),
            "authorized_cross": False,
            "committed_edge": None,
            "onward_phase": PHASE_UNLOADING,
            "last_consumed_sequence": 0,
        }
    else:
        link = _exit_link(state, current, nxt)
        hold = _hold_grid(link, [12.0, 5.0])
        arrival = _arrival_grid(link, [1.5, 5.0])
        journey = {
            "journey_id": _new_journey_id(state, cart_id),
            "actor_id": person_id,
            "cart_id": cart_id,
            "sequence": int(root.get("journey_seq", 0)),
            "phase": PHASE_TO_EXIT,
            "presenting_node": current,
            "from_node": current,
            "to_node": nxt,
            "exit_id": link.get("exit_id"),
            "hold_grid": hold,
            "arrival_grid": arrival,
            "local_from": local_from,
            "local_to": hold,
            "local_pos": list(local_from),
            "progress_ms": 0,
            "duration_ms": 3600,
            "game_ms_start": int(state.clock.get("game_ms", 0)),
            "authorized_cross": False,
            "committed_edge": None,
            "onward_phase": PHASE_TO_WAYPOINT,
            "last_consumed_sequence": 0,
        }
    root["journeys"][person_id] = journey
    root.setdefault("pending_transitions", {})[person_id] = []
    person["grid"] = list(local_from)
    person["presentation_phase"] = journey["phase"]
    return deepcopy(journey)


def mark_waiting_at_exit(state: WorldState, actor_id: str) -> dict[str, Any] | None:
    root = presentation_root(state)
    journey = root.get("journeys", {}).get(actor_id)
    if not isinstance(journey, dict):
        return None
    if journey.get("phase") != PHASE_TO_EXIT:
        return journey
    journey["phase"] = PHASE_WAITING_EXIT
    journey["progress_ms"] = int(journey.get("duration_ms", 0))
    journey["local_pos"] = list(journey.get("local_to") or journey.get("hold_grid") or [0, 0])
    journey["presenting_node"] = str(journey.get("from_node") or journey.get("presenting_node") or "")
    _write_person_pose(state, actor_id, journey)
    return deepcopy(journey)


def enqueue_committed_edge(
    state: WorldState,
    cart_id: str,
    *,
    from_node: str,
    to_node: str,
    blocked: bool = False,
) -> dict[str, Any]:
    """After logistics advances one road edge (or parks blocked)."""
    root = presentation_root(state)
    fx = state.board.get("fx_cargo") or {}
    person_id = str(fx.get("cart_person_id") or "person:cart")
    person = state.people.get(person_id) or {}
    cart = state.carts.get(cart_id) or {}
    link = _exit_link(state, from_node, to_node)
    hold = _hold_grid(link, [12.0, 5.0])
    arrival = _arrival_grid(link, [1.5, 5.0])
    nxt = _next_route_node(cart)
    if blocked:
        transition = {
            "sequence": int(root.get("journey_seq", 0)) + 1,
            "kind": "blocked",
            "from_node": from_node,
            "to_node": from_node,
            "exit_id": link.get("exit_id"),
            "hold_grid": hold,
            "arrival_grid": hold,
            "local_to": hold,
            "committed_edge": [from_node, to_node],
            "authorized_cross": False,
        }
        root["journey_seq"] = int(transition["sequence"])
        _push_pending(root, person_id, transition)
        journey = root.get("journeys", {}).get(person_id) or {}
        journey.update(
            {
                "journey_id": journey.get("journey_id") or _new_journey_id(state, cart_id),
                "actor_id": person_id,
                "cart_id": cart_id,
                "phase": PHASE_BLOCKED,
                "presenting_node": from_node,
                "from_node": from_node,
                "to_node": to_node,
                "hold_grid": hold,
                "local_to": hold,
                "authorized_cross": False,
                "committed_edge": [from_node, to_node],
            }
        )
        root["journeys"][person_id] = journey
        person["presentation_phase"] = PHASE_BLOCKED
        return deepcopy(transition)

    if nxt and str(cart.get("status")) not in {"arrived", "delivered"}:
        next_link = _exit_link(state, to_node, nxt)
        local_to = _hold_grid(next_link, [12.0, 5.0])
        onward_phase = PHASE_TO_WAYPOINT
    else:
        local_to = _delivery_grid(state, fx)
        onward_phase = PHASE_TO_DELIVERY

    transition = {
        "sequence": int(root.get("journey_seq", 0)) + 1,
        "kind": "edge",
        "from_node": from_node,
        "to_node": to_node,
        "exit_id": link.get("exit_id"),
        "hold_grid": hold,
        "arrival_grid": arrival,
        "local_to": local_to,
        "onward_phase": onward_phase,
        "committed_edge": [from_node, to_node],
        "authorized_cross": True,
    }
    root["journey_seq"] = int(transition["sequence"])
    _push_pending(root, person_id, transition)
    pending = root.get("pending_transitions", {}).get(person_id) or []

    person["node_id"] = to_node
    person["grid"] = list(arrival)

    journey = root.get("journeys", {}).get(person_id) or {
        "journey_id": _new_journey_id(state, cart_id),
        "actor_id": person_id,
        "cart_id": cart_id,
        "last_consumed_sequence": 0,
    }
    mid_depart = journey.get("phase") in {
        PHASE_TO_EXIT,
        PHASE_WAITING_EXIT,
        PHASE_DEPARTING,
    } and str(journey.get("from_node")) == from_node
    backlog = len(pending) > 1 or (
        not mid_depart
        and journey.get("phase")
        in {
            PHASE_TO_EXIT,
            PHASE_WAITING_EXIT,
            PHASE_DEPARTING,
            PHASE_HIDDEN,
            PHASE_ENTERING,
            PHASE_TO_WAYPOINT,
            PHASE_TO_DELIVERY,
        }
        and list(journey.get("committed_edge") or []) != [from_node, to_node]
        and journey.get("phase") != PHASE_IDLE
    )
    if mid_depart:
        journey["authorized_cross"] = True
        journey["committed_edge"] = [from_node, to_node]
        journey["pending_arrival"] = transition
    elif backlog:
        journey["authorized_cross"] = True
        journey["committed_edge"] = [from_node, to_node]
    else:
        journey.update(
            {
                "phase": PHASE_ENTERING,
                "presenting_node": to_node,
                "from_node": to_node,
                "to_node": nxt or to_node,
                "exit_id": link.get("exit_id"),
                "hold_grid": hold,
                "arrival_grid": arrival,
                "local_from": arrival,
                "local_to": local_to,
                "local_pos": list(arrival),
                "progress_ms": 0,
                "duration_ms": 4000,
                "game_ms_start": int(state.clock.get("game_ms", 0)),
                "authorized_cross": True,
                "committed_edge": [from_node, to_node],
                "onward_phase": onward_phase,
            }
        )
        person["presentation_phase"] = PHASE_ENTERING
    root["journeys"][person_id] = journey
    return deepcopy(transition)


def maybe_begin_unload_presentation(state: WorldState, cart_id: str) -> dict[str, Any] | None:
    """Start unload depiction only when no edge presentation backlog remains."""
    root = presentation_root(state)
    fx = state.board.get("fx_cargo") or {}
    person_id = str(fx.get("cart_person_id") or "person:cart")
    pending = root.get("pending_transitions", {}).get(person_id) or []
    journey = root.get("journeys", {}).get(person_id) or {}
    phase = str(journey.get("phase") or PHASE_IDLE)
    busy = phase in {
        PHASE_TO_EXIT,
        PHASE_WAITING_EXIT,
        PHASE_DEPARTING,
        PHASE_HIDDEN,
        PHASE_ENTERING,
        PHASE_TO_WAYPOINT,
        PHASE_TO_DELIVERY,
    }
    if pending or busy:
        root["deferred_unload"] = {"cart_id": cart_id, "actor_id": person_id}
        return None
    root.pop("deferred_unload", None)
    return begin_unload_presentation(state, cart_id)


def begin_unload_presentation(state: WorldState, cart_id: str) -> dict[str, Any]:
    root = presentation_root(state)
    fx = state.board.get("fx_cargo") or {}
    person_id = str(fx.get("cart_person_id") or "person:cart")
    person = state.people.get(person_id) or {}
    current = str(person.get("node_id") or "")
    local = _grid_from_person(person, _delivery_grid(state, fx))
    existing = root.get("journeys", {}).get(person_id) or {}
    journey = {
        "journey_id": existing.get("journey_id") or _new_journey_id(state, cart_id),
        "actor_id": person_id,
        "cart_id": cart_id,
        "sequence": int(root.get("journey_seq", 0)),
        "phase": PHASE_UNLOADING,
        "presenting_node": current,
        "from_node": current,
        "to_node": current,
        "local_from": local,
        "local_to": local,
        "local_pos": list(local),
        "progress_ms": 0,
        "duration_ms": 1400,
        "game_ms_start": int(state.clock.get("game_ms", 0)),
        "authorized_cross": False,
        "committed_edge": None,
        "depict_unload_only": True,
        "last_consumed_sequence": int(existing.get("last_consumed_sequence") or 0),
        "onward_phase": PHASE_IDLE,
    }
    root["journeys"][person_id] = journey
    root.pop("deferred_unload", None)
    person["presentation_phase"] = PHASE_UNLOADING
    return deepcopy(journey)


def apply_presentation_progress(state: WorldState, payload: dict[str, Any]) -> dict[str, Any]:
    """Atomically acknowledge a presentation transition and persist leg metadata.

    Does not mutate cargo, stock, or World Turns. Duplicate sequence ACKs are
    idempotent; stale/out-of-order ACKs are ignored.
    """
    root = presentation_root(state)
    actor_id = str(payload.get("actor_id") or "")
    journey = root.get("journeys", {}).get(actor_id)
    if not isinstance(journey, dict):
        return {"status": "ignored", "reason": "no_journey"}
    if payload.get("journey_id") and str(payload.get("journey_id")) != str(journey.get("journey_id")):
        return {"status": "ignored", "reason": "stale_journey", "journey": deepcopy(journey)}

    last = int(journey.get("last_consumed_sequence") or 0)
    want_consume = bool(payload.get("consume_pending"))
    seq_raw = payload.get("consumed_sequence")
    seq: int | None = int(seq_raw) if seq_raw is not None else None

    if want_consume or seq is not None:
        if seq is None:
            return {"status": "ignored", "reason": "missing_sequence", "journey": deepcopy(journey)}
        if seq <= last:
            pass  # idempotent duplicate
        else:
            pending = root.setdefault("pending_transitions", {}).setdefault(actor_id, [])
            if not pending:
                return {"status": "ignored", "reason": "no_pending", "journey": deepcopy(journey)}
            head_seq = int(pending[0].get("sequence", -1))
            if seq != head_seq:
                return {
                    "status": "ignored",
                    "reason": "out_of_order",
                    "expected": head_seq,
                    "got": seq,
                    "journey": deepcopy(journey),
                }
            pending.pop(0)
            journey["last_consumed_sequence"] = seq
            journey["consumed_sequence"] = seq

    if "phase" in payload:
        phase = str(payload["phase"])
        if phase in ALLOWED_PHASES:
            journey["phase"] = phase
    if "presenting_node" in payload and payload["presenting_node"] is not None:
        journey["presenting_node"] = str(payload["presenting_node"])
    if "from_node" in payload and payload["from_node"] is not None:
        journey["from_node"] = str(payload["from_node"])
    if "to_node" in payload and payload["to_node"] is not None:
        journey["to_node"] = str(payload["to_node"])
    if "onward_phase" in payload and payload["onward_phase"] is not None:
        journey["onward_phase"] = str(payload["onward_phase"])
    if "progress_ms" in payload:
        journey["progress_ms"] = max(0, int(payload["progress_ms"]))
    if "duration_ms" in payload:
        journey["duration_ms"] = max(1, int(payload["duration_ms"]))
    if "local_from" in payload:
        journey["local_from"] = _as_grid(payload["local_from"], journey.get("local_from") or [0.0, 0.0])
    if "local_to" in payload:
        journey["local_to"] = _as_grid(payload["local_to"], journey.get("local_to") or [0.0, 0.0])
    if "local_pos" in payload:
        journey["local_pos"] = _as_grid(payload["local_pos"], journey.get("local_pos") or [0.0, 0.0])
    if "authorized_cross" in payload:
        journey["authorized_cross"] = bool(payload["authorized_cross"])
    if "committed_edge" in payload and payload["committed_edge"] is not None:
        journey["committed_edge"] = list(payload["committed_edge"])

    phase_now = str(journey.get("phase") or PHASE_IDLE)
    if phase_now == PHASE_HIDDEN:
        journey["presenting_node"] = ""
    elif "presenting_node" not in payload or payload.get("presenting_node") is None:
        if not journey.get("presenting_node"):
            if phase_now in {
                PHASE_ENTERING,
                PHASE_TO_WAYPOINT,
                PHASE_TO_DELIVERY,
                PHASE_UNLOADING,
                PHASE_IDLE,
            }:
                journey["presenting_node"] = str(journey.get("from_node") or journey.get("to_node") or "")
            else:
                journey["presenting_node"] = str(journey.get("from_node") or "")

    _write_person_pose(state, actor_id, journey)

    deferred = root.get("deferred_unload")
    if isinstance(deferred, dict) and str(deferred.get("actor_id")) == actor_id:
        pending_left = root.get("pending_transitions", {}).get(actor_id) or []
        if not pending_left and phase_now in {PHASE_IDLE, PHASE_TO_DELIVERY, PHASE_UNLOADING}:
            cart_id = str(deferred.get("cart_id") or "")
            root.pop("deferred_unload", None)
            if cart_id and phase_now != PHASE_UNLOADING:
                begin_unload_presentation(state, cart_id)
                journey = root.get("journeys", {}).get(actor_id) or journey

    return {"status": "ok", "journey": deepcopy(journey)}


def _push_pending(root: dict[str, Any], actor_id: str, transition: dict[str, Any]) -> None:
    pending = root.setdefault("pending_transitions", {}).setdefault(actor_id, [])
    edge = transition.get("committed_edge")
    for existing in pending:
        if existing.get("committed_edge") == edge and existing.get("kind") == transition.get("kind"):
            return
    pending.append(transition)
    while len(pending) > MAX_PENDING_TRANSITIONS:
        pending.pop(0)


def journeys_for_view(state: WorldState) -> dict[str, Any]:
    root = state.board.get("presentation") or {}
    return {
        "journeys": deepcopy(root.get("journeys") or {}),
        "pending_transitions": deepcopy(root.get("pending_transitions") or {}),
        "journey_seq": int(root.get("journey_seq") or 0),
    }
