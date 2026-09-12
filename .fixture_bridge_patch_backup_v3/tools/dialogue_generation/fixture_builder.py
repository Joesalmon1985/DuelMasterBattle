from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .config import config
from .workbook_reader import BeatInstance, SourceRow, extract_beats, read_cast_rows, workbook_sha256


# The builder deliberately does not call an LLM.  It consumes an already-approved
# Dialogue Factory export and the same canonical workbook rows used to generate it.


@dataclass
class CastMember:
    id: str
    name: str
    village_role: str
    story_role: str
    personality_summary: str
    anchor: str
    sprite: str
    pos_offset: list[int]
    dialogue_context: str

    def as_json(self, quest_id: str) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.village_role,
            "occupation": self.village_role,
            "home_anchor": self.anchor,
            "work_anchor": self.anchor,
            "sprite": self.sprite,
            "archetype": _slug(self.village_role) or "villager",
            "relationships": {},
            "quest_participation": [quest_id],
            "dialogue_context": self.dialogue_context,
            "story_role": self.story_role,
            "personality_summary": self.personality_summary,
            "pos_offset": self.pos_offset,
        }


@dataclass
class FixtureBuild:
    cast_id: str
    village: dict[str, Any]
    cast: dict[str, Any]
    quest: dict[str, Any]
    dialogue: dict[str, Any]
    stats: dict[str, Any] = field(default_factory=dict)


class FixtureBuildError(RuntimeError):
    pass


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")
    return text or "unknown"


def _flag(value: str) -> str:
    return _slug(value)[:80]


def _economic_profile(cast_id: str) -> str:
    m = re.match(r"^([A-Za-z]+\d+)", cast_id)
    return m.group(1).upper() if m else cast_id.upper()


def _infer_resources(rows: Iterable[SourceRow], cast_id: str) -> list[str]:
    # E17 is the known Wood + Grain + Ore profile.  Other profiles are inferred
    # from the canonical cast roles so the builder remains useful without a giant
    # hard-coded table of 100+ economic profiles.
    if _economic_profile(cast_id) == "E17":
        return ["Wood", "Grain", "Ore"]
    joined = " ".join(r.village_role.lower() for r in rows)
    out: list[str] = []
    checks = [
        ("Wood", ("wood", "forester", "logger", "saw")),
        ("Grain", ("farmer", "grain", "miller", "mill", "baker")),
        ("Ore", ("miner", "mine", "ore", "smith", "blacksmith")),
        ("Pasture", ("shepherd", "herd", "cattle", "goat", "wool")),
        ("Fish", ("fish", "fisher", "boat")),
        ("Clay", ("potter", "clay", "kiln")),
    ]
    for resource, needles in checks:
        if any(n in joined for n in needles):
            out.append(resource)
    return out or ["Mixed"]


def _anchor_for_role(role: str) -> str:
    r = role.lower()
    mapping = [
        (("reeve", "mayor", "chief", "magistrate", "steward", "guard"), "village_hall"),
        (("healer", "physician", "herbal"), "healer_house"),
        (("priest", "priestess", "shrine", "cleric"), "old_shrine"),
        (("tavern", "innkeeper", "inn keeper", "publican"), "tavern"),
        (("merchant", "store", "shopkeeper", "trader"), "general_store"),
        (("potter", "clay"), "pottery"),
        (("blacksmith", "smith", "forge"), "forge"),
        (("miller", "mill"), "mill"),
        (("farmer", "farm", "reaper", "grain"), "farmstead"),
        (("woodcutter", "forester", "logger", "woodsman"), "logging_camp"),
        (("miner", "ore", "quarry"), "mine_mouth"),
        (("scavenger", "salvage"), "workshop"),
        (("elder",), "old_shrine"),
    ]
    for needles, anchor in mapping:
        if any(n in r for n in needles):
            return anchor
    return "village_square"


def _sprite_for_role(role: str) -> str:
    r = role.lower()
    # These are conservative sprite keys already used in production content.
    if any(x in r for x in ("reeve", "mayor", "chief", "guard", "steward")):
        return "official"
    if any(x in r for x in ("elder", "priest", "priestess")):
        return "elder"
    if any(x in r for x in ("miner", "ore", "quarry")):
        return "dwarf"
    return "villager_b"


def _load_export(path: Path, cast_id: str) -> dict[str, Any]:
    if not path.exists():
        raise FixtureBuildError(
            f"Dialogue export not found: {path}. Run 'Run Dialogue Factory.bat export --cast-id {cast_id}' first."
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FixtureBuildError(f"Malformed dialogue export {path}: {exc}") from exc
    if payload.get("cast_id") != cast_id:
        raise FixtureBuildError(
            f"Dialogue export cast_id mismatch: expected {cast_id}, got {payload.get('cast_id')!r}"
        )
    if not isinstance(payload.get("banks"), list) or not payload["banks"]:
        raise FixtureBuildError(f"Dialogue export for {cast_id} contains no approved banks")
    return payload


DEFAULT_WORLDVIEW_ORDER = ["guildist", "monarchist", "religious", "druidic", "arcane", "anarchist", "cracked"]


def _rank_response(response: dict[str, Any], preferred_worldview: str | None) -> tuple:
    worldview = str(response.get("worldview", ""))
    worldview_match = int(bool(preferred_worldview) and worldview == preferred_worldview)
    context_fit = int(response.get("context_fit", 0) or 0)
    scores = response.get("scores", {})
    score_total = 0.0
    if isinstance(scores, dict):
        score_total = sum(float(v) for v in scores.values() if isinstance(v, (int, float)))
    # Lower conviction is a modest tie-breaker: it tends to keep the first
    # fixture playthrough readable while context-fit remains authoritative.
    conviction = int(response.get("conviction_tier", 4) or 4)
    try:
        worldview_priority = -DEFAULT_WORLDVIEW_ORDER.index(worldview)
    except ValueError:
        worldview_priority = -999
    return (worldview_match, context_fit, score_total, -conviction, worldview_priority)


def _select_response(
    bank: dict[str, Any], *, branch: str | None = None, preferred_worldview: str | None = None
) -> dict[str, Any]:
    responses = list(bank.get("responses", []))
    if branch is not None:
        branch_rows = [r for r in responses if str(r.get("branch") or "").upper() == branch.upper()]
        if not branch_rows:
            raise FixtureBuildError(
                f"Bank {bank.get('bank_id')} has no generated response for required branch {branch}"
            )
        responses = branch_rows
    else:
        null_branch = [r for r in responses if r.get("branch") in (None, "")]
        if null_branch:
            responses = null_branch
    if preferred_worldview:
        preferred = [r for r in responses if r.get("worldview") == preferred_worldview]
        if preferred:
            responses = preferred
    if not responses:
        raise FixtureBuildError(f"Bank {bank.get('bank_id')} contains no usable generated responses")
    return max(responses, key=lambda r: _rank_response(r, preferred_worldview))


def _bank_maps(export_payload: dict[str, Any]) -> tuple[dict[str, dict], dict[str, dict]]:
    by_instance: dict[str, dict] = {}
    by_beat: dict[str, dict] = {}
    for bank in export_payload["banks"]:
        if not bank.get("responses"):
            raise FixtureBuildError(f"Approved bank {bank.get('bank_id')} has no responses")
        for ref in bank.get("source_refs", []):
            instance_id = str(ref.get("instance_id", ""))
            beat_id = str(ref.get("beat_id", ""))
            if instance_id:
                by_instance[instance_id] = bank
            if beat_id:
                by_beat.setdefault(beat_id, bank)
    return by_instance, by_beat


def _beat_for_field(instances: list[BeatInstance], row: SourceRow, field: str) -> BeatInstance | None:
    for beat in instances:
        if beat.source_row == row.row_number and beat.source_field == field:
            return beat
    return None


def _exchange_for_beat(
    beat: BeatInstance | None,
    bank_by_instance: dict[str, dict],
    bank_by_beat: dict[str, dict],
    *,
    preferred_worldview: str | None,
    branch: str | None = None,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    if beat is None:
        return [], {}
    bank = bank_by_instance.get(beat.instance_id) or bank_by_beat.get(beat.beat_id)
    if not bank:
        raise FixtureBuildError(
            f"No approved Dialogue Factory bank maps to {beat.instance_id} ({beat.source_sheet}!{beat.source_row} {beat.source_field})"
        )
    response = _select_response(bank, branch=branch, preferred_worldview=preferred_worldview)
    turns: list[dict[str, str]] = []
    if beat.source_text:
        turns.append({"speaker": "npc", "text": beat.source_text})
    john = str(response.get("john", "")).strip()
    reaction = str(response.get("npc_reaction", "")).strip()
    if john:
        turns.append({"speaker": "John", "text": john})
    if reaction:
        turns.append({"speaker": "npc", "text": reaction})
    provenance = {
        "bank_id": bank.get("bank_id", ""),
        "beat_id": beat.beat_id,
        "instance_id": beat.instance_id,
        "source_sheet": beat.source_sheet,
        "source_row": beat.source_row,
        "source_field": beat.source_field,
        "worldview": response.get("worldview"),
        "context_fit": response.get("context_fit"),
        "conviction_tier": response.get("conviction_tier"),
        "branch": response.get("branch"),
    }
    return turns, provenance


def _choice_label(
    beat: BeatInstance,
    bank_by_instance: dict[str, dict],
    bank_by_beat: dict[str, dict],
    branch: str,
    canonical: str,
    preferred_worldview: str | None,
) -> tuple[str, dict[str, Any]]:
    bank = bank_by_instance.get(beat.instance_id) or bank_by_beat.get(beat.beat_id)
    if not bank:
        raise FixtureBuildError(f"No bank maps to consequential beat {beat.instance_id}")
    response = _select_response(bank, branch=branch, preferred_worldview=preferred_worldview)
    label = str(response.get("john", "")).strip() or canonical
    prov = {
        "bank_id": bank.get("bank_id", ""),
        "beat_id": beat.beat_id,
        "instance_id": beat.instance_id,
        "worldview": response.get("worldview"),
        "branch": branch,
    }
    return label, {"response": response, "provenance": prov}


def _consequence_flag(text: str, row_no: int, branch: str) -> str:
    cleaned = _flag(text)
    return cleaned if cleaned and cleaned != "unknown" else f"row_{row_no}_{branch.lower()}"


def _ending_hint(text: str) -> str:
    lowered = text.lower()
    tragic_words = ("tragic", "dead", "dies", "death", "killed", "ruin", "destroyed", "banished")
    return "tragic" if any(w in lowered for w in tragic_words) else "normal"


def _build_cast(rows: list[SourceRow], quest_id: str) -> tuple[list[dict[str, Any]], dict[str, str]]:
    by_name: dict[str, CastMember] = {}
    npc_ids: dict[str, str] = {}
    used_ids: set[str] = set()
    anchor_counts: defaultdict[str, int] = defaultdict(int)
    offsets = [[0, 1], [1, 1], [-1, 1], [1, 0], [-1, 0], [0, 2], [2, 1], [-2, 1]]
    for row in rows:
        key = row.character.strip().casefold()
        if key in by_name:
            continue
        base_id = _slug(row.character)
        npc_id = base_id
        n = 2
        while npc_id in used_ids:
            npc_id = f"{base_id}_{n}"
            n += 1
        used_ids.add(npc_id)
        anchor = _anchor_for_role(row.village_role)
        offset = offsets[anchor_counts[anchor] % len(offsets)]
        anchor_counts[anchor] += 1
        member = CastMember(
            id=npc_id,
            name=row.character,
            village_role=row.village_role,
            story_role=row.story_role,
            personality_summary=row.personality_summary,
            anchor=anchor,
            sprite=_sprite_for_role(row.village_role),
            pos_offset=offset,
            dialogue_context=row.story_context,
        )
        by_name[key] = member
        npc_ids[key] = npc_id
    return [m.as_json(quest_id) for m in by_name.values()], npc_ids


def _building(anchor: str, kind: str = "residential", size: list[int] | None = None) -> dict[str, Any]:
    size = size or [7, 5]
    return {
        "id": anchor,
        "anchor": anchor,
        "size": size,
        "door_offset": [size[0] // 2, size[1] - 1],
        "type": kind,
    }


def _build_village(cast_id: str, rows: list[SourceRow], cast_rows: list[dict[str, Any]]) -> dict[str, Any]:
    resources = _infer_resources(rows, cast_id)
    anchors: dict[str, list[int]] = {
        "village_square": [34, 28],
        "village_hall": [30, 20],
        "healer_house": [22, 19],
        "pottery": [40, 19],
        "workshop": [43, 25],
        "tavern": [28, 33],
        "general_store": [38, 32],
        "old_shrine": [19, 31],
        "forge": [23, 34],
        "mill": [46, 30],
        "farmstead": [52, 43],
        "fields": [59, 47],
        "logging_camp": [10, 11],
        "forest": [7, 8],
        "mine_mouth": [11, 43],
        "mine": [8, 49],
    }
    needed = {str(c.get("work_anchor", "village_square")) for c in cast_rows}
    needed |= {"village_square", "village_hall"}
    if "Wood" in resources:
        needed |= {"forest", "logging_camp"}
    if "Grain" in resources:
        needed |= {"fields", "farmstead", "mill"}
    if "Ore" in resources:
        needed |= {"mine", "mine_mouth", "forge"}

    regions: dict[str, Any] = {
        "village_core": {"name": "Village", "bounds": [16, 14, 38, 28], "terrain": "settlement"},
    }
    if "Wood" in resources:
        regions["forest"] = {"name": "Forest", "bounds": [0, 0, 25, 22], "terrain": "forest"}
    if "Grain" in resources:
        regions["fields"] = {"name": "Fields", "bounds": [46, 36, 26, 22], "terrain": "farmland"}
    if "Ore" in resources:
        regions["mine"] = {"name": "Mine Workings", "bounds": [0, 36, 25, 22], "terrain": "industrial"}

    building_defs = {
        "village_hall": _building("village_hall", "civic", [8, 6]),
        "healer_house": _building("healer_house"),
        "pottery": _building("pottery", "workshop"),
        "workshop": _building("workshop", "workshop"),
        "tavern": _building("tavern", "commercial", [8, 6]),
        "general_store": _building("general_store", "commercial"),
        "old_shrine": _building("old_shrine", "civic", [6, 5]),
        "forge": _building("forge", "workshop"),
        "mill": _building("mill", "workshop", [8, 6]),
        "farmstead": _building("farmstead", "residential", [8, 6]),
        "logging_camp": _building("logging_camp", "camp", [6, 4]),
    }
    buildings = [building_defs[a] for a in building_defs if a in needed]

    roads: list[dict[str, str]] = []
    for anchor in sorted(needed):
        if anchor in {"village_square", "forest", "fields", "mine"}:
            continue
        roads.append({"from": "village_square", "to": anchor})
    if "logging_camp" in needed:
        roads.append({"from": "logging_camp", "to": "forest"})
    if "farmstead" in needed:
        roads.append({"from": "farmstead", "to": "fields"})
    if "mine_mouth" in needed:
        roads.append({"from": "mine_mouth", "to": "mine"})

    signs = {a: a.replace("_", " ").upper() for a in needed if a in anchors}
    situation = next((r.situation_shape for r in rows if r.situation_shape), "Canonical village dialogue story")
    profile = _economic_profile(cast_id)
    resource_label = " + ".join(resources)
    return {
        "id": cast_id,
        "name": f"{cast_id} — {resource_label}",
        "economic_profile": profile,
        "description": situation,
        "resources": resources,
        "map": {"width": 72, "height": 58},
        "regions": regions,
        "semantic_anchors": {k: v for k, v in anchors.items() if k in needed or k == "village_square"},
        "buildings": buildings,
        "player_start": anchors["village_square"],
        "roads": roads,
        "signs": signs,
    }


def _story_title(rows: list[SourceRow], cast_id: str) -> tuple[str, str]:
    situations = [r.situation_shape.strip() for r in rows if r.situation_shape.strip()]
    situation = Counter(situations).most_common(1)[0][0] if situations else "Canonical Village Story"
    title = situation if len(situation) <= 70 else situation[:67].rstrip() + "..."
    return f"{cast_id}: {title}", situation


def _build_story(
    cast_id: str,
    rows: list[SourceRow],
    instances: list[BeatInstance],
    npc_ids: dict[str, str],
    bank_by_instance: dict[str, dict],
    bank_by_beat: dict[str, dict],
    *,
    preferred_worldview: str | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    quest_id = f"{cast_id.lower()}_canonical_story"
    title, premise = _story_title(rows, cast_id)
    nodes: dict[str, Any] = {}
    dialogue_entries: list[dict[str, Any]] = []
    epilogues: defaultdict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    epilogue_prov: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    mapped_instances: set[str] = set()

    scene_ids = [f"scene_{idx:02d}_{npc_ids[row.character.strip().casefold()]}" for idx, row in enumerate(rows, start=1)]

    for idx, row in enumerate(rows):
        npc_id = npc_ids[row.character.strip().casefold()]
        node_id = scene_ids[idx]
        next_id = scene_ids[idx + 1] if idx + 1 < len(scene_ids) else "complete_story"
        anchor = _anchor_for_role(row.village_role)
        node: dict[str, Any] = {
            "npc": npc_id,
            "anchor": anchor,
            "source_row": row.row_number,
            "dialogue_state": row.dialogue_state,
            "trigger_condition": row.trigger_condition,
        }

        if row.gives_choice:
            decision = _beat_for_field(instances, row, "Choice Prompt")
            if decision is None:
                raise FixtureBuildError(f"{cast_id} row {row.row_number} is a choice row but has no decision beat")
            mapped_instances.add(decision.instance_id)
            label_a, data_a = _choice_label(
                decision, bank_by_instance, bank_by_beat, "A", row.option_a, preferred_worldview
            )
            label_b, data_b = _choice_label(
                decision, bank_by_instance, bank_by_beat, "B", row.option_b, preferred_worldview
            )
            node.update({
                "type": "choice",
                "prompt": row.choice_prompt,
                "options": [
                    {
                        "variant": "branch_a",
                        "branch": "A",
                        "fallback_label": row.option_a,
                        "sets": [f"scene_{idx+1:02d}_branch_a", _consequence_flag(row.state_change_a, row.row_number, "A")],
                        "ending_hint": _ending_hint(row.state_change_a),
                        "next": next_id,
                    },
                    {
                        "variant": "branch_b",
                        "branch": "B",
                        "fallback_label": row.option_b,
                        "sets": [f"scene_{idx+1:02d}_branch_b", _consequence_flag(row.state_change_b, row.row_number, "B")],
                        "ending_hint": _ending_hint(row.state_change_b),
                        "next": next_id,
                    },
                ],
            })
            for branch, data, canonical_response, response_field, variant in (
                ("A", data_a, row.response_a, "Response to A", "branch_a"),
                ("B", data_b, row.response_b, "Response to B", "branch_b"),
            ):
                selected = data["response"]
                # The generated John line is used as the actual choice label; after
                # selection the NPC reacts, then the canonical branch response and
                # its generated follow-up exchange are played as one coherent scene.
                turns: list[dict[str, str]] = []
                reaction = str(selected.get("npc_reaction", "")).strip()
                if reaction:
                    turns.append({"speaker": "npc", "text": reaction})
                follow = _beat_for_field(instances, row, response_field)
                follow_prov: dict[str, Any] = {}
                if follow is not None:
                    mapped_instances.add(follow.instance_id)
                    follow_turns, follow_prov = _exchange_for_beat(
                        follow,
                        bank_by_instance,
                        bank_by_beat,
                        preferred_worldview=preferred_worldview,
                    )
                    turns.extend(follow_turns)
                elif canonical_response:
                    turns.append({"speaker": "npc", "text": canonical_response})
                dialogue_entries.append({
                    "npc_id": npc_id,
                    "quest_id": quest_id,
                    "node_id": node_id,
                    "variant": variant,
                    "choice_label": str(selected.get("john", "")).strip() or (row.option_a if branch == "A" else row.option_b),
                    "turns": turns,
                    "provenance": {
                        "decision": data["provenance"],
                        "followup": follow_prov,
                        "source_row": row.row_number,
                    },
                })
        else:
            opening = _beat_for_field(instances, row, "Opening Line")
            node.update({"type": "talk", "sets": [f"scene_{idx+1:02d}_complete"], "next": next_id})
            if opening is not None:
                mapped_instances.add(opening.instance_id)
                turns, provenance = _exchange_for_beat(
                    opening,
                    bank_by_instance,
                    bank_by_beat,
                    preferred_worldview=preferred_worldview,
                )
                dialogue_entries.append({
                    "npc_id": npc_id,
                    "quest_id": quest_id,
                    "node_id": node_id,
                    "variant": "default",
                    "turns": turns,
                    "provenance": provenance,
                })
            else:
                # A row with no opening still remains a visitable story scene, but
                # this is explicit rather than silently fabricating dialogue.
                dialogue_entries.append({
                    "npc_id": npc_id,
                    "quest_id": quest_id,
                    "node_id": node_id,
                    "variant": "default",
                    "turns": [{"speaker": "npc", "text": "..."}],
                    "provenance": {"source_row": row.row_number, "warning": "No opening beat in canonical row"},
                })

        nodes[node_id] = node

        # End-state lines are preserved as post-story NPC dialogue instead of
        # being incorrectly inserted into the middle of the canonical route.
        for field_name, variant in (("Normal End Line", "normal"), ("Tragic End Line", "tragic")):
            beat = _beat_for_field(instances, row, field_name)
            if beat is None:
                continue
            mapped_instances.add(beat.instance_id)
            turns, prov = _exchange_for_beat(
                beat,
                bank_by_instance,
                bank_by_beat,
                preferred_worldview=preferred_worldview,
            )
            epilogues[(npc_id, variant)].extend(turns)
            epilogue_prov[(npc_id, variant)].append(prov)

    nodes["complete_story"] = {
        "type": "conclude",
        "text": "The village story has reached its current ending. You can keep talking to people to hear how they see the aftermath.",
    }
    for (npc_id, variant), turns in epilogues.items():
        dialogue_entries.append({
            "npc_id": npc_id,
            "quest_id": quest_id,
            "node_id": "__epilogue__",
            "variant": variant,
            "turns": turns,
            "provenance": epilogue_prov[(npc_id, variant)],
        })

    missing = [beat for beat in instances if beat.instance_id not in mapped_instances]
    if missing:
        details = ", ".join(f"{b.source_row}:{b.source_field}" for b in missing[:10])
        raise FixtureBuildError(
            f"Fixture mapping left {len(missing)} canonical beat instance(s) unused: {details}"
        )

    quest = {
        "id": quest_id,
        "title": title,
        "premise": premise,
        "start_node": scene_ids[0] if scene_ids else "complete_story",
        "nodes": nodes,
        "generated_route": "canonical_source_row_order",
        "epilogue_variants": ["normal", "tragic"],
    }
    dialogue = {"dialogue": dialogue_entries}
    stats = {
        "source_rows": len(rows),
        "beat_instances": len(instances),
        "mapped_beats": len(mapped_instances),
        "quest_nodes": len(nodes),
        "dialogue_entries": len(dialogue_entries),
    }
    return quest, dialogue, stats


def validate_fixture_data(village: dict, cast: dict, quest: dict, dialogue: dict) -> list[str]:
    errors: list[str] = []
    cast_ids = [str(c.get("id", "")) for c in cast.get("cast", [])]
    if len(cast_ids) != len(set(cast_ids)):
        errors.append("duplicate NPC ids")
    cast_set = set(cast_ids)
    anchors = set(village.get("semantic_anchors", {}).keys())
    nodes = quest.get("nodes", {})
    node_ids = set(nodes.keys())
    if not cast_ids:
        errors.append("cast is empty")
    if not isinstance(nodes, dict) or not nodes:
        errors.append("quest nodes are empty")
    if quest.get("start_node") not in node_ids:
        errors.append(f"start node {quest.get('start_node')!r} does not exist")
    for c in cast.get("cast", []):
        for field_name in ("home_anchor", "work_anchor"):
            anchor = str(c.get(field_name, ""))
            if anchor and anchor not in anchors:
                errors.append(f"NPC {c.get('id')} references missing anchor {anchor}")
    for node_id, node in nodes.items():
        npc = str(node.get("npc", ""))
        if npc and npc not in cast_set:
            errors.append(f"node {node_id} references missing NPC {npc}")
        anchor = str(node.get("anchor", ""))
        if anchor and anchor not in anchors:
            errors.append(f"node {node_id} references missing anchor {anchor}")
        nxt = str(node.get("next", ""))
        if nxt and nxt not in node_ids:
            errors.append(f"node {node_id} references missing next node {nxt}")
        for opt in node.get("options", []):
            target = str(opt.get("next", ""))
            if target and target not in node_ids:
                errors.append(f"node {node_id} option references missing node {target}")
    quest_id = str(quest.get("id", ""))
    for entry in dialogue.get("dialogue", []):
        npc = str(entry.get("npc_id", ""))
        node = str(entry.get("node_id", ""))
        if npc not in cast_set:
            errors.append(f"dialogue references missing NPC {npc}")
        if str(entry.get("quest_id", "")) != quest_id:
            errors.append(f"dialogue for {npc}/{node} has wrong quest id")
        if node not in node_ids and node != "__epilogue__":
            errors.append(f"dialogue references missing node {node}")
        if not isinstance(entry.get("turns", []), list) and not isinstance(entry.get("lines", []), list):
            errors.append(f"dialogue {npc}/{node} has no playable turns/lines")
    return sorted(set(errors))


def build_fixture(
    cast_id: str,
    *,
    workbook: Path | None = None,
    export_json: Path | None = None,
    fixture_root: Path | None = None,
    force: bool = False,
    validate_only: bool = False,
    preferred_worldview: str | None = None,
) -> dict[str, Any]:
    cast_id = cast_id.strip().upper()
    repo_root = Path(__file__).resolve().parents[2]
    workbook = Path(workbook or config.resolve_workbook())
    if not workbook.is_absolute():
        workbook = repo_root / workbook
    export_json = Path(export_json or (config.resolve_output_dir() / f"{cast_id}.json"))
    if not export_json.is_absolute():
        export_json = repo_root / export_json
    fixture_root = Path(fixture_root or (repo_root / "godot_project" / "content" / "village_tests"))
    if not fixture_root.is_absolute():
        fixture_root = repo_root / fixture_root

    rows = read_cast_rows(workbook, cast_id)
    instances = extract_beats(rows)
    digest = workbook_sha256(workbook)
    export_payload = _load_export(export_json, cast_id)
    exported_hash = str(export_payload.get("source_workbook", {}).get("sha256", ""))
    if exported_hash and exported_hash != digest:
        raise FixtureBuildError(
            "Dialogue export was generated from a different workbook revision. "
            f"export={exported_hash[:12]} current={digest[:12]}. Re-ingest/generate/export before building."
        )
    by_instance, by_beat = _bank_maps(export_payload)

    quest_id = f"{cast_id.lower()}_canonical_story"
    cast_rows, npc_ids = _build_cast(rows, quest_id)
    village = _build_village(cast_id, rows, cast_rows)
    quest, dialogue, story_stats = _build_story(
        cast_id,
        rows,
        instances,
        npc_ids,
        by_instance,
        by_beat,
        preferred_worldview=preferred_worldview,
    )
    provenance = {
        "generated_from": {
            "cast_id": cast_id,
            "dialogue_schema_version": export_payload.get("schema_version", ""),
            "source_workbook_sha256": digest,
            "dialogue_export": str(export_json),
            "builder": "dialogue_generation.fixture_builder.v1",
            "preferred_worldview": preferred_worldview,
        }
    }
    village.update(provenance)
    cast_payload = {"id": cast_id, "name": village["name"], "cast": cast_rows, **provenance}
    quest.update(provenance)
    dialogue.update(provenance)

    errors = validate_fixture_data(village, cast_payload, quest, dialogue)
    if errors:
        raise FixtureBuildError("Fixture validation failed: " + "; ".join(errors))

    target = fixture_root / cast_id
    if not validate_only:
        existing = [target / name for name in ("village.json", "cast.json", "quest.json", "dialogue.json") if (target / name).exists()]
        if existing and not force:
            raise FixtureBuildError(
                f"Fixture {target} already exists. Re-run with --force to replace the four generated fixture files."
            )
        target.mkdir(parents=True, exist_ok=True)
        payloads = {
            "village.json": village,
            "cast.json": cast_payload,
            "quest.json": quest,
            "dialogue.json": dialogue,
        }
        for name, payload in payloads.items():
            (target / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "cast_id": cast_id,
        "fixture_dir": str(target),
        "validation": "PASS",
        "written": not validate_only,
        "cast_members": len(cast_rows),
        "dialogue_banks": len(export_payload.get("banks", [])),
        **story_stats,
        "resources": village.get("resources", []),
        "quest_title": quest.get("title", ""),
    }
