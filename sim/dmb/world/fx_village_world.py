"""FX-VILLAGE as a real BoardBuilder settlement slice (G05).

Fixtures select/arrange state on the production runtime; they do not invent a
parallel node outside board topology or fake terrain independent of hexes.
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Any

from sim.dmb.construction.buildings import BuildingService
from sim.dmb.core.world import WorldSim, bootstrap_world
from sim.dmb.hazards.service import CatastropheService
from sim.dmb.industry import fraction
from sim.dmb.industry.layers import ResourceLayerService
from sim.dmb.industry.primary import PrimaryChannel
from sim.dmb.industry.projection import IndustryProjection
from sim.dmb.industry.routes import FactoryRoute, ProcessorBinding
from sim.dmb.people.jobs import JobService
from sim.dmb.people.registry import PeopleService
from sim.dmb.player.visits import VisitService
from sim.dmb.quests.binding import QuestBinder
from sim.dmb.quests.causes import CauseTracker
from sim.dmb.world.generation import BoardBuilder, SetupPlan
from sim.dmb.world.setup import WorldSetupService

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / "godot_project" / "content" / "fixtures" / "village" / "fx_village_v1.json"
QUEST_PATH = (
    ROOT / "godot_project" / "content" / "source" / "quests" / "shortage" / "factory_shortage.json"
)

TERRAIN_RESOURCE = {
    "woodland": ("ind.prehistoric.woodland.renewable", False, "Timber"),
    "ore_mountains": ("ind.prehistoric.ore_mountains.finite", True, "Ore"),
    "clay_mountains": ("ind.prehistoric.clay_mountains.renewable", False, "Clay"),
    "fields": ("ind.prehistoric.fields.renewable", False, "Grain"),
    "grazing_land": ("ind.prehistoric.grazing.renewable", False, "Wool"),
}

TERRAIN_SPRITE = {
    "woodland": "woodcutter",
    "ore_mountains": "miner",
    "clay_mountains": "worker",
    "fields": "farmer",
    "grazing_land": "shepherd",
}

SPRITE_BY_JOB = {
    "job.factory_worker": "worker",
    "job:attendant": "worker",
    "job:carrier": "worker",
}


def person_sprite_for(person: dict[str, Any], *, terrain: str | None = None) -> str:
    """Map persistent person/job/workplace to an existing character sprite family."""
    explicit = str(person.get("sprite") or person.get("visual_profile") or "")
    if explicit:
        return explicit
    job = str(person.get("job_id") or "")
    if job in SPRITE_BY_JOB:
        if terrain and terrain in TERRAIN_SPRITE and job == "job:carrier":
            return TERRAIN_SPRITE[terrain]
        return SPRITE_BY_JOB[job]
    if terrain and terrain in TERRAIN_SPRITE:
        return TERRAIN_SPRITE[terrain]
    role = str(person.get("role") or "")
    if role in {"worker", "carrier", "attendant"}:
        return "worker"
    return "villager_a"


def _pick_shortage_settlement(plan: SetupPlan) -> tuple[Any, dict[str, list[str]]]:
    """Prefer a core whose touching hexes include woodland + ore (+ a third productive)."""
    board = plan.board
    best = None
    best_hexes: dict[str, list[str]] = {}
    for core in plan.cores:
        by_terrain: dict[str, list[str]] = {}
        for hid in board.touching_hexes(core.node_id):
            by_terrain.setdefault(str(plan.hex_terrain[hid]), []).append(str(hid))
        terrains = set(by_terrain)
        if "woodland" not in terrains or "ore_mountains" not in terrains:
            continue
        score = 10
        if "clay_mountains" in terrains:
            score += 4
        score += len(terrains - {"desert"})
        if score > (best[0] if best else -1):
            best = (score, core)
            best_hexes = by_terrain
    if best is None:
        raise RuntimeError(
            f"seed {plan.seed} has no core with woodland+ore; choose another deterministic seed"
        )
    return best[1], best_hexes


def _buildings_on_node(state, node_id: str, slot_kind: str) -> list[dict[str, Any]]:
    rows = [
        b
        for b in state.buildings.values()
        if b.get("node_id") == node_id and str(b.get("slot_kind") or "") == slot_kind and b.get("active", True)
    ]
    rows.sort(key=lambda b: (int(b.get("slot_index") or 0), str(b.get("id"))))
    return rows


def _human_building_label(slot_kind: str, terrain: str | None = None, shortage: bool | None = None) -> str:
    if slot_kind == "primary" and terrain:
        return {
            "woodland": "Woodland cuttings",
            "ore_mountains": "Ore ridge",
            "clay_mountains": "Clay pits",
            "fields": "Grain fields",
            "grazing_land": "Pasture",
        }.get(terrain, f"{terrain.replace('_', ' ').title()} source")
    if slot_kind == "processor":
        return "Works"
    if slot_kind == "factory":
        if shortage is True:
            return "Village factory (quiet)"
        if shortage is False:
            return "Village factory (working)"
        return "Village factory"
    if slot_kind == "centre":
        return "Settlement centre"
    if slot_kind == "warehouse":
        return "Warehouse"
    return slot_kind.replace("_", " ").title()


def load_fx_village(seed: int = 507) -> WorldSim:
    """Build FX-VILLAGE on a real generated two-faction board settlement."""
    meta_file = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    template = json.loads(QUEST_PATH.read_text(encoding="utf-8"))
    sim = bootstrap_world(world_id="world:fx-village", seed=seed)
    state = sim.state
    plan = BoardBuilder.generate(seed, 2)
    WorldSetupService(state).apply(plan)

    core, terrain_hexes = _pick_shortage_settlement(plan)
    node_id = str(core.node_id)
    faction_id = str(core.faction_id)
    settlement = next(
        s for s in state.settlements.values() if s.get("node_id") == node_id and not s.get("staging")
    )
    settlement_id = str(settlement["id"])

    if "woodland" not in terrain_hexes or "ore_mountains" not in terrain_hexes:
        raise RuntimeError(
            f"selected node {node_id} lacks woodland/ore for shortage routes: {sorted(terrain_hexes)}"
        )
    # Route B needs clay when present; otherwise adapt to any non-ore productive terrain.
    alt_terrain = "clay_mountains" if "clay_mountains" in terrain_hexes else next(
        t for t in terrain_hexes if t not in {"ore_mountains", "desert", "woodland"}
    )

    wood_hex = terrain_hexes["woodland"][0]
    ore_hex = terrain_hexes["ore_mountains"][0]
    alt_hex = terrain_hexes[alt_terrain][0]

    primaries = _buildings_on_node(state, node_id, "primary")
    processors_existing = _buildings_on_node(state, node_id, "processor")
    factories = _buildings_on_node(state, node_id, "factory")
    if len(primaries) < 3 or not processors_existing or len(factories) < 2:
        raise RuntimeError("setup did not create expected settlement industry slots")

    # Bind three primaries to the three touching hexes (authoritative hex_id).
    primary_by_terrain = {
        "woodland": primaries[0],
        "ore_mountains": primaries[1],
        alt_terrain: primaries[2],
    }
    hex_by_primary = {
        primaries[0]["id"]: wood_hex,
        primaries[1]["id"]: ore_hex,
        primaries[2]["id"]: alt_hex,
    }
    for terrain, building in primary_by_terrain.items():
        building["hex_id"] = hex_by_primary[building["id"]]
        building["terrain"] = terrain
        building["resource_name"] = TERRAIN_RESOURCE.get(terrain, ("", False, "Resource"))[2]
        building["label"] = _human_building_label("primary", terrain)
        building["slot_kind"] = "primary"

    buildings = BuildingService(state)
    # Extra processors: working chain + Route A + Route B (setup only made one).
    proc_work = processors_existing[0]
    proc_a = buildings.create(
        "building.processor",
        node_id=node_id,
        faction_id=faction_id,
        settlement_id=settlement_id,
        slot_index=1,
    )
    proc_b = buildings.create(
        "building.processor",
        node_id=node_id,
        faction_id=faction_id,
        settlement_id=settlement_id,
        slot_index=2,
    )
    factory_work = factories[0]
    factory_shortage = factories[1]
    alt_label = {
        "clay_mountains": "Clay works",
        "fields": "Grain works",
        "grazing_land": "Wool works",
        "woodland": "Timber works",
        "ore_mountains": "Ore works",
    }.get(alt_terrain, "Village works")
    for row, label in (
        (proc_work, alt_label),
        (proc_a, "Ridge works"),
        (proc_b, "Sluice works"),
        (factory_work, "Muster factory"),
        (factory_shortage, "Village factory"),
    ):
        state.buildings[str(row["id"])]["label"] = label
        row["label"] = label
    # Keep live references into authoritative building records.
    proc_a = state.buildings[str(proc_a["id"])]
    proc_b = state.buildings[str(proc_b["id"])]
    # Label remaining settlement buildings from setup (not on the quest routes).
    for b in _buildings_on_node(state, node_id, "factory"):
        if not b.get("label"):
            b["label"] = "Idle factory"
    for b in _buildings_on_node(state, node_id, "centre"):
        b["label"] = b.get("label") or _human_building_label("centre")
    for b in _buildings_on_node(state, node_id, "warehouse"):
        b["label"] = b.get("label") or _human_building_label("warehouse")

    # Industry layers/channels on real hexes.
    layers = ResourceLayerService(state.industry)
    channel_ids: dict[str, str] = {}
    for terrain, building in primary_by_terrain.items():
        resource_id, finite, _label = TERRAIN_RESOURCE[terrain]
        layer = layers.create_layer(
            str(building["hex_id"]),
            resource_id,
            "prehistoric",
            0,
            finite=finite,
        )
        ch_id = f"channel:{building['id']}:{'finite' if finite else 'renewable'}"
        channel = PrimaryChannel(
            ch_id,
            str(building["id"]),
            node_id,
            terrain,
            "prehistoric",
            0,
            resource_id,
            layer.layer_id,
            finite,
            Fraction(1, 10),
            True,
        )
        sim.industry.install_channel(channel)
        channel_ids[terrain] = ch_id

    wood_ch = channel_ids["woodland"]
    ore_ch = channel_ids["ore_mountains"]
    alt_ch = channel_ids[alt_terrain]

    # Working economy: woodland + alternate (clay) — unaffected by demon on ore.
    sim.industry.install_processor(
        ProcessorBinding(
            str(proc_work["id"]),
            "recipe.prehistoric.pre_07",
            "prehistoric",
            wood_ch,
            alt_ch,
            active=True,
        )
    )
    # Route A (shortage selected): woodland + ore — blocked by demon on ore hex.
    sim.industry.install_processor(
        ProcessorBinding(
            str(proc_a["id"]),
            "recipe.prehistoric.pre_07",
            "prehistoric",
            wood_ch,
            ore_ch,
            active=True,
        )
    )
    # Route B alternate: woodland + alt — inactive under sluice sabotage.
    sim.industry.install_processor(
        ProcessorBinding(
            str(proc_b["id"]),
            "recipe.prehistoric.pre_07",
            "prehistoric",
            wood_ch,
            alt_ch,
            active=False,
            strike=False,
            modifier=Fraction(0),
        )
    )
    proc_b["active"] = False

    sim.industry.install_route(
        FactoryRoute(str(factory_work["id"]), str(proc_work["id"]), "unit.ancient.skirmisher", 2)
    )
    sim.industry.install_route(
        FactoryRoute(str(factory_shortage["id"]), str(proc_a["id"]), "unit.ancient.skirmisher", 2)
    )
    for factory in (factory_work, factory_shortage):
        sim.industry.factories.create(
            str(factory["id"]),
            node_id=node_id,
            faction_id=faction_id,
            era="prehistoric",
            unit_def_id="unit.ancient.skirmisher",
        )

    # Presentation layout sites from real building IDs + local grid anchors.
    state.board["fx_industry"] = {
        "node_id": node_id,
        "processor_id": str(proc_a["id"]),
        "processor_ids": [str(proc_work["id"]), str(proc_a["id"]), str(proc_b["id"])],
        "factory_ids": [str(factory_work["id"]), str(factory_shortage["id"])],
        "output_id": "processed.prehistoric.pre_07",
        "output_name": "Processed goods",
        "selected_route": "route:A",
        "layout": {
            "sites": [
                {
                    "id": str(primary_by_terrain["woodland"]["id"]),
                    "kind": "source",
                    "label": primary_by_terrain["woodland"]["label"],
                    "grid": [16, 18],
                    "entrance": [16, 19],
                    "color": "#2f7d32",
                    "terrain": "woodland",
                },
                {
                    "id": str(primary_by_terrain["ore_mountains"]["id"]),
                    "kind": "source",
                    "label": primary_by_terrain["ore_mountains"]["label"],
                    "grid": [14, 6],
                    "entrance": [14, 7],
                    "color": "#8a8f98",
                    "terrain": "ore_mountains",
                },
                {
                    "id": str(primary_by_terrain[alt_terrain]["id"]),
                    "kind": "source",
                    "label": primary_by_terrain[alt_terrain]["label"],
                    "grid": [10, 24],
                    "entrance": [10, 25],
                    "color": "#b87333",
                    "terrain": alt_terrain,
                },
                {
                    "id": str(proc_work["id"]),
                    "kind": "processor",
                    "label": proc_work["label"],
                    "grid": [20, 22],
                    "entrance": [20, 23],
                    "color": "#4a7a5a",
                },
                {
                    "id": str(proc_a["id"]),
                    "kind": "processor",
                    "label": proc_a["label"],
                    "grid": [22, 14],
                    "entrance": [22, 15],
                    "color": "#5a6a8a",
                },
                {
                    "id": str(proc_b["id"]),
                    "kind": "processor",
                    "label": proc_b["label"],
                    "grid": [18, 26],
                    "entrance": [18, 27],
                    "color": "#6a5a4a",
                },
                {
                    "id": str(factory_work["id"]),
                    "kind": "factory",
                    "label": factory_work["label"],
                    "grid": [26, 22],
                    "entrance": [26, 23],
                    "color": "#3a5a4a",
                },
                {
                    "id": str(factory_shortage["id"]),
                    "kind": "factory",
                    "label": factory_shortage["label"],
                    "grid": [28, 26],
                    "entrance": [28, 27],
                    "color": "#4a4a5a",
                },
            ],
            "assembly": {"grid": [24, 30], "label": "Yard"},
        },
    }

    JobService(state).register_job(
        f"job:attendant:{factory_shortage['id']}",
        workplace_id=str(factory_shortage["id"]),
        job_id="job:attendant",
        node_id=node_id,
        person_id=None,
    )
    JobService(state).register_job(
        f"job:attendant:{factory_work['id']}",
        workplace_id=str(factory_work["id"]),
        job_id="job:attendant",
        node_id=node_id,
        person_id=None,
    )
    IndustryProjection(state).sync_carrier_jobs()

    # Keep distant world catastrophe pressure, but the G05 settlement's touching
    # hexes must only carry the intentional ore-route demon (not random setup cubes).
    touching = {str(h) for h in plan.board.touching_hexes(node_id)}
    cubes = ((state.hazards or {}).get("catastrophe") or {}).get("cubes") or {}
    board_cubes = state.board.setdefault("hazard_cubes", {})
    for cid, cube in list(cubes.items()):
        if str(cube.get("hex_id")) in touching:
            cube["active"] = False
            if cid in board_cubes:
                board_cubes[cid]["active"] = False
    # Plan hazard_hexes also suppress industry; clear them on this settlement.
    state.board["hazard_hexes"] = [
        str(h) for h in (state.board.get("hazard_hexes") or []) if str(h) not in touching
    ]
    demon_id = "cube:demon"
    cubes[demon_id] = {
        "id": demon_id,
        "hex_id": ore_hex,
        "type": "demon",
        "active": True,
        "node_id": node_id,
        "cause_id": "cause:demon_ore",
    }
    board_cubes[demon_id] = {
        "hex_id": ore_hex,
        "active": True,
        "type": "demon",
        "node_id": node_id,
    }
    state.board.setdefault("hex_anchors", {})[ore_hex] = {"grid": [14.0, 4.0]}
    state.board.setdefault("node_adjacent_hexes", {})[node_id] = list(
        plan.board.touching_hexes(node_id)
    )

    # Quest / route metadata mirrors (IndustryService remains production authority).
    state.definitions["installed_routes"] = {
        "route:A": {
            "id": "route:A",
            "factory_id": str(factory_shortage["id"]),
            "processor_id": str(proc_a["id"]),
            "inputs": ["woodland", "ore_mountains"],
            "selected": True,
            "available": False,
            "blocked_by": "demon_cube",
        },
        "route:B": {
            "id": "route:B",
            "factory_id": str(factory_shortage["id"]),
            "processor_id": str(proc_b["id"]),
            "inputs": ["woodland", alt_terrain],
            "selected": False,
            "available": False,
            "modifier": "sluice_sabotage",
        },
        "route:work": {
            "id": "route:work",
            "factory_id": str(factory_work["id"]),
            "processor_id": str(proc_work["id"]),
            "inputs": ["woodland", alt_terrain],
            "selected": True,
            "available": True,
        },
    }
    state.definitions["production_modifiers"] = {
        "sluice_sabotage": {
            "modifier_id": "sluice_sabotage",
            "target_id": "route:B",
            "processor_id": str(proc_b["id"]),
            "kind": "sluice_sabotage",
            "active": True,
        }
    }

    # Persistent Mara at the shortage factory.
    people = PeopleService(state)
    mara = people.create_person(
        name=str(meta_file.get("worker_display_name") or "Mara"),
        role="worker",
        node_id=node_id,
        workplace_id=str(factory_shortage["id"]),
        job_id="job.factory_worker",
        dialogue_profile="dialogue.factory_worker",
        goal_ids=["goal.keep_production"],
        anchor=True,
    )
    mara["sprite"] = "worker"
    mara["visual_profile"] = "worker"
    people.assign_job(mara["id"], "job.factory_worker", str(factory_shortage["id"]))
    people.promote_profile(mara["id"], anchor=True, role="worker")
    # Stamp sprites on industry people after carrier sync.
    IndustryProjection(state).sync_carrier_jobs()
    for person in state.people.values():
        if person.get("node_id") != node_id:
            continue
        workplace = str(person.get("workplace_id") or "")
        terrain = None
        for t, b in primary_by_terrain.items():
            if workplace == b["id"] or workplace.startswith("channel:"):
                terrain = t
        person["sprite"] = person_sprite_for(person, terrain=terrain)
        person.setdefault("visual_profile", person["sprite"])

    state.player = {
        "node_id": node_id,
        "area_id": "area.village",
        "position": [28.0, 32.0],
        "facing": "up",
    }
    # Visit after player record exists so Challenge eligibility is retained.
    VisitService(state).arrive(node_id, "travel", int(state.clock.get("turn") or 0))
    state.board.setdefault("nodes", {})[node_id] = {
        "id": node_id,
        "label": "Settlement",
        "area_id": "area.village",
        "token": int(plan.hex_token.get(wood_hex) or meta_file.get("token") or 6),
        "terrains": sorted(terrain_hexes.keys()),
        "exits": {},
        "settlement_id": settlement_id,
        "faction_id": faction_id,
    }
    state.board["era_id"] = "ancient"
    state.board["fx_village"] = {
        **meta_file,
        "seed": seed,
        "node_id": node_id,
        "settlement_id": settlement_id,
        "faction_id": faction_id,
        "factory_id": str(factory_shortage["id"]),
        "factory_work_id": str(factory_work["id"]),
        "processor_work_id": str(proc_work["id"]),
        "processor_route_a_id": str(proc_a["id"]),
        "processor_route_b_id": str(proc_b["id"]),
        "primary_wood_id": str(primary_by_terrain["woodland"]["id"]),
        "primary_ore_id": str(primary_by_terrain["ore_mountains"]["id"]),
        "primary_alt_id": str(primary_by_terrain[alt_terrain]["id"]),
        "alt_terrain": alt_terrain,
        "demon_hex": ore_hex,
        "demon_cube_id": demon_id,
        "wood_hex": wood_hex,
        "alt_hex": alt_hex,
        "terrains": sorted(terrain_hexes.keys()),
        "board_seed": seed,
        "topology_hexes": len(plan.board.hexes),
        "topology_nodes": len(plan.board.nodes),
        "topology_edges": len(plan.board.edges),
    }

    # Industry tick with demon present.
    sim.industry.advance_quanta(1)
    rates: dict[str, Any] = {}
    for event in reversed(state.industry.get("events") or []):
        if event.get("kind") == "industry_rates":
            rates = event.get("rates") or {}
            break
    shortage_rate = float(fraction(rates.get(str(factory_shortage["id"])) or 0))
    work_rate = float(fraction(rates.get(str(factory_work["id"])) or 0))
    factory_shortage["shortage"] = shortage_rate <= 0
    factory_shortage["output_rate"] = shortage_rate
    factory_shortage["label"] = _human_building_label("factory", shortage=shortage_rate <= 0)
    factory_work["shortage"] = work_rate <= 0
    factory_work["output_rate"] = work_rate
    factory_work["label"] = _human_building_label("factory", shortage=work_rate <= 0).replace(
        "Village factory", "Muster factory"
    )

    tracker = CauseTracker(state)
    binder = QuestBinder(state, tracker)
    binder.register_template(template)
    observed = tracker.observe_changes(
        [
            {
                "kind": "factory_output_shortage",
                "affected_entity_id": str(factory_shortage["id"]),
                "stakeholder_id": mara["id"],
                "site_id": node_id,
                "template_id": template["id"],
                "output_rate": shortage_rate,
            }
        ]
    )
    cause = observed[0]["cause"]
    bound = binder.bind(template["id"], cause)
    state.board["fx_village"]["mara_id"] = mara["id"]
    state.board["fx_village"]["cause_id"] = cause["id"]
    state.board["fx_village"]["quest_id"] = bound["quest"]["id"]

    _seed_fx_village_sluice(state, node_id)
    return sim


def _seed_fx_village_sluice(state, node_id: str) -> None:
    from sim.dmb.adventure.puzzles import PuzzleService
    from sim.dmb.player.inventory import InventoryService

    root = ROOT / "godot_project" / "content" / "source" / "dungeons" / "sluice"
    puzzle_path = root / "puzzle.json"
    layout_path = root / "layout.json"
    if puzzle_path.is_file():
        PuzzleService(state).register_definition(json.loads(puzzle_path.read_text(encoding="utf-8")))
    if layout_path.is_file():
        state.board["dungeon_layouts"] = state.board.get("dungeon_layouts") or {}
        state.board["dungeon_layouts"]["dungeon.sluice"] = json.loads(layout_path.read_text(encoding="utf-8"))
    inv = InventoryService(state)
    existing = [
        iid
        for iid, item in (state.items or {}).items()
        if item.get("definition_id") == "item.sluice_handle" and item.get("alive", True)
    ]
    if not existing:
        inv.spawn_ground(
            definition_id="item.sluice_handle",
            area_id="area.sluice",
            position=[2.0, 1.0],
            quest_bound=True,
            label="Sluice handle",
            item_id="item:sluice_handle",
        )
    state.board.setdefault("entrances", {})["entrance:sluice"] = {
        "id": "entrance:sluice",
        "node_id": node_id,
        "grid": [16, 28],
        "label": "Sluice works",
        "dungeon_id": "dungeon.sluice",
        "active": True,
    }
