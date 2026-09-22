"""Era transition planning package (C11 / G06)."""

from sim.dmb.eras.continuity import ContinuityService
from sim.dmb.eras.collapse import CollapseDisposition, select_collapse_factions
from sim.dmb.eras.fission import FissionDisposition, choose_compact_pairing, plan_fission
from sim.dmb.eras.planner import (
    EraTransitionPlan,
    EraTransitionPlanner,
    TransitionTrigger,
    compute_plan_hash,
    theoretical_site_capacity,
    validate_plan_freshness,
)
from sim.dmb.eras.upgrades import CoreUpgradeService, mark_legacy_sites, upgrade_cores

__all__ = [
    "CollapseDisposition",
    "ContinuityService",
    "CoreUpgradeService",
    "EraTransitionPlan",
    "EraTransitionPlanner",
    "FissionDisposition",
    "TransitionTrigger",
    "choose_compact_pairing",
    "compute_plan_hash",
    "mark_legacy_sites",
    "plan_fission",
    "select_collapse_factions",
    "theoretical_site_capacity",
    "upgrade_cores",
    "validate_plan_freshness",
]
