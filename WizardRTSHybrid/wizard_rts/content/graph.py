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
def entities() -> dict[str, dict[str, Any]]:
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


def _card(slug: str, name: str, era: int, ents: list[str], summary: str) -> dict[str, Any]:
    kinds = [e for e in ents if not e.startswith(("unit:", "wl:"))]
    units = [e[5:] for e in ents if e.startswith("unit:")]
    wl = [e for e in ents if e.startswith("wl:")]
    tribe = next((entities()[e]["tribe"] for e in wl), "")
    return {"id": PREFIX + slug, "name": name, "era": era, "summary": summary, "kinds": kinds, "units": units, "wl_patterns": [], "wl_kinds": wl, "tribe": tribe,
            "requires_cards": [], "requires_working": [], "entities": list(ents)}


@lru_cache(maxsize=1)
def generated_cards() -> dict[str, dict[str, Any]]:
    ents = entities()
    cards: dict[str, dict[str, Any]] = {}
    # Widelands: chain pairs inside one tribe
    by_tribe: dict[str, list[str]] = {}
    for k, e in ents.items():
        if k.startswith("wl:") and not e["foundation"]:
            by_tribe.setdefault(e["tribe"], []).append(k)
    for tribe, kinds in sorted(by_tribe.items()):
        left = list(kinds)
        taken: set[str] = set()
        for k in kinds:
            if k in taken:
                continue
            taken.add(k)
            partner = None
            if _h(k) % 100 < 70:
                outs = set(ents[k].get("outputs", []))
                for other in left:
                    if other not in taken and other != k and outs & set(ents[other].get("inputs", [])) and "deeper" not in other:
                        partner = other
                        break
                if partner is None and _h("any:" + k) % 100 < 45:  # no chain partner: a neighbour of the same tribe (still one card, two buildings)
                    free = [o for o in left if o not in taken and o != k and "deeper" not in o]
                    partner = min(free, key=lambda o: _h(k + o)) if free else None
            group = [k] + ([partner] if partner else [])
            if partner:
                taken.add(partner)
            label = ents[k]["label"] + (f" + {ents[partner]['label']}" if partner else "")
            cards[PREFIX + k[3:]] = _card(k[3:], f"{label} ({tribe})", 0, group, "A Widelands production chain for the %s." % tribe)
    # Mindustry: the hand-written pairs, then relation pairs (an output feeding an input), then singles
    used_m: set[str] = set()
    for a, b in MDY_PAIRS:
        if a in ents and b in ents:
            cards[PREFIX + a.replace(":", "_")] = _card(a.replace(":", "_"), f"{ents[a]['label']} + {ents[b]['label']}", max(ents[a]["era"], ents[b]["era"]), [a, b], "A Mindustry chain.")
            used_m.update((a, b))
    for a, b in _auto_pairs(ents, used_m):
        cards[PREFIX + a.replace(":", "_")] = _card(a.replace(":", "_"), f"{ents[a]['label']} + {ents[b]['label']}", max(ents[a]["era"], ents[b]["era"]), [a, b],
                                                 "A Mindustry chain: %s feeds %s." % (ents[a]["label"].lower(), ents[b]["label"].lower()))
        used_m.update((a, b))
    for k, e in sorted(ents.items()):
        if e["game"] == "mindustry" and e["type"] == "building" and k not in used_m:
            cards[PREFIX + k.replace(":", "_")] = _card(k.replace(":", "_"), e["label"], e["era"], [k], "A Mindustry %s." % e["type"])
            used_m.add(k)
    # hybrid / OpenRA buildings with their first unit, then single units
    unit_by_building: dict[str, list[str]] = {}
    for u, e in ents.items():
        if u.startswith("unit:"):
            unit_by_building.setdefault(e["producer"], []).append(u)
    used_units: set[str] = set()
    for k, e in sorted(ents.items()):
        if e["type"] != "building" or k.startswith(("wl:", "mdy:")) or e["foundation"]:
            continue
        units = [u for u in unit_by_building.get(k, []) if not ents[u]["foundation"]]
        group = [k] + units[:1]
        used_units.update(units[:1])
        cards[PREFIX + k] = _card(k, e["label"] + (f" + {ents[units[0]]['label']}" if units else ""), max([e["era"]] + [ents[u]["era"] for u in units[:1]]), group,
                                  "A %s" % e["label"].lower())
    pool = [u for u, e in sorted(ents.items()) if e["type"] == "unit" and u not in used_units and not e["foundation"] and e["game"] != "mindustry"]
    paired: set[str] = set()
    for u in pool:  # OpenRA units: neighbours that the same building produces share a card about half the time
        if u in paired or _h("upair:" + u) % 100 >= 55:
            continue
        mates = [v for v in pool if v != u and v not in paired and ents[v]["producer"] == ents[u]["producer"] and ents[v]["era"] == ents[u]["era"]]
        if mates:
            v = min(mates, key=lambda c: _h(u + c))
            cards[PREFIX + u.replace(":", "_")] = _card(u.replace(":", "_"), f"{ents[u]['label']} + {ents[v]['label']}", ents[u]["era"], [u, v],
                                                     "Unlocks the %s and the %s." % (ents[u]["label"].lower(), ents[v]["label"].lower()))
            paired.update((u, v))
    for u in pool:
        if u not in paired:
            cards[PREFIX + u.replace(":", "_")] = _card(u.replace(":", "_"), ents[u]["label"], ents[u]["era"], [u], "Unlocks the %s." % ents[u]["label"].lower())
    mu = [u for u, e in sorted(ents.items()) if e["type"] == "unit" and e["game"] == "mindustry" and u not in used_m]
    from wizard_rts.industry import units as U

    chain: dict[str, list[str]] = {}
    for u in mu:
        root = u
        for _ in range(6):
            prev = next((p for p in mu if U.upgrade_of(p[5:]) == root[5:]), None)
            if prev is None:
                break
            root = prev
        chain.setdefault(root, []).append(u)
    for root, members in sorted(chain.items()):
        members.sort(key=lambda x: ents[x]["tier"])
        i = 0
        while i < len(members):
            if i + 1 < len(members) and _h("mpair:" + members[i]) % 100 < 60 and ents[members[i]]["producer"] != "":
                a, b = members[i], members[i + 1]
                cards[PREFIX + a.replace(":", "_")] = _card(a.replace(":", "_"), f"{ents[a]['label']} + {ents[b]['label']}", ents[a]["era"], [a, b],
                                                         "Unlocks two tiers of the same line.")
                used_m.update((a, b))
                i += 2
            else:
                a = members[i]
                cards[PREFIX + a.replace(":", "_")] = _card(a.replace(":", "_"), ents[a]["label"], ents[a]["era"], [a], "Unlocks the %s." % ents[a]["label"].lower())
                used_m.add(a)
                i += 1
    return cards


def check() -> list[str]:
    """Static checks (plan 2.4): every card unlocks 1-2 entities that exist; no entity sits in two cards; foundation entities need no card."""
    problems = []
    ents = entities()
    seen: dict[str, str] = {}
    for cid, c in generated_cards().items():
        if not 1 <= len(c["entities"]) <= 2:
            problems.append(f"{cid}: {len(c['entities'])} entities")
        for e in c["entities"]:
            if e not in ents:
                problems.append(f"{cid}: unknown entity {e}")
            if e in seen:
                problems.append(f"{e} in {cid} and {seen[e]}")
            seen[e] = cid
            if ents.get(e, {}).get("foundation"):
                problems.append(f"{cid}: foundation entity {e} needs no card")
    for k, e in ents.items():  # era rules (owner, 13 Oct 2026)
        if e["game"] in ("openra", "hybrid") and e["type"] == "unit" and e["era"] > OPENRA_LATEST_ERA and k.removeprefix("unit:") not in UNIT_ERA:
            problems.append(f"{k}: an OpenRA unit must be available by Historic, not era {e['era']}")
        if e["game"] == "openra" and e["era"] > OPENRA_LATEST_ERA:
            problems.append(f"{k}: an OpenRA entity must be available by Historic, not era {e['era']}")
        if e["game"] == "mindustry" and e["type"] == "unit" and e["era"] < MINDUSTRY_MILITARY_EARLIEST_ERA:
            problems.append(f"{k}: a Mindustry military unit cannot precede the Dystopian era")
        if e["game"] == "mindustry" and e["type"] == "building" and e["era"] < 2:
            problems.append(f"{k}: Mindustry industry begins in Modern")
        if e["game"] == "widelands" and e["era"] != 0:
            problems.append(f"{k}: Widelands civilian production is Prehistoric")
    for k, e in ents.items():
        if not e["foundation"] and e["functional"] and k not in seen:
            problems.append(f"{k}: functional but on no card")
    return problems
