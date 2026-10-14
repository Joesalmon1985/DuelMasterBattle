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
