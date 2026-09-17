from __future__ import annotations

BEAT_SCHEMA = {
    "type": "object",
    "properties": {
        "scene_id": {"type": "string"},
        "rejected_as_exposition": {"type": "boolean"},
        "beats": {
            "type": "array",
            "minItems": 5,
            "maxItems": 10,
            "items": {
                "type": "object",
                "properties": {
                    "beat": {"type": "integer"},
                    "speaker_or_focus": {"type": "string"},
                    "surface_action": {"type": "string"},
                    "hidden_intention": {"type": "string"},
                    "new_pressure_or_change": {"type": "string"},
                    "information_change": {"type": "string"},
                },
                "required": [
                    "beat",
                    "speaker_or_focus",
                    "surface_action",
                    "hidden_intention",
                    "new_pressure_or_change",
                    "information_change",
                ],
            },
        },
    },
    "required": ["scene_id", "beats"],
}

DIALOGUE_SCHEMA = {
    "type": "object",
    "properties": {
        "scene_id": {"type": "string"},
        "lines": {
            "type": "array",
            "minItems": 8,
            "maxItems": 36,
            "items": {
                "type": "object",
                "properties": {
                    "speaker_id": {"type": "string"},
                    "text": {"type": "string"},
                    "action": {"type": "string"},
                    "beat": {"type": "integer"},
                    "intent": {"type": "string"},
                },
                "required": ["speaker_id", "text", "beat"],
            },
        },
    },
    "required": ["scene_id", "lines"],
}

AUDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["PASS", "WARN", "CANON_BLOCK"]},
        "canon_block": {"type": "boolean"},
        "summary": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["canon_block", "warning", "note"]},
                    "category": {"type": "string"},
                    "detail": {"type": "string"},
                    "fix": {"type": "string"},
                },
                "required": ["severity", "category", "detail"],
            },
        },
    },
    "required": ["verdict", "summary", "findings"],
}

REVISION_SCHEMA = {
    "type": "object",
    "properties": {
        "scene_id": {"type": "string"},
        "revision_notes": {"type": "array", "items": {"type": "string"}},
        "canonical_changes_attempted": {"type": "boolean"},
        "lines": DIALOGUE_SCHEMA["properties"]["lines"],
    },
    "required": ["scene_id", "revision_notes", "lines"],
}
