"""Developer fixture for the settlement story: a genuine Widelands mine whose gallery has caved in (roadmap M3, revised for D22).

The fixture prepares what a long campaign would have reached: the mining cards (with prerequisites), a coal mine built through the
normal construction pipeline (delivered goods, a road, a ration), lets it dig for real, and then brings its gallery down through the
same `disruption.disrupt` call a tremor, war damage or age uses (the natural chance is low, so a scenario cannot wait for it). The
story then opens by itself from that state: nothing about the quest, the miner or the dungeon is placed by hand. Developer/test only.
"""

from __future__ import annotations

from typing import Any

from wizard_rts import ai, construction as con, disruption, story, tech
from wizard_rts.industry import fixture as F


def prepare(world: Any, faction: str = "Red", max_seconds: int = 900) -> dict[str, Any]:
    if not tech.god_allowed(world):
        raise PermissionError("the story fixture is a developer/test command")
    for cid in ("dmb.card.mining", "dmb.card.smelting"):
        r = tech.grant(world, faction, cid)
        assert r["status"] == "ok", r
    wh = con.faction_warehouse(world, faction)
    seq = int(world.dmb.clock.get("clock_sequence", 0))
    tile = None
    for _try in range(10):
        tile = ai._mine_site(world, wh, "coal")
        if tile is None:
            raise RuntimeError("no coal site in territory")
        res = con.place_building(world, faction, "mine", tile[0], tile[1])
        if res["status"] == "ok" and con.build_road(world, faction, res["id"], wh["id"])["status"] == "ok":
            break
        if res["status"] == "ok":
            from wizard_rts.lifecycle import purge_building

            purge_building(world, res["id"], "site_cancelled")
        world.blocked.add(tile)  # try another site
        tile = None
    if tile is None:
        raise RuntimeError("could not place a connected coal mine")
    world.blocked.discard(tile)
    mine = res["id"]
    for _s in range(max_seconds):
        seq += 1
        world.advance(1000, seq, snapshot=False)
        if world.buildings[mine].get("operational"):
            break
    if not world.buildings[mine].get("operational"):
        raise RuntimeError("the mine was not built in time")
    for _s in range(max_seconds):  # let it dig for real first: the quest is about a working mine that stopped
        if world.buildings[mine].get("working_once"):
            break
        seq += 1
        world.advance(1000, seq, snapshot=False)
    world.disruptions_enabled = False  # no further random closures disturb the scenario; the one below is the scenario
    disruption.disrupt(world, world.buildings[mine], "collapse", by="tremor")
    for _s in range(max_seconds):
        seq += 1
        world.advance(1000, seq, snapshot=False)
        if story.state(world)["quests"]:
            break
    qid = next(iter(story.state(world)["quests"]), None)
    if qid is None:
        raise RuntimeError("no quest opened: the collapsed mine was not noticed")
    q = story.state(world)["quests"][qid]
    return {"faction": faction, "mine": mine, "tile": list(tile), "quest": qid, "npc": q["npc"], "dungeon": q["dungeon"], "seq": seq}
