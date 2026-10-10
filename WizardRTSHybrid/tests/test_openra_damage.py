"""Compare the adapted warhead chain to the OpenRA integer rules."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wizard_rts.openra_damage import (  # noqa: E402
    apply_percentage_modifiers,
    damage_versus,
    inflict_damage,
    warhead_damage,
)


def test_percentage_modifiers_match_openra_truncate() -> None:
    assert apply_percentage_modifiers(10, [100]) == 10
    assert apply_percentage_modifiers(10, [50]) == 5
    assert apply_percentage_modifiers(10, [100, 50]) == 5
    # (int)(10 * 0.33m) == 3 in C#.
    assert apply_percentage_modifiers(10, [33]) == 3


def test_versus_and_health_clamp() -> None:
    assert damage_versus({}, []) == 100
    assert damage_versus({"light": 50}, ["light"]) == 50
    assert damage_versus({"light": 50}, ["heavy"]) == 100
    assert warhead_damage(10, [], 50) == 5
    assert inflict_damage(12, 12, 4) == 8
    assert inflict_damage(3, 12, 10) == 0
    assert inflict_damage(0, 12, 10) == 0
