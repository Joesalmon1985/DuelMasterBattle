"""T2.1 and T2.2: the observation schema, the static tables, and the per-decision features (shapes, finiteness, determinism, no hidden information)."""
import json

import numpy as np
import pytest

from neuro import features as F
from neuro import schema as S
from wizard_rts import freeze


# ------------------------------------------------------------------------------------------------------------------------------ T2.1: schema
def test_every_declared_input_width_is_reproduced_by_the_schema():
    for name, width in S.DECLARED.items():
        assert S.DIMS[name] == width, name
    assert S.N_STATIC == 24 and len(S.UNIT_STATIC_COLUMNS) == 12 and len(S.KEY_WARES) == 24 and len(S.GROUP_NAMES) == 6


def test_compose_orders_and_checks_the_parts():
    n2 = S.compose("N2", n1_mean=np.ones((3, 16)), n1_max=2 * np.ones((3, 16)), n1_count=np.full((3, 1), 3.0), n1_damaged=4 * np.ones((3, 16)), raw=5 * np.ones((3, 51)))
    assert n2.shape == (3, 100) and n2.dtype == np.float32
    assert (n2[0, :16] == 1).all() and (n2[0, 16:32] == 2).all() and n2[0, 32] == 3 and (n2[0, 33:49] == 4).all() and (n2[0, 49:] == 5).all()
    with pytest.raises(ValueError):
        S.compose("N2", n1_mean=np.ones((3, 15)), n1_max=np.ones((3, 16)), n1_count=np.ones((3, 1)), n1_damaged=np.ones((3, 16)), raw=np.ones((3, 51)))
    with pytest.raises(KeyError):
        S.compose("N2", n1_mean=np.ones((3, 16)))
    one = S.compose("H0", ctx=np.ones(32), prio=np.zeros(8), raw=np.ones(1))  # a single row may be 1-D
    assert one.shape == (41,)


def test_raw_names_are_unique_within_each_vector():
    for name, fields in S.RAW_NAMES.items():
        assert len(set(fields)) == len(fields), name
    for head, fields in S.HEAD_RAW.items():
        assert len(set(fields)) == len(fields), head


# ------------------------------------------------------------------------------------------------------------------------------ T2.1: tables
def test_the_kind_index_is_the_frozen_roster_plus_three_core_kinds():
    ids = freeze.manifest()["entities"]
    idx = F.kind_index()
    assert len(ids) == 582 and F.n_kinds() == 1 + 582 + 3 == 586
    assert [idx[k] for k in ids] == list(range(1, 583))  # manifest order, row 0 reserved for "unknown"
    assert {k: idx[k] for k in F.EXTRA_KINDS} == {"warehouse": 583, "blight_nest": 584, "unit:soldier": 585}
    assert F.building_kind_row("no-such-kind") == 0 and F.unit_kind_row("no-such-unit") == 0
    assert F.unit_kind_row("soldier") == 585 and F.unit_kind_row("settlers") == idx["unit:settlers"]


def test_kind_static_has_the_declared_shape_and_sensible_rows():
    ks = F.kind_static()
    assert ks.shape == (586, 24) and ks.dtype == np.float32 and np.isfinite(ks).all() and (ks >= 0).all() and (ks <= 5).all()
    assert (ks[0] == 0).all()  # the unknown row
    col = {c: i for i, c in enumerate(S.KIND_STATIC_COLUMNS)}
    assert (ks[1:583, :4].sum(axis=1) == 1).all()  # exactly one game per roster entity
    assert int(ks[:, col["is_unit"]].sum()) == 96 + 1  # the roster's units and the Widelands soldier
    idx = F.kind_index()
    assert ks[idx["clinic"], col["is_clinic"]] == 1 and ks[idx["warehouse"], col["is_centre"]] == 1 and ks[idx["unit:settlers"], col["is_centre"]] == 1
    assert ks[idx["barracks"], col["is_factory"]] == 1 and ks[idx["mdy:duo"], col["is_military"]] == 1
    assert ks[idx["wl:barbarians_coalmine"], col["produces_metal"]] == 1 and ks[idx["wl:barbarians_coalmine"], col["consumes_food"]] == 1
    us = F.unit_static()
    assert us.shape == (586, 12) and np.isfinite(us).all()
    ucol = {c: i for i, c in enumerate(S.UNIT_STATIC_COLUMNS)}
    assert (us[:, [ucol["loco_foot"], ucol["loco_ground_vehicle"], ucol["loco_air"], ucol["loco_naval"]]].sum(axis=1)[[idx[k] for k in freeze.manifest()["units"]]] == 1).all()


def test_every_ware_has_a_group():
    assert [w for w in freeze.manifest()["wares"] if F.group_of(w) is None] == []
    assert [w for w in S.KEY_WARES if F.group_of(w) is None] == []
    mdy = json.loads((freeze.DATA_DIR / "mindustry_defs.json").read_text(encoding="utf-8"))
    assert {F.group_of("mdy." + i) for i in mdy["items"]} == {5}
    assert F.group_of("log") == 1 and F.group_of("ration") == 0 and F.group_of("iron") == 3 and F.group_of("granite") == 2 and F.group_of("ax") == 4
    assert F.group_of("no-such-ware") is None and F.groups_of(["log", "iron"]).tolist() == [0, 1, 0, 1, 0, 0]


def test_the_schema_hash_is_stable_and_follows_the_schema_and_the_roster():
    h = F.obs_schema_hash()
    assert h == F.obs_schema_hash() and len(h) == 64
    assert S.schema_hash("x") != S.schema_hash("y")
    assert S.schema_hash(freeze.roster_hash(freeze.manifest())) == h


# ====================================================================================================================== T2.2: per-decision features
import os
import subprocess
import sys
import time
from pathlib import Path

from neuro import vision
from neuro.observer import FactionObserver
from neuro_worlds import digest, fresh_world, world_at
from wizard_rts import construction as con
from wizard_rts import history, territory
from wizard_rts.industry import fixture as IF
from wizard_rts.world import HybridWorld

WIDTH = {"b_raw": 24, "s_raw": 51, "u_raw": 20, "e_raw": 20, "n4_raw": 78, "n5_raw": 12, "n6_raw": 16, "n7_raw": 44, "n8_raw": 18, "n10_raw": 3, "n12_raw": 28,
         "card_raw": 31, "n13_slots": 16, "n14_regions": 10, "n14_global": 8}
FACTIONS = ("Red", "Blue", "Green", "Yellow", "Purple", "Orange")


def observe(world, faction, t=1200):
    return FactionObserver(world, faction).observe(t)


def check_observation(o):
    for name, width in WIDTH.items():
        a = getattr(o, name)
        assert a.dtype == np.float32 and a.shape[-1] == width, (name, a.shape)
        assert np.isfinite(a).all() and (np.abs(a) <= 5.0).all(), name
    assert o.n13_slots.shape == (8, 16) and o.n14_worst.shape == (3,) and len(o.n14_regions) == 25
    assert o.b_raw.shape[0] == len(o.b_ids) == len(o.b_kind) == len(o.b_settlement)
    assert o.s_raw.shape[0] == len(o.s_ids) == len(o.s_members) == len(o.s_damaged) == len(o.s_centre)
    assert o.u_raw.shape[0] == len(o.u_ids) == len(o.u_kind) == len(o.u_armed) and o.e_raw.shape[0] == len(o.e_ids) == len(o.e_kind) == len(o.e_faction)
    assert o.card_raw.shape[0] == len(o.card_ids)
    assert (o.b_kind >= 0).all() and (o.b_kind < F.n_kinds()).all() and (o.u_kind < F.n_kinds()).all() and (o.e_kind < F.n_kinds()).all()
    assert (o.b_settlement < len(o.s_ids)).all()
    covered = sorted(int(i) for m in o.s_members for i in m)
    assert covered == sorted(set(covered)) and covered == sorted(int(i) for i in np.flatnonzero(o.b_settlement >= 0))  # every building belongs to exactly one settlement
    for j, m in enumerate(o.s_members):
        assert (o.s_damaged[j] == -1) == (len(m) == 0) and (len(m) == 0 or int(o.s_damaged[j]) in set(int(i) for i in m))
    assert -1 <= o.s_threatened < len(o.s_ids) and -1 <= o.s_weakest < len(o.s_ids)
    assert all(f != o.faction for f in o.n13_factions) and len(o.n13_factions) <= 8
    assert ((o.n14_worst >= -1) & (o.n14_worst < len(o.n14_regions))).all()
    assert len(o.expansion_sites) <= 4


def test_features_have_the_declared_shapes_on_a_fresh_world():
    w = fresh_world()
    for f in FACTIONS:
        o = observe(w, f, 0)
        check_observation(o)
        assert len(o.s_ids) == 1 and len(o.u_ids) >= 1 and o.e_raw.shape == (0, 20)
        assert o.n6_raw[S.N6_RAW.index("known_buildings")] == 0 and o.n13_slots[:, S.N13_SLOT.index("known")].sum() == 0  # nobody knows anybody yet


def test_features_have_the_declared_shapes_in_a_developed_world():
    w = world_at(20)
    for f in FACTIONS:
        o = observe(w, f)
        check_observation(o)
        assert len(o.b_ids) >= 5 and len(o.s_ids) >= 1


def test_features_have_the_declared_shapes_for_a_faction_with_nothing_left():
    w = world_at(20)
    for b in [b for b in w.buildings.values() if b["faction_name"] == "Orange"]:
        w.buildings[b["id"]]["hp"] = 0
    for u in [u for u in w.units.values() if u["faction_name"] == "Orange"]:
        u["alive"] = False
    o = observe(w, "Orange")
    check_observation(o)
    assert len(o.b_ids) == 0 and len(o.u_ids) == 0 and len(o.s_ids) == 0 and o.s_threatened == -1 and o.s_weakest == -1


def test_the_modern_era_adds_machines_belts_and_power_without_breaking_the_shapes():
    w = HybridWorld(507, profile="developer")
    w.ai_enabled = False
    IF.modern_fixture(w, "Red")
    for i in range(30):
        w.advance(1000, i + 1, snapshot=False)
    o = observe(w, "Red", 30)
    check_observation(o)
    assert o.n5_raw[S.N5_RAW.index("belt_tiles")] > 0
    assert any(k > 0 for k in o.b_kind)


def test_open_offers_become_card_rows():
    w = fresh_world()
    w.advance(1000, 1, snapshot=False)  # the first draft round opens at one second; the AI picks a few seconds later
    offers = w.tech["Red"]["offers"]
    assert offers
    o = observe(w, "Red", 1)
    assert sorted(o.card_ids) == sorted(offers) and o.card_raw.shape == (len(offers), 31)
    check_observation(o)
    assert o.n8_raw[S.N8_RAW.index("offers")] == pytest.approx(len(offers) / 7.0)


def test_every_building_and_unit_kind_in_play_has_a_row():
    w = world_at(20)
    ks = set(F.kind_index())
    for b in w.buildings.values():
        assert b["kind"] in ks, b["kind"]
    for u in w.units.values():
        assert "unit:" + u["kind"] in ks, u["kind"]


# ---------------------------------------------------------------------------------------------------------------------------- determinism
def test_the_same_world_gives_the_same_features():
    w = world_at(20)
    a = observe(w, "Red").arrays()
    b = observe(w, "Red").arrays()
    assert digest(a) == digest(b)
    c = world_at(20)
    assert digest(observe(c, "Red").arrays()) == digest(a)  # an independent clone of the same game


def _digest_in_subprocess(hashseed):
    root, repo, tests = Path(__file__).resolve().parents[1], Path(__file__).resolve().parents[2], Path(__file__).resolve().parent
    code = (f"import sys; sys.path[:0] = [{str(root)!r}, {str(repo)!r}, {str(tests)!r}]\n"
            "from neuro_worlds import world_at, digest\n"
            "from neuro.observer import FactionObserver\n"
            "w = world_at(4)\n"
            "print(digest({**FactionObserver(w, 'Red').observe(240).arrays(), **FactionObserver(w, 'Blue').observe(240).arrays()}))\n")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env={**os.environ, "PYTHONHASHSEED": str(hashseed)}, timeout=900)
    assert out.returncode == 0, out.stderr[-2000:]
    return out.stdout.strip().splitlines()[-1]


def test_features_do_not_depend_on_the_hash_seed():
    assert _digest_in_subprocess(1) == _digest_in_subprocess(2)


# ---------------------------------------------------------------------------------------------------------------------------- hidden information
def _scramble_what_a_faction_cannot_see(w, me):
    """Change everything about the other factions that `me` has not seen and that is not public: stocks, hit points, internal counters, offers,
    unrest, and the world's global counters. Public facts (VP, era, outbreaks, collapse) are left alone."""
    seen = vision.seen_enemies(w, me)
    seen_b = {r["id"] for r in seen["buildings"]} | set(vision.memory_of(w, me))
    seen_u = {r["id"] for r in seen["units"]}
    for b in w.buildings.values():
        if b["faction_name"] not in (me, "") and b["id"] not in seen_b and "hp" in b and b["id"] in w.stocks:
            for g in list(w.stocks[b["id"]]):
                w.stocks[b["id"]][g] = int(w.stocks[b["id"]][g]) + 37
            b["hp"] = max(1, int(b["hp"]) // 2)
            w.shortages[(b["id"], "log")] = w.shortages.get((b["id"], "log"), 0) + 50
    for u in w.units.values():
        if u["faction_name"] not in (me, "") and u["id"] not in seen_u and u.get("alive", True):
            u["hp"] = max(1, int(u["hp"]) // 2)
    for n in w.faction_info:
        if n == me:
            continue
        w.fstats.setdefault(n, {})["unit_kills"] = w.fstats.get(n, {}).get("unit_kills", 0) + 100
        w.fstats[n]["kill_value"] = w.fstats[n].get("kill_value", 0) + 99999
        flow = w.__dict__.setdefault("ware_flow", {}).setdefault(n, {"made": {}, "consumed": {}})
        flow["made"]["log"] = flow["made"].get("log", 0) + 5000
        w.tech[n]["round"] = int(w.tech[n].get("round", 0)) + 1
        w.tech[n]["offers"] = list(reversed(w.tech[n].get("offers", [])))
        for rec in w.dmb.settlements.values():
            if rec["faction"] == n:
                rec["unrest"] = min(1.0, float(rec.get("unrest", 0)) + 0.3)
    for g in ("log", "granite", "fish", "ration"):  # the world's global counters mix every faction
        w.stats["made_" + g] = w.stats.get("made_" + g, 0) + 1000
        w.stats["consumed_" + g] = w.stats.get("consumed_" + g, 0) + 1000
    w.stats["deliver"] = w.stats.get("deliver", 0) + 5000


@pytest.mark.parametrize("me", ["Red", "Green", "Orange"])
def test_changes_to_what_a_faction_cannot_see_leave_its_features_untouched(me):
    a, b = world_at(20), world_at(20)
    before = observe(a, me)
    _scramble_what_a_faction_cannot_see(b, me)
    after = observe(b, me)
    assert before.b_ids == after.b_ids and before.u_ids == after.u_ids and before.e_ids == after.e_ids and before.s_ids == after.s_ids
    for name, arr in before.arrays().items():
        assert np.array_equal(arr, getattr(after, name)), name


def test_the_scramble_does_change_the_world_and_a_sighting_changes_the_features():
    a, b = world_at(20), world_at(20)
    me = "Red"
    _scramble_what_a_faction_cannot_see(b, me)
    assert b.stats["made_log"] == a.stats["made_log"] + 1000  # the control: the scramble really changed things
    before = observe(a, me)
    wh = con.faction_warehouse(a, me)
    foe = next(u for u in a.units.values() if u["faction_name"] == "Blue" and u.get("alive", True))
    foe["tx"], foe["ty"] = wh["tx"] + 4, wh["ty"]
    after = observe(a, me)
    assert before.e_ids == [] and foe["id"] in after.e_ids
    assert not np.array_equal(before.n6_raw, after.n6_raw) and after.n6_raw[S.N6_RAW.index("enemy_count")] > 0


def test_a_remembered_building_that_is_destroyed_out_of_sight_stays_in_the_features():
    w = world_at(20)
    me = "Red"
    blue = con.faction_warehouse(w, "Blue")
    from wizard_rts import visibility

    visibility.remember(w, me, blue)  # Red saw it once (a sighting writes the memory; controllers cannot)
    first = observe(w, me)
    w.buildings[blue["id"]]["hp"] = 0  # destroyed while nobody of Red looks
    w.buildings[blue["id"]]["destroyed"] = True
    again = observe(w, me)
    k = S.N6_RAW.index("known_buildings")
    assert first.n6_raw[k] == again.n6_raw[k] > 0  # the stale memory is what the faction knows


def test_a_settlement_row_depends_on_its_own_state_not_on_how_many_settlements_the_faction_has():
    me = "Red"
    a, b = world_at(20), world_at(20)
    base = observe(a, me)
    target = base.s_ids[0]
    cc = a.buildings[base.s_centre[0]]
    far = []
    t = b.terrain
    for y in range(8, t.h - 8, 8):
        for x in range(8, t.w - 8, 8):
            if len(far) >= 3:
                break
            if all(territory.cheb((x, y), (c["tx"], c["ty"])) > 150 for c in territory.command_centers(b, me)):
                u = {"id": "u", "definition": territory.SETTLER_DEFINITION, "faction_name": me, "alive": True, "tx": x, "ty": y}
                if territory.deploy_check(b, u) is None:
                    uid = b._unit(b.faction_info[me]["id"], me, "settlers", "Settlers", territory.SETTLER_DEFINITION, (x, y))
                    territory._create_command_center(b, b.units[uid])
                    far.append((x, y))
    assert len(far) >= 2, "no far-away sites for extra settlements"
    for a_ in (a, b):  # an enemy unit stands beside the target settlement in both worlds
        for k, foe in enumerate([u for u in a_.units.values() if u["faction_name"] != me and u.get("alive", True) and u.get("weapon")][:6]):
            foe["tx"], foe["ty"] = cc["tx"] + 5, cc["ty"] + k  # a real raid: more enemy strength than the settlement's own defenders
    one, many = observe(a, me), observe(b, me)
    assert len(many.s_ids) == len(one.s_ids) + len(far)
    assert np.array_equal(one.s_raw[one.s_ids.index(target)], many.s_raw[many.s_ids.index(target)])
    assert one.s_ids[one.s_threatened] == target == many.s_ids[many.s_threatened]  # the most threatened settlement survives pooling with 1 or with many


def test_a_split_successor_is_its_own_faction_for_the_features():
    w = world_at(20)
    red = observe(w, "Red")
    rec = next(r for r in w.dmb.settlements.values() if r["faction"] == "Red" and not r.get("home") and r["state"] == "standing")
    successor = history.split(w, "Red", rec)
    parent, child = observe(w, "Red"), observe(w, successor)
    check_observation(parent)
    check_observation(child)
    assert set(parent.b_ids).isdisjoint(child.b_ids) and set(parent.u_ids).isdisjoint(child.u_ids)
    assert rec["id"] in child.s_ids and rec["id"] not in parent.s_ids and successor not in child.n13_factions and "Red" in child.n13_factions
    assert successor in parent.n13_factions and len(parent.b_ids) + len(child.b_ids) == len(red.b_ids)


def test_production_is_attributed_to_the_faction_that_made_it():
    w = world_at(20)
    flow = w.ware_flow
    for ware in ("log", "granite", "fish", "meat"):
        total = sum(flow[f]["made"].get(ware, 0) for f in flow)
        assert total == w.stats.get("made_" + ware, 0), ware  # nothing is lost and nothing is double counted
    assert sum(1 for f in flow if flow[f]["made"].get("log", 0) > 0) == 6 and len({flow[f]["made"].get("log", 0) for f in flow}) > 1  # each faction has its own number
    per_building = sum(sum(v["made"].values()) for v in w.ware_flow_b.values())
    assert per_building == sum(sum(f["made"].values()) for f in flow.values())
    o = observe(w, "Red")
    assert o.n4_raw[S.N4_RAW.index("stock_log")] > 0


def test_seen_enemies_matches_the_per_point_definition():
    w = world_at(20)
    for f in FACTIONS:
        srcs = vision.sources(w, f)
        got = vision.seen_enemies(w, f)
        want_b = [b["id"] for b in w.buildings.values() if b.get("faction_name") not in (f, None) and "hp" in b and int(b["hp"]) > 0 and not b.get("destroyed")
                  and vision.visible(w, f, b["tx"], b["ty"], srcs)]
        want_u = [u["id"] for u in w.units.values() if u.get("faction_name") not in (f, None) and u.get("alive", True) and not u.get("inside") and not u.get("cloaked")
                  and vision.visible(w, f, u["tx"], u["ty"], srcs)]
        assert [r["id"] for r in got["buildings"]] == want_b and [r["id"] for r in got["units"]] == want_u


# ---------------------------------------------------------------------------------------------------------------------------- cost
def test_feature_assembly_time_is_reported_and_bounded():
    w = world_at(20)
    ts = {}
    for f in FACTIONS:
        ob = FactionObserver(w, f)
        ob.observe(1140)
        t = time.perf_counter()
        for i in range(10):
            ob.observe(1200 + 60 * i)
        ts[f] = (time.perf_counter() - t) / 10 * 1000
    print("feature assembly ms per decision at minute 20:", {k: round(v, 2) for k, v in ts.items()}, "mean", round(sum(ts.values()) / len(ts), 2))
    assert max(ts.values()) < 60.0  # a pathology guard; the target (15 ms) is reported in the milestone evidence


# ---------------------------------------------------------------------------------------------------------------------------- two more leak checks
def test_outbreak_cubes_in_regions_the_faction_has_not_seen_stay_hidden():
    from wizard_rts import regions

    a, b = world_at(20), world_at(20)
    me = "Green"
    before = observe(a, me)
    rg = regions.state(b)
    seen = vision.visible_regions(b, me)
    assert len(seen) < len(rg.cubes)
    for i in range(len(rg.cubes)):
        if i not in seen:
            rg.cubes[i] = (rg.cubes[i] + 2) % 4  # the world changes where Green is not looking
    after = observe(b, me)
    assert any(rg.cubes[i] != regions.state(a).cubes[i] for i in range(len(rg.cubes)))
    for name, arr in before.arrays().items():
        assert np.array_equal(arr, getattr(after, name)), name


def test_an_expansion_site_is_not_dropped_because_of_something_the_faction_has_not_seen():
    w = world_at(20)
    me = "Blue"
    sites = observe(w, me).expansion_sites
    assert sites
    srcs = vision.sources(w, me)
    hidden = [t for t in sites if not vision.visible(w, me, t[0], t[1], srcs)]
    assert hidden  # at least one offered site lies outside the faction's sight
    for t in hidden:
        w.blocked.add(t)  # an unseen enemy building (or anything else) now stands on each of them
        w.blocked.update(territory.footprint(t, territory.SETTLER_DEFINITION))
    assert observe(w, me).expansion_sites == sites


def test_the_schema_document_is_current():
    out = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "dump_obs_schema.py"), "--check"], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, "docs/NEURO_OBS_SCHEMA.md is stale: run py -3 WizardRTSHybrid/scripts/dump_obs_schema.py"


PINNED_SCHEMA_HASH = "f6e5375ea1330bb1b6fc3c915b9f049ac31a3ed1c95cdb537238613555f0f892"


def test_the_schema_hash_is_pinned():
    """Changing any field list, width or ware group, or the roster, changes the observation a trained model was built for. Update this constant (and bump
    schema.OBS_SCHEMA_VERSION and regenerate docs/NEURO_OBS_SCHEMA.md) only on purpose."""
    assert F.obs_schema_hash() == PINNED_SCHEMA_HASH
