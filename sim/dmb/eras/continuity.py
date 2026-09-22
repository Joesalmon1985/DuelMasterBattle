"""Era continuity for people, Rockfall quest, and protected items (C11 / T103).

Translates the pack's historical "shortage quest" acceptance to the canonical
G05 Rockfall quest: quest.blocked_exit_boulder.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from sim.dmb.adventure.item_recovery import ItemRecoveryService
from sim.dmb.world.boulder_quest import (
    QUEST_INSTANCE_ID,
    ROCKFALL_ID,
    _norm_status,
    get_rockfall,
)


def _workplace_operational(state: Any, workplace_id: str | None) -> bool:
    if not workplace_id:
        return False
    building = (state.buildings or {}).get(workplace_id) or {}
    if not building:
        return False
    if building.get("ruin_only") or building.get("status") in {
        "destroyed",
        "inert_ruin",
        "inert",
    }:
        return False
    if building.get("active") is False and building.get("status") != "active":
        return False
    sid = building.get("settlement_id")
    if sid:
        settlement = (state.settlements or {}).get(sid) or {}
        if settlement.get("ruin_only") or settlement.get("status") in {"inert", "destroyed"}:
            return False
        if settlement.get("operational") is False:
            return False
    return True


def person_continuity_row(state: Any, person_id: str) -> dict[str, Any]:
    person = (state.people or {}).get(person_id) or {}
    return {
        "person_id": person_id,
        "display_name": person.get("display_name") or person.get("name"),
        "faction_id": person.get("faction_id"),
        "displaced": person.get("status") == "displaced" or "displaced" in set(person.get("profile_flags") or []),
        "node_id": person.get("node_id"),
        "job_id": person.get("job_id"),
        "workplace_id": person.get("workplace_id"),
        "alive": bool(person.get("alive", True)) and person.get("status") != "dead",
        "status": person.get("status"),
        "collapsed_faction_id": person.get("collapsed_faction_id"),
    }


@dataclass
class ContinuityService:
    state: Any

    def adapt_for_transition(
        self,
        *,
        transition_id: str,
        settlement_assignments: Mapping[str, str] | None = None,
        collapsed_faction_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Reconcile people, Rockfall quest, and protected items after era commit.

        Pure relative to ID identity: never clones Persons or recreates the quest.
        Idempotent per transition_id.
        """
        receipts = self.state.command_receipts.setdefault("era_continuity", {})
        if transition_id in receipts:
            return {"idempotent": True, "receipt": receipts[transition_id]}

        people_before = set(self.state.people)
        quest_before = deepcopy(self.state.quests.get(QUEST_INSTANCE_ID))
        rockfall_before = deepcopy(get_rockfall(self.state))

        person_adaptations = self._adapt_people(
            settlement_assignments=settlement_assignments or {},
            collapsed_faction_ids=set(collapsed_faction_ids or []),
        )
        quest_adaptations = self._adapt_rockfall_quest()
        item_adaptations = self._adapt_protected_items(transition_id=transition_id)

        if set(self.state.people) != people_before:
            raise RuntimeError("continuity must not create or delete Person IDs")
        if QUEST_INSTANCE_ID in (self.state.quests or {}) and quest_before is None:
            raise RuntimeError("continuity must not create a new Rockfall quest")
        if quest_before is not None and QUEST_INSTANCE_ID not in (self.state.quests or {}):
            raise RuntimeError("continuity must not delete the Rockfall quest")

        rockfall_after = get_rockfall(self.state)
        if rockfall_before and rockfall_after:
            if rockfall_before.get("id") != rockfall_after.get("id"):
                raise RuntimeError("Rockfall object id must be preserved")

        receipt = {
            "transition_id": transition_id,
            "person_adaptations": person_adaptations,
            "quest_adaptations": quest_adaptations,
            "item_adaptations": item_adaptations,
            "people_ids": sorted(self.state.people),
            "quest_id": QUEST_INSTANCE_ID if QUEST_INSTANCE_ID in (self.state.quests or {}) else None,
            "rockfall_id": ROCKFALL_ID if get_rockfall(self.state) else None,
            "rockfall_status": _norm_status((get_rockfall(self.state) or {}).get("status")),
        }
        receipts[transition_id] = receipt
        return {"idempotent": False, "receipt": receipt}

    def _adapt_people(
        self,
        *,
        settlement_assignments: Mapping[str, str],
        collapsed_faction_ids: set[str],
    ) -> list[dict[str, Any]]:
        adaptations: list[dict[str, Any]] = []
        for pid, person in list(self.state.people.items()):
            before = person_continuity_row(self.state, pid)
            if not before["alive"]:
                # Dead stay dead — never resurrect.
                adaptations.append({"person_id": pid, "action": "dead_preserved", "before": before, "after": before})
                continue

            workplace_id = person.get("workplace_id")
            if workplace_id and not _workplace_operational(self.state, workplace_id):
                # Truthful displacement: clear current employment; remember past workplace.
                past = {
                    "workplace_id": workplace_id,
                    "job_id": person.get("job_id"),
                    "label": ((self.state.buildings or {}).get(workplace_id) or {}).get("label"),
                }
                person["past_workplace"] = past
                person["workplace_id"] = None
                person["job_id"] = None
                if person.get("status") != "displaced":
                    person["status"] = "displaced"
                    flags = set(person.get("profile_flags") or [])
                    flags.add("displaced")
                    person["profile_flags"] = sorted(flags)
                person["displace_reason"] = person.get("displace_reason") or "workplace_lost_at_transition"

            sid = person.get("settlement_id")
            if sid and sid in settlement_assignments:
                person["faction_id"] = settlement_assignments[sid]
            elif person.get("faction_id") in collapsed_faction_ids:
                person["collapsed_faction_id"] = person.get("faction_id")
                person["faction_id"] = None
                if person.get("status") != "displaced":
                    person["status"] = "displaced"
                    flags = set(person.get("profile_flags") or [])
                    flags.add("displaced")
                    person["profile_flags"] = sorted(flags)

            after = person_continuity_row(self.state, pid)
            adaptations.append({"person_id": pid, "action": "adapted", "before": before, "after": after})
        return adaptations

    def _adapt_rockfall_quest(self) -> list[dict[str, Any]]:
        adaptations: list[dict[str, Any]] = []
        quest = (self.state.quests or {}).get(QUEST_INSTANCE_ID)
        rockfall = get_rockfall(self.state)
        if quest is None and rockfall is None:
            return adaptations

        # Preserve quest ID and helper binding. Never restart or duplicate.
        if quest is not None:
            helper = (
                quest.get("helper_person_id")
                or (quest.get("bindings") or {}).get("helper_person_id")
            )
            if helper:
                person = (self.state.people or {}).get(helper)
                if person is None or not person.get("alive", True) or person.get("status") == "dead":
                    # Dead helper must not resurrect; clear binding with recorded reason.
                    quest["helper_person_id"] = None
                    bindings = dict(quest.get("bindings") or {})
                    bindings["helper_person_id"] = None
                    bindings["helper_lost_reason"] = "helper_dead_at_transition"
                    quest["bindings"] = bindings
                    if rockfall is not None:
                        rockfall["helper_person_id"] = None
                    adaptations.append(
                        {
                            "quest_id": QUEST_INSTANCE_ID,
                            "action": "helper_cleared_dead",
                            "helper_person_id": helper,
                        }
                    )
                else:
                    # Same helper survives; keep binding on quest + rockfall + meta.
                    quest["helper_person_id"] = helper
                    bindings = dict(quest.get("bindings") or {})
                    bindings["helper_person_id"] = helper
                    quest["bindings"] = bindings
                    if rockfall is not None:
                        rockfall["helper_person_id"] = helper
                    fx = (self.state.board or {}).setdefault("fx_village", {})
                    meta = dict(fx.get("boulder_quest") or fx.get("rockfall_quest") or {})
                    meta["helper_person_id"] = helper
                    fx["boulder_quest"] = meta
                    fx["rockfall_quest"] = meta
                    adaptations.append(
                        {
                            "quest_id": QUEST_INSTANCE_ID,
                            "action": "helper_preserved",
                            "helper_person_id": helper,
                        }
                    )

            status = str(quest.get("status") or "")
            rock_status = _norm_status((rockfall or {}).get("status"))
            if status == "completed" or rock_status == "cleared":
                # Cleared stays cleared — never claim blocked.
                quest["status"] = "completed"
                if rockfall is not None:
                    rockfall["status"] = "cleared"
                adaptations.append({"quest_id": QUEST_INSTANCE_ID, "action": "cleared_preserved"})
            elif rock_status == "clearing" and status == "active":
                # Clearing resumes with same helper if alive.
                adaptations.append({"quest_id": QUEST_INSTANCE_ID, "action": "clearing_resumed"})
            elif rockfall is not None and rock_status == "blocking":
                # Unseen or inspected — rockfall remains discoverable.
                adaptations.append(
                    {
                        "quest_id": QUEST_INSTANCE_ID,
                        "action": "blocking_preserved",
                        "quest_status": status,
                    }
                )

        if rockfall is not None:
            # Physical object remains on its node; geography preserved.
            rockfall["id"] = ROCKFALL_ID
            mechs = (self.state.board or {}).setdefault("mechanisms", {})
            mechs[ROCKFALL_ID] = rockfall

        return adaptations

    def _adapt_protected_items(self, *, transition_id: str) -> list[dict[str, Any]]:
        recovery = ItemRecoveryService(self.state)
        adaptations: list[dict[str, Any]] = []
        accessible = set()
        for settlement in (self.state.settlements or {}).values():
            if settlement.get("ruin_only") or not settlement.get("operational", True):
                continue
            node = settlement.get("node_id")
            if node:
                accessible.add(str(node))
        # Also allow player node / any non-ruin settlement area ids.
        player_node = (self.state.player or {}).get("node_id")
        if player_node:
            accessible.add(str(player_node))

        for item_id, item in list(self.state.items.items()):
            if not item.get("alive", True):
                continue
            def_id = str(item.get("definition_id") or "")
            required = def_id in recovery.required_definition_ids() or item.get("required")
            if not required and not item.get("quest_linked"):
                continue
            # Held by player — fine.
            if item.get("holder") == "player" or item.get("location") == "inventory":
                adaptations.append({"item_id": item_id, "action": "inventory_preserved"})
                continue
            node_id = str(item.get("node_id") or item.get("area_id") or "")
            owner_settlement = item.get("settlement_id")
            collapsed_home = False
            if owner_settlement:
                settlement = (self.state.settlements or {}).get(owner_settlement) or {}
                if settlement.get("ruin_only") or settlement.get("status") in {"inert", "destroyed"}:
                    collapsed_home = True
            if collapsed_home or (node_id and node_id not in accessible and accessible):
                try:
                    result = recovery.relocate_stranded(
                        item_id,
                        accessible_area_ids=accessible or {str(player_node or "node:1")},
                        command_id=f"{transition_id}:{item_id}",
                    )
                    adaptations.append(
                        {
                            "item_id": item_id,
                            "action": "relocated",
                            "result": result,
                            "same_id": result.get("item_id", item_id) == item_id,
                        }
                    )
                except Exception as exc:
                    adaptations.append(
                        {
                            "item_id": item_id,
                            "action": "relocation_failed",
                            "error": str(exc),
                        }
                    )
            else:
                adaptations.append({"item_id": item_id, "action": "accessible_preserved"})
        return adaptations


def truthful_occupation_line(state: Any, person_id: str) -> str:
    """Occupation answer that respects displacement / lost workplace history."""
    from sim.dmb.narrative.person_dialogue import occupation_answer_line, person_talk_context

    person = (state.people or {}).get(person_id) or {}
    if person.get("status") == "dead" or not person.get("alive", True):
        return "…"
    displaced = person.get("status") == "displaced" or "displaced" in set(person.get("profile_flags") or [])
    workplace_id = person.get("workplace_id")
    if displaced or (workplace_id and not _workplace_operational(state, workplace_id)):
        past = person.get("past_workplace") or {}
        label = str(past.get("label") or "").strip()
        if label:
            return f"I used to work at {label} before the settlement fell."
        if past.get("workplace_id"):
            return "I used to work there before the settlement fell."
        return "I don't have a workplace anymore. I'm looking for somewhere to settle."
    ctx = person_talk_context(state, person_id)
    return occupation_answer_line(ctx)
