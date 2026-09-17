from __future__ import annotations

import json
from typing import Any

from ..ollama_client import OllamaClient, OllamaResponse
from .schemas import BEAT_SCHEMA

SYSTEM = """You are a dramatic beat-planner for DuelMasterBattle offline authoring.
Python owns canonical world state. You only plan performance.
Write 5-10 beats for one scene.
The opening must already be in motion. Characters want competing things.
There must be escalation, at least one emotional or social turn, and a meaningful endpoint.
Reject mere exposition exchanges: if the scene only explains facts, set rejected_as_exposition true.
Do not invent new identities, secrets, quest outcomes, inventory or relationship states.
Do not put worldview labels in the plan as spoken content.
Return JSON only."""


def beats_are_exposition_only(payload: dict) -> bool:
    beats = payload.get("beats") or []
    if payload.get("rejected_as_exposition") is True:
        return True
    if len(beats) < 5:
        return True
    empty = {"", "none", "n/a", "no change", "no", "nothing"}
    pressure = 0
    turns = 0
    for beat in beats:
        change = str(beat.get("new_pressure_or_change") or "").strip().lower()
        hidden = str(beat.get("hidden_intention") or "").strip().lower()
        if change and change not in empty:
            pressure += 1
        if hidden and hidden not in empty and hidden not in str(beat.get("surface_action") or "").strip().lower():
            turns += 1
    return pressure < 2 or turns < 1


def _prompt(packet: dict) -> str:
    return (
        "Compile a dramatic beat plan from this compact packet.\n\n"
        + json.dumps(packet, ensure_ascii=False)
        + "\n\nEach beat needs speaker_or_focus, surface_action, hidden_intention, "
        "new_pressure_or_change and information_change."
    )


def generate_beat_plan(client: OllamaClient, packet: dict, *, model: str | None = None) -> OllamaResponse:
    prompt = _prompt(packet)
    resp = client.generate_with_retry(
        prompt,
        system=SYSTEM,
        temperature=0.35,
        num_predict=1600,
        format_schema=BEAT_SCHEMA,
        model=model,
    )
    if resp.success and resp.data and beats_are_exposition_only(resp.data):
        repair = (
            prompt
            + "\n\nYour previous plan was exposition-only. Rewrite with competing wants, "
            "a live opening, escalation, and an emotional turn. Do not add facts."
        )
        retry = client.generate_with_retry(
            repair,
            system=SYSTEM,
            temperature=0.4,
            num_predict=1600,
            format_schema=BEAT_SCHEMA,
            model=model,
        )
        if retry.success:
            retry.data = retry.data or {}
            retry.data["exposition_retry"] = True
            return retry
        return OllamaResponse(
            False,
            error="Beat plan was exposition-only and repair failed",
            error_type="model_json",
            data=resp.data,
            raw_response=resp.raw_response,
        )
    return resp
