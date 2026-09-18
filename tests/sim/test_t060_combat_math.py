"""T060 shared combat math and targeting oracles."""

from __future__ import annotations

import json
from pathlib import Path

from sim.dmb.military.math import CombatMath, compute_damage, resolve_combat_step

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "godot_project"
    / "content"
    / "fixtures"
    / "combat_math.json"
)


def test_golden_damage_cases() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for case in data["cases"]:
        got = compute_damage(
            base_attack=case["base_attack"],
            era_factor=case["era_factor"],
            attack_modifiers=case.get("attack_modifiers", 1.0),
            cover=case["cover"],
            armour=case.get("armour", 0),
        )
        assert got == case["expected_damage"], case["id"]
    assert CombatMath.compute_damage(base_attack=15, era_factor=1, cover=0.25) == 11
    assert CombatMath.compute_damage(base_attack=15, era_factor=10, cover=0.25) == 113


def test_target_order_health_then_id() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for case in data["targeting"]["cases"]:
        got = CombatMath.choose_target(case["attacker"], case["candidates"])
        assert got == case["expected_target"], case["id"]


def test_simultaneous_lethal_then_dead_cannot_act() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    sim = data["simultaneity"]
    units = {uid: dict(u) for uid, u in sim["units"].items()}
    step1 = resolve_combat_step(units, step_ms=sim["step_ms"])
    assert len(step1["fired"]) == 2
    assert all(not units[uid]["alive"] for uid in units)
    step2 = resolve_combat_step(units, step_ms=sim["step_ms"])
    assert step2["fired"] == []
    assert step2["damages"] == {}
