from __future__ import annotations

import re
from difflib import SequenceMatcher

from .config import config
from .normalize import normalize_text
from .worldviews import WorldviewSet

WORLDVIEW_KEYS = ["monarchist", "anarchist", "religious", "guildist", "arcane", "druidic", "cracked"]
SPOKEN_BANNED_LABELS = ["monarchist", "anarchist", "guildist", "arcane supremacist", "druidic", "cracked mirror"]


def enrich_exchange(exchange: dict, worldviews: WorldviewSet, bank_id: str) -> dict:
    enriched = {"bank_id": bank_id, "responses": []}
    for raw in exchange.get("responses", []):
        item = dict(raw)
        key = str(item.get("worldview", "")).lower().strip()
        item["worldview"] = key
        if key in worldviews.by_key:
            item["scores"] = worldviews.delta_for_key(key)
        enriched["responses"].append(item)
    return enriched


def _spoken_texts(response: dict) -> list[str]:
    return [str(response.get("john", "")), str(response.get("npc_reaction", ""))]


def validate_exchange(exchange: dict, bank_context: dict, worldviews: WorldviewSet) -> list[dict]:
    issues: list[dict] = []
    responses = exchange.get("responses")
    if not isinstance(responses, list) or len(responses) != 7:
        return [{"category": "structure", "detail": "Exactly seven responses are required"}]

    keys = [str(r.get("worldview", "")).lower() for r in responses]
    if set(keys) != set(WORLDVIEW_KEYS) or len(set(keys)) != 7:
        issues.append({"category": "structure", "detail": f"Worldviews must appear exactly once: {WORLDVIEW_KEYS}; got {keys}"})

    consequential = bool(bank_context["bank"].get("consequential"))
    branches = []
    john_norms: list[tuple[str, str]] = []
    for response in responses:
        key = str(response.get("worldview", "")).lower()
        john = str(response.get("john", "")).strip()
        npc = str(response.get("npc_reaction", "")).strip()
        if not john:
            issues.append({"worldview": key, "category": "structure", "detail": "John response is empty"})
        if not npc:
            issues.append({"worldview": key, "category": "structure", "detail": "NPC reaction is empty"})
        if len(john.split()) > config.generation.max_john_words:
            issues.append({"worldview": key, "category": "length", "detail": f"John response exceeds {config.generation.max_john_words} words"})
        if len(npc.split()) > config.generation.max_npc_words:
            issues.append({"worldview": key, "category": "length", "detail": f"NPC reaction exceeds {config.generation.max_npc_words} words"})
        try:
            fit = int(response.get("context_fit"))
        except (TypeError, ValueError):
            fit = 0
        if fit not in range(1, 6):
            issues.append({"worldview": key, "category": "structure", "detail": "context_fit must be 1-5"})
        try:
            tier = int(response.get("conviction_tier"))
        except (TypeError, ValueError):
            tier = 0
        if tier not in range(1, 5):
            issues.append({"worldview": key, "category": "structure", "detail": "conviction_tier must be 1-4"})

        branch = response.get("branch")
        if consequential:
            if branch not in {"A", "B"}:
                issues.append({"worldview": key, "category": "branch", "detail": "Consequential response must map to A or B"})
            else:
                branches.append(branch)
        elif branch is not None:
            issues.append({"worldview": key, "category": "branch", "detail": "Non-consequential response must have branch=null"})

        expected_scores = worldviews.delta_for_key(key) if key in worldviews.by_key else None
        if expected_scores is not None and response.get("scores") != expected_scores:
            issues.append({"worldview": key, "category": "scores", "detail": "Personality deltas do not match Python-owned worldview deltas"})

        combined = " ".join(_spoken_texts(response))
        lower = combined.lower()
        if "```" in combined or re.search(r"\b(json|schema|bank_id|context_fit|conviction_tier)\b", lower):
            issues.append({"worldview": key, "category": "meta", "detail": "Model/JSON metadata leaked into spoken dialogue"})
        if re.search(r"\bE\d{2}[AB]\b", combined):
            issues.append({"worldview": key, "category": "meta", "detail": "Source Cast ID leaked into spoken dialogue"})
        for label in SPOKEN_BANNED_LABELS:
            if label in lower:
                issues.append({"worldview": key, "category": "meta", "detail": f"Worldview label '{label}' spoken explicitly"})
        john_norms.append((key, normalize_text(john).lower()))

    if consequential and set(branches) != {"A", "B"}:
        issues.append({"category": "branch", "detail": "Consequential bank must preserve both A and B among the seven responses"})

    for i, (key_a, text_a) in enumerate(john_norms):
        for key_b, text_b in john_norms[i + 1:]:
            if text_a and text_a == text_b:
                issues.append({"category": "distinctiveness", "detail": f"{key_a} and {key_b} have identical John responses"})
            elif text_a and text_b and SequenceMatcher(None, text_a, text_b).ratio() >= 0.92:
                issues.append({"category": "distinctiveness", "detail": f"{key_a} and {key_b} John responses are near-identical"})
    return issues
