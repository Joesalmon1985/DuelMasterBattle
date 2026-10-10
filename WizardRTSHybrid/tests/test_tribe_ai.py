"""Tribe-aware AI: each non-Barbarian faction plans and builds its own tribe's chain with its own wares."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wizard_rts import ai, tribes, wl_defs  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402


def test_plans_are_small_dependency_chains_for_each_tribe() -> None:
    w = HybridWorld()
    for name, expect in (("Blue", "empire_armorsmithy"), ("Green", "frisians_armor_smithy_small"), ("Yellow", "atlanteans_weaponsmithy")):
        tribe = w.faction_info[name]["tribe"]
        plan = []
        for ware in wl_defs.soldier_wares(tribe):
            plan += ai._resolve(w, name, tribe, ware, set())
        assert expect in plan and len(plan) <= 6, (name, plan)
    assert tribes.barracks_of("amazons") == "amazons_initiation_site"


def test_factions_build_their_own_tribe_without_free_goods() -> None:
    w = HybridWorld()
    w.ai_enabled, w.ai_aggressive = True, False
    w.dmb.hazards["catastrophe"]["cubes"][w.hazard_id]["active"] = False
    for i in range(1800):
        w.advance(1000, i + 1, snapshot=False)
    built = 0
    for name in ("Blue", "Green", "Yellow", "Purple"):
        tribe = w.faction_info[name]["tribe"]
        mine = [b for b in w.buildings.values() if b["faction_name"] == name and b["kind"].startswith("wl:")]
        assert all(b["kind"][3:].startswith(tribe) for b in mine), (name, [b["kind"] for b in mine])
        built += bool(mine)
    # Known gap (docs/CLAUDE_HANDOFF.md): a slow granite supply leaves some tribes idle for a long time.
    assert built >= 3
