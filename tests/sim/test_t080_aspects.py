"""T080 seven Aspects: checks, fingerprints, once-only rewards."""

from __future__ import annotations

from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.narrative.aspects import (
    ASPECT_IDS,
    AspectService,
    load_aspect_content,
)


def _world() -> WorldState:
    return WorldState(world_id=WorldId("world:t080"), ids=IdAllocator(WorldId("world:t080")))


def test_initial_scores_and_content() -> None:
    state = _world()
    aspects = AspectService(state)
    scores = aspects.ensure_scores()
    assert set(scores) == set(ASPECT_IDS)
    assert all(v == 1 for v in scores.values())
    content = load_aspect_content()
    assert len(content["aspects"]) == 7


def test_check_meets_demanding_with_evidence_and_relation() -> None:
    """1 + evidence 2 + relation 1 meets threshold 4."""
    state = _world()
    aspects = AspectService(state)
    result = aspects.check(
        "reason",
        threshold="demanding",
        evidence_mod=2,
        relationship_mod=1,
        quest_predicates={"quest": "q1", "stage": "ask"},
    )
    assert result["score"] == 1
    assert result["evidence_mod"] == 2
    assert result["relationship_mod"] == 1
    assert result["total"] == 4
    assert result["threshold"] == 4
    assert result["passed"] is True
    assert result["blocked"] is False


def test_failed_repeat_same_fingerprint_blocked() -> None:
    state = _world()
    aspects = AspectService(state)
    first = aspects.check(
        "empathy",
        threshold="demanding",
        evidence_mod=0,
        relationship_mod=0,
        quest_predicates={"quest": "q1"},
    )
    assert first["passed"] is False
    assert first["blocked"] is False
    second = aspects.check(
        "empathy",
        threshold="demanding",
        evidence_mod=0,
        relationship_mod=0,
        quest_predicates={"quest": "q1"},
    )
    assert second["blocked"] is True
    assert second["reason"] == "repeat_fingerprint"
    assert second["fingerprint"] == first["fingerprint"]


def test_new_evidence_enables_retry() -> None:
    state = _world()
    aspects = AspectService(state)
    failed = aspects.check(
        "curiosity",
        threshold="demanding",
        evidence_mod=0,
        relationship_mod=0,
        quest_predicates={"quest": "q1"},
    )
    assert failed["passed"] is False
    # Material evidence change → new fingerprint → retry allowed.
    retry = aspects.check(
        "curiosity",
        threshold="demanding",
        evidence_mod=2,
        relationship_mod=1,
        quest_predicates={"quest": "q1"},
    )
    assert retry["blocked"] is False
    assert retry["passed"] is True
    assert retry["fingerprint"] != failed["fingerprint"]


def test_plus_one_reward_cannot_be_farmed() -> None:
    state = _world()
    aspects = AspectService(state)
    first = aspects.apply_change_once("wonder", 1, change_id="reward:quest:q1")
    assert first["applied"] is True
    assert first["after"] == 2
    second = aspects.apply_change_once("wonder", 1, change_id="reward:quest:q1")
    assert second["applied"] is False
    assert second["idempotent"] is True
    assert second["score"] == 2
    # Different change_id can apply once more, still clamped.
    third = aspects.apply_change_once("wonder", 5, change_id="reward:quest:q2")
    assert third["applied"] is True
    assert third["after"] == 3  # ±1 step only


def test_passive_comment_rate_limited() -> None:
    state = _world()
    aspects = AspectService(state)
    a = aspects.passive_comment(
        "guile",
        scene_id="village",
        cause_id="shortage",
        fact_version=1,
        filtered_context={"label": "Worker", "stocks": 99},
    )
    assert a["emitted"] is True
    assert "stocks" not in a.get("context", {})
    b = aspects.passive_comment(
        "guile",
        scene_id="village",
        cause_id="shortage",
        fact_version=1,
        filtered_context={"label": "Worker"},
    )
    assert b["rate_limited"] is True
    assert b["emitted"] is False


def test_relationship_score_mapping() -> None:
    state = _world()
    aspects = AspectService(state)
    low = aspects.check("authority", threshold=2, evidence_mod=0, relationship_score=-40)
    assert low["relationship_mod"] == -1
    mid = aspects.check("authority", threshold=2, evidence_mod=0, relationship_score=0)
    assert mid["relationship_mod"] == 0
    high = aspects.check("authority", threshold=2, evidence_mod=0, relationship_score=40)
    assert high["relationship_mod"] == 1
