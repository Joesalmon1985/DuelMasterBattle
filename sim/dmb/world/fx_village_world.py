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
    # Proper names stay clean; status belongs in observation text, not the name.
    del shortage  # retained for call-site compatibility
    if slot_kind == "primary" and terrain:
        from sim.dmb.world.settlement_layout import PRIMARY_LABEL

        return PRIMARY_LABEL.get(terrain, f"{terrain.replace('_', ' ').title()} source")
    if slot_kind == "processor":
        return "Works"
    if slot_kind == "factory":
        return "Village Factory"
    if slot_kind == "centre":
        return "Settlement Centre"
    if slot_kind == "warehouse":
        return "Warehouse"
    return slot_kind.replace("_", " ").title()


def load_fx_village(seed: int = 507, *, mode: str = "baseline") -> WorldSim:
    """Build FX-VILLAGE on a real generated two-faction board settlement.

    mode:
      - baseline: healthy working village (Village Foundation / play_g05)
      - quest: shortage quest scenario (FX-VILLAGE-QUEST)
    """
    if mode not in {"baseline", "quest"}:
        raise ValueError(f"unknown fx village mode {mode!r}")
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
        "clay_mountains": "Clay Works",
        "fields": "Grain Works",
        "grazing_land": "Wool Works",
        "woodland": "Timber Works",
        "ore_mountains": "Ore Works",
    }.get(alt_terrain, "Village Works")
    for row, label in (
        (proc_work, alt_label),
        (proc_a, "Ridge Works"),
        (proc_b, "Alternate Works"),
        (factory_work, "Muster Yard"),
        (factory_shortage, "Village Factory"),
    ):
        state.buildings[str(row["id"])]["label"] = label
        row["label"] = label
    # Keep live references into authoritative building records.
    proc_a = state.buildings[str(proc_a["id"])]
    proc_b = state.buildings[str(proc_b["id"])]
    # Label remaining settlement buildings from setup (not on the quest routes).
    for b in _buildings_on_node(state, node_id, "factory"):
        if not b.get("label"):
            b["label"] = "Idle Factory"
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
    # Route B alternate: woodland + alt — inactive under sluice sabotage (quest only).
    if mode == "quest":
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
    else:
        # Baseline: leave alternate works unused / inactive without quest framing.
        proc_b["active"] = False
        proc_b["label"] = "Unused Works"
        state.buildings[str(proc_b["id"])]["label"] = "Unused Works"
        state.buildings[str(proc_b["id"])]["active"] = False

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

    # Spatial grammar: perimeter primaries from touching-hex orientation + built core.
    from sim.dmb.world.settlement_layout import (
        apply_anchors_to_local_projection,
        build_village_layout_sites,
        public_occupation_for,
    )

    node_buildings = {
        str(bid): b
        for bid, b in state.buildings.items()
        if b.get("node_id") == node_id
    }
    anchors, industry_sites = build_village_layout_sites(
        board=plan.board,
        node_id=node_id,
        buildings=node_buildings,
    )
    apply_anchors_to_local_projection(state, node_id, anchors, seed=f"{seed}:{node_id}:v2")
    state.board["fx_industry"] = {
        "node_id": node_id,
        "processor_id": str(proc_a["id"]),
        "processor_ids": [str(proc_work["id"]), str(proc_a["id"]), str(proc_b["id"])],
        "factory_ids": [str(factory_work["id"]), str(factory_shortage["id"])],
        "output_id": "processed.prehistoric.pre_07",
        "output_name": "Processed goods",
        "selected_route": "route:work" if mode == "baseline" else "route:A",
        "layout": {
            "sites": industry_sites,
            "assembly": {
                "grid": [
                    int(anchors.get(str(factory_work["id"]), {}).get("approach", [24, 30])[0]),
                    int(anchors.get(str(factory_work["id"]), {}).get("approach", [24, 30])[1]) + 2,
                ],
                "label": "Yard",
            },
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

    # Keep distant world catastrophe pressure; settlement touching hexes stay clear
    # unless the quest mode places its intentional ore-route demon.
    touching = {str(h) for h in plan.board.touching_hexes(node_id)}
    cubes = ((state.hazards or {}).get("catastrophe") or {}).get("cubes") or {}
    board_cubes = state.board.setdefault("hazard_cubes", {})
    for cid, cube in list(cubes.items()):
        if str(cube.get("hex_id")) in touching:
            cube["active"] = False
            if cid in board_cubes:
                board_cubes[cid]["active"] = False
    state.board["hazard_hexes"] = [
        str(h) for h in (state.board.get("hazard_hexes") or []) if str(h) not in touching
    ]
    demon_id = "cube:demon"
    if mode == "quest":
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
        ore_anchor = anchors.get(str(primary_by_terrain["ore_mountains"]["id"]), {})
        demon_grid = list(ore_anchor.get("grid") or [14, 4])
        state.board.setdefault("hex_anchors", {})[ore_hex] = {
            "grid": [float(demon_grid[0]) + 1.0, float(demon_grid[1]) - 1.0]
        }
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
            "selected": mode == "quest",
            "available": mode == "baseline",
            "blocked_by": "demon_cube" if mode == "quest" else None,
        },
        "route:B": {
            "id": "route:B",
            "factory_id": str(factory_shortage["id"]),
            "processor_id": str(proc_b["id"]),
            "inputs": ["woodland", alt_terrain],
            "selected": False,
            "available": False,
            "modifier": "sluice_sabotage" if mode == "quest" else None,
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
    if mode == "quest":
        state.definitions["production_modifiers"] = {
            "sluice_sabotage": {
                "modifier_id": "sluice_sabotage",
                "target_id": "route:B",
                "processor_id": str(proc_b["id"]),
                "kind": "sluice_sabotage",
                "active": True,
            }
        }
    else:
        state.definitions["production_modifiers"] = {}

    # Persistent Mara — ordinary factory worker in baseline; quest binds later.
    people = PeopleService(state)
    mara_workplace = str(factory_work["id"] if mode == "baseline" else factory_shortage["id"])
    mara = people.create_person(
        name=str(meta_file.get("worker_display_name") or "Mara"),
        role="worker",
        node_id=node_id,
        workplace_id=mara_workplace,
        job_id="job.factory_worker",
        dialogue_profile="dialogue.factory_worker",
        goal_ids=["goal.keep_production"],
        anchor=True,
    )
    mara["sprite"] = "worker"
    mara["visual_profile"] = "worker"
    mara["occupation"] = "Factory worker"
    people.assign_job(mara["id"], "job.factory_worker", mara_workplace)
    people.promote_profile(mara["id"], anchor=True, role="worker")
    # Stamp sprites + occupations on industry people after carrier sync.
    IndustryProjection(state).sync_carrier_jobs()
    for person in state.people.values():
        if person.get("node_id") != node_id:
            continue
        workplace = str(person.get("workplace_id") or "")
        workplace_rec = state.buildings.get(workplace) or {}
        terrain = str(workplace_rec.get("terrain") or "")
        if not terrain:
            for t, b in primary_by_terrain.items():
                if workplace == b["id"]:
                    terrain = t
                    break
        person["sprite"] = person_sprite_for(person, terrain=terrain or None)
        person.setdefault("visual_profile", person["sprite"])
        person["occupation"] = public_occupation_for(
            person, workplace=workplace_rec if workplace_rec else {"terrain": terrain}
        )

    # Player start near built core, south of centre.
    layout_rec = (state.board.get("local_projections") or {}).get(node_id) or {}
    centre = layout_rec.get("centre") or [24, 24]
    state.player = {
        "node_id": node_id,
        "area_id": "area.village",
        "position": [float(centre[0]), float(centre[1]) + 8.0],
        "facing": "up",
    }
    # Visit after player record exists so Challenge eligibility is retained.
    VisitService(state).arrive(node_id, "travel", int(state.clock.get("turn") or 0))
    # Wire real topology exits before stamping settlement metadata.
    wire_topology_travel(state, plan.board, home_node_id=node_id)
    home = state.board.setdefault("nodes", {}).setdefault(node_id, {"id": node_id})
    home.update(
        {
            "id": node_id,
            "label": "Settlement",
            "area_id": "area.village",
            "token": int(plan.hex_token.get(wood_hex) or meta_file.get("token") or 6),
            "terrains": sorted(terrain_hexes.keys()),
            "settlement_id": settlement_id,
            "faction_id": faction_id,
        }
    )
    # Preserve exits from wire_topology_travel (do not wipe).
    home.setdefault("exits", {})
    state.board["era_id"] = "ancient"
    state.board["fx_village"] = {
        **meta_file,
        "seed": seed,
        "mode": mode,
        "quest_enabled": mode == "quest",
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
        "demon_hex": ore_hex if mode == "quest" else None,
        "demon_cube_id": demon_id if mode == "quest" else None,
        "wood_hex": wood_hex,
        "alt_hex": alt_hex,
        "terrains": sorted(terrain_hexes.keys()),
        "board_seed": seed,
        "topology_hexes": len(plan.board.hexes),
        "topology_nodes": len(plan.board.nodes),
        "topology_edges": len(plan.board.edges),
        "mara_id": mara["id"],
    }

    # Industry tick (quest mode includes demon pressure; baseline is healthy).
    sim.industry.advance_quanta(1)
    rates: dict[str, Any] = {}
    for event in reversed(state.industry.get("events") or []):
        if event.get("kind") == "industry_rates":
            rates = event.get("rates") or {}
            break
    shortage_rate = float(fraction(rates.get(str(factory_shortage["id"])) or 0))
    work_rate = float(fraction(rates.get(str(factory_work["id"])) or 0))
    factory_shortage["shortage"] = mode == "quest" and shortage_rate <= 0
    factory_shortage["output_rate"] = shortage_rate
    factory_shortage["label"] = "Village Factory"
    factory_work["shortage"] = False
    factory_work["output_rate"] = work_rate
    factory_work["label"] = "Muster Yard"
    state.buildings[str(factory_shortage["id"])]["label"] = "Village Factory"
    state.buildings[str(factory_work["id"])]["label"] = "Muster Yard"
    state.buildings[str(factory_shortage["id"])]["shortage"] = factory_shortage["shortage"]
    state.buildings[str(factory_work["id"])]["shortage"] = False

    if mode == "quest":
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
        state.board["fx_village"]["cause_id"] = cause["id"]
        state.board["fx_village"]["quest_id"] = bound["quest"]["id"]
        state.board["fx_village"]["quest_template_id"] = template["id"]
        _seed_fx_village_sluice(state, node_id)
    else:
        state.board["fx_village"]["cause_id"] = None
        state.board["fx_village"]["quest_id"] = None
        state.board["fx_village"]["quest_template_id"] = None
        # Ensure no sluice entrance leaks into baseline play.
        entrances = state.board.setdefault("entrances", {})
        entrances.pop("entrance:sluice", None)

    # Refresh people anchors after Mara exists.
    apply_anchors_to_local_projection(state, node_id, anchors, seed=f"{seed}:{node_id}:v2")
    return sim


_DIR_GRIDS = {
    "north": lambda w, h: [w // 2, 1],
    "south": lambda w, h: [w // 2, h - 2],
    "east": lambda w, h: [w - 2, h // 2],
    "west": lambda w, h: [1, h // 2],
}
_OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east"}
_LEAVE_FACING = {"north": "up", "south": "down", "east": "right", "west": "left"}
_ARRIVE_FACING = {"north": "down", "south": "up", "east": "left", "west": "right"}


def _node_plane(board, node_id: str) -> tuple[float, float]:
    from sim.dmb.world.board import parse_hex_id

    hexes = board.touching_hexes(node_id)
    if not hexes:
        return (0.0, 0.0)
    qs: list[float] = []
    rs: list[float] = []
    for hid in hexes:
        q, r = parse_hex_id(str(hid))
        qs.append(float(q))
        rs.append(float(r))
    return (sum(qs) / len(qs), sum(rs) / len(rs))


def _cardinal_for(dx: float, dy: float) -> str:
    if abs(dx) >= abs(dy):
        return "east" if dx >= 0 else "west"
    return "south" if dy >= 0 else "north"


def wire_topology_travel(state, board, *, home_node_id: str, width: int = 48, height: int = 48) -> None:
    """Ensure every topology node exists with lawful Travel exits to adjacent nodes."""
    import math

    nodes = state.board.setdefault("nodes", {})
    settlement_by_node = {
        str(s.get("node_id")): s
        for s in state.settlements.values()
        if not s.get("staging") and s.get("node_id")
    }
    for nid in board.nodes:
        nid = str(nid)
        rec = nodes.setdefault(nid, {"id": nid})
        rec["id"] = nid
        if nid == home_node_id:
            rec.setdefault("label", "Settlement")
            rec.setdefault("area_id", "area.village")
        elif nid in settlement_by_node:
            rec.setdefault("label", "Settlement")
            rec.setdefault("area_id", f"area.{nid.replace(':', '_')}")
            rec["settlement_id"] = settlement_by_node[nid].get("id")
            rec["faction_id"] = settlement_by_node[nid].get("faction_id")
        else:
            rec.setdefault("label", "Wilderness")
            rec.setdefault("area_id", f"area.{nid.replace(':', '_')}")
        rec.setdefault("exits", {})

    # Assign unique cardinals per node among neighbours.
    for nid in board.nodes:
        nid = str(nid)
        ox, oy = _node_plane(board, nid)
        ranked: list[tuple[float, str, str]] = []
        for other in board.adjacent_nodes(nid):
            other = str(other)
            tx, ty = _node_plane(board, other)
            dx, dy = tx - ox, ty - oy
            ang = math.atan2(dy, dx)
            ranked.append((ang, other, _cardinal_for(dx, dy)))
        ranked.sort(key=lambda row: row[0])
        used: set[str] = set()
        assigned: dict[str, str] = {}
        for _ang, other, preferred in ranked:
            direction = preferred
            if direction in used:
                for cand in ("north", "east", "south", "west"):
                    if cand not in used:
                        direction = cand
                        break
            used.add(direction)
            assigned[other] = direction

        exits: dict[str, Any] = {}
        for other, direction in assigned.items():
            opp = _OPPOSITE[direction]
            hold = _DIR_GRIDS[direction](width, height)
            arrive = _DIR_GRIDS[opp](width, height)
            other_rec = nodes[other]
            exits[other] = {
                "exit_id": f"{nid}.{direction}",
                "direction": direction,
                "label": f"{direction.title()} path",
                "hold_position": [float(hold[0]), float(hold[1])],
                "hold_facing": _LEAVE_FACING[direction],
                "arrival": {
                    "node_id": other,
                    "area_id": str(other_rec.get("area_id") or f"area.{other.replace(':', '_')}"),
                    "position": [float(arrive[0]), float(arrive[1])],
                    "facing": _ARRIVE_FACING[direction],
                },
            }
        nodes[nid]["exits"] = exits

    state.board["nodes"] = nodes


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
