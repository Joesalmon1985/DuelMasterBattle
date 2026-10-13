"""Liquids and heat: pumps, conduits, tanks, bridges, consumers (owner programme 13 Oct 2026).

Mindustry's own rules (Building.moveLiquid / dumpLiquid): a block hands liquid to a neighbour in proportion to the difference of their fill
fractions, a neighbour only accepts the liquid it already holds (or any when nearly empty) and only if it consumes or stores it. Conduits are
directional tiles that push to the tile in front; an open end leaks. Machines keep their own tank `m["liq"]`.

Conservation: pumped / produced liquid is `liq_made_<liquid>`, drunk by a consumer `liq_used_<liquid>`, leaked or lost `liq_lost_<liquid>`;
`liquid_books(world)` checks made = held + used + lost for every liquid.
"""

from __future__ import annotations

from typing import Any

from wizard_rts.industry import registry as R

DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))
DT_TICKS = 6  # a 100 ms quantum is six Mindustry ticks
SUBSTEPS = 3
LEAK_FRACTION = 0.25
EPS = 1e-9

FLUID_ROLES = ("pump", "conduit", "tank", "liquid_junction", "liquid_bridge")


def init_fluid(world: Any, b: dict, m: dict, spec: dict) -> None:
    m["liq"] = {}
    if spec["role"] == "liquid_bridge":
        m["link"] = b.pop("mdy_link", None)
    if spec["role"] == "pump":
        m["pumped"] = 0.0


def cap_of(spec: dict) -> float:
    return float(spec.get("liquid_capacity", 10.0))


def amount(m: dict) -> float:
    return sum(m["liq"].values())


def current(m: dict) -> str | None:
    return max(m["liq"], key=lambda k: m["liq"][k]) if m["liq"] else None


def accepts_liquid(world: Any, b: dict, liquid: str) -> float:
    """Room (units) for `liquid` in machine `b`; 0 when it does not take it."""
    m = b.get("mdy")
    if m is None or b.get("constructing") or int(b.get("hp", 1)) <= 0:
        return 0.0
    spec = R.block(b["kind"])
    role = m["role"]
    cap = cap_of(spec)
    cur = current(m)
    if role in ("tank", "liquid_junction", "liquid_bridge", "conduit"):
        if cur not in (None, liquid) and amount(m) >= 0.2:
            return 0.0
        return max(0.0, cap - amount(m))
    wanted = set(spec["consume_liquids"]) | set(spec["boost_liquids"])
    if role == "turret":
        wanted |= set((spec.get("ammo") or {}).keys()) & set(R.defs()["liquids"]) if spec.get("class") in ("LiquidTurret", "ContinuousLiquidTurret") else set()
        if spec.get("coolant"):
            wanted |= {"water", "cryofluid"}
    if liquid not in wanted:
        return 0.0
    return max(0.0, cap - m["liq"].get(liquid, 0.0))


def add_liquid(world: Any, b: dict, liquid: str, qty: float) -> None:
    m = b["mdy"]
    m["liq"][liquid] = m["liq"].get(liquid, 0.0) + qty


def take_liquid(m: dict, liquid: str, qty: float) -> float:
    have = m["liq"].get(liquid, 0.0)
    got = min(have, qty)
    if got > 0:
        m["liq"][liquid] = have - got
        if m["liq"][liquid] <= EPS:
            m["liq"].pop(liquid)
    return got


def note(world: Any, key: str, liquid: str, qty: float) -> None:
    if qty > 0:
        world.stats[key + liquid] = world.stats.get(key + liquid, 0.0) + qty


def produce(world: Any, b: dict, liquid: str, qty: float) -> float:
    """A producer fills its own tank (up to capacity); returns what fitted. Booked as made."""
    m = b["mdy"]
    single = R.block(b["kind"])["role"] in ("tank", "liquid_junction", "liquid_bridge", "conduit")
    room = max(0.0, cap_of(R.block(b["kind"])) - (amount(m) if single else m["liq"].get(liquid, 0.0)))
    if single and m["liq"] and current(m) != liquid and amount(m) >= 0.2:
        return 0.0
    got = min(room, qty)
    if got > 0:
        add_liquid(world, b, liquid, got)
        note(world, "liq_made_", liquid, got)
    return got


def consume(world: Any, b: dict, liquid: str, qty: float) -> float:
    got = take_liquid(b["mdy"], liquid, qty)
    note(world, "liq_used_", liquid, got)
    return got


# ------------------------------------------------------------------ flow

def _move(src_amt: float, src_cap: float, dst_amt: float, dst_cap: float, liquid_have: float, scale: float = 1.0) -> float:
    """Building.moveLiquid: flow = clamp(src_fraction - dst_fraction) * src_capacity, limited by what is there and by the destination's room."""
    fract = src_amt / src_cap
    ofract = dst_amt / dst_cap
    if ofract > fract:
        return 0.0
    flow = min(max(0.0, min(1.0, fract - ofract)) * src_cap * scale, liquid_have)
    return min(flow, dst_cap - dst_amt)


def _pipe_target(world: Any, st: Any, tile: tuple[int, int], liquid: str):
    """What stands in front of a pipe tile: ('pipe', tile) | ('machine', building) | None."""
    pipe = st.pipes[tile]
    dx, dy = DIRS[pipe["d"]]
    nxt = (tile[0] + dx, tile[1] + dy)
    if nxt in st.pipes:
        q = st.pipes[nxt]
        odx, ody = DIRS[q["d"]]
        if (nxt[0] + odx, nxt[1] + ody) == tile:
            return None  # that pipe points at us: nothing flows into its front
        if q.get("armored") and not pipe.get("armored_ok", True):
            return None
        if q["liq"] not in (None, "", liquid) and q["amt"] >= 0.2:
            return None
        return ("pipe", nxt)
    ob_id = st.tile_owner.get(nxt)
    if ob_id is not None:
        ob = world.buildings.get(ob_id)
        if ob is not None and accepts_liquid(world, ob, liquid) > 0:
            return ("machine", ob)
    return None


def step_pipes(world: Any, st: Any) -> None:
    for _ in range(SUBSTEPS):
        for tile in st.pipe_order:
            p = st.pipes[tile]
            if p["amt"] <= EPS or not p["liq"]:
                continue
            liquid = p["liq"]
            tgt = _pipe_target(world, st, tile, liquid)
            if tgt is None:
                dx, dy = DIRS[p["d"]]
                nxt = (tile[0] + dx, tile[1] + dy)
                if nxt in st.pipes or st.tile_owner.get(nxt) is not None:
                    continue  # blocked, not open: the liquid waits
                lost = min(p["amt"], p["cap"] * LEAK_FRACTION / SUBSTEPS)  # an open end leaks (Conduit.leaks)
                p["amt"] -= lost
                note(world, "liq_lost_", liquid, lost)
                if p["amt"] <= EPS:
                    p["liq"], p["amt"] = None, 0.0
                continue
            if tgt[0] == "pipe":
                q = st.pipes[tgt[1]]
                flow = _move(p["amt"], p["cap"], q["amt"], q["cap"], p["amt"])
                if flow > 0:
                    q["liq"] = liquid
                    q["amt"] += flow
                    p["amt"] -= flow
            else:
                ob = tgt[1]
                m = ob["mdy"]
                spec = R.block(ob["kind"])
                flow = _move(p["amt"], p["cap"], m["liq"].get(liquid, 0.0), cap_of(spec), p["amt"])
                if flow > 0:
                    add_liquid(world, ob, liquid, flow)
                    p["amt"] -= flow
            if p["amt"] <= EPS:
                p["liq"], p["amt"] = None, 0.0


def dump_liquid(world: Any, st: Any, b: dict, liquid: str, scaling: float = 2.0) -> None:
    """Building.dumpLiquid: give to adjacent acceptors in rotation, proportional to the fill difference."""
    from wizard_rts.industry import sim as S

    m = b["mdy"]
    spec = R.block(b["kind"])
    have = m["liq"].get(liquid, 0.0)
    if have <= EPS:
        return
    ring = S.adjacent_tiles(S.footprint(b))
    n = len(ring)
    cap = cap_of(spec)
    for k in range(n):
        t = ring[(m.get("ldump", 0) + k) % n]
        have = m["liq"].get(liquid, 0.0)
        if have <= EPS:
            break
        if t in st.pipes:
            q = st.pipes[t]
            dx, dy = DIRS[q["d"]]
            front = (t[0] + dx, t[1] + dy)
            if front in S.footprint(b):
                continue  # a conduit pointing into this block is a source, not a sink
            if q["liq"] not in (None, "", liquid) and q["amt"] >= 0.2:
                continue
            fract, ofract = have / cap, q["amt"] / q["cap"]
            if ofract < fract:
                flow = min((fract - ofract) * cap / scaling, have, q["cap"] - q["amt"])
                if flow > 0:
                    q["liq"] = liquid
                    q["amt"] += flow
                    take_liquid(m, liquid, flow)
            continue
        ob_id = st.tile_owner.get(t)
        if ob_id is None or ob_id == b["id"]:
            continue
        ob = world.buildings.get(ob_id)
        if ob is None or accepts_liquid(world, ob, liquid) <= 0:
            continue
        om = ob["mdy"]
        ocap = cap_of(R.block(ob["kind"]))
        fract, ofract = have / cap, om["liq"].get(liquid, 0.0) / ocap
        if ofract < fract or R.block(ob["kind"])["role"] not in ("tank", "liquid_junction", "liquid_bridge", "conduit"):
            flow = min((fract - ofract) * cap / scaling if ofract < fract else min(have, ocap - om["liq"].get(liquid, 0.0)), have, ocap - om["liq"].get(liquid, 0.0))
            if flow > 0:
                take_liquid(m, liquid, flow)
                add_liquid(world, ob, liquid, flow)
    m["ldump"] = (m.get("ldump", 0) + 1) % max(1, n)


def pump_rate(world: Any, b: dict, spec: dict) -> tuple[str, float]:
    """(liquid, units per tick at full power): Pump.pumpAmount per water tile under the footprint; SolidPump on any tile; Fracker makes oil."""
    from wizard_rts.industry import sim as S

    tiles = S.footprint(b)
    amt = float(spec["fields"].get("pumpAmount", 0.1))
    cls = spec["class"]
    if cls == "Pump":
        t = world.terrain
        n = sum(1 for (x, y) in tiles if t is not None and t.in_bounds(x, y) and t.is_water(x, y))
        return "water", amt * n
    if cls == "SolidPump":
        return "water", amt * len(tiles)
    if cls == "Fracker":
        return "oil", amt * len(tiles)
    return "water", 0.0


def step_machines(world: Any, st: Any, machines: list[dict], sat: dict[int, float]) -> None:
    """Pumps, tanks, bridges and every machine that outputs liquid."""
    for b in machines:
        m = b["mdy"]
        spec = R.block(b["kind"])
        role = m["role"]
        if b.get("disrupted"):
            continue
        if role == "pump":
            _pump_step(world, st, b, m, spec, sat.get(st.graph_of.get(b["id"], -1), 0.0))
        elif role in ("tank",):
            for liquid in list(m["liq"]):
                dump_liquid(world, st, b, liquid)
            m["state"] = "holding" if amount(m) > 0 else "empty"
        elif role == "liquid_junction":
            _junction_step(world, st, b, m, spec)
        elif role == "liquid_bridge":
            _bridge_step(world, st, b, m, spec)
        elif spec["output_liquid"] and role in ("crafter", "generator"):
            for liquid in list(m["liq"]):
                if liquid in spec["output_liquid"]:
                    dump_liquid(world, st, b, liquid)


def _pump_step(world: Any, st: Any, b: dict, m: dict, spec: dict, satisfaction: float) -> None:
    liquid, per_tick = pump_rate(world, b, spec)
    if per_tick <= 0:
        m["state"] = "no liquid under it"
        return
    if spec["power_use_per_s"] > 0 and satisfaction <= 0:
        m["state"] = "no power"
        return
    # a Fracker also needs its input item and water (consume lists), checked by the crafter-style consumption below
    eff = satisfaction if spec["power_use_per_s"] > 0 else 1.0
    if spec["class"] == "Fracker":
        if spec["consume_liquids"].get("water", 0) * DT_TICKS > m["liq"].get("water", 0.0) + EPS:
            m["state"] = "needs water"
            return
        need_item = next(iter(spec["consume_items"]), None)
        if need_item and m["buf"].get(need_item, 0) < 1 and m["progress"] <= 0:
            m["state"] = "needs " + need_item
            return
        m["progress"] += DT_TICKS
        if m["progress"] >= int(spec["fields"].get("itemUseTime", 100)):
            m["progress"] = 0
            if need_item:
                m["buf"][need_item] -= 1
                world.stats["consumed_" + need_item] = world.stats.get("consumed_" + need_item, 0) + 1
        consume(world, b, "water", spec["consume_liquids"]["water"] * DT_TICKS)
    got = produce(world, b, liquid, per_tick * DT_TICKS * eff)
    m["pumped"] = got
    m["state"] = "pumping" if got > 0 else "full"
    dump_liquid(world, st, b, liquid)


def _junction_step(world: Any, st: Any, b: dict, m: dict, spec: dict) -> None:
    """A liquid junction passes liquid straight through: tiles pointing into it deliver to the tile opposite (we approximate by averaging)."""
    m["state"] = "passing"
    for liquid in list(m["liq"]):
        dump_liquid(world, st, b, liquid, scaling=1.0)


def _bridge_step(world: Any, st: Any, b: dict, m: dict, spec: dict) -> None:
    link = world.buildings.get(m.get("link") or "")
    if link is not None and (link.get("mdy") is None or int(link.get("hp", 1)) <= 0):
        link = None
    rng = int(spec["fields"].get("range", 4))
    if link is not None and (link["tx"] == b["tx"] or link["ty"] == b["ty"]) and abs(link["tx"] - b["tx"]) + abs(link["ty"] - b["ty"]) <= rng:
        if spec["power_use_per_s"] > 0 and not b.get("powered", True):
            return
        for liquid in list(m["liq"]):
            lm = link["mdy"]
            cap = cap_of(spec)
            flow = _move(m["liq"][liquid], cap, lm["liq"].get(liquid, 0.0), cap_of(R.block(link["kind"])), m["liq"][liquid], 1.0)
            if flow > 0 and accepts_liquid(world, link, liquid) > 0:
                take_liquid(m, liquid, flow)
                add_liquid(world, link, liquid, flow)
        m["state"] = "sending"
        return
    for liquid in list(m["liq"]):
        dump_liquid(world, st, b, liquid, scaling=1.0)
    m["state"] = "outputting"


def liquid_held(world: Any) -> dict[str, float]:
    st = getattr(world, "industry", None)
    out: dict[str, float] = {}
    if st is None:
        return out
    for p in st.pipes.values():
        if p["liq"] and p["amt"] > 0:
            out[p["liq"]] = out.get(p["liq"], 0.0) + p["amt"]
    for b in world.buildings.values():
        m = b.get("mdy")
        if m and m.get("liq"):
            for k, v in m["liq"].items():
                out[k] = out.get(k, 0.0) + v
    return out


def liquid_books(world: Any, tol: float = 1e-6) -> list[tuple[str, float, float]]:
    """Liquids whose books do not balance: made = held + used + lost (the liquid twin of ledger.check)."""
    held = liquid_held(world)
    bad = []
    names = set(held) | {k[len("liq_made_"):] for k in world.stats if k.startswith("liq_made_")}
    for liquid in sorted(names):
        made = world.stats.get("liq_made_" + liquid, 0.0)
        out = held.get(liquid, 0.0) + world.stats.get("liq_used_" + liquid, 0.0) + world.stats.get("liq_lost_" + liquid, 0.0)
        if abs(made - out) > tol * max(1.0, made):
            bad.append((liquid, made, out))
    return bad
