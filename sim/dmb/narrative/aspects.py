"""Seven Aspects and repeat-safe checks (C09 / T080)."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError
from sim.dmb.people.registry import relationship_band

ASPECT_IDS = (
    "reason",
    "empathy",
    "authority",
    "guile",
    "resolve",
    "curiosity",
    "wonder",
)

FALLIBILITY = {
    "reason": "overlooks_emotion",
    "empathy": "overtrusts",
    "authority": "overvalues_legitimacy",
    "guile": "suspects_too_much",
    "resolve": "persists_unwisely",
    "curiosity": "discounts_danger",
    "wonder": "overinterprets_patterns",
}

THRESHOLDS = {"easy": 2, "demanding": 4, "exceptional": 6}

ASPECT_SCHEMA_VERSION = 1
MIN_SCORE = 0
MAX_SCORE = 5
DEFAULT_SCORE = 1

_CONTENT_ROOT = (
    Path(__file__).resolve().parents[3] / "godot_project" / "content" / "source" / "aspects"
)


def load_aspect_content(root: Path | None = None) -> dict[str, Any]:
    base = root or _CONTENT_ROOT
    path = base / "aspects.json"
    if not path.is_file():
        return {"aspects": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return {"aspects": payload}
    return {"aspects": list(payload.get("aspects") or [])}


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(parts: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical(parts).encode("utf-8")).hexdigest()
    return digest[:32]


@dataclass
class AspectService:
    state: WorldState

    def _store(self) -> dict[str, Any]:
        aspects = self.state.definitions.setdefault("aspects", {})
        if "schema_version" not in aspects:
            aspects["schema_version"] = ASPECT_SCHEMA_VERSION
        aspects.setdefault("scores", {})
        aspects.setdefault("applied_changes", {})
        aspects.setdefault("failed_fingerprints", {})
        aspects.setdefault("passive_log", [])
        return aspects

    def ensure_scores(self, actor_id: str = "player") -> dict[str, int]:
        store = self._store()
        scores = dict(store["scores"].get(actor_id) or {})
        for aspect_id in ASPECT_IDS:
            if aspect_id not in scores:
                scores[aspect_id] = DEFAULT_SCORE
            else:
                scores[aspect_id] = max(MIN_SCORE, min(MAX_SCORE, int(scores[aspect_id])))
        store["scores"][actor_id] = scores
        return dict(scores)

    def get_score(self, aspect_id: str, *, actor_id: str = "player") -> int:
        aspect_id = str(aspect_id).lower()
        if aspect_id not in ASPECT_IDS:
            raise TypeValidationError(f"unknown aspect {aspect_id}")
        return int(self.ensure_scores(actor_id)[aspect_id])

    def apply_change_once(
        self,
        aspect_id: str,
        delta: int,
        *,
        change_id: str,
        actor_id: str = "player",
    ) -> dict[str, Any]:
        """Quest ±1 effect, clamped 0–5, applied once per change_id."""
        aspect_id = str(aspect_id).lower()
        if aspect_id not in ASPECT_IDS:
            raise TypeValidationError(f"unknown aspect {aspect_id}")
        if not change_id:
            raise TypeValidationError("change_id required")
        store = self._store()
        applied = dict(store["applied_changes"])
        if change_id in applied:
            return {
                "ok": True,
                "applied": False,
                "idempotent": True,
                "aspect_id": aspect_id,
                "score": self.get_score(aspect_id, actor_id=actor_id),
                "change_id": change_id,
            }
        scores = self.ensure_scores(actor_id)
        before = int(scores[aspect_id])
        # Contract: quest effects are ±1 clamped.
        step = 1 if int(delta) > 0 else -1 if int(delta) < 0 else 0
        after = max(MIN_SCORE, min(MAX_SCORE, before + step))
        scores[aspect_id] = after
        store["scores"][actor_id] = scores
        applied[change_id] = {
            "aspect_id": aspect_id,
            "actor_id": actor_id,
            "delta": step,
            "before": before,
            "after": after,
        }
        store["applied_changes"] = applied
        return {
            "ok": True,
            "applied": True,
            "idempotent": False,
            "aspect_id": aspect_id,
            "before": before,
            "after": after,
            "score": after,
            "change_id": change_id,
        }

    def retry_fingerprint(
        self,
        *,
        aspect_id: str,
        score: int,
        evidence_mod: int,
        relationship_mod: int,
        quest_predicates: dict[str, Any] | None = None,
    ) -> str:
        return _fingerprint(
            {
                "aspect_id": str(aspect_id).lower(),
                "score": int(score),
                "evidence_mod": int(evidence_mod),
                "relationship_mod": int(relationship_mod),
                "quest_predicates": dict(quest_predicates or {}),
            }
        )

    def check(
        self,
        aspect_id: str,
        *,
        threshold: str | int = "demanding",
        evidence_mod: int = 0,
        relationship_score: int | None = None,
        relationship_mod: int | None = None,
        quest_predicates: dict[str, Any] | None = None,
        actor_id: str = "player",
        allow_retry_token: str | None = None,
    ) -> dict[str, Any]:
        aspect_id = str(aspect_id).lower()
        if aspect_id not in ASPECT_IDS:
            raise TypeValidationError(f"unknown aspect {aspect_id}")
        score = self.get_score(aspect_id, actor_id=actor_id)
        ev = max(0, min(2, int(evidence_mod)))
        if relationship_mod is None:
            rel = relationship_band(int(relationship_score or 0))
        else:
            rel = max(-1, min(1, int(relationship_mod)))
        if isinstance(threshold, str):
            need = THRESHOLDS.get(threshold)
            if need is None:
                raise TypeValidationError(f"unknown threshold {threshold}")
        else:
            need = int(threshold)
        total = score + ev + rel
        fp = self.retry_fingerprint(
            aspect_id=aspect_id,
            score=score,
            evidence_mod=ev,
            relationship_mod=rel,
            quest_predicates=quest_predicates,
        )
        store = self._store()
        failed = dict(store["failed_fingerprints"])
        if fp in failed and allow_retry_token != fp:
            return {
                "ok": True,
                "passed": False,
                "blocked": True,
                "reason": "repeat_fingerprint",
                "aspect_id": aspect_id,
                "score": score,
                "evidence_mod": ev,
                "relationship_mod": rel,
                "total": total,
                "threshold": need,
                "fingerprint": fp,
                "fallibility": FALLIBILITY[aspect_id],
            }
        passed = total >= need
        if not passed:
            failed[fp] = {
                "aspect_id": aspect_id,
                "score": score,
                "evidence_mod": ev,
                "relationship_mod": rel,
                "quest_predicates": dict(quest_predicates or {}),
            }
            store["failed_fingerprints"] = failed
        elif fp in failed:
            # Success after material change clears the old failure for this fingerprint.
            failed.pop(fp, None)
            store["failed_fingerprints"] = failed
        return {
            "ok": True,
            "passed": passed,
            "blocked": False,
            "aspect_id": aspect_id,
            "score": score,
            "evidence_mod": ev,
            "relationship_mod": rel,
            "total": total,
            "threshold": need,
            "fingerprint": fp,
            "fallibility": FALLIBILITY[aspect_id],
        }

    def clear_fingerprint(self, fingerprint: str) -> None:
        store = self._store()
        failed = dict(store["failed_fingerprints"])
        failed.pop(fingerprint, None)
        store["failed_fingerprints"] = failed

    def passive_comment(
        self,
        aspect_id: str,
        *,
        scene_id: str,
        cause_id: str | None = None,
        fact_version: int = 1,
        filtered_context: dict[str, Any] | None = None,
        actor_id: str = "player",
    ) -> dict[str, Any]:
        """Rate-limited passive remark; reads only filtered context."""
        aspect_id = str(aspect_id).lower()
        if aspect_id not in ASPECT_IDS:
            raise TypeValidationError(f"unknown aspect {aspect_id}")
        store = self._store()
        key = f"{actor_id}:{aspect_id}:{scene_id}:{cause_id or ''}:{int(fact_version)}"
        for entry in store["passive_log"]:
            if entry.get("key") == key:
                return {
                    "ok": True,
                    "emitted": False,
                    "rate_limited": True,
                    "aspect_id": aspect_id,
                    "fallibility": FALLIBILITY[aspect_id],
                    "text_key": entry.get("text_key"),
                }
        safe_ctx = {
            k: v
            for k, v in dict(filtered_context or {}).items()
            if k in {"label", "kind", "role", "status", "quest_stage", "cause_active"}
        }
        text_key = f"aspect.{aspect_id}.passive"
        entry = {
            "key": key,
            "aspect_id": aspect_id,
            "scene_id": scene_id,
            "cause_id": cause_id,
            "fact_version": int(fact_version),
            "text_key": text_key,
            "context": safe_ctx,
            "fallibility": FALLIBILITY[aspect_id],
        }
        log = list(store["passive_log"])
        log.append(entry)
        store["passive_log"] = log
        return {
            "ok": True,
            "emitted": True,
            "rate_limited": False,
            "aspect_id": aspect_id,
            "fallibility": FALLIBILITY[aspect_id],
            "text_key": text_key,
            "context": deepcopy(safe_ctx),
        }
