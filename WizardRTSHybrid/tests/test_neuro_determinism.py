"""T3.2: the same genome and seed give the same game, whatever the string-hash seed of the interpreter."""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

from neuro import nets as N
from neuro.controller import read_log

HYB = Path(__file__).resolve().parents[1]


def _play(tmp: Path, genome: Path, hashseed: str, tag: str) -> tuple[dict, list]:
    out, rec = tmp / f"{tag}.json", tmp / f"{tag}.jsonl.gz"
    env = {**os.environ, "PYTHONHASHSEED": hashseed, "HYBRID_AI": "1", "PYTHONPATH": str(HYB) + os.pathsep + str(HYB.parent)}
    cp = subprocess.run([sys.executable, "-m", "neuro.cli", "play", "--genome", str(genome), "--seed", "7", "--minutes", "15", "--map", "small", "--seat", "Red",
                         "--record", str(rec), "--json", str(out)], cwd=HYB, env=env, capture_output=True, text=True, timeout=900)
    assert cp.returncode == 0, cp.stderr[-2000:]
    return json.loads(out.read_text(encoding="utf-8")), read_log(rec)


def test_two_processes_with_different_hash_seeds_play_the_identical_game(tmp_path):
    g = tmp_path / "g.npy"
    np.save(g, N.random_genome(np.random.default_rng(3)))
    a, la = _play(tmp_path, g, "1", "a")
    b, lb = _play(tmp_path, g, "12345", "b")
    assert a["state_hash"] == b["state_hash"] and len(a["state_hash"]) == 40
    assert la == lb and len(la) > 20
    assert a["stats"]["Red"]["commands"] == b["stats"]["Red"]["commands"] > 0
    assert a["books_ok"] and b["books_ok"]
