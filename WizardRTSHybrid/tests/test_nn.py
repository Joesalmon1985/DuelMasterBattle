"""The NumPy network really learns: gradient check, XOR, masked softmax and policy-gradient direction."""
import numpy as np
import pytest

from wizard_rts.learn import nn


def test_backprop_matches_numerical_gradients():
    net = nn.MLP([4, 5, 3], seed=1, out_scale=1.0)
    rng = np.random.RandomState(0)
    x = rng.randn(6, 4)
    t = rng.randint(0, 3, size=6)

    def loss(n):
        out, _ = n.forward(x)
        return nn.xent_grad(out, None, t)[0]

    out, acts = net.forward(x)
    _l, dlog = nn.xent_grad(out, None, t)
    gW, gb = net.backward(dlog, acts)
    eps = 1e-6
    for li in range(len(net.W)):
        for idx in [(0, 0), (1, 2), (2, 1)]:
            if idx[0] >= net.W[li].shape[0] or idx[1] >= net.W[li].shape[1]:
                continue
            net.W[li][idx] += eps
            up = loss(net)
            net.W[li][idx] -= 2 * eps
            down = loss(net)
            net.W[li][idx] += eps
            assert gW[li][idx] == pytest.approx((up - down) / (2 * eps), rel=1e-4, abs=1e-7)


def test_learns_xor():
    net = nn.MLP([2, 8, 2], seed=3, out_scale=1.0)
    x = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], float)
    y = np.array([0, 1, 1, 0])
    for _ in range(1500):
        out, acts = net.forward(x)
        _l, g = nn.xent_grad(out, None, y)
        net.step(*net.backward(g, acts), lr=0.03)
    assert (net.predict(x).argmax(axis=1) == y).all()


def test_mask_makes_illegal_actions_impossible():
    p = nn.masked_softmax(np.array([[10.0, 0.0, 0.0]]), np.array([[0, 1, 1]]))
    assert p[0, 0] == 0.0 and p[0, 1] == pytest.approx(0.5)


def test_policy_gradient_raises_the_probability_of_advantaged_actions():
    net = nn.MLP([1, 4, 3], seed=2)
    x = np.ones((8, 1))
    acts = np.array([2] * 8)
    for _ in range(300):
        out, cache = net.forward(x)
        _l, g = nn.policy_gradient(out, None, acts, np.ones(8), entropy_coef=0.0)
        net.step(*net.backward(g, cache), lr=0.02)
    assert nn.masked_softmax(net.predict(x[:1]), None)[0, 2] > 0.9


def test_save_and_load_roundtrip(tmp_path):
    net = nn.MLP([3, 4, 2], seed=5)
    path = str(tmp_path / "m.json")
    net.save(path)
    other = nn.MLP.load(path)
    x = np.random.RandomState(1).randn(2, 3)
    assert np.allclose(net.predict(x), other.predict(x))
