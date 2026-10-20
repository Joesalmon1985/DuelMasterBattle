"""Who ordered the planks? Guess Who with the forgetful sawyer, over the village's real people. The board is up to sixteen villagers (residents,
workers and carriers near the sawmill, drawn with their own figures); each has traits read from the simulation (trade, tribe, whether they carry
something, whether they work indoors) and a few cosmetic ones seeded by their name (headwear, a beard, hair). You pick a person for the sawyer to
guess; the sawyer has the one who ordered the planks in mind. Turns alternate: ask a yes-or-no question about a trait, or name the person. A wrong
name loses. The sawyer asks the question that best halves what is left and names the person when one remains."""

from __future__ import annotations

import zlib
from typing import Any

from wizard_rts.minigames import base

TRAITS = ("trade", "tribe", "carrying", "indoors", "headwear", "beard", "hair")
NEAR = 30  # tiles (Manhattan) from the host: who counts as the village
LABELS = {"trade": "trade", "tribe": "tribe", "carrying": "carrying something", "indoors": "works indoors", "headwear": "headwear", "beard": "a beard", "hair": "hair"}
COSMETIC = {"headwear": ["a hat", "a hood", "bare-headed"], "beard": ["yes", "no"], "hair": ["dark", "fair", "red", "grey"]}


def _cosmetic(seed: int, pid: str, trait: str) -> str:
    opts = COSMETIC[trait]
    return opts[zlib.crc32(f"{seed}|{pid}|{trait}".encode()) % len(opts)]


def prepare(world: Any, sp: dict[str, Any], opts: dict[str, Any]) -> dict[str, Any]:
    """The village's people as faces: nearest first, the host left out."""
    from wizard_rts.narrative import characters, residents

    people: list[dict[str, Any]] = []
    hx, hy = sp["tile"]
    seen: set[str] = set()
    for pid, r in sorted(residents.table(world).items()):
        if r["status"] != "present" or r["role"] in ("pest", "body", "stranger") or pid == sp["pid"]:
            continue
        people.append({"id": pid, "name": world.dmb.people[pid]["name"], "figure": residents.figure(r), "tile": r["tile"], "trade": r["role"].replace("_", " "),
                       "tribe": r.get("tribe") or "none", "carrying": "no", "indoors": "no"})
        seen.add(pid)
    faction = str(sp["row"].get("faction_name", "")) if sp.get("row") else ""
    for kind, table in (("worker", world.workers), ("carrier", world.carriers)):
        for eid, row in sorted(table.items()):
            if faction and row.get("faction_name") != faction:
                continue
            if abs(int(row["tx"]) - hx) + abs(int(row["ty"]) - hy) > NEAR:
                continue  # the village's own people, not every worker of the world (a Person record is made for each face)
            pid = characters.person_for(world, kind, eid)
            if not pid or pid in seen or pid == sp["pid"]:
                continue
            seen.add(pid)
            tribe = str(world.faction_info.get(row.get("faction_name", ""), {}).get("tribe", "none"))
            role = str(row.get("role", kind))
            fig = f"widelands.{tribe}_{'carrier' if kind == 'carrier' else role}_worker"
            carrying = row.get("carrying") if kind == "worker" else (row.get("cargo") or {}).get("good")
            people.append({"id": pid, "name": world.dmb.people[pid]["name"], "figure": fig, "tile": [int(row["tx"]), int(row["ty"])], "trade": role,
                           "tribe": tribe, "carrying": "yes" if carrying else "no", "indoors": "yes" if characters.lifecycle(world, pid) == "inside" else "no"})
    people.sort(key=lambda p: (abs(int(p["tile"][0]) - hx) + abs(int(p["tile"][1]) - hy), p["id"]))
    faces = int(opts.get("faces", 16))
    chosen = people[:faces]
    seed = int(world.seed)
    for p in chosen:
        for t in ("headwear", "beard", "hair"):
            p[t] = _cosmetic(seed, p["id"], t)
        p.pop("tile", None)
    return {**opts, "people": chosen}


def _fallback_people(n: int) -> list[dict[str, Any]]:
    names = ["Arn", "Bela", "Cori", "Dag", "Eda", "Finn", "Gudrun", "Hal", "Ida", "Jor", "Kel", "Lis", "Mund", "Nia", "Orm", "Pia"]
    trades = ["lumberjack", "ranger", "stonemason", "hunter", "carrier", "farmer", "baker", "weaver"]
    out = []
    for i in range(n):
        pid = f"face:{i}"
        out.append({"id": pid, "name": names[i % len(names)], "figure": "", "trade": trades[i % len(trades)], "tribe": "barbarians" if i % 3 else "empire",
                    "carrying": "yes" if i % 2 else "no", "indoors": "yes" if i % 4 == 0 else "no", **{t: _cosmetic(7, pid, t) for t in ("headwear", "beard", "hair")}})
    return out


def new(seed: int, opts: dict[str, Any]) -> dict[str, Any]:
    people = list(opts.get("people") or [])
    if len(people) < 6:
        people = people + _fallback_people(16 - len(people))
    st = base.fresh("guesswho", seed, ["you", str(opts.get("host", "them"))], people=people, secret=None, theirs=None, alive=[True] * len(people),
                    their_alive=[True] * len(people), phase="pick", turn=0, asked=[], their_asked=[])
    st["theirs"] = base.rng(st, "theirs").randrange(len(people))
    base.say(st, "Think of somebody. I have the one who ordered in mind.")
    return st


def _questions(state: dict[str, Any], alive: list[bool]) -> list[tuple[str, str]]:
    out = []
    for t in TRAITS:
        values = sorted({str(p[t]) for p, a in zip(state["people"], alive) if a})
        if len(values) >= 2:
            for v in values:
                out.append((t, v))
    return out


def actions(state: dict[str, Any], seat: int) -> list[dict[str, Any]]:
    if state["over"] or seat != state["turn"]:
        return []
    if state["phase"] == "pick":
        return [{"id": f"pick:{i}", "face": i, "text": f"Think of {p['name']}", "hidden": True} for i, p in enumerate(state["people"])] if seat == 0 else []
    alive = state["alive"] if seat == 0 else state["their_alive"]
    asked = state["asked"] if seat == 0 else state["their_asked"]
    out = []
    for t, v in _questions(state, alive):
        if [t, v] in asked:
            continue
        text = {"carrying": "Are they carrying something?" if v == "yes" else "Are they empty-handed?", "indoors": "Do they work indoors?" if v == "yes" else "Do they work outside?",
                "beard": "Do they have a beard?" if v == "yes" else "Are they clean-shaven?"}.get(t, f"Is their {LABELS[t]} {v}?")
        if t == "headwear":
            text = f"Are they {v}?" if v == "bare-headed" else f"Do they wear {v}?"
        out.append({"id": f"ask:{t}:{v}", "trait": t, "value": v, "text": text})
    for i, p in enumerate(state["people"]):
        if alive[i]:
            out.append({"id": f"guess:{i}", "face": i, "text": f"It is {p['name']}", "hidden": True})
    return out


def bot(state: dict[str, Any], seat: int, rng: Any) -> dict[str, Any]:
    alive = state["their_alive"]
    left = [i for i, a in enumerate(alive) if a]
    if len(left) == 1:
        return {"id": f"guess:{left[0]}", "face": left[0]}
    best = None
    for t, v in _questions(state, alive):
        if [t, v] in state["their_asked"]:
            continue
        yes = sum(1 for i in left if str(state["people"][i][t]) == v)
        score = abs(yes - (len(left) - yes))
        if best is None or score < best[0]:
            best = (score, t, v)
    if best is None:
        return {"id": f"guess:{left[0]}", "face": left[0]}
    return {"id": f"ask:{best[1]}:{best[2]}", "trait": best[1], "value": best[2]}


def act(state: dict[str, Any], seat: int, action: dict[str, Any]) -> dict[str, Any]:
    a = base.find(actions(state, seat), action)
    state["moves"] += 1
    aid = a["id"]
    if aid.startswith("pick:"):
        state["secret"] = int(a["face"])
        state["phase"] = "ask"
        base.say(state, f"You think of {state['people'][state['secret']]['name']}. Ask away.")
        return state
    if aid.startswith("ask:"):
        t, v = a["trait"], a["value"]
        if seat == 0:
            answer = str(state["people"][state["theirs"]][t]) == v
            for i, p in enumerate(state["people"]):
                if state["alive"][i] and (str(p[t]) == v) != answer:
                    state["alive"][i] = False
            state["asked"].append([t, v])
            base.say(state, f"{a['text']} {'Yes.' if answer else 'No.'} {sum(state['alive'])} left.")
        else:
            answer = str(state["people"][state["secret"]][t]) == v
            for i, p in enumerate(state["people"]):
                if state["their_alive"][i] and (str(p[t]) == v) != answer:
                    state["their_alive"][i] = False
            state["their_asked"].append([t, v])
            base.say(state, f"{state['seats'][1]}: {a.get('text', t + ' ' + v)} You: {'yes' if answer else 'no'}. {sum(state['their_alive'])} left on {'their' if seat else 'your'} board.")
        state["turn"] = 1 - seat
        return state
    i = int(a["face"])
    if seat == 0:
        if i == state["theirs"]:
            base.finish(state, "win", f"{state['people'][i]['name']}: yes, that was them.")
        else:
            base.finish(state, "lose", f"{state['people'][i]['name']}? No. It was {state['people'][state['theirs']]['name']}.")
    else:
        if i == state["secret"]:
            base.finish(state, "lose", f"{state['seats'][1]} names {state['people'][i]['name']}: right.")
        else:
            base.finish(state, "win", f"{state['seats'][1]} names {state['people'][i]['name']}: wrong, it was {state['people'][state['secret']]['name']}.")
    return state


def view(state: dict[str, Any], seat: int) -> dict[str, Any]:
    mine = state["turn"] == 0 and not state["over"]
    items = []
    for i, p in enumerate(state["people"]):
        item = {"id": p["id"], "name": p["name"], "figure": p.get("figure", ""), "traits": [p["trade"], p["headwear"], "beard" if p["beard"] == "yes" else "no beard", p["hair"] + " hair"],
                "down": not state["alive"][i] and state["phase"] != "pick", "selected": state["secret"] == i}
        if mine and state["phase"] == "pick":
            item["action"] = {"id": f"pick:{i}", "face": i}
        elif mine and state["alive"][i]:
            item["action"] = {"id": f"guess:{i}", "face": i}
        items.append(item)
    label = "Who do you think of? (tap)" if state["phase"] == "pick" else ("The village (tap a face to name them)" if mine else "The village")
    areas = [base.area("score", "", rows=[{"name": "left on your board", "value": sum(state["alive"])}, {"name": f"left on {state['seats'][1]}'s", "value": sum(state["their_alive"])}]),
             base.area("faces", label, size=96, items=items)]
    if state["over"]:
        msg = "That was them." if state["result"] == "win" else "Not them."
    elif state["phase"] == "pick":
        msg = "Think of somebody in the village: tap them. The sawyer will try to guess who."
    elif mine:
        msg = "Ask about them, or name them."
    else:
        msg = f"{state['seats'][1]} is thinking."
    return base.head(state, "Who ordered the planks?", msg, areas, actions(state, seat))
