"""Auditable content coverage: one record per upstream entity (plan v2 15.1, owner programme 13 Oct 2026).

Every Widelands building, OpenRA actor, Mindustry block/unit/item/liquid gets a row with:
  status      functional | pending | excluded          (the simulation either runs it or says why not)
  blocker     what is missing when pending / why excluded
  era, card   where it can be unlocked (content graph), or "foundation"
  art         none | static | states | directional | layered  (what the art catalogue holds)
  verified    the name of the data-driven test family that exercises it, or ""
The table is generated, never hand-edited; `tests/test_coverage.py` fails when a functional entity is not unlockable, has no recipe, etc.
A feature counts as complete only when status is functional, art is at least the level its class requires, and `verified` is set.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

HYB = Path(__file__).resolve().parents[1]
DATA = Path(__file__).with_name("data")
ART = HYB.parent / "godot_project" / "client" / "hybrid" / "art" / "catalogue.json"

EXCLUDED_RA = {"harv": "harvester: the credit economy is replaced by wares (roster rule 4.2)", "ant": "mission-only creature", "zombie": "mission-only creature",
               "fireant": "mission-only creature", "scoutant": "mission-only creature", "warriorant": "mission-only creature",
               "hind": "disabled in the RA rules (prerequisite ~disabled)"}
SANDBOX_CLASSES = {"ItemSource", "ItemVoid", "LiquidSource", "LiquidVoid", "PowerSource", "PowerVoid", "LightBlock", "CanvasBlock"}


@lru_cache(maxsize=1)
def _catalogue() -> dict[str, dict[str, Any]]:
    if not ART.is_file():
        return {}
    return {i["id"]: i for i in json.loads(ART.read_text(encoding="utf-8"))["items"]}


def art_level(prefix: str, extra: tuple[str, ...] = ()) -> str:
    """Highest art tier found for catalogue ids starting with `prefix` (exact id or `prefix.<state>`)."""
    cat = _catalogue()
    ids = [k for k in cat if k == prefix or k.startswith(prefix + ".")] + [k for e in extra for k in cat if k == e]
    if not ids:
        return "none"
    items = [cat[k] for k in ids]
    if any(i.get("layers") for i in items):
        return "layered"
    if any(int(i.get("facings", 1)) > 1 or ".walk." in i["id"] for i in items):
        return "directional"
    if len(ids) > 1 or any(int(i.get("frames", 1)) > 1 for i in items):
        return "states"
    if all(i.get("status") == "alias_placeholder" for i in items):
        return "placeholder"
    return "static"


def build() -> list[dict[str, Any]]:
    from wizard_rts import construction as con
    from wizard_rts.content import graph
    from wizard_rts.industry import registry as mdy
    from wizard_rts import tech

    ents = graph.entities()
    cards = graph.generated_cards()
    card_of = {e: cid for cid, c in cards.items() for e in c["entities"]}
    menu = con.full_menu()
    rows: list[dict[str, Any]] = []

    def add(key: str, game: str, typ: str, name: str, status: str, blocker: str = "", ent_id: str = "", art: str = "none", extra: dict | None = None) -> None:
        e = ents.get(ent_id, {}) if ent_id else {}
        rows.append({"key": key, "game": game, "type": typ, "name": name, "status": status, "blocker": blocker, "entity": ent_id,
                     "era": e.get("era", ""), "card": ("foundation" if e.get("foundation") else card_of.get(ent_id, "")) if ent_id else "", "art": art, **(extra or {})})

    wl = json.loads((DATA / "widelands_defs.json").read_text())
    for n, b in sorted(wl["buildings"].items()):
        kind = f"wl:{n}"
        art = art_level("widelands." + n)
        if n.endswith("headquarters"):
            add(kind, "widelands", b["type"], b.get("descname") or n, "functional", art=art, extra={"tribe": b["tribe"], "note": "the hybrid warehouse (a settlement's command centre) is the headquarters"})
        elif "headquarters" in n:
            add(kind, "widelands", b["type"], b.get("descname") or n, "excluded", "scenario start variant of the headquarters (interim / shipwreck): the hybrid starts every faction with one warehouse", art=art,
                extra={"tribe": b["tribe"]})
        elif kind in menu:
            add(kind, "widelands", b["type"], b.get("descname") or n, "functional", ent_id=kind, art=art, extra={"tribe": b["tribe"]})
        elif b["type"] in ("militarysite", "trainingsite"):
            add(kind, "widelands", b["type"], b.get("descname") or n, "excluded", "Widelands military/training: replaced by the OpenRA military (D05)", art=art, extra={"tribe": b["tribe"]})
        else:
            add(kind, "widelands", b["type"], b.get("descname") or n, "pending", b.get("blocked_by") or f"{b['type']} not simulated", art=art, extra={"tribe": b["tribe"]})
    ra = json.loads((DATA / "openra_rules.json").read_text())
    have_units = {r["definition"].split(".", 1)[1]: u for rs in con.RECIPES.values() for u, r in rs.items() if str(r.get("definition", "")).startswith("openra.")}
    have_blds = {s["definition"].split(".", 1)[1]: k for k, s in menu.items() if str(s.get("definition", "")).startswith("openra.")}
    for a, r in sorted(ra["actors"].items()):
        queue = r.get("queue")
        if r.get("is_building") and queue in ("Building", "Defense"):
            from wizard_rts import openra_content as OC

            if a in OC.EXCLUDED_BUILDING:
                add("openra:" + a, "openra", "building", r.get("name", a), "excluded", OC.EXCLUDED_BUILDING[a], art=art_level("openra." + a))
            elif a in OC.EXISTING_BUILDING and a not in have_blds:
                add("openra:" + a, "openra", "building", r.get("name", a), "functional", ent_id=OC.EXISTING_BUILDING[a], art=art_level("openra." + a),
                    extra={"note": "same hybrid building as " + OC.EXISTING_BUILDING[a]})
            elif a in have_blds:
                add("openra:" + a, "openra", "building", r.get("name", a), "functional", ent_id=have_blds[a], art=art_level("openra." + a))
            else:
                add("openra:" + a, "openra", "building", r.get("name", a), "pending", "not in the build menu", art=art_level("openra." + a))
        elif not r.get("is_building") and queue in ("Infantry", "Vehicle", "Ship", "Aircraft"):
            if a in EXCLUDED_RA:
                add("openra:" + a, "openra", "unit", r.get("name", a), "excluded", EXCLUDED_RA[a], art=art_level("openra." + a))
            elif a in have_units:
                add("openra:" + a, "openra", "unit", r.get("name", a), "functional", ent_id="unit:" + have_units[a], art=art_level("openra." + a))
            else:
                add("openra:" + a, "openra", "unit", r.get("name", a), "pending", "no recipe / mechanic", art=art_level("openra." + a))
    from wizard_rts.industry import blocks as B
    from wizard_rts.industry import units as U

    md = json.loads((DATA / "mindustry_defs.json").read_text())
    mkinds = {R_id(k): k for k in mdy.kinds()}
    for n, b in sorted(md["blocks"].items()):
        art = art_level("mindustry.block." + n.replace("-", "_"))
        kind = B.kind_of(n)
        sp = B.spec(kind)
        if sp is not None and sp["sandbox"]:
            add("mdy:" + n, "mindustry", b["class"], n, "excluded", "developer sandbox block (no requirements or sandbox class)", art=art)
        elif n in mkinds:
            add("mdy:" + n, "mindustry", b["class"], n, "functional", ent_id=mkinds[n], art=art, extra={"role": sp["role"] if sp else ""})
        else:
            add("mdy:" + n, "mindustry", b["class"], n, "pending", "class " + b["class"] + " not simulated", art=art)
    for n in U.unit_list():
        art = art_level("mindustry.unit." + n.replace("-", "_"))
        if n in U.CORE_UNITS:
            add("mdyu:" + n, "mindustry", "unit", n, "excluded", "core builder unit: spawned for the player by a core, not produced", art=art)
        elif ("unit:" + n) in ents:
            add("mdyu:" + n, "mindustry", "unit", n, "functional", ent_id="unit:" + n, art=art, extra={"tier": U.chains().get(n, 0)})
        else:
            add("mdyu:" + n, "mindustry", "unit", n, "pending", "no factory, reconstructor or assembler plan produces it", art=art)
    for n in sorted(U.INTERNAL):
        add("mdyu:" + n, "mindustry", "unit", n, "excluded", "internal entity (block unit or missile)", art="none")
    for n in sorted(md["items"]):
        add("mdyi:" + n, "mindustry", "item", n, "functional", ent_id="", art="none")
    for n in sorted(md["liquids"]):
        add("mdyl:" + n, "mindustry", "liquid", n, "functional", ent_id="", art="none")
    return rows


def R_id(kind: str) -> str:
    from wizard_rts.industry import registry as mdy

    sp = mdy.block(kind)
    return sp["id"] if sp and sp.get("id") else kind[4:].replace("_", "-")


def summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for r in rows:
        k = f"{r['game']} {r['type'] if r['game'] != 'mindustry' else ('block' if r['key'].startswith('mdy:') else r['type'])}"
        out.setdefault(k, {"functional": 0, "pending": 0, "excluded": 0})[r["status"]] += 1
    return out
