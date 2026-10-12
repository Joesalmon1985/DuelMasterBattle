"""NumPy MLP with manual backpropagation, Adam, masked categorical policies and policy-gradient helpers.

Chosen over PyTorch because the machine has no torch/gymnasium and the policies are small (a few thousand parameters, CPU only,
seconds to train). `docs/TRAINING_PROGRAMME.md` documents an optional PyTorch/Gymnasium adapter for later; nothing here depends on it.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np


class MLP:
    """Fully connected net with tanh hidden layers and a linear output. Parameters are plain arrays (saved as JSON, no pickle)."""

    def __init__(self, sizes: list[int], seed: int = 0, out_scale: float = 0.1) -> None:
        rng = np.random.RandomState(seed)
        self.sizes = list(sizes)
        self.W = [rng.randn(a, b) * np.sqrt(1.0 / a) for a, b in zip(sizes[:-1], sizes[1:])]
        self.b = [np.zeros(b) for b in sizes[1:]]
        self.W[-1] *= out_scale
        self.opt: Adam | None = None

    # ---- forward / backward
    def forward(self, x: np.ndarray) -> tuple[np.ndarray, list[np.ndarray]]:
        acts = [np.atleast_2d(x).astype(np.float64)]
        h = acts[0]
        for i, (w, b) in enumerate(zip(self.W, self.b)):
            z = h @ w + b
            h = z if i == len(self.W) - 1 else np.tanh(z)
            acts.append(h)
        return h, acts

    def predict(self, x: np.ndarray) -> np.ndarray:
        return self.forward(x)[0]

    def backward(self, dout: np.ndarray, acts: list[np.ndarray]) -> tuple[list[np.ndarray], list[np.ndarray]]:
        gW = [None] * len(self.W)
        gb = [None] * len(self.b)
        d = dout
        for i in range(len(self.W) - 1, -1, -1):
            gW[i] = acts[i].T @ d
            gb[i] = d.sum(axis=0)
            if i > 0:
                d = (d @ self.W[i].T) * (1.0 - acts[i] ** 2)
        return gW, gb

    # ---- optimisation
    def step(self, gW: list[np.ndarray], gb: list[np.ndarray], lr: float = 1e-3, clip: float = 5.0) -> None:
        if self.opt is None:
            self.opt = Adam(self)
        norm = np.sqrt(sum(float((g ** 2).sum()) for g in gW + gb))
        scale = min(1.0, clip / (norm + 1e-12))
        self.opt.apply([g * scale for g in gW], [g * scale for g in gb], lr)

    # ---- persistence (JSON, no pickle)
    def to_json(self) -> dict[str, Any]:
        return {"sizes": self.sizes, "W": [w.tolist() for w in self.W], "b": [b.tolist() for b in self.b]}

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "MLP":
        m = cls(d["sizes"])
        m.W = [np.array(w) for w in d["W"]]
        m.b = [np.array(b) for b in d["b"]]
        return m

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(self.to_json(), f)

    @classmethod
    def load(cls, path: str) -> "MLP":
        with open(path) as f:
            return cls.from_json(json.load(f))

    def n_params(self) -> int:
        return sum(w.size for w in self.W) + sum(b.size for b in self.b)


class Adam:
    def __init__(self, net: MLP, b1: float = 0.9, b2: float = 0.999, eps: float = 1e-8) -> None:
        self.mW = [np.zeros_like(w) for w in net.W]
        self.vW = [np.zeros_like(w) for w in net.W]
        self.mb = [np.zeros_like(b) for b in net.b]
        self.vb = [np.zeros_like(b) for b in net.b]
        self.t = 0
        self.b1, self.b2, self.eps, self.net = b1, b2, eps, net

    def apply(self, gW: list[np.ndarray], gb: list[np.ndarray], lr: float) -> None:
        self.t += 1
        c1, c2 = 1 - self.b1 ** self.t, 1 - self.b2 ** self.t
        for i in range(len(gW)):
            for g, m, v, p in ((gW[i], self.mW, self.vW, self.net.W), (gb[i], self.mb, self.vb, self.net.b)):
                m[i] = self.b1 * m[i] + (1 - self.b1) * g
                v[i] = self.b2 * v[i] + (1 - self.b2) * g * g
                p[i] -= lr * (m[i] / c1) / (np.sqrt(v[i] / c2) + self.eps)


# ---------------------------------------------------------------- masked categorical policy

NEG = -1e9


def masked_softmax(logits: np.ndarray, mask: np.ndarray | None) -> np.ndarray:
    z = np.array(logits, dtype=np.float64)
    if mask is not None:
        z = np.where(mask > 0, z, NEG)
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    if mask is not None:
        e = e * (mask > 0)
    return e / np.maximum(e.sum(axis=-1, keepdims=True), 1e-12)


def sample(probs: np.ndarray, rng: np.random.RandomState) -> int:
    return int(rng.choice(len(probs), p=probs / probs.sum()))


def xent_grad(logits: np.ndarray, mask: np.ndarray | None, target: np.ndarray, weight: np.ndarray | None = None) -> tuple[float, np.ndarray]:
    """Cross-entropy of masked softmax against integer targets. Returns (mean loss, d loss / d logits)."""
    p = masked_softmax(logits, mask)
    n = p.shape[0]
    loss = -np.log(np.maximum(p[np.arange(n), target], 1e-12))
    g = p.copy()
    g[np.arange(n), target] -= 1.0
    if weight is not None:
        loss = loss * weight
        g = g * weight[:, None]
    return float(loss.mean()), g / n


def policy_gradient(logits: np.ndarray, mask: np.ndarray | None, actions: np.ndarray, advantages: np.ndarray, entropy_coef: float = 0.01) -> tuple[float, np.ndarray]:
    """REINFORCE with an advantage and an entropy bonus. Returns (loss, d loss / d logits) for a batch."""
    p = masked_softmax(logits, mask)
    n = p.shape[0]
    logp = np.log(np.maximum(p[np.arange(n), actions], 1e-12))
    loss = -(advantages * logp).mean()
    g = p.copy()
    g[np.arange(n), actions] -= 1.0
    g = g * advantages[:, None]
    ent = -(p * np.log(np.maximum(p, 1e-12))).sum(axis=1)
    # entropy gradient: d(-H)/dlogits = p * (log p + H)
    gent = p * (np.log(np.maximum(p, 1e-12)) + ent[:, None])
    g = g + entropy_coef * gent
    return float(loss - entropy_coef * ent.mean()), g / n


def discounted(rewards: list[float], gamma: float) -> np.ndarray:
    out = np.zeros(len(rewards))
    run = 0.0
    for i in range(len(rewards) - 1, -1, -1):
        run = rewards[i] + gamma * run
        out[i] = run
    return out
