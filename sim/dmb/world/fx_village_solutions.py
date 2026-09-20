"""FX-VILLAGE shortage solutions via owning industry / hazard services.

Never assigns buildings[factory].output_rate. Production resumes only after the
next IndustryService tick computes positive rates. Processor/factory IDs come
from fx_village meta bound to the real settlement.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.industry.routes import FactoryRoute, ProcessorBinding


def _factory_rate(state: WorldState, factory_id: str) -> float:
    from sim.dmb.industry import fraction

    rates: dict[str, Any] = {}
    for event in reversed((state.industry or {}).get("events") or []):
        if event.get("kind") == "industry_rates":
            rates = event.get("rates") or {}
            break
    return float(fraction(rates.get(factory_id) or 0))


def _fx(state: WorldState) -> dict[str, Any]:
    return (state.board or {}).get("fx_village") or {}


def apply_demon_solution(state: WorldState) -> dict[str, Any]:
    """Route A: cube already cleared by HazardDuelService; re-select Route A processor."""
    fx = _fx(state)
    factory_id = str(fx.get("factory_id") or "")
    proc_a = str(fx.get("processor_route_a_id") or "")
    if not factory_id or not proc_a:
        return {"status": "missing_fx_meta"}
    from sim.dmb.industry.service import IndustryService

    industry = IndustryService(state)
    industry.install_route(FactoryRoute(factory_id, proc_a, "unit.ancient.skirmisher", 2))
    meta = state.definitions.setdefault("installed_routes", {})
    if "route:A" in meta:
        meta["route:A"]["selected"] = True
        meta["route:A"]["available"] = True
        meta["route:A"].pop("blocked_by", None)
    if "route:B" in meta:
        meta["route:B"]["selected"] = False
    fx_ind = state.board.setdefault("fx_industry", {})
    fx_ind["processor_id"] = proc_a
    fx_ind["selected_route"] = "route:A"
    industry.advance_quanta(1)
    rate = _factory_rate(state, factory_id)
    factory = state.buildings.get(factory_id)
    if isinstance(factory, dict):
        factory["shortage"] = rate <= 0
        factory["label"] = "Village factory (working)" if rate > 0 else "Village factory (quiet)"
    quest_id = str(fx.get("quest_id") or "")
    if quest_id and quest_id in (state.quests or {}):
        state.quests[quest_id]["pending_resolution"] = "demon_duel"
        state.quests[quest_id]["claims_demon_cleared"] = True
    return {
        "status": "applied",
        "solution": "demon_duel",
        "factory_id": factory_id,
        "route": "route:A",
        "processor_id": proc_a,
        "computed_rate": rate,
    }


def apply_sluice_solution(state: WorldState) -> dict[str, Any]:
    """Route B: activate Route B processor and select it for the shortage factory."""
    fx = _fx(state)
    factory_id = str(fx.get("factory_id") or "")
    proc_b = str(fx.get("processor_route_b_id") or "")
    if not factory_id or not proc_b:
        return {"status": "missing_fx_meta"}
    from sim.dmb.industry.service import IndustryService

    industry = IndustryService(state)
    processors = (state.industry or {}).get("processors") or {}
    existing = processors.get(proc_b) or {}
    industry.install_processor(
        ProcessorBinding(
            proc_b,
            str(existing.get("recipe_id") or "recipe.prehistoric.pre_07"),
            str(existing.get("era") or "prehistoric"),
            str(existing.get("input_a_channel_id") or ""),
            str(existing.get("input_b_channel_id") or ""),
            active=True,
            modifier=Fraction(1),
        )
    )
    if proc_b in state.buildings:
        state.buildings[proc_b]["active"] = True
    industry.install_route(FactoryRoute(factory_id, proc_b, "unit.ancient.skirmisher", 2))
    mods = state.definitions.setdefault("production_modifiers", {})
    mods.pop("sluice_sabotage", None)
    meta = state.definitions.setdefault("installed_routes", {})
    if "route:B" in meta:
        meta["route:B"]["selected"] = True
        meta["route:B"]["available"] = True
        meta["route:B"].pop("modifier", None)
    if "route:A" in meta and not meta["route:A"].get("available"):
        meta["route:A"]["selected"] = False
    fx_ind = state.board.setdefault("fx_industry", {})
    fx_ind["processor_id"] = proc_b
    fx_ind["selected_route"] = "route:B"
    history = state.definitions.setdefault("history_facts", {})
    history["sluice_open"] = {"fact_id": "sluice_open", "predicate": "sluice_open", "value": True}
    industry.advance_quanta(1)
    rate = _factory_rate(state, factory_id)
    factory = state.buildings.get(factory_id)
    if isinstance(factory, dict):
        factory["shortage"] = rate <= 0
        factory["label"] = "Village factory (working)" if rate > 0 else "Village factory (quiet)"
    quest_id = str(fx.get("quest_id") or "")
    if quest_id and quest_id in (state.quests or {}):
        state.quests[quest_id]["pending_resolution"] = "sluice_route"
        state.quests[quest_id]["claims_demon_cleared"] = False
    return {
        "status": "applied",
        "solution": "sluice_route",
        "factory_id": factory_id,
        "route": "route:B",
        "processor_id": proc_b,
        "claims_demon_cleared": False,
        "computed_rate": rate,
    }


def confirm_pending_quest(state: WorldState) -> dict[str, Any] | None:
    """Complete an open quest when industry already restored (playable path)."""
    fx = _fx(state)
    quest_id = str(fx.get("quest_id") or "")
    if not quest_id or quest_id not in (state.quests or {}):
        return None
    quest = state.quests[quest_id]
    intervention = str(quest.get("pending_resolution") or quest.get("resolution") or "")
    if not intervention:
        return None
    if quest.get("status") in {"completed", "resolved_by_world", "failed_with_consequence"}:
        return {"status": "already_terminal", "quest": dict(quest)}
    factory_id = str(fx.get("factory_id") or "")
    if factory_id and _factory_rate(state, factory_id) <= 0:
        return {"status": "waiting_for_industry", "computed_rate": 0.0}
    from sim.dmb.quests.runtime import QuestService

    svc = QuestService(state)
    if quest.get("status") == "offered":
        svc.accept(quest_id)
    result = svc.evaluate(
        quest_id,
        world_signals={"output_confirmed": True, "intervention": intervention},
    )
    state.quests[quest_id]["resolution"] = intervention
    return result
