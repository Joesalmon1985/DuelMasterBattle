from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECK_PATH = ROOT / "tools" / "check.py"
TRACKING = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking"


def _load_check():
    spec = importlib.util.spec_from_file_location("dmb_check_tracking", CHECK_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_live_progress_resume_selects_first_unmet_task() -> None:
    check = _load_check()
    progress = json.loads((TRACKING / "progress.json").read_text(encoding="utf-8"))
    expected = None
    for number in range(1, 161):
        task = f"T{number:03d}"
        if progress["tasks"].get(task) != "DONE":
            expected = task
            break
    problems, resume = check.validate_tracking_state()
    assert problems == []
    assert resume == {"kind": "task", "id": expected}


def test_completed_task_without_evidence_is_rejected(tmp_path: Path) -> None:
    check = _load_check()
    progress = json.loads((TRACKING / "progress.json").read_text(encoding="utf-8"))
    handoffs = tmp_path / "handoffs"
    handoffs.mkdir()
    for path in (TRACKING / "handoffs").glob("T*.json"):
        shutil.copy2(path, handoffs / path.name)
    # Corrupt T001 receipt into a DONE claim with no checks.
    bad = {
        "task_id": "T001",
        "status": "DONE",
        "commit": "a" * 40,
        "files": [],
        "checks": [],
        "next_task": "T002",
    }
    (handoffs / "T001.json").write_text(json.dumps(bad), encoding="utf-8")
    progress_path = tmp_path / "progress.json"
    progress_path.write_text(json.dumps(progress), encoding="utf-8")
    problems, _resume = check.validate_tracking_state(progress_path, handoffs)
    assert any("no check evidence" in problem for problem in problems)


def test_failed_task_remains_current_instead_of_advancing(tmp_path: Path) -> None:
    check = _load_check()
    progress = json.loads((TRACKING / "progress.json").read_text(encoding="utf-8"))
    progress["tasks"]["T006"] = "FAILED"
    progress["current_task"] = "T006"
    handoffs = tmp_path / "handoffs"
    shutil.copytree(TRACKING / "handoffs", handoffs)
    progress_path = tmp_path / "progress.json"
    progress_path.write_text(json.dumps(progress), encoding="utf-8")
    problems, resume = check.validate_tracking_state(progress_path, handoffs)
    assert problems == []
    assert resume == {"kind": "task", "id": "T006"}


def test_manual_gate_blocks_until_joe_pass(tmp_path: Path) -> None:
    check = _load_check()
    progress = json.loads((TRACKING / "progress.json").read_text(encoding="utf-8"))
    for number in range(1, 25):
        progress["tasks"][f"T{number:03d}"] = "DONE"
    progress["current_task"] = "T025"
    progress["gates"]["G01"]["status"] = "AWAITING_HUMAN"
    handoffs = tmp_path / "handoffs"
    shutil.copytree(TRACKING / "handoffs", handoffs)
    # Minimal receipts for synthetic DONE tasks beyond existing ones.
    for number in range(6, 25):
        task = f"T{number:03d}"
        (handoffs / f"{task}.json").write_text(
            json.dumps(
                {
                    "task_id": task,
                    "status": "DONE",
                    "commit": "b" * 40,
                    "files": ["x"],
                    "checks": [{"command": "echo", "exit_code": 0, "result": "ok"}],
                    "next_task": f"T{number + 1:03d}",
                }
            ),
            encoding="utf-8",
        )
    progress_path = tmp_path / "progress.json"
    progress_path.write_text(json.dumps(progress), encoding="utf-8")
    problems, resume = check.validate_tracking_state(progress_path, handoffs)
    assert problems == []
    assert resume == {"kind": "gate", "id": "G01"}


def test_defects_policy_forbids_skipping_and_caps_repairs() -> None:
    defects = json.loads((TRACKING / "defects.json").read_text(encoding="utf-8"))
    assert defects["policy"]["max_focused_repair_attempts"] == 3
    assert defects["policy"]["test_skipping_allowed"] is False
    assert defects["policy"]["assertion_weakening_allowed"] is False


def test_resume_cli_is_nonzero_when_ledger_is_invalid(tmp_path: Path) -> None:
    # The live CLI validates the pack ledger; this unit covers the helper via a
    # temporary invalid current_task mismatch.
    check = _load_check()
    progress = json.loads((TRACKING / "progress.json").read_text(encoding="utf-8"))
    progress["current_task"] = "T007"
    handoffs = tmp_path / "handoffs"
    shutil.copytree(TRACKING / "handoffs", handoffs)
    progress_path = tmp_path / "progress.json"
    progress_path.write_text(json.dumps(progress), encoding="utf-8")
    problems, resume = check.validate_tracking_state(progress_path, handoffs)
    assert resume["id"] == "T006"
    assert any("current_task" in problem for problem in problems)


def test_check_py_resume_cli_runs() -> None:
    completed = subprocess.run(
        [sys.executable, str(CHECK_PATH), "--resume"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["resume"]["kind"] in {"task", "gate", "complete"}
    assert payload["resume"]["id"]
