"""Encode ObservationV1 / ActionCandidate into fixed numeric tensors (C12)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

SCHEMA_PATH = Path(__file__).resolve().parent / "observation_schema.json"
_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
OBS_DIM = int(_SCHEMA["observation_dim"])
CAND_DIM = int(_SCHEMA["candidate_dim"])

_GOODS = ("timber", "brick", "wheat", "sheep", "ore")
_KIND_INDEX = {
    "construct": 0,
    "trade_propose": 1,
    "diplomacy_propose": 2,
    "military_move": 3,
    "military_objective": 3,
    "military_withdraw": 3,
    "tech_pick": 4,
    "hazard_treat": 5,
    "noop": 6,
}


def _stock_total(stocks: dict[str, Any], good: str) -> float:
    total = 0.0
    for store in (stocks or {}).values():
        if not isinstance(store, dict):
            continue
        goods = store.get("goods") or store
        if isinstance(goods, dict):
            total += float(goods.get(good) or 0)
    return total


def encode_observation(observation: dict[str, Any], *, faction_index: int = 0) -> np.ndarray:
    vec = np.zeros(OBS_DIM, dtype=np.float64)
    time = observation.get("time") or {}
    own = observation.get("own") or {}
    public = observation.get("public") or {}
    observed = observation.get("observed") or {}

    def put(idx: int, value: float, scale: float = 1.0) -> None:
        if 0 <= idx < OBS_DIM and scale:
            vec[idx] = float(value) / float(scale)

    put(0, float(time.get("turn") or 0), 1000)
    put(1, float(time.get("round") or 0), 100)
    put(2, float(time.get("game_ms") or 0), 3_600_000)
    put(3, float(own.get("vp") or 0), 10)
    put(4, len(own.get("centres") or []), 8)
    put(5, len(own.get("roads") or []), 32)
    put(6, len(own.get("units") or []), 32)
    put(7, len(own.get("carts") or []), 16)
    stocks = own.get("stocks") or {}
    for i, good in enumerate(_GOODS):
        put(8 + i, _stock_total(stocks, good), 20)
    cat = public.get("catastrophe") or {}
    put(13, 1.0 if cat else 0.0, 1)
    put(14, 1.0 if time.get("seat_is_active") else 0.0, 1)
    era = str(time.get("era") or "prehistoric").lower()
    for i, name in enumerate(("prehistoric", "historic", "modern", "future")):
        put(15 + i, 1.0 if era == name else 0.0, 1)
    put(19, len(observed.get("enemies") or []), 32)
    put(20, len(own.get("hand") or []), 7)
    research = own.get("research") or {}
    put(21, len(research.get("activated") or []), 24)
    put(22, len(observation.get("commitments") or []), 8)
    put(23, faction_index, 6)
    # Remaining dims reserved / zero (missing masks).
    return vec


def encode_candidate(candidate: dict[str, Any]) -> np.ndarray:
    vec = np.zeros(CAND_DIM, dtype=np.float64)
    kind = str(candidate.get("action_kind") or "")
    params = candidate.get("params") or {}
    benefit = candidate.get("benefit") or {}
    cost = candidate.get("cost") or {}

    ki = _KIND_INDEX.get(kind)
    if ki is not None and ki < CAND_DIM:
        vec[ki] = 1.0
    vec[7] = float(benefit.get("vp_gain") or 0) / 2.0
    # Utility proxy from construction-like benefits.
    utility = (
        1000 * float(benefit.get("vp_gain") or 0)
        + 100 * float(benefit.get("new_catan_good_types") or 0)
        + 20 * float(benefit.get("target_best_pips") or 0)
        + 10 * float(benefit.get("additional_milliunits_per_second") or 0)
        - 5 * float(benefit.get("required_cart_edge_trips") or 0)
        - 10 * float(benefit.get("new_road_edges_needed") or 0)
    )
    vec[8] = utility / 2000.0
    vec[9] = float(benefit.get("shortage_goods_covered") or 0) / 4.0
    vec[10] = float(benefit.get("route_length") or 0) / 20.0
    vec[11] = 1.0 if benefit.get("threat_observed") else 0.0
    vec[12] = 1.0 if benefit.get("target_observed") else 0.0
    action = str(params.get("action") or "")
    if action == "city":
        vec[13] = 1.0
    elif action == "settlement":
        vec[14] = 1.0
    elif action == "road":
        vec[15] = 1.0
    objective = str(params.get("objective") or "")
    if objective == "attack" or kind == "military_move":
        vec[16] = 1.0
    if objective == "defend":
        vec[17] = 1.0
    if isinstance(cost, dict):
        vec[18] = sum(float(v) for v in cost.values() if isinstance(v, (int, float))) / 20.0
    return vec


def encode_candidates(candidates: list[dict[str, Any]]) -> np.ndarray:
    if not candidates:
        return np.zeros((0, CAND_DIM), dtype=np.float64)
    return np.stack([encode_candidate(c) for c in candidates], axis=0)
