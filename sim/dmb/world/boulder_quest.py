"""G05 simple persistent blocked-exit boulder quest.

Python owns boulder durability, Travel gating, quest progression and worker
assignment. Godot only presents the walk/push/slide.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sim.dmb.quests.binding import QuestBinder
from sim.dmb.quests.causes import CauseTracker
from sim.dmb.quests.runtime import QuestService

BOULDER_ID = "boulder:1"
TEMPLATE_ID = "quest.blocked_exit_boulder"
CAUSE_KIND = "exit_blocked_by_boulder"
QUEST_INSTANCE_ID = "quest.blocked_exit_boulder"
CAUSE_TEMPLATE_ID = "cause.blocked_exit_boulder"

# Authoritative Game Time budget for walk + push (pause freezes AdvanceGame).
MOVE_DURATION_MS = 4500

OBSERVE_FAR = "A large boulder blocks the path out of the village."
OBSERVE_NEAR_BLOCKING = "It is far too heavy for John to move alone."
OBSERVE_NEAR_MOVED = "The boulder has been rolled clear of the path."
TRAVEL_BLOCKED = "The boulder blocks the way."

ACTIVITY_MOVING = "Moving boulder"


def _south_exit(state: Any, node_id: str) -> tuple[str, dict[str, Any]] | None:
    node = ((state.board or {}).get("nodes") or {}).get(node_id) or {}
    exits = node.get("exits") or {}
    if not isinstance(exits, dict):
        return None
    for to_node, link in exits.items():
        if str((link or {}).get("direction") or "") == "south":
            return str(to_node), dict(link)
    return None


def _pick_factory_worker(state: Any, node_id: str, *, prefer_id: str | None = None) -> str | None:
    if prefer_id:
        person = (state.people or {}).get(prefer_id)
        if (
            person
            and person.get("alive", True)
            and person.get("status") != "dead"
            and str(person.get("node_id") or "") == node_id
            and str(person.get("occupation") or "") == "Factory worker"
        ):
            return prefer_id
    candidates: list[str] = []
    for pid, person in sorted((state.people or {}).items()):
        if not person.get("alive", True) or person.get("status") == "dead":
            continue
        if str(person.get("node_id") or "") != node_id:
            continue
        if str(person.get("occupation") or "") != "Factory worker":
            continue
        candidates.append(pid)
    return candidates[0] if candidates else None


def get_boulder(state: Any) -> dict[str, Any] | None:
    mechs = ((state.board or {}).get("mechanisms") or {})
    rec = mechs.get(BOULDER_ID)
    return dict(rec) if isinstance(rec, dict) else None


def _store_boulder(state: Any, boulder: dict[str, Any]) -> None:
    mechs = state.board.setdefault("mechanisms", {})
    mechs[BOULDER_ID] = boulder


def boulder_blocks_travel(state: Any, from_node: str, to_node: str) -> bool:
    boulder = get_boulder(state)
    if not boulder:
        return False
    if str(boulder.get("status") or "") not in {"blocking", "moving"}:
        return False
    return (
        str(boulder.get("node_id") or "") == str(from_node)
        and str(boulder.get("target_node_id") or "") == str(to_node)
    )


def travel_block_reason(state: Any, from_node: str, to_node: str) -> str | None:
    if boulder_blocks_travel(state, from_node, to_node):
        return TRAVEL_BLOCKED
    return None


def presentation_position(boulder: dict[str, Any], *, game_ms: int) -> list[float]:
    blocking = list(boulder.get("blocking_position") or boulder.get("position") or [24, 40])
    moved = list(boulder.get("moved_position") or [27, 40])
    status = str(boulder.get("status") or "blocking")
    if status == "moved":
        return [float(moved[0]), float(moved[1])]
    if status != "moving":
        return [float(blocking[0]), float(blocking[1])]
    start = int(boulder.get("move_started_game_ms") or 0)
    duration = max(1, int(boulder.get("move_duration_ms") or MOVE_DURATION_MS))
    # Slide during the last third of the move window (after walk + push beat).
    t = max(0.0, min(1.0, (game_ms - start) / float(duration)))
    slide_t = 0.0 if t < 0.66 else (t - 0.66) / 0.34
    x = float(blocking[0]) + (float(moved[0]) - float(blocking[0])) * slide_t
    y = float(blocking[1]) + (float(moved[1]) - float(blocking[1])) * slide_t
    return [x, y]


def move_progress(boulder: dict[str, Any], *, game_ms: int) -> float:
    if str(boulder.get("status") or "") == "moved":
        return 1.0
    if str(boulder.get("status") or "") != "moving":
        return 0.0
    start = int(boulder.get("move_started_game_ms") or 0)
    duration = max(1, int(boulder.get("move_duration_ms") or MOVE_DURATION_MS))
    return max(0.0, min(1.0, (game_ms - start) / float(duration)))


def install_boulder_quest(state: Any, *, start_node_id: str | None = None) -> dict[str, Any]:
    """Place one durable boulder on the home settlement south exit and bind the quest."""
    node_id = str(start_node_id or (state.player or {}).get("node_id") or "")
    if not node_id:
        raise ValueError("install_boulder_quest requires start_node_id")

    existing = get_boulder(state)
    existing_quest = (state.quests or {}).get(QUEST_INSTANCE_ID)
    if existing is not None and existing_quest is not None:
        revalidate(state)
        meta = ((state.board or {}).get("g05") or {}).get("boulder_quest") or {}
        return {
            "boulder_id": BOULDER_ID,
            "quest_id": QUEST_INSTANCE_ID,
            "cause_id": meta.get("cause_id"),
            "worker_person_id": meta.get("worker_person_id") or existing_quest.get("stakeholder_id"),
            "exit_id": existing.get("exit_id"),
            "to_node": existing.get("target_node_id"),
            "from_node": existing.get("node_id"),
            "status": "deduped",
        }

    picked = _south_exit(state, node_id)
    if picked is None:
        raise ValueError(f"no south exit on {node_id}")
    target_node, link = picked
    exit_id = str(link.get("exit_id") or f"{node_id}.south")
    hold = list(link.get("hold_position") or [24.0, 46.0])
    # Sit on the path a few tiles before the exit tile.
    blocking = [float(hold[0]), max(2.0, float(hold[1]) - 6.0)]
    moved = [float(blocking[0]) + 3.0, float(blocking[1])]

    preferred = "person:16"
    worker_id = _pick_factory_worker(state, node_id, prefer_id=preferred)
    if worker_id is None:
        raise ValueError(f"no living factory worker on {node_id}")

    boulder = {
        "id": BOULDER_ID,
        "kind": "boulder",
        "mechanism_kind": "boulder",
        "label": "Boulder",
        "node_id": node_id,
        "exit_id": exit_id,
        "target_node_id": target_node,
        "position": list(blocking),
        "blocking_position": list(blocking),
        "moved_position": list(moved),
        "status": "blocking",
        "moved_by_person_id": None,
        "move_started_game_ms": None,
        "move_duration_ms": MOVE_DURATION_MS,
        "observe_far": OBSERVE_FAR,
        "observe_near": OBSERVE_NEAR_BLOCKING,
        "observe_near_moved": OBSERVE_NEAR_MOVED,
    }
    _store_boulder(state, boulder)

    template = {
        "id": TEMPLATE_ID,
        "version": 1,
        "title": "Blocked path",
        "required_cause": {"kinds": [CAUSE_KIND]},
        "binding": {"stakeholder_id": worker_id, "site_id": node_id},
        "stage_count": 4,
        "summary": "A boulder blocks one village exit; a factory worker can move it.",
    }
    tracker = CauseTracker(state)
    binder = QuestBinder(state, tracker)
    binder.register_template(template)
    observed = tracker.observe_changes(
        [
            {
                "kind": CAUSE_KIND,
                "cause_kind": CAUSE_KIND,
                "affected_entity_id": BOULDER_ID,
                "stakeholder_id": worker_id,
                "site_id": node_id,
                "template_id": TEMPLATE_ID,
                "exit_id": exit_id,
                "target_node_id": target_node,
            }
        ]
    )
    cause = observed[0]["cause"]
    bound = binder.bind(TEMPLATE_ID, cause)
    quest = dict(bound["quest"])
    # Stable instance id so dialogue / conditions do not depend on mint order.
    old_id = str(quest["id"])
    if old_id != QUEST_INSTANCE_ID:
        quest["id"] = QUEST_INSTANCE_ID
        state.quests[QUEST_INSTANCE_ID] = quest
        state.quests.pop(old_id, None)
    else:
        state.quests[QUEST_INSTANCE_ID] = quest

    quest["stage"] = 0
    quest["status"] = "offered"
    quest["stage_count"] = 4
    quest["bindings"] = {
        **dict(quest.get("bindings") or {}),
        "boulder_id": BOULDER_ID,
        "blocked_exit_id": exit_id,
        "target_node_id": target_node,
        "stakeholder_id": worker_id,
        "workplace_id": str((state.people.get(worker_id) or {}).get("workplace_id") or ""),
    }

    g05 = state.board.setdefault("g05", {})
    g05["quest_enabled"] = True
    g05["mode"] = "full_prehistoric_world_boulder_quest"
    g05["boulder_quest"] = {
        "boulder_id": BOULDER_ID,
        "quest_id": QUEST_INSTANCE_ID,
        "quest_template_id": TEMPLATE_ID,
        "cause_id": cause["id"],
        "cause_kind": CAUSE_KIND,
        "exit_id": exit_id,
        "from_node": node_id,
        "to_node": target_node,
        "worker_person_id": worker_id,
        "workplace_id": quest["bindings"]["workplace_id"],
    }
    fx = state.board.setdefault("fx_village", {})
    fx["quest_enabled"] = True
    fx["quest_id"] = QUEST_INSTANCE_ID
    fx["quest_template_id"] = TEMPLATE_ID
    fx["cause_id"] = cause["id"]
    fx["cause_template_id"] = CAUSE_TEMPLATE_ID
    fx["boulder_id"] = BOULDER_ID
    fx["mode"] = "boulder_quest"

    revalidate(state)
    return {
        "boulder_id": BOULDER_ID,
        "quest_id": QUEST_INSTANCE_ID,
        "cause_id": cause["id"],
        "worker_person_id": worker_id,
        "exit_id": exit_id,
        "to_node": target_node,
        "from_node": node_id,
    }


def talk_context(state: Any, speaker_id: str) -> dict[str, Any] | None:
    """Return dialogue quest context when this speaker is the bound worker."""
    meta = ((state.board or {}).get("g05") or {}).get("boulder_quest") or {}
    quest = (state.quests or {}).get(QUEST_INSTANCE_ID)
    if not quest or not meta:
        return None
    stakeholder = str(
        quest.get("stakeholder_id")
        or (quest.get("bindings") or {}).get("stakeholder_id")
        or meta.get("worker_person_id")
        or ""
    )
    if str(speaker_id) != stakeholder:
        return None
    boulder = get_boulder(state)
    status = str(quest.get("status") or "offered")
    stage = int(quest.get("stage") or 0)
    if status == "completed" and quest.get("completion_ack"):
        return None
    if status == "resolved_by_world":
        return {
            "quest_id": QUEST_INSTANCE_ID,
            "stage": stage,
            "cause_id": CAUSE_TEMPLATE_ID,
            "line_hint": "resolved",
        }
    # Mark completion acknowledgement when the done line is presented.
    if status == "completed" and not quest.get("completion_ack"):
        quest["completion_ack"] = True
        stage = 3
    return {
        "quest_id": TEMPLATE_ID,  # line catalog keys use template id
        "instance_id": QUEST_INSTANCE_ID,
        "stage": stage,
        "cause_id": CAUSE_TEMPLATE_ID,
        "boulder_status": str((boulder or {}).get("status") or ""),
        "quest_status": status,
    }


def accept_move(state: Any, *, effect_id: str | None = None) -> dict[str, Any]:
    """Player asked the bound worker — begin authoritative move progression."""
    quest = (state.quests or {}).get(QUEST_INSTANCE_ID)
    boulder = get_boulder(state)
    if quest is None or boulder is None:
        return {"status": "missing"}
    if str(boulder.get("status") or "") == "moved":
        QuestService(state).evaluate(QUEST_INSTANCE_ID, world_signals={"cause_cleared_by_world": True})
        return {"status": "already_moved", "quest": dict(state.quests[QUEST_INSTANCE_ID])}
    if str(boulder.get("status") or "") == "moving" or str(quest.get("status") or "") == "active":
        return {"status": "idempotent", "quest": dict(quest), "boulder": dict(boulder)}

    worker_id = str(quest.get("stakeholder_id") or (quest.get("bindings") or {}).get("stakeholder_id") or "")
    person = (state.people or {}).get(worker_id)
    if person is None or not person.get("alive", True) or person.get("status") == "dead":
        return {"status": "stakeholder_dead"}

    if str(quest.get("status") or "") == "offered":
        QuestService(state).accept(QUEST_INSTANCE_ID)

    boulder["status"] = "moving"
    boulder["moved_by_person_id"] = worker_id
    boulder["move_started_game_ms"] = int((state.clock or {}).get("game_ms") or 0)
    boulder["move_duration_ms"] = int(boulder.get("move_duration_ms") or MOVE_DURATION_MS)
    boulder["observe_near"] = OBSERVE_NEAR_BLOCKING
    _store_boulder(state, boulder)

    person["activity"] = ACTIVITY_MOVING
    person["occupation"] = "Factory worker"
    quest["stage"] = 2  # intervention
    quest["status"] = "active"
    quest["resolution"] = None
    if effect_id:
        receipts = list(quest.get("effect_receipts") or [])
        if effect_id not in receipts:
            receipts.append(effect_id)
        quest["effect_receipts"] = receipts
    return {"status": "accepted", "quest": dict(quest), "boulder": dict(boulder), "person_id": worker_id}


def complete_move(state: Any) -> dict[str, Any]:
    quest = (state.quests or {}).get(QUEST_INSTANCE_ID)
    boulder = get_boulder(state)
    if quest is None or boulder is None:
        return {"status": "missing"}
    if str(boulder.get("status") or "") == "moved" and str(quest.get("status") or "") == "completed":
        return {"status": "idempotent", "quest": dict(quest), "boulder": dict(boulder)}

    worker_id = str(boulder.get("moved_by_person_id") or quest.get("stakeholder_id") or "")
    person = (state.people or {}).get(worker_id)
    if person is not None:
        if person.get("activity") == ACTIVITY_MOVING:
            person["activity"] = "working"
        person["occupation"] = "Factory worker"

    moved_pos = list(boulder.get("moved_position") or boulder.get("position") or [27, 40])
    boulder["status"] = "moved"
    boulder["position"] = list(moved_pos)
    boulder["observe_near"] = OBSERVE_NEAR_MOVED
    boulder["observe_far"] = OBSERVE_NEAR_MOVED
    _store_boulder(state, boulder)

    if str(quest.get("status") or "") == "offered":
        # World cleared the boulder before John asked — resolve rather than complete.
        if str(boulder.get("moved_by_person_id") or "") == "":
            QuestService(state).evaluate(QUEST_INSTANCE_ID, world_signals={"cause_cleared_by_world": True})
            quest = state.quests[QUEST_INSTANCE_ID]
            quest["stage"] = 3
            quest["resolution"] = "boulder_moved"
            cause_id = str((((state.board or {}).get("g05") or {}).get("boulder_quest") or {}).get("cause_id") or "")
            if cause_id:
                CauseTracker(state).resolve(cause_id, reason="boulder_moved")
            return {"status": "resolved_by_world", "quest": dict(quest), "boulder": dict(boulder)}
        QuestService(state).accept(QUEST_INSTANCE_ID)
    quest = state.quests[QUEST_INSTANCE_ID]
    if str(quest.get("status") or "") in {"active", "suspended"}:
        QuestService(state).apply_outcome(QUEST_INSTANCE_ID, "completed")
    quest = state.quests[QUEST_INSTANCE_ID]
    quest["stage"] = 3
    quest["resolution"] = "boulder_moved"

    cause_id = str((((state.board or {}).get("g05") or {}).get("boulder_quest") or {}).get("cause_id") or "")
    if cause_id:
        CauseTracker(state).resolve(cause_id, reason="boulder_moved")

    return {"status": "completed", "quest": dict(quest), "boulder": dict(boulder)}


def tick(state: Any) -> list[dict[str, Any]]:
    """Advance boulder move from Game Time; no-op while paused (zero quanta)."""
    events: list[dict[str, Any]] = []
    boulder = get_boulder(state)
    if not boulder or str(boulder.get("status") or "") != "moving":
        return events
    game_ms = int((state.clock or {}).get("game_ms") or 0)
    start = int(boulder.get("move_started_game_ms") or 0)
    duration = int(boulder.get("move_duration_ms") or MOVE_DURATION_MS)
    if game_ms - start < duration:
        # Keep presentation position authoritative for export.
        boulder["position"] = presentation_position(boulder, game_ms=game_ms)
        _store_boulder(state, boulder)
        return events
    events.append({"kind": "boulder_moved", **complete_move(state)})
    return events


def revalidate(state: Any) -> dict[str, Any]:
    """Handle already-moved boulder / dead unbound worker without cloning."""
    quest = (state.quests or {}).get(QUEST_INSTANCE_ID)
    boulder = get_boulder(state)
    if quest is None:
        return {"status": "no_quest"}
    meta = ((state.board or {}).get("g05") or {}).setdefault("boulder_quest", {})

    if boulder and str(boulder.get("status") or "") == "moved":
        if str(quest.get("status") or "") in {"offered", "active", "suspended"}:
            QuestService(state).evaluate(QUEST_INSTANCE_ID, world_signals={"cause_cleared_by_world": True})
            return {"status": "resolved_by_world", "quest": dict(state.quests[QUEST_INSTANCE_ID])}

    if str(quest.get("status") or "") not in {"offered"}:
        return {"status": "unchanged"}

    worker_id = str(quest.get("stakeholder_id") or meta.get("worker_person_id") or "")
    person = (state.people or {}).get(worker_id)
    if person and person.get("alive", True) and person.get("status") != "dead":
        return {"status": "ok"}

    node_id = str(meta.get("from_node") or (state.player or {}).get("node_id") or "")
    replacement = _pick_factory_worker(state, node_id, prefer_id=None)
    if replacement:
        quest["stakeholder_id"] = replacement
        bindings = dict(quest.get("bindings") or {})
        bindings["stakeholder_id"] = replacement
        bindings["workplace_id"] = str((state.people.get(replacement) or {}).get("workplace_id") or "")
        quest["bindings"] = bindings
        meta["worker_person_id"] = replacement
        meta["workplace_id"] = bindings["workplace_id"]
        return {"status": "rebound", "worker_person_id": replacement}

    QuestService(state).apply_outcome(QUEST_INSTANCE_ID, "failed_with_consequence")
    quest = state.quests[QUEST_INSTANCE_ID]
    quest["resolution"] = "no_eligible_worker"
    return {"status": "failed", "quest": dict(quest)}


def worker_row_override(state: Any, person_id: str, base_row: dict[str, Any]) -> dict[str, Any]:
    """Presentation waypoints while the bound worker moves the boulder."""
    person = (state.people or {}).get(person_id) or {}
    if person.get("activity") != ACTIVITY_MOVING:
        return base_row
    boulder = get_boulder(state)
    if not boulder or str(boulder.get("status") or "") not in {"blocking", "moving"}:
        return base_row
    game_ms = int((state.clock or {}).get("game_ms") or 0)
    progress = move_progress(boulder, game_ms=game_ms)
    origin = list((base_row.get("waypoints") or [{}])[0].get("grid") or person.get("position") or [24, 24])
    target = presentation_position(boulder, game_ms=game_ms)
    cue = "moving_boulder"
    if progress >= 0.66:
        cue = "pushing_boulder"
    row = dict(base_row)
    row.update(
        {
            "cue": cue,
            "activity": ACTIVITY_MOVING,
            "occupation": "Factory worker",
            "public_occupation": "Factory worker",
            "public_role": "Factory worker",
            "waypoints": [
                {"id": "workplace", "kind": "station", "grid": [int(origin[0]), int(origin[1])]},
                {"id": BOULDER_ID, "kind": "boulder", "grid": [int(round(target[0])), int(round(target[1]))]},
            ],
            "return_waypoints": [],
            "stationary": False,
            "quest_path": True,
            "loaded": False,
        }
    )
    return row


def export_entity(state: Any, node_id: str) -> dict[str, Any] | None:
    boulder = get_boulder(state)
    if not boulder or str(boulder.get("node_id") or "") != str(node_id):
        return None
    game_ms = int((state.clock or {}).get("game_ms") or 0)
    pos = presentation_position(boulder, game_ms=game_ms)
    status = str(boulder.get("status") or "blocking")
    near = OBSERVE_NEAR_MOVED if status == "moved" else OBSERVE_NEAR_BLOCKING
    far = OBSERVE_NEAR_MOVED if status == "moved" else OBSERVE_FAR
    return {
        "kind": "boulder",
        "id": BOULDER_ID,
        "pos": [int(round(pos[0])), int(round(pos[1]))],
        "pos_f": [float(pos[0]), float(pos[1])],
        "label": "Boulder",
        "status": status,
        "exit_id": boulder.get("exit_id"),
        "target_node_id": boulder.get("target_node_id"),
        "progress": move_progress(boulder, game_ms=game_ms),
        "bridge_entity": True,
        "blocks_walk": status in {"blocking", "moving"},
        "presentation": "boulder",
        "semantic": {
            "knowledge_key": BOULDER_ID,
            "interaction": "inspect",
            "dismiss_on_move": True,
            "labels": [
                {"level": 0, "text": "Boulder"},
                {"level": 1, "text": "Boulder"},
            ],
            "observe_far": far,
            "observe_near": near,
        },
    }


def snapshot_meta(state: Any) -> dict[str, Any]:
    meta = deepcopy((((state.board or {}).get("g05") or {}).get("boulder_quest") or {}))
    boulder = get_boulder(state)
    quest = (state.quests or {}).get(QUEST_INSTANCE_ID)
    if boulder:
        meta["boulder"] = {
            "id": boulder.get("id"),
            "status": boulder.get("status"),
            "position": list(boulder.get("position") or []),
            "moved_by_person_id": boulder.get("moved_by_person_id"),
        }
    if quest:
        meta["quest_status"] = quest.get("status")
        meta["quest_stage"] = quest.get("stage")
    return meta
