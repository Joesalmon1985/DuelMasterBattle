from __future__ import annotations

from typing import Any

from ..ensemble.policies import WRITER_POLICIES

CLIP = 320
HISTORY_CLIP = 420


def _clip(value: Any, limit: int = CLIP) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _profile_map(scene: dict) -> dict[str, dict]:
    return {p.get("character_id"): p for p in scene.get("participant_profiles") or [] if p.get("character_id")}


def _compact_voice(profile: dict) -> dict[str, str]:
    voice = profile.get("voice") or {}
    return {key: _clip(voice.get(key), 160) for key in ("register", "sentence_shape", "vocabulary_domain", "verbal_tic", "humour_style", "silence_behaviour")}


def _compact_psychology(profile: dict) -> dict[str, str]:
    psych = profile.get("psychology") or {}
    keys = (
        "core_desire",
        "immediate_want",
        "core_fear",
        "central_contradiction",
        "moral_boundary",
        "false_belief",
        "pressure_behaviour",
        "repair_behaviour",
        "social_mask",
        "self_image",
        "specific_regret",
        "specific_hope",
        "misjudges_others_by",
    )
    return {key: _clip(psych.get(key)) for key in keys}


def _compact_participant(profile: dict, scene: dict) -> dict:
    knowledge = profile.get("knowledge") or {}
    return {
        "character_id": profile.get("character_id"),
        "display_name": profile.get("display_name"),
        "role": profile.get("role"),
        "narrative_tier": profile.get("narrative_tier"),
        "district": profile.get("district"),
        "home_or_base": profile.get("home_or_base"),
        "presence_reason": scene.get("presence_reasons", {}).get(profile.get("character_id")) or profile.get("presence_reason") or "",
        "voice": _compact_voice(profile),
        "psychology": _compact_psychology(profile),
        "knowledge_boundary": _clip(knowledge.get("boundary"), 260),
        "what_they_notice": _clip(knowledge.get("what_they_notice"), 180),
        "what_they_miss": _clip(knowledge.get("what_they_miss"), 180),
    }


def _compact_history(edge: dict) -> dict:
    return {
        "relationship_id": edge.get("relationship_id"),
        "source_id": edge.get("source_id"),
        "target_id": edge.get("target_id"),
        "type": edge.get("type"),
        "reciprocity": edge.get("reciprocity"),
        "contact_reason": edge.get("contact_reason") or "",
        "origin_event": _clip(edge.get("origin_event"), HISTORY_CLIP),
        "shared_history": _clip(edge.get("shared_history") or edge.get("description"), HISTORY_CLIP),
        "public_story": _clip(edge.get("public_story"), 240),
        "private_truth": _clip(edge.get("private_truth"), HISTORY_CLIP),
        "current_tension": _clip(edge.get("current_tension"), 240),
        "reason_for_presence": _clip(edge.get("reason_for_presence"), 240),
    }


def _predecessor_summary(predecessor: dict | None) -> dict | None:
    if not predecessor:
        return None
    return {
        "scene_id": predecessor.get("scene_id"),
        "scene_type": predecessor.get("scene_type"),
        "district": predecessor.get("district"),
        "location": predecessor.get("location"),
        "primary_character_id": predecessor.get("primary_character_id"),
        "participant_ids": list(predecessor.get("participant_ids") or []),
        "dramatic_problem": _clip(predecessor.get("dramatic_problem"), 360),
        "possible_outcomes": list(predecessor.get("possible_outcomes") or [])[:6],
    }


def compile_scene_packet(
    scene: dict,
    *,
    catalogue: list[dict] | None = None,
    policies: dict[str, str] | None = None,
) -> dict:
    """Build one compact writer packet. Never include the full catalogue or CSV."""
    profiles = _profile_map(scene)
    policy_map = policies or WRITER_POLICIES
    refs = list(scene.get("policy_refs") or [])
    reveal = scene.get("reveal_policy") or {}
    private = scene.get("private_facts_for_writer_only") or {}
    forbidden = list(scene.get("forbidden_revelations") or [])
    permitted: list[str] = []
    if reveal.get("primary_secret_may_be_revealed"):
        primary = profiles.get(scene.get("primary_character_id"), {})
        secret = ((primary.get("private") or {}).get("secret")) or ""
        if secret:
            permitted.append(_clip(secret, 240))

    predecessor = None
    trigger = scene.get("trigger") or {}
    if scene.get("scene_type") == "consequence" and trigger.get("required_scene_id") and catalogue:
        pred_id = trigger.get("required_scene_id")
        predecessor = next((item for item in catalogue if item.get("scene_id") == pred_id), None)

    quest = scene.get("quest_material") or {}
    puzzle = scene.get("puzzle_material") or {}

    packet = {
        "schema_version": "dmb-ensemble-writer-packet-v1",
        "scene_id": scene.get("scene_id"),
        "SCENE_FUNCTION": {
            "scene_type": scene.get("scene_type"),
            "location": scene.get("location"),
            "district": scene.get("district"),
            "primary_character_id": scene.get("primary_character_id"),
            "dramatic_problem": scene.get("dramatic_problem"),
            "scene_requirements": list(scene.get("scene_requirements") or []),
            "player_affordances": list(scene.get("player_affordances") or []),
            "possible_outcomes": list(scene.get("possible_outcomes") or []),
        },
        "CANONICAL_FACTS": {
            "participant_ids": list(scene.get("participant_ids") or []),
            "presence_reasons": dict(scene.get("presence_reasons") or {}),
            "knowledge_boundaries": {
                pid: _clip((profiles.get(pid, {}).get("knowledge") or {}).get("boundary") or (scene.get("knowledge_boundaries") or {}).get(pid), 260)
                for pid in scene.get("participant_ids") or []
            },
            "trigger": trigger,
            "predecessor": _predecessor_summary(predecessor),
            "policy_refs": refs,
            "policy_text": {key: policy_map[key] for key in refs if key in policy_map},
        },
        "WRITER_ONLY_PRIVATE_FACTS": {
            pid: [_clip(item, 240) for item in (private.get(pid) or []) if str(item).strip()]
            for pid in scene.get("participant_ids") or []
        },
        "PERMITTED_REVELATIONS": permitted,
        "FORBIDDEN_REVELATIONS": [_clip(item, 240) for item in forbidden],
        "CHARACTER_OBJECTIVES": dict(scene.get("character_objectives") or {}),
        "RELATIONSHIP_HISTORY": [_compact_history(edge) for edge in scene.get("relationship_context") or []],
        "participants": [_compact_participant(profiles[pid], scene) for pid in scene.get("participant_ids") or [] if pid in profiles],
        "quest_context": {
            "hook": _clip(quest.get("hook"), 360),
            "complication": _clip(quest.get("complication"), 360),
            "alternate_solution": _clip(quest.get("alternate_solution"), 420),
            "primary_solution": _clip(quest.get("primary_solution"), 320),
            "who_benefits": quest.get("who_benefits") or "",
            "who_pays": quest.get("who_pays") or "",
        },
        "puzzle_context": {
            "type": puzzle.get("type") or "",
            "logic": _clip(puzzle.get("logic"), 240),
            "clue_source": _clip(puzzle.get("clue_source"), 200),
        },
        "authoring_limits": {
            "may_vary": ["wording", "emotional interpretation", "subtext", "pacing", "humour", "gestures"],
            "must_not_change": [
                "identity",
                "relationship state",
                "known facts",
                "witnessed events",
                "inventory",
                "quest progression",
                "history",
                "secrets",
                "world state",
            ],
            "no_worldview_labels_in_spoken_text": True,
            "python_owns_canonical_state": True,
        },
    }
    return packet


def packet_contains_catalogue(packet: dict, catalogue_size: int) -> bool:
    blob = str(packet)
    return catalogue_size > 20 and blob.count("SCN_") > 8
