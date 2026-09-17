from __future__ import annotations

import json

from ..ollama_client import OllamaClient, OllamaResponse
from .schemas import DIALOGUE_SCHEMA

SYSTEM = """You write one reviewed-but-still-draft dramatic scene for DuelMasterBattle.
Python owns canonical game state. You may vary wording, subtext, pacing, humour and gestures.
You may not invent or change identity, relationship state, known facts, witnessed events, inventory, quest progression, history, secrets or world state.
Write 12-30 spoken turns as JSON lines.
Not every character must speak equally.
Player lines use speaker_id PLAYER and may be short intent nodes.
speaker_id MUST be a compiled character id such as NPC_001, or PLAYER. Never use display names.
No worldview labels, scores, bank ids or authoring metadata in spoken text.
No giant exposition speeches. Keep NPC lines under about 40 words.
Secrets stay in subtext unless PERMITTED REVELATIONS explicitly allows them."""


def generate_dialogue(client: OllamaClient, packet: dict, beats: dict, *, model: str | None = None) -> OllamaResponse:
    prompt = (
        "Write scene dialogue from this packet and beat plan.\n\nPACKET:\n"
        + json.dumps(packet, ensure_ascii=False)
        + "\n\nBEATS:\n"
        + json.dumps(beats, ensure_ascii=False)
        + "\n\nReturn JSON with scene_id and lines[{speaker_id,text,action,beat,intent}]."
    )
    return client.generate_with_retry(
        prompt,
        system=SYSTEM,
        temperature=None,
        num_predict=2800,
        format_schema=DIALOGUE_SCHEMA,
        model=model,
    )
