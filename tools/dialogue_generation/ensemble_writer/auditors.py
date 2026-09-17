from __future__ import annotations

import json
import re
from typing import Any

from ..ollama_client import OllamaClient, OllamaResponse
from .schemas import AUDIT_SCHEMA

WORLDVIEW_LEAK = re.compile(
    r"\b(monarchist|anarchist|guildist|druidic|worldview|conviction tier|bank_id)\b",
    re.I,
)
GENERIC_QUEST = re.compile(
    r"\b(quest marker|main quest|press e to|i have a task for you|bring me \d+)\b",
    re.I,
)
AFFIRMATIVE_PRESERVATION = re.compile(
    r"\b("
    r"no changes were made|remains? unchanged|remain(?:s|ed)? consistent|"
    r"is unchanged|are unchanged|was not changed|were not changed|"
    r"were not added|was not added|not altered|not revealed|"
    r"no secrets were revealed|identity remains consistent|"
    r"does not contain any true canon|adheres to (the )?(provided |established )?(authoring limits|narrative)"
    r")\b",
    re.I,
)
VIOLATION_LANGUAGE = re.compile(
    r"\b(invents?|invented|leaks?|leaked|contradicts?|unknown speaker|forbidden|does not know|cannot know)\b",
    re.I,
)
STAGE_DIRECTION = re.compile(
    r"^(performing|observing|investigating|confronted|making a decision|baking |noticing |explains |shows |joins |demonstrates |guides |begins )",
    re.I,
)


def _sanitize_finding(raw: dict) -> dict:
    item = {
        "severity": str(raw.get("severity") or "warning"),
        "category": str(raw.get("category") or "unspecified"),
        "detail": str(raw.get("detail") or ""),
        "fix": str(raw.get("fix") or ""),
    }
    detail = item["detail"]
    if item["severity"] == "canon_block" and not VIOLATION_LANGUAGE.search(detail):
        if AFFIRMATIVE_PRESERVATION.search(detail) or re.match(r"^no\b", detail, re.I):
            item["severity"] = "note"
            item["category"] = f"{item['category']}_preserved"
    return item


def parse_audit_result(payload: Any) -> dict:
    if not isinstance(payload, dict):
        return {
            "verdict": "WARN",
            "canon_block": False,
            "summary": "Audit payload was not an object",
            "findings": [{"severity": "warning", "category": "parse", "detail": "Non-object audit result", "fix": "Return the audit schema"}],
        }
    findings = [_sanitize_finding(raw) for raw in (payload.get("findings") or []) if isinstance(raw, dict)]
    remaining_blocks = [item for item in findings if item["severity"] == "canon_block"]
    verdict = str(payload.get("verdict") or "").upper()
    summary = str(payload.get("summary") or "")
    canon_block = bool(remaining_blocks)
    if not remaining_blocks and (bool(payload.get("canon_block")) or verdict == "CANON_BLOCK"):
        if VIOLATION_LANGUAGE.search(summary) and not AFFIRMATIVE_PRESERVATION.search(summary):
            canon_block = True
            findings.append({
                "severity": "canon_block",
                "category": "unspecified",
                "detail": summary or "Auditor asserted CANON_BLOCK without findings",
                "fix": "Quote the spoken line that invents or leaks a forbidden fact",
            })
    if canon_block:
        verdict = "CANON_BLOCK"
    elif verdict == "CANON_BLOCK":
        verdict = "WARN" if findings else "PASS"
    elif verdict not in {"PASS", "WARN", "CANON_BLOCK"}:
        verdict = "WARN" if findings else "PASS"
    return {
        "verdict": verdict,
        "canon_block": canon_block,
        "summary": summary,
        "findings": findings,
    }


def _participant_ids(packet: dict) -> list[str]:
    facts = packet.get("CANONICAL_FACTS") or {}
    ids = [str(pid) for pid in (facts.get("participant_ids") or []) if pid]
    if ids:
        return ids
    return [str(profile.get("character_id")) for profile in packet.get("participants") or [] if profile.get("character_id")]


def normalize_speakers(draft: dict, packet: dict) -> dict:
    """Map display names and 1-based participant indices to compiled character ids."""
    names: dict[str, str] = {"player": "PLAYER", "john": "PLAYER", "wizard": "PLAYER"}
    firsts: dict[str, list[str]] = {}
    ids = _participant_ids(packet)
    for index, cid in enumerate(ids, start=1):
        names[str(index)] = cid
        names[f"speaker {index}"] = cid
        names[f"character {index}"] = cid
        names[f"npc {index}"] = cid
        compact = cid.lower().replace("_", "")
        names[compact] = cid
        names[cid.lower().replace("_", " ")] = cid
        names[cid.lower().replace("npc_", "")] = cid
    for profile in packet.get("participants") or []:
        cid = str(profile.get("character_id") or "")
        display = str(profile.get("display_name") or "").strip()
        if not cid:
            continue
        names[cid.lower()] = cid
        if display:
            names[display.lower()] = cid
            first = display.split()[0].lower()
            firsts.setdefault(first, []).append(cid)
    for first, mapped in firsts.items():
        if len(mapped) == 1:
            names.setdefault(first, mapped[0])
    out = dict(draft)
    lines = []
    for line in draft.get("lines") or []:
        item = dict(line)
        raw = str(item.get("speaker_id") or "").strip()
        item["speaker_id"] = names.get(raw.lower(), raw)
        lines.append(item)
    out["lines"] = lines
    return out


def _secret_needles(packet: dict) -> list[tuple[str, str]]:
    needles = []
    private = packet.get("WRITER_ONLY_PRIVATE_FACTS") or {}
    for pid, facts in private.items():
        for fact in facts:
            text = str(fact).strip()
            if len(text) >= 24:
                needles.append((pid, text[:48].lower()))
    for item in packet.get("FORBIDDEN_REVELATIONS") or []:
        text = str(item).strip()
        if len(text) >= 24:
            needles.append(("forbidden", text[:48].lower()))
    return needles


def mechanics_audit_local(packet: dict, draft: dict) -> dict:
    findings: list[dict] = []
    participants = set(packet.get("CANONICAL_FACTS", {}).get("participant_ids") or [])
    permitted = " ".join(str(item).lower() for item in packet.get("PERMITTED_REVELATIONS") or [])
    needles = _secret_needles(packet)
    lines = draft.get("lines") if isinstance(draft, dict) else None
    if not lines:
        findings.append({"severity": "canon_block", "category": "structure", "detail": "Draft has no lines", "fix": "Write 12-30 spoken turns"})
        return parse_audit_result({"verdict": "CANON_BLOCK", "canon_block": True, "summary": "Empty draft", "findings": findings})

    speakers = []
    for line in lines:
        speaker = str(line.get("speaker_id") or "")
        text = str(line.get("text") or "")
        speakers.append(speaker)
        if speaker and speaker not in participants and speaker != "PLAYER":
            findings.append({
                "severity": "canon_block",
                "category": "identity",
                "detail": f"Unknown speaker {speaker} is not a compiled participant",
                "fix": "Use only participant ids or PLAYER",
            })
        if WORLDVIEW_LEAK.search(text):
            findings.append({
                "severity": "canon_block",
                "category": "metadata_leak",
                "detail": f"{speaker} spoke worldview/authoring metadata",
                "fix": "Remove labels and scores from spoken text",
            })
        lowered = text.lower()
        for owner, needle in needles:
            if needle and needle in lowered and needle not in permitted:
                if owner == speaker:
                    findings.append({
                        "severity": "canon_block",
                        "category": "secret_leakage",
                        "detail": f"{speaker} stated a writer-only private fact in dialogue",
                        "fix": "Keep the secret as subtext unless permitted",
                    })
                elif owner != "forbidden":
                    findings.append({
                        "severity": "canon_block",
                        "category": "knowledge",
                        "detail": f"{speaker} stated another character's private fact",
                        "fix": "Respect knowledge boundaries",
                    })
                else:
                    findings.append({
                        "severity": "canon_block",
                        "category": "forbidden_revelation",
                        "detail": "Dialogue contains a forbidden revelation",
                        "fix": "Remove the explicit reveal",
                    })

    if packet.get("SCENE_FUNCTION", {}).get("scene_type") == "consequence":
        trigger = packet.get("CANONICAL_FACTS", {}).get("trigger") or {}
        if not trigger.get("required_scene_id"):
            findings.append({
                "severity": "canon_block",
                "category": "predecessor",
                "detail": "Consequence packet lacks required_scene_id",
                "fix": "Bind a predecessor before writing",
            })
        pred = packet.get("CANONICAL_FACTS", {}).get("predecessor")
        if trigger.get("required_scene_id") and pred is None:
            findings.append({
                "severity": "canon_block",
                "category": "predecessor",
                "detail": "Consequence references a predecessor that was not compiled into the packet",
                "fix": "Include predecessor summary from the catalogue",
            })

    if packet.get("SCENE_FUNCTION", {}).get("scene_type") == "introduction":
        blob = " ".join(str(line.get("text") or "") for line in lines).lower()
        if "the quest is complete" in blob or "central contradiction is resolved" in blob:
            findings.append({
                "severity": "canon_block",
                "category": "quest_state",
                "detail": "Introduction resolves a principal quest or contradiction",
                "fix": "Leave the long conflict open",
            })

    blocks = [item for item in findings if item["severity"] == "canon_block"]
    verdict = "CANON_BLOCK" if blocks else ("WARN" if findings else "PASS")
    return parse_audit_result({
        "verdict": verdict,
        "canon_block": bool(blocks),
        "summary": "Local mechanics audit",
        "findings": findings,
    })


def merge_audits(*reports: dict) -> dict:
    findings = []
    for report in reports:
        findings.extend(report.get("findings") or [])
    canon_block = any(report.get("canon_block") for report in reports) or any(item.get("severity") == "canon_block" for item in findings)
    if canon_block:
        verdict = "CANON_BLOCK"
    elif any(report.get("verdict") == "WARN" or item.get("severity") == "warning" for report in reports for item in (report.get("findings") or [report])):
        verdict = "WARN"
    else:
        verdict = "PASS"
    summaries = [str(report.get("summary") or "") for report in reports if report.get("summary")]
    return parse_audit_result({
        "verdict": verdict,
        "canon_block": canon_block,
        "summary": " | ".join(summaries),
        "findings": findings,
    })


def _llm_audit(client: OllamaClient, system: str, packet: dict, draft: dict, *, model: str | None, temperature: float) -> dict:
    prompt = (
        system.split(".")[0]
        + "\n\nPACKET:\n"
        + json.dumps(packet, ensure_ascii=False)
        + "\n\nDIALOGUE:\n"
        + json.dumps(draft, ensure_ascii=False)
        + "\n\nReturn the audit schema. Use severity canon_block only for true canon violations."
    )
    resp = client.generate_with_retry(
        prompt,
        system=system,
        temperature=temperature,
        num_predict=1800,
        format_schema=AUDIT_SCHEMA,
        model=model,
    )
    if not resp.success:
        return parse_audit_result({
            "verdict": "WARN",
            "summary": resp.error or "audit failed",
            "findings": [{"severity": "warning", "category": "llm", "detail": resp.error or "audit failed", "fix": "Rerun audit"}],
        })
    return parse_audit_result(resp.data)


MECHANICS_SYSTEM = """You are the narrative-mechanics auditor for DuelMasterBattle offline authoring.
Check speaker knowledge, causal correctness, quest/world-state assumptions, predecessor state, secret leakage, contradictions, repetition, and unsupported player actions.
Use severity canon_block ONLY when a spoken line actually invents, leaks, or contradicts identity, relationships, secrets, inventory, quest state, history or witnessed facts, or when a speaker knows something their boundary forbids.
Do not CANON_BLOCK to report that facts were preserved, unchanged, or consistent. Those are notes, not blocks.
Do not CANON_BLOCK for mere dullness."""

SUBJECTIVITY_SYSTEM = """You are the character-subjectivity auditor.
Ask: could several characters say this unchanged? Check occupational vocabulary, individual voice, relationship charge, social status, personal interpretation, pressure behaviour, generic quest-NPC language, and overused tics.
Give actionable findings. Do not CANON_BLOCK; this auditor cannot own world state."""

EMOTIONAL_SYSTEM = """You are the emotional-craft auditor.
Check displayed vs hidden feeling, subtext, friction, status, vulnerability, hesitation/evasion, emotional movement, player impact, and whether the scene actually changes.
Give actionable findings. Do not CANON_BLOCK; this auditor cannot own world state."""


def soften_llm_canon_blocks(report: dict) -> dict:
    """LLM preservation notes cannot own CANON_BLOCK. Keep only findings that cite a real violation."""
    findings = []
    for raw in report.get("findings") or []:
        item = dict(raw)
        detail = str(item.get("detail") or "")
        if item.get("severity") == "canon_block" and not VIOLATION_LANGUAGE.search(detail):
            item["severity"] = "warning"
        findings.append(item)
    return parse_audit_result({
        "verdict": "WARN" if findings else "PASS",
        "canon_block": False,
        "summary": report.get("summary") or "",
        "findings": findings,
    })


def mechanics_audit(client: OllamaClient | None, packet: dict, draft: dict, *, model: str | None = None) -> dict:
    local = mechanics_audit_local(packet, draft)
    if client is None:
        return local
    llm = soften_llm_canon_blocks(_llm_audit(client, MECHANICS_SYSTEM, packet, draft, model=model, temperature=0.1))
    return merge_audits(local, llm)


def subjectivity_audit_local(packet: dict, draft: dict) -> dict:
    findings = []
    spoken = [str(line.get("text") or "") for line in (draft.get("lines") or []) if line.get("speaker_id") != "PLAYER"]
    if spoken and len(set(spoken)) <= max(1, len(spoken) // 3):
        findings.append({"severity": "warning", "category": "voice", "detail": "Many NPC lines are identical", "fix": "Differentiate speakers"})
    blob = " ".join(spoken)
    if GENERIC_QUEST.search(blob):
        findings.append({"severity": "warning", "category": "quest_terminal", "detail": "Generic quest-giver phrasing", "fix": "Root the ask in occupation and relationship history"})
    stagey = [text for text in spoken if STAGE_DIRECTION.search(text.strip())]
    if stagey and len(stagey) >= max(2, len(spoken) // 2):
        findings.append({
            "severity": "warning",
            "category": "quest_terminal",
            "detail": "Most lines read as stage directions rather than character speech",
            "fix": "Write spoken voice rooted in occupation, status and the scene's dramatic problem",
        })
    names = [p.get("display_name") for p in packet.get("participants") or []]
    if names and not any(name and name.split()[0] in blob for name in names):
        findings.append({"severity": "note", "category": "relationship", "detail": "No character is addressed by name", "fix": "Use specific address where natural"})
    return parse_audit_result({"verdict": "WARN" if findings else "PASS", "summary": "Local subjectivity audit", "findings": findings})


def emotional_audit_local(draft: dict) -> dict:
    findings = []
    lines = draft.get("lines") or []
    actions = [str(line.get("action") or "") for line in lines]
    if not any(actions):
        findings.append({"severity": "warning", "category": "subtext", "detail": "No physical actions or pauses", "fix": "Add hesitation, work-gestures or withheld replies"})
    texts = [str(line.get("text") or "") for line in lines]
    if texts and len(set(t.split("?")[0] for t in texts)) == 1:
        findings.append({"severity": "warning", "category": "movement", "detail": "Scene does not move off its first sentence", "fix": "Escalate or turn"})
    return parse_audit_result({"verdict": "WARN" if findings else "PASS", "summary": "Local emotional audit", "findings": findings})


def subjectivity_audit(client: OllamaClient | None, packet: dict, draft: dict, *, model: str | None = None) -> dict:
    local = subjectivity_audit_local(packet, draft)
    if client is None:
        return local
    llm = _llm_audit(client, SUBJECTIVITY_SYSTEM, packet, draft, model=model, temperature=0.1)
    llm["canon_block"] = False
    if llm.get("verdict") == "CANON_BLOCK":
        llm["verdict"] = "WARN"
        for item in llm.get("findings") or []:
            if item.get("severity") == "canon_block":
                item["severity"] = "warning"
    return merge_audits(local, llm)


def emotional_audit(client: OllamaClient | None, packet: dict, draft: dict, *, model: str | None = None) -> dict:
    local = emotional_audit_local(draft)
    if client is None:
        return local
    llm = _llm_audit(client, EMOTIONAL_SYSTEM, packet, draft, model=model, temperature=0.1)
    llm["canon_block"] = False
    if llm.get("verdict") == "CANON_BLOCK":
        llm["verdict"] = "WARN"
        for item in llm.get("findings") or []:
            if item.get("severity") == "canon_block":
                item["severity"] = "warning"
    return merge_audits(local, llm)
