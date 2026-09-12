from __future__ import annotations

import json

CLASSIFIER_SCHEMA = {
    "type": "object",
    "properties": {
        "best_match": {"type": ["string", "null"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "can_share_dialogue": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["best_match", "confidence", "can_share_dialogue", "reason"],
    "additionalProperties": False,
}

WRITER_SCHEMA = {
    "type": "object",
    "properties": {
        "bank_id": {"type": "string"},
        "responses": {
            "type": "array",
            "minItems": 7,
            "maxItems": 7,
            "items": {
                "type": "object",
                "properties": {
                    "worldview": {"type": "string", "enum": ["monarchist", "anarchist", "religious", "guildist", "arcane", "druidic", "cracked"]},
                    "context_fit": {"type": "integer", "minimum": 1, "maximum": 5},
                    "conviction_tier": {"type": "integer", "minimum": 1, "maximum": 4},
                    "branch": {"type": ["string", "null"], "enum": ["A", "B", None]},
                    "john": {"type": "string"},
                    "npc_reaction": {"type": "string"},
                },
                "required": ["worldview", "context_fit", "conviction_tier", "branch", "john", "npc_reaction"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["bank_id", "responses"],
    "additionalProperties": False,
}

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "approved": {"type": "boolean"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "worldview": {"type": ["string", "null"]},
                    "severity": {"type": "string", "enum": ["error", "warning"]},
                    "category": {"type": "string"},
                    "detail": {"type": "string"},
                },
                "required": ["worldview", "severity", "category", "detail"],
                "additionalProperties": False,
            },
        },
        "summary": {"type": "string"},
    },
    "required": ["approved", "issues", "summary"],
    "additionalProperties": False,
}


def classifier_prompts(beat: dict, candidates: list[dict]) -> tuple[str, str]:
    system = """You classify reusable dialogue situations for Duel Master Battle.
Python owns story facts and bank membership; you only judge semantic reuse.
Two beats may share a bank ONLY if essentially the same seven John replies and NPC reactions can safely serve both without contradicting names, objects, events, relationships, branch meanings or moral facts.
'Same theme' is not enough. Prefer a new bank when uncertain."""
    user = "CURRENT BEAT:\n" + json.dumps(beat, ensure_ascii=False, indent=2)
    user += "\n\nCANDIDATE BANKS:\n" + json.dumps(candidates, ensure_ascii=False, indent=2)
    user += "\n\nChoose at most one candidate. Return only the requested structured result."
    return system, user


def writer_prompts(bank_id: str, bank_context: dict, worldview_text: str, repair_issues: list | None = None) -> tuple[str, str]:
    system = f"""You write concise fantasy-game dialogue for Duel Master Battle.
Generate seven contrasting possible replies by John and an NPC reaction to each reply.
The seven philosophical worldviews are authoring lenses, never labels John should say aloud.
Do not change story facts, names, relationships, choices or consequences. Do not invent a third plot branch.
For consequential beats, every response must choose existing branch A or B and the seven responses collectively must include both branches.
For non-consequential beats, branch must be null.
Keep John normally under 35 words and NPC reactions normally under 40 words. Avoid speeches and modern-world vocabulary.
Cracked Mirror should be subtle unless conviction is high; it must not automatically break the fourth wall at low conviction.
Do not include personality score deltas; Python supplies those authoritatively.

AUTHORITATIVE WORLDVIEWS:\n{worldview_text}"""
    payload = {
        "bank_id": bank_id,
        "representative": bank_context["bank"],
        "source_instances": bank_context["instances"],
    }
    user = "AUTHORITATIVE BANK CONTEXT:\n" + json.dumps(payload, ensure_ascii=False, indent=2)
    if repair_issues:
        user += "\n\nPREVIOUS REVIEW/VALIDATION ISSUES TO REPAIR:\n" + json.dumps(repair_issues, ensure_ascii=False, indent=2)
    user += "\n\nReturn exactly seven distinct responses, one for each worldview key."
    return system, user


def reviewer_prompts(bank_context: dict, exchange: dict, worldview_text: str) -> tuple[str, str]:
    system = f"""You are an independent dialogue QA reviewer for Duel Master Battle.
Review but do not silently rewrite. Treat supplied story context and A/B branches as authoritative.
Assess worldview fidelity, distinctiveness, factual consistency, NPC personality, branch correctness, unsupported invention, fantasy tone and playability.
Warnings may be stylistic; errors mean the material should not be approved.

AUTHORITATIVE WORLDVIEWS:\n{worldview_text}"""
    user = "SOURCE CONTEXT:\n" + json.dumps(bank_context, ensure_ascii=False, indent=2)
    user += "\n\nGENERATED EXCHANGE:\n" + json.dumps(exchange, ensure_ascii=False, indent=2)
    user += "\n\nReturn structured findings only."
    return system, user
