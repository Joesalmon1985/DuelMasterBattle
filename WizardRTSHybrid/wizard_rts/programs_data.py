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
# tribes/immovables/wheatfield/*/init.lua: tiny 30 s, small 45 s, medium 50 s, ripe 8 m 20 s then it rots; harvested 8 m 20 s then gone
FIELD_STAGES: dict[str, tuple[int, float, str]] = {
    "tiny": (30_000, 0.0, "small"),
    "small": (45_000, 0.0, "medium"),
    "medium": (50_000, 0.0, "ripe"),
    "ripe": (500_000, 100.0, "ripe"),
    "harvested": (500_000, 100.0, "harvested"),
}
STAGE_TABLES = {"beech": TREE_STAGES, "wheat": FIELD_STAGES}
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
    "farmer": {
        # tribes/workers/barbarians/farmer/init.lua
        "plant": [
            ("findspace", {"radius": 2, "avoid": "", "saplingsearches": 5}),
            ("walk", {"to": "coords"}),
            ("animate", {"name": "plant", "ms": 6_000}),
            ("plant", {"attrib": "seed_wheat"}),
            ("animate", {"name": "plant", "ms": 6_000}),
            ("return", {}),
        ],
        "harvest": [
            ("findobject", {"attrib": "ripe_wheat", "radius": 2}),
            ("walk", {"to": "object"}),
            ("animate", {"name": "harvest", "ms": 10_000}),
            ("callobject", {"program": "harvest"}),
            ("animate", {"name": "gather", "ms": 4_000}),
            ("createware", {"ware": "wheat"}),
            ("return", {}),
        ],
    },
    "hunter": {
        # tribes/workers/barbarians/hunter/init.lua
        "hunt": [
            ("findobject", {"attrib": "eatable", "radius": 13}),
            ("walk", {"to": "object"}),
            ("animate", {"name": "idle", "ms": 1_000}),
            ("removeobject", {}),
            ("createware", {"ware": "meat"}),
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
    # barbarians/farm: plant, then harvest
    "farm": [
        ("callworker", {"program": "plant"}),
        ("animate", {"ms": 7_000}),
        ("sleep", {"ms": 3_000}),
        ("callworker", {"program": "harvest"}),
        ("animate", {"ms": 3_000}),
        ("sleep", {"ms": 1_000}),
    ],
    # barbarians/hunters_hut
    "hunter": [("callworker", {"program": "hunt"}), ("sleep", {"ms": 35_000})],
    # barbarians/well (a "needs water" gate is added so the hybrid does not pump forever)
    "well": [
        ("needs", {"good": "water"}),
        ("sleep", {"ms": 20_000}),
        ("animate", {"ms": 20_000}),
        ("mine", {"resource": "water", "radius": 1, "yield": 100.0, "when_empty": 65.0}),
        ("produce", {"water": 1}),
    ],
    # barbarians/tavern: one ration from bread, fish or meat
    "tavern": [
        ("needs", {"good": "ration"}),
        ("consume_any", {"goods": ["bread", "fish", "meat"]}),
        ("animate", {"ms": 23_400}),
        ("sleep", {"ms": 10_000}),
        ("produce", {"ration": 1}),
    ],
    # barbarians/bakery
    "bakery": [
        ("needs", {"good": "bread"}),
        ("consume", {"water": 3, "wheat": 3}),
        ("sleep", {"ms": 20_800}),
        ("animate", {"ms": 20_000}),
        ("produce", {"bread": 1}),
        ("animate", {"ms": 20_000}),
        ("produce", {"bread": 1}),
    ],
    "processor": [
        ("needs", {"good": "plank"}),
        ("consume", {"log": 2}),
        ("sleep", {"ms": 16_400}),
        ("animate", {"ms": 20_000}),
        ("produce", {"plank": 1}),
    ],
    # barbarians/coalmine and ironmine
    "mine": [
        ("needs", {"good": "coal"}),
        ("consume", {"ration": 1}),
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
        ("consume", {"ration": 1}),
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
WORKER_FOR_BUILDING = {"producer": "lumberjack", "ranger": "ranger", "quarry": "stonemason", "farm": "farmer", "hunter": "hunter"}
# Input stock caps (inputs = {...} in the building definitions) and wares pushed to a warehouse.
BUILDING_INPUTS: dict[str, dict[str, int]] = {
    "processor": {"log": 8},
    "smelter": {"coal": 8, "iron_ore": 8},
    "smithy": {"coal": 8, "iron": 8},
    "mine": {"ration": 6},
    "ironmine": {"ration": 6},
    "tavern": {"fish": 4, "meat": 4, "bread": 4},
    "bakery": {"water": 6, "wheat": 6},
}
BUILDING_OUTPUTS: dict[str, list[str]] = {
    "producer": ["log"],
    "quarry": ["granite"],
    "processor": ["plank"],
    "mine": ["coal"],
    "ironmine": ["iron_ore"],
    "smelter": ["iron"],
    "smithy": ["ax"],
    "farm": ["wheat"],
    "hunter": ["meat"],
    "well": ["water"],
    "tavern": ["ration"],
    "bakery": ["bread"],
}
# "economy needs": a ware is wanted while the faction's warehouses hold fewer than this.
ECONOMY_TARGETS = {"plank": 20, "coal": 24, "iron_ore": 12, "iron": 10, "ax": 8, "granite": 16, "ration": 16, "bread": 8, "water": 12, "meat": 10, "wheat": 12}
# Resource fields: per-node amounts placed around a mine's tile (radius 2 = 25 nodes).
RESOURCE_PER_NODE = {"coal": 6, "iron": 6, "water": 8}
ROCK_AMOUNT = 6
FAIL_SLEEP_MS = 10_000
# One tile per step. Widelands uses 1.8 s per node; a node is smaller than a 64 px tile here.
WALK_MS = 600

# Wild animals (world/critters/*). reproduction_rate is a percent chance per breeding check.
ANIMAL_SPECIES = {"deer": {"reproduction": 40, "move_ms": 1500}, "bunny": {"reproduction": 50, "move_ms": 1200}}
ANIMAL_BREED_CHECK_MS = 120_000
ANIMAL_CAP_NEAR = 10  # animals within 14 cells of one another before breeding stops
START_WARES = {"log": 12, "plank": 6, "ration": 10}
