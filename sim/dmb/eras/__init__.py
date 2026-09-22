"""Era transition planning package (C11 / G06)."""

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

__all__ = [
    "CollapseDisposition",
    "EraTransitionPlan",
    "EraTransitionPlanner",
    "FissionDisposition",
    "TransitionTrigger",
    "choose_compact_pairing",
    "compute_plan_hash",
    "plan_fission",
    "select_collapse_factions",
    "theoretical_site_capacity",
    "validate_plan_freshness",
]
