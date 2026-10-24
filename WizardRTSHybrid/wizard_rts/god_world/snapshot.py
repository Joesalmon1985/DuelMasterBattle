"""What the viewer receives: the static board once (`board_view`), and a snapshot each poll with stable ids and every semantic field the labels
need. Positions are board units; journey positions are interpolated authoritatively here from leg progress (the client only smooths)."""

from __future__ import annotations

from typing import Any

from . import composition, rules

_LAYOUT_CACHE: dict[tuple[str, str, int, int], dict[str, Any]] = {}


def village_layout(world, v: dict[str, Any]) -> dict[str, Any]:
    key = (world.run_id, v["id"], int(v["age"]), int(v["level"]) if v["status"] not in ("pending", "building") else 0)
    lay = _LAYOUT_CACHE.get(key)
    if lay is None:
        lay = composition.layout(world.board, v, int(v["age"]), level=key[3])
        if len(_LAYOUT_CACHE) > 2000:
            _LAYOUT_CACHE.clear()
        _LAYOUT_CACHE[key] = lay
    return lay


def board_view(world) -> dict[str, Any]:
    b = world.board
    hexes = []
    for hid in b.hexes:
        q, r = b.axial(hid)
        x, y = b.hex_xy(hid)
        hexes.append({"id": hid, "q": q, "r": r, "x": round(x, 4), "y": round(y, 4), "role": b.role(hid), "token": b.token(hid), "pips": rules.pips(b.token(hid)),
                      "corners": [[round(c, 4) for c in b.node_xy(n)] for n in b.hex_nodes[hid]], "nodes": list(b.hex_nodes[hid])})
    return {"shape": b.shape, "hexes": hexes, "nodes": {n: [round(c, 4) for c in b.node_xy(n)] for n in b.nodes},
            "edges": {e: list(ab) for e, ab in b.edge_endpoints.items()}, "bounds": [round(c, 4) for c in b.bounds], "centre": [round(c, 4) for c in b.centre],
            "cosmetic_seed": world.cosmetic_seed, "roles": list(rules.ROLES)}


def journey_pose(j: dict[str, Any]) -> tuple[float, float, float]:
    legs = j["legs"]
    if not legs:
        return 0.0, 0.0, 0.0
    i = min(int(j["leg"]), len(legs) - 1)
    leg = legs[i]
    t = 1.0 if j["phase"] == "building" or int(j["leg"]) >= len(legs) else min(1.0, float(j["leg_ms"]) / max(1.0, float(leg["ms"])))
    ax, ay = leg["a"]
    bx, by = leg["b"]
    x = ax + (bx - ax) * t
    y = ay + (by - ay) * t
    import math

    return x, y, math.atan2(by - ay, bx - ax)


def snapshot(world) -> dict[str, Any]:
    age = int(world.age)
    out: dict[str, Any] = {"profile": world.profile, "run_id": world.run_id, "game_ms": int(world.game_ms), "clock_sequence": int(world.clock_sequence),
                           "age": age, "age_name": rules.age_name(age), "phase": world.phase, "paused": world.paused, "speed": world.speed, "seed": world.seed,
                           "next_roll_in_ms": (int(world.next_roll_ms) - int(world.game_ms)) if world.next_roll_ms else None, "last_roll": world.last_roll,
                           "role_names": {r: rules.role_name(age, r) for r in rules.ROLES}, "pulses": int(world.pulses), "setup": {"step": world.setup["step"], "total": len(world.setup["order"])}}
    out["factions"] = [{"id": f["id"], "name": f["name"], "colour": f["colour"], "vp": world.vp(f["id"]), "hand": world.ledger.available(f["id"]),
                        "reserved": _reserved(world, f["id"]), "goal": world.ai[f["id"]].get("goal", ""), "reason": world.ai[f["id"]].get("reason", ""),
                        "villages": sum(1 for v in world.villages.values() if v["faction"] == f["id"] and v["status"] in ("operational", "rebuilding")),
                        "cities": sum(1 for v in world.villages.values() if v["faction"] == f["id"] and v["status"] == "operational" and int(v["level"]) >= 2)}
                       for f in world.factions]
    villages = []
    for vid in sorted(world.villages):
        v = world.villages[vid]
        if v["status"] == "cancelled":
            continue
        row: dict[str, Any] = {"id": vid, "name": v["name"], "node": v["node"], "faction": v["faction"], "level": int(v["level"]), "status": v["status"], "age": int(v["age"]),
                               "x": round(world.board.node_xy(v["node"])[0], 4), "y": round(world.board.node_xy(v["node"])[1], 4),
                               "ready": bool(world.game_ms >= int(v.get("ready_ms", 0))), "produced": dict(v.get("produced", {}))}
        c = v.get("construction")
        if c:
            row["construction"] = {"kind": c["kind"], "progress": _progress(world, c)}
        u = v.get("upgrade")
        if u:
            row["upgrade"] = {"progress": _progress(world, u)}
        if v["status"] == "historical":
            row["final_level"] = int(v.get("final_level", 1))
            row["retired_age"] = int(v.get("retired_age", age))
            lay = village_layout(world, {**v, "level": 1})
            row["warehouse"] = lay["warehouse"]
            row["districts"] = []
            row["military"] = None
        elif v["status"] == "pending":
            row["districts"] = []
            row["warehouse"] = None
            row["military"] = None
        else:
            lay = village_layout(world, v)
            row["warehouse"] = lay["warehouse"]
            row["districts"] = lay["districts"]
            row["stations_total"] = lay["stations_total"]
            row["military"] = lay["military"]
            row["expected"] = round(composition.expected_output(world.board, v["node"], int(v["level"])), 4)
            row["units"] = [{"id": u["id"], "art": u["art"], "name": u["name"], "slot": int(u["slot"]), "status": u["status"], "age": int(u["age"])}
                            for u in sorted(world.units.values(), key=lambda u: u["id"]) if u["village"] == vid and u["status"] == "active"]
            row["veterans"] = sum(1 for u in world.units.values() if u["village"] == vid and u["status"] == "veteran")
        villages.append(row)
    out["villages"] = villages
    roads = []
    for eid in sorted(world.roads):
        r = world.roads[eid]
        a, b = world.board.edge_xy(eid)
        row = {"id": eid, "faction": r["faction"], "status": r["status"], "age": int(r["age"]), "a": [round(a[0], 4), round(a[1], 4)], "b": [round(b[0], 4), round(b[1], 4)],
               "from_node": r.get("from_node")}
        if r["status"] == "building":
            row["progress"] = _progress(world, r)
        roads.append(row)
    out["roads"] = roads
    journeys = []
    for jid in sorted(world.journeys):
        j = world.journeys[jid]
        x, y, heading = journey_pose(j)
        row = {"id": jid, "type": j["type"], "faction": j["faction"], "phase": j["phase"], "x": round(x, 4), "y": round(y, 4), "heading": round(heading, 4),
               "origin": j.get("origin"), "leg": int(j["leg"]), "legs": len(j["legs"]), "started_ms": int(j["started_ms"]),
               "on_road": bool(j["legs"][min(int(j["leg"]), len(j["legs"]) - 1)].get("road", j["type"] == "expedition")) if j["legs"] else False}
        if j["type"] == "expedition":
            row.update(village=j["village"], dest_node=j["dest_node"], party=j["party"], supplies=j["supplies"], route=j["route"])
        elif j["type"] == "caravan":
            row.update(partner=j["partner"], dest=j["dest"], give=j["give"], want=j["want"], exchanged=bool(j["exchanged"]),
                       cargo=world.ledger.cargo.get(j["cargo"], {}).get("goods", {}) if j.get("cargo") else {})
        elif j["type"] == "bank":
            row.update(give=j["give"], want=j["want"], bank=True, cargo=world.ledger.cargo.get(j["cargo"], {}).get("goods", {}) if j.get("cargo") else {})
        journeys.append(row)
    out["journeys"] = journeys
    out["events"] = world.events[-30:]
    out["transition"] = world.transition
    out["final_result"] = world.final_result
    out["history"] = {"age_winners": world.history["age_winners"]}
    out["counters"] = dict(world.counters)
    return out


def _reserved(world, fid: str) -> dict[str, int]:
    out = {r: 0 for r in rules.ROLES}
    for rec in world.ledger.reservations.values():
        if rec["faction"] == fid:
            for r, n in rec["goods"].items():
                out[r] += n
    for rec in world.ledger.escrows.values():
        if rec["faction"] == fid:
            for r, n in rec["goods"].items():
                out[r] += n
    return out


def _progress(world, rec: dict[str, Any]) -> float:
    start, done = int(rec.get("started_ms", 0)), int(rec.get("done_ms", 0))
    if done <= start:
        return 1.0
    return round(max(0.0, min(1.0, (world.game_ms - start) / float(done - start))), 3)
