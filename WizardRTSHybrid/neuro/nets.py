"""The networks and the genome (execution plan T3.1; design sections 4.3 and 7.1).

A genome is ONE flat float32 vector holding every parameter of every network plus the kind embedding and the head temperatures. `LAYOUT` fixes the order and the
widths (the in-widths are exactly the input widths of neuro/schema.py; `schema.compose()` builds the inputs). `Nets(genome)` slices the vector into weight views and offers a
batched forward pass per network. Nothing here touches the simulation.

Activations (a documented choice of M3, the design left them open): every network is  in -> hidden (tanh) -> out ; the two-number entries (N13slot, N14region) are
a single layer. The OUTPUT of a representation network (N1-N10, N13, N14, the slot and region encoders, N8card's hidden layer, and the first 56 outputs of N12) passes through
tanh so representations stay in (-1, 1); scores and logits (the heads, N8card's score, N11's logits, N12's wait logit) are linear.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from neuro import features as F
from neuro import schema as S

ARCH_VERSION = "arch-1.0.0"

# (name, in, hidden, out); hidden 0 means a single layer. The in-widths must equal schema.DECLARED.
LAYOUT: list[tuple[str, int, int, int]] = [
    ("N1", 32, 32, 16), ("N3", 28, 24, 12), ("N2", 100, 64, 24), ("N4", 102, 48, 16), ("N5", 12, 16, 8), ("N6", 112, 64, 16), ("N7", 68, 32, 12),
    ("N8", 50, 32, 16), ("N8card", 31, 16, 1), ("N13slot", 16, 0, 8), ("N13", 17, 16, 8), ("N14region", 10, 0, 8), ("N14", 56, 32, 12),
    ("N9", 124, 64, 16), ("N10", 63, 32, 16), ("N12", 112, 64, 57), ("N11", 74, 32, 4),
    ("H0", 41, 16, 1), ("H1", 108, 48, 1), ("H2", 70, 32, 1), ("H3", 84, 32, 1), ("H4", 60, 32, 1), ("H5", 96, 48, 1), ("H6", 49, 16, 1), ("H7", 60, 24, 1), ("H8", 50, 24, 1),
    ("H9", 100, 32, 1),
]
HEAD_NAMES = ("H0", "H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9")
HEAD_DOMAIN = {"H1": 0, "H2": 1, "H3": 2, "H4": 3, "H5": 4, "H6": 5, "H7": 6, "H8": 6, "H9": 7}  # which of the 8 priorities biases a head
LINEAR_OUT = {"N8card_score", "N11", "H0", "H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9"}  # outputs that are not squashed
EMB_ROWS = F.n_kinds()
EMB_SCALE = 0.3
N12_SPLIT = {"context": (0, 32), "memory": (32, 48), "priorities": (48, 56), "wait": (56, 57)}

for _n, _i, _h, _o in LAYOUT:
    assert _i == S.DECLARED[_n], (_n, _i, S.DECLARED[_n])


@dataclass(frozen=True)
class Slot:
    start: int
    stop: int
    shapes: tuple  # ((name, shape), ...) in storage order


def _build_slots() -> tuple[dict[str, Slot], int]:
    slots: dict[str, Slot] = {}
    pos = 0
    for name, i, h, o in LAYOUT:
        shapes = (("W1", (i, h)), ("b1", (h,)), ("W2", (h, o)), ("b2", (o,))) if h else (("W1", (i, o)), ("b1", (o,)))
        n = sum(int(np.prod(sh)) for _k, sh in shapes)
        slots[name] = Slot(pos, pos + n, shapes)
        pos += n
    slots["EMB"] = Slot(pos, pos + EMB_ROWS * S.EMB_DIM, (("E", (EMB_ROWS, S.EMB_DIM)),))
    pos += EMB_ROWS * S.EMB_DIM
    slots["TEMP"] = Slot(pos, pos + len(HEAD_NAMES), (("T", (len(HEAD_NAMES),)),))
    pos += len(HEAD_NAMES)
    return slots, pos


SLOTS, GENOME_SIZE = _build_slots()
MODULES = tuple(SLOTS)  # the unit of module-wise mutation


def genome_size() -> int:
    return GENOME_SIZE


def slices() -> dict[str, tuple[int, int]]:
    """module -> (start, stop) in the flat genome."""
    return {k: (v.start, v.stop) for k, v in SLOTS.items()}


def layout_table() -> list[dict]:
    """The architecture as data (for the model file): name, widths, parameter range."""
    out = [{"module": n, "in": i, "hidden": h, "out": o, "range": [SLOTS[n].start, SLOTS[n].stop]} for n, i, h, o in LAYOUT]
    out += [{"module": "EMB", "rows": EMB_ROWS, "dim": S.EMB_DIM, "range": [SLOTS["EMB"].start, SLOTS["EMB"].stop]},
            {"module": "TEMP", "size": len(HEAD_NAMES), "range": [SLOTS["TEMP"].start, SLOTS["TEMP"].stop]}]
    return out


def random_genome(rng: np.random.Generator) -> np.ndarray:
    """He-scaled weights (hidden layers sqrt(2/fan_in), output layers half of sqrt(1/fan_in) so first scores are moderate), zero biases, temperatures 1.0, embeddings N(0, 0.3)."""
    g = np.zeros(GENOME_SIZE, dtype=np.float32)
    for name, i, h, o in LAYOUT:
        sl = SLOTS[name]
        pos = sl.start
        for key, shape in sl.shapes:
            n = int(np.prod(shape))
            if key == "W1":
                g[pos:pos + n] = rng.normal(0.0, np.sqrt(2.0 / shape[0]) * (1.0 if h else 0.5), n)
            elif key == "W2":
                g[pos:pos + n] = rng.normal(0.0, 0.5 * np.sqrt(1.0 / shape[0]), n)
            pos += n
    e = SLOTS["EMB"]
    g[e.start:e.stop] = rng.normal(0.0, EMB_SCALE, e.stop - e.start)
    t = SLOTS["TEMP"]
    g[t.start:t.stop] = 1.0
    return g


class Nets:
    """Weight views over one genome and the forward passes. All inputs are 2-D batches [n, in]; an empty batch gives an empty [0, out] result."""

    def __init__(self, genome: np.ndarray) -> None:
        g = np.asarray(genome, dtype=np.float32)
        if g.shape != (GENOME_SIZE,):
            raise ValueError(f"genome has {g.shape}, the architecture needs ({GENOME_SIZE},)")
        self.genome = g
        self.w: dict[str, dict[str, np.ndarray]] = {}
        for name, sl in SLOTS.items():
            pos, d = sl.start, {}
            for key, shape in sl.shapes:
                n = int(np.prod(shape))
                d[key] = g[pos:pos + n].reshape(shape)
                pos += n
            self.w[name] = d
        self.emb = self.w["EMB"]["E"]
        self.temp = self.w["TEMP"]["T"]

    def forward(self, name: str, x: np.ndarray) -> np.ndarray:
        """Forward pass of network `name` on x [n, in]."""
        x = np.asarray(x, dtype=np.float32)
        d = self.w[name]
        if "W2" in d:
            y = np.tanh(x @ d["W1"] + d["b1"]) @ d["W2"] + d["b2"]
        else:
            y = x @ d["W1"] + d["b1"]
        if name in LINEAR_OUT:
            return y
        if name == "N12":
            y = y.copy()
            y[:, :56] = np.tanh(y[:, :56])
            return y
        return np.tanh(y)

    def hidden(self, name: str, x: np.ndarray) -> np.ndarray:
        """The tanh hidden layer of a two-layer network (N8card's per-card feature)."""
        d = self.w[name]
        return np.tanh(np.asarray(x, dtype=np.float32) @ d["W1"] + d["b1"])

    def card(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """N8card: (hidden [k, 16], score [k])."""
        d = self.w["N8card"]
        h = np.tanh(np.asarray(x, dtype=np.float32) @ d["W1"] + d["b1"])
        return h, (h @ d["W2"] + d["b2"])[:, 0]

    def embed(self, rows: np.ndarray) -> np.ndarray:
        return self.emb[np.asarray(rows, dtype=np.int64)]

    def head_gain(self, head: str) -> float:
        return float(self.temp[HEAD_NAMES.index(head)])


def pool(x: np.ndarray, width: int) -> tuple[np.ndarray, np.ndarray]:
    """(mean, max) over the rows of x [n, width]; zeros for an empty set."""
    if len(x) == 0:
        z = np.zeros(width, dtype=np.float32)
        return z, z
    return x.mean(axis=0), x.max(axis=0)
