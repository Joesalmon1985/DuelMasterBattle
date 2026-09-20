"""FX-VILLAGE shortage solutions — restore factory output via Route A or B.

Industry/route mutations only. Quest completion stays with QuestService.evaluate
so scenario tests can drive the state machine explicitly after confirming output.
"""

from __future__ import annotations

from typing import Any

from sim.dmb.core.state import WorldState


def apply_demon_solution(state: WorldState) -> dict[str, Any]:
    """Route A: demon cleared → enable selected route, resume factory output."""
    fx = (state.board or {}).get("fx_village") or {}
    factory_id = str(fx.get("factory_id") or "building:factory_main")
    routes = state.definitions.setdefault("installed_routes", {})
    route_a = routes.get("route:A")
    if isinstance(route_a, dict):
        route_a["available"] = True
        route_a["selected"] = True
        route_a.pop("blocked_reason", None)
    factory = state.buildings.get(factory_id)
    if isinstance(factory, dict):
        factory["output_rate"] = 1.0
        factory["shortage"] = False
        factory["allocation"] = {"route": "route:A", "units": 1}
    quest_id = str(fx.get("quest_id") or "")
    if quest_id and quest_id in (state.quests or {}):
        state.quests[quest_id]["pending_resolution"] = "demon_duel"
        state.quests[quest_id]["claims_demon_cleared"] = True
    return {
        "status": "applied",
        "solution": "demon_duel",
        "factory_id": factory_id,
        "route": "route:A",
        "output_rate": (factory or {}).get("output_rate") if isinstance(factory, dict) else None,
    }


def apply_sluice_solution(state: WorldState) -> dict[str, Any]:
    """Route B: sluice sabotage removed → enable alternate route; do not claim demon cleared."""
    fx = (state.board or {}).get("fx_village") or {}
    factory_id = str(fx.get("factory_id") or "building:factory_main")
    mods = state.definitions.setdefault("production_modifiers", {})
    mods.pop("sluice_sabotage", None)
    routes = state.definitions.setdefault("installed_routes", {})
    route_b = routes.get("route:B")
    if isinstance(route_b, dict):
        route_b["available"] = True
        route_b["selected"] = True
        route_b.pop("modifier", None)
    route_a = routes.get("route:A")
    if isinstance(route_a, dict) and not route_a.get("available"):
        route_a["selected"] = False
    factory = state.buildings.get(factory_id)
    if isinstance(factory, dict):
        factory["output_rate"] = 1.0
        factory["shortage"] = False
        factory["allocation"] = {"route": "route:B", "units": 1}
    history = state.definitions.setdefault("history_facts", {})
    history["sluice_open"] = {"fact_id": "sluice_open", "predicate": "sluice_open", "value": True}
    quest_id = str(fx.get("quest_id") or "")
    if quest_id and quest_id in (state.quests or {}):
        state.quests[quest_id]["pending_resolution"] = "sluice_route"
        state.quests[quest_id]["claims_demon_cleared"] = False
    return {
        "status": "applied",
        "solution": "sluice_route",
        "factory_id": factory_id,
        "route": "route:B",
        "claims_demon_cleared": False,
        "output_rate": (factory or {}).get("output_rate") if isinstance(factory, dict) else None,
    }


def confirm_pending_quest(state: WorldState) -> dict[str, Any] | None:
    """Complete an open quest when industry already restored (playable path)."""
    fx = (state.board or {}).get("fx_village") or {}
    quest_id = str(fx.get("quest_id") or "")
    if not quest_id or quest_id not in (state.quests or {}):
        return None
    quest = state.quests[quest_id]
    intervention = str(quest.get("pending_resolution") or quest.get("resolution") or "")
    if not intervention:
        return None
    if quest.get("status") in {"completed", "resolved_by_world", "failed_with_consequence"}:
        return {"status": "already_terminal", "quest": dict(quest)}
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
