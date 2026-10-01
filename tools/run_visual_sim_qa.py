#!/usr/bin/env python3
"""Visual Simulation QA runner — sim / godot / pilot / long / oracle / report."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sim.dmb.testing.visual_sim.contracts import load_contract  # noqa: E402
from sim.dmb.testing.visual_sim.images import check_image  # noqa: E402
from sim.dmb.testing.visual_sim.oracle import run_oracle  # noqa: E402
from sim.dmb.testing.visual_sim.report import (  # noqa: E402
    new_run_dir,
    write_json,
    write_review_table,
    write_summary,
    write_combined_gallery,
    cluster_failures,
)
from sim.dmb.testing.visual_sim.runner import run_sim_smoke  # noqa: E402

GODOT_TIMEOUT_DEFAULT = 420
LONG_CEILINGS = {
    "wall_minutes": 90,
    "cheap_checkpoints": 1000,
    "screenshots": 300,
    "evidence_mib": 500,
}


def _godot() -> str:
    env = os.environ.get("GODOT", "").strip().strip('"')
    if env and Path(env).is_file():
        return env
    for cand in (
        Path.home() / "Documents/Godot/Godot_v4.4.1-stable_linux.x86_64",
        Path.home() / "Documents/Godot/Godot_v4.5.2-stable_linux.x86_64",
    ):
        if cand.is_file():
            return str(cand)
    raise SystemExit("Godot not found — set GODOT=")


def _git_meta() -> dict[str, Any]:
    def _run(args: list[str]) -> str:
        try:
            return subprocess.check_output(args, cwd=str(ROOT), text=True).strip()
        except Exception:
            return ""

    dirty = _run(["git", "status", "--porcelain"])
    return {
        "revision": _run(["git", "rev-parse", "HEAD"]),
        "dirty": bool(dirty),
        "dirty_summary": dirty[:2000],
        "branch": _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
    }


def _run_godot_kernel(
    run_dir: Path,
    *,
    mode: str,
    fixture: str,
    seed: int,
    resolution: str,
    session_id: str,
    headless: bool = False,
    timeout: int = GODOT_TIMEOUT_DEFAULT,
    variations: int = 1,
) -> dict[str, Any]:
    godot = _godot()
    env = os.environ.copy()
    env["DMB_VISUAL_SIM_OUT"] = str(run_dir)
    env["DMB_FIXTURE"] = fixture
    env["DMB_SEED"] = str(seed)
    env["DMB_VISUAL_SIM_MODE"] = mode
    env["DMB_RESOLUTION"] = resolution
    env["DMB_SESSION_ID"] = session_id
    env["DMB_VISUAL_SIM_VARIATIONS"] = str(max(1, int(variations)))
    env.setdefault("DMB_SAVE_SLOT", f"visual_sim_{run_dir.name}_{session_id}")
    cmd = [godot, "--path", str(ROOT / "godot_project"), "--rendering-driver", "opengl3"]
    if headless:
        cmd.append("--headless")
    if resolution:
        cmd += ["--resolution", resolution]
    cmd += ["--script", "res://client/tests/run_visual_sim_kernel.gd"]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        proc = subprocess.CompletedProcess(cmd, 124, exc.stdout or "", exc.stderr or "")
    log = run_dir / "logs" / f"godot_{mode}_{seed}_{resolution}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        f"$ {' '.join(cmd)}\nexit={proc.returncode}\ntimeout={timed_out}\nelapsed={time.time()-t0:.1f}s\n\n"
        f"STDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}\n",
        encoding="utf-8",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    runtime_errors = []
    for marker in ("SCRIPT ERROR", "Parse Error", "Invalid call", "ObjectDB instances leaked"):
        if marker in out:
            runtime_errors.append(marker)
    status = "OK"
    if timed_out:
        status = "TIMEOUT"
    elif proc.returncode != 0:
        status = "NONZERO_EXIT"
    elif "VISUAL_SIM_KERNEL_OK" not in out and "VISUAL_SIM_ORACLE_FAULTS_WRITTEN" not in out:
        status = "INCOMPLETE"
    if status in {"TIMEOUT", "NONZERO_EXIT"}:
        ok = False
    else:
        ok = "VISUAL_SIM_KERNEL_OK" in out or "VISUAL_SIM_ORACLE_FAULTS_WRITTEN" in out
    return {
        "exit_code": proc.returncode,
        "timed_out": timed_out,
        "ok_marker": "VISUAL_SIM_KERNEL_OK" in out,
        "status_class": status,
        "ok": ok and status not in {"TIMEOUT", "NONZERO_EXIT"},
        "log": str(log),
        "runtime_errors": runtime_errors,
        "elapsed_s": round(time.time() - t0, 2),
        "cmd": cmd,
        "variations": variations,
    }


def _load_checkpoint_artifacts(run_dir: Path) -> list[dict[str, Any]]:
    cps = sorted((run_dir / "checkpoints").glob("*.json")) if (run_dir / "checkpoints").is_dir() else []
    rows = []
    for p in cps:
        meta = json.loads(p.read_text(encoding="utf-8"))
        cid = meta.get("capture_id") or p.stem
        auth_p = run_dir / "authority" / f"{cid}.json"
        rend_p = run_dir / "render" / f"{cid}.json"
        authority = json.loads(auth_p.read_text(encoding="utf-8")) if auth_p.is_file() else None
        render = json.loads(rend_p.read_text(encoding="utf-8")) if rend_p.is_file() else None
        img_rel = meta.get("image_rel") or ""
        img_path = run_dir / img_rel if img_rel else None
        rows.append(
            {
                "capture_id": cid,
                "meta": meta,
                "authority": authority,
                "render": render,
                "image_path": img_path,
                "auth_rel": f"authority/{cid}.json" if auth_p.is_file() else "",
                "render_rel": f"render/{cid}.json" if rend_p.is_file() else "",
                "image_rel": img_rel,
            }
        )
    # Fallback: legacy single harvest layout
    if not rows:
        auth = run_dir / "authority" / "observe.json"
        rend = run_dir / "render" / "harvest.json"
        shots = sorted((run_dir / "shots").glob("*.png"))
        if auth.is_file() or rend.is_file() or shots:
            rows.append(
                {
                    "capture_id": "SMOKE_BOOT",
                    "meta": {"checkpoint": "after", "action": "fixture_boot"},
                    "authority": json.loads(auth.read_text(encoding="utf-8")) if auth.is_file() else None,
                    "render": json.loads(rend.read_text(encoding="utf-8")) if rend.is_file() else None,
                    "image_path": shots[0] if shots else None,
                    "auth_rel": "authority/observe.json" if auth.is_file() else "",
                    "render_rel": "render/harvest.json" if rend.is_file() else "",
                    "image_rel": f"shots/{shots[0].name}" if shots else "",
                }
            )
    return rows


def _verdict_row(
    *,
    planned: dict[str, Any],
    artifact: dict[str, Any] | None,
    contract: dict[str, Any],
    seed: int,
    resolution: str,
    session_id: str,
    scenario_class: str,
) -> dict[str, Any]:
    cid = planned["capture_id"]
    expect = planned.get("expectations") or contract.get("expectations") or {}
    mini_contract = {
        "scenario_id": contract.get("scenario_id"),
        "scenario_class": scenario_class,
        "fixture": contract.get("fixture"),
        "seed": seed,
        "expectations": expect,
    }
    authority = artifact.get("authority") if artifact else None
    render = artifact.get("render") if artifact else None
    image_result: dict[str, Any]
    if artifact and artifact.get("image_path") and Path(artifact["image_path"]).is_file():
        expect_size = tuple(int(x) for x in resolution.split("x")) if "x" in resolution else None
        image_result = check_image(artifact["image_path"], expect_size=expect_size)
    else:
        image_result = {"status": "FAIL", "code": "blank_or_missing_screenshot", "reason": "missing_capture"}

    # Session binding: authority must claim same session when present
    bind_failures: list[dict] = []
    if authority and authority.get("session_id") and authority.get("session_id") != session_id:
        bind_failures.append(
            {
                "code": "session_mismatch",
                "layer": "authority",
                "message": f"authority session {authority.get('session_id')} != {session_id}",
            }
        )
    if render and render.get("session_id") and render.get("session_id") != session_id:
        bind_failures.append(
            {
                "code": "session_mismatch",
                "layer": "render",
                "message": f"render session {render.get('session_id')} != {session_id}",
            }
        )
    if authority and render:
        aw = authority.get("world_version")
        rw = render.get("world_version")
        if aw is not None and rw is not None and int(aw) != int(rw):
            bind_failures.append(
                {
                    "code": "world_version_mismatch",
                    "layer": "bind",
                    "message": f"authority wv={aw} render wv={rw}",
                }
            )

    oracle = run_oracle(mini_contract, authority=authority, render=render, image=image_result)
    if bind_failures:
        oracle["failures"].extend(bind_failures)
        oracle["status"] = "FAIL"

    state_v = "PASS"
    render_v = "PASS"
    if any(f.get("layer") == "authority" for f in oracle["failures"]):
        state_v = "FAIL"
    if authority is None and (expect.get("authority") is not None):
        state_v = "FAIL"
    if any(f.get("layer") == "render" for f in oracle["failures"]):
        render_v = "FAIL"
    if render is None and (expect.get("render") is not None):
        render_v = "FAIL"
    image_v = image_result.get("status", "FAIL")
    overall = "PASS" if oracle["status"] == "PASS" and image_v == "PASS" and not bind_failures else "FAIL"
    if artifact is None:
        overall = "FAIL"
        oracle["failures"].append({"code": "missing_evidence", "layer": "oracle", "message": f"planned capture {cid} absent"})

    auth_summary = ""
    if authority:
        auth_summary = json.dumps(
            {
                "counts": authority.get("counts"),
                "world_version": authority.get("world_version"),
                "session_id": authority.get("session_id"),
                "sidecar": authority.get("sidecar"),
            }
        )
    rend_summary = ""
    if render:
        rend_summary = json.dumps(
            {
                "entity_count": render.get("entity_count"),
                "node_backed_count": render.get("node_backed_count"),
                "ui_overlaps": render.get("ui_overlaps"),
            }
        )

    return {
        "capture_id": cid,
        "scenario_id": contract.get("scenario_id"),
        "scenario_class": scenario_class,
        "checkpoint": planned.get("checkpoint") or (artifact or {}).get("meta", {}).get("checkpoint", ""),
        "seed": seed,
        "resolution": resolution,
        "session_id": session_id,
        "turn_or_time": (authority or {}).get("clock") if authority else "",
        "action": planned.get("action") or (artifact or {}).get("meta", {}).get("action", ""),
        "command_receipt": planned.get("command_receipt") or "",
        "should_be_visible": planned.get("should_be_visible") or (artifact or {}).get("meta", {}).get("should_be_visible", ""),
        "should_be_absent": planned.get("should_be_absent", ""),
        "should_change": planned.get("should_change", ""),
        "assertions": ",".join(planned.get("assertions") or []),
        "authority_summary": auth_summary,
        "render_summary": rend_summary,
        "authority_obs": authority,
        "render_obs": render,
        "image_result": image_v,
        "state_verdict": state_v,
        "render_verdict": render_v,
        "image_verdict": image_v,
        "failed_assertions": oracle.get("failures") or [],
        "assertion_count": oracle.get("assertion_count", 0),
        "overall": overall,
        "human_review": "PENDING",
        "retention": "keep" if overall != "PASS" else "pilot_or_first_long",
        "failure_signature": _signature(oracle.get("failures") or [], cid, contract.get("scenario_id")),
        "image_rel": (artifact or {}).get("image_rel", ""),
        "auth_rel": (artifact or {}).get("auth_rel", ""),
        "render_rel": (artifact or {}).get("render_rel", ""),
        "log_rel": "",
        "oracle": oracle,
    }


def _signature(failures: list[dict], capture_id: str, scenario_id: str | None) -> str:
    if not failures:
        return ""
    parts = [str(scenario_id or ""), str(capture_id)]
    for f in failures:
        parts.append(f.get("layer", ""))
        parts.append(f.get("code", ""))
        msg = str(f.get("message") or "")
        # Normalize volatile numbers
        norm = "".join(ch if not ch.isdigit() else "#" for ch in msg)[:120]
        parts.append(norm)
    raw = "|".join(parts)
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def cmd_sim(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    run_dir = new_run_dir(ROOT, args.run_id)
    packed = run_sim_smoke(contract)
    authority = packed["authority"]
    write_json(run_dir / "authority" / "observe.json", authority)
    oracle = run_oracle(contract, authority=authority, render=None, image=None, require_assertions=False)
    # Explicit sim-only scope — never claim visual PASS.
    from sim.dmb.testing.visual_sim.oracle import assert_authority_expectations

    try:
        assert_authority_expectations(contract, authority)
        status = "PASS"
    except Exception as exc:
        status = "FAIL"
        oracle = {"status": "FAIL", "failures": [{"code": "authority", "message": str(exc)}], "assertions": []}
    rows = [
        {
            "capture_id": "SIM_ONLY",
            "scenario_id": contract["scenario_id"],
            "scenario_class": contract["scenario_class"],
            "checkpoint": "after",
            "seed": contract["seed"],
            "resolution": "",
            "action": "fixture_boot",
            "should_be_visible": "n/a (sim-only; render/image NOT_RUN)",
            "assertions": "authority",
            "authority_summary": json.dumps(authority.get("counts")),
            "render_summary": "NOT_RUN",
            "image_result": "NOT_RUN",
            "state_verdict": status,
            "render_verdict": "NOT_RUN",
            "image_verdict": "NOT_RUN",
            "overall": status,
            "human_review": "PENDING",
            "image_rel": "",
            "failure_signature": "",
            "retention": "keep",
        }
    ]
    write_review_table(run_dir, rows)
    summary = {
        "mode": "sim",
        "scope": "authority_only",
        "run_id": run_dir.name,
        "status": status,
        "layers": {"authority": status, "render": "NOT_RUN", "image": "NOT_RUN"},
        "oracle": oracle,
        "git": _git_meta(),
        "platform": sys.platform,
        "windows_certified": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_summary(run_dir, summary)
    print(f"VISUAL_SIM_SIM_OK run={run_dir}" if status == "PASS" else "VISUAL_SIM_SIM_FAIL")
    return 0 if status == "PASS" else 1


def cmd_godot(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    run_dir = new_run_dir(ROOT, args.run_id)
    session_id = f"g_{uuid.uuid4().hex[:10]}"
    resolution = args.resolution or "1280x720"
    mode = str(contract.get("mode") or "smoke")
    g = _run_godot_kernel(
        run_dir,
        mode=mode,
        fixture=str(contract["fixture"]),
        seed=int(contract["seed"]),
        resolution=resolution,
        session_id=session_id,
        headless=bool(getattr(args, "force_headless", False)),
    )
    artifacts = {a["capture_id"]: a for a in _load_checkpoint_artifacts(run_dir)}
    planned = contract.get("captures") or [{"capture_id": "SMOKE_BOOT", "checkpoint": "after", "expectations": contract.get("expectations")}]
    rows = []
    for p in planned:
        # Attach per-capture expectations if absent
        if "expectations" not in p:
            p = {**p, "expectations": contract.get("expectations")}
        art = artifacts.get(p["capture_id"])
        row = _verdict_row(
            planned=p,
            artifact=art,
            contract=contract,
            seed=int(contract["seed"]),
            resolution=resolution,
            session_id=session_id,
            scenario_class=str(contract["scenario_class"]),
        )
        row["log_rel"] = Path(g["log"]).name if g.get("log") else ""
        rows.append(row)
    write_review_table(run_dir, rows)
    overall = "PASS" if g.get("ok") and all(r["overall"] == "PASS" for r in rows) else "FAIL"
    if g.get("status_class") in {"TIMEOUT", "NONZERO_EXIT", "INCOMPLETE"}:
        overall = "FAIL"
    summary = {
        "mode": "godot",
        "run_id": run_dir.name,
        "session_id": session_id,
        "status": overall,
        "planned_captures": len(planned),
        "produced_captures": len(artifacts),
        "checked_captures": len(rows),
        "godot": g,
        "git": _git_meta(),
        "platform": sys.platform,
        "godot_bin": _godot(),
        "windows_certified": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_summary(run_dir, summary)
    print(json.dumps({"status": overall, "run": str(run_dir)}, indent=2))
    print("VISUAL_SIM_GODOT_OK" if overall == "PASS" else "VISUAL_SIM_GODOT_FAIL")
    return 0 if overall == "PASS" else 1


def _expand_variations(captures: list[dict[str, Any]], variations: int) -> list[dict[str, Any]]:
    """Expand each semantic checkpoint into N movement-variation captures (_v0.._vN-1)."""
    if variations <= 1:
        return list(captures)
    out: list[dict[str, Any]] = []
    for cap in captures:
        base = str(cap["capture_id"])
        for vi in range(variations):
            row = dict(cap)
            row["capture_id"] = f"{base}_v{vi}"
            row["base_capture_id"] = base
            row["variation"] = vi
            row["should_be_visible"] = f"{cap.get('should_be_visible', '')} [variation v{vi} nudge]"
            out.append(row)
    return out


def _pilot_matrix(*, variations: int = 5) -> list[dict[str, Any]]:
    """Pilot: 2 journeys × 2 seeds × 2 resolutions × 4 checkpoints × variations."""
    seeds = [507, 511]
    resolutions = ["450x800", "1280x720"]
    journeys = [
        {
            "scenario_id": "journey_construction",
            "mode": "construction",
            "scenario_class": "PRODUCTION_JOURNEY",
            "fixture": "FX-MVP",
            "captures": [
                {"capture_id": "CONSTRUCT_BEFORE", "checkpoint": "before", "action": "setup", "should_be_visible": "World before construction waits", "expectations": {"authority": {"min_buildings": 1}, "render": {"min_node_backed": 1, "kinds_present": ["player"]}, "image": {"require_nonblank": True}}},
                {"capture_id": "CONSTRUCT_SCAFFOLD", "checkpoint": "transition", "action": "Wait", "should_be_visible": "Active construction order / scaffold", "should_change": "order reserved/in_progress", "expectations": {"authority": {"order_status_any": {"statuses": ["reserved", "ready", "in_progress", "delivering", "committed"], "min": 1}}, "render": {"min_node_backed": 1}, "image": {"require_nonblank": True}}},
                {"capture_id": "CONSTRUCT_DONE", "checkpoint": "after", "action": "Wait", "should_be_visible": "Committed order consequence", "should_be_absent": "scaffold for committed order", "expectations": {"authority": {"order_status_any": {"statuses": ["committed"], "min": 1}}, "render": {"min_node_backed": 1, "forbid_scaffold_orders": True}, "image": {"require_nonblank": True}}},
                {"capture_id": "CONSTRUCT_AFTERMATH", "checkpoint": "aftermath", "action": "Wait", "should_be_visible": "World after construction; no stale scaffold", "expectations": {"authority": {"order_status_any": {"statuses": ["committed"], "min": 1}}, "render": {"min_node_backed": 1, "forbid_scaffold_orders": True, "no_text_control_overlap": True}, "image": {"require_nonblank": True}}},
            ],
        },
        {
            "scenario_id": "journey_combat",
            "mode": "combat",
            "scenario_class": "PRODUCTION_JOURNEY",
            "fixture": "FX-MVP",
            "captures": [
                {"capture_id": "COMBAT_BEFORE", "checkpoint": "before", "action": "AdvanceGame", "should_be_visible": "Units/formations after industry", "expectations": {"authority": {"min_units": 1}, "render": {"min_node_backed": 1}, "image": {"require_nonblank": True}}},
                {"capture_id": "COMBAT_CONTACT", "checkpoint": "transition", "action": "Wait", "should_be_visible": "Battle contacted", "expectations": {"authority": {"battle_states_any": ["PENDING", "LOCAL", "ACTIVE", "OFFSCREEN", "READY"]}, "render": {"min_node_backed": 1}, "image": {"require_nonblank": True}}},
                {"capture_id": "COMBAT_ATTENDED", "checkpoint": "transition", "action": "OpenBattleLease", "should_be_visible": "Attended lease open", "expectations": {"authority": {"min_units": 1}, "render": {"min_node_backed": 1}, "image": {"require_nonblank": True}}},
                {"capture_id": "COMBAT_RETURN", "checkpoint": "aftermath", "action": "CloseBattleLease", "should_be_visible": "Returned to world; lease closed", "expectations": {"authority": {"min_units": 1, "lease_not_active_for_closed": True}, "render": {"min_node_backed": 1, "kinds_present": ["player"]}, "image": {"require_nonblank": True}}},
            ],
        },
    ]
    matrix = []
    for j in journeys:
        expanded = _expand_variations(j["captures"], variations)
        for seed in seeds:
            for res in resolutions:
                matrix.append({**j, "captures": expanded, "seed": seed, "resolution": res, "variations": variations})
    return matrix


def cmd_pilot(args: argparse.Namespace) -> int:
    variations = int(getattr(args, "variations", 5) or 5)
    matrix = _pilot_matrix(variations=variations)
    run_id = args.run_id or f"pilot_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    root_dir = new_run_dir(ROOT, run_id)
    # Preserve pointer to prior incomplete attempt.
    prior = ROOT / "qa" / "visual_sim" / "out" / "pilot_iter2"
    if prior.is_dir() and run_id != "pilot_iter2":
        write_json(root_dir / "prior_attempt.json", {
            "path": str(prior),
            "note": "First pilot attempt (INCOMPLETE 22/32) preserved; this run adds 5 movement variations per checkpoint.",
        })
    all_rows: list[dict[str, Any]] = []
    session_logs: list[dict] = []
    planned = 0
    produced = 0
    first_failures: list[dict] = []

    for cell in matrix:
        planned += len(cell["captures"])
        session_id = f"p_{cell['scenario_id']}_{cell['seed']}_{cell['resolution']}_{uuid.uuid4().hex[:6]}"
        cell_dir = root_dir / "sessions" / session_id
        cell_dir.mkdir(parents=True, exist_ok=True)
        for sub in ("shots", "authority", "render", "logs", "checkpoints"):
            (cell_dir / sub).mkdir(exist_ok=True)
        g = _run_godot_kernel(
            cell_dir,
            mode=cell["mode"],
            fixture=cell["fixture"],
            seed=int(cell["seed"]),
            resolution=cell["resolution"],
            session_id=session_id,
            timeout=int(getattr(args, "timeout", 900)),
            variations=int(cell.get("variations") or variations),
        )
        session_logs.append({"session_id": session_id, "godot": g, "cell": {k: cell[k] for k in ("scenario_id", "seed", "resolution", "mode") if k in cell}})
        artifacts = {a["capture_id"]: a for a in _load_checkpoint_artifacts(cell_dir)}
        produced += len([a for a in artifacts.values() if a.get("image_path")])
        contract = {
            "scenario_id": cell["scenario_id"],
            "scenario_class": cell["scenario_class"],
            "fixture": cell["fixture"],
            "seed": cell["seed"],
            "expectations": {},
        }
        for p in cell["captures"]:
            art = artifacts.get(p["capture_id"])
            row = _verdict_row(
                planned=p,
                artifact=art,
                contract=contract,
                seed=int(cell["seed"]),
                resolution=cell["resolution"],
                session_id=session_id,
                scenario_class=cell["scenario_class"],
            )
            row["variation"] = p.get("variation", 0)
            row["base_capture_id"] = p.get("base_capture_id", p["capture_id"])
            if row.get("image_rel"):
                row["image_rel"] = f"sessions/{session_id}/{row['image_rel']}"
            if row.get("auth_rel"):
                row["auth_rel"] = f"sessions/{session_id}/{row['auth_rel']}"
            if row.get("render_rel"):
                row["render_rel"] = f"sessions/{session_id}/{row['render_rel']}"
            row["log_rel"] = f"sessions/{session_id}/logs/{Path(g['log']).name}" if g.get("log") else ""
            if row["overall"] != "PASS" and len(first_failures) < 80:
                first_failures.append({"session": session_id, "capture": row["capture_id"], "failures": row["failed_assertions"], "godot": g.get("status_class")})
            all_rows.append(row)

    write_review_table(root_dir, all_rows)
    write_combined_gallery(root_dir, all_rows)
    packets = cluster_failures(root_dir, all_rows)
    checked = len(all_rows)
    incomplete = any(r["overall"] != "PASS" for r in all_rows) or produced < planned
    status = "PASS" if not incomplete and all(r["overall"] == "PASS" for r in all_rows) else ("INCOMPLETE" if produced < planned else "FAIL")
    summary = {
        "mode": "pilot",
        "run_id": root_dir.name,
        "status": status,
        "variations_per_checkpoint": variations,
        "planned_captures": planned,
        "produced_captures": produced,
        "checked_captures": checked,
        "unique_failure_signatures": sorted({r["failure_signature"] for r in all_rows if r.get("failure_signature")}),
        "failure_packets": len(packets),
        "first_attempt_failures": first_failures,
        "prior_attempt": "qa/visual_sim/out/pilot_iter2" if prior.is_dir() else None,
        "sessions": session_logs,
        "git": _git_meta(),
        "platform": sys.platform,
        "godot_bin": _godot(),
        "godot_version": "4.4.1",
        "windows_certified": False,
        "reproduction": f"DISPLAY=:0 python3 tools/run_visual_sim_qa.py pilot --variations {variations} --run-id {root_dir.name}",
        "gallery": str(root_dir / "index.html"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_summary(root_dir, summary)
    write_json(root_dir / "session_logs.json", session_logs)
    print(json.dumps({k: summary[k] for k in ("status", "planned_captures", "produced_captures", "checked_captures", "variations_per_checkpoint", "gallery", "unique_failure_signatures")}, indent=2))
    print(f"VISUAL_SIM_PILOT_{status} run={root_dir}")
    return 0 if status == "PASS" else 1


def _expanded_matrix() -> list[dict[str, Any]]:
    """Up to 120 captures: 5 families × 3 seeds × 2 res × ≤4 checkpoints."""
    seeds = [507, 511, 521]
    resolutions = ["450x800", "1280x720"]
    families = [
        *_pilot_matrix_families(),
        {
            "scenario_id": "ui_move",
            "mode": "ui_move",
            "scenario_class": "PRODUCTION_JOURNEY",
            "fixture": "FX-MVP",
            "captures": [
                {"capture_id": "UI_BEFORE", "checkpoint": "before", "action": "boot", "should_be_visible": "HUD before map", "expectations": {"authority": {"min_buildings": 1}, "render": {"min_node_backed": 1, "control_visible": ["control:wait"]}, "image": {"require_nonblank": True}}},
                {"capture_id": "UI_MAP_OPEN", "checkpoint": "transition", "action": "open_world_map", "should_be_visible": "World map open", "expectations": {"render": {"control_visible": ["control:world_map"], "min_node_backed": 1}, "image": {"require_nonblank": True}}},
                {"capture_id": "UI_AFTER_WAIT", "checkpoint": "after", "action": "pointer_Wait", "should_be_visible": "After pointer Wait", "should_change": "clock/turn advanced", "expectations": {"authority": {"min_buildings": 1}, "render": {"min_node_backed": 1}, "image": {"require_nonblank": True}}},
                {"capture_id": "UI_MAP_CLOSED", "checkpoint": "aftermath", "action": "close_world_map", "should_be_visible": "Map closed", "expectations": {"render": {"min_node_backed": 1}, "image": {"require_nonblank": True}}},
            ],
        },
        {
            "scenario_id": "smoke_boot",
            "mode": "smoke",
            "scenario_class": "ARRANGED_STATE",
            "fixture": "FX-MVP",
            "captures": [
                {"capture_id": "SMOKE_BOOT", "checkpoint": "after", "action": "fixture_boot", "should_be_visible": "Boot overworld nonblank", "expectations": {"authority": {"min_buildings": 1, "player_node_id": "node:35"}, "render": {"min_node_backed": 1, "kinds_present": ["player"]}, "image": {"require_nonblank": True}}},
            ],
        },
    ]
    # Draft / age: report presentation gap via ARRANGED_STATE smoke of authority keys only if no player draft UI.
    families.append(
        {
            "scenario_id": "draft_authority_observe",
            "mode": "smoke",
            "scenario_class": "ARRANGED_STATE",
            "fixture": "FX-MVP",
            "note": "Canonical faction drafting is autonomous; no invented player card controls. Observe tech_draft/research keys at boot.",
            "captures": [
                {"capture_id": "SMOKE_BOOT", "checkpoint": "after", "action": "fixture_boot", "should_be_visible": "Boot; draft keys observable in authority if present", "expectations": {"authority": {"min_buildings": 1}, "render": {"min_node_backed": 1}, "image": {"require_nonblank": True}}},
            ],
        }
    )
    matrix = []
    for fam in families:
        for seed in seeds:
            for res in resolutions:
                matrix.append({**fam, "seed": seed, "resolution": res})
    # Cap at 120 planned captures
    planned = 0
    capped = []
    for cell in matrix:
        n = len(cell["captures"])
        if planned + n > 120:
            break
        capped.append(cell)
        planned += n
    return capped


def _pilot_matrix_families() -> list[dict[str, Any]]:
    """Journey family templates without seeds/resolutions."""
    full = _pilot_matrix(variations=1)
    seen = {}
    for cell in full:
        seen[cell["scenario_id"]] = {
            "scenario_id": cell["scenario_id"],
            "mode": cell["mode"],
            "scenario_class": cell["scenario_class"],
            "fixture": cell["fixture"],
            "captures": cell["captures"],
        }
    return list(seen.values())


def cmd_long(args: argparse.Namespace) -> int:
    ceilings = dict(LONG_CEILINGS)
    run_id = args.run_id or f"long_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    root_dir = new_run_dir(ROOT, run_id)
    t0 = time.time()
    deadline = t0 + ceilings["wall_minutes"] * 60
    matrix = _expanded_matrix()
    all_rows: list[dict[str, Any]] = []
    cheap_checks = 0
    screenshots = 0
    planned = sum(len(c["captures"]) for c in matrix)
    session_logs = []
    stalled = []

    # Cheap sim-only checkpoints first (no headed rendering).
    from sim.dmb.testing.visual_sim.slices import run_slice_a_combat, run_slice_b_construction

    for seed in (507, 511, 521, 601, 602):
        if cheap_checks >= ceilings["cheap_checkpoints"] or time.time() > deadline:
            break
        b = run_slice_b_construction(seed=seed)
        cheap_checks += 1
        a = run_slice_a_combat(seed=seed)
        cheap_checks += 1
        write_json(root_dir / "cheap" / f"construct_{seed}.json", {"ok": b["ok"], "order": b.get("committed_order"), "seed": seed})
        write_json(root_dir / "cheap" / f"combat_{seed}.json", {"ok": a["ok"], "attended": a.get("attended_ok"), "seed": seed})
        if not b["ok"]:
            stalled.append({"kind": "construct_sim", "seed": seed})
        if not a["ok"]:
            stalled.append({"kind": "combat_sim", "seed": seed})

    for cell in matrix:
        if time.time() > deadline or screenshots >= ceilings["screenshots"]:
            break
        evidence_mib = _dir_mib(root_dir)
        if evidence_mib >= ceilings["evidence_mib"]:
            stalled.append({"kind": "evidence_budget", "mib": evidence_mib})
            break
        session_id = f"l_{cell['scenario_id']}_{cell['seed']}_{cell['resolution']}_{uuid.uuid4().hex[:6]}"
        cell_dir = root_dir / "sessions" / session_id
        cell_dir.mkdir(parents=True, exist_ok=True)
        for sub in ("shots", "authority", "render", "logs", "checkpoints"):
            (cell_dir / sub).mkdir(exist_ok=True)
        g = _run_godot_kernel(
            cell_dir,
            mode=cell["mode"],
            fixture=cell["fixture"],
            seed=int(cell["seed"]),
            resolution=cell["resolution"],
            session_id=session_id,
            timeout=int(getattr(args, "timeout", GODOT_TIMEOUT_DEFAULT)),
        )
        session_logs.append({"session_id": session_id, "godot": g})
        artifacts = {a["capture_id"]: a for a in _load_checkpoint_artifacts(cell_dir)}
        screenshots += len([a for a in artifacts.values() if a.get("image_path")])
        contract = {
            "scenario_id": cell["scenario_id"],
            "scenario_class": cell["scenario_class"],
            "fixture": cell["fixture"],
            "seed": cell["seed"],
            "expectations": {},
        }
        for p in cell["captures"]:
            row = _verdict_row(
                planned=p,
                artifact=artifacts.get(p["capture_id"]),
                contract=contract,
                seed=int(cell["seed"]),
                resolution=cell["resolution"],
                session_id=session_id,
                scenario_class=cell["scenario_class"],
            )
            if row.get("image_rel"):
                row["image_rel"] = f"sessions/{session_id}/{row['image_rel']}"
            if row.get("auth_rel"):
                row["auth_rel"] = f"sessions/{session_id}/{row['auth_rel']}"
            if row.get("render_rel"):
                row["render_rel"] = f"sessions/{session_id}/{row['render_rel']}"
            row["log_rel"] = f"sessions/{session_id}/logs/{Path(g['log']).name}" if g.get("log") else ""
            all_rows.append(row)

    write_review_table(root_dir, all_rows)
    write_combined_gallery(root_dir, all_rows)
    packets = cluster_failures(root_dir, all_rows)
    produced = screenshots
    checked = len(all_rows)
    budget_hit = time.time() > deadline or screenshots >= ceilings["screenshots"] or _dir_mib(root_dir) >= ceilings["evidence_mib"]
    all_pass = all(r["overall"] == "PASS" for r in all_rows) if all_rows else False
    if checked < planned or produced < planned:
        status = "INCOMPLETE"
    elif not all_pass:
        status = "FAIL"
    elif budget_hit and checked < planned:
        status = "INCOMPLETE"
    else:
        status = "PASS"
    summary = {
        "mode": "long",
        "run_id": root_dir.name,
        "status": status,
        "ceilings": ceilings,
        "cheap_checkpoints": cheap_checks,
        "planned_captures": planned,
        "produced_captures": produced,
        "checked_captures": checked,
        "evidence_mib": _dir_mib(root_dir),
        "elapsed_s": round(time.time() - t0, 1),
        "stalled": stalled,
        "unique_failure_signatures": sorted({r["failure_signature"] for r in all_rows if r.get("failure_signature")}),
        "failure_packets": len(packets),
        "git": _git_meta(),
        "platform": sys.platform,
        "godot_bin": _godot(),
        "windows_certified": False,
        "reproduction": f"DISPLAY=:0 python3 tools/run_visual_sim_qa.py profile long --run-id {root_dir.name}",
        "gallery": str(root_dir / "index.html"),
        "pruning_policy": "Retain pilot + first completed long run screenshots. Later runs may prune older PASS evidence; retain FAIL until triaged.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_summary(root_dir, summary)
    write_json(root_dir / "session_logs.json", session_logs)
    print(json.dumps({k: summary[k] for k in ("status", "planned_captures", "produced_captures", "checked_captures", "cheap_checkpoints", "gallery", "unique_failure_signatures")}, indent=2))
    print(f"VISUAL_SIM_LONG_{status} run={root_dir}")
    return 0 if status == "PASS" else 1


def _dir_mib(path: Path) -> float:
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            total += p.stat().st_size
    return round(total / (1024 * 1024), 2)


def cmd_oracle(args: argparse.Namespace) -> int:
    """Disposable Godot faults → Python verdict pipeline (healthy + negatives)."""
    run_dir = new_run_dir(ROOT, args.run_id or f"oracle_{uuid.uuid4().hex[:8]}")
    session_id = f"oracle_{uuid.uuid4().hex[:8]}"
    g = _run_godot_kernel(
        run_dir,
        mode="oracle_fault",
        fixture="FX-MVP",
        seed=507,
        resolution=args.resolution or "1280x720",
        session_id=session_id,
    )
    healthy_art = None
    for a in _load_checkpoint_artifacts(run_dir):
        if a["capture_id"] == "FAULT_HEALTHY":
            healthy_art = a
            break
    fault_target = {}
    tp = run_dir / "logs" / "fault_target.json"
    if tp.is_file():
        fault_target = json.loads(tp.read_text(encoding="utf-8"))
    sid = str(fault_target.get("sim_id") or "")
    cases = [
        ("healthy", healthy_art, {"render": {"require_sim_ids": [sid]} if sid else {"min_node_backed": 1}, "image": {"require_nonblank": True}}, "PASS", None),
        ("duplicate", _fault_render(run_dir, "fault_duplicate.json", healthy_art), {"render": {"require_sim_ids": [sid]}}, "FAIL", "duplicate_render_entity"),
        ("hidden", _fault_render(run_dir, "fault_hidden.json", healthy_art), {"render": {"entity_visible": [sid]}}, "FAIL", "hidden_or_off_viewport"),
        ("moved", _fault_render(run_dir, "fault_moved.json", healthy_art), {"render": {"grid_near": [{"sim_id": sid, "grid": [0, 0], "tol": 2.0}]}}, "FAIL", "wrong_location"),
        ("missing", _fault_render(run_dir, "fault_missing.json", healthy_art), {"render": {"require_sim_ids": [sid]}}, "FAIL", "missing_render_entity"),
    ]
    # Blank screenshot negative via Python
    from PIL import Image

    blank = run_dir / "shots" / "solid_blank.png"
    blank.parent.mkdir(exist_ok=True)
    Image.new("RGB", (64, 64), (40, 40, 200)).save(blank)
    blank_check = check_image(blank)
    results = []
    ok = g.get("ok") or "VISUAL_SIM_ORACLE_FAULTS_WRITTEN" in Path(g["log"]).read_text(encoding="utf-8")
    for name, art, expect, want_status, want_code in cases:
        contract = {
            "scenario_id": f"oracle_{name}",
            "scenario_class": "ARRANGED_STATE",
            "fixture": "FX-MVP",
            "seed": 507,
            "expectations": expect,
        }
        if name == "healthy" and art:
            image = check_image(art["image_path"]) if art.get("image_path") else {"status": "FAIL", "code": "blank_or_missing_screenshot"}
            oracle = run_oracle(contract, authority=art.get("authority"), render=art.get("render"), image=image)
        else:
            render = art if isinstance(art, dict) and "entities" in art else (art or {}).get("render") if isinstance(art, dict) else None
            # For fault JSON files, art is the render dict
            if isinstance(art, dict) and "entities" in art:
                render = art
            oracle = run_oracle(contract, render=render, image={"status": "PASS", "near_blank": False, "bytes": 1000} if name != "healthy" else None)
        code = (oracle.get("failures") or [{}])[0].get("code") if oracle.get("failures") else None
        passed = oracle["status"] == want_status and (want_code is None or code == want_code)
        results.append({"case": name, "want": want_status, "want_code": want_code, "got": oracle["status"], "code": code, "ok": passed, "oracle": oracle})
        if not passed:
            ok = False
    blank_oracle = run_oracle(
        {"scenario_id": "blank", "scenario_class": "ARRANGED_STATE", "fixture": "FX-MVP", "seed": 507, "expectations": {"image": {"require_nonblank": True}}},
        image=blank_check,
    )
    blank_ok = blank_oracle["status"] == "FAIL" and (blank_oracle["failures"][0]["code"] == "blank_or_missing_screenshot")
    results.append({"case": "solid_screenshot", "ok": blank_ok, "oracle": blank_oracle})
    ok = ok and blank_ok

    # Restore healthy must pass again
    if healthy_art and sid:
        restored = run_oracle(
            {"scenario_id": "restored", "scenario_class": "ARRANGED_STATE", "fixture": "FX-MVP", "seed": 507, "expectations": {"render": {"require_sim_ids": [sid]}, "image": {"require_nonblank": True}}},
            authority=healthy_art.get("authority"),
            render=healthy_art.get("render"),
            image=check_image(healthy_art["image_path"]) if healthy_art.get("image_path") else {"status": "FAIL"},
        )
        results.append({"case": "restore_healthy", "ok": restored["status"] == "PASS", "oracle": restored})
        ok = ok and restored["status"] == "PASS"

    write_json(run_dir / "oracle_results.json", {"results": results, "godot": g, "fault_target": fault_target})
    write_summary(run_dir, {"mode": "oracle", "status": "PASS" if ok else "FAIL", "results": results, "git": _git_meta(), "windows_certified": False})
    print(json.dumps({"status": "PASS" if ok else "FAIL", "results": [{k: r[k] for k in ("case", "ok", "code", "want_code") if k in r} for r in results]}, indent=2))
    print("VISUAL_SIM_ORACLE_OK" if ok else "VISUAL_SIM_ORACLE_FAIL")
    return 0 if ok else 1


def _fault_render(run_dir: Path, name: str, healthy_art: dict | None) -> dict | None:
    p = run_dir / "render" / name
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def cmd_report(args: argparse.Namespace) -> int:
    run_dir = Path(args.path)
    rows = []
    jsonl = run_dir / "screenshots.jsonl"
    if jsonl.is_file():
        for line in jsonl.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    write_combined_gallery(run_dir, rows)
    cluster_failures(run_dir, rows)
    print(f"VISUAL_SIM_REPORT_OK {run_dir / 'index.html'}")
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    """Prune older PASS evidence; retain failures and protected runs."""
    out = ROOT / "qa" / "visual_sim" / "out"
    protect = set(args.keep or [])
    protect.update({"pilot_", "long_"})  # prefix protect first of each via policy file
    policy = out / "_retention.json"
    retained = []
    if policy.is_file():
        retained = json.loads(policy.read_text(encoding="utf-8")).get("retain") or []
    removed = []
    for d in sorted(out.iterdir()):
        if not d.is_dir():
            continue
        if d.name in retained or any(d.name.startswith(p) for p in retained):
            continue
        summary_p = d / "summary.json"
        if not summary_p.is_file():
            continue
        summary = json.loads(summary_p.read_text(encoding="utf-8"))
        if summary.get("status") != "PASS":
            continue  # retain failures until triaged
        if args.dry_run:
            removed.append(d.name)
            continue
        shutil.rmtree(d)
        removed.append(d.name)
    print(json.dumps({"pruned": removed, "dry_run": args.dry_run}))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Visual Simulation QA")
    ap.add_argument("--run-id", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_sim = sub.add_parser("sim")
    p_sim.add_argument("--contract", default="smoke_boot.json")
    p_sim.add_argument("--run-id", default=None)
    p_sim.set_defaults(func=cmd_sim)

    p_g = sub.add_parser("godot")
    p_g.add_argument("--contract", default="smoke_boot.json")
    p_g.add_argument("--resolution", default="1280x720")
    p_g.add_argument("--headed", action="store_true")
    p_g.add_argument("--run-id", default=None)
    p_g.set_defaults(func=cmd_godot)

    p_pilot = sub.add_parser("pilot", help="32-capture construction+combat pilot (× variations)")
    p_pilot.add_argument("--run-id", default=None)
    p_pilot.add_argument("--timeout", type=int, default=900)
    p_pilot.add_argument("--variations", type=int, default=5, help="Movement variations per checkpoint (default 5)")
    p_pilot.set_defaults(func=cmd_pilot)

    p_oracle = sub.add_parser("oracle", help="Disposable fault oracle via live pipeline")
    p_oracle.add_argument("--run-id", default=None)
    p_oracle.add_argument("--resolution", default="1280x720")
    p_oracle.set_defaults(func=cmd_oracle)

    p_r = sub.add_parser("report")
    p_r.add_argument("path")
    p_r.set_defaults(func=cmd_report)

    p_prune = sub.add_parser("prune")
    p_prune.add_argument("--dry-run", action="store_true")
    p_prune.add_argument("--keep", nargs="*", default=[])
    p_prune.set_defaults(func=cmd_prune)

    p_prof = sub.add_parser("profile")
    p_prof.add_argument("name", choices=["smoke", "long", "pilot"])
    p_prof.add_argument("--headed", action="store_true")
    p_prof.add_argument("--contract", default="smoke_boot.json")
    p_prof.add_argument("--resolution", default="1280x720")
    p_prof.add_argument("--run-id", default=None)
    p_prof.add_argument("--timeout", type=int, default=GODOT_TIMEOUT_DEFAULT)
    p_prof.add_argument("--variations", type=int, default=5)

    def _profile(ns: argparse.Namespace) -> int:
        if ns.name == "smoke":
            ns.run_id = ns.run_id or f"smoke_{uuid.uuid4().hex[:8]}"
            return cmd_godot(ns)
        if ns.name == "pilot":
            return cmd_pilot(ns)
        return cmd_long(ns)

    p_prof.set_defaults(func=_profile)

    args = ap.parse_args()
    if not getattr(args, "run_id", None):
        args.run_id = None
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
