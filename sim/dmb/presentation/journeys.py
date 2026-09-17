"""Local journey presentation leases for carts (and future actors).

Authoritative node crossings remain CartService / World Turn logistics.
These records only describe Game-Time local walks between portal anchors.
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
PHASE_ENTERING = "entering"
PHASE_TO_WAYPOINT = "to_waypoint"
PHASE_TO_DELIVERY = "to_delivery"
PHASE_UNLOADING = "unloading"
PHASE_BLOCKED = "blocked"


def presentation_root(state: WorldState) -> dict[str, Any]:
    board = state.board.setdefault("presentation", {})
    journeys = board.setdefault("journeys", {})
    pending = board.setdefault("pending_transitions", {})
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
        # Already at destination node — walk to delivery point.
        local_to = _delivery_grid(state, fx)
        journey = {
            "journey_id": _new_journey_id(state, cart_id),
            "actor_id": person_id,
            "cart_id": cart_id,
            "sequence": int(root.get("journey_seq", 0)),
            "phase": PHASE_TO_DELIVERY,
            "from_node": current,
            "to_node": current,
            "exit_id": None,
            "hold_grid": local_to,
            "arrival_grid": local_to,
            "local_from": local_from,
            "local_to": local_to,
            "local_pos": list(local_from),
            "progress_ms": 0,
            "duration_ms": 2200,
            "game_ms_start": int(state.clock.get("game_ms", 0)),
            "authorized_cross": False,
            "committed_edge": None,
        }
    else:
        link = _exit_link(state, current, nxt)
        hold = _hold_grid(link, [12.0, 5.0] if current == "node:1" else [12.0, 5.0])
        arrival = _arrival_grid(link, [1.5, 5.0])
        journey = {
            "journey_id": _new_journey_id(state, cart_id),
            "actor_id": person_id,
            "cart_id": cart_id,
            "sequence": int(root.get("journey_seq", 0)),
            "phase": PHASE_TO_EXIT,
            "from_node": current,
            "to_node": nxt,
            "exit_id": link.get("exit_id"),
            "hold_grid": hold,
            "arrival_grid": arrival,
            "local_from": local_from,
            "local_to": hold,
            "local_pos": list(local_from),
            "progress_ms": 0,
            "duration_ms": 2500,
            "game_ms_start": int(state.clock.get("game_ms", 0)),
            "authorized_cross": False,
            "committed_edge": None,
        }
    root["journeys"][person_id] = journey
    root.setdefault("pending_transitions", {})[person_id] = []
    # Presentation pose hint (fractional grid); strategic node unchanged.
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
    person = state.people.get(actor_id)
    if isinstance(person, dict):
        person["grid"] = list(journey["local_pos"])
        person["presentation_phase"] = PHASE_WAITING_EXIT
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
        # Stay on from_node visually at / approaching exit.
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

    # Destination local target after entrance: next exit hold, or delivery pad.
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

    # Authoritative person node updates immediately; local pose starts at arrival.
    person["node_id"] = to_node
    person["grid"] = list(arrival)
    person["presentation_phase"] = PHASE_ENTERING

    journey = root.get("journeys", {}).get(person_id) or {
        "journey_id": _new_journey_id(state, cart_id),
        "actor_id": person_id,
        "cart_id": cart_id,
    }
    mid_depart = journey.get("phase") in {
        PHASE_TO_EXIT,
        PHASE_WAITING_EXIT,
        PHASE_DEPARTING,
    } and str(journey.get("from_node")) == from_node
    # Rapid successive edges: keep the current presentation lease and drain the
    # pending queue in order — do not reset local progress or replay finished legs.
    backlog = len(pending) > 1 or (
        mid_depart is False
        and journey.get("phase")
        in {
            PHASE_TO_EXIT,
            PHASE_WAITING_EXIT,
            PHASE_DEPARTING,
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
        # Leave phase/local_pos alone so the presenter finishes in-order.
    else:
        # Instantly adopt entrance leg (presenter may still play from queue).
        journey.update(
            {
                "phase": PHASE_ENTERING,
                "from_node": to_node,
                "to_node": nxt or to_node,
                "exit_id": link.get("exit_id"),
                "hold_grid": hold,
                "arrival_grid": arrival,
                "local_from": arrival,
                "local_to": local_to,
                "local_pos": list(arrival),
                "progress_ms": 0,
                "duration_ms": 2800,
                "game_ms_start": int(state.clock.get("game_ms", 0)),
                "authorized_cross": True,
                "committed_edge": [from_node, to_node],
                "onward_phase": onward_phase,
            }
        )
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
    # Preserve journey_id when continuing the same delivery presentation.
    existing = root.get("journeys", {}).get(person_id) or {}
    journey = {
        "journey_id": existing.get("journey_id") or _new_journey_id(state, cart_id),
        "actor_id": person_id,
        "cart_id": cart_id,
        "sequence": int(root.get("journey_seq", 0)),
        "phase": PHASE_UNLOADING,
        "from_node": current,
        "to_node": current,
        "local_from": local,
        "local_to": local,
        "local_pos": list(local),
        "progress_ms": 0,
        "duration_ms": 1200,
        "game_ms_start": int(state.clock.get("game_ms", 0)),
        "authorized_cross": False,
        "committed_edge": None,
        "depict_unload_only": True,
    }
    root["journeys"][person_id] = journey
    root.pop("deferred_unload", None)
    person["presentation_phase"] = PHASE_UNLOADING
    return deepcopy(journey)


def apply_presentation_progress(state: WorldState, payload: dict[str, Any]) -> dict[str, Any]:
    """Godot SyncPresentation: update local progress without mutating cargo/turns."""
    root = presentation_root(state)
    actor_id = str(payload.get("actor_id") or "")
    journey = root.get("journeys", {}).get(actor_id)
    if not isinstance(journey, dict):
        return {"status": "ignored", "reason": "no_journey"}
    if payload.get("journey_id") and str(payload.get("journey_id")) != str(journey.get("journey_id")):
        return {"status": "ignored", "reason": "stale_journey"}
    if "progress_ms" in payload:
        journey["progress_ms"] = max(0, int(payload["progress_ms"]))
    if "phase" in payload:
        phase = str(payload["phase"])
        allowed = {
            PHASE_TO_EXIT,
            PHASE_WAITING_EXIT,
            PHASE_DEPARTING,
            PHASE_ENTERING,
            PHASE_TO_WAYPOINT,
            PHASE_TO_DELIVERY,
            PHASE_UNLOADING,
            PHASE_BLOCKED,
            PHASE_IDLE,
        }
        if phase in allowed:
            journey["phase"] = phase
    pos = payload.get("local_pos")
    if isinstance(pos, (list, tuple)) and len(pos) >= 2:
        journey["local_pos"] = [float(pos[0]), float(pos[1])]
        person = state.people.get(actor_id)
        if isinstance(person, dict):
            # Only write local grid when the person is on the node being presented.
            node = str(person.get("node_id") or "")
            phase = str(journey.get("phase") or "")
            presenting_node = str(journey.get("from_node") or "")
            if phase in {PHASE_ENTERING, PHASE_TO_WAYPOINT, PHASE_TO_DELIVERY, PHASE_UNLOADING, PHASE_IDLE}:
                presenting_node = str(journey.get("to_node") or journey.get("from_node") or "")
            if node == presenting_node:
                person["grid"] = list(journey["local_pos"])
            person["presentation_phase"] = journey.get("phase")
    if payload.get("consume_pending"):
        pending = root.setdefault("pending_transitions", {}).setdefault(actor_id, [])
        seq = payload.get("consumed_sequence")
        if pending and (seq is None or int(pending[0].get("sequence", -1)) == int(seq)):
            pending.pop(0)
    # Flush deferred unload once edge presentation backlog is clear.
    deferred = root.get("deferred_unload")
    if isinstance(deferred, dict) and str(deferred.get("actor_id")) == actor_id:
        phase_now = str(journey.get("phase") or "")
        pending_left = root.get("pending_transitions", {}).get(actor_id) or []
        if not pending_left and phase_now in {PHASE_IDLE, PHASE_TO_DELIVERY}:
            cart_id = str(deferred.get("cart_id") or "")
            root.pop("deferred_unload", None)
            if cart_id:
                begin_unload_presentation(state, cart_id)
                journey = root.get("journeys", {}).get(actor_id) or journey
    return {"status": "ok", "journey": deepcopy(journey)}


def _push_pending(root: dict[str, Any], actor_id: str, transition: dict[str, Any]) -> None:
    pending = root.setdefault("pending_transitions", {}).setdefault(actor_id, [])
    # Deduplicate identical committed edges.
    edge = transition.get("committed_edge")
    for existing in pending:
        if existing.get("committed_edge") == edge and existing.get("kind") == transition.get("kind"):
            return
    pending.append(transition)
    while len(pending) > MAX_PENDING_TRANSITIONS:
        # Drop oldest visual-only backlog; end-state already applied via person.node_id.
        pending.pop(0)


def journeys_for_view(state: WorldState) -> dict[str, Any]:
    root = state.board.get("presentation") or {}
    return {
        "journeys": deepcopy(root.get("journeys") or {}),
        "pending_transitions": deepcopy(root.get("pending_transitions") or {}),
        "journey_seq": int(root.get("journey_seq") or 0),
    }
