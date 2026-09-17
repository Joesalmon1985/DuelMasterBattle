"""T026 board generation checks."""

from __future__ import annotations

from sim.dmb.world.generation import (
    NUMBER_MULTISET,
    TERRAIN_MULTISET,
    BoardBuilder,
    generate,
    validate_setup,
)


def test_terrain_and_token_multisets() -> None:
    plan = generate(7, 2)
    terrains = list(plan.hex_terrain.values())
    tokens = sorted(plan.hex_token.values())
    for name in set(TERRAIN_MULTISET):
        assert terrains.count(name) == TERRAIN_MULTISET.count(name)
    assert tokens == sorted(NUMBER_MULTISET)


def test_two_and_six_faction_placements_legal() -> None:
    for count in (2, 6):
        plan = BoardBuilder.generate(11, count)
        assert validate_setup(plan) == []
        assert len(plan.cores) == count * 2


def test_same_seed_deterministic() -> None:
    a = generate(99, 2)
    b = generate(99, 2)
    assert a.to_dict()["hex_terrain"] == b.to_dict()["hex_terrain"]
    assert a.to_dict()["hex_token"] == b.to_dict()["hex_token"]
    assert [(c.faction_id, c.node_id) for c in a.cores] == [
        (c.faction_id, c.node_id) for c in b.cores
    ]


def test_fallback_fixture_loads_when_forced() -> None:
    from sim.dmb.world import generation as g

    original = g._select_cores

    def never(*_a, **_k):
        return None

    g._select_cores = never  # type: ignore[assignment]
    try:
        plan = generate(12345, 2)
    finally:
        g._select_cores = original  # type: ignore[assignment]
    assert plan.used_fallback is True
    assert plan.attempts == g.MAX_ATTEMPTS
    assert validate_setup(plan) == []
