"""T4.2: the manifest records what decides reuse, and compatibility follows design 10.4."""
import copy

from neuro import manifest as M
from neuro.curriculum import Curriculum
from wizard_rts import RULES_VERSION, freeze


def test_default_manifest_says_level_c0_scale_one_and_records_the_versions():
    m = M.build({})
    assert m["catastrophe_level"] == "C0" and m["outbreak_interval_scale"] == 1.0
    assert m["curriculum"] == Curriculum().to_json()
    assert m["rules_version"] == RULES_VERSION == "rules-2026-10-14"
    assert m["roster_version"] == freeze.ROSTER_VERSION and m["roster_hash"] == freeze.roster_hash()
    assert m["architecture"]["genome_size"] == 87430 and m["obs_schema"]["version"] == "obs-1.0.0" and len(m["wizard_rts_sha256"]) == 64
    assert m["act_schema_version"] == "act-1.0.0" and m["fit_schema_version"] == "fit-1.0.0"
    assert m["hardware"]["cpu_count"] and m["numpy"] and m["python"]
    assert {"sha", "dirty"} <= set(m["git"])


def test_compatibility_rule():
    a = M.build({})
    assert M.compatible(a, copy.deepcopy(a)) == "same"
    b = copy.deepcopy(a)
    b["rules_version"] = "rules-2099-01-01"
    assert M.compatible(a, b) == "reevaluate"
    b = copy.deepcopy(a)
    b["catastrophe_level"], b["outbreak_interval_scale"] = "C1", 0.5
    assert M.compatible(a, b) == "reevaluate"
    for path, val in ((("roster_version",), "roster-9.0.0"), (("architecture", "version"), "arch-9"), (("obs_schema", "version"), "obs-9"),
                      (("act_schema_version",), "act-9"), (("fit_schema_version",), "fit-9"), (("roster_hash",), "x")):
        b = copy.deepcopy(a)
        d = b
        for k in path[:-1]:
            d = d[k]
        d[path[-1]] = val
        assert M.compatible(a, b) == "incompatible", path
    b = copy.deepcopy(a)
    b["git"]["sha"], b["wizard_rts_sha256"] = "other", "other"  # code differences alone are recorded, not compared
    assert M.compatible(a, b) == "same"
    assert M.differences(a, b) == {"incompatible": [], "reevaluate": []}


def test_the_config_and_a_two_rung_curriculum_are_recorded():
    cfg = {"curriculum": {"levels": {"C0": 1.0, "C1": 0.5}, "current": "C1"}, "population": 4}
    m = M.build(cfg)
    assert m["catastrophe_level"] == "C1" and m["outbreak_interval_scale"] == 0.5 and m["config"]["population"] == 4
    assert M.compatible(M.build({}), m) == "reevaluate"


def test_tree_hash_changes_with_content(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    h1 = M.tree_hash(tmp_path)
    M._cache.clear()
    (tmp_path / "a.py").write_text("x = 2\n")
    assert M.tree_hash(tmp_path) != h1
    M._cache.clear()
