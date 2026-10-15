"""Observation features for the neural controller (execution plan T2.1 and T2.2).

Part 1 (this section): the static tables, computed once per process from the frozen roster: the kind index, the static kind features, the ware
groups, the card features and the schema hash. Part 2 (below): the per-decision assembly of every network's raw features from the world.

The definitive field lists and widths live in `neuro/schema.py`; this module fills them. Nothing here changes the simulation. Everything is
deterministic: ids are sorted before any decision, no wall clock, no hash-order iteration, float32 arrays, so Windows and Linux agree.

KIND INDEX. `KIND_INDEX` maps an entity id to a row: row 0 is "unknown", rows 1..582 are the frozen roster's entities in manifest order
(buildings and `unit:*` units), and three kinds that exist in play but are not roster entities follow: the settlement core `warehouse`, the factionless
`blight_nest` and the Widelands soldier `unit:soldier`. N_KINDS = 586 rows (not the 594 the plan assumed from the pre-v4 roster of 593).
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from neuro import schema
from neuro.schema import (GROUP_NAMES, KEY_WARES, KIND_STATIC_COLUMNS, N_GROUPS, N_STATIC, UNIT_STATIC_COLUMNS)
from wizard_rts import freeze

EXTRA_KINDS = ("warehouse", "blight_nest", "unit:soldier")  # in play, not roster entities (see the module docstring)

_TABLES: dict[str, Any] = {}


# ---------------------------------------------------------------------------------------------------------------------------- ware groups
_FOOD = {"ration", "bread", "bread_frisians", "fish", "meat", "smoked_fish", "smoked_meat", "beer", "beer_strong", "wine", "mead", "honey", "honey_bread", "meal",
         "snack", "fruit", "grape", "cassavaroot", "chocolate", "cocoa_beans", "corn", "cornmeal", "flour", "blackroot", "blackroot_flour", "barley", "wheat", "water"}
_WOOD = {"log", "plank", "blackwood", "ironwood", "balsa", "rubber", "liana", "rope", "bark"}
_STONE = {"granite", "marble", "marble_column", "brick", "grout", "clay", "quartz", "diamond"}
_METAL = {"iron", "iron_ore", "coal", "gold", "gold_ore", "gold_dust", "gold_thread", "scrap_iron", "scrap_metal_mixed", "coal_ore", "bronze", "steel"}
_METAL_PREFIX = ("armor", "helmet", "shield", "spear", "sword", "trident", "boots", "ax_")  # soldiers' equipment comes out of the forges
_CLOTH_TOOLS = {"cloth", "spidercloth", "spider_silk", "fur", "wool", "reed", "tunic", "tabard", "tabard_golden", "vest_padded", "protector_padded", "warriors_coat",
                "ax", "felling_ax", "pick", "saw", "hammer", "shovel", "scythe", "basket", "buckets", "chisel", "fire_tongs", "firestones", "fishing_net",
                "fishing_rod", "hook_pole", "hunting_bow", "hunting_spear", "kitchen_tools", "machete", "milking_tongs", "needles", "bread_paddle", "stone_bowl",
                "paper", "garment"}


def group_of(ware: str) -> int | None:
    """Index into GROUP_NAMES (food, wood, stone, metal, cloth_tools, industrial) or None for an unclassified ware. Mindustry items (`mdy.*`) are industrial."""
    if ware.startswith("mdy."):
        return 5
    if ware in _FOOD:
        return 0
    if ware in _WOOD:
        return 1
    if ware in _STONE:
        return 2
    if ware in _METAL or ware.startswith(_METAL_PREFIX):
        return 3
    if ware in _CLOTH_TOOLS or ware.startswith("fur_garment"):
        return 4
    return None


def groups_of(wares) -> np.ndarray:
    """6-vector of 0/1: which groups the given wares touch."""
    v = np.zeros(N_GROUPS, dtype=np.float32)
    for w in wares:
        g = group_of(w)
        if g is not None:
            v[g] = 1.0
    return v


# ---------------------------------------------------------------------------------------------------------------------------- kind index
def _roster() -> list[str]:
    return list(freeze.manifest()["entities"])


def kind_index() -> dict[str, int]:
    if "kind_index" not in _TABLES:
        ids = _roster()
        _TABLES["kind_index"] = {k: i + 1 for i, k in enumerate(ids + [x for x in EXTRA_KINDS if x not in set(ids)])}
    return _TABLES["kind_index"]


def n_kinds() -> int:
    return len(kind_index()) + 1


def building_kind_row(kind: str) -> int:
    """Row of a building kind (0 when unknown)."""
    return kind_index().get(kind, 0)


def unit_kind_row(kind: str) -> int:
    """Row of a unit kind: the roster names units `unit:<kind>`."""
    return kind_index().get("unit:" + kind, 0)


# ---------------------------------------------------------------------------------------------------------------------------- static features
_SIZE = {"small": 1.0 / 3.0, "mine": 1.0 / 3.0, "medium": 2.0 / 3.0, "big": 1.0, "port": 1.0, "water3": 1.0}
_LOCO_COL = {"foot": 0, "legs": 0, "wheeled": 1, "heavywheeled": 1, "tracked": 1, "lighttracked": 1, "heavytracked": 1, "hover": 1, "fly": 2, "naval": 3, "lcraft": 3}


def _spec_io(eid: str, ent: dict) -> tuple[list[str], list[str], dict]:
    """(input wares, output wares, extra facts) of an entity from the registries."""
    from wizard_rts import wl_defs
    from wizard_rts.industry import registry as ind

    facts: dict[str, Any] = {}
    ins, outs = list(ent.get("inputs", []) or []), list(ent.get("outputs", []) or [])
    if eid.startswith("wl:"):
        spec = wl_defs.spec_for_kind(eid) or {}
        ins = list(spec.get("inputs", {}) or ins)
        outs = list(spec.get("outputs", []) or outs)
        facts.update(size=spec.get("size", ""), store=bool(spec.get("store")), port=bool(spec.get("port")), market=bool(spec.get("market")),
                     clinic=any(cmd == "cure" for steps in (spec.get("programs") or {}).values() for cmd, _a in steps))
    elif eid.startswith("mdy:"):
        spec = ind.block(eid) or {}
        ins = list((spec.get("consume_items") or {}))
        outs = list((spec.get("output_item") or {}))
        if spec.get("role") == "drill":
            outs = outs or ["mdy.copper"]
        facts.update(size=spec.get("size", 0), role=spec.get("role", ""), turret=spec.get("role") == "turret")
    return ins, outs, facts


def _static_rows() -> tuple[np.ndarray, np.ndarray]:
    from wizard_rts import construction as con
    from wizard_rts import rules, territory
    from wizard_rts.content import graph

    ents = graph.entities()
    n = n_kinds()
    static = np.zeros((n, N_STATIC), dtype=np.float32)
    ustatic = np.zeros((n, len(UNIT_STATIC_COLUMNS)), dtype=np.float32)
    col = {c: i for i, c in enumerate(KIND_STATIC_COLUMNS)}
    ucol = {c: i for i, c in enumerate(UNIT_STATIC_COLUMNS)}
    menu = con.full_menu()
    factories = set(con.RECIPES)
    recipe_def = {u: r.get("definition", "") for rs in con.RECIPES.values() for u, r in rs.items()}  # hybrid units carry no definition in the content graph
    from wizard_rts.ai_plus import strength_of

    for eid, row in kind_index().items():
        ent = ents.get(eid)
        r = static[row]
        if ent is None:  # the three in-play kinds outside the roster
            if eid == "warehouse":
                r[col["game_hybrid"]], r[col["is_centre"]] = 1.0, 1.0
                r[col["size"]] = 1.0
            elif eid == "blight_nest":
                r[col["game_hybrid"]], r[col["is_military"]] = 1.0, 1.0
            elif eid == "unit:soldier":
                r[col["game_widelands"]], r[col["is_unit"]], r[col["is_military"]] = 1.0, 1.0, 1.0
                ustatic[row, ucol["loco_foot"]] = 1.0
                ustatic[row, ucol["strength"]] = min(strength_of("widelands.soldier", None) / 1000.0, 5.0)
            continue
        is_unit = ent["type"] == "unit"
        r[col["game_" + ent["game"]]] = 1.0
        r[col["is_unit"]] = 1.0 if is_unit else 0.0
        r[col["era"]] = float(ent.get("era", 0)) / 3.0
        ins, outs, facts = _spec_io(eid, ent)
        cost = dict(ent.get("cost", {}) or {})
        r[col["cost_log1p"]] = math.log1p(sum(cost.values())) / 5.0
        for w in outs:
            g = group_of(w)
            if g is not None:
                r[col["produces_" + GROUP_NAMES[g]]] = 1.0
        for w in (ins if not is_unit else list(cost)):
            g = group_of(w)
            if g is not None:
                r[col["consumes_" + GROUP_NAMES[g]]] = 1.0
        if is_unit:
            definition = ent.get("definition") or recipe_def.get(eid[len("unit:"):], "")
            actor = rules.actor(definition) if definition else None
            r[col["is_military"]] = 1.0 if (actor and actor.get("armaments")) else 0.0
            r[col["is_centre"]] = 1.0 if definition in territory.DEPLOYERS else 0.0
            ustatic[row, ucol["is_founder"]] = r[col["is_centre"]]
            loco = _LOCO_COL.get((actor or {}).get("locomotor", "foot"), 0)
            ustatic[row, ucol[("loco_foot", "loco_ground_vehicle", "loco_air", "loco_naval")[loco]]] = 1.0
            ustatic[row, ucol["strength"]] = min(strength_of(definition, None) / 1000.0, 5.0) if actor else 0.0
            tot = float(sum(cost.values())) or 1.0
            for w, k in cost.items():
                g = group_of(w)
                if g is not None:
                    ustatic[row, ucol["cost_" + GROUP_NAMES[g]]] += k / tot
        else:
            spec = menu.get(eid) or {}
            size = facts.get("size", spec.get("size", ""))
            if isinstance(size, (int, float)):  # a Mindustry footprint edge
                r[col["size"]] = 1.0 / 3.0 if size <= 1 else (2.0 / 3.0 if size <= 2 else 1.0)
            else:
                r[col["size"]] = _SIZE.get(size, 2.0 / 3.0)
            definition = spec.get("definition", "")
            actor = rules.actor(definition) if definition.startswith("openra.") else None
            r[col["is_military"]] = 1.0 if (facts.get("turret") or (actor and actor.get("armaments"))) else 0.0
            r[col["is_clinic"]] = 1.0 if (eid == "clinic" or facts.get("clinic")) else 0.0
            r[col["is_centre"]] = 1.0 if (facts.get("store") or facts.get("port") or facts.get("market")) else 0.0
            r[col["is_factory"]] = 1.0 if eid in factories else 0.0
    return static, ustatic


def kind_static() -> np.ndarray:
    """[N_KINDS, 24] float32 static features of every kind (columns: schema.KIND_STATIC_COLUMNS)."""
    if "static" not in _TABLES:
        _TABLES["static"], _TABLES["ustatic"] = _static_rows()
    return _TABLES["static"]


def unit_static() -> np.ndarray:
    """[N_KINDS, 12] float32 static features of unit kinds (H3; columns: schema.UNIT_STATIC_COLUMNS); zero rows for buildings."""
    kind_static()
    return _TABLES["ustatic"]


# ---------------------------------------------------------------------------------------------------------------------------- cards and hashes
def card_features(world: Any, faction: str, card_id: str) -> np.ndarray:
    """The 28 card features of learn/draft_module.card_features (era 4, tribe fit, entity mix, groups made and used, freshness, cost); its first four
    blocks are static, the rest depend on what the faction makes and holds. Note: its group blocks use the five legacy groups of draft_module."""
    from wizard_rts.learn import draft_module

    return draft_module.card_features(world, faction, card_id).astype(np.float32)


CARD_FEATURES = card_features


def obs_schema_hash() -> str:
    """sha256 of the observation schema (version, every field list and width, the key wares, the kind-static columns) and the roster hash."""
    return schema.schema_hash(freeze.roster_hash(freeze.manifest()))
