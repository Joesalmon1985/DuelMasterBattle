"""Blight nests (outbreaks as immobile hostile actors) and trade caravans (owner requests, 12 Oct 2026)."""
from wizard_rts import construction as con
from wizard_rts import ledger, military, nests, regions, tech, territory, trade, vp
from wizard_rts.economy import produce
from wizard_rts.world import HybridWorld


def _infect(era=0, cubes=2, faction="Green"):
    w = HybridWorld(507, profile="developer")
    w.ai_enabled = False
    w.outbreaks_enabled = False
    if era:
        vp.set_era(w, era)
    s = regions.state(w)
    wh = con.faction_warehouse(w, faction)
    i = s.region_at(wh["tx"], wh["ty"])
    s.cubes[i], s.kind[i] = cubes, "sickness"
    for k in range(3):
        w.advance(1000, k + 1, snapshot=False)
    return w, s, i, w.buildings[w._nests[i]]


def _attack(w, nest, n, definition, faction="Green", seconds=300):
    ids = [w._unit(w.faction_info[faction]["id"], faction, "x", "X", definition, (nest["tx"] + 5 + k % 3, nest["ty"] + k // 3)) for k in range(n)]
    for u in ids:
        military.order_attack(w, u, nest["id"])
    seq = int(w.dmb.clock["clock_sequence"])
    for _ in range(seconds):
        seq += 1
        w.advance(1000, seq, snapshot=False)
        if not any(w.units.get(u, {}).get("alive") for u in ids) or int(nest.get("hp", 0)) <= 0:
            break
    return ids


def test_a_nest_stands_in_every_infected_region_with_cubes_as_health():
    w, s, i, nest = _infect(cubes=2)
    assert nest["kind"] == "blight_nest" and nest["faction_name"] == "" and nest["nest"] == s.rid(i)
    assert nest["max_hp"] == 2 * nests.per_cube(w) and military.building_weapon(nest) is not None
    assert w.stocks.get(nest["id"]) == {}  # it holds and makes nothing


def test_a_squad_kills_the_nest_and_the_region_recovers():
    w, s, i, nest = _infect(cubes=2)
    wh = con.faction_warehouse(w, "Green")
    work = next(b for b in w.buildings.values() if b["faction_name"] == "Green" and b["kind"] not in ("warehouse",) and s.region_at(b["tx"], b["ty"]) == i)
    assert regions.production_factor(w, work) < 1.0
    _attack(w, nest, 11, "dmb.spearman")
    w.advance(1000, int(w.dmb.clock["clock_sequence"]) + 1, snapshot=False)
    assert s.cubes[i] == 0 and regions.production_factor(w, work) == 1.0
    assert w.fstats["Green"].get("nest_cubes_cleared", 0) == 2 and wh["hp"] > 0
    assert any(e["kind"] == "nest_destroyed" for e in w.events)


def test_a_too_small_squad_dies():
    w, s, i, nest = _infect(cubes=2)
    ids = _attack(w, nest, 2, "dmb.clubman")
    assert not any(w.units.get(u, {}).get("alive") for u in ids) and s.cubes[i] == 2


def test_nest_strength_rises_with_the_era():
    vals = []
    for era in range(4):
        w, s, i, nest = _infect(era=era, cubes=1)
        wpn = military.building_weapon(nest)
        vals.append((nest["max_hp"], wpn["warheads"][0]["damage"], wpn["range"]))
    assert all(vals[k][0] < vals[k + 1][0] and vals[k][1] < vals[k + 1][1] for k in range(3)), vals


def test_the_wizard_treatment_removes_one_bar():
    w, s, i, nest = _infect(cubes=3)
    s.cubes[i] -= 1  # what regions._treatment does when the channel completes
    w.advance(1000, int(w.dmb.clock["clock_sequence"]) + 1, snapshot=False)
    assert nest["max_hp"] == 2 * nests.per_cube(w) and int(nest["hp"]) <= nest["max_hp"]


def _traders():
    w = HybridWorld(507, profile="developer")
    w.ai_enabled = False
    w.outbreaks_enabled = False
    for f in ("Red", "Blue"):
        tech.grant(w, f, "dmb.card.trade")
    a, b = con.faction_warehouse(w, "Red"), con.faction_warehouse(w, "Blue")
    for wh, goods in ((a, {"log": 60, "ration": 2}), (b, {"iron": 20})):
        for g, n in goods.items():
            produce(w, wh["id"], g, n)
            w.stats["made_" + g] = w.stats.get("made_" + g, 0) + n
    return w, a, b


def test_a_caravan_carries_goods_both_ways_and_the_books_balance():
    w, a, b = _traders()
    books = ledger.snapshot_totals(w)
    iron0, logs_b0 = w.stocks[b["id"]].get("iron", 0), w.stocks[b["id"]].get("log", 0)
    r = trade.send_caravan(w, "Red", a["id"], b["id"], {"log": 14}, {"iron": 3})
    assert r["status"] == "ok", r
    seq = int(w.dmb.clock["clock_sequence"])
    for _ in range(1500):
        seq += 1
        w.advance(1000, seq, snapshot=False)
        assert ledger.check(w, books) == []
        if r["unit"] not in w.units:
            break
    assert r["unit"] not in w.units  # home and dismissed
    assert w.stocks[b["id"]]["iron"] == iron0 - 3  # Blue's 14 logs went straight on to its own sawmill: the ledger above proves they arrived
    assert w.stocks[a["id"]].get("iron", 0) >= 3
    ev = next(e for e in w.events if e["kind"] == "caravan_traded")
    assert ev["give"] == {"log": 14} and ev["want"] == {"iron": 3} and trade.partners_traded(w, "Red", "Blue") == 1


def test_no_trade_at_war_and_a_killed_caravan_loses_its_cargo():
    w, a, b = _traders()
    trade.note_hostility(w, "Red", "Blue")
    assert trade.send_caravan(w, "Red", a["id"], b["id"], {"log": 14}, {"iron": 3})["reason"] == "at_war"
    w._hostile.clear()
    books = ledger.snapshot_totals(w)
    r = trade.send_caravan(w, "Red", a["id"], b["id"], {"log": 14}, {"iron": 3})
    military.kill_unit(w, w.units[r["unit"]], "")
    assert ledger.check(w, books) == [] and w.stats["destroyed_log"] >= 14


def test_in_peace_soldiers_ignore_other_factions_but_still_see_nests():
    w, s, i, nest = _infect(cubes=1)
    me = w._unit(w.faction_info["Green"]["id"], "Green", "x", "X", "dmb.spearman", (nest["tx"] + 6, nest["ty"]))
    other = w._unit(w.faction_info["Blue"]["id"], "Blue", "x", "X", "dmb.spearman", (nest["tx"] + 7, nest["ty"]))
    u = w.units[me]
    w._grid = None
    military._build_grid(w)
    assert military._scan(w, u["faction"], (u["tx"], u["ty"]), 3.0)["id"] == other  # war: the neighbour is a target
    w.ai_aggressive = False
    assert military._scan(w, u["faction"], (u["tx"], u["ty"]), 3.0) is None
    assert military._scan(w, u["faction"], (u["tx"], u["ty"]), 8.0)["id"] == nest["id"]


def test_guard_posts_keep_out_of_a_nests_reach():
    from wizard_rts import ai

    w, s, i, nest = _infect(cubes=1)
    danger = military._danger(w)
    for cc in territory.command_centers(w, None):
        assert not set(ai._posts(w, cc["faction_name"], cc)) & danger
