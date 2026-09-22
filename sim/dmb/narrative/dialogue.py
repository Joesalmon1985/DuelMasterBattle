"""Offline dialogue runtime selection (C09 / T084).

No LLM/network. Priority: exact quest/stage/cause/role/era → role/cause/era →
role/state → neutral truthful fallback. Missing variables select fallback text.
"""

from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError
from sim.dmb.narrative.conditions import evaluate_condition
from sim.dmb.narrative.knowledge import filter_entity
from sim.dmb.narrative.line_catalog import LineCatalog

_VAR_PATTERN = re.compile(r"\{([a-zA-Z0-9_\.]+)\}")
SESSION_SCHEMA_VERSION = 1


def _stable_pick(seed: str, options: list[str]) -> str:
    if not options:
        raise TypeValidationError("no dialogue variants")
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    idx = int(digest[:8], 16) % len(options)
    return options[idx]


@dataclass
class DialogueResolver:
    state: WorldState
    catalog: LineCatalog = field(default_factory=LineCatalog)

    def _sessions(self) -> dict[str, Any]:
        store = self.state.definitions.setdefault("dialogue_runtime", {})
        store.setdefault("schema_version", SESSION_SCHEMA_VERSION)
        store.setdefault("sessions", {})
        store.setdefault("variant_bindings", {})
        return store

    def start(
        self,
        *,
        speaker_id: str,
        quest_id: str | None = None,
        stage: int | None = None,
        cause_id: str | None = None,
        era_id: str | None = None,
        node_id: str | None = None,
    ) -> dict[str, Any]:
        speaker = self.state.people.get(speaker_id) or {}
        role = str(speaker.get("role") or "worker")
        session_id = self.state.ids.new("dialogue")
        line = self._select_line(
            speaker_id=speaker_id,
            speaker_role=role,
            quest_id=quest_id,
            stage=stage,
            cause_id=cause_id,
            era_id=era_id or str((self.state.board or {}).get("era_id") or "ancient"),
        )
        session = {
            "id": session_id,
            "speaker_id": speaker_id,
            "quest_id": quest_id,
            "stage": stage,
            "cause_id": cause_id,
            "era_id": era_id,
            "node_id": node_id,
            "line_id": line.get("id"),
            "text": line.get("text"),
            "choices": list(line.get("choices") or []),
            "closed": False,
            "schema_version": SESSION_SCHEMA_VERSION,
        }
        self._sessions()["sessions"][session_id] = session
        return dict(session)

    def choices(self, session_id: str) -> list[dict[str, Any]]:
        session = self._require(session_id)
        visible: list[dict[str, Any]] = []
        for choice in session.get("choices") or []:
            cond = choice.get("condition")
            if cond is not None and not evaluate_condition(
                self.state,
                cond,
                context={"speaker_id": session["speaker_id"], "quest_id": session.get("quest_id")},
            ):
                continue
            visible.append(dict(choice))
        return visible[:3]  # ~three visible; paging later

    def choose(self, session_id: str, choice_id: str) -> dict[str, Any]:
        session = self._require(session_id)
        if session.get("closed"):
            raise TypeValidationError("dialogue already closed")
        match = next((c for c in self.choices(session_id) if c.get("id") == choice_id), None)
        if match is None:
            # Stale context — refresh choices.
            return {"status": "stale", "choices": self.choices(session_id), "session": dict(session)}
        session["last_choice_id"] = choice_id
        session["pending_effects"] = list(match.get("effect_ids") or match.get("effects") or [])
        next_node = match.get("next")
        if next_node:
            line = self.catalog.get(str(next_node)) or {"id": next_node, "text": "", "choices": []}
            session["line_id"] = line.get("id")
            session["text"] = self._render(line, speaker_id=session["speaker_id"])
            session["choices"] = list(line.get("choices") or [])
        return {"status": "chosen", "choice": match, "session": dict(session)}

    def close(self, session_id: str) -> dict[str, Any]:
        session = self._require(session_id)
        session["closed"] = True
        return dict(session)

    def _require(self, session_id: str) -> dict[str, Any]:
        session = self._sessions()["sessions"].get(session_id)
        if session is None:
            raise TypeValidationError(f"unknown dialogue session {session_id}")
        return session

    def _select_line(
        self,
        *,
        speaker_id: str,
        speaker_role: str,
        quest_id: str | None,
        stage: int | None,
        cause_id: str | None,
        era_id: str,
    ) -> dict[str, Any]:
        # Score candidates by specificity.
        scored: list[tuple[int, dict[str, Any]]] = []
        for line in self.catalog.lines.values():
            if line.get("speaker_role") and line["speaker_role"] != speaker_role:
                continue
            score = 0
            # Reject wrong era/cause when the line requires them.
            if line.get("era_id") and line["era_id"] not in {era_id, "all"}:
                continue
            if line.get("cause_id") and cause_id and line["cause_id"] != cause_id:
                continue
            if line.get("cause_id") and not cause_id and line.get("require_cause"):
                continue
            if line.get("quest_id"):
                if not quest_id or line["quest_id"] != quest_id:
                    continue
                score += 8
            if stage is not None and line.get("stage") is not None and int(line["stage"]) == int(stage):
                score += 4
            if line.get("cause_id") and cause_id and line["cause_id"] == cause_id:
                score += 4
            if line.get("speaker_role") == speaker_role:
                score += 2
            if line.get("priority") == "fallback":
                score += 0
            elif line.get("priority") == "role_default":
                score += 5
            if line.get("condition") is not None:
                if not evaluate_condition(
                    self.state,
                    line["condition"],
                    context={"speaker_id": speaker_id, "quest_id": quest_id, "cause_id": cause_id},
                ):
                    continue
            scored.append((score, line))
        if not scored:
            return {
                "id": "dialogue.neutral_fallback",
                "text": "They have nothing more to say right now.",
                "choices": [],
                "priority": "fallback",
            }
        scored.sort(key=lambda pair: (-pair[0], str(pair[1].get("id"))))
        best_score = scored[0][0]
        tied = [line for score, line in scored if score == best_score]
        # Stable variant binding per context.
        ids = [str(line["id"]) for line in tied]
        ctx = f"{speaker_id}|{quest_id}|{stage}|{cause_id}|{era_id}|{best_score}"
        bindings = self._sessions()["variant_bindings"]
        if ctx in bindings and bindings[ctx] in ids:
            chosen_id = bindings[ctx]
        else:
            chosen_id = _stable_pick(ctx, ids)
            bindings[ctx] = chosen_id
        line = next(line for line in tied if line["id"] == chosen_id)
        rendered = dict(line)
        rendered["text"] = self._render(line, speaker_id=speaker_id)
        rendered["match_score"] = best_score
        return rendered

    def _render(self, line: dict[str, Any], *, speaker_id: str) -> str:
        template = str(line.get("text") or line.get("text_key") or "")
        fallback = str(line.get("fallback") or line.get("fallback_key") or "…")
        variables = dict(line.get("variables") or {})
        known = filter_entity(self.state, speaker_id)
        safe_vars = {
            "speaker_role": known.get("role") or "someone",
            "speaker_name": known.get("name"),  # may be None — must not leak true name
        }
        # Never leak authoritative person.name when unknown.
        person = self.state.people.get(speaker_id) or {}
        if known.get("name"):
            safe_vars["speaker_name"] = known["name"]
        else:
            safe_vars["speaker_name"] = None

        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            if key in variables:
                # Typed declaration only; resolve via knowledge/context.
                declared = variables[key]
                value = safe_vars.get(key)
                if value is None and isinstance(declared, dict):
                    value = declared.get("default")
                if value is None:
                    raise KeyError(key)
                return str(value)
            if key in safe_vars and safe_vars[key] is not None:
                return str(safe_vars[key])
            raise KeyError(key)

        try:
            text = _VAR_PATTERN.sub(repl, template)
        except KeyError:
            return fallback
        # Escape residual braces / markup-ish tokens.
        if "{" in text or "}" in text:
            return fallback
        # Guard: raw secret name must not appear when unknown.
        secret = person.get("name")
        if secret and not known.get("name") and secret in text:
            return fallback
        return text
