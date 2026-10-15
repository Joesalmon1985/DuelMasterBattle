"""The factions must actually DO things (docs/PLAYTEST_FIXES.md, observation 7): not "no crash" but expansion, recruitment, movement, attacks.

One deterministic 36 game-minute war on the standard map (about a minute), judged by scripts/ai_report.behaviour_checks.

T1.1 (14 Oct 2026): the AIs no longer know where the other capitals are; they find them by reconnaissance and by walking past them, so the first attacks come
about ten minutes later than they did (30 minutes: 3 attacks by 3 factions; 40 minutes: 14 by 5). The horizon was 22 minutes before.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB))
sys.path.insert(0, str(HYB.parent))

spec = importlib.util.spec_from_file_location("ai_report", HYB / "scripts" / "ai_report.py")
ai_report = importlib.util.module_from_spec(spec)
sys.modules["ai_report"] = ai_report
spec.loader.exec_module(ai_report)


def test_factions_expand_recruit_move_attack_and_do_not_stall() -> None:
    result = ai_report.run(507, 36, aggressive=True)
    failed = [k for k, v in result["checks"].items() if not v]
    assert not failed, f"behaviour checks failed: {failed}\n{result['final']}"
    last = result["final"]["factions"]
    assert sum(1 for f in last.values() if f["mcv_deployed"] >= 1) >= 4, "at least four factions deployed a second command centre"
    assert sum(f["attacks"] for f in last.values()) >= 3
    assert sum(1 for f in last.values() if f["navy"] > 0) >= 1 or sum(f["fleet_attacks"] + f["fleet_defends"] for f in last.values()) >= 1
    assert result["worst_step_ms"] < 4000, "a single simulation step must never freeze the game for seconds"


def test_peace_runs_expand_without_a_single_battle() -> None:
    result = ai_report.run(11, 16, aggressive=False)
    last = result["final"]["factions"]
    assert all(f["alive"] for f in last.values())
    assert sum(f["unit_kills"] + f["building_kills"] for f in last.values()) == 0
    assert sum(1 for f in last.values() if f["mcv_deployed"] >= 1) >= 4
    assert all(f["completed"] >= 8 for f in last.values())
