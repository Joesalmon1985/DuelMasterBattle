"""The Candidate record and its feature helper (shared by the candidate modules; see neuro/candidates.py)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from neuro import schema as S

HEADS = ("H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9")
EXCLUDE_S = 60  # a rejected key is not offered again for this many game seconds


@dataclass
class Candidate:
    head: str
    action: dict[str, Any]  # the exact HybridEnv.apply payload
    features: np.ndarray  # raw per-candidate features, float32, width schema.HEAD_RAW[head]
    key: tuple  # stable identity: the same command gives the same key
    refs: dict[str, Any] = field(default_factory=dict)  # pointers into the Observation (rows of buildings, units, settlements, offers, ...)


def feat(head: str, **values: float) -> np.ndarray:
    """A candidate feature vector from named fields of schema.HEAD_RAW[head] (an unknown name is an error; unset fields are 0)."""
    names = S.HEAD_RAW[head]
    v = np.zeros(len(names), dtype=np.float32)
    pos = {n: i for i, n in enumerate(names)}
    for k, x in values.items():
        v[pos[k]] = x
    np.clip(v, -5.0, 5.0, out=v)
    return v
