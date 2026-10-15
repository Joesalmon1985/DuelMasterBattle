"""Model files, checkpoints and disk pruning (execution plan T5.3; design 10.1-10.3).

    save_model / load_model     best_ai.json (manifest, evaluation, layout, npz sha256) + best_ai.npz (one array per module and the whole genome `theta`)
    save_checkpoint / load_checkpoint   atomic (temp + fsync + rename), a sha256 header, the newest valid of the last three wins
    prune                       keep the last 3 checkpoints, game folders of the last 4 generations and every promotion game, stay under the size cap
"""
from __future__ import annotations

import hashlib
import json
import os
import pickle
import shutil
from pathlib import Path
from typing import Any

import numpy as np

from neuro import manifest as M
from neuro import nets


class ModelError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic_bytes(path: Path, blob: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as fh:
        fh.write(blob)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


# ---------------------------------------------------------------------------------------------------------------------------- models
def save_model(path_json: str | Path, genome: np.ndarray, manifest: dict, evaluation: dict | None = None) -> Path:
    path_json = Path(path_json)
    npz = path_json.with_suffix(".npz")
    g = np.asarray(genome, dtype=np.float32)
    if g.shape != (nets.genome_size(),):
        raise ModelError(f"genome has {g.shape}, the architecture needs ({nets.genome_size()},)")
    arrays = {name: g[a:b] for name, (a, b) in nets.slices().items()}
    arrays["theta"] = g
    tmp = npz.with_name(npz.name + ".tmp")
    with open(tmp, "wb") as fh:
        np.savez(fh, **arrays)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, npz)
    meta = {"format": "dmb-neuro-model-1", "manifest": manifest, "evaluation": evaluation or {}, "layout": nets.layout_table(), "npz": npz.name, "npz_sha256": _sha256(npz),
            "catastrophe_level": manifest.get("catastrophe_level", "C0"), "outbreak_interval_scale": manifest.get("outbreak_interval_scale", 1.0)}
    _atomic_bytes(path_json, json.dumps(meta, indent=1, default=str).encode("utf-8"))
    return path_json


def load_model(path_json: str | Path, current: dict | None = None) -> tuple[np.ndarray, dict]:
    """(genome, meta). Verifies the npz hash, the shapes and, when `current` (a manifest) is given, the compatibility: an incompatible model is refused, a model made
    under other rules or another catastrophe level is returned with meta['compatibility'] == 'reevaluate'."""
    path_json = Path(path_json)
    meta = json.loads(path_json.read_text(encoding="utf-8"))
    npz = path_json.with_name(meta["npz"])
    if _sha256(npz) != meta["npz_sha256"]:
        raise ModelError(f"{npz.name}: hash does not match the model file (corrupt or edited)")
    with np.load(npz) as z:
        theta = z["theta"].astype(np.float32)
        if theta.shape != (nets.genome_size(),):
            raise ModelError(f"{npz.name}: theta has {theta.shape}, the architecture needs ({nets.genome_size()},)")
        for name, (a, b) in nets.slices().items():
            if z[name].shape != (b - a,) or not np.array_equal(z[name], theta[a:b]):
                raise ModelError(f"{npz.name}: module {name} does not match theta")
    meta["compatibility"] = "same"
    if current is not None:
        c = M.compatible(meta["manifest"], current)
        if c == "incompatible":
            raise ModelError(f"{path_json.name} is incompatible with this code: {M.differences(meta['manifest'], current)['incompatible']}")
        meta["compatibility"] = c
    return theta, meta


# ---------------------------------------------------------------------------------------------------------------------------- checkpoints
def _ckpt_dir(run_dir: str | Path) -> Path:
    return Path(run_dir) / "checkpoints"


def save_checkpoint(run_dir: str | Path, state: dict[str, Any], generation: int) -> Path:
    payload = pickle.dumps(state, protocol=5)
    blob = hashlib.sha256(payload).digest() + payload
    path = _ckpt_dir(run_dir) / f"ckpt_{generation:06d}.pkl"
    _atomic_bytes(path, blob)
    return path


def _read_checkpoint(path: Path) -> dict[str, Any]:
    blob = path.read_bytes()
    digest, payload = blob[:32], blob[32:]
    if len(blob) < 33 or hashlib.sha256(payload).digest() != digest:
        raise ModelError(f"{path.name}: checksum mismatch")
    return pickle.loads(payload)


def load_checkpoint(run_dir: str | Path) -> dict[str, Any] | None:
    """The newest valid checkpoint (a corrupt newest one falls back to the previous), or None."""
    for path in sorted(_ckpt_dir(run_dir).glob("ckpt_*.pkl"), reverse=True):
        try:
            return _read_checkpoint(path)
        except Exception:  # noqa: BLE001 - a half-written or corrupt file is skipped, the older one is used
            continue
    return None


# ---------------------------------------------------------------------------------------------------------------------------- disk
def dir_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def prune(run_dir: str | Path, keep_checkpoints: int = 3, keep_generations: int = 4, max_run_gb: float = 20.0, current_generation: int | None = None) -> dict:
    """Keep the last `keep_checkpoints` checkpoints, the game folders of the last `keep_generations` generations (games/gen_NNNNNN) and everything under
    games/promotion; if the run is still over the cap, delete the oldest generation folders (never a checkpoint, a champion, a report or a promotion game)."""
    run_dir = Path(run_dir)
    removed = {"checkpoints": 0, "generations": 0}
    ckpts = sorted(_ckpt_dir(run_dir).glob("ckpt_*.pkl"))
    for p in ckpts[:-keep_checkpoints] if keep_checkpoints > 0 else ckpts:
        p.unlink(missing_ok=True)
        removed["checkpoints"] += 1
    for p in _ckpt_dir(run_dir).glob("*.tmp"):
        p.unlink(missing_ok=True)
    games = run_dir / "games"
    gens = sorted(p for p in games.glob("gen_*") if p.is_dir()) if games.exists() else []
    old = gens[:-keep_generations] if keep_generations > 0 else gens
    for p in old:
        shutil.rmtree(p, ignore_errors=True)
        removed["generations"] += 1
    gens = [p for p in gens if p.exists()]
    cap = max_run_gb * 1e9
    while gens and dir_size(run_dir) > cap and len(gens) > 1:
        shutil.rmtree(gens.pop(0), ignore_errors=True)
        removed["generations"] += 1
    removed["bytes"] = dir_size(run_dir)
    return removed
