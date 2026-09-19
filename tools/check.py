#!/usr/bin/env python3
"""Fail-closed task and gate verification entrypoint.

T004 establishes the wrapper contract. Later tasks replace their explicit
NOT_IMPLEMENTED entries with meaningful checks; no future task or gate can
pass merely because its suite has not been wired yet.
"""

from __future__ import annotations

import argparse
import json
import os
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
GATE_AFTER_TASK = {
    24: "G01",
    48: "G02",
    58: "G03",
    76: "G04",
    96: "G05",
    114: "G06",
    132: "G07",
    142: "G08",
    150: "G09",
    160: "G10",
}
TASK_STATUSES = {
    "NOT_STARTED",
    "IN_PROGRESS",
    "DONE",
    "FAILED",
    "BLOCKED",
    "WAITING_HUMAN",
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


def validate_tracking_state(
    progress_path: Path = TRACKING / "progress.json",
    handoff_dir: Path = TRACKING / "handoffs",
) -> tuple[list[str], dict[str, str]]:
    problems: list[str] = []
    progress = _read_json(progress_path)
    if not isinstance(progress, dict):
        return ["progress root must be an object"], {"kind": "invalid", "id": ""}
    tasks = progress.get("tasks")
    gates = progress.get("gates")
    if not isinstance(tasks, dict) or not isinstance(gates, dict):
        return ["progress requires tasks and gates objects"], {"kind": "invalid", "id": ""}

    resume: dict[str, str] | None = None
    blocked_gate: str | None = None
    for number in range(1, 161):
        task = f"T{number:03d}"
        status = tasks.get(task)
        if status not in TASK_STATUSES:
            problems.append(f"{task} has invalid or missing status {status!r}")
            continue
        if blocked_gate and status == "DONE":
            problems.append(f"{task} is DONE while required {blocked_gate} is not PASS")
        if status == "DONE":
            receipt_path = handoff_dir / f"{task}.json"
            if not receipt_path.is_file():
                problems.append(f"{task} is DONE but receipt is missing")
            else:
                try:
                    receipt = _read_json(receipt_path)
                except (OSError, json.JSONDecodeError) as exc:
                    problems.append(f"{task} receipt is invalid: {exc}")
                else:
                    if not isinstance(receipt, dict):
                        problems.append(f"{task} receipt root must be an object")
                    else:
                        for field in ("task_id", "status", "commit", "files", "checks", "next_task"):
                            if field not in receipt:
                                problems.append(f"{task} receipt missing {field}")
                        if receipt.get("task_id") != task or receipt.get("status") != "DONE":
                            problems.append(f"{task} receipt identity/status mismatch")
                        commit = receipt.get("commit")
                        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
                            problems.append(f"{task} receipt commit is not a full SHA")
                        checks = receipt.get("checks")
                        if not isinstance(checks, list) or not checks:
                            problems.append(f"{task} completed receipt has no check evidence")
                        else:
                            for index, check in enumerate(checks):
                                if not isinstance(check, dict) or not all(
                                    key in check for key in ("command", "exit_code", "result")
                                ):
                                    problems.append(f"{task} check {index} lacks command/exit_code/result")
        elif resume is None and blocked_gate is None:
            resume = {"kind": "task", "id": task}

        gate = GATE_AFTER_TASK.get(number)
        if gate:
            gate_data = gates.get(gate)
            if not isinstance(gate_data, dict):
                problems.append(f"{gate} progress entry is missing")
                blocked_gate = gate
                continue
            gate_status = gate_data.get("status")
            if gate_status == "PASS":
                for field in ("accepted_by", "accepted_build", "evidence"):
                    if not gate_data.get(field):
                        problems.append(f"{gate} is PASS but {field} is missing")
            else:
                blocked_gate = gate
                if resume is None or all(tasks.get(f"T{i:03d}") == "DONE" for i in range(1, number + 1)):
                    resume = {"kind": "gate", "id": gate}

    if resume is None:
        resume = {"kind": "complete", "id": "T160"}
    current = progress.get("current_task")
    if resume["kind"] == "task" and current != resume["id"]:
        problems.append(f"current_task is {current!r}; first unmet dependency is {resume['id']}")
    return problems, resume


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


def _pytest(name: str, *paths: str) -> CheckResult:
    return run_command(
        CommandCheck(
            name=name,
            argv=(sys.executable, "-m", "pytest", "-q", *paths),
            required_pattern=r"\bpassed\b",
            count_pattern=r"(\d+)\s+passed",
        )
    )


def _godot_bin() -> str | None:
    env = os.environ.get("GODOT", "").strip()
    if env and Path(env).is_file():
        return env
    local = ROOT / ".dmb_windows_local.json"
    if local.is_file():
        try:
            data = _read_json(local)
            if isinstance(data, dict):
                exe = data.get("godot")
                if isinstance(exe, str) and Path(exe).is_file():
                    return exe
        except (OSError, json.JSONDecodeError):
            pass
    toolchain = TRACKING / "toolchain.json"
    if toolchain.is_file():
        try:
            data = _read_json(toolchain)
            if isinstance(data, dict):
                exe = ((data.get("godot") or {}) if isinstance(data.get("godot"), dict) else {}).get(
                    "executable"
                )
                if isinstance(exe, str) and Path(exe).is_file():
                    return exe
        except (OSError, json.JSONDecodeError):
            pass
    return None


def _godot_script(name: str, script: str, required_pattern: str) -> CheckResult:
    godot = _godot_bin()
    if not godot:
        return CheckResult(
            name=name,
            status="FAIL",
            exit_code=2,
            duration_seconds=0.0,
            detail="Godot executable not found (GODOT env, .dmb_windows_local.json, or toolchain.json)",
        )
    return run_command(
        CommandCheck(
            name=name,
            argv=(godot, "--headless", "--path", "godot_project", "--script", script),
            required_pattern=required_pattern,
        )
    )


def checks_for_task(task: str) -> list[CheckResult]:
    number = int(task[1:])
    if task in {"T001", "T002", "T003"}:
        return _audit_task(task)
    mapping = {
        "T004": lambda: [_pytest("verification_wrapper_tests", "tests/test_check_tool.py")],
        "T005": lambda: [_pytest("manifest_and_rule_map_tests", "tests/test_manifests.py")],
        "T006": lambda: [_pytest("tracking_and_receipt_tests", "tests/test_tracking.py")],
        "T007": lambda: [_pytest("id_allocator_tests", "tests/sim/test_t007_ids.py")],
        "T008": lambda: [_pytest("definition_catalog_tests", "tests/sim/test_t008_catalog.py")],
        "T009": lambda: [_pytest("world_state_view_tests", "tests/sim/test_t009_state.py")],
        "T010": lambda: [_pytest("rng_replay_tests", "tests/sim/test_t010_rng_replay.py")],
        "T011": lambda: [_pytest("command_dispatch_tests", "tests/sim/test_t011_commands.py")],
        "T012": lambda: [_pytest("clock_tests", "tests/sim/test_t012_clock.py")],
        "T013": lambda: [_pytest("turn_runner_tests", "tests/sim/test_t013_turns.py")],
        "T014": lambda: [_pytest("persistence_tests", "tests/sim/test_t014_persistence.py")],
        "T015": lambda: [_pytest("frame_codec_tests", "tests/sim/test_t015_codec.py")],
        "T016": lambda: [_pytest("bridge_protocol_tests", "tests/sim/test_t016_bridge.py")],
        "T017": lambda: [
            _godot_script(
                "g01_sidecar_smoke",
                "res://client/tests/run_g01_smoke.gd",
                r"G01_SMOKE_OK",
            )
        ],
        "T018": lambda: [_pytest("lease_registry_tests", "tests/sim/test_t018_leases.py")],
        "T019": lambda: [_pytest("recovery_tests", "tests/sim/test_t019_recovery.py")],
        "T020": lambda: [
            _pytest("playable_fx_clock_commands", "tests/sim/test_t020_playable.py"),
            _godot_script(
                "g01_playable_scene",
                "res://client/tests/run_g01_playable.gd",
                r"G01_PLAYABLE_OK",
            ),
            _godot_script(
                "g01_bridge_play",
                "res://client/tests/run_g01_bridge_play.gd",
                r"G01_BRIDGE_PLAY_OK",
            ),
        ],
        "T021": lambda: [_pytest("semantic_knowledge_tests", "tests/sim/test_t021_semantic.py")],
        "T022": lambda: [_pytest("clock_driver_tests", "tests/sim/test_t022_clock_driver.py")],
        "T023": lambda: [_pytest("fixture_entrypoint_tests", "tests/sim/test_t023_fixtures.py")],
        "T024": lambda: [
            _pytest(
                "bridge_clock_integration",
                "tests/integration/test_bridge_clock.py",
                "tests/sim/test_t023_fixtures.py",
            ),
            validate_evidence(
                "g01_gate_packet",
                [
                    TRACKING / "gates" / "G01" / "packet.md",
                    TRACKING / "gates" / "G01" / "launch.txt",
                    TRACKING / "gates" / "G01" / "fx_clock_record.json",
                ],
            ),
        ],
        "T025": lambda: [_pytest("hex_board_topology", "tests/sim/test_t025_board.py")],
        "T026": lambda: [_pytest("board_generation", "tests/sim/test_t026_generation.py")],
        "T027": lambda: [_pytest("buildings_units", "tests/sim/test_t027_buildings.py")],
        "T028": lambda: [_pytest("people_jobs", "tests/sim/test_t028_people.py")],
        "T029": lambda: [_pytest("catan_grants", "tests/sim/test_t029_catan_grants.py")],
        "T030": lambda: [_pytest("stock_ledger", "tests/sim/test_t030_stock.py")],
        "T031": lambda: [_pytest("placement_score", "tests/sim/test_t031_placement_score.py")],
        "T032": lambda: [_pytest("construction_orders", "tests/sim/test_t032_orders.py")],
        "T033": lambda: [_pytest("carts", "tests/sim/test_t033_carts.py")],
        "T034": lambda: [_pytest("routes_movement", "tests/sim/test_t034_routes.py")],
        "T035": lambda: [_pytest("logistics_director", "tests/sim/test_t035_director.py")],
        "T036": lambda: [_pytest("world_setup", "tests/sim/test_t036_setup.py")],
        "T037": lambda: [_pytest("destruction", "tests/sim/test_t037_destruction.py")],
        "T038": lambda: [
            _pytest(
                "construction_cargo_integration",
                "tests/integration/test_construction_cargo.py",
            )
        ],
        "T039": lambda: [_pytest("tech_defs", "tests/sim/test_t039_tech_defs.py")],
        "T040": lambda: [_pytest("research_archive", "tests/sim/test_t040_research.py")],
        "T041": lambda: [_pytest("tech_draft", "tests/sim/test_t041_draft.py")],
        "T042": lambda: [_pytest("legal_obs", "tests/sim/test_t042_legal_obs.py")],
        "T043": lambda: [_pytest("heuristic_policy", "tests/sim/test_t043_heuristic.py")],
        "T044": lambda: [_pytest("diplomacy", "tests/sim/test_t044_diplomacy.py")],
        "T045": lambda: [_pytest("bilateral_trade", "tests/sim/test_t045_trade.py")],
        "T046": lambda: [_pytest("seat_round", "tests/sim/test_t046_seat_round.py")],
        "T047": lambda: [_pytest("faction_expansion", "tests/scenarios/test_faction_expansion.py")],
        "T048": lambda: [
            _pytest(
                "g02_cumulative_python",
                "tests/integration/test_construction_cargo.py",
                "tests/sim/test_t045_trade.py",
                "tests/sim/test_t046_seat_round.py",
                "tests/scenarios/test_faction_expansion.py",
                "tests/sim/test_t020_playable.py",
            ),
            validate_evidence(
                "g02_gate_packet",
                [
                    TRACKING / "gates" / "G02" / "packet.md",
                    TRACKING / "gates" / "G02" / "launch.txt",
                    TRACKING / "gates" / "G02" / "fx_cargo_record.json",
                    TRACKING / "gates" / "G02" / "screenshot_wizard.png",
                    TRACKING / "gates" / "G02" / "screenshot_450x800.png",
                    TRACKING / "gates" / "G02" / "screenshot_720x1280.png",
                    TRACKING / "gates" / "G02" / "screenshot_1280x720.png",
                ],
            ),
            _godot_script(
                "g02_sidecar_smoke",
                "res://client/tests/run_g02_smoke.gd",
                r"G02_SMOKE_OK",
            ),
        ],
        "T049": lambda: [
            _pytest("industry_catalogue_tests", "tests/sim/test_t049_catalogues.py"),
            run_command(
                CommandCheck(
                    name="industry_catalogue_reproducibility",
                    argv=(sys.executable, "tools/content/import_recipes.py", "--check"),
                    required_pattern=r"T049_CATALOGUES_OK",
                )
            ),
        ],
        "T050": lambda: [_pytest("industry_layer_primary_tests", "tests/sim/test_t050_layers_primary.py")],
        "T051": lambda: [_pytest("industry_route_constraint_tests", "tests/sim/test_t051_routes_constraints.py")],
        "T052": lambda: [_pytest("industry_allocation_tests", "tests/sim/test_t052_allocation.py")],
        "T053": lambda: [_pytest("industry_factory_tests", "tests/sim/test_t053_factories.py")],
        "T054": lambda: [
            _pytest(
                "global_industry_tests",
                "tests/sim/test_t054_industry_service.py",
                "tests/sim/test_t053_factories.py",
            )
        ],
        "T055": lambda: [
            _pytest(
                "industry_worker_projection_tests",
                "tests/sim/test_t055_workers_projection.py",
                "tests/sim/test_t028_people.py",
            ),
            _godot_script(
                "worker_controller_smoke",
                "res://client/tests/run_worker_controller_smoke.gd",
                r"T055_WORKER_CONTROLLER_OK",
            ),
        ],
        "T056": lambda: [
            _pytest(
                "industry_repair_route_tests",
                "tests/sim/test_t056_industry_repairs_routes.py",
                "tests/sim/test_t032_orders.py",
                "tests/sim/test_t051_routes_constraints.py",
            )
        ],
        "T057": lambda: [
            _pytest(
                "industry_causality_scenarios",
                "tests/scenarios/test_industry_causality.py",
                "tests/sim/test_t054_industry_service.py",
            ),
            validate_evidence(
                "fx_industry_fixture_manifest",
                [ROOT / "godot_project" / "content" / "fixtures" / "industry" / "fx_industry_v1.json"],
            ),
        ],
        "T058": lambda: [
            _pytest(
                "g03_industry_cumulative",
                "tests/sim/test_t054_industry_service.py",
                "tests/sim/test_t055_workers_projection.py",
                "tests/sim/test_t056_industry_repairs_routes.py",
                "tests/scenarios/test_industry_causality.py",
            ),
            _godot_script(
                "g03_playable_smoke",
                "res://client/tests/run_g03_smoke.gd",
                r"G03_SMOKE_OK",
            ),
            validate_evidence(
                "g03_task_packet",
                [
                    TRACKING / "gates" / "G03" / "packet.md",
                    TRACKING / "gates" / "G03" / "launch.txt",
                    TRACKING / "gates" / "G03" / "acceptance.json",
                    TRACKING / "gates" / "G03" / "fx_industry_record.json",
                    TRACKING / "gates" / "G03" / "screenshot_450x800.png",
                    TRACKING / "gates" / "G03" / "screenshots" / "before_production.png",
                    TRACKING / "gates" / "G03" / "screenshots" / "after_unit_production.png",
                    TRACKING / "gates" / "G03" / "screenshots" / "worker_path_blocked.png",
                    TRACKING / "gates" / "G03" / "screenshots" / "damaged_bottleneck.png",
                    TRACKING / "gates" / "G03" / "screenshots" / "strike_stopped.png",
                    TRACKING / "gates" / "G03" / "known_defects.md",
                    TRACKING / "gates" / "G03" / "reset.md",
                ],
            ),
        ],
        "T059": lambda: [_pytest("military_unit_state", "tests/sim/test_t059_units.py")],
        "T060": lambda: [
            _pytest("combat_math", "tests/sim/test_t060_combat_math.py"),
            _godot_script(
                "combat_math_godot",
                "res://client/tests/run_combat_math.gd",
                r"COMBAT_MATH_OK",
            ),
        ],
        "T061": lambda: [_pytest("strategic_movement", "tests/sim/test_t061_movement.py")],
        "T062": lambda: [_pytest("offscreen_battle", "tests/sim/test_t062_offscreen.py")],
        "T063": lambda: [
            _pytest("local_battle_python", "tests/sim/test_t063_local_battle.py"),
            _godot_script(
                "local_battle_godot",
                "res://client/tests/run_local_battle.gd",
                r"LOCAL_BATTLE_OK",
            ),
        ],
        "T064": lambda: [_pytest("battle_handoffs", "tests/sim/test_t064_handoffs.py")],
        "T065": lambda: [_pytest("destruction_magic", "tests/sim/test_t065_magic.py")],
        "T066": lambda: [_pytest("support_buffs", "tests/sim/test_t066_buffs.py")],
        "T067": lambda: [_pytest("military_ai_turn", "tests/sim/test_t067_military_ai.py")],
        "T068": lambda: [
            _pytest("battle_magic_scenarios", "tests/scenarios/test_battle_magic.py"),
            validate_evidence(
                "fx_battle_fixture",
                [ROOT / "godot_project" / "content" / "fixtures" / "battle" / "fx_battle_v1.json"],
            ),
        ],
        "T069": lambda: [_pytest("hazard_cubes_deck", "tests/sim/test_t069_hazards.py")],
        "T070": lambda: [_pytest("outbreak_terminal", "tests/sim/test_t070_propagation.py")],
        "T071": lambda: [_pytest("hazard_disruption", "tests/sim/test_t071_disruption.py")],
        "T072": lambda: [_pytest("visit_allowances", "tests/sim/test_t072_visits.py")],
        "T073": lambda: [_pytest("hazard_responders", "tests/sim/test_t073_responders.py")],
        "T074": lambda: [_pytest("hazard_duels", "tests/sim/test_t074_hazard_duels.py")],
        "T075": lambda: [
            _pytest("catastrophe_scenarios", "tests/scenarios/test_catastrophe.py"),
            validate_evidence(
                "fx_hazard_fixture",
                [ROOT / "godot_project" / "content" / "fixtures" / "hazards" / "fx_hazard_v1.json"],
            ),
        ],
        "T076": lambda: [
            _pytest(
                "g04_cumulative_python",
                "tests/sim/test_t060_combat_math.py",
                "tests/sim/test_t064_handoffs.py",
                "tests/sim/test_t065_magic.py",
                "tests/sim/test_t066_buffs.py",
                "tests/scenarios/test_battle_magic.py",
                "tests/scenarios/test_catastrophe.py",
                "tests/sim/test_t070_propagation.py",
                "tests/sim/test_t072_visits.py",
                "tests/sim/test_r02_view_merge.py",
                "tests/sim/test_r03_fixture_ownership.py",
                "tests/sim/test_r04_semantic_magic.py",
                "tests/sim/test_r06_mastermind_duel.py",
                "tests/sim/test_g04_ward_pool_int_coercion.py",
                "tests/sim/test_u05_retained_ward_duel.py",
            ),
            _godot_script(
                "g04_playable_bridge",
                "res://client/tests/run_g04_playable.gd",
                r"G04_PLAYABLE_OK",
            ),
            _godot_script(
                "g04_spellbook_pointer",
                "res://client/tests/run_g04_spellbook_pointer.gd",
                r"G04_SPELLBOOK_POINTER_OK",
            ),
            _godot_script(
                "g04_lease_return",
                "res://client/tests/run_g04_lease_return.gd",
                r"G04_LEASE_RETURN_OK",
            ),
            _godot_script(
                "mira_semantic_label",
                "res://client/tests/run_mira_semantic_label.gd",
                r"MIRA_SEMANTIC_OK",
            ),
            validate_evidence(
                "g04_task_packet",
                [
                    TRACKING / "gates" / "G04" / "packet.md",
                    TRACKING / "gates" / "G04" / "launch.txt",
                    TRACKING / "gates" / "G04" / "acceptance.json",
                    TRACKING / "gates" / "G04" / "fx_battle_record.json",
                    TRACKING / "gates" / "G04" / "fx_hazard_record.json",
                    TRACKING / "gates" / "G04" / "screenshot_450x800.png",
                    TRACKING / "gates" / "G04" / "screenshot_battle_450x800.png",
                    TRACKING / "gates" / "G04" / "screenshot_hazard_450x800.png",
                    TRACKING / "gates" / "G04" / "known_defects.md",
                    TRACKING / "gates" / "G04" / "reset.md",
                ],
            ),
        ],
        "T077": lambda: [
            _pytest(
                "people_profiles",
                "tests/sim/test_t077_people_profiles.py",
                "tests/sim/test_t028_people.py",
            ),
            validate_evidence(
                "people_content",
                [
                    ROOT / "godot_project" / "content" / "source" / "people" / "preferences.json",
                    ROOT / "godot_project" / "content" / "source" / "people" / "dialogue_profiles.json",
                    ROOT / "godot_project" / "content" / "source" / "people" / "goals.json",
                ],
            ),
        ],
    }
    if task in mapping:
        return mapping[task]()
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
    if gate == "G01":
        packet = TRACKING / "gates" / "G01"
        results = [
            _pytest(
                "g01_cumulative_python",
                "tests/sim/test_t007_ids.py",
                "tests/sim/test_t012_clock.py",
                "tests/sim/test_t016_bridge.py",
                "tests/integration/test_bridge_clock.py",
                "tests/sim/test_t023_fixtures.py",
                "tests/sim/test_t020_playable.py",
            ),
            validate_evidence(
                "g01_packet_files",
                [
                    packet / "packet.md",
                    packet / "launch.txt",
                    packet / "fx_clock_record.json",
                    packet / "screenshot_wizard.png",
                    packet / "screenshot_450x800.png",
                    packet / "screenshot_720x1280.png",
                    packet / "screenshot_1280x720.png",
                ],
            ),
            # Fail closed if Godot is unavailable — G01 requires scene checks.
            _godot_script(
                "g01_sidecar_smoke",
                "res://client/tests/run_g01_smoke.gd",
                r"G01_SMOKE_OK",
            ),
            _godot_script(
                "g01_playable_scene",
                "res://client/tests/run_g01_playable.gd",
                r"G01_PLAYABLE_OK",
            ),
            _godot_script(
                "g01_bridge_play",
                "res://client/tests/run_g01_bridge_play.gd",
                r"G01_BRIDGE_PLAY_OK",
            ),
        ]
        return results
    if gate == "G02":
        packet = TRACKING / "gates" / "G02"
        return [
            _pytest(
                "g02_cumulative_python",
                "tests/integration/test_construction_cargo.py",
                "tests/sim/test_t045_trade.py",
                "tests/sim/test_t046_seat_round.py",
                "tests/scenarios/test_faction_expansion.py",
                "tests/sim/test_t020_playable.py",
                "tests/sim/test_presentation_journeys.py",
                "tests/sim/test_g02_perf_bridge.py",
            ),
            validate_evidence(
                "g02_packet_files",
                [
                    packet / "packet.md",
                    packet / "launch.txt",
                    packet / "fx_cargo_record.json",
                    packet / "screenshot_wizard.png",
                    packet / "screenshot_450x800.png",
                    packet / "screenshot_720x1280.png",
                    packet / "screenshot_1280x720.png",
                ],
            ),
            _godot_script(
                "g02_sidecar_smoke",
                "res://client/tests/run_g02_smoke.gd",
                r"G02_SMOKE_OK",
            ),
            _godot_script(
                "g02_cart_followthrough",
                "res://client/tests/run_g02_cart_followthrough.gd",
                r"G02_CART_FOLLOWTHROUGH_OK",
            ),
            # Retain meaningful G01 regressions (playable + bridge, not smoke alone).
            _godot_script(
                "g01_regression_smoke",
                "res://client/tests/run_g01_smoke.gd",
                r"G01_SMOKE_OK",
            ),
            _godot_script(
                "g01_regression_playable",
                "res://client/tests/run_g01_playable.gd",
                r"G01_PLAYABLE_OK",
            ),
            _godot_script(
                "g01_regression_bridge_play",
                "res://client/tests/run_g01_bridge_play.gd",
                r"G01_BRIDGE_PLAY_OK",
            ),
        ]
    if gate == "G03":
        packet = TRACKING / "gates" / "G03"
        return [
            _pytest(
                "g03_cumulative_python",
                "tests/sim/test_t054_industry_service.py",
                "tests/sim/test_t055_workers_projection.py",
                "tests/sim/test_t056_industry_repairs_routes.py",
                "tests/scenarios/test_industry_causality.py",
            ),
            validate_evidence(
                "g03_packet_files",
                [
                    packet / "packet.md",
                    packet / "launch.txt",
                    packet / "acceptance.json",
                    packet / "fx_industry_record.json",
                    packet / "screenshot_wizard.png",
                    packet / "screenshot_450x800.png",
                    packet / "screenshots" / "before_production.png",
                    packet / "screenshots" / "after_unit_production.png",
                    packet / "screenshots" / "worker_path_blocked.png",
                    packet / "screenshots" / "damaged_bottleneck.png",
                    packet / "screenshots" / "strike_stopped.png",
                    packet / "known_defects.md",
                    packet / "reset.md",
                ],
            ),
            _godot_script(
                "g03_sidecar_playable",
                "res://client/tests/run_g03_smoke.gd",
                r"G03_SMOKE_OK",
            ),
            _godot_script(
                "g02_regression_smoke",
                "res://client/tests/run_g02_smoke.gd",
                r"G02_SMOKE_OK",
            ),
            _godot_script(
                "g01_regression_smoke",
                "res://client/tests/run_g01_smoke.gd",
                r"G01_SMOKE_OK",
            ),
        ]
    if gate == "G04":
        packet = TRACKING / "gates" / "G04"
        return [
            _pytest(
                "g04_cumulative_python",
                "tests/sim/test_t060_combat_math.py",
                "tests/sim/test_t064_handoffs.py",
                "tests/sim/test_t065_magic.py",
                "tests/sim/test_t066_buffs.py",
                "tests/scenarios/test_battle_magic.py",
                "tests/scenarios/test_catastrophe.py",
                "tests/sim/test_t070_propagation.py",
                "tests/sim/test_t072_visits.py",
                "tests/sim/test_r02_view_merge.py",
                "tests/sim/test_r03_fixture_ownership.py",
                "tests/sim/test_r04_semantic_magic.py",
                "tests/sim/test_r06_mastermind_duel.py",
            ),
            validate_evidence(
                "g04_packet_files",
                [
                    packet / "packet.md",
                    packet / "launch.txt",
                    packet / "acceptance.json",
                    packet / "fx_battle_record.json",
                    packet / "fx_hazard_record.json",
                    packet / "screenshot_450x800.png",
                    packet / "screenshot_battle_450x800.png",
                    packet / "screenshot_hazard_450x800.png",
                    packet / "known_defects.md",
                    packet / "reset.md",
                ],
            ),
            _godot_script(
                "g04_sidecar_playable",
                "res://client/tests/run_g04_playable.gd",
                r"G04_PLAYABLE_OK",
            ),
            _godot_script(
                "g04_spellbook_pointer",
                "res://client/tests/run_g04_spellbook_pointer.gd",
                r"G04_SPELLBOOK_POINTER_OK",
            ),
            _godot_script(
                "g04_lease_return",
                "res://client/tests/run_g04_lease_return.gd",
                r"G04_LEASE_RETURN_OK",
            ),
            _godot_script(
                "g03_regression_smoke",
                "res://client/tests/run_g03_smoke.gd",
                r"G03_SMOKE_OK",
            ),
            _godot_script(
                "g02_regression_smoke",
                "res://client/tests/run_g02_smoke.gd",
                r"G02_SMOKE_OK",
            ),
            _godot_script(
                "g01_regression_smoke",
                "res://client/tests/run_g01_smoke.gd",
                r"G01_SMOKE_OK",
            ),
        ]
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
    choice.add_argument("--resume", action="store_true")
    parser.add_argument("--json-report", type=Path)
    args = parser.parse_args(argv)

    if args.resume:
        problems, resume = validate_tracking_state()
        payload = {
            "target": "resume",
            "status": "PASS" if not problems else "FAIL",
            "resume": resume,
            "problems": problems,
        }
        if args.json_report:
            _write_report(args.json_report, payload)
        print(json.dumps(payload, indent=2))
        return 0 if not problems else 1

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
