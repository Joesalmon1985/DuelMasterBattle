"""Content graph and generated technology cards (plan v2 sections 4 and 5.2).

Entities come from the game's own registries, so a card can only ever unlock something that exists:
  buildings  construction.full_menu()  (hybrid kinds plus every runnable Widelands building, key `wl:<tribe>_<name>`)
  units      construction.RECIPES      (unit kind -> producing building)
A card unlocks one or two entities. Cards are generated deterministically (no randomness, only stable hashes of names):
  * a Widelands building and, for about half of them, a partner of the same tribe that consumes what it makes (a chain pair);
  * a hybrid/OpenRA building together with its first unit, and every further unit alone.
Ids are `gen.<slug>`. They coexist with the hand-written `dmb.card.*` set; the old draft ignores `gen.` cards and drafting v2 deals only
them when `world.cardset == "v2"`. The foundation (what a faction always has) is tech.FOUNDATION_* plus the primitive kit.
"""

from __future__ import annotations

import zlib
from functools import lru_cache
from typing import Any

from wizard_rts import construction as con
from wizard_rts import wl_defs

PREFIX = "gen."
HYBRID_BUILDING_ERA = {  # era of the earlier hand-written card that unlocked it (data/tech_cards.json), kept so v2 starts from the same order
    "farm": 0, "mine": 0, "ironmine": 0, "smelter": 0, "smithy": 0, "scriptorium": 0, "clinic": 0, "bakery": 0, "war_lodge": 0, "barracks": 1, "vehicle_factory": 1,
    "defense": 1, "flame_tower": 1, "tesla_coil": 1, "naval_yard": 1, "sub_pen": 1,
}
UNIT_ERA = {  # rule (owner, 13 Oct 2026): the whole OpenRA roster is available by Historic (era 1); primitive Widelands troops and settlers are Prehistoric
    "clubman": 0, "spearman": 0, "slinger": 0, "settlers": 0,
}
OPENRA_LATEST_ERA = 1
MINDUSTRY_MILITARY_EARLIEST_ERA = 3


MDY_ERA: dict[str, int] = {}  # every functional Mindustry building is Modern (era 2): the whole industrial line must be draftable inside one era; units are Dystopian
def _mdy_units() -> dict[str, int]:
    from wizard_rts.industry import units as U

    return {n: MINDUSTRY_MILITARY_EARLIEST_ERA for n in U.unit_list() if U.is_producible(n)}
# hand-written pairs (an input-output chain or a producer with its first product), reviewed once; every other Mindustry entity is a single card
MDY_PAIRS = [("mdy:mechanical_drill", "mdy:conveyor"), ("mdy:combustion_generator", "mdy:power_node"), ("mdy:solar_panel", "mdy:battery"),
             ("mdy:graphite_press", "mdy:silicon_smelter"), ("mdy:ground_factory", "unit:dagger"), ("mdy:air_factory", "unit:flare"), ("mdy:naval_factory", "unit:risso"),
             ("mdy:additive_reconstructor", "unit:mace"), ("mdy:multiplicative_reconstructor", "unit:fortress"), ("mdy:exponential_reconstructor", "unit:scepter"),
             ("mdy:tetrative_reconstructor", "unit:reign"), ("mdy:mech_fabricator", "unit:merui"), ("mdy:ship_fabricator", "unit:retusa"), ("mdy:tank_fabricator", "unit:stell")]


def _mdy_producer(unit: str) -> str:
    from wizard_rts.industry import blocks as B
    from wizard_rts.industry import units as U

    if U.chains().get(unit, 1) == 1:
        for k, sp in sorted(B.specs().items()):
            if any(p["unit"] == unit for p in sp.get("plans") or []):
                return k
    for k, sp in sorted(B.specs().items()):
        for pair in sp.get("upgrades") or []:
            if len(pair) > 1 and pair[1] == unit:
                return k
    for k, sp in sorted(B.specs().items()):
        if any(p["unit"] == unit for p in sp.get("assembler_plans") or []):
            return k
    return ""


def _io(kind: str) -> tuple[set[str], set[str]]:
    from wizard_rts.industry import registry as mdy

    sp = mdy.block(kind)
    if sp is None:
        return set(), set()
    outs = set(sp["output_item"]) | set(sp["output_liquid"]) | set(sp.get("results", {}))
    ins = set(sp["consume_items"]) | set(sp["consume_liquids"])
    if sp["role"] in ("generator",) or sp["power_production_per_s"] > 0:
        outs.add("power")
    if sp["power_use_per_s"] > 0:
        ins.add("power")
    if sp["role"] == "drill":
        outs.add("ore")
    if sp["role"] in ("belt", "stack_belt", "router", "sorter", "overflow", "junction", "bridge", "unloader"):
        ins.add("ore")
        outs.add("ore")
    if sp["role"] in ("conduit", "tank", "liquid_junction", "liquid_bridge"):
        ins.add("water")
        outs.add("water")
    return outs, ins


def _auto_pairs(ents: dict[str, dict], taken: set[str]) -> list[tuple[str, str]]:
    """About 45 % of the remaining Mindustry blocks of an era go two to a card, each with a block it exchanges something with (an output of one is an
    input of the other); deterministic (stable hashes only). Units are paired elsewhere."""
    pairs: list[tuple[str, str]] = []
    left = [k for k, e in sorted(ents.items()) if e["game"] == "mindustry" and e["type"] == "building" and k not in taken]
    done: set[str] = set()
    for k in sorted(left, key=_h):
        if k in done or _h("pair:" + k) % 100 >= 42:
            continue
        o1, i1 = _io(k)
        cands = [c for c in left if c != k and c not in done and ents[c]["era"] == ents[k]["era"]]
        rel = [c for c in cands if (o1 & _io(c)[1]) or (i1 & _io(c)[0])]
        pool = rel or cands
        if not pool:
            continue
        partner = min(pool, key=lambda c: _h(k + c))
        pairs.append((k, partner))
        done.update((k, partner))
    return pairs


def _h(name: str) -> int:
    return zlib.crc32(name.encode())


def foundation_kind(kind: str) -> bool:
    from wizard_rts import tech

    if kind in tech.primitive()["kinds"] or kind in tech.FOUNDATION_KINDS:
        return True
    if kind.startswith("wl:"):
        pats = list(tech.primitive()["wl_patterns"]) + list(tech.FOUNDATION_PATTERNS)
        name = kind[3:]
        for suffix in tech.RESTRICTED:
            if suffix in name:
                return False
        return any(p in name for p in pats)
    return False


@lru_cache(maxsize=1)
def raw_entities() -> dict[str, dict[str, Any]]:
    """Every functional entity with the facts the card generator needs (its era here is the legacy one; `entities` has the real one)."""
    out: dict[str, dict[str, Any]] = {}
    for kind, spec in sorted(con.full_menu().items()):
        wl = kind.startswith("wl:")
        out[kind] = {"id": kind, "type": "building", "game": spec.get("game", "hybrid"), "tribe": spec.get("tribe", ""), "label": spec["label"],
                     "era": 0 if wl else (OPENRA_LATEST_ERA if spec.get("game") == "openra" else HYBRID_BUILDING_ERA.get(kind, 0)), "cost": dict(spec["cost"]), "foundation": foundation_kind(kind),
                     "functional": True}
        if wl:
            ws = wl_defs.spec_for_kind(kind)
            out[kind]["inputs"] = sorted(ws["inputs"]) if ws else []
            out[kind]["outputs"] = list(ws["outputs"]) if ws else []
    from wizard_rts.industry import registry as mdy

    for kind in mdy.kinds():  # the Mindustry slice that is functional today (plan v2 P9 and P11 grow this)
        b = mdy.build_spec(kind)
        out[kind] = {"id": kind, "type": "building", "game": "mindustry", "family": "industrial-hybrid" if kind.startswith("mdy:hy_") else "mindustry", "tribe": "", "label": b["label"], "era": MDY_ERA.get(kind, 2), "cost": dict(b["cost"]),
                     "foundation": False, "functional": True}
    from wizard_rts.industry import units as U

    for unit, era in _mdy_units().items():
        out["unit:" + unit] = {"id": "unit:" + unit, "type": "unit", "game": "mindustry", "tribe": "", "label": U.label_of(unit), "era": era, "cost": {},
                               "producer": _mdy_producer(unit), "foundation": False, "functional": True, "definition": "mindustry." + unit.replace("-", "_"),
                               "tier": U.chains().get(unit, 1)}
    for building, recipes in sorted(con.RECIPES.items()):
        for unit, rec in sorted(recipes.items()):
            out["unit:" + unit] = {"id": "unit:" + unit, "type": "unit", "game": "openra" if str(rec.get("definition", "")).startswith("openra.") else "hybrid",
                                   "tribe": "", "label": rec["label"], "era": UNIT_ERA.get(unit, OPENRA_LATEST_ERA), "cost": dict(rec.get("cost", {})), "producer": building,
                                   "foundation": unit in ("settlers",), "functional": True}
    return out


@lru_cache(maxsize=1)
def entities() -> dict[str, dict[str, Any]]:
    """The entity table with the eras of the card rework (content/cards.py): the era of an entity is the era of the slot that holds it."""
    from wizard_rts.content import cards

    out = {k: dict(e) for k, e in raw_entities().items()}
    for slot in cards.slots().values():
        for m in slot.members:
            if m in out:
                out[m]["era"] = slot.era
    return out


@lru_cache(maxsize=1)
def generated_cards() -> dict[str, dict[str, Any]]:
    from wizard_rts.content import cards

    return cards.generate()


def check() -> list[str]:
    """Static checks: every card holds 1-4 slots of things that exist; every non-foundation functional entity is on a card; each era holds exactly
    42 cards; essential capabilities have enough suppliers; the era rules hold."""
    from wizard_rts.content import cards as C

    problems = []
    ents = entities()
    seen: set[str] = set()
    per_era = {e: 0 for e in range(C.ERAS)}
    for cid, c in generated_cards().items():
        per_era[c["era"]] += 1
        if not 1 <= len(c["slots"]) <= C.CAP:
            problems.append(f"{cid}: {len(c['slots'])} slots")
        for e in c["entities"]:
            if e not in ents:
                problems.append(f"{cid}: unknown entity {e}")
            elif ents[e]["foundation"]:
                problems.append(f"{cid}: foundation entity {e} needs no card")
            elif ents[e]["era"] != c["era"]:
                problems.append(f"{cid}: {e} belongs to era {ents[e]['era']}, card is era {c['era']}")
            seen.add(e)
    for era, n in per_era.items():
        if n != C.ERA_CARDS:
            problems.append(f"era {era} has {n} cards, not {C.ERA_CARDS}")
    for k, e in ents.items():
        if not e["foundation"] and e["functional"] and k not in seen:
            problems.append(f"{k}: functional but on no card")
        if e["game"] in ("openra", "hybrid") and e["type"] == "unit" and e["era"] > OPENRA_LATEST_ERA and k.removeprefix("unit:") not in UNIT_ERA:
            problems.append(f"{k}: an OpenRA unit must be available by Historic, not era {e['era']}")
        if e["game"] == "openra" and e["era"] != OPENRA_LATEST_ERA:
            problems.append(f"{k}: an OpenRA entity is Historic, not era {e['era']}")
        if e["game"] == "mindustry" and e["type"] == "unit" and e["era"] != MINDUSTRY_MILITARY_EARLIEST_ERA:
            problems.append(f"{k}: a Mindustry military unit is Dystopian")
        if e["game"] == "mindustry" and e["type"] == "building" and e["era"] < 2:
            problems.append(f"{k}: Mindustry industry begins in Modern")
        if e["game"] == "widelands" and e["era"] > 1:
            problems.append(f"{k}: Widelands production is Prehistoric or Historic")
    problems += C.audit()
    return problems
