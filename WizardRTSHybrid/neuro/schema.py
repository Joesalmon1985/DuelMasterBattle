"""The definitive observation schema (execution plan T2.1/T2.2): every vector's fields, widths and how network outputs are composed into inputs.

This module is the single source of truth that `features.py` fills and that M3 (`nets.py`) consumes. Nothing here touches the simulation.

HOW AN INPUT IS BUILT. The design (section 4.3) lists, for each network, a declared input width. Part of every input is a *raw feature* (computed
here from the world) and part is the *output of another network* (an N1 building vector pooled into a settlement input, for example), and the
kind embeddings are learned. So per network the schema gives an ordered list of parts, `(part name, width, source)`:

    source "raw"  - filled by features.py, shape [n, width]
    source "emb"  - a learned kind embedding (EMB_DIM wide) looked up by the kind index features.py supplies
    source "net:X" - the output (or a pooling of the output) of network X, supplied by the controller in M3
    source "ctx"/"prio" - the faction coordinator's context (32) or domain priorities (8)

`compose(name, **parts)` concatenates the parts in the declared order and checks the total against the declared width, so the order is defined in
one place. DIMS holds the declared width of every network input; they are the in-widths of nets.LAYOUT (M3).

DISCREPANCIES RESOLVED against the plan (each field list in the design was shorter or longer than its declared width; the declared widths are kept,
because the execution plan's LAYOUT fixes them, and the field lists below are the definitive ones; fields marked "added" are not in the design's
list and were added to reach the declared width):
  * KIND_STATIC: the listed columns sum to 29 (game 4, type 2, era 4, size 3, three flags, produces 6, consumes 6, cost 1) against the declared 24
    that H1 (108) and H9 (100) are built on. Resolved by compressing: type 2 -> is_unit 1, era one-hot 4 -> era/3, size one-hot 3 -> ordinal 1, and
    adding is_factory (1): 4 + 1 + 1 + 1 + 4 + 12 + 1 = 24.
  * N1 raw 19 listed (24 needed), N3 raw 16 listed (20), N2 raw 47 listed (51), N5 10 listed (12), N6 raw 13 listed (16), N7 raw 37 listed (44),
    N8 raw 15 listed (18), N12 raw 14 listed (28), N13 slot 14 listed (16), N14 globals 7 listed (8), H2 5 (6), H4 8 (4: the other four are in N7), H5 raw
    4 (8), H7 raw 17 (20), H8 raw 9 (10), H9 (4 action types: dismantle and convert share one, enhance and upgrade share one).
  * N14: the plan's T2.2 says "13 globals"; the design's 56 = pooled 16 + three worst regions 24 + N13 8 + 8 raw globals. The schema follows the 56.
  * Kind embedding rows: 586, not 594 (see features.py): 1 unknown + 582 roster entities + 3 in-play kinds outside the roster.
  * The domain priorities (8) enter H1 and H0 as inputs; for the other heads M3 applies them as an additive bias per head (the design's head widths
    exclude them). This is an M3 decision recorded here.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np

OBS_SCHEMA_VERSION = "obs-1.0.0"
EMB_DIM = 8
CTX_DIM = 32
PRIO_DIM = 8
MEM_DIM = 16

KEY_WARES = ("log", "plank", "granite", "coal", "iron_ore", "iron", "gold", "ration", "bread", "meat", "fish", "wheat", "water", "ax", "brick",
             "marble", "blackwood", "grout", "reed", "cloth", "smoked_fish", "smoked_meat", "beer", "paper")
GROUP_NAMES = ("food", "wood", "stone", "metal", "cloth_tools", "industrial")
N_GROUPS = len(GROUP_NAMES)

KIND_STATIC_COLUMNS = (
    "game_widelands", "game_openra", "game_mindustry", "game_hybrid", "is_unit", "era", "size", "is_military", "is_clinic", "is_centre", "is_factory",
    *(f"produces_{g}" for g in GROUP_NAMES), *(f"consumes_{g}" for g in GROUP_NAMES), "cost_log1p",
)
N_STATIC = len(KIND_STATIC_COLUMNS)
assert N_STATIC == 24

UNIT_STATIC_COLUMNS = ("strength", *(f"cost_{g}" for g in GROUP_NAMES), "loco_foot", "loco_ground_vehicle", "loco_air", "loco_naval", "is_founder")  # H3: 12
assert len(UNIT_STATIC_COLUMNS) == 12

IDLE_REASONS = ("no_input", "no_worker", "no_resource", "full", "outbreak", "none")
N_TOP_CANDIDATES = 4  # expansion sites in N7
N_DIPLO_SLOTS = 8

# --------------------------------------------------------------------------------------------------------------------------- raw field names
N1_RAW = ("hp", "operational", "working", "constructing", "disrupted", "waiting_worker", "queue_len", "input_satisfaction",
          *(f"idle_{r}" for r in IDLE_REASONS), "outbreak_factor", "dist_centre", "has_road", "is_clinic", "nest_nearby",
          "stall_minutes", "workers_fraction", "under_threat", "is_store", "construction_progress")  # last five added
N3_RAW = ("hp", "strength", "loco_foot", "loco_ground_vehicle", "loco_air", "loco_naval", "has_weapon", "range", "is_founder", "carrying_cargo",
          "dist_own_centre", "dist_enemy", "engaged", "idle", "moving", "region_cubes", "speed", "has_order", "weapon_ready", "max_hp")  # last four added
N2_RAW = (*(f"stock_{w}" for w in KEY_WARES), *(f"made_{g}" for g in GROUP_NAMES), *(f"consumed_{g}" for g in GROUP_NAMES),
          "unrest", "standing_vp", "is_home", "radius", "region_cubes", "nest_hp", "own_clinics", "enemy_strength", "own_strength", "dist_enemy_settlement",
          "founded_minutes", "operational_fraction", "constructing_count", "connected_fraction", "shortage_count")  # last four added
N4_RAW = (*(f"stock_{w}" for w in KEY_WARES), *(f"stock_group_{g}" for g in GROUP_NAMES), *(f"made_{g}" for g in GROUP_NAMES),
          *(f"consumed_{g}" for g in GROUP_NAMES), *(f"requests_{g}" for g in GROUP_NAMES), *(f"shortages_{g}" for g in GROUP_NAMES),
          *(f"producers_{g}" for g in GROUP_NAMES), *(f"chain_{k}_{g}" for g in GROUP_NAMES for k in ("unlocked", "consumers", "deficit")))
N5_RAW = ("roads", "unconnected", "carriers_busy", "carriers_waiting", "stuck", "belt_tiles", "machines_unpowered", "waterways", "ports", "caravans",
          "carriers", "requests_outstanding")  # last two added
N6_RAW = ("own_count", "own_strength", "enemy_count", "enemy_strength", "enemy_mean_distance", "known_buildings", "known_nearest_distance", "known_mean_hp",
          "kills_minus_losses_units", "kills_minus_losses_buildings", "defences", "factories", "production_queue",
          "own_idle_fraction", "own_engaged_fraction", "enemy_buildings_near")  # last three added
N7_RAW = ("settlements", "founders", "founder_cargo",
          *(f"cand{i}_{f}" for i in range(N_TOP_CANDIDATES) for f in ("distance", "fertility", "coal", "iron", "gold", "stone", "threat", "region_cubes")),
          "frontier_contact", "map_fraction", "territory_cells", "explored_fraction", "nearest_unexplored", "settlers_in_production", "can_afford_founder",
          "founded_recently", "settlements_lost")  # last seven added
N8_RAW = ("era_widelands", "era_openra", "era_historic", "era_modern", "era_progress", "minutes_to_stall", "own_vp", "max_other_vp", "rank",
          "draft_round", "minutes_left_in_round", "cards_buildings", "cards_units", "cards_military", "cards_industry",
          "offers", "cards_total", "drafts_lapsed")  # last three added
N12_RAW = ("minutes", "minutes_since_decision", *(f"event_{i}" for i in range(10)), "outbreaks", "era_outbreaks",
           "era_0", "era_1", "era_2", "era_3", "own_vp", "vp_gap", "settlements", "strength", *(f"stock_group_{g}" for g in GROUP_NAMES))  # last fourteen added
N13_SLOT = ("rel_war", "rel_truce", "rel_peace", "rel_alliance", "offer_from_them", "offer_to_them", "truce_minutes_left", "trades_done", "caravans_lost",
            "their_vp", "their_strength", "their_distance", "their_pressure", "collapsed", "known", "known_settlements")  # last two added
N14_REGION = ("cubes", "kind_0", "kind_1", "kind_2", "kind_3", "own_settlement", "own_clinic", "nest_hp", "visible", "dist_own")
N14_GLOBAL = ("outbreaks", "era_outbreaks", "minutes_to_cube", "cured_recently", "clinics", "rations", "water", "cubes_total")  # last added
N10_RAW = ("strongest_enemy", "own_strength", "vp_gap")
CARD_FLAGS = ("affordable_now", "adds_new", "era_open")  # appended to the 28 card features: 31
N_CARD = 28 + len(CARD_FLAGS)
HEAD_RAW = {
    "H0": ("minutes_since_command",),
    "H1": (*KIND_STATIC_COLUMNS, "site_distance", "site_trees", "site_arable", *(f"site_deposit_{k}" for k in ("none", "coal", "iron", "gold", "stone")),
           "site_deposit_amount", "site_water", "site_frontier", "site_region_cubes"),
    "H2": ("is_settlement_link", "is_belt", "is_waterway", "path_estimate", "a_is_store", "b_is_store"),
    "H3": UNIT_STATIC_COLUMNS,
    "H4": ("distance", "fertility", "threat", "region_cubes"),
    "H5": ("distance", "force_ratio", "is_nest", "is_allied_region", "t_enemy_building", "t_nest", "t_defend", "t_rally"),
    "H6": (),
    "H7": ("surplus", "deficit", "distance", "partner_pressure", *(f"give_{g}" for g in GROUP_NAMES), *(f"want_{g}" for g in GROUP_NAMES),
           "is_aid", "partner_vp_gap", "recent_hostility", "already_trading"),
    "H8": ("pressure", "relative_strength", "vp_gap", "a_propose_truce", "a_propose_peace", "a_propose_alliance", "a_accept", "a_decline", "a_break",
           "offer_time_left"),
    "H9": ("a_demolish", "a_dismantle_convert", "a_enhance_upgrade", "a_other"),
}

RAW_NAMES = {"N1": N1_RAW, "N3": N3_RAW, "N2": N2_RAW, "N4": N4_RAW, "N5": N5_RAW, "N6": N6_RAW, "N7": N7_RAW, "N8": N8_RAW, "N12": N12_RAW,
             "N13slot": N13_SLOT, "N14region": N14_REGION, "N14": N14_GLOBAL, "N10": N10_RAW}
RAW_DIMS = {k: len(v) for k, v in RAW_NAMES.items()}
RAW_DIMS["N8card"] = N_CARD
RAW_DIMS.update({f"{h}_raw": len(v) for h, v in HEAD_RAW.items()})

# --------------------------------------------------------------------------------------------------------------------------- input composition
E, R = "emb", "raw"
NET_INPUTS: dict[str, list[tuple[str, int, str]]] = {
    "N1": [("kind_emb", EMB_DIM, E), ("raw", RAW_DIMS["N1"], R)],
    "N3": [("kind_emb", EMB_DIM, E), ("raw", RAW_DIMS["N3"], R)],
    "N2": [("n1_mean", 16, "net:N1"), ("n1_max", 16, "net:N1"), ("n1_count", 1, "net:N1"), ("n1_damaged", 16, "net:N1"), ("raw", RAW_DIMS["N2"], R)],
    "N4": [("raw", RAW_DIMS["N4"], R), ("n2_mean", 24, "net:N2")],
    "N5": [("raw", RAW_DIMS["N5"], R)],
    "N6": [("n3_own_mean", 12, "net:N3"), ("n3_own_max", 12, "net:N3"), ("n3_nearest_enemy", 12, "net:N3"), ("n3_enemy_3", 36, "net:N3"),
           ("n2_threatened", 24, "net:N2"), ("raw", RAW_DIMS["N6"], R)],
    "N7": [("raw", RAW_DIMS["N7"], R), ("n2_max", 24, "net:N2")],
    "N8": [("raw", RAW_DIMS["N8"], R), ("card_sum", 16, "net:N8card"), ("card_max", 16, "net:N8card")],
    "N8card": [("raw", N_CARD, R)],
    "N9": [("n4", 16, "net:N4"), ("n5", 8, "net:N5"), ("n7", 12, "net:N7"), ("n8", 16, "net:N8"), ("n2_mean", 24, "net:N2"), ("n2_max", 24, "net:N2"),
           ("n2_weakest", 24, "net:N2")],
    "N10": [("n6", 16, "net:N6"), ("n7", 12, "net:N7"), ("n2_threatened", 24, "net:N2"), ("n13_summary", 8, "net:N13"), ("raw", RAW_DIMS["N10"], R)],
    "N12": [("n9", 16, "net:N9"), ("n10", 16, "net:N10"), ("n14", 12, "net:N14"), ("n13", 8, "net:N13"), ("n8", 16, "net:N8"), ("raw", RAW_DIMS["N12"], R),
            ("memory", MEM_DIM, "mem")],
    "N13slot": [("raw", RAW_DIMS["N13slot"], R)],
    "N13": [("slot_mean", 8, "net:N13slot"), ("slot_max", 8, "net:N13slot"), ("pressure", 1, R)],
    "N14region": [("raw", RAW_DIMS["N14region"], R)],
    "N14": [("region_mean", 8, "net:N14region"), ("region_max", 8, "net:N14region"), ("worst_3", 24, "net:N14region"), ("raw", RAW_DIMS["N14"], R),
            ("n13", 8, "net:N13")],
    "N11": [("squad_mean", 12, "net:N3"), ("squad_max", 12, "net:N3"), ("enemy_mean", 12, "net:N3"), ("enemy_count", 1, R), ("enemy_strength", 1, R),
            ("force_ratio", 1, R), ("dist_centre", 1, R), ("retreat_blocked", 1, R), ("n10", 16, "net:N10"), ("n6", 16, "net:N6"), ("pad", 1, R)],
    "H0": [("ctx", CTX_DIM, "ctx"), ("prio", PRIO_DIM, "prio"), ("raw", RAW_DIMS["H0_raw"], R)],
    "H1": [("kind_emb", EMB_DIM, E), ("raw", RAW_DIMS["H1_raw"], R), ("n2", 24, "net:N2"), ("ctx", CTX_DIM, "ctx"), ("prio", PRIO_DIM, "prio")],
    "H2": [("raw", RAW_DIMS["H2_raw"], R), ("n1_a", 16, "net:N1"), ("n1_b", 16, "net:N1"), ("ctx", CTX_DIM, "ctx")],
    "H3": [("kind_emb", EMB_DIM, E), ("raw", RAW_DIMS["H3_raw"], R), ("n1_factory", 16, "net:N1"), ("n6", 16, "net:N6"), ("ctx", CTX_DIM, "ctx")],
    "H4": [("raw", RAW_DIMS["H4_raw"], R), ("n3_founder", 12, "net:N3"), ("n7", 12, "net:N7"), ("ctx", CTX_DIM, "ctx")],
    "H5": [("squad_mean", 12, "net:N3"), ("squad_max", 12, "net:N3"), ("n1_target", 16, "net:N1"), ("raw", RAW_DIMS["H5_raw"], R), ("n10", 16, "net:N10"),
           ("ctx", CTX_DIM, "ctx")],
    "H6": [("card_hidden", 16, "net:N8card"), ("card_score", 1, "net:N8card"), ("ctx", CTX_DIM, "ctx")],
    "H7": [("raw", RAW_DIMS["H7_raw"], R), ("slot", 8, "net:N13slot"), ("ctx", CTX_DIM, "ctx")],
    "H8": [("raw", RAW_DIMS["H8_raw"], R), ("slot", 8, "net:N13slot"), ("ctx", CTX_DIM, "ctx")],
    "H9": [("raw", RAW_DIMS["H9_raw"], R), ("n1", 16, "net:N1"), ("n2", 24, "net:N2"), ("kind_static", N_STATIC, R), ("ctx", CTX_DIM, "ctx")],
}
# H9's per-candidate raw features are (action one-hot 4) + the 24 kind-static columns, passed separately; the declared width counts both.

DIMS = {name: sum(w for _p, w, _s in parts) for name, parts in NET_INPUTS.items()}
DECLARED = {  # the in-widths of nets.LAYOUT in the execution plan (T3.1): the schema must reproduce them exactly
    "N1": 32, "N3": 28, "N2": 100, "N4": 102, "N5": 12, "N6": 112, "N7": 68, "N8": 50, "N8card": 31, "N13slot": 16, "N13": 17, "N14region": 10, "N14": 56,
    "N9": 124, "N10": 63, "N12": 112, "N11": 74, "H0": 41, "H1": 108, "H2": 70, "H3": 84, "H4": 60, "H5": 96, "H6": 49, "H7": 60, "H8": 50, "H9": 100,
}
for _name, _w in DECLARED.items():
    assert DIMS[_name] == _w, f"schema input width of {_name} is {DIMS[_name]}, the plan declares {_w}"


def compose(name: str, **parts: np.ndarray) -> np.ndarray:
    """Concatenate the named parts of network `name`'s input in the declared order along the last axis; widths are checked against the schema.
    Every part listed in NET_INPUTS[name] must be supplied (a 1-D part is treated as one row)."""
    spec = NET_INPUTS[name]
    missing = [p for p, _w, _s in spec if p not in parts]
    extra = [p for p in parts if p not in {q for q, _w, _s in spec}]
    if missing or extra:
        raise KeyError(f"{name}: missing parts {missing}, unexpected parts {extra}")
    cols = []
    for part, width, _src in spec:
        a = np.asarray(parts[part], dtype=np.float32)
        if a.shape[-1] != width:
            raise ValueError(f"{name}.{part}: width {a.shape[-1]}, schema says {width}")
        cols.append(a)
    lead = np.broadcast_shapes(*[c.shape[:-1] for c in cols])
    return np.concatenate([np.broadcast_to(c, lead + (c.shape[-1],)) for c in cols], axis=-1)


def schema_description() -> dict:
    """Everything that defines the observation, for hashing and for the generated document."""
    return {"version": OBS_SCHEMA_VERSION, "emb_dim": EMB_DIM, "key_wares": list(KEY_WARES), "groups": list(GROUP_NAMES), "kind_static": list(KIND_STATIC_COLUMNS),
            "raw": {k: list(v) for k, v in RAW_NAMES.items()}, "heads_raw": {k: list(v) for k, v in HEAD_RAW.items()}, "card_flags": list(CARD_FLAGS),
            "inputs": {k: [list(p) for p in v] for k, v in NET_INPUTS.items()}, "dims": DIMS}


def schema_hash(roster_hash: str) -> str:
    """sha256 over the schema, the roster hash and the kind table's definition: a change to any of them is a new observation schema."""
    blob = json.dumps({"schema": schema_description(), "roster": roster_hash}, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()
