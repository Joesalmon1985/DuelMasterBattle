"""Developer fixture for the settlement story: a genuine Widelands mine whose deposit is used up (roadmap M3).

The fixture prepares what a long campaign would have reached: the mining cards (with prerequisites), a coal mine built through the
normal construction pipeline (delivered goods, a road, a ration), and then its reserve is drained so the real depletion rule fires
(`production_mine` sets `deposit_exhausted`). The story then opens by itself from that state: nothing about the quest, the miner or
the dungeon is placed by hand. Developer/test profiles only.
"""

from __future__ import annotations

from typing import Any

from wizard_rts import ai, construction as con, story, tech
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
    # the seam runs dry: drain the Widelands reserve in the mine's work area; the real depletion rule then flags the mine
    for (x, y, amount, _i) in world.terrain.cells(tile[0], tile[1], 2, "coal"):
        world.terrain.take(x, y, "coal", amount)
    for _s in range(max_seconds):
        seq += 1
        world.advance(1000, seq, snapshot=False)
        if story.state(world)["quests"]:
            break
    qid = next(iter(story.state(world)["quests"]), None)
    if qid is None:
        raise RuntimeError("no quest opened: the mine did not report exhaustion")
    q = story.state(world)["quests"][qid]
    return {"faction": faction, "mine": mine, "tile": list(tile), "quest": qid, "npc": q["npc"], "dungeon": q["dungeon"], "seq": seq}
