"""Relations between factions (plan v2 7.3): war, truce, peace, alliance, with expiry and explicit breaking.

Hostility is the only thing relations change: units and buildings of factions that are not at war do not target each other
(military._scan, order_attack, the AIs' target lists). Nests belong to nobody and are always hostile to everyone, so a truce lets
rivals fight a catastrophe side by side. `world.diplomacy_enabled` switches the heuristic AIs' cooperative rule on (default off until the
P10 calibration study); the relation commands themselves always work.
"""

from __future__ import annotations

from typing import Any

STATES = ("war", "truce", "peace", "alliance")
TRUCE_MS = 15 * 60_000
OFFER_MS = 2 * 60_000
PRESSURE_TO_COOPERATE = 0.4


def _key(a: str, b: str) -> str:
    return "|".join(sorted((a, b)))


def rel(world: Any) -> dict[str, dict[str, Any]]:
    return world.__dict__.setdefault("relations", {})


def state_of(world: Any, a: str, b: str) -> str:
    r = rel(world).get(_key(a, b))
    return r["state"] if r else "war"


def hostile(world: Any, a: str, b: str) -> bool:
    """Do two faction NAMES fight each other? Different, and at war."""
    if a == b:
        return False
    return not a or not b or state_of(world, a, b) == "war"  # a nest (no faction) is hostile to everyone


def hostile_ids(world: Any, a_id: str, b_id: str) -> bool:
    """The same for faction ids (what units carry in `faction`); neutral (empty id) is hostile to everybody."""
    if not a_id or not b_id:
        return True
    if not rel(world):
        return a_id != b_id
    names = world.__dict__.get("_fid_names")
    if names is None or len(names) != len(world.faction_info):
        names = world._fid_names = {i["id"]: n for n, i in world.faction_info.items()}
    return a_id != b_id and hostile(world, names.get(a_id, a_id), names.get(b_id, b_id))


def set_state(world: Any, a: str, b: str, state: str, duration_ms: int = 0, why: str = "") -> dict[str, Any]:
    if state not in STATES or a == b or a not in world.faction_info or b not in world.faction_info:
        return {"status": "rejected", "reason": "bad_relation"}
    now = int(world.dmb.clock.get("game_ms", 0))
    old = state_of(world, a, b)
    if state == "war":
        rel(world).pop(_key(a, b), None)
    else:
        rel(world)[_key(a, b)] = {"state": state, "since_ms": now, "until_ms": now + duration_ms if duration_ms else 0}
    world.events.append({"kind": "relation_changed", "a": a, "b": b, "from": old, "to": state, "why": why, "until_ms": rel(world).get(_key(a, b), {}).get("until_ms", 0)})
    return {"status": "ok"}


def break_treaty(world: Any, a: str, b: str, why: str = "broken") -> dict[str, Any]:
    """Either side may end any non-war relation at once. Units that were standing side by side are enemies again from the next quantum."""
    if state_of(world, a, b) == "war":
        return {"status": "rejected", "reason": "already_at_war"}
    world.fstat(a, "treaties_broken")
    return set_state(world, a, b, "war", why=why)


def propose(world: Any, a: str, b: str, state: str = "truce", duration_ms: int = TRUCE_MS) -> dict[str, Any]:
    offers = world.__dict__.setdefault("offers", {})
    if state not in STATES[1:] or a == b:
        return {"status": "rejected", "reason": "bad_offer"}
    now = int(world.dmb.clock.get("game_ms", 0))
    oid = f"offer:{len(offers) + world.__dict__.get('_offer_n', 0)}"
    world._offer_n = world.__dict__.get("_offer_n", 0) + 1
    offers[oid] = {"id": oid, "from": a, "to": b, "state": state, "duration_ms": duration_ms, "expires_ms": now + OFFER_MS}
    world.events.append({"kind": "offer_made", "id": oid, "from": a, "to": b, "state": state})
    return {"status": "ok", "offer": oid}


def respond(world: Any, offer_id: str, accept: bool) -> dict[str, Any]:
    offer = world.__dict__.get("offers", {}).pop(offer_id, None)
    if offer is None:
        return {"status": "rejected", "reason": "no_offer"}
    if not accept:
        world.events.append({"kind": "offer_refused", "id": offer_id, "from": offer["from"], "to": offer["to"]})
        return {"status": "ok", "accepted": False}
    set_state(world, offer["from"], offer["to"], offer["state"], offer["duration_ms"], why="offer " + offer_id)
    return {"status": "ok", "accepted": True}


def pressure(world: Any) -> float:
    """How close the world is to collective loss: the larger of the cumulative and the current-era outbreak fractions."""
    from wizard_rts import regions

    s = regions.state(world)
    if s is None:
        return 0.0
    total = int(getattr(world, "loss_outbreaks_total", regions.const("loss_outbreaks")))
    per_era = int(getattr(world, "loss_outbreaks_per_era", regions.config()["constants"].get("loss_outbreaks_per_era", total)))
    return max(s.outbreaks / max(1, total), s.era_outbreaks.get(int(getattr(world, "era_index", 0)), 0) / max(1, per_era))


def policy_of(world: Any, name: str) -> str:
    return world.__dict__.get("diplomacy_policy", {}).get(name, "coop")


def diplomacy_quantum(world: Any) -> None:
    """Expire treaties and offers (once a game second); with `diplomacy_enabled`, the heuristic cooperative rule runs every 10 s."""
    if world.economy_quanta % 10:
        return
    now = int(world.dmb.clock.get("game_ms", 0))
    for key, r in list(rel(world).items()):
        if r["until_ms"] and now >= r["until_ms"]:
            a, b = key.split("|")
            set_state(world, a, b, "war", why="expired")
    offers = world.__dict__.get("offers", {})
    for oid, o in list(offers.items()):
        if now >= o["expires_ms"]:
            offers.pop(oid)
    if not getattr(world, "diplomacy_enabled", False) or world.economy_quanta % 100:
        return
    p = pressure(world)
    names = [n for n in world.faction_info if (world.__dict__.get("history") or {}).get("faction", {}).get(n, {}).get("state") != "collapsed"]
    if p < PRESSURE_TO_COOPERATE:
        return
    for i, a in enumerate(names):
        if policy_of(world, a) != "coop":
            continue
        for b in names[i + 1:]:
            if policy_of(world, b) == "coop" and state_of(world, a, b) == "war" and not any(o["from"] == a and o["to"] == b for o in offers.values()):
                res = propose(world, a, b, "truce")
                respond(world, res["offer"], True)  # both are cooperative and see the same pressure: the heuristic accepts
