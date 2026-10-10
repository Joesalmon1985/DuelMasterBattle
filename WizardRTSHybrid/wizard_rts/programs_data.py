"""Widelands production data, transcribed from the pinned source.

Tree lifecycle: data/world/immovables/trees/beech/{sapling,pole,mature,old}/init.lua
(each stage: animate duration, remove chance, grow; old: transform deadtree chance, seed).
Felled tree: data/world/immovables/trees/fallentree/init.lua (30 s then remove).
Worker programs: data/tribes/workers/barbarians/{lumberjack,ranger}/init.lua.
Building programs: data/tribes/buildings/productionsites/{barbarians,empire}/<building>/init.lua.
GPL-2.0-or-later, Widelands Development Team.
"""

from __future__ import annotations

# stage -> (duration_ms, die_chance_percent, next_stage)
TREE_STAGES: dict[str, tuple[int, float, str]] = {
    "sapling": (55_000, 13.67, "pole"),
    "pole": (65_000, 9.37, "mature"),
    "mature": (72_000, 7.42, "old"),
    "old": (25 * 60_000 + 25_000, 7.81, "old"),
}
OLD_SEED_RADIUS = 3
FELLED_MS = 30_000

# Worker programs. Each step is (command, args).
WORKER_PROGRAMS: dict[str, dict[str, list[tuple[str, dict]]]] = {
    "lumberjack": {
        "harvest": [
            ("findobject", {"attrib": "tree", "radius": 10}),
            ("walk", {"to": "object"}),
            ("animate", {"name": "hack", "ms": 15_000}),
            ("callobject", {"program": "fall"}),
            ("animate", {"name": "idle", "ms": 2_000}),
            ("createware", {"ware": "log"}),
            ("return", {}),
        ],
    },
    "stonemason": {
        "cut_granite": [
            ("findobject", {"attrib": "rocks", "radius": 6}),
            ("walk", {"to": "object"}),
            ("animate", {"name": "hack", "ms": 17_500}),
            ("callobject", {"program": "shrink"}),
            ("createware", {"ware": "granite"}),
            ("return", {}),
        ],
    },
    "ranger": {
        "plant": [
            ("findspace", {"radius": 5, "avoid": "field", "saplingsearches": 5}),
            ("walk", {"to": "coords"}),
            ("animate", {"name": "dig", "ms": 3_500}),
            ("animate", {"name": "plant", "ms": 2_500}),
            ("plant", {"attrib": "tree_sapling"}),
            ("animate", {"name": "water", "ms": 3_500}),
            ("return", {}),
        ],
    },
}

# Building programs: ordered actions.
#   needs      skip the program unless the faction's economy needs the ware ("return=skipped unless economy needs")
#   consume    take wares from the building's input stock, or fail and retry later
#   sleep / animate   wait; animate also marks the building as working
#   mine       extract from the resource field around the building (resource, radius, yield %, when_empty %)
#   produce    add wares to the building's output stock
#   callworker run a worker program and wait for the worker to be back home
BUILDING_PROGRAMS: dict[str, list[tuple[str, dict]]] = {
    "producer": [("callworker", {"program": "harvest"}), ("sleep", {"ms": 20_000})],
    "ranger": [("callworker", {"program": "plant"}), ("sleep", {"ms": 11_500})],
    "quarry": [("callworker", {"program": "cut_granite"}), ("sleep", {"ms": 17_500})],
    # empire/sawmill
    "processor": [
        ("needs", {"good": "plank"}),
        ("consume", {"log": 2}),
        ("sleep", {"ms": 16_400}),
        ("animate", {"ms": 20_000}),
        ("produce", {"plank": 1}),
    ],
    # barbarians/coalmine and ironmine. "consume=ration" is left out until the food chain exists.
    "mine": [
        ("needs", {"good": "coal"}),
        ("sleep", {"ms": 34_800}),
        ("animate", {"ms": 10_000}),
        ("mine", {"resource": "coal", "radius": 2, "yield": 33.33, "when_empty": 5.0}),
        ("produce", {"coal": 1}),
        ("animate", {"ms": 10_000}),
        ("mine", {"resource": "coal", "radius": 2, "yield": 33.33, "when_empty": 5.0}),
        ("produce", {"coal": 1}),
    ],
    "ironmine": [
        ("needs", {"good": "iron_ore"}),
        ("sleep", {"ms": 34_800}),
        ("animate", {"ms": 10_000}),
        ("mine", {"resource": "iron", "radius": 2, "yield": 33.33, "when_empty": 5.0}),
        ("produce", {"iron_ore": 1}),
        ("animate", {"ms": 10_000}),
        ("mine", {"resource": "iron", "radius": 2, "yield": 33.33, "when_empty": 5.0}),
        ("produce", {"iron_ore": 1}),
    ],
    # barbarians/smelting_works (iron program)
    "smelter": [
        ("needs", {"good": "iron"}),
        ("consume", {"coal": 1, "iron_ore": 1}),
        ("sleep", {"ms": 29_400}),
        ("animate", {"ms": 35_000}),
        ("produce", {"iron": 1}),
    ],
    # barbarians/ax_workshop (produce_ax)
    "smithy": [
        ("needs", {"good": "ax"}),
        ("consume", {"coal": 1, "iron": 1}),
        ("sleep", {"ms": 23_400}),
        ("animate", {"ms": 22_000}),
        ("sleep", {"ms": 9_000}),
        ("produce", {"ax": 1}),
    ],
}
WORKER_FOR_BUILDING = {"producer": "lumberjack", "ranger": "ranger", "quarry": "stonemason"}
# Input stock caps (inputs = {...} in the building definitions) and wares pushed to a warehouse.
BUILDING_INPUTS: dict[str, dict[str, int]] = {
    "processor": {"log": 8},
    "smelter": {"coal": 8, "iron_ore": 8},
    "smithy": {"coal": 8, "iron": 8},
}
BUILDING_OUTPUTS: dict[str, list[str]] = {
    "producer": ["log"],
    "quarry": ["granite"],
    "processor": ["plank"],
    "mine": ["coal"],
    "ironmine": ["iron_ore"],
    "smelter": ["iron"],
    "smithy": ["ax"],
}
# "economy needs": a ware is wanted while the faction's warehouses hold fewer than this.
ECONOMY_TARGETS = {"plank": 20, "coal": 24, "iron_ore": 12, "iron": 10, "ax": 8, "granite": 16}
# Resource fields: per-node amounts placed around a mine's tile (radius 2 = 25 nodes).
RESOURCE_PER_NODE = {"coal": 6, "iron": 6}
ROCK_AMOUNT = 6
FAIL_SLEEP_MS = 10_000
# One tile per step. Widelands uses 1.8 s per node; a node is smaller than a 64 px tile here.
WALK_MS = 600
