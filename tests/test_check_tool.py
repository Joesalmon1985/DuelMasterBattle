from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECK_PATH = ROOT / "tools" / "check.py"
SCENARIO_PATH = ROOT / "tools" / "run_scenario.py"


def _load_check_module():
    spec = importlib.util.spec_from_file_location("dmb_check", CHECK_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_failed_subprocess_never_passes() -> None:
    check = _load_check_module()
    result = check.run_command(
        check.CommandCheck(
            name="deliberate_failure",
            argv=(sys.executable, "-c", "raise SystemExit(7)"),
        )
    )
    assert result.status == "FAIL"
    assert result.exit_code == 7


def test_empty_pytest_suite_never_passes(tmp_path: Path) -> None:
    check = _load_check_module()
    result = check.run_command(
        check.CommandCheck(
            name="empty_suite",
            argv=(sys.executable, "-m", "pytest", "-q", str(tmp_path)),
            count_pattern=r"(\d+)\s+passed",
        )
    )
    assert result.status == "FAIL"
    assert result.exit_code != 0


def test_unexpected_skip_never_passes() -> None:
    check = _load_check_module()
    result = check.run_command(
        check.CommandCheck(
            name="unexpected_skip",
            argv=(sys.executable, "-c", "print('1 passed, 1 skipped')"),
            required_pattern=r"\bpassed\b",
            count_pattern=r"(\d+)\s+passed",
            expected_skips=0,
        )
    )
    assert result.status == "FAIL"
    assert "unexpected skip count" in result.detail


def test_missing_audit_evidence_never_passes(tmp_path: Path) -> None:
    check = _load_check_module()
    result = check.validate_evidence("missing", [tmp_path / "absent.json"])
    assert result.status == "FAIL"
    assert result.exit_code != 0


def test_future_task_and_gate_fail_closed() -> None:
    check = _load_check_module()
    task = check.checks_for_task("T006")
    gate = check.checks_for_gate("G01")
    assert task[0].status == "NOT_IMPLEMENTED"
    assert gate[0].status == "NOT_READY"


def test_unknown_task_cli_is_nonzero() -> None:
    completed = subprocess.run(
        [sys.executable, str(CHECK_PATH), "--task", "T999"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode != 0
    assert "unknown T identifier" in completed.stderr


def test_unimplemented_scenario_records_failure(tmp_path: Path) -> None:
    report = tmp_path / "clock.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCENARIO_PATH),
            "--fixture",
            "FX-CLOCK",
            "--record",
            str(report),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode != 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == "NOT_IMPLEMENTED"
    assert "No scenario was run" in payload["message"]


def test_scenario_list_is_explicit_and_nonempty() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCENARIO_PATH), "--list"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["FX-CLOCK"] == "T012/T024"
    assert len(payload) == 11
