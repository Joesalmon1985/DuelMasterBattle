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


PROGRAM_V2 = r"""
import sys
sys.path.insert(0, %r)
from wizard_rts.world import HybridWorld
from wizard_rts import draft
w = HybridWorld(seed=507, profile="campaign")
w.cardset, w.draft_v2 = "v2", True
for i in range(%d * 60):
    w.advance(1000, i + 1, snapshot=False)
st = draft.state(w)
print(w.state_hash(), sorted((f, tuple(c)) for f, s in w.tech.items() for c in [s["cards"]]), st["round"])
"""


def test_drafting_v2_is_deterministic_across_processes() -> None:
    """The generated cards, the tribe-balanced deal, the ring and the AI picks must not depend on string-hash salting."""
    def run(hashseed: str) -> str:
        env = dict(os.environ, PYTHONHASHSEED=hashseed, HYBRID_AI="1", HYBRID_AI_POLICY="plus")
        out = subprocess.run([sys.executable, "-c", PROGRAM_V2 % (str(HYB), 13)], env=env, capture_output=True, text=True, timeout=900, cwd=str(HYB))
        assert out.returncode == 0, out.stderr[-2000:]
        return out.stdout.strip().splitlines()[-1]

    a, b = run("3"), run("424242")
    assert a == b, f"two processes disagree:\n{a}\n{b}"
