"""Widelands forestry data, transcribed from the pinned source.

Tree lifecycle: data/world/immovables/trees/beech/{sapling,pole,mature,old}/init.lua
(each stage: animate duration, remove chance, grow; old: transform deadtree chance, seed).
Felled tree: data/world/immovables/trees/fallentree/init.lua (30 s then remove).
Worker programs: data/tribes/workers/barbarians/{lumberjack,ranger}/init.lua.
Building programs: data/tribes/buildings/productionsites/barbarians/{lumberjacks_hut,rangers_hut}/init.lua.
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
BUILDING_PROGRAMS: dict[str, list[tuple[str, dict]]] = {
    "producer": [("callworker", {"program": "harvest"}), ("sleep", {"ms": 20_000})],
    "ranger": [("callworker", {"program": "plant"}), ("sleep", {"ms": 11_500})],
}
WORKER_FOR_BUILDING = {"producer": "lumberjack", "ranger": "ranger"}
FAIL_SLEEP_MS = 10_000
# One tile per step. Widelands uses 1.8 s per node; a node is smaller than a 64 px tile here.
WALK_MS = 600
