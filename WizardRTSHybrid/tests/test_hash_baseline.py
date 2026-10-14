"""The recorded V5 state-hash baselines still reproduce (a gameplay change must re-record them under a new label).

v5 (T1.1, 14 Oct 2026) replaced v4: the heuristic AIs now find targets only through their visibility memory, which changed the `baseline` AI's play from
minute 12. The v4 files stay in docs/perf as history (v4 showcase no longer reproduces; v4 campaign/plus still does for its first 20 minutes).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("name", ["hash_baseline_v5.json", "hash_baseline_v5_campaign_plus.json"])
def test_v5_baseline_reproduces_for_three_minutes(name):
    base = ROOT / "docs" / "perf" / name
    assert json.loads(base.read_text(encoding="utf-8"))["label"].startswith("v5")
    r = subprocess.run([sys.executable, str(ROOT / "WizardRTSHybrid" / "scripts" / "hash_gate.py"), "check", "--baseline", str(base), "--limit-minutes", "3"],
                       capture_output=True, text=True, env={**os.environ, "HYBRID_AI": "1"}, timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr
