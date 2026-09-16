#!/usr/bin/env python3
"""Fail-closed task and gate verification entrypoint.

T004 establishes the wrapper contract. Later tasks replace their explicit
NOT_IMPLEMENTED entries with meaningful checks; no future task or gate can
pass merely because its suite has not been wired yet.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
TRACKING = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking"
GATE_OWNER = {
    "G01": "T024",
    "G02": "T048",
    "G03": "T058",
    "G04": "T076",
    "G05": "T096",
    "G06": "T114",
    "G07": "T132",
    "G08": "T142",
    "G09": "T150",
    "G10": "T160",
}


@dataclass(frozen=True)
class CommandCheck:
    name: str
    argv: tuple[str, ...]
    cwd: Path = ROOT
    required_pattern: str | None = None
    count_pattern: str | None = None
    expected_skips: int = 0


@dataclass
class CheckResult:
    name: str
    status: str
    exit_code: int
    duration_seconds: float
    detail: str
    command: list[str] | None = None


def _read_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_evidence(name: str, required: Sequence[Path]) -> CheckResult:
    started = time.monotonic()
    problems: list[str] = []
    for path in required:
        display_path = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
        if not path.is_file():
            problems.append(f"missing {display_path}")
            continue
        if path.stat().st_size == 0:
            problems.append(f"empty {display_path}")
            continue
        if path.suffix == ".json":
            try:
                _read_json(path)
            except (OSError, json.JSONDecodeError) as exc:
                problems.append(f"invalid JSON {display_path}: {exc}")
    return CheckResult(
        name=name,
        status="FAIL" if problems else "PASS",
        exit_code=1 if problems else 0,
        duration_seconds=round(time.monotonic() - started, 3),
        detail="; ".join(problems) if problems else f"{len(required)} evidence files valid",
    )


def run_command(spec: CommandCheck) -> CheckResult:
    started = time.monotonic()
    completed = subprocess.run(
        spec.argv,
        cwd=spec.cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output = completed.stdout
    problems: list[str] = []
    if completed.returncode != 0:
        problems.append(f"subprocess exited {completed.returncode}")
    if spec.required_pattern and not re.search(spec.required_pattern, output, re.MULTILINE):
        problems.append(f"required output pattern missing: {spec.required_pattern}")
    if spec.count_pattern:
        match = re.search(spec.count_pattern, output, re.MULTILINE)
        if not match:
            problems.append(f"test-count pattern missing: {spec.count_pattern}")
        elif int(match.group(1)) <= 0:
            problems.append("required suite discovered zero passing tests")
    skipped = re.search(r"(\d+)\s+skipped", output)
    observed_skips = int(skipped.group(1)) if skipped else 0
    if observed_skips != spec.expected_skips:
        problems.append(
            f"unexpected skip count: expected {spec.expected_skips}, observed {observed_skips}"
        )
    tail = "\n".join(output.rstrip().splitlines()[-12:])
    if problems:
        detail = "; ".join(problems)
        if tail:
            detail += f"\n--- subprocess tail ---\n{tail}"
    else:
        detail = tail or "command completed with required non-empty evidence"
    return CheckResult(
        name=spec.name,
        status="FAIL" if problems else "PASS",
        exit_code=completed.returncode if completed.returncode else (1 if problems else 0),
        duration_seconds=round(time.monotonic() - started, 3),
        detail=detail,
        command=list(spec.argv),
    )


def _audit_task(task: str) -> list[CheckResult]:
    evidence = {
        "T001": [
            TRACKING / "repository_map.json",
            TRACKING / "baseline.md",
            TRACKING / "handoffs" / "T001.json",
        ],
        "T002": [
            TRACKING / "reuse_inventory.json",
            TRACKING / "duel_rules.md",
            TRACKING / "handoffs" / "T002.json",
        ],
        "T003": [
            TRACKING / "toolchain.json",
            TRACKING / "baseline_tests.json",
            TRACKING / "handoffs" / "T003.json",
        ],
    }
    return [validate_evidence(f"{task.lower()}_evidence", evidence[task])]


def checks_for_task(task: str) -> list[CheckResult]:
    number = int(task[1:])
    if task in {"T001", "T002", "T003"}:
        return _audit_task(task)
    if task == "T004":
        return [
            run_command(
                CommandCheck(
                    name="verification_wrapper_tests",
                    argv=(sys.executable, "-m", "pytest", "-q", "tests/test_check_tool.py"),
                    required_pattern=r"\bpassed\b",
                    count_pattern=r"(\d+)\s+passed",
                )
            )
        ]
    return [
        CheckResult(
            name=f"task_contract_{task}",
            status="NOT_IMPLEMENTED",
            exit_code=2,
            duration_seconds=0.0,
            detail=(
                f"{task} is recognized (task {number}/160), but its required checks "
                "have not been implemented by its owning task."
            ),
        )
    ]


def checks_for_gate(gate: str) -> list[CheckResult]:
    return [
        CheckResult(
            name=f"gate_contract_{gate}",
            status="NOT_READY",
            exit_code=2,
            duration_seconds=0.0,
            detail=(
                f"{gate} is recognized but remains blocked through {GATE_OWNER[gate]}; "
                "its cumulative behavioural suite and gate packet are not implemented."
            ),
        )
    ]


def _target(value: str, prefix: str, highest: int) -> str:
    value = value.upper()
    if not re.fullmatch(rf"{prefix}\d{{3}}" if prefix == "T" else rf"{prefix}\d{{2}}", value):
        raise argparse.ArgumentTypeError(f"expected {prefix} task/gate identifier, got {value!r}")
    number = int(value[1:])
    if number < 1 or number > highest:
        raise argparse.ArgumentTypeError(f"unknown {prefix} identifier {value}")
    return value


def _write_report(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--task", type=lambda value: _target(value, "T", 160))
    choice.add_argument("--gate", type=lambda value: _target(value, "G", 10))
    parser.add_argument("--json-report", type=Path)
    args = parser.parse_args(argv)

    target = args.task or args.gate
    results = checks_for_task(args.task) if args.task else checks_for_gate(args.gate)
    passed = bool(results) and all(result.status == "PASS" for result in results)
    payload: dict[str, object] = {
        "target": target,
        "status": "PASS" if passed else "FAIL",
        "results": [asdict(result) for result in results],
    }
    if args.json_report:
        _write_report(args.json_report, payload)
    print(json.dumps(payload, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
