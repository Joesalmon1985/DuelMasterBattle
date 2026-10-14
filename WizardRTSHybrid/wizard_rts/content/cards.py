"""Card generator v3 (owner programme, 13 Oct 2026): four era selections of exactly 42 cards, each unlocking 1-4 things.

Why 42: a six-faction ring deals seven packs of seven, one pick per faction per round, so a completed phase drafts exactly 42 cards.
If an era's pool is exactly 42 cards, a completed phase puts every card of the era in someone's hands, so the WORLD always obtains the
whole technology of the era (`world_coverage`), whatever the individual picks were.

What a card unlocks is a *slot*: one building, one unit, or a family that the game treats as one thing (a Widelands building together with
its paid enhancements, a Mindustry block together with its large size). A card holds 1-4 slots. Essential capabilities (an iron chain, a
barracks, a starter industrial line, a unit factory) are repeated in at least six cards, so every faction in a six-faction ring has a way
to get them with its seven picks ("a chance to have unlocked everything required"). Everything else appears in exactly one card.

Era selections (owner rules of 13 Oct 2026, with the Historic metal age added by the card rework):
  Prehistoric  Widelands food, farming, timber, stone, textile, trade and seafaring chains, war lodge and its clubs, spears and slings
  Historic     Widelands mining, smelting and smithing, the whole OpenRA roster (military buildings first, units with their producers)
  Modern       Mindustry industry: drills, logistics, power, liquids, heat, crafters, storage, payloads, logic, the Mk2 assembly lines
  Dystopian    Mindustry military industry (unit factories, reconstructors, assemblers, turrets, walls, shields) and the Mindustry units

Everything here is deterministic: stable sorts and CRC hashes, no randomness.
"""

from __future__ import annotations

import re
import zlib
from functools import lru_cache
from typing import Any

PREFIX = "gen."
CAP = 4  # entities (slots) per card, at most
ERA_CARDS = 42  # cards per era = 6 factions x 7 rounds
ERAS = 4

# ---- era selections -----------------------------------------------------------------------------------------------------------

# Widelands buildings of the metal age (Historic): mining, smelting, charcoal for the furnaces, smithing, weapon and armour making
WL_HISTORIC = re.compile(r"(mine$|mine_|smelting|furnace|charcoal|smithy|workshop|warmill|metal|helmsmith|armorsmith|armor_smith|weaponsmith|toolsmith|blacksmith|recycling|tailors|dressmakery|gold_spinning)")
HYBRID_ERA = {"farm": 0, "bakery": 0, "scriptorium": 0, "war_lodge": 0, "clinic": 0, "mine": 1, "ironmine": 1, "smelter": 1, "smithy": 1}
# Mindustry roles that belong to the military industry (Dystopian); everything else is Modern industry
MDY_MILITARY_ROLES = {"turret", "wall", "door", "shield", "mender", "repair", "overdrive", "unit_factory", "reconstructor", "assembler", "assembler_module",
                      "build_turret", "mine", "radar", "cargo", "core", "launch_pad", "accelerator", "payload_driver", "mass_driver"}
SIZE_WORDS = re.compile(r"(^large_|^small_|_large$|_huge$|^huge_|_gigantic$)")

CHEAP_UNITS_PER_CARD = 3  # a producer card holds the producer and up to three of its units


def _h(name: str) -> int:
    return zlib.crc32(name.encode())


# ---- slots -------------------------------------------------------------------------------------------------------------------


class Slot:
    __slots__ = ("key", "members", "era", "tribe", "game", "type", "role", "label", "tags", "producer")

    def __init__(self, key: str, members: list[str], era: int, tribe: str, game: str, typ: str, role: str, label: str, producer: str = "") -> None:
        self.key, self.members, self.era, self.tribe, self.game, self.type, self.role, self.label, self.producer = key, members, era, tribe, game, typ, role, label, producer
        self.tags: set[str] = set()


def _wl_root(kind: str, ents: dict[str, dict], parent: dict[str, str]) -> str:
    """Follow `enhanced_from` upward while the parent is itself a gated (non-foundation) entity."""
    for _ in range(6):
        up = parent.get(kind, "")
        if up and up in ents and not ents[up]["foundation"]:
            kind = up
        else:
            break
    return kind


def wl_era(base: str) -> int:
    return 1 if WL_HISTORIC.search(base) else 0


@lru_cache(maxsize=1)
def slots() -> dict[str, Slot]:
    from wizard_rts import wl_defs
    from wizard_rts.content import graph
    from wizard_rts.industry import blocks as B
    from wizard_rts.industry import units as U

    ents = graph.raw_entities()
    out: dict[str, Slot] = {}
    parent = {}
    for k in ents:
        if k.startswith("wl:"):
            sp = wl_defs.spec_for_kind(k)
            if sp and sp.get("enhanced_from"):
                parent[k] = sp["enhanced_from"]
    fam: dict[str, list[str]] = {}
    for k, e in ents.items():
        if e["foundation"]:
            continue
        if k.startswith("wl:"):
            fam.setdefault(_wl_root(k, ents, parent), []).append(k)
    for root, members in sorted(fam.items()):
        e = ents[root]
        tribe = e["tribe"]
        base = root[3:]
        if tribe and base.startswith(tribe + "_"):
            base = base[len(tribe) + 1:]
        s = Slot(root, sorted(members, key=lambda m: (m != root, m)), wl_era(base) if tribe else HYBRID_ERA.get(root[3:], 0), tribe, "widelands", "building", "wl", e["label"])
        out[root] = s
    for k, e in sorted(ents.items()):
        if e["foundation"] or k.startswith(("wl:", "mdy:", "unit:")):
            continue
        if e["game"] == "widelands":  # legacy tribe-free hybrid kinds (farm, mine, smelter...)
            out[k] = Slot(k, [k], HYBRID_ERA.get(k, 0), "", "widelands", "building", "wl", e["label"])
        else:
            out[k] = Slot(k, [k], e["era"], "", e["game"], "building", "hybrid" if e["game"] == "hybrid" else "ra", e["label"])
    for k, e in sorted(ents.items()):
        if e["foundation"] or not k.startswith("unit:"):
            continue
        out[k] = Slot(k, [k], e["era"], "", e["game"], "unit", "unit", e["label"], producer=e.get("producer", ""))
    # Mindustry blocks: a block and its large size are one slot
    mfam: dict[str, list[str]] = {}
    for k, e in sorted(ents.items()):
        if k.startswith("mdy:"):
            mfam.setdefault("mdy:" + SIZE_WORDS.sub("", k[4:]).replace("__", "_"), []).append(k)
    for key, members in sorted(mfam.items()):
        members.sort(key=lambda m: (len(m), m))
        sp = B.spec(members[0])
        role = sp["role"] if sp else ""
        mil = role in MDY_MILITARY_ROLES and not members[0].startswith("mdy:hy_assembly")
        out[key] = Slot(key, members, 3 if mil else 2, "", "mindustry", "building", role, ents[members[0]]["label"])
    return out


# ---- themes ---------------------------------------------------------------------------------------------------------------------

WL_THEMES = (
    ("seafaring and trade", re.compile(r"(ferry|shipyard|port$|market|dikers|warehouse|scout)")),
    ("mining", re.compile(r"(mine$|mine_)")),
    ("metalworking", re.compile(r"(smelting|furnace|charcoal|recycling|smithy|smith$|workshop|warmill|metal|toolsmith|blacksmith)")),
    ("textiles", re.compile(r"(weaving|sewing|reed|rope|liana|spider|fibre|dress|tailor|gold_spinning)")),
    ("husbandry", re.compile(r"(cattle|donkey|horse|tapir|reindeer|sheep|piggery|gamekeeper|fishbreeder|hunter|wilderness)")),
    ("farming and food", re.compile(r"(farm|mill$|bakery|brewery|winery|vineyard|cassava|cocoa|chocolate|blackroot|honey|mead|aqua|berry|collector|beekeeper|smokery|tavern|inn$|drinking|preserver|food)")),
    ("building materials", re.compile(r"(kiln|clay|wood_hardener|stonemason|lime|brick|sawmill|rare_tree|jungle|gardening)")),
    ("military", re.compile(r"(barracks|initiation|training)")),
)
OPENRA_THEMES = {"pbox": "defences", "hbox": "defences", "agun": "defences", "sam": "defences", "defense": "defences", "flame_tower": "defences", "tesla_coil": "defences",
                 "sbag": "walls", "fenc": "walls", "brik": "walls", "atek": "command and tech", "stek": "command and tech", "dome": "command and tech", "fix": "command and tech",
                 "gap": "command and tech", "iron": "superweapons", "pdox": "superweapons", "mslo": "superweapons"}
MDY_THEMES = {
    "logistics": {"belt", "stack_belt", "router", "sorter", "overflow", "junction", "bridge", "unloader", "mass_driver", "launch_pad", "incinerator"},
    "liquids": {"conduit", "tank", "pump", "liquid_junction", "liquid_bridge"},
    "power": {"generator", "battery", "node", "diode"},
    "heat": {"heater", "heat_conductor"},
    "extraction": {"drill", "wall_drill", "harvester"},
    "crafting": {"crafter"},
    "payloads": {"payload_belt", "payload_loader", "constructor", "deconstructor", "payload_driver"},
    "logic": {"logic"},
    "storage": {"store", "core"},
    "assembly lines": {"unit_factory", "reconstructor", "assembler", "assembler_module"},
    "turrets": {"turret", "build_turret"},
    "defences": {"wall", "door", "shield", "mender", "repair", "overdrive", "radar", "mine", "cargo", "accelerator"},
}
MDY_THEME_OF = {r: t for t, rs in MDY_THEMES.items() for r in rs}


def theme(s: Slot) -> str:
    if s.game == "widelands":
        name = s.key.split(":", 1)[-1]
        if s.tribe and name.startswith(s.tribe + "_"):
            name = name[len(s.tribe) + 1:]
        for t, rx in WL_THEMES:
            if rx.search(name):
                return t
        return "misc"
    if s.game == "openra":
        return OPENRA_THEMES.get(s.key, "misc")
    if s.game == "mindustry":
        return MDY_THEME_OF.get(s.role, "misc")
    return "misc"


# ---- grouping ---------------------------------------------------------------------------------------------------------------------


def _related(a: Slot, b: Slot, ents: dict[str, dict]) -> int:
    """How strongly two slots belong together: a shared ware chain, the same role, the same producer."""
    s = 4 if theme(a) == theme(b) and theme(a) != "misc" else 0
    if a.game == "widelands" and b.game == "widelands":
        ea, eb = ents[a.members[0]], ents[b.members[0]]
        oa, ob = set(ea.get("outputs", [])), set(eb.get("outputs", []))
        ia, ib = set(ea.get("inputs", [])), set(eb.get("inputs", []))
        s += 3 * len(oa & ib) + 3 * len(ob & ia) + len(ia & ib)
        na, nb = a.key.split("_", 1)[-1], b.key.split("_", 1)[-1]
        if na.split("_")[-1] == nb.split("_")[-1]:
            s += 2
    elif a.game == "mindustry" and b.game == "mindustry":
        s += 4 if a.role == b.role else 0
        from wizard_rts.content import graph

        oa, ia = graph._io(a.members[0])
        ob, ib = graph._io(b.members[0])
        s += len(oa & ib) + len(ob & ia)
    else:
        s += 2 if a.role == b.role else 0
    return s


def cluster(items: list[Slot], ents: dict[str, dict], cap: int = CAP) -> list[list[Slot]]:
    """Greedy connected groups of at most `cap` slots; a slot joins the group it is most related to."""
    left = sorted(items, key=lambda s: s.key)
    groups: list[list[Slot]] = []
    while left:
        g = [left.pop(0)]
        while len(g) < cap:
            best, score = None, 0
            for c in left:
                sc = sum(_related(c, m, ents) for m in g)
                if sc > score:
                    best, score = c, sc
            if best is None:
                break
            left.remove(best)
            g.append(best)
        groups.append(g)
    return groups


def adjust(groups: list[list[Slot]], target: int, ents: dict[str, dict], cap: int = CAP) -> list[list[Slot]]:
    """Merge the most related fitting pair, or split the biggest group, until there are exactly `target` groups."""
    groups = [list(g) for g in groups]
    while len(groups) > target:
        best = None
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                n = len(groups[i]) + len(groups[j])
                if n > cap:
                    continue
                rel = sum(_related(a, b, ents) for a in groups[i] for b in groups[j])
                key = (n, -rel, i, j)  # fill the smallest result first, then the most related
                if best is None or key < best[0]:
                    best = (key, i, j)
        if best is None:
            raise ValueError(f"cannot merge {len(groups)} groups down to {target} with cap {cap}")
        _, i, j = best
        groups[i] += groups[j]
        del groups[j]
    while len(groups) < target:
        i = max(range(len(groups)), key=lambda x: (len(groups[x]), -x))
        g = groups[i]
        if len(g) < 2:
            raise ValueError(f"cannot split {len(groups)} groups up to {target}")
        a, b = [g[0]], list(g[1:])
        while len(a) < len(g) // 2 + len(g) % 2 and len(b) > 1:  # move the slot most related to the first part
            m = max(b, key=lambda s: (sum(_related(s, x, ents) for x in a), s.key))
            b.remove(m)
            a.append(m)
        groups[i:i + 1] = [a, b]
    return groups


# ---- cards ---------------------------------------------------------------------------------------------------------------------


def _name(slots_: list[Slot], theme_: str = "") -> str:
    theme = theme_
    if not theme:
        ts = [theme_of for theme_of in (globals()["theme"](s) for s in slots_) if theme_of != "misc"]
        theme = max(sorted(set(ts)), key=ts.count).capitalize() if ts else ""
    labels = [s.label for s in slots_]
    text = ", ".join(labels[:-1]) + " & " + labels[-1] if len(labels) > 1 else labels[0]
    tribe = next((s.tribe for s in slots_ if s.tribe), "")
    return (theme + ": " if theme else "") + text + (f" ({tribe})" if tribe else "")


def _card(cid: str, era: int, slots_: list[Slot], theme: str = "", tags: tuple[str, ...] = (), summary: str = "") -> dict[str, Any]:
    from wizard_rts.content import graph

    members = [m for s in slots_ for m in s.members]
    ents = graph.raw_entities()
    kinds = [m for m in members if not m.startswith(("unit:", "wl:"))]
    units = [m[5:] for m in members if m.startswith("unit:")]
    wl = [m for m in members if m.startswith("wl:")]
    tribe = next((s.tribe for s in slots_ if s.tribe), "")
    return {"id": PREFIX + cid, "name": _name(slots_, theme), "era": era, "summary": summary or (theme or "Unlocks " + ", ".join(s.label.lower() for s in slots_)),
            "kinds": kinds, "units": units, "wl_patterns": [], "wl_kinds": wl, "tribe": tribe, "requires_cards": [], "requires_working": [],
            "entities": members, "slots": [s.key for s in slots_], "tags": sorted(tags), "essential": bool(tags)}


def _chunks(units_: list[Slot], n: int, per: int) -> list[list[Slot]]:
    """Spread `units_` over `n` cards as evenly as possible, at most `per` each."""
    units_ = sorted(units_, key=lambda s: s.key)
    out: list[list[Slot]] = [[] for _ in range(n)]
    for i, u in enumerate(units_):
        out[i % n].append(u)
    assert all(len(c) <= per for c in out), (n, per, [len(c) for c in out])
    return out


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _prehistoric(S: dict[str, Slot], ents: dict[str, dict]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    era = [s for s in S.values() if s.era == 0]
    lodge = S["war_lodge"]
    troops = [S["unit:clubman"], S["unit:spearman"], S["unit:slinger"]]
    pairs = [(0, 1), (1, 2), (2, 0), (0, 2), (1, 0), (2, 1)]  # six war lodge cards, each with two of the three low-tech troops
    for i, (a, b) in enumerate(pairs):
        cards.append(_card(f"p_war_lodge_{i + 1}", 0, [lodge, troops[a], troops[b]], "War band", ("mil_pre",), "The war lodge and two kinds of low-tech troops: the first army of a young settlement."))
    rest = [s for s in era if s is not lodge and s not in troops]
    neutral = [s for s in rest if not s.tribe]
    by_tribe: dict[str, list[Slot]] = {}
    for s in rest:
        if s.tribe:
            by_tribe.setdefault(s.tribe, []).append(s)
    groups: list[list[Slot]] = cluster(neutral, ents)
    for t in sorted(by_tribe):
        groups += cluster(by_tribe[t], ents)
    groups = _adjust_by_class(groups, ERA_CARDS - len(cards), ents)
    for g in sorted(groups, key=lambda g: g[0].key):
        cards.append(_card("p_" + _slug(g[0].key.replace("wl:", "")), 0, g))
    return cards


def _adjust_by_class(groups: list[list[Slot]], target: int, ents: dict[str, dict]) -> list[list[Slot]]:
    """Adjust the number of groups while keeping every group inside one tribe (or tribe-free)."""
    classes: dict[str, list[list[Slot]]] = {}
    for g in groups:
        classes.setdefault(g[0].tribe, []).append(g)
    total = len(groups)
    # distribute the target over the classes in proportion to their slots, every class keeping at least ceil(slots / CAP) groups
    slot_n = {t: sum(len(g) for g in gs) for t, gs in classes.items()}
    need = {t: -(-slot_n[t] // CAP) for t in classes}
    have = {t: len(gs) for t, gs in classes.items()}
    goal = dict(have)
    while sum(goal.values()) > target:  # merge where it frees a card at the least cost
        t = max((t for t in goal if goal[t] > need[t]), key=lambda t: (goal[t] - need[t], t), default=None)
        if t is None:
            break
        goal[t] -= 1
    while sum(goal.values()) < target:  # split where the groups are biggest
        t = max((t for t in goal if goal[t] < slot_n[t]), key=lambda t: (slot_n[t] / goal[t], t))
        goal[t] += 1
    out: list[list[Slot]] = []
    for t in sorted(classes):
        out += adjust(classes[t], goal[t], ents)
    return out


def _historic(S: dict[str, Slot], ents: dict[str, dict]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    units = {k: s for k, s in S.items() if s.type == "unit" and s.era == 1}
    ra_b = {k: s for k, s in S.items() if s.game == "openra" and s.type == "building"}

    def by_producer(p: str) -> list[Slot]:
        return [s for s in units.values() if s.producer == p]

    # producers repeated in six or seven cards: the barracks and the war factory are essential to an army
    for prod, n, tag in (("barracks", 6, "inf"), ("vehicle_factory", 7, "veh")):
        for i, chunk in enumerate(_chunks(by_producer(prod), n, CHEAP_UNITS_PER_CARD)):
            cards.append(_card(f"h_{prod}_{i + 1}", 1, [ra_b[prod]] + chunk, "Barracks" if prod == "barracks" else "War factory", (tag,)))
    ny = by_producer("naval_yard")
    for i, chunk in enumerate(_chunks(ny, 2, CHEAP_UNITS_PER_CARD)):
        cards.append(_card(f"h_naval_yard_{i + 1}", 1, [ra_b["naval_yard"]] + chunk, "Naval yard", ("navy",)))
    for prod, theme, tag in (("sub_pen", "Submarine pen", "navy"), ("afld", "Airfield", "air"), ("hpad", "Helipad", "air"), ("kenn", "Kennel", "")):
        cards.append(_card(f"h_{prod}", 1, [ra_b[prod]] + by_producer(prod), theme, (tag,) if tag else ()))
    taken = {"barracks", "vehicle_factory", "naval_yard", "sub_pen", "afld", "hpad", "kenn"}
    support = [s for k, s in ra_b.items() if k not in taken]
    wl_h = [s for s in S.values() if s.game == "widelands" and s.era == 1]
    # Widelands metal age: a metallurgy card and a smithing card per tribe are the essentials; the neutral hybrid foundry is the sixth supplier
    neutral = sorted([s for s in wl_h if not s.tribe], key=lambda s: s.key)
    # two neutral foundries: an Amazon faction has no iron or coal mine of its own, so it needs two ways to the metal age
    cards.append(_card("h_foundry_1", 1, neutral, "Foundry", ("metal", "smith"), "Coal and iron mines, a smelter and a smithy for any settlement."))
    cards.append(_card("h_foundry_2", 1, neutral, "Foundry", ("metal", "smith"), "Coal and iron mines, a smelter and a smithy for any settlement."))
    order = ("coalmine", "ironmine", "smelting", "furnace", "charcoal_kiln", "charcoal_burners")
    for t in sorted({s.tribe for s in wl_h if s.tribe}):
        mine = [s for s in wl_h if s.tribe == t and re.search(r"(coalmine|ironmine|smelting|furnace|charcoal)", s.key)]
        mine.sort(key=lambda s: next((i for i, w in enumerate(order) if w in s.key), 99))
        if mine:
            real = any(re.search(r"(coalmine|ironmine)", x.key) for x in mine[:CAP])  # the Amazons smelt gold only: no coal or iron of their own
            cards.append(_card(f"h_{t}_metal", 1, mine[:CAP], "Metallurgy", ("metal",) if real else ("gold",)))
    placed = {k for c in cards for k in c["slots"]}
    rest_wl = [s for s in wl_h if s.tribe and s.key not in placed]
    groups = cluster(support, ents)
    for t in sorted({s.tribe for s in rest_wl}):
        groups += cluster([s for s in rest_wl if s.tribe == t], ents)
    # smithing is essential for a tribe: tag the group that holds a smithy or workshop
    groups = _adjust_by_class(groups, ERA_CARDS - len(cards), ents)
    for g in sorted(groups, key=lambda g: g[0].key):
        smith = bool(g[0].tribe) and any(re.search(r"(smithy|workshop|warmill)", s.key) for s in g)
        cards.append(_card("h_" + _slug(g[0].key.replace("wl:", "")), 1, g, tags=("smith",) if smith else ()))
    return cards


def _modern(S: dict[str, Slot], ents: dict[str, dict]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    era = {k: s for k, s in S.items() if s.era == 2}
    # six starter industrial lines: the silicon smelter, a drill and the conveyor are the essential trio; each also carries one block of its own
    starters_extra = ["mdy:combustion_generator", "mdy:solar_panel", "mdy:graphite_press", "mdy:power_node", "mdy:junction", "mdy:router"]
    for i, extra in enumerate(starters_extra):
        parts = [era["mdy:silicon_smelter"], era["mdy:mechanical_drill"], era["mdy:conveyor"]]
        if extra in era:
            parts.append(era[extra])
        cards.append(_card(f"m_starter_{i + 1}", 2, parts, "Starter line", ("line",), "A silicon smelter, a drill and a belt: the first automated line."))
    placed = {k for c in cards for k in c["slots"]}
    rest = [s for k, s in era.items() if k not in placed]
    groups = adjust(cluster(rest, ents), ERA_CARDS - len(cards), ents)
    for g in sorted(groups, key=lambda g: g[0].key):
        cards.append(_card("m_" + _slug(g[0].key.replace("mdy:", "")), 2, g))
    return cards


def _dystopian(S: dict[str, Slot], ents: dict[str, dict]) -> list[dict[str, Any]]:
    from wizard_rts.industry import units as U

    cards: list[dict[str, Any]] = []
    era = {k: s for k, s in S.items() if s.era == 3}
    units = {k: s for k, s in era.items() if s.type == "unit"}
    blds = {k: s for k, s in era.items() if s.type == "building"}
    placed: set[str] = set()
    # the six unit factories are the essentials; each comes with tier-1 units it makes
    for fac in ("ground_factory", "air_factory", "naval_factory", "mech_fabricator", "ship_fabricator", "tank_fabricator"):
        key = "mdy:" + fac
        mine = sorted([s for k, s in units.items() if s.producer == key], key=lambda s: s.key)[:CAP - 1]
        cards.append(_card(f"d_{fac}", 3, [blds[key]] + mine, "Factory", ("factory",)))
        placed.update([key] + [s.key for s in mine])
    # every other unit travels with the reconstructor or assembler that makes it (the producer is repeated when it makes more than three)
    by_prod: dict[str, list[Slot]] = {}
    for k, s in sorted(units.items()):
        if k not in placed:
            by_prod.setdefault(s.producer, []).append(s)
    groups: list[list[Slot]] = []
    for prod, us in sorted(by_prod.items()):
        n = -(-len(us) // CHEAP_UNITS_PER_CARD)
        for chunk in _chunks(us, n, CHEAP_UNITS_PER_CARD):
            groups.append(([blds[prod]] if prod in blds else []) + chunk)
        placed.add(prod)
        placed.update(s.key for s in us)
    groups += cluster([s for k, s in era.items() if k not in placed], ents)
    groups = adjust(groups, ERA_CARDS - len(cards), ents)
    for g in sorted(groups, key=lambda g: g[0].key):
        cards.append(_card("d_" + _slug(g[0].key.replace("mdy:", "").replace("unit:", "u_")), 3, g))
    return cards


@lru_cache(maxsize=1)
def generate() -> dict[str, dict[str, Any]]:
    from wizard_rts.content import graph

    ents = graph.raw_entities()
    S = slots()
    out: dict[str, dict[str, Any]] = {}
    for builder in (_prehistoric, _historic, _modern, _dystopian):
        cards = builder(S, ents)
        for c in cards:
            base, n = c["id"], 2
            while c["id"] in out:
                c["id"], n = f"{base}_{n}", n + 1
            out[c["id"]] = c
    # a producer that serves many units is repeated on each card that needs it: those cards are tagged so the repeat is deliberate
    count: dict[str, int] = {}
    for c in out.values():
        for e in c["entities"]:
            count[e] = count.get(e, 0) + 1
    for c in out.values():
        if any(count[e] > 1 for e in c["entities"]) and "shared" not in c["tags"]:
            c["tags"] = sorted(set(c["tags"]) | {"shared"})
            c["essential"] = True
    return out


def by_era() -> dict[int, list[dict[str, Any]]]:
    out: dict[int, list[dict[str, Any]]] = {e: [] for e in range(ERAS)}
    for c in generate().values():
        out[c["era"]].append(c)
    return out


# ---- essentials and audit ---------------------------------------------------------------------------------------------------------

ESSENTIAL_ORDER = {0: ("mil_pre",), 1: ("metal", "smith", "inf", "veh"), 2: ("line",), 3: ("factory",)}  # what a first pack must offer, most urgent first
# what a faction needs from the era to be able to play it; every tag must be held (by a card usable by the faction) for the era to count as "ready"
REQUIRED = {0: ("mil_pre",), 1: ("metal", "smith", "prod"), 2: ("line",), 3: ("factory",)}
MIN_SUPPLIERS = 6  # a six-faction ring: every faction can have its own supplier of an essential capability


def card_tags(card: dict[str, Any]) -> set[str]:
    t = set(card.get("tags", ()))
    if t & {"inf", "veh"}:
        t.add("prod")  # a barracks or a war factory cards counts as military production
    return t


def usable_by(card: dict[str, Any], tribe: str) -> bool:
    return not card.get("tribe") or card["tribe"] == tribe


def missing(held: set[str], tribe: str, era: int) -> list[str]:
    """Required capabilities of `era` that the cards in `held` (ids) do not give a faction of `tribe`."""
    cs = generate()
    have: set[str] = set()
    for cid in held:
        c = cs[cid]
        if c["era"] == era and usable_by(c, tribe):
            have |= card_tags(c)
    return [t for t in REQUIRED[era] if t not in have]


def _matchable(factions: list[str], suppliers: list[dict[str, Any]], tribe_of: dict[str, str]) -> bool:
    """Can every faction get its own supplier? (bipartite matching: a supplier serves one faction and must be usable by it)"""
    owner: dict[str, str] = {}

    def place(f: str, seen: set[str]) -> bool:
        for c in suppliers:
            if not usable_by(c, tribe_of[f]) or c["id"] in seen:
                continue
            seen.add(c["id"])
            if c["id"] not in owner or place(owner[c["id"]], seen):
                owner[c["id"]] = f
                return True
        return False

    return all(place(f, set()) for f in factions)


def audit() -> list[str]:
    """Static guarantees: for every way six factions can share the five tribes, every faction can be given its own supplier of every capability
    the era requires (the neutral cards serve whoever needs them)."""
    problems: list[str] = []
    cs = generate()
    tribes_ = sorted({c["tribe"] for c in cs.values() if c["tribe"]})
    for double in tribes_:
        ring = [(t, 0) for t in tribes_] + [(double, 1)]
        names = [f"{t}#{i}" for t, i in ring]
        tribe_of = {n: t for n, (t, _) in zip(names, ring)}
        for era, tags in REQUIRED.items():
            for tag in tags:
                suppliers = [c for c in cs.values() if c["era"] == era and tag in card_tags(c)]
                if not _matchable(names, suppliers, tribe_of):
                    problems.append(f"era {era}: with {double} twice, not every faction can have its own supplier of {tag!r}")
    return problems
