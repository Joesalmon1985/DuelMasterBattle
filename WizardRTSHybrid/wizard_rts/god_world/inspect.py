"""Plain-language details for a tapped thing (PRD 12.3). The viewer sends a semantic id; this answers with a title, a subtitle and lines of
ordinary game language. No class names, no token enums: the age's own words."""

from __future__ import annotations

from typing import Any

from . import composition, rules
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
    except KeyError:
        pass
    return {"id": sid, "title": "Nothing here", "subtitle": "", "lines": []}


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
