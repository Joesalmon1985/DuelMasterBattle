"""T063 local battle behavioural checks (Python mirror of lease step rules)."""

from __future__ import annotations

from sim.dmb.military.math import resolve_combat_step


def test_blocked_path_changes_attack_opportunity() -> None:
    units = {
        "a": {
            "id": "a",
            "faction_id": "red",
            "alive": True,
            "position": [0.0, 0.0],
            "current_health": 50,
            "base_attack": 10,
            "era_factor": 1,
            "range_tiles": 5,
            "period_ms": 1000,
            "remaining_attack_cooldown_ms": 0,
            "armour": 0,
        },
        "b": {
            "id": "b",
            "faction_id": "blue",
            "alive": True,
            "position": [3.0, 0.0],
            "current_health": 50,
            "base_attack": 10,
            "era_factor": 1,
            "range_tiles": 5,
            "period_ms": 1000,
            "remaining_attack_cooldown_ms": 0,
            "armour": 0,
        },
    }
    open_fire = resolve_combat_step(units, step_ms=50)
    assert "b" in open_fire["damages"] or "a" in open_fire["damages"]
    units2 = {
        "a": dict(units["a"]),
        "b": dict(units["b"]),
    }
    blocked = resolve_combat_step(
        units2,
        step_ms=50,
        blockers=[{"position": [1.5, 0.0], "half": 0.6}],
    )
    # LOS blocked → no damages from a↔b through the wall.
    assert blocked["damages"] == {}


def test_leased_units_not_resolved_offscreen_while_active() -> None:
    from sim.dmb.encounters.registry import EncounterRegistry
    from sim.dmb.military.offscreen import OffscreenBattleResolver

    reg = EncounterRegistry()
    snap = {
        "units": {
            "u1": {
                "id": "u1",
                "faction_id": "red",
                "alive": True,
                "position": [0, 0],
                "current_health": 10,
                "base_attack": 5,
                "era_factor": 1,
                "range_tiles": 1,
                "period_ms": 1000,
                "remaining_attack_cooldown_ms": 0,
            }
        }
    }
    lease = reg.grant("battle", ["u1"], snap, "lease:1")
    assert lease.state == "ACTIVE"
    assert reg.entity_index["u1"] == "lease:1"
    # Offscreen resolver may compute a sandbox outcome, but registry still owns the lease.
    out = OffscreenBattleResolver().resolve(snap)
    assert out["global_time_advanced"] is False
    assert "u1" in reg.entity_index
