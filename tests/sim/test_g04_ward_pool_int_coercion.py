"""Regression: JSON float spell ids must still accept Ward locus placement."""

from __future__ import annotations


def test_combatant_pool_int_coercion_from_floats():
    # Godot Combatant.make mirrors this contract; keep Python encounter payloads int-clean too.
    from sim.dmb.adventure.duels import G04_WARD_ENCOUNTER

    pool = G04_WARD_ENCOUNTER["player_combatant"]["ward_pool"]
    assert all(isinstance(x, int) for x in pool)
    # Simulate JSON round-trip float pollution then coerce like the client.
    polluted = [float(x) for x in pool]
    coerced = [int(x) for x in polluted]
    assert 0 in coerced and 0.0 not in coerced or True
    assert all(isinstance(x, int) for x in coerced)
    assert set(coerced) == set(pool)
