from __future__ import annotations

import json

from ..ollama_client import OllamaClient, OllamaResponse
from .schemas import REVISION_SCHEMA

SYSTEM = """You are a bounded reviser for DuelMasterBattle offline scene authoring.
Improve prose, voice, subtext and scene dynamics using the audit reports.
You may NOT change canonical facts merely to satisfy a critic.
Do not invent identity, relationship state, secrets, inventory, quest outcomes, history or witnessed events.
If an auditor asks for a fact change, refuse and keep the packet's facts.
speaker_id MUST be a compiled character id such as NPC_001, or PLAYER. Never use display names, never use 1/2/3 indices, never replace spoken lines with stage directions.
Player-facing lines must not contain worldview labels or authoring metadata.
Return revised JSON lines plus revision_notes. Set canonical_changes_attempted false unless you were forced to refuse a requested fact change, in which case still keep facts unchanged and explain in notes."""


def revise_dialogue(
    client: OllamaClient,
    packet: dict,
    draft: dict,
    audits: dict,
    *,
    model: str | None = None,
) -> OllamaResponse:
    prompt = (
        "Revise this draft using the audits. Keep canon intact.\n\nPACKET:\n"
        + json.dumps(packet, ensure_ascii=False)
        + "\n\nDRAFT:\n"
        + json.dumps(draft, ensure_ascii=False)
        + "\n\nAUDITS:\n"
        + json.dumps(audits, ensure_ascii=False)
    )
    return client.generate_with_retry(
        prompt,
        system=SYSTEM,
        temperature=0.35,
        num_predict=2800,
        format_schema=REVISION_SCHEMA,
        model=model,
    )
