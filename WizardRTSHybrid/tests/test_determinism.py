"""A seed must give the same game in any process: no iteration over salted-hash containers may steer the simulation."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]

PROGRAM = r"""
import sys
sys.path.insert(0, %r)
from wizard_rts.world import HybridWorld
from wizard_rts import territory
w = HybridWorld(seed=507)
seq = 0
for _ in range(%d * 600):
    seq += 1
    w.advance(100, seq, snapshot=False)
import hashlib
parts = sorted((b["id"], b["tx"], b["ty"], int(b.get("hp", 0))) for b in w.buildings.values())
parts += sorted((u["id"], u["tx"], u["ty"], int(u.get("hp", 0))) for u in w.units.values())
parts += [("cc", c["id"], c["tx"], c["ty"]) for c in territory.command_centers(w)]
print(hashlib.sha256(repr(parts).encode()).hexdigest(), len(territory.command_centers(w)), sum(w.stats.values()))
"""


def _run(hashseed: str, minutes: int) -> str:
    env = dict(os.environ, PYTHONHASHSEED=hashseed, HYBRID_AI="1")
    out = subprocess.run([sys.executable, "-c", PROGRAM % (str(HYB), minutes)], env=env, capture_output=True, text=True, timeout=600, cwd=str(HYB))
    assert out.returncode == 0, out.stderr[-2000:]
    return out.stdout.strip().splitlines()[-1]


def test_same_seed_same_game_across_processes_with_expansion() -> None:
    a = _run("1", 14)
    b = _run("98765", 14)
    assert a == b, f"two processes disagree:\n{a}\n{b}"
    assert int(a.split()[1]) >= 7, "the run must include at least one deployed command centre (6 homes + 1) so expansion is covered"
