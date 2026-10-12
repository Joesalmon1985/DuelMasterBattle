"""The training harness runs end to end on the smoke budget: real weights update, held-out seeds are disjoint, baselines are measured."""
import os

import numpy as np
import pytest

from wizard_rts.learn import domains


@pytest.fixture(autouse=True)
def runs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DMB_RUNS_DIR", str(tmp_path))


def test_duel_policy_trains_and_beats_random_on_held_out_seeds():
    res = domains.train_duel("smoke", seed=1)
    assert res["curve"][-1] < res["curve"][0]  # the loss really fell: weights were updated
    ev = res["eval"]["random"]
    assert ev["net"]["solve_rate"] >= ev["random"]["solve_rate"]
    assert res["seeds"]["train"][1] < res["seeds"]["val"][0] < res["seeds"]["test"][0]  # disjoint ranges
    assert os.path.exists(res["run_dir"] + "/policy.json") and os.path.exists(res["run_dir"] + "/run.json")


def test_dungeon_policy_trains_and_reports_failures_honestly():
    res = domains.train_dungeon("smoke", seed=1)
    assert set(res["eval"]) == {"net_greedy", "net_sampled", "expert", "random"}
    assert res["eval"]["expert"]["solve_rate"] == 1.0  # the content is reachable: the expert solves every held-out dungeon
    assert res["eval"]["net_greedy"]["illegal"] == 0  # the mask makes illegal actions impossible
    assert isinstance(res["failures_by_first_unsolved_puzzle"], dict)


def test_outbreak_policy_runs_and_is_compared_with_noop_and_greedy():
    res = domains.train_outbreak("smoke", seed=1)
    d = res["eval"]["default"]
    assert {"net", "greedy", "random", "noop"} <= set(d) and "ci95_lo" in d["net_vs_noop_return"]
    assert d["noop"]["loss_rate"] >= d["greedy"]["loss_rate"]


def test_training_is_seed_reproducible():
    a = domains.train_duel("smoke", seed=3)
    b = domains.train_duel("smoke", seed=3)
    assert a["curve"] == b["curve"]
