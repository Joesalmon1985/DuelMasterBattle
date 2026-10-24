"""Plain-language details for a tapped thing (PRD 12.3). The viewer sends a semantic id; this answers with a title, a subtitle and lines of
ordinary game language. No class names, no token enums: the age's own words."""

from __future__ import annotations

from typing import Any

from . import composition, local_ops, rules
from .snapshot import village_layout


def _faction_name(world, fid: str) -> str:
    return world.faction(fid)["name"]


def _goods(world, goods: dict[str, int]) -> str:
    age = int(world.age)
    parts = [f"{n} {rules.role_name(age, r).lower()}" for r, n in goods.items() if n]
    return ", ".join(parts) if parts else "nothing"


def label(world, sid: str) -> dict[str, Any]:
    """The compact first-stage label: {title, subtitle, faction}."""
    d = details(world, sid)
    return {"id": sid, "title": d.get("title", "?"), "subtitle": d.get("subtitle", ""), "faction": d.get("faction", "")}


def details(world, sid: str) -> dict[str, Any]:
    kind, _, rest = sid.partition(":")
    try:
        if kind == "hex":
            return _hex(world, sid)
        if kind == "village" or kind == "warehouse":
            return _village(world, rest)
        if kind == "station":
            return _station(world, rest)
        if kind == "road":
            return _road(world, rest)
        if kind == "journey":
            return _journey(world, rest)
        if kind == "facility":
            return _facility(world, rest)
        if kind == "unit":
            return _unit(world, rest)
        if kind == "remains":
            return _village(world, rest)
        if kind == "site":
            return _site(world, rest)
        if kind == "agent":
            return _agent(world, rest)
        if kind in ("formation", "responder", "post"):
            return _campaign(world, kind, rest)
    except KeyError:
        pass
    return {"id": sid, "title": "Nothing here", "subtitle": "", "lines": []}


def _campaign(world, kind: str, rest: str) -> dict[str, Any]:
    from .pandemic import presentation as P, rules as R

    camp = world.pandemic
    if camp is None:
        raise KeyError(rest)
    st = camp["state"]
    age = int(camp["age"])
    if kind == "formation":
        nid, _, fam = rest.rpartition(":")
        loc = st["locations"][nid]
        n = int(loc["units"].get(fam, 0))
        if n <= 0:
            raise KeyError(rest)
        name = P.family_name(age, fam)
        lines = [f"A hostile formation of {name.lower()}: {n} {'unit' if n == 1 else 'units'} on this ground." + (" At full strength: one more and they break out into every neighbouring place." if n >= 3 else ""),
                 "They are beaten by the responders' work here, not by the garrisons: each treatment sends one unit back; a cured family goes at once."]
        if st["families"][fam]["cured"]:
            lines.append("Their countermeasure is known.")
        return {"id": f"formation:{rest}", "title": name, "subtitle": f"{n} of 3 · {rules.hex_name(age, world.board.role(world.board.node_hexes[nid][0])) if world.board.node_hexes[nid] else 'crossing'}", "lines": lines, "faction": ""}
    if kind == "responder":
        r = R.responder(st, rest)
        by = R.hand_by_family(st, r)
        held = ", ".join(f"{P.family_name(age, f)} {len(c)}" for f, c in by.items() if c) or "no location cards"
        fname = _faction_name(world, r["faction"])
        role_lines = {"medic": "Clears every unit of a family where she works, and keeps a cured family from returning where she stands.",
                      "scientist": "Finds a countermeasure with four matching cards instead of five.",
                      "researcher": "May hand any location card to a responder standing with him.",
                      "dispatcher": "May move another responder, or bring one to any responder's side.",
                      "operations_expert": "Raises a field post anywhere without a card, and may fly from a post to any place once a turn.",
                      "quarantine_specialist": "No unit arrives where she stands or in the neighbouring places."}
        lines = [f"Manufactured at {fname}'s base under supply contract for {P.CAMPAIGN_NAMES.get(age, 'the campaign').lower()}.", role_lines[r["role"]], f"Holding {held}; events: {', '.join(R.EVENT_NAMES[c] for c in r['hand'] if c in R.EVENTS) or 'none'}."]
        if r is R.current(st) and st["result"] is None:
            lines.append("Acting now.")
        return {"id": f"responder:{rest}", "title": R.ROLE_NAMES[r["role"]], "subtitle": f"{fname} · responder", "lines": lines, "faction": r["faction"]}
    if kind == "post":
        nid = rest
        if not st["locations"][nid]["post"]:
            raise KeyError(rest)
        owner = next((fid for fid, b in camp.get("bases", {}).items() if b == nid), "")
        lines = ["A field post: countermeasures are found here, and responders shuttle between posts in one move."]
        return {"id": f"post:{nid}", "title": "Field post", "subtitle": (_faction_name(world, owner) + "'s base") if owner else "raised in the field", "lines": lines, "faction": owner}
    raise KeyError(rest)


def _hex(world, hid: str) -> dict[str, Any]:
    b = world.board
    age = int(world.age)
    role = b.role(hid)
    token = b.token(hid)
    lines = []
    if role == rules.DESERT:
        lines.append("Nothing grows or is dug here. No village gains from it.")
    else:
        lines.append(f"Produces {rules.role_name(age, role).lower()} when the dice show {token}: {rules.odds_text(token)} of rolls.")
    around = [v for v in world.villages.values() if v["status"] in ("operational", "rebuilding") and hid in b.node_hexes[v["node"]]]
    if around:
        lines.append("Bordering villages: " + ", ".join(f"{v['name']} ({_faction_name(world, v['faction'])}, {'city' if int(v['level']) >= 2 else 'settlement'})" for v in sorted(around, key=lambda v: v["id"])))
    else:
        lines.append("No village borders it yet.")
    if world.last_roll and role != rules.DESERT:
        hits = [g for g in world.last_roll["grants"] if g["hex"] == hid]
        if hits:
            lines.append(f"Last roll ({world.last_roll['total']}): " + ", ".join(f"{world.villages[g['village']]['name']} gained {g['n']}" for g in hits))
    return {"id": hid, "title": rules.hex_name(age, role), "subtitle": f"{token}" if token else "", "lines": lines, "faction": ""}


def _village(world, vid: str) -> dict[str, Any]:
    v = world.villages[vid]
    age = int(world.age)
    fname = _faction_name(world, v["faction"])
    if v["status"] == "historical":
        lines = [f"Founded in the {rules.age_name(int(v['history'][0]['age']))} age by {fname}; left behind when the {rules.age_name(int(v.get('retired_age', age)))} age ended.",
                 f"It was a {'city' if int(v.get('final_level', 1)) >= 2 else 'settlement'} then. It produces nothing now and holds no claim on the land."]
        return {"id": f"remains:{vid}", "title": f"Remains of {v['name']}", "subtitle": f"{fname} · historical", "lines": lines, "faction": v["faction"]}
    kind = {"pending": "settlers on the road", "building": "warehouse under construction", "rebuilding": f"building the {rules.age_name(age)} age"}.get(v["status"])
    if kind is None:
        kind = "City" if int(v["level"]) >= 2 else "Settlement"
    lines = []
    hexes = world.board.productive_hexes(v["node"])
    if v["status"] in ("operational", "rebuilding"):
        lines.append(f"Worth {rules.vp_for_level(int(v['level']))} point{'s' if rules.vp_for_level(int(v['level'])) != 1 else ''} this age.")
    if hexes:
        lines.append("Touches " + ", ".join(f"{rules.hex_name(age, r).lower()} {t}" for _h, r, t in hexes) + ".")
        exp = composition.expected_output(world.board, v["node"], max(1, int(v["level"])))
        lines.append(f"Expected yield {exp:.2f} tokens a roll ({'two' if int(v['level']) >= 2 else 'one'} per matching hex).")
    if v["status"] in ("operational", "rebuilding"):
        lay = village_layout(world, v)
        lines.append(f"{lay['stations_total']} production stations in {sum(1 for d in lay['districts'] if d['count'])} districts; one warehouse.")
    hand = world.ledger.available(v["faction"])
    lines.append(f"{fname}'s resources: {_goods(world, hand)}.")
    produced = {r: n for r, n in v.get("produced", {}).items() if n}
    if produced:
        lines.append(f"Produced here this age: {_goods(world, produced)}.")
    if v.get("upgrade"):
        lines.append("A city is being raised here.")
    journeys = [j for j in world.journeys.values() if j.get("origin") == vid or j.get("dest") == vid]
    if journeys:
        lines.append(f"{len(journeys)} journey{'s' if len(journeys) != 1 else ''} to or from this warehouse.")
    st = world.ai[v["faction"]]
    plan = st.get("goal") or st.get("plan") or ""
    if plan:
        lines.append(f"{fname} is working on: {plan}." + (f" Waiting: {st['reason']}." if st.get("reason") else ""))
    return {"id": f"village:{vid}", "title": v["name"], "subtitle": f"{fname} · {kind}", "lines": lines, "faction": v["faction"]}


def _goods_ops(goods: dict[str, int]) -> str:
    parts = [f"{n} {local_ops.good_name(g)}" for g, n in goods.items() if n]
    return ", ".join(parts) if parts else "nothing"


def _site(world, sid: str) -> dict[str, Any]:
    vid = sid.split(":", 1)[0]
    v = world.villages[vid]
    ops = v.get("ops") or {}
    s = ops.get("sites", {}).get(sid)
    fname = _faction_name(world, v["faction"])
    if s is None and v.get("frozen"):
        fs = next((x for x in v["frozen"]["sites"] if x["id"] == sid), None)
        if fs is None:
            raise KeyError(sid)
        return {"id": f"site:{sid}", "title": f"Old {fs['name'].lower()}", "subtitle": f"{v['name']} · {fname} · {rules.age_name(int(v['frozen']['age']))} age",
                "lines": [f"Built when {v['name']} was {fname}'s. It stands quiet now: nobody works here and nothing it held counts.", "A new settlement on this ground may build over it."],
                "faction": v["faction"]}
    if s is None:
        raise KeyError(sid)
    age = int(v["age"])
    lines: list[str] = []
    state = {"planned": "Planned: waiting for the builders.", "reserved": "The builders are on their way.", "foundation": "The foundations are being laid.",
             "building": "Under construction.", "idle": "Ready for the next job.", "working": "At work.", "full": "Its store is full: waiting for a carrier.",
             "short": "Waiting for its inputs.", "no_work": "Nothing to work on nearby just now.", "unpowered": "No power."}.get(s["state"], s["state"])
    if s["state"] in local_ops.CONSTRUCTION:
        lines.append(f"{state} {int(local_ops.build_progress(s) * 100)}% built.")
    if s["kind"] == "hub":
        hub = ops.get("hub", {})
        lines.append(f"{v['name']}'s one store and dispatch yard. Everything the village makes is carried here.")
        dev = v.get("dev") or {}
        if dev:
            lines.append("Growth: " + "; ".join(f"{rules.hex_name(age, world.board.role(h)).lower()} {world.board.token(h)}: {r['unlocked']} of {r['cap']} places unlocked" for h, r in sorted(dev.items())) + ". Each matching roll unlocks one more.")
        stock = _goods_ops(hub.get("stock", {}))
        lines.append(f"In the yard: {stock}.")
        shipped = sum(int(n) for n in hub.get("shipped", {}).values())
        if shipped:
            lines.append(f"{shipped} loads have gone out to the wider world since the age began.")
        hand = world.ledger.available(v["faction"])
        lines.append(f"{fname}'s tradeable resources (the faction's hand, not this yard's goods): {_goods(world, hand)}.")
    elif s["kind"] == "producer":
        hexname = rules.hex_name(age, world.board.role(s["hex"])).lower() if s.get("hex") else "the land"
        token = world.board.token(s["hex"]) if s.get("hex") else 0
        lines.append(f"Works the {hexname} {token} for {local_ops.good_name(s['good'])}. {state}")
        lines.append(f"Made {int(s.get('produced', 0))} loads this age; {_goods_ops(s['out'])} waiting at the door.")
        lines.append(f"The dice decide what {fname} can trade and build: this district's region pays {rules.role_name(age, world.board.role(s['hex'])).lower() if s.get('hex') else ''} on a {token}.")
    elif s["kind"] == "processor":
        lines.append(f"Turns {', '.join(f'{n} {local_ops.good_name(g)}' for g, n in s.get('recipe', {}).items())} into {local_ops.good_name(s['good'])}. {state}")
        lines.append(f"Holds {_goods_ops(s['in'])}; {_goods_ops(s['out'])} finished and waiting; {int(s.get('produced', 0))} made this age.")
    elif s["kind"] == "support":
        lines.append({"plant": "Replants the woodland the woodcutters fell.", "": "Keeps the district supplied."}.get(s.get("task", ""), "Supports the district.") + f" {state}")
    elif s["kind"] == "military":
        return _facility(world, vid)
    elif s["kind"] == "generator":
        lines.append(f"Burns coal for the village's machines. {'Running.' if s['state'] == 'working' else 'Out of coal: the machines stand idle.'} Coal in the hopper: {int(s['in'].get('coal', 0))}.")
    elif s["kind"] == "pump":
        lines.append(f"Draws water {'from the shore' if 'pump' in s['id'] else 'from the ground'} into the pipe. {state}")
    elif s["kind"] == "tank":
        lines.append(f"Holds {int(s.get('water', 0))} of {int(s.get('cap', 12))} water for the cultivator.")
    elif s["kind"] == "factory":
        lines.append(f"Builds a unit from {', '.join(f'{n} {local_ops.good_name(g)}' for g, n in s.get('recipe', {}).items())}. {state}")
        lines.append(f"Holds {_goods_ops(s['in'])}; {int(ops.get('units_made', 0))} units mustered this age. Beyond the garrison's quota it stops.")
    if s.get("support"):
        lines.append("A local supply for the village's machines: it yields operating material only, never a tradeable resource.")
    if s.get("power") and not ops.get("power", True):
        lines.append("Unpowered: the generator has no coal.")
    return {"id": f"site:{sid}", "title": s["name"], "subtitle": f"{v['name']} · {fname}", "lines": lines, "faction": v["faction"]}


def _agent(world, aid: str) -> dict[str, Any]:
    vid = aid.split(":", 1)[0]
    v = world.villages[vid]
    ops = v.get("ops") or {}
    a = ops.get("agents", {}).get(aid)
    if a is None:
        raise KeyError(aid)
    site = ops.get("sites", {}).get(a["site"], {})
    fname = _faction_name(world, v["faction"])
    if a["kind"] == "worker":
        job = {"fell": "Woodcutter", "plant": "Forester", "quarry": "Quarryman", "hunt": "Hunter", "field": "Farmer", "tend": "Herder", "mine": "Miner"}.get(a.get("task", ""), "Worker")
        doing = {"home": "at the door, between jobs", "to_work": "walking out to work", "working": "working", "to_home": "carrying the load home"}.get(a["phase"], a["phase"])
        lines = [f"{job} of the {site.get('name', 'workshop').lower()} at {v['name']}: {doing}."]
        if a.get("cargo"):
            lines.append(f"Carrying {local_ops.good_name(a['cargo'])}.")
        return {"id": f"agent:{aid}", "title": job, "subtitle": f"{v['name']} · {fname}", "lines": lines, "faction": v["faction"]}
    title = "Carrier" if a["kind"] == "carrier" else "Cargo truck"
    doing = {"idle": "waiting at the yard for a load", "to_pickup": "going to fetch a load", "to_deliver": "delivering", "to_home": "returning to the yard"}.get(a["phase"], a["phase"])
    lines = [f"{title} of {v['name']}: {doing}."]
    job = a.get("job") or {}
    if job:
        frm = ops["sites"].get(job.get("from"), {}).get("name", "a workshop")
        to = ops["sites"].get(job.get("to"), {}).get("name", "the store")
        lines.append(f"{local_ops.good_name(job.get('good', ''))} from the {frm.lower()} to the {to.lower()}.")
    return {"id": f"agent:{aid}", "title": title, "subtitle": f"{v['name']} · {fname}", "lines": lines, "faction": v["faction"]}


def _station(world, rest: str) -> dict[str, Any]:
    vid = rest.split(":", 1)[0]
    v = world.villages[vid]
    age = int(v["age"])
    lay = village_layout(world, v)
    for d in lay["districts"]:
        for s in d["stations"]:
            if s["id"] == rest or any(b["id"] == rest for b in s["buildings"]):
                role = d["role"]
                name = rules.role_name(age, role)
                names = [rules.hex_name(age, role)]
                lines = [f"{name} district of {v['name']} · source: {names[0].lower()} {d['token']} · {d['count']} stations.",
                         f"{v['name']} gains {'two' if int(v['level']) >= 2 else 'one'} {name.lower()} when a {d['token']} is rolled ({rules.odds_text(d['token'])}).",
                         "The buildings show the work; the dice decide the yield."]
                if len(s["buildings"]) > 1:
                    lines.append("This station is a pair: the first building works the source, the second finishes the goods.")
                return {"id": f"station:{s['id']}", "title": f"{name} works", "subtitle": f"{v['name']} · {_faction_name(world, v['faction'])}", "lines": lines, "faction": v["faction"]}
    raise KeyError(rest)


def _road(world, eid: str) -> dict[str, Any]:
    r = world.roads[eid]
    a, b = world.board.edge_endpoints[eid]
    fname = _faction_name(world, r["faction"])
    ends = []
    for n in (a, b):
        v = world.active_village_at(n)
        ends.append(v["name"] if v else "a junction")
    lines = [f"From {ends[0]} to {ends[1]}."]
    if r["status"] == "building":
        lines.append("Under construction: the crew is laying it now.")
    elif r["status"] == "historical":
        lines.append(f"An old road of the {rules.age_name(int(r['age']))} age. Caravans still walk it; it no longer carries {fname}'s claim.")
    else:
        lines.append(f"Completed in the {rules.age_name(int(r['age']))} age. Settlers may found along it; caravans of every faction may use it.")
    traffic = sum(1 for j in world.journeys.values() if j["type"] in ("caravan", "expedition") and any(leg.get("node") in (a, b) for leg in j["legs"]))
    if traffic:
        lines.append(f"{traffic} journey{'s' if traffic != 1 else ''} routed this way.")
    return {"id": f"road:{eid}", "title": f"{fname} road" if r["status"] != "historical" else "Old road", "subtitle": r["status"], "lines": lines, "faction": r["faction"]}


def _journey(world, jid: str) -> dict[str, Any]:
    j = world.journeys[jid]
    fname = _faction_name(world, j["faction"])
    origin = world.villages.get(j.get("origin", ""), {}).get("name", "home")
    if j["type"] == "expedition":
        roles = ", ".join(m["role"] for m in j["party"])
        lines = [f"From {origin} to a new site. {roles}.", f"Carrying {_goods(world, j['supplies'])} for the new warehouse.",
                 "On the road" if j["phase"] == "outbound" else "Raising the warehouse", f"Leg {min(j['leg'] + 1, len(j['legs']))} of {len(j['legs'])}."]
        return {"id": f"journey:{jid}", "title": f"{fname} settlers", "subtitle": "founding expedition", "lines": lines, "faction": j["faction"]}
    if j["type"] == "bank":
        lines = [f"From {origin} to the coast and back: {_goods(world, j['give'])} offered to the bank for {_goods(world, j['want'])}.",
                 "Outbound" if j["phase"] == "outbound" else "Returning", "The bank always trades four of a kind for one of another."]
        return {"id": f"journey:{jid}", "title": f"{fname} bank caravan", "subtitle": "bank trade (4 for 1)", "lines": lines, "faction": j["faction"]}
    pname = _faction_name(world, j["partner"])
    dest = world.villages.get(j.get("dest", ""), {}).get("name", pname)
    lines = [f"From {origin} to {dest} ({pname}).", f"Gives {_goods(world, j['give'])}; brings back {_goods(world, j['want'])}.",
             ("Returning with the goods" if j["exchanged"] else "Outbound with the offer") + f" · leg {min(j['leg'] + 1, len(j['legs']))} of {len(j['legs'])}."]
    return {"id": f"journey:{jid}", "title": f"{fname} caravan", "subtitle": f"trade with {pname}", "lines": lines, "faction": j["faction"]}


def _facility(world, vid: str) -> dict[str, Any]:
    v = world.villages[vid]
    spec = rules.military_spec(int(v["age"]))
    units = [u for u in world.units.values() if u["village"] == vid and u["status"] == "active"]
    quota = rules.limit("garrison_city") if int(v["level"]) >= 2 else rules.limit("garrison_settlement")
    lines = [f"{spec.get('facility_name', 'Barracks')} of {v['name']}. {len(units)} of {quota} {spec.get('unit_name', 'soldiers').lower()}s mustered.",
             "They stand guard. Nobody is at war in this age of the world."]
    vets = sum(1 for u in world.units.values() if u["village"] == vid and u["status"] == "veteran")
    if vets:
        lines.append(f"{vets} veterans of earlier ages remain in the village's memory.")
    return {"id": f"facility:{vid}", "title": spec.get("facility_name", "Barracks"), "subtitle": f"{v['name']} · {_faction_name(world, v['faction'])}", "lines": lines, "faction": v["faction"]}


def _unit(world, uid: str) -> dict[str, Any]:
    u = world.units[uid]
    v = world.villages[u["village"]]
    lines = [f"Mustered at {v['name']} in the {rules.age_name(int(u['age']))} age.", "Standing idle at the parade ground." if u["status"] == "active" else "A veteran of an earlier age."]
    return {"id": f"unit:{uid}", "title": str(u["name"]), "subtitle": f"{_faction_name(world, u['faction'])} · {u['status']}", "lines": lines, "faction": u["faction"]}
