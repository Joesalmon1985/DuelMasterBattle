"""Helpers for the player stress suite (`test_player_stress.py`): a recorder that writes what the world said and did to
`docs/evidence/stress/observations.json`, a conversation crawler, and the small moves a misbehaving player makes.

The suite plays the game badly on purpose through the real `MultiplayerSession` (tests/_party.py): it ignores quests, leaves at once,
spams people, burns the village, loses on purpose. Each test asserts only what must hold whatever the player does (no crash, the world
still answers, nobody is left without a line) and records the rest for `docs/PLAYER_STRESS_REPORT.md`."""
from __future__ import annotations

import atexit
import json
from pathlib import Path
from typing import Any

from _party import Table

from wizard_rts.narrative import campaign, ledger, mortality, mother, party, pests, residents, tutorial, wizard

OUT = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "stress" / "observations.json"
OBS: dict[str, Any] = {}


def record(test: str, **data: Any) -> None:
    OBS.setdefault(test, {}).update(data)


def _flush() -> None:
    if OBS:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(OBS, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


atexit.register(_flush)


# ------------------------------------------------------------------ reading the world

def game_min(t: Table) -> float:
    return round(int(t.world.dmb.clock.get("game_ms", 0)) / 60000.0, 1)


def stage(t: Table) -> str:
    return campaign.stage(t.world)


def notices(h, kind: str | None = None) -> list[dict]:
    ns = h.state()["notices"]
    return [n for n in ns if kind is None or n["kind"] == kind]


def said_by_ai(h) -> list[str]:
    return [str(n.get("line", "")) + ": " + str(n.get("text", ""))[:80] for n in notices(h, "ai_says")]


def text_of(reply: dict) -> str:
    return " ".join(list(reply.get("lines", [])) + ([reply["text"]] if reply.get("text") else []))


def choices_of(reply: dict) -> list[tuple[str, str, bool]]:
    return [(c["id"], c.get("text", ""), bool(c.get("available", True))) for c in reply.get("choices", [])]


def ledger_counts(t: Table, seat: str | None = None) -> dict[str, int]:
    st = ledger.state(t.world)
    src = st["world"] if seat is None else st["seats"].get(str(seat), {})
    return {k: int(v) for k, v in sorted(src.items()) if v}


def keeper_facts(t: Table) -> dict:
    inf = pests.live(t.world) or (pests.latest(t.world, pests.home(t.world)[0]) if pests.home(t.world) else None)
    return pests.facts(t.world, inf["keeper"]) if inf else {}


def food_left(t: Table) -> int:
    found = pests.home(t.world)
    if found is None:
        return -1
    _sid, b = found
    return sum(int(t.world.stocks.get(b["id"], {}).get(g, 0)) for g in pests.FOOD)


# ------------------------------------------------------------------ moving and talking

def stand_by_person(t: Table, h, key: str) -> None:
    """Beside a resident (mentor, mother, keeper, official) or a worker / carrier / unit by id."""
    res = residents.table(t.world).get(key)
    if res is not None:
        tile = res["tile"]
    else:
        for table in (t.world.workers, t.world.carriers, t.world.units):
            if key in table:
                tile = (table[key]["tx"], table[key]["ty"])
                break
        else:
            raise KeyError(key)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1)):
        tile2 = (int(tile[0]) + dx, int(tile[1]) + dy)
        if tile2 not in t.world.blocked and t.world.tile_in_map(*tile2):
            h.pose["tx"], h.pose["ty"] = tile2
            return
    h.pose["tx"], h.pose["ty"] = int(tile[0]) + 1, int(tile[1])


def ask(t: Table, h, key: str) -> dict:
    """Walk up and talk; the reply as the client sees it (status may be rejected: that is an observation too)."""
    stand_by_person(t, h, key)
    return h.op("talk", npc=key)


def talk_and_leave(t: Table, h, key: str) -> dict:
    r = ask(t, h, key)
    h.op("end_talk", npc=key)
    return r


def mentor(t: Table) -> str:
    return tutorial.state(t.world)["teacher"]


def mum(t: Table, h) -> str | None:
    return mother.pid_of(t.world, h.id)


def keeper(t: Table) -> str:
    inf = pests.live(t.world) or pests.latest(t.world, pests.home(t.world)[0])
    return inf["keeper"]


def official(t: Table) -> str:
    from wizard_rts.trial import run as trial

    return trial.state(t.world)["official"]


def crawl(t: Table, h, key: str, cap: int = 40) -> dict:
    """Press every button a conversation offers, depth first, re-opening it when it ends. Records every reply, every refused choice that was
    offered as available, every empty reply, and whether the crawl ran out of new choices (it should) or hit the cap."""
    seen_choices: set[str] = set()
    transcript: list[dict] = []
    defects: list[str] = []
    ops = 0
    r = ask(t, h, key)
    if r.get("status") != "ok":
        return {"opened": False, "reply": r}
    transcript.append({"talk": text_of(r)[:160], "choices": choices_of(r)})
    while ops < cap:
        ops += 1
        avail = [c for c in choices_of(r) if c[2] and c[0] not in seen_choices]
        if not avail:
            if r.get("ends") or not choices_of(r):
                r = ask(t, h, key)
                if r.get("status") != "ok":
                    defects.append(f"could not reopen: {r.get('reason')}")
                    break
                fresh = [c for c in choices_of(r) if c[2] and c[0] not in seen_choices]
                if not fresh:
                    h.op("end_talk", npc=key)
                    return {"opened": True, "exhausted": True, "ops": ops, "choices_tried": sorted(seen_choices), "transcript": transcript, "defects": defects}
                continue
            # every remaining choice already tried: close and reopen to see the hub again
            h.op("end_talk", npc=key)
            r = ask(t, h, key)
            if not [c for c in choices_of(r) if c[2] and c[0] not in seen_choices]:
                h.op("end_talk", npc=key)
                return {"opened": True, "exhausted": True, "ops": ops, "choices_tried": sorted(seen_choices), "transcript": transcript, "defects": defects}
            continue
        cid, ctext, _a = avail[0]
        seen_choices.add(cid)
        r2 = h.op("choose", npc=key, choice=cid)
        entry = {"choice": cid, "button": ctext[:60], "status": r2.get("status"), "reply": text_of(r2)[:160], "choices": choices_of(r2), "ends": r2.get("ends", False)}
        if r2.get("check"):
            entry["check"] = r2["check"]
        if "duel_lease" in r2:
            entry["duel"] = True
            rec = r2["duel_lease"]["payload"]["duel"]
            from test_wizard_duel_lease import play

            h.op("duel_resolve", duel_id=rec["id"], **play(rec, win=True))
            entry["duel_outcome"] = "won"
        transcript.append(entry)
        if r2.get("status") != "ok":
            defects.append(f"choice {cid} offered as available but refused: {r2.get('reason')}")
            r = ask(t, h, key)
            continue
        if not text_of(r2).strip() and not r2.get("ends"):
            defects.append(f"choice {cid} answered with nothing")
        r = r2
    h.op("end_talk", npc=key)
    return {"opened": True, "exhausted": False, "ops": ops, "choices_tried": sorted(seen_choices), "transcript": transcript, "defects": defects}


# ------------------------------------------------------------------ fire

def burn(t: Table, h, target: str) -> dict:
    """Stand beside the thing and burn it."""
    for table in (t.world.buildings, t.world.trees, t.world.rocks, t.world.workers, t.world.carriers, t.world.units, t.world.animals):
        row = table.get(target)
        if row is not None:
            h.pose["tx"], h.pose["ty"] = int(row["tx"]) + 1, int(row["ty"])
            break
    return h.op("fire", target=target)


def red_workers(t: Table, role: str | None = None) -> list[str]:
    return [i for i, r in sorted(t.world.workers.items()) if r["faction_name"] == "Red" and (role is None or r["role"] == role)]


def alive_people(t: Table, keys: list[str]) -> dict[str, bool]:
    return {k: bool(t.world.dmb.people.get(k, {}).get("alive", False)) for k in keys}


def dead(t: Table, h) -> bool:
    return mortality.is_dead(t.world, h.id)


def my_spells(t: Table, h) -> dict:
    with party.as_player(t.world, h.id):
        w = wizard.wiz(t.world)
        return {"spells": list(w["spells"]), "weave": int(w["weave_size"]), "lessons": sorted(w["lessons"])}
