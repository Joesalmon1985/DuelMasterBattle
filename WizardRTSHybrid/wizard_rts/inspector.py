"""God Mode inspector queries (plan v2 8.6): the card catalogue, what each faction holds and has produced, and the draft state.

Everything is computed from the authoritative world; nothing here changes it. `art_status` reads the Godot art catalogue so a card
shows whether each entity it unlocks has real imported art, an alias placeholder, or none."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from wizard_rts import construction as con
from wizard_rts import draft, tech, vp

ART_CATALOGUE = Path(__file__).resolve().parents[2] / "godot_project" / "client" / "hybrid" / "art" / "catalogue.json"


@lru_cache(maxsize=1)
def _art() -> dict[str, dict[str, Any]]:
    try:
        return {i["id"]: i for i in json.loads(ART_CATALOGUE.read_text(encoding="utf-8"))["items"]}
    except OSError:
        return {}


def art_key(entity: str) -> str:
    """The art catalogue id that draws an entity (a building's definition, a unit recipe's definition)."""
    if entity.startswith("unit:"):
        kind = entity[5:]
        from wizard_rts.industry import registry as mdy

        if mdy.ground_unit(kind):
            return str(mdy.ground_unit(kind)["definition"])
        for recipes in con.RECIPES.values():
            if kind in recipes:
                return str(recipes[kind].get("definition", ""))
        return ""
    spec = con.build_spec(entity)
    return str(spec.get("definition", "")) if spec else ""


def art_status(entity: str) -> dict[str, Any]:
    key = art_key(entity)
    if key.startswith("mindustry.") and key.count(".") == 1:  # the art catalogue files Mindustry pictures under block. / unit.
        key = "mindustry.%s.%s" % ("unit" if entity.startswith("unit:") else "block", key.split(".", 1)[1].replace("-", "_"))
    item = _art().get(key)
    if item is None:
        return {"key": key, "status": "missing"}
    return {"key": key, "status": item.get("status", "imported"), "alias_of": item.get("alias_of", ""), "mode": item.get("mode", ""),
            "facings": item.get("facings", 1)}


def catalogue(world: Any) -> dict[str, Any]:
    from wizard_rts.content import graph

    ents = graph.entities()
    cards = []
    for cid, c in sorted(tech.pool(world).items(), key=lambda kv: (kv[1]["era"], kv[0])):
        cards.append({"id": cid, "name": c["name"], "era": tech.ERAS[c["era"]], "tribe": c.get("tribe", ""), "summary": c.get("summary", ""),
                      "entities": [{"id": e, "label": ents[e]["label"] if e in ents else e, "type": ents[e]["type"] if e in ents else "",
                                    "art": art_status(e)} for e in c.get("entities", [])]})
    missing = [e["id"] for c in cards for e in c["entities"] if e["art"]["status"] in ("missing", "alias_placeholder")]
    return {"cards": cards, "count": len(cards), "entities_without_real_art": sorted(set(missing))}


def factions(world: Any) -> dict[str, Any]:
    stats = world.__dict__.get("entity_stats", {})
    out = {}
    for f, st in world.tech.items():
        held = []
        for cid in st["cards"]:
            c = tech.lookup()[cid]
            ents = c.get("entities") or [*c.get("kinds", []), *("unit:" + u for u in c.get("units", [])), *c.get("wl_kinds", [])]
            held.append({"card": cid, "era": tech.ERAS[c["era"]],
                         "entities": [{"id": e, "produced": stats.get(f, {}).get(e, {}).get("count", 0), "first_ms": stats.get(f, {}).get(e, {}).get("first_ms")}
                                      for e in ents]})
        out[f] = {"cards": held, "unproduced": sorted(e["id"] for h in held for e in h["entities"] if not e["produced"])}
    return out


def draft_view(world: Any) -> dict[str, Any]:
    st = draft.state(world)
    totals = vp.totals(world)
    now = int(world.dmb.clock.get("game_ms", 0))
    would_award = {f: list(p) for f, p in st["packs"].items() if p and totals.get(f, 0) >= draft.LEFTOVER_VP}
    would_lose = {f: list(p) for f, p in st["packs"].items() if p and totals.get(f, 0) < draft.LEFTOVER_VP}
    era = vp.era_state(world)
    return {"enabled": draft.enabled(world), "era": tech.ERAS[max(0, st["era"])] if st["era"] >= 0 else "", "round": st["round"] + 1 if st["round"] < draft.ROUNDS else draft.ROUNDS,
            "rounds": draft.ROUNDS, "next_round_in_ms": max(0, st["open_ms"] + draft.ROUND_MS - now) if st["round"] < draft.ROUNDS else 0, "ring": list(st["ring"]),
            "packs": {f: list(p) for f, p in st["packs"].items()}, "chosen": dict(st["chosen"]), "bonus": {f: list(h) for f, h in st["bonus"].items()},
            "reserve": len(st["reserve"]), "vp": totals, "era_bar": int(era.get("bar", getattr(world, "era_vp_end", vp.ERA_VP_END))),
            "if_era_ended_now": {"awarded": would_award, "lost": would_lose, "leftover_vp": draft.LEFTOVER_VP},
            "default_picks": st["default_picks"], "duplicated_cards": st["duplicated_cards"]}


def catastrophe(world: Any) -> dict[str, Any]:
    from wizard_rts import regions

    s = regions.state(world)
    if s is None:
        return {"enabled": False}
    e = int(getattr(world, "era_index", 0))
    return {"enabled": True, "outbreaks_total": s.outbreaks, "total_limit": int(getattr(world, "loss_outbreaks_total", regions.const("loss_outbreaks"))),
            "outbreaks_this_era": s.era_outbreaks.get(e, 0), "era_limit": int(getattr(world, "loss_outbreaks_per_era", regions.config()["constants"].get("loss_outbreaks_per_era", regions.const("loss_outbreaks")))),
            "by_era": {tech.ERAS[k]: v for k, v in sorted(s.era_outbreaks.items())}, "lost": s.lost, "lost_by": s.lost_by,
            "cubes": {s.rid(i): c for i, c in enumerate(s.cubes) if c}}
