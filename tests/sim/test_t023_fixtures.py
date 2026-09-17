"""T023 fixture production entrypoint."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sim.dmb.testing.fixtures import load_fixture, run_fx_clock


def test_fx_clock_loads_and_reproduces(tmp_path: Path) -> None:
    sim = load_fixture("FX-CLOCK", seed=7)
    result = run_fx_clock(sim)
    assert result.status == "PASS"
    # Replay from fresh fixture reproduces turn/node.
    again = run_fx_clock(load_fixture("FX-CLOCK", seed=7))
    assert again.details["end_node"] == result.details["end_node"]
    assert again.details["turns"] == result.details["turns"]


def test_invalid_fixture_fails_before_play() -> None:
    with pytest.raises(ValueError, match="unsupported fixture"):
        load_fixture("FX-NOT-A-THING")


def test_run_scenario_script(tmp_path: Path) -> None:
    import subprocess
    import sys

    record = tmp_path / "fx.json"
    completed = subprocess.run(
        [sys.executable, "tools/run_scenario.py", "--fixture", "FX-CLOCK", "--record", str(record)],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    payload = json.loads(record.read_text(encoding="utf-8"))
    assert payload["status"] == "PASS"
