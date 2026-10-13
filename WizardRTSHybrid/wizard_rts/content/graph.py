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
    "farm": 0, "mine": 0, "ironmine": 0, "smelter": 0, "smithy": 1, "scriptorium": 1, "bakery": 0, "war_lodge": 0, "barracks": 1, "vehicle_factory": 1,
    "defense": 1, "flame_tower": 1, "tesla_coil": 2, "naval_yard": 1, "sub_pen": 2,
}
UNIT_ERA = {
    "clubman": 0, "spearman": 0, "slinger": 0, "settlers": 0, "infantry": 1, "grenadier": 1, "rocket_soldier": 1, "tank": 1, "jeep": 1,
    "light_tank": 1, "medium_tank": 1, "apc": 1, "artillery": 1, "mammoth": 1, "v2_launcher": 1, "mcv": 1, "patrol_boat": 1,
    "tesla_tank": 2, "phase_tank": 2, "chrono_tank": 3, "shock_trooper": 3, "submarine": 2,
    "flamethrower": 1, "attack_dog": 1, "destroyer": 1, "commando": 3, "cruiser": 2, "missile_sub": 2,
}


MDY_ERA = {"mdy:solar_panel_large": 3, "mdy:pneumatic_drill": 3, "mdy:silicon_smelter": 3, "mdy:graphite_press": 2, "mdy:battery": 3, "mdy:ground_factory": 3}
MDY_UNITS = {"dagger": 3, "crawler": 3, "nova": 3}
# hand-written pairs (an input-output chain or a producer with its first product), reviewed once; every other Mindustry entity is a single card
MDY_PAIRS = [("mdy:mechanical_drill", "mdy:conveyor"), ("mdy:combustion_generator", "mdy:power_node"), ("mdy:solar_panel", "mdy:battery"),
             ("mdy:graphite_press", "mdy:silicon_smelter"), ("mdy:ground_factory", "unit:dagger")]


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
                     "era": 0 if wl else HYBRID_BUILDING_ERA.get(kind, 0), "cost": dict(spec["cost"]), "foundation": foundation_kind(kind),
                     "functional": True}
        if wl:
            ws = wl_defs.spec_for_kind(kind)
            out[kind]["inputs"] = sorted(ws["inputs"]) if ws else []
            out[kind]["outputs"] = list(ws["outputs"]) if ws else []
    from wizard_rts.industry import registry as mdy

    for kind in mdy.kinds():  # the Mindustry slice that is functional today (plan v2 P9 and P11 grow this)
        b = mdy.build_spec(kind)
        out[kind] = {"id": kind, "type": "building", "game": "mindustry", "tribe": "", "label": b["label"], "era": MDY_ERA.get(kind, 2), "cost": dict(b["cost"]),
                     "foundation": False, "functional": True}
    for unit, era in MDY_UNITS.items():
        u = mdy.ground_unit(unit)
        out["unit:" + unit] = {"id": "unit:" + unit, "type": "unit", "game": "mindustry", "tribe": "", "label": u["label"], "era": era, "cost": {},
                               "producer": "mdy:ground_factory", "foundation": False, "functional": True, "definition": u["definition"]}
    for building, recipes in sorted(con.RECIPES.items()):
        for unit, rec in sorted(recipes.items()):
            out["unit:" + unit] = {"id": "unit:" + unit, "type": "unit", "game": "openra" if str(rec.get("definition", "")).startswith("openra.") else "hybrid",
                                   "tribe": "", "label": rec["label"], "era": UNIT_ERA.get(unit, 1), "cost": dict(rec.get("cost", {})), "producer": building,
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
            if _h(k) % 100 < 55:
                outs = set(ents[k].get("outputs", []))
                for other in left:
                    if other not in taken and other != k and outs & set(ents[other].get("inputs", [])) and "deeper" not in other:
                        partner = other
                        break
            group = [k] + ([partner] if partner else [])
            if partner:
                taken.add(partner)
            label = ents[k]["label"] + (f" + {ents[partner]['label']}" if partner else "")
            cards[PREFIX + k[3:]] = _card(k[3:], f"{label} ({tribe})", 0, group, "A Widelands production chain for the %s." % tribe)
    # Mindustry: the hand-written pairs, then everything left alone
    used_m: set[str] = set()
    for a, b in MDY_PAIRS:
        if a in ents and b in ents:
            cards[PREFIX + a.replace(":", "_")] = _card(a.replace(":", "_"), f"{ents[a]['label']} + {ents[b]['label']}", max(ents[a]["era"], ents[b]["era"]), [a, b], "A Mindustry chain.")
            used_m.update((a, b))
    for k, e in sorted(ents.items()):
        if e["game"] == "mindustry" and k not in used_m:
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
    for u, e in sorted(ents.items()):
        if e["type"] == "unit" and u not in used_units and not e["foundation"] and e["game"] != "mindustry":
            cards[PREFIX + u.replace(":", "_")] = _card(u.replace(":", "_"), e["label"], e["era"], [u], "Unlocks the %s." % e["label"].lower())
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
    for k, e in ents.items():
        if not e["foundation"] and e["functional"] and k not in seen:
            problems.append(f"{k}: functional but on no card")
    return problems
