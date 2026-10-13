"""The generic Mindustry block engine, role by role, on the real world (owner programme 13 Oct 2026). Each test builds a small scene with the
fixture's instant placement (no payment, no waiting) and checks that wares flow through the physical blocks and the books balance."""
from __future__ import annotations

import pytest

from conftest import set_resource
from wizard_rts import ledger
from wizard_rts.industry import commands as C
from wizard_rts.industry import fixture as F
from wizard_rts.industry import fluids as FL
from wizard_rts.industry import registry as R
from wizard_rts.industry import sim as S
from wizard_rts.world import HybridWorld

SEED = 507


def unlock(w, faction="Red"):
    """Every generated card (the test scaffolding of a faction that has drafted the whole Modern line)."""
    from wizard_rts import tech
    from wizard_rts.content import graph

    have = w.tech[faction]["cards"]
    for cid in sorted(graph.generated_cards()):
        if cid not in have:
            have.append(cid)


def world(profile="developer"):
    w = HybridWorld(SEED, profile=profile)
    w.ai_enabled = False
    w._seq = 0
    F.grant_cards(w, "Red")
    unlock(w)
    return w


def run(w, seconds):
    for _ in range(int(seconds)):
        w._seq += 1
        w.advance(1000, w._seq, snapshot=False)


def put(w, kind, tile, force=False, **cfg):
    b = None
    why, ctx = C.check_machine(w, "Red", kind, tile)
    if not force:
        assert why is None, (kind, tile, why)
    spec = R.block(kind)
    bid = w._building(w.faction_info["Red"]["id"], "Red", kind, tile, spec["label"], spec["definition"])
    b = w.buildings[bid]
    if not ctx.get("footprint"):
        n = spec["size"]
        ctx = {"footprint": [(tile[0] + dx, tile[1] + dy) for dy in range(n) for dx in range(n)]}
    b["ground_footprint"] = [list(t) for t in ctx["footprint"]]
    w.blocked.update(ctx["footprint"])
    for k, v in cfg.items():
        b["mdy_" + k] = v
    S._init_machine(w, b)
    S.ind(w).dirty = True
    return bid


def belt(w, tiles, end_dir=None, kind="mdy:conveyor"):
    res = C.place_belt(w, "Red", tiles, end_dir, kind)
    assert res["status"] == "ok", res
    b = w.buildings[res["id"]]
    b.pop("constructing")
    b["operational"] = True
    b["hp"] = b["max_hp"]
    w.recipe_requests.pop(b["id"], None)
    return b["id"]


def stock(w, bid, ware):
    return int(w.stocks.get(bid, {}).get(ware, 0))


def balanced(w):
    return not ledger.check(w)


def test_every_implemented_block_has_a_spec_and_hybrid_cost():
    for k in R.kinds():
        sp = R.block(k)
        assert sp["cost"] and sp["role"] and sp["size"] >= 1, k


def feed(w, tile, ware, n=1):
    """Inject wares onto a belt tile as a source would (booked as made so the ledger stays honest)."""
    for _ in range(n):
        S.belt_put(S.ind(w), tile, ware)
    w.stats["made_" + ware] = w.stats.get("made_" + ware, 0) + n


def scene(width=14, height=7):
    w = world()
    x, y = F.open_ground(w, "Red", width, height)
    return w, x, y


def test_router_passes_items_to_a_store():
    w, x, y = scene()
    router = put(w, "mdy:router", (x + 3, y + 2))
    cont = put(w, "mdy:container", (x + 4, y + 2))
    run(w, 1)
    snap = ledger.snapshot_totals(w)
    b = belt(w, [(x, y + 2), (x + 1, y + 2), (x + 2, y + 2)])
    run(w, 1)
    feed(w, (x, y + 2), "mdy.copper", 3)
    run(w, 8)
    assert stock(w, cont, "mdy.copper") == 3
    assert not ledger.check(w, snap)


def test_sorter_sends_the_chosen_item_forward_and_the_rest_to_the_sides():
    w, x, y = scene()
    sorter = put(w, "mdy:sorter", (x + 3, y + 2), item="mdy.copper")
    fwd = put(w, "mdy:container", (x + 4, y + 2))
    up = put(w, "mdy:container", (x + 3, y), )
    down = put(w, "mdy:container", (x + 2, y + 3))
    run(w, 1)
    snap = ledger.snapshot_totals(w)
    belt(w, [(x, y + 2), (x + 1, y + 2), (x + 2, y + 2)])
    run(w, 1)
    feed(w, (x, y + 2), "mdy.copper", 2)
    feed(w, (x + 1, y + 2), "mdy.lead", 2)
    run(w, 10)
    assert stock(w, fwd, "mdy.copper") == 2 and stock(w, fwd, "mdy.lead") == 0
    assert stock(w, up, "mdy.lead") + stock(w, down, "mdy.lead") == 2 and stock(w, up, "mdy.copper") + stock(w, down, "mdy.copper") == 0
    assert not ledger.check(w, snap)


def test_overflow_gate_uses_the_sides_only_when_the_front_is_full():
    w, x, y = scene()
    gate = put(w, "mdy:overflow_gate", (x + 3, y + 2))
    fwd = put(w, "mdy:container", (x + 4, y + 2))
    side = put(w, "mdy:container", (x + 2, y + 3))
    run(w, 1)
    cap = R.block("mdy:container")["item_capacity"]
    w.stocks[fwd]["mdy.copper"] = cap - 2  # nearly full front
    snap = ledger.snapshot_totals(w)
    belt(w, [(x, y + 2), (x + 1, y + 2), (x + 2, y + 2)])
    run(w, 1)
    feed(w, (x, y + 2), "mdy.copper", 1)
    feed(w, (x + 1, y + 2), "mdy.copper", 1)
    run(w, 6)
    assert stock(w, fwd, "mdy.copper") == cap and stock(w, side, "mdy.copper") == 0
    feed(w, (x, y + 2), "mdy.copper", 2)
    run(w, 8)
    assert stock(w, fwd, "mdy.copper") == cap and stock(w, side, "mdy.copper") == 2  # the front is full: the rest overflows to the side


def test_junction_crosses_two_flows_without_mixing():
    w, x, y = scene()
    j = put(w, "mdy:junction", (x + 3, y + 3))
    east = put(w, "mdy:container", (x + 4, y + 3))
    south = put(w, "mdy:container", (x + 2, y + 4))
    run(w, 1)
    snap = ledger.snapshot_totals(w)
    belt(w, [(x, y + 3), (x + 1, y + 3), (x + 2, y + 3)])
    belt(w, [(x + 3, y), (x + 3, y + 1), (x + 3, y + 2)])
    run(w, 1)
    feed(w, (x, y + 3), "mdy.copper", 3)
    feed(w, (x + 3, y), "mdy.lead", 3)
    run(w, 12)
    assert stock(w, east, "mdy.copper") == 3 and stock(w, east, "mdy.lead") == 0
    assert stock(w, south, "mdy.lead") == 3 and stock(w, south, "mdy.copper") == 0
    assert not ledger.check(w, snap)


def test_bridge_carries_items_over_a_gap():
    w, x, y = scene()
    a = put(w, "mdy:bridge_conveyor", (x + 2, y + 2))
    c = put(w, "mdy:bridge_conveyor", (x + 5, y + 2))
    w.buildings[a]["mdy"]["link"] = c
    cont = put(w, "mdy:container", (x + 6, y + 2))
    run(w, 1)
    snap = ledger.snapshot_totals(w)
    belt(w, [(x, y + 2), (x + 1, y + 2)])
    run(w, 1)
    feed(w, (x, y + 2), "mdy.copper", 4)
    run(w, 15)
    assert stock(w, cont, "mdy.copper") == 4
    assert not ledger.check(w, snap)


def test_unloader_pulls_from_a_store_onto_a_belt_and_a_core_never_blocks():
    w, x, y = scene()
    cont = put(w, "mdy:container", (x + 1, y + 2))
    w.stocks[cont]["mdy.silicon"] = 5
    w.stats["made_mdy.silicon"] = 5
    un = put(w, "mdy:unloader", (x + 3, y + 2))
    core = put(w, "mdy:core_shard", (x + 6, y + 1))
    run(w, 1)
    snap = ledger.snapshot_totals(w)
    belt(w, [(x + 4, y + 2), (x + 5, y + 2)])
    run(w, 20)
    assert stock(w, cont, "mdy.silicon") == 0 and stock(w, core, "mdy.silicon") == 5
    assert not ledger.check(w, snap)


# ------------------------------------------------------------------ liquids

def shore(w, size=2):
    """(water tile, anchor of a free size x size buildable block nearby, conduit tiles from the pump's shore to that block, last direction)."""
    t = w.terrain
    wh = [b for b in w.buildings.values() if b["kind"] == "warehouse" and b["faction_name"] == "Red"][0]
    from wizard_rts import territory
    cands = []
    for dy in range(-30, 31):
        for dx in range(-30, 31):
            x, y = wh["tx"] + dx, wh["ty"] + dy
            if t.in_bounds(x, y) and t.is_water(x, y) and territory.in_territory(w, "Red", (x, y)):
                for ddx, ddy in S.DIRS:
                    a = (x + ddx, y + ddy)
                    if t.in_bounds(*a) and t.ground(*a) and C._tile_free(w, a, allow_trees=True) is None and territory.in_territory(w, "Red", a):
                        cands.append((abs(dx) + abs(dy), (x, y)))
                        break
    cands.sort()
    for _d, water in cands[:40]:
        try:
            anchor = F.open_ground(w, "Red", size, size, near=water)
        except RuntimeError:
            continue
        tank_fp = [(anchor[0] + a, anchor[1] + b) for a in range(size) for b in range(size)]
        route = F._route(w, "Red", [water], tank_fp, set(), set())
        if route:
            return water, anchor, route[0], route[1]
    raise RuntimeError("no shore")


def held_liquid(w, name):
    return FL.liquid_held(w).get(name, 0.0)


def test_pump_and_conduit_fill_a_tank_and_the_liquid_books_balance():
    w = world()
    water, anchor, tiles, end_dir = shore(w)
    tank = put(w, "mdy:liquid_container", anchor)
    pump = put(w, "mdy:mechanical_pump", water)
    belt(w, tiles, end_dir, kind="mdy:conduit")
    run(w, 40)
    amt = w.buildings[tank]["mdy"]["liq"].get("water", 0.0)
    assert amt > 20.0, amt
    assert FL.liquid_books(w) == []
    st = S.ind(w)
    assert w.stats["liq_made_water"] > 0 and amt <= R.block("mdy:liquid_container")["liquid_capacity"] + 1e-6


def test_an_open_conduit_end_leaks_and_the_books_still_balance():
    w = world()
    water, anchor, tiles, end_dir = shore(w)
    pump = put(w, "mdy:mechanical_pump", water)
    belt(w, tiles, end_dir, kind="mdy:conduit")  # no tank at the end
    run(w, 20)
    assert w.stats.get("liq_lost_water", 0.0) > 1.0
    assert FL.liquid_books(w) == []


def test_a_belt_can_end_in_a_widelands_warehouse_and_the_wares_join_the_settlement_stock():
    from wizard_rts import construction as con
    w = world()
    wh = con.faction_warehouse(w, "Red")
    # a belt of three tiles whose last tile points at the warehouse tile
    for dx, dy in S.DIRS:
        tiles = [(wh["tx"] - 3 * dx + k * dx, wh["ty"] - 3 * dy + k * dy) for k in range(3)]
        if all(C._tile_free(w, t, allow_trees=True, allow_road=True) is None for t in tiles):
            break
    else:
        import pytest
        pytest.skip("no free approach to the warehouse on this seed")
    for t in tiles:
        tid = w.tree_tiles.get(t)
        if tid:
            from wizard_rts.workers import remove_tree
            remove_tree(w, tid, "test")
    belt(w, tiles, S.DIRS.index((dx, dy)))
    run(w, 1)
    snap = ledger.snapshot_totals(w)
    before = int(w.stocks[wh["id"]].get("mdy.silicon", 0))
    feed(w, tiles[0], "mdy.silicon", 4)
    run(w, 12)
    assert int(w.stocks[wh["id"]].get("mdy.silicon", 0)) - before == 4
    assert not ledger.check(w, snap)
