"""Pure-numpy candidate-scoring model (C12 / T145).

Observation encoder 128→64, candidate encoder 64→32, concat → 64-unit head → score,
plus value head from observation embedding. No torch dependency — genuine local
weights, not a heuristic clone.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from training.features import CAND_DIM, OBS_DIM, encode_candidates, encode_observation
from training.environment import schema_hash

MODEL_ARCH = {
    "obs_in": OBS_DIM,
    "obs_hidden": 64,
    "cand_in": CAND_DIM,
    "cand_hidden": 32,
    "score_hidden": 64,
    "schema": "ObservationV1",
}


def _relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(x, 0.0)


def _xavier(rng: np.random.Generator, fan_in: int, fan_out: int) -> np.ndarray:
    limit = np.sqrt(6.0 / (fan_in + fan_out))
    return rng.uniform(-limit, limit, size=(fan_in, fan_out)).astype(np.float64)


@dataclass
class CandidateScorer:
    """Masked candidate scorer + value head."""

    params: dict[str, np.ndarray]
    schema_hash: str
    trained: bool = False
    provenance: dict[str, Any] | None = None

    @classmethod
    def create(cls, seed: int = 0, *, trained: bool = False) -> "CandidateScorer":
        rng = np.random.default_rng(seed)
        params = {
            "W_obs1": _xavier(rng, OBS_DIM, 64),
            "b_obs1": np.zeros(64, dtype=np.float64),
            "W_cand1": _xavier(rng, CAND_DIM, 32),
            "b_cand1": np.zeros(32, dtype=np.float64),
            "W_score1": _xavier(rng, 64 + 32, 64),
            "b_score1": np.zeros(64, dtype=np.float64),
            "W_score2": _xavier(rng, 64, 1),
            "b_score2": np.zeros(1, dtype=np.float64),
            "W_value": _xavier(rng, 64, 1),
            "b_value": np.zeros(1, dtype=np.float64),
        }
        return cls(params=params, schema_hash=schema_hash(), trained=trained, provenance={"init_seed": seed})

    def forward(
        self, obs_vec: np.ndarray, cand_mat: np.ndarray
    ) -> tuple[np.ndarray, float, dict[str, np.ndarray]]:
        """Return (scores[N], value, cache)."""
        h_obs = _relu(obs_vec @ self.params["W_obs1"] + self.params["b_obs1"])
        value = float((h_obs @ self.params["W_value"] + self.params["b_value"])[0])
        if cand_mat.size == 0:
            return np.zeros(0, dtype=np.float64), value, {"h_obs": h_obs}
        h_cand = _relu(cand_mat @ self.params["W_cand1"] + self.params["b_cand1"])
        # Broadcast obs embedding across candidates.
        h_obs_b = np.repeat(h_obs[None, :], cand_mat.shape[0], axis=0)
        concat = np.concatenate([h_obs_b, h_cand], axis=1)
        h = _relu(concat @ self.params["W_score1"] + self.params["b_score1"])
        scores = (h @ self.params["W_score2"] + self.params["b_score2"]).reshape(-1)
        cache = {"h_obs": h_obs, "h_cand": h_cand, "concat": concat, "h": h, "cand_mat": cand_mat, "obs_vec": obs_vec}
        return scores, value, cache

    def score_candidates(
        self, observation: dict[str, Any], candidates: list[dict[str, Any]], *, faction_index: int = 0
    ) -> list[tuple[str, float]]:
        obs_vec = encode_observation(observation, faction_index=faction_index)
        cand_mat = encode_candidates(candidates)
        scores, _, _ = self.forward(obs_vec, cand_mat)
        return [(str(c["id"]), float(scores[i])) for i, c in enumerate(candidates)]

    def choose_id(
        self, observation: dict[str, Any], candidates: list[dict[str, Any]], *, faction_index: int = 0
    ) -> str:
        if not candidates:
            raise RuntimeError("no candidates")
        ranked = self.score_candidates(observation, candidates, faction_index=faction_index)
        # Deterministic: higher score, then stable id.
        ranked.sort(key=lambda x: (-x[1], x[0]))
        return ranked[0][0]

    def weights_digest(self) -> str:
        h = hashlib.sha256()
        for key in sorted(self.params):
            h.update(key.encode())
            h.update(self.params[key].tobytes())
        return h.hexdigest()[:16]

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format": "dmb_candidate_scorer_v1",
            "arch": MODEL_ARCH,
            "schema_hash": self.schema_hash,
            "trained": bool(self.trained),
            "provenance": self.provenance or {},
            "weights_digest": self.weights_digest(),
            "params": {k: v.tolist() for k, v in self.params.items()},
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path, *, expect_schema_hash: str | None = None) -> "CandidateScorer":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("format") != "dmb_candidate_scorer_v1":
            raise ValueError("unsupported model format")
        sh = str(payload.get("schema_hash") or "")
        if expect_schema_hash is not None and sh != expect_schema_hash:
            raise ValueError(f"schema mismatch: model={sh} expected={expect_schema_hash}")
        current = schema_hash()
        if sh != current:
            raise ValueError(f"schema mismatch: model={sh} current={current}")
        params = {k: np.asarray(v, dtype=np.float64) for k, v in payload["params"].items()}
        return cls(
            params=params,
            schema_hash=sh,
            trained=bool(payload.get("trained")),
            provenance=dict(payload.get("provenance") or {}),
        )


def softmax(logits: np.ndarray) -> np.ndarray:
    if logits.size == 0:
        return logits
    z = logits - np.max(logits)
    e = np.exp(z)
    return e / (np.sum(e) + 1e-12)


def imitation_loss_and_grads(
    model: CandidateScorer,
    obs_vec: np.ndarray,
    cand_mat: np.ndarray,
    target_index: int,
) -> tuple[float, dict[str, np.ndarray], float]:
    """Cross-entropy on masked candidate scores; returns loss, grads, value."""
    scores, value, cache = model.forward(obs_vec, cand_mat)
    if scores.size == 0:
        zeros = {k: np.zeros_like(v) for k, v in model.params.items()}
        return 0.0, zeros, value
    probs = softmax(scores)
    loss = float(-np.log(probs[target_index] + 1e-12))
    # dL/dscores
    ds = probs.copy()
    ds[target_index] -= 1.0

    h = cache["h"]
    concat = cache["concat"]
    h_obs = cache["h_obs"]
    h_cand = cache["h_cand"]

    # score2
    dW_score2 = h.T @ ds.reshape(-1, 1)
    db_score2 = ds.reshape(-1, 1).sum(axis=0)
    dh = ds.reshape(-1, 1) @ model.params["W_score2"].T
    # relu
    dh *= (h > 0).astype(np.float64)
    dW_score1 = concat.T @ dh
    db_score1 = dh.sum(axis=0)
    dconcat = dh @ model.params["W_score1"].T
    dh_obs_b = dconcat[:, :64]
    dh_cand = dconcat[:, 64:]
    dh_obs = dh_obs_b.sum(axis=0)
    dh_cand_relu = dh_cand * (h_cand > 0).astype(np.float64)
    dW_cand1 = cand_mat.T @ dh_cand_relu
    db_cand1 = dh_cand_relu.sum(axis=0)
    dh_obs_relu = dh_obs * (h_obs > 0).astype(np.float64)
    dW_obs1 = np.outer(obs_vec, dh_obs_relu)
    db_obs1 = dh_obs_relu

    grads = {
        "W_obs1": dW_obs1,
        "b_obs1": db_obs1,
        "W_cand1": dW_cand1,
        "b_cand1": db_cand1,
        "W_score1": dW_score1,
        "b_score1": db_score1,
        "W_score2": dW_score2,
        "b_score2": db_score2,
        "W_value": np.zeros_like(model.params["W_value"]),
        "b_value": np.zeros_like(model.params["b_value"]),
    }
    return loss, grads, value


def apply_grads(
    model: CandidateScorer,
    grads: dict[str, np.ndarray],
    *,
    lr: float,
    max_norm: float = 5.0,
) -> None:
    # Global norm clip.
    total = 0.0
    for g in grads.values():
        total += float(np.sum(g * g))
    total = np.sqrt(total) + 1e-12
    scale = min(1.0, max_norm / total)
    for k, g in grads.items():
        model.params[k] = model.params[k] - lr * scale * g
