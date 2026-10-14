"""Worlds for the neuro tests: built once per test session (a 20-minute AI game takes about 20 s) and handed out as pickled clones.

Not a test module (no tests here); imported by test_neuro_features.py and test_neuro_candidates.py.
"""
from __future__ import annotations

import os
import pickle
from typing import Any

from wizard_rts.world import HybridWorld

_BLOBS: dict[tuple, bytes] = {}


def _build(seed: int, minutes: int) -> HybridWorld:
    prev = os.environ.get("HYBRID_AI")
    os.environ["HYBRID_AI"] = "1"
    try:
        w = HybridWorld(seed, terrain=True, map_size="standard", profile="campaign")
    finally:
        if prev is None:
            os.environ.pop("HYBRID_AI", None)
        else:
            os.environ["HYBRID_AI"] = prev
    w.ai_enabled = True
    w.cardset, w.draft_v2, w.diplomacy_enabled = "v2", True, True
    w.nest_policy = {n: "coop" for n in w.faction_info}
    w.ai_policy = {n: "plus" for n in w.faction_info}
    for i in range(minutes * 60):
        w.advance(1000, i + 1, snapshot=False)
    return w


def world_at(minutes: int = 20, seed: int = 7) -> HybridWorld:
    """A fresh clone of a campaign world advanced `minutes` game minutes with the plus AI playing every faction."""
    key = (seed, minutes)
    if key not in _BLOBS:
        _BLOBS[key] = pickle.dumps(_build(seed, minutes), protocol=5)
    return pickle.loads(_BLOBS[key])


def fresh_world(seed: int = 7) -> HybridWorld:
    """A campaign world at game second 0 (no AI has acted)."""
    return world_at(0, seed)


def digest(arrays: dict[str, Any]) -> str:
    """sha256 of a set of arrays (name, dtype, shape, bytes), for reproducibility checks across processes."""
    import hashlib

    h = hashlib.sha256()
    for k in sorted(arrays):
        a = arrays[k]
        h.update(k.encode())
        h.update(str((a.dtype, a.shape)).encode())
        h.update(a.tobytes())
    return h.hexdigest()
