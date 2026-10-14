"""The recorded V4 state-hash baseline still reproduces (a gameplay change must re-record it under a new label)."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_v4_baseline_reproduces_for_three_minutes():
    base = ROOT / "docs" / "perf" / "hash_baseline_v4.json"
    assert json.loads(base.read_text())["label"].startswith("v4")
    r = subprocess.run([sys.executable, str(ROOT / "WizardRTSHybrid" / "scripts" / "hash_gate.py"), "check", "--baseline", str(base), "--limit-minutes", "3"],
                       capture_output=True, text=True, env={**os.environ, "HYBRID_AI": "1"}, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
