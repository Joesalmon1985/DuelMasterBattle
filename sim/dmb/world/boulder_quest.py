"""G05 simple persistent blocked-exit rockfall quest.

Python owns rockfall durability, Travel gating, quest progression and helper
binding. Godot only presents the walk/push/slide. Helper Person is chosen when
the player asks an eligible village worker — never preselected at install.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sim.dmb.quests.binding import QuestBinder
from sim.dmb.quests.causes import CauseTracker
from sim.dmb.quests.runtime import QuestService

# Canonical obstruction (visual pieces are presentation components).
ROCKFALL_ID = "rockfall:1"
# Back-compat alias used by older call sites / packet notes.
BOULDER_ID = ROCKFALL_ID

TEMPLATE_ID = "quest.blocked_exit_boulder"
CAUSE_KIND = "exit_blocked_by_rockfall"
QUEST_INSTANCE_ID = "quest.blocked_exit_boulder"
CAUSE_TEMPLATE_ID = "cause.blocked_exit_boulder"

MOVE_DURATION_MS = 4500

OBSERVE_FAR = "Several large boulders block the path out of the village."
OBSERVE_NEAR_BLOCKING = (
    "The rocks are far too heavy for John to move alone. "
    "Maybe one of the workers in the village could help."
)
OBSERVE_NEAR_CLEARED = "The boulders have been rolled clear of the path."
TRAVEL_BLOCKED = "The rockfall blocks the way."

ACTIVITY_CLEARING = "Clearing rockfall"
# Alias for older activity string checks.
ACTIVITY_MOVING = ACTIVITY_CLEARING

# Status vocabulary: blocking | clearing | cleared
# (legacy "moving"/"moved" still recognised when reading saves)

# Piece offsets relative to exit hold — cover the approach corridor.
_BLOCKING_OFFSETS = (
    (-2, -4),
    (0, -5),
    (2, -4),
    (-1, -3),
    (1, -3),
)
_CLEARED_OFFSETS = (
    (-6, -4),
    (-5, -5),
    (6, -4),
    (-6, -3),
    (6, -3),
)


def _south_exit(state: Any, node_id: str) -> tuple[str, dict[str, Any]] | None:
    node = ((state.board or {}).get("nodes") or {}).get(node_id) or {}
    exits = node.get("exits") or {}
    if not isinstance(exits, dict):
        return None
    for to_node, link in exits.items():
        if str((link or {}).get("direction") or "") == "south":
            return str(to_node), dict(link)
    return None


def _norm_status(raw: str | None) -> str:
    s = str(raw or "blocking")
    if s == "moving":
        return "clearing"
    if s == "moved":
        return "cleared"
    return s


def eligible_boulder_helpers(state: Any, node_id: str) -> list[str]:
    """Living employed settlement workers on this node (not soldiers/ambient)."""
    out: list[str] = []
    for pid, person in sorted((state.people or {}).items()):
        if not _is_eligible_helper(state, pid, node_id):
            continue
        out.append(pid)
    return out


def _is_eligible_helper(state: Any, person_id: str, node_id: str) -> bool:
    person = (state.people or {}).get(person_id)
    if person is None:
        return False
    if not person.get("alive", True) or person.get("status") == "dead":
        return False
    if str(person.get("node_id") or "") != str(node_id):
        return False
    # Soldiers are Persons with units — exclude unless they also hold a workplace job.
    role = str(person.get("role") or "")
    if role in {"soldier", "commander", "wizard"}:
        return False
    if person.get("unit_id") and not person.get("workplace_id"):
        return False
    workplace = str(person.get("workplace_id") or "")
    if not workplace:
        return False
    occupation = str(person.get("occupation") or "").strip()
    if not occupation:
        return False
    return True


def get_rockfall(state: Any) -> dict[str, Any] | None:
    mechs = ((state.board or {}).get("mechanisms") or {})
    rec = mechs.get(ROCKFALL_ID) or mechs.get("boulder:1")
    return dict(rec) if isinstance(rec, dict) else None


# Back-compat
get_boulder = get_rockfall


def _store_rockfall(state: Any, rockfall: dict[str, Any]) -> None:
    mechs = state.board.setdefault("mechanisms", {})
    mechs[ROCKFALL_ID] = rockfall
    # Drop legacy single-boulder key if present.
    mechs.pop("boulder:1", None)


def rockfall_blocks_travel(state: Any, from_node: str, to_node: str) -> bool:
    rockfall = get_rockfall(state)
    if not rockfall:
        return False
    if _norm_status(rockfall.get("status")) not in {"blocking", "clearing"}:
        return False
    return (
        str(rockfall.get("node_id") or "") == str(from_node)
        and str(rockfall.get("target_node_id") or "") == str(to_node)
    )


boulder_blocks_travel = rockfall_blocks_travel


def travel_block_reason(state: Any, from_node: str, to_node: str) -> str | None:
    if rockfall_blocks_travel(state, from_node, to_node):
        return TRAVEL_BLOCKED
    return None


def move_progress(rockfall: dict[str, Any], *, game_ms: int) -> float:
    status = _norm_status(rockfall.get("status"))
    if status == "cleared":
        return 1.0
    if status != "clearing":
        return 0.0
    start = int(rockfall.get("move_started_game_ms") or 0)
    duration = max(1, int(rockfall.get("move_duration_ms") or MOVE_DURATION_MS))
    return max(0.0, min(1.0, (game_ms - start) / float(duration)))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def piece_presentation_positions(rockfall: dict[str, Any], *, game_ms: int) -> list[dict[str, Any]]:
    """Current positions for each visual stone (authoritative offsets)."""
    status = _norm_status(rockfall.get("status"))
    progress = move_progress(rockfall, game_ms=game_ms)
    slide_t = 0.0 if progress < 0.66 else (progress - 0.66) / 0.34
    out: list[dict[str, Any]] = []
    for piece in rockfall.get("pieces") or []:
        blocking = list(piece.get("blocking_position") or piece.get("position") or [24, 40])
        cleared = list(piece.get("cleared_position") or blocking)
        if status == "cleared":
            pos = [float(cleared[0]), float(cleared[1])]
        elif status == "clearing":
            pos = [
                _lerp(float(blocking[0]), float(cleared[0]), slide_t),
                _lerp(float(blocking[1]), float(cleared[1]), slide_t),
            ]
        else:
            pos = [float(blocking[0]), float(blocking[1])]
        out.append(
            {
                "id": piece.get("id"),
                "pos": pos,
                "pos_i": [int(round(pos[0])), int(round(pos[1]))],
                "blocking_position": blocking,
                "cleared_position": cleared,
            }
        )
    return out


def blocked_tiles(rockfall: dict[str, Any], *, game_ms: int | None = None) -> list[list[int]]:
    """Tiles that must block local walk while the rockfall obstructs."""
    if _norm_status(rockfall.get("status")) not in {"blocking", "clearing"}:
        return []
    ms = int(game_ms if game_ms is not None else 0)
    tiles: list[list[int]] = []
    seen: set[tuple[int, int]] = set()
    for piece in piece_presentation_positions(rockfall, game_ms=ms):
        # While clearing, keep blocking the original corridor until slide finishes.
        if _norm_status(rockfall.get("status")) == "clearing":
            bp = piece["blocking_position"]
            key = (int(round(float(bp[0]))), int(round(float(bp[1]))))
        else:
            key = (piece["pos_i"][0], piece["pos_i"][1])
        if key in seen:
            continue
        seen.add(key)
        tiles.append([key[0], key[1]])
    return tiles


def _build_pieces(hold: list[float]) -> list[dict[str, Any]]:
    hx, hy = float(hold[0]), float(hold[1])
    pieces: list[dict[str, Any]] = []
    for i, ((bx, by), (cx, cy)) in enumerate(zip(_BLOCKING_OFFSETS, _CLEARED_OFFSETS)):
        blocking = [hx + bx, hy + by]
        cleared = [hx + cx, hy + cy]
        pieces.append(
            {
                "id": f"{ROCKFALL_ID}.stone:{i + 1}",
                "blocking_position": blocking,
                "cleared_position": cleared,
                "position": list(blocking),
            }
        )
    return pieces


def install_boulder_quest(state: Any, *, start_node_id: str | None = None) -> dict[str, Any]:
    """Place a durable rockfall on the home settlement south exit; no helper yet."""
    node_id = str(start_node_id or (state.player or {}).get("node_id") or "")
    if not node_id:
        raise ValueError("install_boulder_quest requires start_node_id")

    existing = get_rockfall(state)
    existing_quest = (state.quests or {}).get(QUEST_INSTANCE_ID)
    if existing is not None and existing_quest is not None:
        revalidate(state)
        meta = ((state.board or {}).get("g05") or {}).get("boulder_quest") or {}
        return {
            "rockfall_id": ROCKFALL_ID,
            "boulder_id": ROCKFALL_ID,
            "quest_id": QUEST_INSTANCE_ID,
            "cause_id": meta.get("cause_id"),
            "helper_person_id": meta.get("helper_person_id"),
            "exit_id": existing.get("exit_id"),
            "to_node": existing.get("target_node_id"),
            "from_node": existing.get("node_id"),
            "status": "deduped",
            "eligible_helpers": eligible_boulder_helpers(state, node_id),
        }

    helpers = eligible_boulder_helpers(state, node_id)
    if not helpers:
        raise ValueError(f"no eligible village workers on {node_id}")

    picked = _south_exit(state, node_id)
    if picked is None:
        raise ValueError(f"no south exit on {node_id}")
    target_node, link = picked
    exit_id = str(link.get("exit_id") or f"{node_id}.south")
    hold = list(link.get("hold_position") or [24.0, 46.0])
    pieces = _build_pieces(hold)
    # Anchor at corridor centre (middle stone).
    anchor = list(pieces[1]["blocking_position"])

    rockfall = {
        "id": ROCKFALL_ID,
        "kind": "rockfall",
        "mechanism_kind": "rockfall",
        "label": "Rockfall",
        "node_id": node_id,
        "exit_id": exit_id,
        "target_node_id": target_node,
        "position": list(anchor),
        "blocking_position": list(anchor),
        "hold_position": [float(hold[0]), float(hold[1])],
        "pieces": pieces,
        "status": "blocking",
        "helper_person_id": None,
        "moved_by_person_id": None,
        "move_started_game_ms": None,
        "move_duration_ms": MOVE_DURATION_MS,
        "observe_far": OBSERVE_FAR,
        "observe_near": OBSERVE_NEAR_BLOCKING,
        "observe_near_moved": OBSERVE_NEAR_CLEARED,
        "observe_near_cleared": OBSERVE_NEAR_CLEARED,
    }
    _store_rockfall(state, rockfall)

    template = {
        "id": TEMPLATE_ID,
        "version": 2,
        "title": "Blocked path",
        "required_cause": {"kinds": [CAUSE_KIND, "exit_blocked_by_boulder"]},
        "binding": {"site_id": node_id},
        "stage_count": 4,
        "summary": "A rockfall blocks one village exit; any village worker can clear it.",
    }
    tracker = CauseTracker(state)
    binder = QuestBinder(state, tracker)
    binder.register_template(template)
    observed = tracker.observe_changes(
        [
            {
                "kind": CAUSE_KIND,
                "cause_kind": CAUSE_KIND,
                "affected_entity_id": ROCKFALL_ID,
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
    quest["stakeholder_id"] = None
    quest["helper_person_id"] = None
    quest["bindings"] = {
        **dict(quest.get("bindings") or {}),
        "rockfall_id": ROCKFALL_ID,
        "boulder_id": ROCKFALL_ID,
        "blocked_exit_id": exit_id,
        "target_node_id": target_node,
        "site_id": node_id,
        "stakeholder_id": None,
        "helper_person_id": None,
    }

    g05 = state.board.setdefault("g05", {})
    g05["quest_enabled"] = True
    g05["mode"] = "full_prehistoric_world_boulder_quest"
    g05["boulder_quest"] = {
        "rockfall_id": ROCKFALL_ID,
        "boulder_id": ROCKFALL_ID,
        "quest_id": QUEST_INSTANCE_ID,
        "quest_template_id": TEMPLATE_ID,
        "cause_id": cause["id"],
        "cause_kind": CAUSE_KIND,
        "exit_id": exit_id,
        "from_node": node_id,
        "to_node": target_node,
        "helper_person_id": None,
        "eligible_helper_count": len(helpers),
    }
    fx = state.board.setdefault("fx_village", {})
    fx["quest_enabled"] = True
    fx["quest_id"] = QUEST_INSTANCE_ID
    fx["quest_template_id"] = TEMPLATE_ID
    fx["cause_id"] = cause["id"]
    fx["cause_template_id"] = CAUSE_TEMPLATE_ID
    fx["boulder_id"] = ROCKFALL_ID
    fx["rockfall_id"] = ROCKFALL_ID
    fx["mode"] = "boulder_quest"

    revalidate(state)
    return {
        "rockfall_id": ROCKFALL_ID,
        "boulder_id": ROCKFALL_ID,
        "quest_id": QUEST_INSTANCE_ID,
        "cause_id": cause["id"],
        "helper_person_id": None,
        "exit_id": exit_id,
        "to_node": target_node,
        "from_node": node_id,
        "eligible_helpers": helpers,
    }


def talk_context(state: Any, speaker_id: str) -> dict[str, Any] | None:
    """Dialogue context for eligible workers / chosen helper — reads world state only."""
    meta = ((state.board or {}).get("g05") or {}).get("boulder_quest") or {}
    quest = (state.quests or {}).get(QUEST_INSTANCE_ID)
    if not quest or not meta:
        return None
    node_id = str(meta.get("from_node") or (state.player or {}).get("node_id") or "")
    rockfall = get_rockfall(state)
    rock_status = _norm_status((rockfall or {}).get("status"))
    q_status = str(quest.get("status") or "offered")
    helper = str(
        quest.get("helper_person_id")
        or (quest.get("bindings") or {}).get("helper_person_id")
        or meta.get("helper_person_id")
        or ((rockfall or {}).get("helper_person_id") if rockfall else "")
        or ""
    )

    # Completion dialogue only when the world is actually clear.
    if q_status == "completed" and rock_status == "cleared":
        if quest.get("completion_ack"):
            return None
        if str(speaker_id) != helper:
            return None
        if rockfall_blocks_travel(state, node_id, str(meta.get("to_node") or "")):
            return None
        return {
            "quest_id": TEMPLATE_ID,
            "instance_id": QUEST_INSTANCE_ID,
            "stage": 3,
            "cause_id": CAUSE_TEMPLATE_ID,
            "rockfall_status": rock_status,
            "quest_status": q_status,
            "line_hint": "done",
        }

    if q_status == "resolved_by_world":
        return None

    if q_status == "active" and rock_status == "clearing":
        if str(speaker_id) == helper:
            return {
                "quest_id": TEMPLATE_ID,
                "instance_id": QUEST_INSTANCE_ID,
                "stage": 2,
                "cause_id": CAUSE_TEMPLATE_ID,
                "rockfall_status": rock_status,
                "quest_status": q_status,
                "line_hint": "clearing",
            }
        # Other workers: optional watching line (stage 1).
        if _is_eligible_helper(state, speaker_id, node_id):
            return {
                "quest_id": TEMPLATE_ID,
                "instance_id": QUEST_INSTANCE_ID,
                "stage": 1,
                "cause_id": CAUSE_TEMPLATE_ID,
                "rockfall_status": rock_status,
                "quest_status": q_status,
                "line_hint": "other_watching",
            }
        return None

    if q_status == "offered" and rock_status == "blocking":
        if not _is_eligible_helper(state, speaker_id, node_id):
            return None
        return {
            "quest_id": TEMPLATE_ID,
            "instance_id": QUEST_INSTANCE_ID,
            "stage": 0,
            "cause_id": CAUSE_TEMPLATE_ID,
            "rockfall_status": rock_status,
            "quest_status": q_status,
            "line_hint": "offer",
        }

    return None


def mark_completion_ack(state: Any, *, session: dict[str, Any] | None = None) -> None:
    """Set completion_ack only after the done line was actually presented."""
    quest = (state.quests or {}).get(QUEST_INSTANCE_ID)
    if not quest:
        return
    rockfall = get_rockfall(state)
    if str(quest.get("status") or "") != "completed":
        return
    if _norm_status((rockfall or {}).get("status")) != "cleared":
        return
    if session is not None:
        line_id = str(session.get("line_id") or "")
        stage = session.get("stage")
        if line_id != "dialogue.boulder.done" and stage != 3:
            return
    quest["completion_ack"] = True


def accept_move(
    state: Any,
    *,
    helper_person_id: str | None = None,
    effect_id: str | None = None,
) -> dict[str, Any]:
    """Player asked an eligible worker — bind helper and begin clearing."""
    quest = (state.quests or {}).get(QUEST_INSTANCE_ID)
    rockfall = get_rockfall(state)
    if quest is None or rockfall is None:
        return {"status": "missing"}
    meta = ((state.board or {}).get("g05") or {}).setdefault("boulder_quest", {})
    node_id = str(meta.get("from_node") or rockfall.get("node_id") or "")

    if _norm_status(rockfall.get("status")) == "cleared":
        QuestService(state).evaluate(QUEST_INSTANCE_ID, world_signals={"cause_cleared_by_world": True})
        return {"status": "already_cleared", "quest": dict(state.quests[QUEST_INSTANCE_ID])}

    existing_helper = str(
        quest.get("helper_person_id")
        or (quest.get("bindings") or {}).get("helper_person_id")
        or meta.get("helper_person_id")
        or ""
    )
    if _norm_status(rockfall.get("status")) == "clearing" or str(quest.get("status") or "") == "active":
        return {
            "status": "idempotent",
            "quest": dict(quest),
            "rockfall": dict(rockfall),
            "helper_person_id": existing_helper,
        }

    helper = str(helper_person_id or existing_helper or "")
    if not helper or not _is_eligible_helper(state, helper, node_id):
        return {"status": "ineligible_helper", "helper_person_id": helper}

    person = state.people[helper]
    if str(quest.get("status") or "") == "offered":
        QuestService(state).accept(QUEST_INSTANCE_ID)

    rockfall["status"] = "clearing"
    rockfall["helper_person_id"] = helper
    rockfall["moved_by_person_id"] = helper
    rockfall["move_started_game_ms"] = int((state.clock or {}).get("game_ms") or 0)
    rockfall["move_duration_ms"] = int(rockfall.get("move_duration_ms") or MOVE_DURATION_MS)
    rockfall["observe_near"] = OBSERVE_NEAR_BLOCKING
    _store_rockfall(state, rockfall)

    person["activity"] = ACTIVITY_CLEARING
    # Occupation unchanged.

    quest = state.quests[QUEST_INSTANCE_ID]
    quest["stage"] = 2
    quest["status"] = "active"
    quest["stakeholder_id"] = helper
    quest["helper_person_id"] = helper
    quest["resolution"] = None
    bindings = dict(quest.get("bindings") or {})
    bindings["stakeholder_id"] = helper
    bindings["helper_person_id"] = helper
    bindings["workplace_id"] = str(person.get("workplace_id") or "")
    quest["bindings"] = bindings
    meta["helper_person_id"] = helper
    meta["workplace_id"] = bindings["workplace_id"]

    if effect_id:
        receipts = list(quest.get("effect_receipts") or [])
        if effect_id not in receipts:
            receipts.append(effect_id)
        quest["effect_receipts"] = receipts

    return {
        "status": "accepted",
        "quest": dict(quest),
        "rockfall": dict(rockfall),
        "helper_person_id": helper,
        "person_id": helper,
    }


accept_clear = accept_move


def complete_move(state: Any) -> dict[str, Any]:
    quest = (state.quests or {}).get(QUEST_INSTANCE_ID)
    rockfall = get_rockfall(state)
    if quest is None or rockfall is None:
        return {"status": "missing"}
    if _norm_status(rockfall.get("status")) == "cleared" and str(quest.get("status") or "") == "completed":
        return {"status": "idempotent", "quest": dict(quest), "rockfall": dict(rockfall)}

    helper = str(
        rockfall.get("helper_person_id")
        or quest.get("helper_person_id")
        or quest.get("stakeholder_id")
        or ""
    )
    person = (state.people or {}).get(helper)
    if person is not None and person.get("activity") == ACTIVITY_CLEARING:
        person["activity"] = "working"

    for piece in rockfall.get("pieces") or []:
        cleared = list(piece.get("cleared_position") or piece.get("position") or [])
        piece["position"] = list(cleared)
    rockfall["status"] = "cleared"
    if rockfall.get("pieces"):
        rockfall["position"] = list(rockfall["pieces"][1].get("position") or rockfall.get("position"))
    rockfall["observe_near"] = OBSERVE_NEAR_CLEARED
    rockfall["observe_far"] = OBSERVE_NEAR_CLEARED
    _store_rockfall(state, rockfall)

    if str(quest.get("status") or "") == "offered":
        if not helper:
            QuestService(state).evaluate(QUEST_INSTANCE_ID, world_signals={"cause_cleared_by_world": True})
            quest = state.quests[QUEST_INSTANCE_ID]
            quest["stage"] = 3
            quest["resolution"] = "rockfall_cleared"
            cause_id = str((((state.board or {}).get("g05") or {}).get("boulder_quest") or {}).get("cause_id") or "")
            if cause_id:
                CauseTracker(state).resolve(cause_id, reason="rockfall_cleared")
            return {"status": "resolved_by_world", "quest": dict(quest), "rockfall": dict(rockfall)}
        QuestService(state).accept(QUEST_INSTANCE_ID)
    quest = state.quests[QUEST_INSTANCE_ID]
    if str(quest.get("status") or "") in {"active", "suspended"}:
        QuestService(state).apply_outcome(QUEST_INSTANCE_ID, "completed")
    quest = state.quests[QUEST_INSTANCE_ID]
    quest["stage"] = 3
    quest["resolution"] = "rockfall_cleared"

    cause_id = str((((state.board or {}).get("g05") or {}).get("boulder_quest") or {}).get("cause_id") or "")
    if cause_id:
        CauseTracker(state).resolve(cause_id, reason="rockfall_cleared")

    return {"status": "completed", "quest": dict(quest), "rockfall": dict(rockfall)}


def tick(state: Any) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    rockfall = get_rockfall(state)
    if not rockfall or _norm_status(rockfall.get("status")) != "clearing":
        return events
    game_ms = int((state.clock or {}).get("game_ms") or 0)
    start = int(rockfall.get("move_started_game_ms") or 0)
    duration = int(rockfall.get("move_duration_ms") or MOVE_DURATION_MS)
    if game_ms - start < duration:
        for piece, presented in zip(rockfall.get("pieces") or [], piece_presentation_positions(rockfall, game_ms=game_ms)):
            piece["position"] = list(presented["pos"])
        rockfall["position"] = list((rockfall.get("pieces") or [{}])[1].get("position") or rockfall.get("position"))
        _store_rockfall(state, rockfall)
        return events
    events.append({"kind": "rockfall_cleared", **complete_move(state)})
    return events


def revalidate(state: Any) -> dict[str, Any]:
    quest = (state.quests or {}).get(QUEST_INSTANCE_ID)
    rockfall = get_rockfall(state)
    if quest is None:
        return {"status": "no_quest"}
    meta = ((state.board or {}).get("g05") or {}).setdefault("boulder_quest", {})

    if rockfall and _norm_status(rockfall.get("status")) == "cleared":
        if str(quest.get("status") or "") in {"offered", "active", "suspended"}:
            QuestService(state).evaluate(QUEST_INSTANCE_ID, world_signals={"cause_cleared_by_world": True})
            return {"status": "resolved_by_world", "quest": dict(state.quests[QUEST_INSTANCE_ID])}

    if str(quest.get("status") or "") == "active":
        helper = str(quest.get("helper_person_id") or meta.get("helper_person_id") or "")
        person = (state.people or {}).get(helper)
        if helper and (person is None or not person.get("alive", True) or person.get("status") == "dead"):
            QuestService(state).suspend(QUEST_INSTANCE_ID, reason="helper_dead")
            return {"status": "suspended", "quest": dict(state.quests[QUEST_INSTANCE_ID])}
        return {"status": "ok"}

    # Offered: no helper bound yet — ensure at least one eligible worker exists.
    if str(quest.get("status") or "") == "offered":
        node_id = str(meta.get("from_node") or (state.player or {}).get("node_id") or "")
        helpers = eligible_boulder_helpers(state, node_id)
        meta["eligible_helper_count"] = len(helpers)
        if not helpers:
            QuestService(state).apply_outcome(QUEST_INSTANCE_ID, "failed_with_consequence")
            quest = state.quests[QUEST_INSTANCE_ID]
            quest["resolution"] = "no_eligible_worker"
            return {"status": "failed", "quest": dict(quest)}
        return {"status": "ok", "eligible_helpers": helpers}

    return {"status": "unchanged"}


def worker_row_override(state: Any, person_id: str, base_row: dict[str, Any]) -> dict[str, Any]:
    person = (state.people or {}).get(person_id) or {}
    if person.get("activity") != ACTIVITY_CLEARING:
        return base_row
    rockfall = get_rockfall(state)
    if not rockfall or _norm_status(rockfall.get("status")) not in {"blocking", "clearing"}:
        return base_row
    game_ms = int((state.clock or {}).get("game_ms") or 0)
    progress = move_progress(rockfall, game_ms=game_ms)
    origin = list((base_row.get("waypoints") or [{}])[0].get("grid") or person.get("position") or [24, 24])
    pieces = piece_presentation_positions(rockfall, game_ms=game_ms)
    target = pieces[1]["pos"] if pieces else list(rockfall.get("position") or [24, 40])
    cue = "clearing_rockfall"
    if progress >= 0.66:
        cue = "pushing_rockfall"
    occupation = str(base_row.get("public_occupation") or person.get("occupation") or "Worker")
    row = dict(base_row)
    row.update(
        {
            "cue": cue,
            "activity": ACTIVITY_CLEARING,
            "occupation": occupation,
            "public_occupation": occupation,
            "public_role": occupation,
            "waypoints": [
                {"id": "workplace", "kind": "station", "grid": [int(origin[0]), int(origin[1])]},
                {"id": ROCKFALL_ID, "kind": "rockfall", "grid": [int(round(target[0])), int(round(target[1]))]},
            ],
            "return_waypoints": [],
            "stationary": False,
            "quest_path": True,
            "loaded": False,
        }
    )
    return row


def export_entity(state: Any, node_id: str) -> dict[str, Any] | None:
    rockfall = get_rockfall(state)
    if not rockfall or str(rockfall.get("node_id") or "") != str(node_id):
        return None
    game_ms = int((state.clock or {}).get("game_ms") or 0)
    status = _norm_status(rockfall.get("status"))
    pieces = piece_presentation_positions(rockfall, game_ms=game_ms)
    anchor = pieces[1]["pos"] if len(pieces) > 1 else list(rockfall.get("position") or [24, 40])
    near = OBSERVE_NEAR_CLEARED if status == "cleared" else OBSERVE_NEAR_BLOCKING
    far = OBSERVE_NEAR_CLEARED if status == "cleared" else OBSERVE_FAR
    block = status in {"blocking", "clearing"}
    return {
        "kind": "rockfall",
        "id": ROCKFALL_ID,
        "pos": [int(round(anchor[0])), int(round(anchor[1]))],
        "pos_f": [float(anchor[0]), float(anchor[1])],
        "label": "Rockfall",
        "status": status,
        "exit_id": rockfall.get("exit_id"),
        "target_node_id": rockfall.get("target_node_id"),
        "progress": move_progress(rockfall, game_ms=game_ms),
        "pieces": [
            {
                "id": p["id"],
                "pos": p["pos_i"],
                "pos_f": p["pos"],
            }
            for p in pieces
        ],
        "blocked_tiles": blocked_tiles(rockfall, game_ms=game_ms) if block else [],
        "bridge_entity": True,
        "blocks_walk": block,
        "presentation": "rockfall",
        "semantic": {
            "knowledge_key": ROCKFALL_ID,
            "interaction": "inspect",
            "dismiss_on_move": True,
            "labels": [
                {"level": 0, "text": "Rockfall"},
                {"level": 1, "text": "Rockfall"},
            ],
            "observe_far": far,
            "observe_near": near,
        },
    }


def snapshot_meta(state: Any) -> dict[str, Any]:
    meta = deepcopy((((state.board or {}).get("g05") or {}).get("boulder_quest") or {}))
    rockfall = get_rockfall(state)
    quest = (state.quests or {}).get(QUEST_INSTANCE_ID)
    if rockfall:
        meta["rockfall"] = {
            "id": rockfall.get("id"),
            "status": _norm_status(rockfall.get("status")),
            "helper_person_id": rockfall.get("helper_person_id"),
            "pieces": [
                {
                    "id": p.get("id"),
                    "position": list(p.get("position") or []),
                    "blocking_position": list(p.get("blocking_position") or []),
                    "cleared_position": list(p.get("cleared_position") or []),
                }
                for p in (rockfall.get("pieces") or [])
            ],
        }
    if quest:
        meta["quest_status"] = quest.get("status")
        meta["quest_stage"] = quest.get("stage")
        meta["helper_person_id"] = quest.get("helper_person_id")
    return meta
