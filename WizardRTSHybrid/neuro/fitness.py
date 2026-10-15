"""Seat fitness (design section 8, execution plan T4.1): pure functions, no simulation access.

    Tier S (the world survived to the horizon, the seat did not collapse):  F = survive_base + vp_weight*VP + margin_weight*(VP - median VP of the other root factions)
    Tier E (the world survived, the seat collapsed at t_e):                  F = elim_base + elim_time_weight*(t_e/T) + vp_weight*VP        (VP: permanent conquest awards only)
    Tier C (collective loss at t_c, every seat):                             F = loss_base + loss_time_weight*(t_c/T)                      (VP ignored)

Selection uses the advantage over the control game, `advantage(F_candidate, F_control)`.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass


@dataclass
class FitnessConfig:
    survive_base: float = 1000.0
    vp_weight: float = 10.0
    margin_weight: float = 3.0
    elim_base: float = 100.0
    elim_time_weight: float = 400.0
    loss_base: float = -1000.0
    loss_time_weight: float = 500.0
    horizon_min: float = 240.0


def seat_fitness(cfg: FitnessConfig, end_reason: str, t_end_min: float, seat_vp: int, seat_state: str, collapsed_at_min: float | None,
                 other_root_vps: list[int]) -> tuple[float, str]:
    """(F, tier) of one seat. `seat_vp` is the seat's VP at the end, or, for a collapsed seat, its permanent conquest VP only.
    A game that ended early for another reason than a collective loss scores the survivors as tier S at the time it ended."""
    horizon = float(cfg.horizon_min)
    if end_reason == "collective_loss":
        return cfg.loss_base + cfg.loss_time_weight * (min(float(t_end_min), horizon) / horizon), "C"
    if seat_state == "collapsed":
        t_e = float(t_end_min if collapsed_at_min is None else collapsed_at_min)
        return cfg.elim_base + cfg.elim_time_weight * (min(t_e, horizon) / horizon) + cfg.vp_weight * seat_vp, "E"
    median = statistics.median(other_root_vps) if other_root_vps else 0.0
    return cfg.survive_base + cfg.vp_weight * seat_vp + cfg.margin_weight * (seat_vp - median), "S"


def advantage(f_candidate: float, f_control: float) -> float:
    return float(f_candidate) - float(f_control)
