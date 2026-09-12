from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from .config import config
from .database import DialogueDatabase
from .normalize import jaccard, stable_id
from .ollama_client import OllamaClient
from .prompts import (
    CLASSIFIER_SCHEMA, REVIEW_SCHEMA, WRITER_SCHEMA,
    classifier_prompts, reviewer_prompts, writer_prompts,
)
from .validator import enrich_exchange, validate_exchange
from .workbook_reader import extract_beats, read_cast_rows, workbook_sha256
from .worldviews import WorldviewSet, load_worldviews

logger = logging.getLogger(__name__)


@dataclass
class RunCounters:
    classifier_requests: int = 0
    writer_requests: int = 0
    reviewer_requests: int = 0
    approved: int = 0
    needs_review: int = 0
    skipped_approved: int = 0

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def ingest_cast(db: DialogueDatabase, workbook: Path, cast_id: str) -> dict:
    rows = read_cast_rows(workbook, cast_id)
    instances = extract_beats(rows)
    digest = workbook_sha256(workbook)
    stats = db.ingest(workbook, digest, rows, instances)
    stats["workbook_hash"] = digest
    return stats


def _candidate_payload(db: DialogueDatabase, candidate: dict) -> dict:
    ctx = db.bank_context(candidate["bank_id"])
    return {
        "bank_id": candidate["bank_id"],
        "representative_text": candidate["source_text"],
        "beat_type": candidate["beat_type"],
        "consequential": bool(candidate["consequential"]),
        "examples": [
            {
                "character": i["character"],
                "personality": i["personality_summary"],
                "story_context": i["story_context"],
                "source_text": i["source_text"],
                "branch_a": i["branch_a"],
                "branch_b": i["branch_b"],
            }
            for i in ctx["instances"][:3]
        ],
    }


def build_banks(db: DialogueDatabase, cast_id: str, client: OllamaClient, counters: RunCounters) -> None:
    for beat in db.unbanked_beats(cast_id):
        reps = db.bank_representatives(cast_id)
        scored = []
        for rep in reps:
            if bool(rep["consequential"]) != bool(beat["consequential"]):
                continue
            score = jaccard(beat["source_text"], rep["source_text"])
            if score >= config.generation.candidate_min_overlap:
                scored.append((score, rep))
        scored.sort(key=lambda item: (-item[0], item[1]["bank_id"]))
        candidate_rows = [item[1] for item in scored[:config.generation.candidate_limit]]

        if not candidate_rows:
            bank_id = stable_id("BANK", beat["beat_id"], length=12)
            db.create_bank(bank_id, beat["beat_id"])
            continue

        current_instances = db.conn.execute(
            "SELECT * FROM beat_instances WHERE beat_id=? AND cast_id=? ORDER BY source_row, source_field",
            (beat["beat_id"], cast_id),
        ).fetchall()
        current = {
            "beat_id": beat["beat_id"],
            "source_text": beat["source_text"],
            "beat_type": beat["beat_type"],
            "consequential": bool(beat["consequential"]),
            "branch_a": beat["branch_a"],
            "branch_b": beat["branch_b"],
            "instances": [
                {"character": r["character"], "personality": r["personality_summary"], "story_context": r["story_context"]}
                for r in current_instances[:3]
            ],
        }
        candidates = [_candidate_payload(db, row) for row in candidate_rows]
        system, prompt = classifier_prompts(current, candidates)
        counters.classifier_requests += 1
        resp = client.generate_with_retry(
            prompt,
            system=system,
            temperature=config.ollama.temp_classifier,
            num_predict=config.ollama.num_predict_classifier,
            format_schema=CLASSIFIER_SCHEMA,
        )
        classification = resp.data if resp.success and resp.data else {
            "best_match": None,
            "confidence": 0.0,
            "can_share_dialogue": False,
            "reason": f"Classifier failed safely: {resp.error}",
        }
        candidate_ids = {c["bank_id"] for c in candidates}
        best = classification.get("best_match")
        confidence = float(classification.get("confidence", 0.0) or 0.0)
        if (
            classification.get("can_share_dialogue") is True
            and best in candidate_ids
            and confidence >= config.generation.classification_confidence
        ):
            db.assign_bank(beat["beat_id"], best, classification)
        else:
            bank_id = stable_id("BANK", beat["beat_id"], length=12)
            db.create_bank(bank_id, beat["beat_id"], classification)


def _generation_is_current(gen: dict, *, model: str, worldviews: WorldviewSet, source_fingerprint: str) -> bool:
    return (
        gen.get("status") == "approved"
        and gen.get("model") == model
        and gen.get("prompt_version") == config.generation.prompt_version
        and gen.get("worldview_version") == worldviews.version
        and gen.get("source_fingerprint") == source_fingerprint
    )


def _review_once(db: DialogueDatabase, bank_id: str, exchange: dict, bank_context: dict,
                 worldviews: WorldviewSet, client: OllamaClient, counters: RunCounters) -> tuple[dict | None, str | None]:
    system, prompt = reviewer_prompts(bank_context, exchange, worldviews.prompt_text())
    db.set_generation_status(bank_id, "reviewing", reviewer_increment=True)
    counters.reviewer_requests += 1
    resp = client.generate_with_retry(
        prompt,
        system=system,
        temperature=config.ollama.temp_reviewer,
        num_predict=config.ollama.num_predict_reviewer,
        format_schema=REVIEW_SCHEMA,
    )
    if not resp.success:
        return None, resp.error
    return resp.data, None


def generate_bank(db: DialogueDatabase, bank_id: str, client: OllamaClient,
                  worldviews: WorldviewSet, counters: RunCounters) -> str:
    bank_context = db.bank_context(bank_id)
    model = client.model
    source_fingerprint = db.bank_source_fingerprint(bank_id)
    gen = db.generation(bank_id)
    if _generation_is_current(gen, model=model, worldviews=worldviews, source_fingerprint=source_fingerprint):
        counters.skipped_approved += 1
        return "approved"

    repair_issues: list | None = None
    last_exchange: dict | None = None
    last_review: dict | None = None
    last_error: str | None = None

    for _ in range(1 + config.generation.max_repair_attempts):
        system, prompt = writer_prompts(bank_id, bank_context, worldviews.prompt_text(), repair_issues)
        db.set_generation_status(
            bank_id, "generating", model=model, prompt_version=config.generation.prompt_version,
            worldview_version=worldviews.version, source_fingerprint=source_fingerprint,
            writer_increment=True,
        )
        counters.writer_requests += 1
        resp = client.generate_with_retry(
            prompt,
            system=system,
            temperature=config.ollama.temp_writer,
            num_predict=config.ollama.num_predict_writer,
            format_schema=WRITER_SCHEMA,
        )
        if not resp.success or not resp.data:
            last_error = resp.error
            repair_issues = [{"category": "generation", "detail": resp.error or "Writer failed"}]
            continue

        exchange = enrich_exchange(resp.data, worldviews, bank_id)
        last_exchange = exchange
        deterministic = validate_exchange(exchange, bank_context, worldviews)
        if deterministic:
            repair_issues = deterministic
            last_error = f"Deterministic validation found {len(deterministic)} issue(s)"
            db.set_generation_status(bank_id, "pending", generated=exchange, error=last_error)
            continue

        db.set_generation_status(bank_id, "generated", generated=exchange, error="")
        review, review_error = _review_once(db, bank_id, exchange, bank_context, worldviews, client, counters)
        if review_error:
            last_error = review_error
            repair_issues = [{"category": "review", "detail": review_error}]
            continue
        last_review = review
        error_issues = [i for i in review.get("issues", []) if i.get("severity") == "error"] if review else []
        if review and review.get("approved") is True and not error_issues:
            db.set_generation_status(
                bank_id, "approved", model=model, prompt_version=config.generation.prompt_version,
                worldview_version=worldviews.version, source_fingerprint=source_fingerprint,
                generated=exchange, review=review, error="",
            )
            counters.approved += 1
            return "approved"
        repair_issues = review.get("issues", []) if review else [{"category": "review", "detail": "Reviewer did not approve"}]
        last_error = review.get("summary", "Reviewer did not approve") if review else "Reviewer did not approve"

    db.set_generation_status(
        bank_id, "needs_review", model=model, prompt_version=config.generation.prompt_version,
        worldview_version=worldviews.version, source_fingerprint=source_fingerprint,
        generated=last_exchange, review=last_review, error=last_error or "Repair attempts exhausted",
    )
    counters.needs_review += 1
    return "needs_review"


def generate_cast(db: DialogueDatabase, cast_id: str, client: OllamaClient,
                  worldviews: WorldviewSet | None = None) -> dict:
    worldviews = worldviews or load_worldviews()
    counters = RunCounters()
    build_banks(db, cast_id, client, counters)
    for bank_id in db.bank_ids_for_cast(cast_id):
        generate_bank(db, bank_id, client, worldviews, counters)
    result = db.cast_stats(cast_id)
    result.update(counters.as_dict())
    return result


def review_cast(db: DialogueDatabase, cast_id: str, client: OllamaClient,
                worldviews: WorldviewSet | None = None) -> dict:
    worldviews = worldviews or load_worldviews()
    counters = RunCounters()
    for bank_id in db.bank_ids_for_cast(cast_id):
        gen = db.generation(bank_id)
        exchange = db.generation_payload(bank_id)
        if not exchange or gen["status"] == "approved":
            continue
        context = db.bank_context(bank_id)
        deterministic = validate_exchange(exchange, context, worldviews)
        if deterministic:
            db.set_generation_status(bank_id, "needs_review", error=json.dumps(deterministic, ensure_ascii=False))
            counters.needs_review += 1
            continue
        review, error = _review_once(db, bank_id, exchange, context, worldviews, client, counters)
        if review and review.get("approved") and not any(i.get("severity") == "error" for i in review.get("issues", [])):
            db.set_generation_status(bank_id, "approved", review=review, error="")
            counters.approved += 1
        else:
            db.set_generation_status(bank_id, "needs_review", review=review, error=error or (review or {}).get("summary", "Not approved"))
            counters.needs_review += 1
    result = db.cast_stats(cast_id)
    result.update(counters.as_dict())
    return result
