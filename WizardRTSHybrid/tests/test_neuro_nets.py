"""Genome layout and network forward passes (execution plan T3.1)."""
import numpy as np
import pytest

from neuro import nets as N
from neuro import schema as S


def test_layout_matches_schema_and_sizes_add_up():
    assert [n for n, *_ in N.LAYOUT] == list(dict.fromkeys(n for n, *_ in N.LAYOUT))
    for name, i, h, o in N.LAYOUT:
        assert S.DECLARED[name] == i
    sizes = [v.stop - v.start for v in N.SLOTS.values()]
    assert sum(sizes) == N.genome_size()
    sl = N.slices()
    pos = 0
    for k in N.MODULES:
        assert sl[k][0] == pos
        pos = sl[k][1]
    assert pos == N.genome_size()
    assert N.SLOTS["EMB"].stop - N.SLOTS["EMB"].start == 586 * 8


def test_round_trip_flat_to_modules_to_flat_is_exact():
    g = N.random_genome(np.random.default_rng(1))
    nets = N.Nets(g)
    parts = []
    for k in N.MODULES:
        for key, _shape in N.SLOTS[k].shapes:
            parts.append(nets.w[k][key].reshape(-1))
    assert np.array_equal(np.concatenate(parts), g)
    # views share memory: editing a module edits the genome
    nets.w["H0"]["b1"][0] = 7.0
    assert g[N.SLOTS["H0"].start + 41 * 16] == 7.0


def test_random_genome_is_deterministic_finite_float32():
    a = N.random_genome(np.random.default_rng(5))
    b = N.random_genome(np.random.default_rng(5))
    c = N.random_genome(np.random.default_rng(6))
    assert a.dtype == np.float32 and np.array_equal(a, b) and not np.array_equal(a, c)
    assert np.isfinite(a).all()
    assert np.allclose(N.Nets(a).temp, 1.0)


@pytest.mark.parametrize("rows", [0, 1, 500])
def test_forward_shapes_for_every_network(rows):
    nets = N.Nets(N.random_genome(np.random.default_rng(2)))
    rng = np.random.default_rng(3)
    for name, i, h, o in N.LAYOUT:
        x = rng.normal(0, 1, (rows, i)).astype(np.float32)
        y = nets.forward(name, x)
        assert y.shape == (rows, o) and y.dtype == np.float32 and np.isfinite(y).all()
        if name not in N.LINEAR_OUT and name != "N12":
            assert (np.abs(y) <= 1.0).all()


def test_n12_split_and_card_and_wrong_size_rejected():
    nets = N.Nets(N.random_genome(np.random.default_rng(4)))
    y = nets.forward("N12", np.ones((1, 112), np.float32) * 50)  # extreme input stays finite, representation part squashed
    assert np.abs(y[:, :56]).max() <= 1.0 and np.isfinite(y).all()
    assert N.N12_SPLIT["wait"] == (56, 57)
    hid, score = nets.card(np.zeros((3, 31), np.float32))
    assert hid.shape == (3, 16) and score.shape == (3,)
    hid0, score0 = nets.card(np.zeros((0, 31), np.float32))
    assert hid0.shape == (0, 16) and score0.shape == (0,)
    with pytest.raises(ValueError):
        N.Nets(np.zeros(10, np.float32))


def test_pool_handles_empty_and_extremes():
    m, x = N.pool(np.zeros((0, 4), np.float32), 4)
    assert m.shape == (4,) and x.shape == (4,) and not m.any()
    big = np.full((100000, 3), 1e6, np.float32)
    m, x = N.pool(big, 3)
    assert np.isfinite(m).all() and np.isfinite(x).all()
