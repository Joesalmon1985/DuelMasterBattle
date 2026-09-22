"""Allowlisted condition AST evaluator (C09 / C10 / T081).

Operators: all/any/not, eq/gte/lte, has_knowledge, relationship_band,
entity_status, quest_state, cause_active. No eval / arbitrary expressions.
"""

from __future__ import annotations

from typing import Any, Mapping

from sim.dmb.core.types import TypeValidationError
from sim.dmb.people.registry import relationship_band

ALLOWED_OPS = frozenset(
    {
        "all",
        "any",
        "not",
        "eq",
        "gte",
        "lte",
        "has_knowledge",
        "relationship_band",
        "entity_status",
        "quest_state",
        "cause_active",
        "true",
        "false",
    }
)


class ConditionEvaluator:
    def __init__(self, state: Any, *, context: Mapping[str, Any] | None = None):
        self.state = state
        self.context = dict(context or {})

    def evaluate(self, node: Any) -> bool:
        if node is True or node is False:
            return bool(node)
        if node is None:
            return True
        if isinstance(node, (int, float, str)):
            raise TypeValidationError("bare scalar is not a condition AST node")
        if not isinstance(node, dict):
            raise TypeValidationError("condition must be object AST")
        op = str(node.get("op") or node.get("operator") or "")
        if op not in ALLOWED_OPS:
            raise TypeValidationError(f"unknown condition op {op!r}")
        if op == "true":
            return True
        if op == "false":
            return False
        if op == "all":
            return all(self.evaluate(child) for child in list(node.get("args") or []))
        if op == "any":
            return any(self.evaluate(child) for child in list(node.get("args") or []))
        if op == "not":
            args = list(node.get("args") or [])
            if len(args) != 1:
                raise TypeValidationError("not requires one argument")
            return not self.evaluate(args[0])
        if op in {"eq", "gte", "lte"}:
            left = self._resolve(node.get("left"))
            right = self._resolve(node.get("right"))
            if op == "eq":
                return left == right
            if left is None or right is None:
                return False
            if op == "gte":
                return left >= right
            return left <= right
        if op == "has_knowledge":
            entity_id = str(self._resolve(node.get("entity_id")) or "")
            fact = str(self._resolve(node.get("fact")) or "")
            known = (self.state.knowledge or {}).get(entity_id) or {}
            if not known:
                return False
            if fact and fact not in {str(known.get("fact") or ""), str(known.get("role") or "")}:
                # Also accept fact id lists on person known_facts.
                person = (self.state.people or {}).get(entity_id) or {}
                facts = person.get("known_facts") or []
                return any(str(f.get("id") if isinstance(f, dict) else f) == fact for f in facts)
            return bool(known.get("known", True))
        if op == "relationship_band":
            person_id = str(self._resolve(node.get("person_id")) or self.context.get("speaker_id") or "")
            other_id = str(self._resolve(node.get("other_id")) or self.context.get("player_id") or "player")
            expected = int(self._resolve(node.get("band")))
            person = (self.state.people or {}).get(person_id) or {}
            score = int((person.get("relationship_map") or {}).get(other_id, 0))
            return relationship_band(score) == expected
        if op == "entity_status":
            entity_id = str(self._resolve(node.get("entity_id")) or "")
            expected = str(self._resolve(node.get("status")) or "")
            record = self._entity(entity_id)
            if record is None:
                return expected in {"missing", "gone", "destroyed"}
            status = str(record.get("status") or ("alive" if record.get("alive", True) else "dead"))
            return status == expected
        if op == "quest_state":
            quest_id = str(self._resolve(node.get("quest_id")) or "")
            expected = str(self._resolve(node.get("status")) or "")
            quest = (self.state.quests or {}).get(quest_id) or {}
            return str(quest.get("status") or "") == expected
        if op == "cause_active":
            cause_id = str(self._resolve(node.get("cause_id")) or "")
            causes = ((self.state.definitions or {}).get("causes") or {})
            active = causes.get("active") if isinstance(causes, dict) else None
            if isinstance(active, dict):
                rec = active.get(cause_id) or {}
                return bool(rec.get("active", False))
            board_causes = ((self.state.board or {}).get("causes") or {})
            rec = board_causes.get(cause_id) or {}
            return bool(rec.get("active", False))
        raise TypeValidationError(f"unhandled condition op {op!r}")

    def _resolve(self, value: Any) -> Any:
        if isinstance(value, dict) and "ref" in value:
            ref = str(value["ref"])
            if ref in self.context:
                return self.context[ref]
            parts = ref.split(".")
            cur: Any = self.context
            for part in parts:
                if isinstance(cur, dict):
                    cur = cur.get(part)
                else:
                    return None
            return cur
        return value

    def _entity(self, entity_id: str) -> dict[str, Any] | None:
        for bucket in (self.state.people, self.state.buildings, self.state.units, self.state.carts, self.state.items):
            if entity_id in (bucket or {}):
                return bucket[entity_id]
        return None


def evaluate_condition(state: Any, node: Any, *, context: Mapping[str, Any] | None = None) -> bool:
    return ConditionEvaluator(state, context=context).evaluate(node)
