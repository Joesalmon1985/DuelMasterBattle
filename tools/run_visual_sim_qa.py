#!/usr/bin/env python3
"""Visual Simulation QA runner — cheap sim / Godot / headed modes."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sim.dmb.testing.visual_sim.authority import observe_authority  # noqa: E402
from sim.dmb.testing.visual_sim.contracts import load_contract  # noqa: E402
from sim.dmb.testing.visual_sim.images import check_image  # noqa: E402
from sim.dmb.testing.visual_sim.oracle import run_oracle  # noqa: E402
from sim.dmb.testing.visual_sim.report import new_run_dir, write_json, write_review_table, write_summary  # noqa: E402
from sim.dmb.testing.visual_sim.runner import run_sim_smoke  # noqa: E402


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


def _run_godot_kernel(run_dir: Path, contract: dict, *, headless: bool, resolution: str) -> dict:
    godot = _godot()
    env = os.environ.copy()
    env["DMB_VISUAL_SIM_OUT"] = str(run_dir)
    env["DMB_FIXTURE"] = str(contract["fixture"])
    env["DMB_SEED"] = str(contract["seed"])
    env["DMB_VISUAL_SIM_MODE"] = str(contract.get("mode") or "smoke")
    env["DMB_RESOLUTION"] = resolution
    env["DMB_VISUAL_SIM_WAITS"] = str(int((contract.get("setup") or {}).get("waits") or 0))
    env.setdefault("DMB_SAVE_SLOT", f"visual_sim_{run_dir.name}")
    cmd = [godot, "--path", str(ROOT / "godot_project"), "--rendering-driver", "opengl3"]
    # Dummy headless renderer cannot capture viewport textures — prefer OpenGL window.
    if headless:
        cmd.append("--headless")
    if resolution:
        cmd += ["--resolution", resolution]
    cmd += ["--script", "res://client/tests/run_visual_sim_kernel.gd"]
    proc = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=180)
    log = run_dir / "logs" / "godot_kernel.log"
    log.write_text(
        f"$ {' '.join(cmd)}\nexit={proc.returncode}\n\nSTDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}\n",
        encoding="utf-8",
    )
    return {
        "exit_code": proc.returncode,
        "ok_marker": "VISUAL_SIM_KERNEL_OK" in (proc.stdout + proc.stderr),
        "log": str(log),
        "stdout_tail": (proc.stdout or "")[-500:],
    }


def cmd_sim(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    run_dir = new_run_dir(ROOT, args.run_id)
    packed = run_sim_smoke(contract)
    authority = packed["authority"]
    write_json(run_dir / "authority" / "observe.json", authority)
    # Sim-only: render/image NOT_RUN — still prove Layer1 independent of contract source.
    oracle = run_oracle(contract, authority=authority, render=None, image=None)
    # Re-run authority expectations only for gate when --sim
    from sim.dmb.testing.visual_sim.oracle import assert_authority_expectations

    assert_authority_expectations(contract, authority)
    rows = [
        {
            "capture_id": "SIM_ONLY",
            "scenario_id": contract["scenario_id"],
            "scenario_class": contract["scenario_class"],
            "checkpoint": "after",
            "seed": contract["seed"],
            "resolution": "",
            "action": "fixture_boot",
            "should_be_visible": "n/a (sim mode)",
            "assertions": "authority",
            "authority_summary": json.dumps(authority.get("counts")),
            "render_summary": "NOT_RUN",
            "image_result": "NOT_RUN",
            "overall": "PASS",
            "human_review": "PENDING",
            "image_rel": "",
        }
    ]
    write_review_table(run_dir, rows)
    summary = {
        "mode": "sim",
        "run_id": run_dir.name,
        "scenario_id": contract["scenario_id"],
        "scenario_class": contract["scenario_class"],
        "status": "PASS",
        "layers": {"authority": "PASS", "render": "NOT_RUN", "image": "NOT_RUN"},
        "oracle": oracle,
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_summary(run_dir, summary)
    print(json.dumps(summary, indent=2))
    print(f"VISUAL_SIM_SIM_OK run={run_dir}")
    return 0


def cmd_godot(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    run_dir = new_run_dir(ROOT, args.run_id)
    packed = run_sim_smoke(contract)
    authority = packed["authority"]
    write_json(run_dir / "authority" / "observe.json", authority)

    resolution = args.resolution or "1280x720"
    # Screenshots require a real renderer; default is OpenGL windowed (not dummy headless).
    g = _run_godot_kernel(run_dir, contract, headless=bool(getattr(args, "force_headless", False)), resolution=resolution)
    harvest_path = run_dir / "render" / "harvest.json"
    render = json.loads(harvest_path.read_text(encoding="utf-8")) if harvest_path.is_file() else {"entities": [], "error": "missing"}
    shots = sorted((run_dir / "shots").glob("*.png"))
    image_result = (
        check_image(shots[0], expect_size=tuple(int(x) for x in resolution.split("x")))
        if shots
        else {"status": "FAIL", "code": "blank_or_missing_screenshot", "reason": "no_png"}
    )
    write_json(run_dir / "shots" / "image_check.json", image_result)

    oracle = run_oracle(contract, authority=authority, render=render, image=image_result)
    overall = "PASS" if oracle["status"] == "PASS" and g["ok_marker"] else "FAIL"
    img_rel = f"shots/{shots[0].name}" if shots else ""
    rows = [
        {
            "capture_id": "SMOKE_BOOT",
            "scenario_id": contract["scenario_id"],
            "scenario_class": contract["scenario_class"],
            "checkpoint": "after",
            "seed": contract["seed"],
            "resolution": resolution,
            "action": "fixture_boot",
            "should_be_visible": (contract.get("captures") or [{}])[0].get("should_be_visible", ""),
            "assertions": ",".join((contract.get("captures") or [{}])[0].get("assertions") or []),
            "authority_summary": json.dumps(authority.get("counts")),
            "render_summary": f"entities={len(render.get('entities') or [])}",
            "image_result": image_result.get("status"),
            "overall": overall,
            "human_review": "PENDING",
            "image_rel": img_rel,
        }
    ]
    write_review_table(run_dir, rows)
    summary = {
        "mode": "headed" if args.headed else "godot",
        "run_id": run_dir.name,
        "scenario_id": contract["scenario_id"],
        "scenario_class": contract["scenario_class"],
        "status": overall,
        "layers": {
            "authority": "PASS" if not any(f.get("layer") == "authority" for f in oracle["failures"]) else "FAIL",
            "render": "PASS" if not any(f.get("layer") == "render" for f in oracle["failures"]) else "FAIL",
            "image": image_result.get("status"),
        },
        "godot": g,
        "oracle": oracle,
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "godot_bin": _godot(),
        "windows_certified": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_summary(run_dir, summary)
    print(json.dumps({"status": overall, "run": str(run_dir), "oracle": oracle}, indent=2))
    if overall != "PASS":
        print("VISUAL_SIM_GODOT_FAIL")
        return 1
    print(f"VISUAL_SIM_GODOT_OK run={run_dir}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    run_dir = Path(args.path)
    rows = []
    jsonl = run_dir / "screenshots.jsonl"
    if jsonl.is_file():
        for line in jsonl.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    write_review_table(run_dir, rows)
    print(f"VISUAL_SIM_REPORT_OK {run_dir / 'index.html'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Visual Simulation QA kernel")
    ap.add_argument("--run-id", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_sim = sub.add_parser("sim", help="Cheap authority-only smoke")
    p_sim.add_argument("--contract", default="smoke_boot.json")
    p_sim.add_argument("--run-id", default=None)
    p_sim.set_defaults(func=cmd_sim)

    p_g = sub.add_parser("godot", help="Godot harvest + capture + oracle")
    p_g.add_argument("--contract", default="smoke_boot.json")
    p_g.add_argument("--resolution", default="1280x720")
    p_g.add_argument("--headed", action="store_true")
    p_g.add_argument("--run-id", default=None)
    p_g.set_defaults(func=cmd_godot)

    p_r = sub.add_parser("report", help="Regenerate HTML/CSV from stored rows")
    p_r.add_argument("path")
    p_r.set_defaults(func=cmd_report)

    # Profile aliases matching plan CLI sketch
    p_prof = sub.add_parser("profile", help="smoke|long profiles (Stage 5)")
    p_prof.add_argument("name", choices=["smoke", "long"])
    p_prof.add_argument("--headed", action="store_true")
    p_prof.add_argument("--contract", default="smoke_boot.json")
    p_prof.add_argument("--resolution", default="1280x720")
    p_prof.add_argument("--run-id", default=None)

    def _profile(ns: argparse.Namespace) -> int:
        if ns.name == "smoke":
            ns.contract = ns.contract
            ns.run_id = ns.run_id or f"smoke_{uuid.uuid4().hex[:8]}"
            return cmd_godot(ns)
        print("LONG profile requires Stage 5 implementation; run smoke first")
        return 2

    p_prof.set_defaults(func=_profile)

    args = ap.parse_args()
    if not getattr(args, "run_id", None):
        args.run_id = None
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
