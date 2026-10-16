"""The wizard's first live-settlement story (roadmap M3): a real shortage, a person, a dungeon, a puzzle, a duel, a real consequence.

Everything here is bound to the one HybridWorld:
- The *cause* is a state condition: a working mine whose gallery has caved in (`disruption.py`, cause `collapse`), so it stops and the
  workplaces that need its ware stall. (Until 12 Oct 2026 it was an exhausted vein; D22 made mineral sites inexhaustible.) Causes, quest binding and quest states reuse the legacy `sim/dmb/quests` (CauseTracker, QuestBinder, QuestService) on
  `world.dmb`; people reuse `PeopleService`; dialogue checks reuse `AspectService`; the duel is the Python-owned `MastermindDuel`; the
  dungeon is the Python port of the game's puzzle code (`wizard_rts/puzzle`, parity-tested against the GDScript).
- The *person* is a real Person record bound to the mine (workplace id), standing at a real tile beside it.
- The *consequence* is a typed effect applied once with a receipt: it reopens the collapsed gallery (`reopen_gallery`), so the mine
  produces again and the starved smelter resumes. The faction can also dig itself out (timber props delivered, then a long repair). Destroying the mine mid-quest fails the quest
  with a consequence; the AI repairing the shortage first resolves it by the world. Nothing mutates the world from free text.
- The wizard's actions are narrow (talk, choose, enter, move, interact, guess, leave); they work through `world.player` position and
  never command a faction (D02). Time keeps running while the wizard is underground; a duel freezes `game_ms` with a pause token.
"""

from __future__ import annotations

import json
import random
import zlib
from pathlib import Path
from typing import Any

from sim.dmb.adventure.mastermind import MastermindDuel
from sim.dmb.narrative.aspects import AspectService
from sim.dmb.people.registry import PeopleService
from sim.dmb.quests.binding import QuestBinder
from sim.dmb.quests.causes import CauseTracker
from sim.dmb.quests.runtime import QuestService
from sim.dmb.time.clock import ClockService

from wizard_rts import disruption, narrative, settlements
from wizard_rts.puzzle import gen as puzzle_gen
from wizard_rts.puzzle import items as puzzle_items
from wizard_rts.puzzle.dungeon import ENTRY, DungeonRun

TEMPLATE = Path(__file__).resolve().parent / "data" / "story" / "quest.shortage.gallery_collapse.json"
TEMPLATE_ID = "quest.shortage.gallery_collapse"
OPEN = ("offered", "active", "suspended")
TALK_RANGE = 3  # tiles (Manhattan): the wizard has to be standing close
ENTER_RANGE = 2
MAX_OPEN_QUESTS = 4
CHECK_EVERY = 10  # economy quanta (one game second)
SIGIL_WORDS = ["ash", "vale", "ember", "tarn", "flint", "moss", "brine", "cinder"]
MINE_RESOURCE = {"mine": "coal", "ironmine": "iron"}


def _tun() -> dict[str, Any]:
    return json.loads(TEMPLATE.read_text())["tunables"]


def state(world: Any) -> dict[str, Any]:
    s = world.__dict__.get("story")
    if s is None:
        s = world.story = {"version": 1, "npcs": {}, "dungeons": {}, "quests": {}, "inventory": [], "in_dungeon": "", "duel": None,
                           "known": [], "log": []}
    return s


OUTBREAK_TEMPLATE = TEMPLATE.with_name("quest.catastrophe.outbreak_treatment.json")
OUTBREAK_TEMPLATE_ID = "quest.catastrophe.outbreak_treatment"


def _binder(world: Any) -> QuestBinder:
    b = QuestBinder(world.dmb)
    have = world.dmb.definitions.get("quest_templates", {})
    for tid, path in ((TEMPLATE_ID, TEMPLATE), (OUTBREAK_TEMPLATE_ID, OUTBREAK_TEMPLATE)):
        if tid not in have:
            b.register_template(json.loads(path.read_text()))
    return b


def _log(world: Any, kind: str, **kw: Any) -> None:
    ev = {"kind": kind, **kw}
    state(world)["log"].append({"game_ms": int(world.dmb.clock.get("game_ms", 0)), **ev})
    if len(state(world)["log"]) > 400:
        del state(world)["log"][:200]
    world.events.append(ev)


# ------------------------------------------------------------------ detection and binding

def _deposit_kind(world: Any, b: dict) -> str:
    if b["kind"] in MINE_RESOURCE:
        return MINE_RESOURCE[b["kind"]]
    if b["kind"].startswith("wl:"):
        from wizard_rts import wl_defs

        spec = wl_defs.building_spec(b["kind"][3:])
        for prog in (spec or {}).get("programs", {}).values():
            for cmd, args in prog:
                if cmd == "mine":
                    return str(args["resource"])
    if b["kind"].startswith("mdy:") and world.terrain is not None:
        from wizard_rts.industry import sim as S
        from wizard_rts import terrain as T

        counts: dict[str, int] = {}
        for (x, y) in S.footprint(b):
            code = world.terrain.res_kind[y * world.terrain.w + x]
            if code:
                counts[T.RES_NAMES[code]] = counts.get(T.RES_NAMES[code], 0) + 1
        if counts:
            return sorted(counts, key=lambda k: (-counts[k], k))[0]
    return ""


def _exhausted(world: Any, b: dict) -> bool:
    """The mine is shut by a real collapse (the name is kept for the callers; nothing is exhausted since D22)."""
    if b.get("constructing") or int(b.get("hp", 1)) <= 0 or b.get("destroyed"):
        return False
    d = b.get("disrupted")
    return bool(d and d.get("cause") == "collapse")


def _open_quest_for(world: Any, mine_id: str) -> str | None:
    s = state(world)
    for qid, q in sorted(s["quests"].items()):
        if q["mine"] == mine_id and world.dmb.quests.get(qid, {}).get("status") in OPEN:
            return qid
    return None


def _free_tile_near(world: Any, b: dict, radius: int, avoid: set[tuple[int, int]]) -> tuple[int, int] | None:
    fp = {(b["tx"], b["ty"])} | {(int(p[0]), int(p[1])) for p in b.get("ground_footprint", [])}
    cx, cy = b["tx"], b["ty"]
    best = None
    occupied = {(u["tx"], u["ty"]) for u in world.units.values() if u.get("alive", True)}
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            t = (cx + dx, cy + dy)
            if t in fp or t in avoid or t in occupied or t in world.blocked or t in world.tree_tiles or t in world.road_tile_set:
                continue
            if not world.tile_in_map(*t) or (world.terrain is not None and not world.terrain.ground(*t)):
                continue
            key = (abs(dx) + abs(dy), t[1], t[0])
            if best is None or key < best[0]:
                best = (key, t)
    return best[1] if best else None


def _taken_tiles(world: Any) -> set[tuple[int, int]]:
    s = state(world)
    out = {tuple(n["tile"]) for n in s["npcs"].values()}
    out |= {tuple(d["entrance"]["tile"]) for d in s["dungeons"].values()}
    if "narrative" in world.__dict__:
        out |= {tuple(r["tile"]) for r in world.narrative["residents"].values()}
    return out


def _ensure_npc(world: Any, b: dict, sid: str | None) -> str:
    s = state(world)
    for pid, n in sorted(s["npcs"].items()):
        if n["building"] == b["id"]:
            return pid
    tile = _free_tile_near(world, b, 3, _taken_tiles(world)) or (b["tx"], b["ty"])
    rec = settlements.record(world, sid) if sid else None
    label = rec["name"] if rec else b["faction_name"]
    person = PeopleService(world.dmb).create_person(
        name=f"Miner of {label}", role="worker", workplace_id=b["id"], affiliation=b["faction_name"], area_id="hybrid.world",
        position=[tile[0], tile[1]], dialogue_profile="dialogue.anchor", anchor=True, profile_flags=["worker"])
    s["npcs"][person["id"]] = {"building": b["id"], "tile": [tile[0], tile[1]], "role": "miner", "settlement": sid or "", "faction": b["faction_name"]}
    return person["id"]


def _ensure_dungeon(world: Any, b: dict, sid: str | None, npc_id: str) -> str:
    s = state(world)
    did = f"cave:{b['id']}"
    if did in s["dungeons"]:
        return did
    seed = zlib.crc32(f"{world.seed}:{b['id']}".encode()) & 0x7FFFFFFF
    word = SIGIL_WORDS[seed % len(SIGIL_WORDS)]
    d = {"id": did.replace(":", "_"), "kind": "cave", "faction": b["faction_name"], "settlement": sid or "", "seed": seed, "index": len(s["dungeons"]),
         "provides": f"sigil_gallery_{len(s['dungeons']) + 1}", "needs": {"item": f"sigil_{word}", "from": "settlement"}, "reward": {}}
    d["puzzles"] = puzzle_gen.generate(d)
    tile = _free_tile_near(world, b, 5, _taken_tiles(world) | {(b["tx"] + 1, b["ty"] + 1)}) or (b["tx"], b["ty"])
    s["dungeons"][did] = {"record": d, "entrance": {"tile": [tile[0], tile[1]], "building": b["id"], "settlement": sid or ""}, "run": None,
                          "npc": npc_id, "solved_ms": None, "visits": 0}
    return did


def _open_quest(world: Any, b: dict) -> str | None:
    s = state(world)
    if sum(1 for qid in s["quests"] if world.dmb.quests.get(qid, {}).get("status") in OPEN) >= MAX_OPEN_QUESTS:
        return None
    sid = settlements.of(world, b)
    resource = _deposit_kind(world, b)
    npc = _ensure_npc(world, b, sid)
    did = _ensure_dungeon(world, b, sid, npc)
    cause = CauseTracker(world.dmb).observe_changes([{"kind": "gallery_collapse", "affected_entity_id": b["id"], "stakeholder_id": npc,
                                                    "site_id": sid, "template_id": TEMPLATE_ID, "resource": resource}])
    if not cause or cause[0].get("status") == "deduped":
        return None
    out = _binder(world).bind(TEMPLATE_ID, cause[0]["cause"])
    if out["status"] != "bound":
        return None
    qid = out["quest"]["id"]
    s["quests"][qid] = {"mine": b["id"], "npc": npc, "dungeon": did, "resource": resource, "settlement": sid or "", "faction": b["faction_name"],
                        "stage": "offered", "evidence": 0, "learned": [], "sigil_given": False, "persuaded": False, "outcome": "",
                        "opened_ms": int(world.dmb.clock.get("game_ms", 0)), "duel": {"attempts": 0, "result": ""}}
    _log(world, "story_quest_offered", quest=qid, mine=b["id"], npc=npc, settlement=sid or "", resource=resource)
    return qid


def story_quantum(world: Any) -> None:
    """Once a game second: open quests for real shortages and close them when the world changed under them."""
    if world.economy_quanta % CHECK_EVERY:
        return
    s = state(world)
    for bid, b in sorted(world.buildings.items()):
        if disruption.is_mine(b) and _exhausted(world, b) and _open_quest_for(world, bid) is None:
            if not any(q["mine"] == bid and world.dmb.quests.get(qid, {}).get("status") in ("completed", "failed_with_consequence")
                       and q["outcome"] in ("abandoned",) for qid, q in s["quests"].items()):
                _open_quest(world, b)
    _outbreak_quantum(world)
    svc = QuestService(world.dmb)
    for qid, q in sorted(s["quests"].items()):
        quest = world.dmb.quests.get(qid)
        if quest is None or quest["status"] not in OPEN or q.get("family") == "outbreak":
            continue
        mine = world.buildings.get(q["mine"])
        if mine is None or mine.get("destroyed") or int(mine.get("hp", 1)) <= 0:
            res = svc.evaluate(qid, world_signals={"target_destroyed": True})
            q["outcome"] = "destroyed_mine"
            _displace(world, q)
            _log(world, "story_quest_failed", quest=qid, why="mine_destroyed", status=res["status"])
            _release_duel(world, q)
            continue
        if not _exhausted(world, mine) and not q.get("effect_pending"):
            CauseTracker(world.dmb).resolve(quest["cause_id"], reason="world_fix")
            svc.evaluate(qid, world_signals={"world_repaired": True})
            q["outcome"] = "resolved_by_world"
            _log(world, "story_quest_resolved_by_world", quest=qid, mine=q["mine"])
            _release_duel(world, q)
    if "narrative" in world.__dict__:  # Wizard Mode only: server.py creates world.narrative; HybridEnv and training worlds never have it
        narrative.tick(world)


def _outbreak_quantum(world: Any) -> None:
    """Outbreak family: a healer and a quest for every standing settlement whose hex region holds two or more cubes."""
    from wizard_rts import regions

    s = state(world)
    rg = regions.state(world)
    if rg is None:
        return
    svc = QuestService(world.dmb)
    open_regions = {q["region"] for qid, q in s["quests"].items() if q.get("family") == "outbreak" and world.dmb.quests.get(qid, {}).get("status") in OPEN}
    if sum(1 for qid in s["quests"] if world.dmb.quests.get(qid, {}).get("status") in OPEN) < MAX_OPEN_QUESTS:
        for rec in sorted(settlements.standing(world), key=lambda r: r["id"]):
            i = rg.region_at(rec["tile"][0], rec["tile"][1])
            rid = rg.rid(i)
            if rg.cubes[i] >= 2 and rid not in open_regions and not any(q.get("family") == "outbreak" and q["region"] == rid and q["settlement"] == rec["id"]
                                                                      and world.dmb.quests[qid]["status"] != "resolved_by_world" and q["outcome"] == "abandoned" for qid, q in s["quests"].items()):
                centre = world.buildings.get(rec["centre"])
                if centre is None:
                    continue
                tile = _free_tile_near(world, centre, 4, _taken_tiles(world)) or (centre["tx"], centre["ty"])
                person = PeopleService(world.dmb).create_person(name=f"Healer of {rec['name']}", role="worker", workplace_id=centre["id"], affiliation=rec["faction"],
                                                                 area_id="hybrid.world", position=[tile[0], tile[1]], dialogue_profile="dialogue.anchor", anchor=True, profile_flags=["worker"])
                s["npcs"][person["id"]] = {"building": centre["id"], "tile": [tile[0], tile[1]], "role": "healer", "settlement": rec["id"], "faction": rec["faction"]}
                cause = CauseTracker(world.dmb).observe_changes([{"kind": "outbreak", "affected_entity_id": rid, "stakeholder_id": person["id"], "site_id": rec["id"],
                                                                "template_id": OUTBREAK_TEMPLATE_ID}])
                if not cause or cause[0].get("status") == "deduped":
                    continue
                out = _binder(world).bind(OUTBREAK_TEMPLATE_ID, cause[0]["cause"])
                if out["status"] != "bound":
                    continue
                qid = out["quest"]["id"]
                s["quests"][qid] = {"family": "outbreak", "region": rid, "mine": "", "npc": person["id"], "dungeon": "", "resource": "", "settlement": rec["id"],
                                    "faction": rec["faction"], "stage": "offered", "evidence": 0, "learned": [], "sigil_given": False, "persuaded": False, "outcome": "",
                                    "opened_ms": int(world.dmb.clock.get("game_ms", 0)), "duel": {"attempts": 0, "result": ""}, "start_cubes": rg.cubes[i]}
                open_regions.add(rid)
                _log(world, "story_quest_offered", quest=qid, region=rid, npc=person["id"], settlement=rec["id"], family="outbreak")
    for qid, q in sorted(s["quests"].items()):
        quest = world.dmb.quests.get(qid)
        if q.get("family") != "outbreak" or quest is None or quest["status"] not in OPEN:
            continue
        rec = settlements.record(world, q["settlement"])
        i = rg.index[tuple(int(x) for x in q["region"].split(":")[1].split(","))]
        if rec is None or rec["state"] != "standing":
            svc.evaluate(qid, world_signals={"site_destroyed": True})
            q["outcome"] = "destroyed_settlement"
            _log(world, "story_quest_failed", quest=qid, why="settlement_destroyed")
        elif rg.cubes[i] == 0:
            if q.get("treated_by_wizard"):
                if quest["status"] == "offered":
                    svc.accept(qid)
                svc.evaluate(qid, world_signals={"output_confirmed": True, "intervention": "treated"})
                CauseTracker(world.dmb).resolve(quest["cause_id"], reason="treated")
                q["outcome"] = "treated"
                q["stage"] = "resolution"
            else:
                CauseTracker(world.dmb).resolve(quest["cause_id"], reason="world_fix")
                svc.evaluate(qid, world_signals={"world_repaired": True})
                q["outcome"] = "resolved_by_world"
            _log(world, "story_quest_closed", quest=qid, outcome=q["outcome"])


def _displace(world: Any, q: dict) -> None:
    pid = q["npc"]
    if pid in world.dmb.people and world.dmb.people[pid].get("alive", True):
        PeopleService(world.dmb).displace(pid, reason="building_destroyed")


def _release_duel(world: Any, q: dict) -> None:
    s = state(world)
    duel = s.get("duel")
    if duel and duel["quest"] in [k for k, v in s["quests"].items() if v is q]:
        _end_duel(world, duel, "abandoned")


# ------------------------------------------------------------------ the wizard

def _wiz(world: Any) -> tuple[int, int]:
    return int(world.player["tx"]), int(world.player["ty"])


def _near(world: Any, tile: list[int] | tuple[int, int], rng: int) -> bool:
    x, y = _wiz(world)
    return abs(x - int(tile[0])) + abs(y - int(tile[1])) <= rng


def facts(world: Any, q: dict) -> dict[str, Any]:
    """What the miner can truthfully say, computed from the live world (never from the quest text)."""
    mine = world.buildings.get(q["mine"])
    out: dict[str, Any] = {"mine_exists": mine is not None, "resource": q["resource"], "settlement": settlements.record(world, q["settlement"]) and
                           settlements.record(world, q["settlement"])["name"] or q["faction"]}
    if mine is None:
        return out
    left = world.resource_total((mine["tx"], mine["ty"]), 2, q["resource"]) if q["resource"] and world.terrain is not None else 0
    wares = {"coal": "coal", "iron": "iron ore", "gold": "gold ore", "stones": "granite"}
    d = mine.get("disrupted") or {}
    have = world.stocks.get(mine["id"], {})
    props_need = sum(int(n) for n in d.get("repair", {}).values())
    props_have = sum(min(int(have.get(g, 0)), int(n)) for g, n in d.get("repair", {}).items())
    out.update(mine_label=mine["label"], deposit_left=left, exhausted=_exhausted(world, mine), ware=wares.get(q["resource"], q["resource"]),
               collapsed_by=d.get("by", ""), props_need=props_need, props_have=props_have,
               repair_pct=int(100 * int(d.get("progress_ms", 0)) / max(1, int(d.get("repair_ms", 1)))) if d else 100)
    wh = None
    for cc in sorted((x for x in world.buildings.values() if x["kind"] == "warehouse" and x["faction_name"] == mine["faction_name"]), key=lambda x: x["id"]):
        wh = cc if wh is None or settlements.of(world, mine) == cc.get("settlement_id") else wh
    out["stock"] = int(world.stocks.get(wh["id"], {}).get(q["resource"], 0)) if wh else 0
    starved = []
    for x in sorted(world.buildings.values(), key=lambda x: x["id"]):
        if x["faction_name"] == mine["faction_name"] and x.get("stall") and x["stall"].get("reason") == "inputs" and q["resource"] in str(x["stall"].get("detail", "")):
            starved.append(x["id"])
    out["starved"] = starved
    mins = max(0, (int(world.dmb.clock.get("game_ms", 0)) - q["opened_ms"]) // 60_000)
    out["minutes_since"] = mins
    return out


def _quest_of_npc(world: Any, npc_id: str) -> tuple[str, dict] | None:
    s = state(world)
    best = None
    for qid, q in sorted(s["quests"].items()):
        if q["npc"] == npc_id:
            status = world.dmb.quests[qid]["status"]
            if status in OPEN:
                return qid, q
            best = (qid, q)
    return best


def _outbreak_facts(world: Any, q: dict) -> dict[str, Any]:
    from wizard_rts import regions

    rg = regions.state(world)
    i = rg.index[tuple(int(x) for x in q["region"].split(":")[1].split(","))]
    k = next((x for x in regions.config()["kinds"] if x["id"] == rg.kind[i]), regions.config()["kinds"][0])
    rec = settlements.record(world, q["settlement"]) or {}
    sample = next((b for b in sorted(world.buildings.values(), key=lambda x: x["id"]) if b["faction_name"] == q["faction"] and "hp" in b
                   and rg.region_at(b["tx"], b["ty"]) == i and regions.production_factor(world, b) < 1.0), None)
    return {"cubes": rg.cubes[i], "label": k["label"], "clue": k["clue"], "factor": regions.production_factor(world, sample) if sample else 1.0,
            "unrest": round(float(rec.get("unrest", 0.0)), 2), "settlement": rec.get("name", q["faction"])}


def _lines(world: Any, qid: str, q: dict) -> list[str]:
    quest = world.dmb.quests[qid]
    if q.get("family") == "outbreak":
        f = _outbreak_facts(world, q)
        st = quest["status"]
        if st == "completed":
            return ["The %s is gone from the region. Work is back to full speed." % f["label"].lower()]
        if st == "resolved_by_world":
            return ["It passed on its own. I cannot say how."]
        if st == "failed_with_consequence":
            return ["You said you could not help. The %s stays." % f["label"].lower() if q["outcome"] == "abandoned" else "The settlement is gone."]
        lines = ["%s: %d %s in the region, and you can see it (%s)." % (f["settlement"], f["cubes"], "mark" if f["cubes"] == 1 else "marks", f["clue"])]
        if f["factor"] < 1.0:
            lines.append("Work in the affected workplaces runs at about %d%% of its normal pace. Unrest in the settlement: %.2f." % (round(f["factor"] * 100), f["unrest"]))
        return lines
    f = facts(world, q)
    status = quest["status"]
    lines: list[str] = []
    if status == "completed":
        if q["outcome"] == "full":
            lines.append("The old gallery runs round the fall. The carts are coming up again.")
        else:
            lines.append("You showed us the short way through. The crew finishes the dig-out in a few minutes.")
        if f.get("mine_exists"):
            lines.append("%s is %s; the warehouse has %d %s." % (f["mine_label"], "shut still" if f["exhausted"] else "working", f["stock"], f["ware"]))
    elif status == "resolved_by_world":
        lines.append("The trouble you asked about is already gone.")
    elif status == "failed_with_consequence":
        lines.append({"abandoned": "You said you could not help. We are still short, and I will remember it.",
                      "destroyed_mine": "There is no mine left to dig. Whatever you could have done, it is too late."}.get(q["outcome"], "Nothing more to say."))
    else:
        if not f.get("mine_exists"):
            return ["The mine is gone."]
        why = {"tremor": "The ground shook", "war_damage": "The fighting cracked the props", "age": "Old props gave way"}.get(f.get("collapsed_by", ""), "The roof came down")
        lines.append("%s: the gallery of %s caved in %d minutes ago. The seam is still there; we cannot reach it." % (why, f["mine_label"], f["minutes_since"]))
        lines.append("Timber props on site: %d of %d. Digging out: %d%%. That takes the crew a long while." % (f["props_have"], f["props_need"], f["repair_pct"]))
        lines.append("%d workplace%s here %s waiting on %s. The warehouse holds %d." % (
            len(f["starved"]), "" if len(f["starved"]) == 1 else "s", "is" if len(f["starved"]) == 1 else "are", f["ware"], f["stock"]))
        if "gallery" in q["learned"]:
            lines.append("The old gallery behind the spoil heap runs round the fall. The warden there keeps a code, and the stone answers only to the right sigil.")
        if q["sigil_given"]:
            lines.append("You have my mark. The first niche will take it and give it back.")
    return lines


def _choices(world: Any, qid: str, q: dict) -> list[dict[str, Any]]:
    status = world.dmb.quests[qid]["status"]
    out: list[dict[str, Any]] = []
    if status not in OPEN:
        return out
    if q.get("family") == "outbreak":
        return [{"id": "accept_treat", "text": "I will treat the region. Stand in it and hold still.", "available": status == "offered"},
                {"id": "give_up", "text": "I cannot help.", "available": True}]
    out.append({"id": "ask_cause", "text": "What happened to the mine?", "available": "cause" not in q["learned"]})
    out.append({"id": "ask_gallery", "text": "Is there another way in?", "available": "cause" in q["learned"] and "gallery" not in q["learned"]})
    out.append({"id": "accept_help", "text": "I will go down the old gallery.", "available": "gallery" in q["learned"] and not q["sigil_given"]})
    out.append({"id": "persuade", "text": "(Empathy) Tell me what the warden does.", "available": q["sigil_given"] and not q["persuaded"],
                "check": {"aspect": "empathy", "threshold": "easy"}})
    out.append({"id": "give_up", "text": "I cannot help.", "available": True})
    return out


def talk(world: Any, npc_id: str) -> dict[str, Any]:
    s = state(world)
    npc = s["npcs"].get(npc_id)
    if npc is None:
        if "narrative" in world.__dict__:  # anyone else: the teacher, or any worker, carrier or soldier (narrative/conversation.py owns the lifecycle)
            from wizard_rts.narrative import conversation

            return conversation.talk(world, npc_id)
        return {"status": "rejected", "reason": "no_such_person"}
    if not _near(world, npc["tile"], TALK_RANGE):
        return {"status": "rejected", "reason": "too_far"}
    person = world.dmb.people.get(npc_id, {})
    found = _quest_of_npc(world, npc_id)
    if found is None:
        return {"status": "ok", "npc": npc_id, "name": person.get("name", ""), "lines": ["They nod and keep working."], "choices": []}
    qid, q = found
    return {"status": "ok", "npc": npc_id, "name": person.get("name", ""), "quest": qid, "quest_status": world.dmb.quests[qid]["status"],
            "lines": _lines(world, qid, q), "choices": _choices(world, qid, q)}


def choose(world: Any, npc_id: str, choice: str) -> dict[str, Any]:
    s = state(world)
    if "narrative" in world.__dict__ and npc_id not in s["npcs"]:
        from wizard_rts.narrative import conversation

        return conversation.choose(world, npc_id, choice)
    res = talk(world, npc_id)
    if res["status"] != "ok" or "quest" not in res:
        return res
    qid = res["quest"]
    q = s["quests"][qid]
    quest = world.dmb.quests[qid]
    allowed = {c["id"]: c for c in res["choices"] if c["available"]}
    if choice not in allowed:
        return {"status": "rejected", "reason": "choice_unavailable", "choices": res["choices"]}
    svc = QuestService(world.dmb)
    people = PeopleService(world.dmb)
    text = ""
    if choice == "accept_treat":
        svc.accept(qid)
        q["stage"] = "treatment"
        text = "'Stand anywhere in the region and send the word `treat`. It takes a few seconds, and you must not leave.'"
        return {"status": "ok", "text": text, "lines": _lines(world, qid, q), "choices": _choices(world, qid, q)}
    if choice == "ask_cause":
        q["learned"].append("cause")
        q["evidence"] = min(2, q["evidence"] + 1)
        people.add_known_fact(npc_id, {"id": f"fact.cause.{qid}", "subject": q["mine"], "predicate": "collapsed", "value": True,
                                       "learned_time": int(world.dmb.clock.get("game_ms", 0))})
        text = "He points at the shaft mouth, choked with broken props and rubble. 'The seam is fine. We just cannot get to it.'"
        q["stage"] = "investigate"
    elif choice == "ask_gallery":
        q["learned"].append("gallery")
        text = "'My grandfather's crew broke through into an old gallery behind the spoil heap. It runs round the fall. The stone there answers to a sigil, and something keeps the way.'"
    elif choice == "accept_help":
        if len(s["inventory"]) >= puzzle_items.MAX_SLOTS:
            return {"status": "rejected", "reason": "inventory_full"}
        d = s["dungeons"][q["dungeon"]]["record"]
        s["inventory"].append(str(d["needs"]["item"]))
        q["sigil_given"] = True
        q["stage"] = "gallery"
        if quest["status"] == "offered":
            svc.accept(qid)
        text = "He presses a worn stone mark into your palm. 'Take it to the gallery mouth. Open the old way and we can work again.'"
        _log(world, "story_item_given", quest=qid, item=d["needs"]["item"])
    elif choice == "persuade":
        score = int(person_rel(world, npc_id))
        chk = AspectService(world.dmb).check("empathy", threshold="easy", evidence_mod=q["evidence"], relationship_score=score,
                                              quest_predicates={"quest": qid, "evidence": q["evidence"]})
        if chk["passed"]:
            q["persuaded"] = True
            people.set_relationship(npc_id, "player", min(100, score + 15))
            text = "He relents. 'The warden never hurries. Four colours in a row, six to choose from. Take your time, and it may give you two more tries.'"
        else:
            text = "He shrugs you off. 'You do not know what I know.'" + (" (blocked: nothing has changed since you last tried)" if chk.get("blocked") else "")
        return {"status": "ok", "text": text, "check": chk, "lines": _lines(world, qid, q), "choices": _choices(world, qid, q)}
    elif choice == "give_up":
        svc._transition(qid, "failed_with_consequence")  # the legacy runtime has no public abandon call
        quest["resolution"] = "abandoned"
        quest["branch"] = "abandoned"
        q["outcome"] = "abandoned"
        people.set_relationship(npc_id, "player", max(-100, person_rel(world, npc_id) - 20))
        people.append_history(npc_id, f"history.abandoned.{qid}")
        _log(world, "story_quest_failed", quest=qid, why="abandoned")
        text = "He says nothing. The shortage stays."
    return {"status": "ok", "text": text, "lines": _lines(world, qid, q), "choices": _choices(world, qid, q)}


def person_rel(world: Any, npc_id: str) -> int:
    return int(world.dmb.people[npc_id].get("relationship_map", {}).get("player", 0))


# ------------------------------------------------------------------ the dungeon

def _run_for(world: Any, did: str) -> DungeonRun:
    s = state(world)
    entry = s["dungeons"][did]
    run = DungeonRun(entry["record"], entry["run"], inventory=s["inventory"])
    entry["run"] = run.state
    return run


def enter(world: Any, did: str) -> dict[str, Any]:
    s = state(world)
    entry = s["dungeons"].get(did)
    if entry is None:
        return {"status": "rejected", "reason": "no_such_dungeon"}
    if s["in_dungeon"]:
        return {"status": "rejected", "reason": "already_inside"}
    if not _near(world, entry["entrance"]["tile"], ENTER_RANGE):
        return {"status": "rejected", "reason": "too_far"}
    if entry["entrance"]["building"] not in world.buildings:
        return {"status": "rejected", "reason": "entrance_gone"}
    run = _run_for(world, did)
    run.state["pos"] = list(ENTRY)  # every visit starts at the mouth; solved rooms stay solved
    run.state["out"] = False
    s["in_dungeon"] = did
    entry["visits"] += 1
    _log(world, "story_dungeon_entered", dungeon=did, visit=entry["visits"])
    return {"status": "ok", "dungeon": did, "view": dungeon_view(world)}


def dungeon_view(world: Any) -> dict[str, Any]:
    s = state(world)
    did = s["in_dungeon"]
    if not did:
        return {}
    view = _run_for(world, did).view()
    view["dungeon"] = did
    return view


def dungeon_move(world: Any, dx: int, dy: int) -> dict[str, Any]:
    s = state(world)
    if not s["in_dungeon"]:
        return {"status": "rejected", "reason": "not_inside"}
    if s["duel"]:
        return {"status": "rejected", "reason": "duel_open"}
    run = _run_for(world, s["in_dungeon"])
    res = run.move(int(dx), int(dy))
    if res.get("exit"):
        s["in_dungeon"] = ""
        run.state["out"] = False
        _log(world, "story_dungeon_left", dungeon=run.d["id"])
        res["left"] = True
    return res


def dungeon_interact(world: Any, entity: str, item: str | None = None, spell: int | None = None) -> dict[str, Any]:
    s = state(world)
    if not s["in_dungeon"]:
        return {"status": "rejected", "reason": "not_inside"}
    if s["duel"]:
        return {"status": "rejected", "reason": "duel_open"}
    run = _run_for(world, s["in_dungeon"])
    ent = next((e for e in run.area()["entities"] if e["id"] == entity), None)
    if ent is not None and "dungeon_reward" in ent and run.solved_all():
        qid = _quest_for_dungeon(world, s["in_dungeon"])
        if qid and world.dmb.quests[qid]["status"] in OPEN and not s["quests"][qid]["duel"]["result"]:
            return {"status": "duel_required", "text": "The plinth is held by the gallery warden. It wants its code broken."}
    return run.interact(entity, item=item, spell=spell)


def _quest_for_dungeon(world: Any, did: str) -> str | None:
    for qid, q in sorted(state(world)["quests"].items()):
        if q["dungeon"] == did and world.dmb.quests.get(qid, {}).get("status") in OPEN:
            return qid
    return None


# ------------------------------------------------------------------ the duel

def duel_begin(world: Any) -> dict[str, Any]:
    s = state(world)
    if not s["in_dungeon"]:
        return {"status": "rejected", "reason": "not_inside"}
    if s["duel"]:
        return {"status": "rejected", "reason": "duel_open", "public": MastermindDuel.public_view(s["duel"]["mm"])}
    run = _run_for(world, s["in_dungeon"])
    if not run.solved_all():
        return {"status": "rejected", "reason": "puzzles_unsolved"}
    qid = _quest_for_dungeon(world, s["in_dungeon"])
    if qid is None:
        return {"status": "rejected", "reason": "no_open_quest"}
    reward = next((e for e in run.area()["entities"] if "dungeon_reward" in e), None)
    if reward is None or not _in_dungeon_range(run, reward):
        return {"status": "rejected", "reason": "too_far"}
    q = s["quests"][qid]
    q["duel"]["attempts"] += 1
    seed = zlib.crc32(f"{world.seed}:{qid}:duel:{q['duel']['attempts']}".encode())
    mm: dict[str, Any] = {"id": f"duel:{qid}:{q['duel']['attempts']}", "cube_id": "", "hex_id": ""}
    MastermindDuel.attach(mm, rng=random.Random(seed))
    if q["persuaded"]:
        mm["mastermind"]["max_casts"] += int(_tun()["duel_extra_casts_with_evidence"])
    token = ClockService(world.dmb.clock).acquire_pause("story_duel", mm["id"])
    s["duel"] = {"quest": qid, "mm": mm, "token": token}
    _log(world, "story_duel_begun", quest=qid, attempt=q["duel"]["attempts"], max_casts=mm["mastermind"]["max_casts"])
    return {"status": "started", "public": MastermindDuel.public_view(mm)}


def _in_dungeon_range(run: DungeonRun, ent: dict) -> bool:
    x, y = run.state["pos"]
    return abs(x - ent["pos"][0]) + abs(y - ent["pos"][1]) <= 1


def duel_view(world: Any) -> dict[str, Any]:
    d = state(world)["duel"]
    return MastermindDuel.public_view(d["mm"]) if d else {}


def duel_guess(world: Any, guess: list[int]) -> dict[str, Any]:
    s = state(world)
    d = s["duel"]
    if d is None:
        return {"status": "rejected", "reason": "no_duel"}
    res = MastermindDuel.submit_guess(d["mm"], list(guess))
    if res["status"] in ("rejected", "already_resolved"):
        return res
    out = {"status": res["status"], "feedback": res.get("feedback"), "public": MastermindDuel.public_view(d["mm"])}
    if res["status"] == "solved":
        out["result"] = _end_duel(world, d, "full")
    elif res["status"] == "exhausted":
        out["result"] = _end_duel(world, d, "thin")
    return out


def duel_abandon(world: Any) -> dict[str, Any]:
    d = state(world)["duel"]
    if d is None:
        if "narrative" in world.__dict__:  # a story Ward lease (the lesson duels) is closed without counting
            from wizard_rts.narrative import duel_lease

            out = duel_lease.abandon(world)
            if out["closed"]:
                return out
        return {"status": "rejected", "reason": "no_duel"}
    return {"status": "ok", "result": _end_duel(world, d, "abandoned")}


def _end_duel(world: Any, d: dict, outcome: str) -> dict[str, Any]:
    s = state(world)
    qid = d["quest"]
    q = s["quests"].get(qid)
    try:
        ClockService(world.dmb.clock).release_pause(d["token"])
    except Exception:
        pass
    s["duel"] = None
    if q is None:
        return {"outcome": outcome}
    q["duel"]["result"] = outcome if outcome != "abandoned" else ""
    _log(world, "story_duel_ended", quest=qid, outcome=outcome)
    if outcome == "abandoned":
        return {"outcome": outcome, "quest_status": world.dmb.quests[qid]["status"]}
    q["effect_pending"] = True
    applied = apply_effects(world, qid, [{"kind": "reopen_gallery", "mode": "full" if outcome == "full" else "thin", "mine": q["mine"]},
                                         {"kind": "history_fact", "fact": f"gallery_reopened:{outcome}", "person": q["npc"]}], prefix=f"duel{q['duel']['attempts']}")
    q["effect_pending"] = False
    quest = world.dmb.quests[qid]
    if quest["status"] in OPEN:
        if quest["status"] == "offered":
            QuestService(world.dmb).accept(qid)
        QuestService(world.dmb).evaluate(qid, world_signals={"output_confirmed": True, "intervention": f"gallery_{outcome}"})
        CauseTracker(world.dmb).resolve(quest["cause_id"], reason="gallery_reopened")
    q["outcome"] = outcome
    q["stage"] = "resolution"
    s["dungeons"][q["dungeon"]]["solved_ms"] = int(world.dmb.clock.get("game_ms", 0))
    return {"outcome": outcome, "effects": applied, "quest_status": quest["status"]}


# ------------------------------------------------------------------ typed effects with receipts

ALLOWED_EFFECTS = ("reopen_gallery", "history_fact")


def apply_effects(world: Any, qid: str, effects: list[dict[str, Any]], prefix: str) -> dict[str, Any]:
    """Validate every effect, then apply each exactly once (receipts in world.dmb.command_receipts), atomically for the batch."""
    for i, e in enumerate(effects):
        if str(e.get("kind")) not in ALLOWED_EFFECTS:
            return {"status": "aborted", "reason": f"unknown_effect:{e.get('kind')}"}
        if e["kind"] == "reopen_gallery" and world.buildings.get(e["mine"]) is None:
            return {"status": "aborted", "reason": "gallery_target_missing"}
    done: list[dict[str, Any]] = []
    for i, e in enumerate(effects):
        eid = f"{qid}:{prefix}:{i}:{e['kind']}"
        if eid in world.dmb.command_receipts:
            done.append({"effect_id": eid, "status": "idempotent"})
            continue
        if e["kind"] == "reopen_gallery":
            result = _reopen_gallery(world, world.buildings[e["mine"]], str(e["mode"]))
        else:
            PeopleService(world.dmb).add_known_fact(str(e["person"]), {"id": f"fact.{eid}", "subject": qid, "predicate": "outcome", "value": str(e["fact"]),
                                                                       "learned_time": int(world.dmb.clock.get("game_ms", 0))})
            result = {"fact": e["fact"]}
        world.dmb.command_receipts[eid] = result
        world.dmb.quests[qid].setdefault("effect_receipts", []).append(eid)
        done.append({"effect_id": eid, "status": "applied", "result": result})
        world.events.append({"kind": "story_effect", "effect_id": eid, "result": result})
    return {"status": "ok", "applied": done}


def _reopen_gallery(world: Any, mine: dict, mode: str) -> dict[str, Any]:
    """The wizard's way round the fall. full: the collapse is cleared now and the props already carried in stay in the mine's stock
    (nothing is created; they simply are not used up). thin: the faction's own dig-out finishes `thin_repair_left_ms` after its props
    arrive. Either way the mine's programme runs again through the ordinary production loop, so the restored output is real."""
    d = mine.get("disrupted")
    if not d or d.get("cause") != "collapse":
        return {"reopened": False, "reason": "not_collapsed"}
    if mode == "full":
        disruption.clear(world, mine, "wizard")
        return {"reopened": True, "mode": mode}
    left = int(json.loads(TEMPLATE.read_text())["tunables"]["thin_repair_left_ms"])
    d["progress_ms"] = max(int(d["progress_ms"]), int(d["repair_ms"]) - left)
    return {"reopened": False, "mode": mode, "repair_left_ms": int(d["repair_ms"]) - int(d["progress_ms"])}


# ------------------------------------------------------------------ snapshot rows

FIGURES = {  # the Widelands worker sprite that stands for a story person (art in godot_project/client/hybrid/art/widelands/gen)
    "miner": {"barbarians": "barbarians_miner", "empire": "empire_miner", "atlanteans": "atlanteans_miner", "frisians": "frisians_miner", "amazons": "barbarians_miner"},
    "healer": {"barbarians": "barbarians_innkeeper", "empire": "empire_innkeeper", "atlanteans": "empire_innkeeper", "frisians": "barbarians_innkeeper", "amazons": "amazons_cook"},
}


def _figure(tribe: str, role: str) -> str:
    return "widelands.%s_worker" % FIGURES.get(role, FIGURES["miner"]).get(tribe, "barbarians_miner")


def entity_rows(world: Any) -> list[dict[str, Any]]:
    """NPCs and dungeon entrances as ordinary snapshot entities (what Godot draws and labels)."""
    s = world.__dict__.get("story")
    rows = []
    if "narrative" in world.__dict__:  # residents: the teacher and the villagers of the narrative layer; the Trial's gate
        from wizard_rts.narrative import residents, tutorial
        from wizard_rts.trial import run as trial

        rows.extend(residents.entity_rows(world, tutorial.row_info(world)))
        rows.extend(trial.entity_rows(world))
    if not s:
        return rows
    for pid, n in sorted(s["npcs"].items()):
        person = world.dmb.people.get(pid, {})
        found = _quest_of_npc(world, pid)
        tribe = world.faction_info.get(n["faction"], {}).get("tribe", "barbarians")
        rows.append({"id": pid, "class": "npc", "kind": "npc", "definition": "story.miner", "faction": "", "faction_name": n["faction"],
                     "label": person.get("name", "Miner"), "tx": n["tile"][0], "ty": n["tile"][1], "alive": bool(person.get("alive", True)),
                     "figure": _figure(tribe, n["role"]),
                     "role": n["role"], "quest_status": world.dmb.quests[found[0]]["status"] if found else "",
                     "has_quest": bool(found and world.dmb.quests[found[0]]["status"] in OPEN)})
    for did, d in sorted(s["dungeons"].items()):
        if d["entrance"]["building"] in world.buildings:
            t = d["entrance"]["tile"]
            rows.append({"id": f"entrance:{did}", "class": "landmark", "kind": "dungeon_entrance", "definition": "story.entrance", "faction": "",
                         "faction_name": "", "label": "Disused gallery", "tx": t[0], "ty": t[1], "alive": True, "dungeon": did,
                         "solved": d["solved_ms"] is not None})
    return rows


def snapshot(world: Any) -> dict[str, Any]:
    out = _story_snapshot(world)
    if "narrative" in world.__dict__:
        from wizard_rts.narrative import characters, events

        out["narrative"] = {"version": world.narrative["version"], "events": events.recent(world)}
        out["persons"] = characters.persons_view(world)
        from wizard_rts.narrative import tutorial

        out["narrative"]["journal"] = tutorial.snapshot(world)
    return out


def _story_snapshot(world: Any) -> dict[str, Any]:
    s = world.__dict__.get("story")
    if not s:
        return {}
    return {"quests": [{"id": qid, "status": world.dmb.quests[qid]["status"], "stage": q["stage"], "mine": q["mine"], "npc": q["npc"],
                        "outcome": q["outcome"], "settlement": q["settlement"]} for qid, q in sorted(s["quests"].items())],
            "inventory": list(s["inventory"]), "in_dungeon": s["in_dungeon"], "duel_open": bool(s["duel"]),
            "dungeons": {did: {"entrance": d["entrance"], "visits": d["visits"], "solved": d["solved_ms"] is not None} for did, d in sorted(s["dungeons"].items())}}


# ------------------------------------------------------------------ the wizard's command surface

WIZARD_OPS = ("treat", "talk", "choose", "enter", "dungeon_move", "dungeon_interact", "duel_begin", "duel_guess", "duel_abandon", "story_view",
              "duel_resolve", "duel_checkpoint", "end_talk", "opening_done", "journal", "call_out", "inspect_building", "inspect_person", "scene_next", "scene_choose",
              "resurrect", "pest_fight", "trial_enter", "trial_move", "trial_interact", "trial_choose", "trial_leave", "trial_view")


def dispatch(world: Any, message: dict[str, Any]) -> dict[str, Any]:
    """The only ways the wizard acts in the story. Faction control is not here (D02)."""
    op = str(message.get("op", ""))
    if op == "treat":
        from wizard_rts import regions

        out = regions.begin_treatment(world)
    elif op == "talk":
        out = talk(world, str(message.get("npc", "")))
    elif op == "choose":
        out = choose(world, str(message.get("npc", "")), str(message.get("choice", "")))
    elif op == "enter":
        out = enter(world, str(message.get("dungeon", "")))
    elif op == "dungeon_move":
        out = dungeon_move(world, int(message.get("dx", 0)), int(message.get("dy", 0)))
    elif op == "dungeon_interact":
        out = dungeon_interact(world, str(message.get("entity", "")), message.get("item"), message.get("spell"))
    elif op == "duel_begin":
        out = duel_begin(world)
    elif op == "duel_guess":
        out = duel_guess(world, list(message.get("guess", [])))
    elif op == "duel_abandon":
        out = duel_abandon(world)
    elif op in ("duel_resolve", "duel_checkpoint", "end_talk", "opening_done", "journal", "call_out", "inspect_building", "inspect_person", "scene_next", "scene_choose", "resurrect", "pest_fight") or op.startswith("trial_"):
        from wizard_rts.narrative import ops

        out = ops.handle(world, message)
    else:
        out = {"status": "ok"}
    if not op.startswith("trial_"):  # the Trial's ops carry their own `view` (the zone)
        out["view"] = dungeon_view(world) if state(world)["in_dungeon"] else {}
    out["duel"] = duel_view(world)
    return out
