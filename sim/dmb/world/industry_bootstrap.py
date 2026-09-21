"""Install normal prehistoric industry for settlements from board truth.

Binds primaries to real touching hexes, selects a catalogue recipe whose
inputs match available industrial resources, and wires one processor + three
military factories. Does not invent quest routes.
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Any

from sim.dmb.industry.layers import ResourceLayerService
from sim.dmb.industry.primary import PrimaryChannel
from sim.dmb.industry.projection import IndustryProjection
from sim.dmb.industry.routes import FactoryRoute, ProcessorBinding
from sim.dmb.people.jobs import JobService
from sim.dmb.world.settlement_layout import PRIMARY_LABEL, public_occupation_for

ROOT = Path(__file__).resolve().parents[3]
RECIPES_PATH = ROOT / "godot_project" / "content" / "source" / "recipes" / "mvp.json"

# Canonical industrial resources (not Catan construction goods).
TERRAIN_INDUSTRIAL = {
    "woodland": {
        "renewable": ("ind.prehistoric.woodland.renewable", "Foraged berries and nuts"),
        "finite": ("ind.prehistoric.woodland.finite", "Hunted boar"),
    },
    "ore_mountains": {
        "renewable": ("ind.prehistoric.ore_mountains.renewable", "Mountain herbs"),
        "finite": ("ind.prehistoric.ore_mountains.finite", "Flint"),
    },
    "clay_mountains": {
        "renewable": ("ind.prehistoric.clay_mountains.renewable", "Spring water"),
        "finite": ("ind.prehistoric.clay_mountains.finite", "Surface clay"),
    },
    "fields": {
        "renewable": ("ind.prehistoric.fields.renewable", "Foraged food"),
        "finite": ("ind.prehistoric.fields.finite", "Wild grain"),
    },
    "grazing_land": {
        "renewable": ("ind.prehistoric.grazing_land.renewable", "Wild wool"),
        "finite": ("ind.prehistoric.grazing_land.finite", "Hunted goats"),
    },
    "desert": {
        "renewable": ("ind.prehistoric.desert.renewable", "Desert fruit"),
        "finite": ("ind.prehistoric.desert.finite", "Desert game"),
    },
}

TERRAIN_SPRITE = {
    "woodland": "woodcutter",
    "ore_mountains": "miner",
    "clay_mountains": "worker",
    "fields": "farmer",
    "grazing_land": "shepherd",
    "desert": "villager_a",
}

UNIT_DEFS = (
    "unit.ancient.skirmisher",
    "unit.ancient.line",
    "unit.ancient.heavy",
)


def _load_mvp_recipes() -> list[dict[str, Any]]:
    data = json.loads(RECIPES_PATH.read_text(encoding="utf-8"))
    return [r for r in data.get("recipes") or [] if r.get("era") == "prehistoric" and r.get("mvp_subset")]


def _terrain_for_resource(resource_id: str) -> str | None:
    for terrain, kinds in TERRAIN_INDUSTRIAL.items():
        for _kind, (rid, _name) in kinds.items():
            if rid == resource_id:
                return terrain
    return None


def _pick_recipe(available_terrains: set[str], *, blocked_terrains: set[str] | None = None) -> dict[str, Any] | None:
    """Pick an MVP recipe whose both inputs are available; prefer unblocked terrains."""
    blocked = blocked_terrains or set()
    candidates: list[tuple[int, dict[str, Any]]] = []
    for recipe in _load_mvp_recipes():
        ta = _terrain_for_resource(str(recipe.get("input_a_id") or ""))
        tb = _terrain_for_resource(str(recipe.get("input_b_id") or ""))
        if not (ta and tb and ta in available_terrains and tb in available_terrains and ta != tb):
            continue
        blocked_count = int(ta in blocked) + int(tb in blocked)
        # Prefer fewer blocked inputs, then catalogue order.
        candidates.append((blocked_count, recipe))
    if not candidates:
        return None
    candidates.sort(key=lambda row: row[0])
    return candidates[0][1]


def _blocked_terrains_for_node(state: Any, node_id: str, by_terrain: dict[str, list[str]]) -> set[str]:
    from sim.dmb.hazards.queries import industrial_blocked

    blocked: set[str] = set()
    for terrain, hexes in by_terrain.items():
        if any(industrial_blocked(state.board, hid) for hid in hexes):
            blocked.add(terrain)
    return blocked


def _ensure_workplace_jobs(state: Any, *, node_id: str, building_ids: list[str]) -> None:
    """Register vacant site-worker slots for settlement workplaces; backfill people."""
    jobs = JobService(state)
    for bid in building_ids:
        building = state.buildings.get(bid) or {}
        slot = str(building.get("slot_kind") or "")
        job_id = "job:attendant" if slot == "factory" else "job:site_worker"
        key = f"{'attendant' if slot == 'factory' else 'site_worker'}:{bid}"
        if key not in (state.definitions.get("jobs") or {}):
            jobs.register_job(key, workplace_id=bid, job_id=job_id, node_id=node_id, person_id=None)
    jobs.backfill_tick(name_prefix="Worker")


def _write_fx_layout(
    state: Any,
    *,
    node_id: str,
    processor_id: str | None,
    factory_ids: list[str],
    recipe: dict[str, Any] | None,
) -> None:
    sites = []
    for b in state.buildings.values():
        if b.get("node_id") != node_id or not b.get("active", True):
            continue
        slot = str(b.get("slot_kind") or "")
        if slot not in {"primary", "processor", "factory"}:
            continue
        sites.append(
            {
                "id": str(b["id"]),
                "kind": "source" if slot == "primary" else slot,
                "label": b.get("label") or slot,
                "terrain": b.get("terrain"),
            }
        )
    fx_industry = state.board.setdefault("fx_industry_by_node", {})
    fx_industry[node_id] = {
        "node_id": node_id,
        "processor_id": processor_id,
        "factory_ids": list(factory_ids),
        "output_id": (recipe or {}).get("output_id"),
        "output_name": (recipe or {}).get("output_name"),
        "recipe_id": (recipe or {}).get("id"),
        "layout": {"sites": sites},
    }
    if str((state.player or {}).get("node_id") or "") == node_id or not state.board.get("fx_industry"):
        state.board["fx_industry"] = dict(fx_industry[node_id])


def bootstrap_settlement_industry(sim: Any, *, node_id: str, settlement_id: str, faction_id: str) -> dict[str, Any]:
    """Bind primaries / processor / factories for one settlement. Idempotent-ish."""
    state = sim.state
    board = state.board
    hex_terrain = board.get("hex_terrain") or {}
    touching = list(board.get("node_hexes", {}).get(node_id) or [])
    by_terrain: dict[str, list[str]] = {}
    for hid in touching:
        terr = str(hex_terrain.get(hid) or "")
        if terr:
            by_terrain.setdefault(terr, []).append(str(hid))

    primaries = [
        b
        for b in state.buildings.values()
        if b.get("node_id") == node_id
        and str(b.get("slot_kind") or "") == "primary"
        and b.get("active", True)
    ]
    primaries.sort(key=lambda b: (int(b.get("slot_index") or 0), str(b.get("id"))))
    processors = [
        b
        for b in state.buildings.values()
        if b.get("node_id") == node_id and str(b.get("slot_kind") or "") == "processor" and b.get("active", True)
    ]
    factories = [
        b
        for b in state.buildings.values()
        if b.get("node_id") == node_id and str(b.get("slot_kind") or "") == "factory" and b.get("active", True)
    ]
    factories.sort(key=lambda b: (int(b.get("slot_index") or 0), str(b.get("id"))))

    # Label centre / warehouse.
    for b in state.buildings.values():
        if b.get("node_id") != node_id:
            continue
        slot = str(b.get("slot_kind") or "")
        if slot == "centre":
            b["label"] = b.get("label") or "Settlement Centre"
        elif slot == "warehouse":
            b["label"] = b.get("label") or "Warehouse"

    # Bind primaries to touching hexes (round-robin terrains).
    terrain_order = sorted(by_terrain.keys())
    layers = ResourceLayerService(state.industry)
    channel_by_resource: dict[str, str] = {}
    bound_terrains: set[str] = set()
    for i, primary in enumerate(primaries):
        if not terrain_order:
            primary["label"] = primary.get("label") or "Resource site"
            continue
        terrain = terrain_order[i % len(terrain_order)]
        hid = by_terrain[terrain][0]
        meta = TERRAIN_INDUSTRIAL.get(terrain) or {}
        # Prefer renewable for display resource; still create both layers when defined.
        renew = meta.get("renewable")
        finite = meta.get("finite")
        resource_id = renew[0] if renew else (finite[0] if finite else "")
        resource_name = renew[1] if renew else (finite[1] if finite else "Resource")
        primary["hex_id"] = hid
        primary["terrain"] = terrain
        primary["resource_name"] = resource_name
        primary["label"] = PRIMARY_LABEL.get(terrain, f"{terrain.replace('_', ' ').title()} workings")
        bound_terrains.add(terrain)
        if renew:
            layer = layers.create_layer(hid, renew[0], "prehistoric", 0, finite=False)
            ch = PrimaryChannel(
                f"channel:{primary['id']}:renewable",
                str(primary["id"]),
                node_id,
                terrain,
                "prehistoric",
                0,
                renew[0],
                layer.layer_id,
                False,
                Fraction(1, 10),
                True,
            )
            sim.industry.install_channel(ch)
            channel_by_resource[renew[0]] = ch.channel_id
        if finite:
            layer = layers.create_layer(hid, finite[0], "prehistoric", 0, finite=True)
            ch = PrimaryChannel(
                f"channel:{primary['id']}:finite",
                str(primary["id"]),
                node_id,
                terrain,
                "prehistoric",
                0,
                finite[0],
                layer.layer_id,
                True,
                Fraction(1, 10),
                True,
            )
            sim.industry.install_channel(ch)
            channel_by_resource.setdefault(finite[0], ch.channel_id)

    blocked = _blocked_terrains_for_node(state, node_id, by_terrain)
    recipe = _pick_recipe(bound_terrains, blocked_terrains=blocked)
    local_recipe: dict[str, Any] | None = None
    if recipe is None and bound_terrains:
        # Single-terrain settlements still process renewable+finite from their
        # own hex — otherwise only multi-hex vertices can ever muster units.
        terrain = sorted(bound_terrains)[0]
        meta = TERRAIN_INDUSTRIAL.get(terrain) or {}
        renew = meta.get("renewable")
        finite = meta.get("finite")
        if renew and finite and renew[0] in channel_by_resource and finite[0] in channel_by_resource:
            local_recipe = {
                "id": f"recipe.local.{terrain}",
                "input_a_id": renew[0],
                "input_b_id": finite[0],
                "processor_name": f"{terrain.replace('_', ' ').title()} Works",
                "output_name": f"{terrain.replace('_', ' ').title()} provisions",
                "output_id": f"processed.local.{terrain}",
            }
            recipe = local_recipe
    workplace_ids = [str(b["id"]) for b in primaries + processors + factories]
    _ensure_workplace_jobs(state, node_id=node_id, building_ids=workplace_ids)

    result: dict[str, Any] = {
        "node_id": node_id,
        "settlement_id": settlement_id,
        "terrains": sorted(bound_terrains),
        "recipe_id": None,
        "processor_id": None,
        "factory_ids": [],
        "industry_active": False,
    }

    processor = processors[0] if processors else None
    factory_ids: list[str] = []

    if recipe and processor and len(factories) >= 1:
        input_a = str(recipe["input_a_id"])
        input_b = str(recipe["input_b_id"])
        ch_a = channel_by_resource.get(input_a)
        ch_b = channel_by_resource.get(input_b)
        if ch_a and ch_b:
            processor["label"] = str(recipe.get("processor_name") or recipe.get("building_family") or "Works")
            processor["recipe_id"] = recipe["id"]
            processor["output_name"] = recipe.get("output_name")
            sim.industry.install_processor(
                ProcessorBinding(
                    str(processor["id"]),
                    str(recipe["id"]),
                    "prehistoric",
                    ch_a,
                    ch_b,
                    active=True,
                )
            )
            for i, factory in enumerate(factories[:3]):
                unit_def = UNIT_DEFS[i % len(UNIT_DEFS)]
                label = {0: "Skirmisher Yard", 1: "Line Yard", 2: "Heavy Yard"}.get(i, "Muster Yard")
                factory["label"] = label
                # Avoid double-installing routes on re-bootstrap.
                if str(factory["id"]) not in (sim.state.industry.get("routes") or {}):
                    sim.industry.install_route(
                        FactoryRoute(str(factory["id"]), str(processor["id"]), unit_def, 2 + i)
                    )
                sim.industry.factories.create(
                    str(factory["id"]),
                    node_id=node_id,
                    faction_id=faction_id,
                    era="prehistoric",
                    unit_def_id=unit_def,
                )
                factory_ids.append(str(factory["id"]))
            result.update(
                {
                    "recipe_id": recipe["id"],
                    "processor_id": str(processor["id"]),
                    "factory_ids": factory_ids,
                    "industry_active": True,
                    "output_name": recipe.get("output_name"),
                }
            )
        else:
            recipe = None
    else:
        recipe = None
        if processor:
            processor["label"] = processor.get("label") or "Works"

    _write_fx_layout(
        state,
        node_id=node_id,
        processor_id=str(processor["id"]) if processor else None,
        factory_ids=factory_ids,
        recipe=recipe,
    )

    # Point projection at this node briefly so sync_carrier_jobs sees local connections.
    prev_fx = state.board.get("fx_industry")
    state.board["fx_industry"] = dict((state.board.get("fx_industry_by_node") or {}).get(node_id) or {})
    IndustryProjection(state).sync_carrier_jobs()
    if prev_fx is not None and str((state.player or {}).get("node_id") or "") != node_id:
        state.board["fx_industry"] = prev_fx

    for person in state.people.values():
        if person.get("node_id") != node_id:
            continue
        workplace = state.buildings.get(str(person.get("workplace_id") or "")) or {}
        terrain = str(workplace.get("terrain") or "")
        if terrain and terrain in TERRAIN_SPRITE:
            person["sprite"] = TERRAIN_SPRITE[terrain]
            person["visual_profile"] = person["sprite"]
        elif not person.get("sprite"):
            person["sprite"] = "worker"
            person["visual_profile"] = "worker"
        person["occupation"] = public_occupation_for(person, workplace=workplace)

    return result


def bootstrap_all_settlement_industry(sim: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for settlement in sim.state.settlements.values():
        if settlement.get("staging") or not settlement.get("operational", True):
            continue
        node_id = str(settlement.get("node_id") or "")
        faction_id = str(settlement.get("faction_id") or "")
        if not node_id:
            continue
        out.append(
            bootstrap_settlement_industry(
                sim,
                node_id=node_id,
                settlement_id=str(settlement["id"]),
                faction_id=faction_id,
            )
        )
    return out
