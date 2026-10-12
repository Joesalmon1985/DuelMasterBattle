"""The spectator's view of the world: a plain-English feed of major events and a one-line overview per faction (P6 HUD).

Nothing here decides anything; it reads the event stream (EventLog.append calls `capture`) and the live state. The feed is a bounded
ring kept on the world, so a Godot client that joins late still sees the recent history.
"""

from __future__ import annotations

from collections import deque
from typing import Any

FEED_LEN = 40
KINDS = {
    "era_advanced", "card_drafted", "deployed", "settlement_destroyed", "vp_conquest", "faction_declined", "faction_recovered", "faction_split",
    "faction_collapsed", "outbreak", "outbreak_cube", "catastrophe_destroyed", "disrupted", "disruption_cleared", "treatment_done", "ai_attack",
    "ai_retreat", "caravan_traded", "nest_destroyed", "nest_cube_cleared", "cycle_due", "terminal_loss", "ai_industry_placed", "story_quest_offered", "draft_offer",
}
ERA_NAMES = {"prehistoric": "Prehistoric", "historic": "Historic", "modern": "Modern", "dystopian": "Dystopian Future"}


def _feed(world: Any) -> deque:
    f = world.__dict__.get("feed")
    if f is None:
        f = world.feed = deque(maxlen=FEED_LEN)
    return f


def _bkind(world: Any, bid: str) -> str:
    b = world.buildings.get(bid)
    return (b.get("label") or b.get("kind", "building")) if b else "a building"


def text(world: Any, e: dict) -> str | None:
    k = e.get("kind", "")
    f = e.get("faction", "")
    if k == "era_advanced":
        why = {"vp_threshold": "the world founded and conquered enough settlements", "stall_guard": "the era's time limit ran out"}.get(e.get("reason", ""), e.get("reason", ""))
        return "A new era: %s (%s)." % (ERA_NAMES.get(e.get("era", ""), e.get("era", "")), why)
    if k == "card_drafted":
        from wizard_rts import tech

        c = tech.cards().get(e.get("card", ""), {})
        return "%s drafted %s." % (f, c.get("name", e.get("card", "")))
    if k == "draft_offer":
        return None  # every four minutes for every faction: too frequent for the feed (the draft panel shows it)
    if k == "deployed":
        return "%s founded a new settlement." % f
    if k == "settlement_destroyed":
        return "A settlement of %s was destroyed (%s)." % (e.get("faction", ""), e.get("cause", ""))
    if k == "vp_conquest":
        return ("%s razed a settlement of %s (+1 VP)." % (e.get("winner"), e.get("owner"))) if e.get("winner") else None
    if k == "faction_declined":
        return "%s is in decline (%s)." % (f, str(e.get("why", "")).replace("_", " "))
    if k == "faction_recovered":
        return "%s has recovered." % f
    if k == "faction_split":
        return "%s split: %s broke away." % (f, e.get("successor", ""))
    if k == "faction_collapsed":
        return "%s collapsed and left only ruins." % f
    if k == "outbreak":
        return "Outbreak! %s overflowed in %s." % (str(e.get("hazard", "")).replace("_", " ").capitalize(), e.get("region", ""))
    if k == "outbreak_cube":
        return "%s spreads in %s (%d marks)." % (str(e.get("hazard", "")).replace("_", " ").capitalize(), e.get("region", ""), int(e.get("cubes", 0)))
    if k == "catastrophe_destroyed":
        return "The %s burned down a %s of %s." % (str(e.get("hazard", "")).replace("_", " "), str(e.get("building_kind", "")).replace("wl:", ""), f)
    if k == "disrupted":
        return "%s: %s at a %s." % (f, e.get("label", "closure"), str(e.get("building_kind", "")).replace("wl:", ""))
    if k == "disruption_cleared":
        return "%s reopened a workplace (%s)." % (f, e.get("how", ""))
    if k == "treatment_done":
        return "The wizard treated %s (%d marks left)." % (e.get("region", ""), int(e.get("cubes", 0)))
    if k == "ai_attack":
        return "%s attacks %s's %s with %d units." % (f, e.get("of", ""), str(e.get("target_kind", "")).replace("wl:", ""), int(e.get("units", 0)))
    if k == "ai_retreat":
        return "%s's attack failed: %d of %d units fall back." % (f, int(e.get("left", 0)), int(e.get("launched", 0)))
    if k == "caravan_traded":
        return "%s traded %s with %s for %s." % (f, ", ".join("%d %s" % (n, g) for g, n in e.get("give", {}).items()), e.get("partner", ""),
                                                 ", ".join("%d %s" % (n, g) for g, n in e.get("want", {}).items()))
    if k == "nest_cube_cleared":
        return "%s cut a blight nest back in %s (-%d)." % (e.get("by") or "Someone", e.get("region", ""), int(e.get("cubes", 0)))
    if k == "nest_destroyed":
        return "A blight nest was destroyed in %s: the region is clean." % e.get("region", "")
    if k == "cycle_due":
        return "The historical cycle is over."
    if k == "terminal_loss":
        return "Eight outbreaks: the world is lost."
    if k == "ai_industry_placed":
        return "%s laid out its first machine line." % f
    if k == "story_quest_offered":
        return "Someone in %s needs the wizard." % e.get("settlement", "a settlement")
    return None


def capture(world: Any, e: dict) -> None:
    if e.get("kind") not in KINDS:
        return
    t = text(world, e)
    if t:
        _feed(world).append({"game_ms": int(world.dmb.clock.get("game_ms", 0)), "kind": e["kind"], "faction": e.get("faction", ""), "text": t})


def overview(world: Any) -> list[dict[str, Any]]:
    """One row per faction for the spectator table (counts from one pass over buildings and units)."""
    from wizard_rts import ai, history, territory, vp

    food_g = ("ration", "bread", "meat", "fish", "smoked_fish", "smoked_meat")
    rows: dict[str, dict[str, Any]] = {}
    hist = history.state(world)["faction"]
    for name, info in world.faction_info.items():
        rows[name] = {"name": name, "color": info.get("color", "#ffffff"), "tribe": info.get("tribe", ""), "parent": info.get("parent", ""),
                      "policy": ai.policy_of(world, name), "state": hist.get(name, {}).get("state", "active"), "vp": vp.faction_vp(world, name),
                      "settlements": 0, "buildings": 0, "sites": 0, "closed": 0, "army": 0, "food": 0, "iron": 0, "unrest": 0.0,
                      "cards": len(world.tech.get(name, {}).get("cards", [])), "controlled": name == world.controlled_faction}
    for b in world.buildings.values():
        r = rows.get(b["faction_name"])
        if r is None or "hp" not in b or int(b["hp"]) <= 0:
            continue
        r["buildings"] += 1
        r["sites"] += 1 if b.get("constructing") else 0
        r["closed"] += 1 if b.get("disrupted") else 0
        if b.get("command_center"):
            r["settlements"] += 1
            st = world.stocks.get(b["id"], {})
            r["food"] += sum(int(st.get(g, 0)) for g in food_g)
            r["iron"] += int(st.get("iron", 0))
    for u in world.units.values():
        r = rows.get(u["faction_name"])
        if r is not None and u.get("alive", True) and u.get("weapon"):
            r["army"] += 1
    for rec in world.dmb.settlements.values():
        r = rows.get(rec["faction"])
        if r is not None and rec["state"] == "standing":
            r["unrest"] = round(max(r["unrest"], float(rec.get("unrest", 0.0))), 2)
    return list(rows.values())


def snapshot(world: Any) -> list[dict[str, Any]]:
    return list(_feed(world))
