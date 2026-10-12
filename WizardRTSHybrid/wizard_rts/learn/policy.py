"""Masked categorical policies, behaviour cloning, DAgger and REINFORCE on the environment contract (`reset`, `step`, `encode`, `legal_mask`)."""

from __future__ import annotations

from typing import Any, Callable

import numpy as np

from wizard_rts.learn import nn


class Policy:
    def __init__(self, in_dim: int, n_actions: int, hidden: tuple[int, ...] = (128, 64), seed: int = 0) -> None:
        self.net = nn.MLP([in_dim, *hidden, n_actions], seed=seed)
        self.n = n_actions
        self.rng = np.random.RandomState(seed + 1)

    def probs(self, x: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
        return nn.masked_softmax(self.net.predict(x), None if mask is None else np.atleast_2d(mask))

    def act(self, x: np.ndarray, mask: np.ndarray | None, greedy: bool = False) -> int:
        p = self.probs(x, mask)[0]
        return int(np.argmax(p)) if greedy else nn.sample(p, self.rng)

    def save(self, path: str) -> None:
        self.net.save(path)

    @classmethod
    def load(cls, path: str) -> "Policy":
        net = nn.MLP.load(path)
        p = cls(net.sizes[0], net.sizes[-1], tuple(net.sizes[1:-1]))
        p.net = net
        return p


def behaviour_clone(policy: Policy, X: np.ndarray, Y: np.ndarray, M: np.ndarray | None, epochs: int = 30, lr: float = 2e-3, batch: int = 128, seed: int = 0,
                    weights: np.ndarray | None = None) -> list[float]:
    rng = np.random.RandomState(seed)
    curve = []
    n = len(X)
    for ep in range(epochs):
        order = rng.permutation(n)
        total = 0.0
        for i in range(0, n, batch):
            idx = order[i:i + batch]
            out, acts = policy.net.forward(X[idx])
            loss, g = nn.xent_grad(out, None if M is None else M[idx], Y[idx], None if weights is None else weights[idx])
            policy.net.step(*policy.net.backward(g, acts), lr=lr)
            total += loss * len(idx)
        curve.append(total / n)
    return curve


def rollout(env, policy_fn: Callable[[Any, np.ndarray, np.ndarray], int], seed: int, max_steps: int = 10_000, **scenario: Any) -> dict[str, Any]:
    """One episode; returns observations (encoded), masks, actions, rewards and the final reason."""
    env.reset(seed, **scenario)
    X, M, A, R = [], [], [], []
    for _ in range(max_steps):
        x, m = env.encode(), env.legal_mask()
        a = policy_fn(env, x, m)
        _o, r, term, trunc, _i = env.step(a)
        X.append(x)
        M.append(m)
        A.append(a)
        R.append(r)
        if env.done:
            break
    return {"X": np.array(X), "M": np.array(M), "A": np.array(A), "R": np.array(R), "reason": env.reason, "return": float(np.sum(R))}


def reinforce(policy: Policy, env, seeds: list[int], iterations: int, episodes_per_iter: int = 8, gamma: float = 0.97, lr: float = 1e-3, entropy: float = 0.01,
              baseline: str = "mean", on_iter: Callable[[int, dict[str, Any]], None] | None = None, **scenario: Any) -> list[dict[str, Any]]:
    """Plain REINFORCE with a per-timestep mean baseline and advantage normalisation. `seeds` is cycled; the caller keeps train/val/test disjoint."""
    curve = []
    k = 0
    for it in range(iterations):
        eps = []
        for _ in range(episodes_per_iter):
            eps.append(rollout(env, lambda e, x, m: policy.act(x, m, greedy=False), seeds[k % len(seeds)], **scenario))
            k += 1
        X = np.concatenate([e["X"] for e in eps])
        M = np.concatenate([e["M"] for e in eps])
        A = np.concatenate([e["A"] for e in eps])
        G = np.concatenate([nn.discounted(list(e["R"]), gamma) for e in eps])
        T = np.concatenate([np.arange(len(e["R"])) for e in eps])
        adv = G.copy()
        if baseline == "mean":
            for t in np.unique(T):
                sel = T == t
                adv[sel] = G[sel] - G[sel].mean()
        adv = (adv - adv.mean()) / (adv.std() + 1e-8)
        out, acts = policy.net.forward(X)
        loss, g = nn.policy_gradient(out, M, A, adv, entropy)
        policy.net.step(*policy.net.backward(g, acts), lr=lr)
        row = {"iter": it, "mean_return": float(np.mean([e["return"] for e in eps])), "loss": loss, "episodes": k}
        curve.append(row)
        if on_iter:
            on_iter(it, row)
    return curve


def evaluate(env, policy_fn: Callable[[Any, np.ndarray, np.ndarray], int], seeds: list[int], metric: Callable[[Any], dict[str, float]], **scenario: Any) -> list[dict[str, float]]:
    out = []
    for s in seeds:
        env.reset(s, **scenario)
        for _ in range(env.max_steps + 5):
            if env.done:
                break
            env.step(policy_fn(env, env.encode(), env.legal_mask()))
        out.append({"seed": s, "return": env.return_, **metric(env)})
    return out


def paired_stats(a: list[float], b: list[float], n_boot: int = 2000, seed: int = 0) -> dict[str, float]:
    """Mean difference a-b over paired seeds with a bootstrap 95% interval and the share of seeds where a >= b."""
    d = np.array(a) - np.array(b)
    rng = np.random.RandomState(seed)
    boots = [float(d[rng.randint(0, len(d), len(d))].mean()) for _ in range(n_boot)]
    return {"mean_a": float(np.mean(a)), "mean_b": float(np.mean(b)), "diff": float(d.mean()), "ci95_lo": float(np.percentile(boots, 2.5)), "ci95_hi": float(np.percentile(boots, 97.5)),
            "a_ge_b": float(np.mean(d >= 0)), "n": len(d)}
