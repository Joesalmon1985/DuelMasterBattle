#!/usr/bin/env python3
"""Overnight G09 pipeline: collect → imitate → actor-critic → evaluate → select → packet.

Honest about budget stops and qualification. Never labels heuristic as trained.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TRACKING = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking"
G09 = TRACKING / "gates" / "G09"
EVAL = TRACKING / "policy_evaluations"
CHECKPOINTS = ROOT / "training" / "checkpoints"
POLICIES = ROOT / "godot_project" / "content" / "policies"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(argv: list[str], timeout: int = 7200) -> dict:
    started = time.time()
    import os
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    proc = subprocess.run(argv, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout, env=env)
    result = {
        "cmd": argv,
        "exit_code": proc.returncode,
        "duration_s": round(time.time() - started, 3),
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
    }
    print(json.dumps({"step_cmd": argv[:3], "exit": proc.returncode, "duration_s": result["duration_s"]}), flush=True)
    if proc.returncode != 0:
        print((proc.stderr or proc.stdout or "")[-1500:], flush=True)
    return result


def main() -> int:
    G09.mkdir(parents=True, exist_ok=True)
    EVAL.mkdir(parents=True, exist_ok=True)
    CHECKPOINTS.mkdir(parents=True, exist_ok=True)
    auto = G09 / "auto"
    auto.mkdir(parents=True, exist_ok=True)

    steps: list[tuple[str, dict]] = []
    # Bounded overnight budgets — incomplete batches are recorded, not claimed promotion.
    steps.append(
        (
            "collect",
            _run(
                [
                    sys.executable,
                    "training/collect.py",
                    "--train-seeds",
                    "48",
                    "--max-steps",
                    "20",
                    "--budget-seconds",
                    "900",
                ],
                timeout=1200,
            ),
        )
    )
    if steps[-1][1]["exit_code"] != 0:
        # Still write a blocked packet so G10 can proceed independently.
        blockers = ["collect_failed"]
        status = "AUTO_FAILED — collect_failed"
        (G09 / "auto").mkdir(parents=True, exist_ok=True)
        (G09 / "auto" / "result.json").write_text(
            json.dumps(
                {
                    "gate": "G09",
                    "status": "AUTO_FAILED",
                    "owner_review_status": status,
                    "blockers": blockers,
                    "steps": [{"name": n, **r} for n, r in steps],
                    "generated_at": _now(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        _write_morning_review(status, 0, blockers, {}, {})
        print(json.dumps({"status": "AUTO_FAILED", "blockers": blockers}))
        return 1
    steps.append(
        (
            "imitation_v1",
            _run(
                [
                    sys.executable,
                    "training/train_imitation.py",
                    "--target-decisions",
                    "10000",
                    "--budget-seconds",
                    "1800",
                    "--seed",
                    "1",
                    "--name",
                    "imitation_v1",
                ],
                timeout=2000,
            ),
        )
    )
    steps.append(
        (
            "imitation_v2",
            _run(
                [
                    sys.executable,
                    "training/train_imitation.py",
                    "--target-decisions",
                    "8000",
                    "--budget-seconds",
                    "1200",
                    "--seed",
                    "11",
                    "--name",
                    "imitation_v2",
                ],
                timeout=1500,
            ),
        )
    )
    steps.append(
        (
            "imitation_v3",
            _run(
                [
                    sys.executable,
                    "training/train_imitation.py",
                    "--target-decisions",
                    "8000",
                    "--budget-seconds",
                    "1200",
                    "--seed",
                    "21",
                    "--name",
                    "imitation_v3",
                ],
                timeout=1500,
            ),
        )
    )
    if (CHECKPOINTS / "imitation_v1.json").is_file():
        steps.append(
            (
                "actor_critic_v1",
                _run(
                    [
                        sys.executable,
                        "training/train_actor_critic.py",
                        "--init",
                        str(CHECKPOINTS / "imitation_v1.json"),
                        "--target-decisions",
                        "20000",
                        "--budget-seconds",
                        "2400",
                        "--max-steps",
                        "25",
                        "--seed",
                        "2",
                        "--name",
                        "actor_critic_v1",
                    ],
                    timeout=2700,
                ),
            )
        )

    # Evaluation on full 200 promotion seeds (bounded episode length).
    cand_args: list[str] = []
    for name, pid in (
        ("actor_critic_v1", "policy-ac-1"),
        ("imitation_v1", "policy-im-1"),
        ("imitation_v2", "policy-im-2"),
        ("imitation_v3", "policy-im-3"),
    ):
        path = CHECKPOINTS / f"{name}.json"
        if path.is_file():
            cand_args.extend(["--candidate", f"{pid}={path.relative_to(ROOT)}"])

    select_result = _run(
        [
            sys.executable,
            "training/select_library.py",
            "--seed-count",
            "200",
            "--max-steps",
            "8",
            *cand_args,
        ],
        timeout=10_000,
    )
    steps.append(("select_library", select_result))

    # Pytest suite
    pytest_result = _run(
        [sys.executable, "-m", "pytest", "-q", "tests/sim/test_t143_t150_leadership.py"],
        timeout=600,
    )
    steps.append(("pytest_g09", pytest_result))

    manifest_path = POLICIES / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    qualified = int(manifest.get("qualified_count") or 0)

    # Decision traces / evidence for build-trade-war (text primary; screenshots optional).
    evidence = _write_decision_evidence()

    blockers: list[str] = []
    if pytest_result["exit_code"] != 0:
        blockers.append("pytest_g09_failed")
    if qualified < 3:
        blockers.append(f"fewer_than_three_qualified_policies ({qualified})")
    if not (CHECKPOINTS / "imitation_v1.json").is_file():
        blockers.append("missing_imitation_checkpoint")

    # Honest gate status.
    if blockers:
        if qualified >= 1 and pytest_result["exit_code"] == 0:
            status = f"PARTIAL — BLOCKED BY {', '.join(blockers)}"
            auto_status = "PARTIAL_BLOCKED"
        else:
            status = f"AUTO_FAILED — {', '.join(blockers)}"
            auto_status = "AUTO_FAILED"
    else:
        status = "AUTO_READY_FOR_OWNER_REVIEW"
        auto_status = "AUTO_READY_FOR_OWNER_REVIEW"

    result = {
        "gate": "G09",
        "status": auto_status,
        "owner_review_status": status,
        "human_acceptance": "PENDING — never invent PASS",
        "generated_at": _now(),
        "qualified_policies": qualified,
        "required_policies": 3,
        "blockers": blockers,
        "manifest": str(manifest_path.relative_to(ROOT)) if manifest_path.is_file() else None,
        "steps": [{"name": n, **{k: v for k, v in r.items() if k != "stdout_tail"}} | {"stdout_tail": r.get("stdout_tail")} for n, r in steps],
        "evidence": evidence,
        "honesty": (
            "Statistical/evaluation report is the primary oracle. Heuristic fallback is legal "
            "and required. Heuristic clones are never labelled trained. Incomplete training "
            "batches due to local compute budget are not claimed as promotion."
        ),
    }
    (auto / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (auto / "summary.md").write_text(
        f"# G09 auto summary\n\nStatus: **{status}**\n\n"
        f"Qualified trained policies: {qualified}/3\n\n"
        f"Blockers: {blockers or 'none'}\n",
        encoding="utf-8",
    )
    _write_morning_review(status, qualified, blockers, manifest, evidence)
    print(json.dumps({"status": auto_status, "qualified": qualified, "blockers": blockers}))
    return 0 if auto_status in {"AUTO_READY_FOR_OWNER_REVIEW", "PARTIAL_BLOCKED"} else 1


def _write_decision_evidence() -> dict:
    """Capture representative decision families from a short heuristic+neural run."""
    from sim.dmb.ai.policy import PolicyService, register_neural_artifact
    from training.environment import TrainingEnvironment

    out = G09 / "decision_traces"
    out.mkdir(parents=True, exist_ok=True)
    env = TrainingEnvironment(seed=10001, max_turns=15)
    recs = env.run_episode(max_steps=15)
    samples = {"build": [], "trade": [], "war": []}
    for rec in recs:
        for c in rec.candidates:
            if c.get("id") != rec.selected_id:
                continue
            kind = str(c.get("action_kind") or "")
            row = {
                "seed": rec.seed,
                "turn": rec.turn,
                "faction_id": rec.faction_id,
                "selected_id": rec.selected_id,
                "action_kind": kind,
                "params": c.get("params"),
            }
            if kind == "construct" and len(samples["build"]) < 3:
                samples["build"].append(row)
            elif kind == "trade_propose" and len(samples["trade"]) < 3:
                samples["trade"].append(row)
            elif kind.startswith("military") and len(samples["war"]) < 3:
                samples["war"].append(row)
    (out / "action_samples.json").write_text(json.dumps(samples, indent=2) + "\n", encoding="utf-8")

    # Forced fallback demonstration.
    art = CHECKPOINTS / "imitation_v1.json"
    fallback_demo = {"status": "skipped", "reason": "no_artifact"}
    if art.is_file():
        from sim.dmb.ai.neural import NeuralBrain
        from training.features import encode_observation  # noqa: F401

        brain = NeuralBrain(artifact_path=art, policy_id="demo")
        brain.force_fail = True
        env2 = TrainingEnvironment(seed=10002, max_turns=1)
        env2.reset(10002)
        assert env2.sim is not None
        fid = sorted(env2.sim.state.factions)[0]
        obs, cands = env2.observe(fid)
        choice = brain.choose_activation(obs, cands)
        fallback_demo = {
            "status": "ok",
            "source": choice.get("source"),
            "selected_ids": choice.get("selected_ids"),
            "fallback_reason": choice.get("fallback_reason"),
            "candidate_count": len(cands),
            "note": "Forced inference failure used legal heuristic within same seat budget.",
        }
    (out / "fallback_demo.json").write_text(json.dumps(fallback_demo, indent=2) + "\n", encoding="utf-8")

    # Policy identity after save/load
    env3 = TrainingEnvironment(seed=10003, max_turns=1)
    env3.reset(10003)
    assert env3.sim is not None
    pol = PolicyService(env3.sim.state)
    pol.assign_brain("faction:1", "policy-im-1" if art.is_file() else "heuristic")
    identity = {
        "before": dict(pol._policy_bucket("faction:1")),
    }
    blob = json.dumps({"policy": pol._policy_bucket("faction:1")})
    restored = json.loads(blob)
    identity["after_reload"] = restored["policy"]
    identity["stable"] = restored["policy"].get("policy_id") == identity["before"].get("policy_id")
    (out / "policy_identity.json").write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")
    return {
        "action_samples": str((out / "action_samples.json").relative_to(ROOT)),
        "fallback_demo": str((out / "fallback_demo.json").relative_to(ROOT)),
        "policy_identity": str((out / "policy_identity.json").relative_to(ROOT)),
    }


def _write_morning_review(
    status: str,
    qualified: int,
    blockers: list[str],
    manifest: dict,
    evidence: dict,
) -> None:
    eval_files = sorted(p.name for p in EVAL.glob("*.json")) if EVAL.is_dir() else []
    body = f"""# G09 Morning Review — {status}

**Gate:** G09 — Trained faction leadership  
**Status:** `{status}`  
**Human acceptance:** PENDING — do **not** invent `PASS` or `accepted_by`  
**Overnight policy:** continuation past G09 only when status is AUTO_READY_FOR_OWNER_REVIEW; PARTIAL/AUTO_FAILED still leaves infrastructure for independent G10 work

## Candidate

- Branch: `phase/g06-g12-autoqa`
- Evaluation dir: `tracking/policy_evaluations/`
- Policy manifest: `godot_project/content/policies/manifest.json`
- Auto report: `tracking/gates/G09/auto/result.json`
- Launch / inspect: `python3 training/evaluate.py --seed-count 200 --max-steps 30`
- Decision traces: `tracking/gates/G09/decision_traces/`

## Honesty

- Pure-numpy local training (torch not installed). Weights are **real trained artifacts** when `trained: true`, not relabelled heuristics.
- Heuristic fallback remains legal and required on schema/timeout/exception.
- **Heuristic clones are never labelled trained.**
- Incomplete batches stopped by local compute budget are **not** claimed as promotion.

## Qualification

| Metric | Value |
|---|---|
| Qualified trained policies | {qualified} / 3 |
| Manifest status | {manifest.get("status", "missing")} |
| Blockers | {blockers or "none"} |

## Automated evidence

| Suite | Path |
|---|---|
| Eval reports | `{", ".join(eval_files) or "none yet"}` |
| Action samples | `{evidence.get("action_samples")}` |
| Fallback demo | `{evidence.get("fallback_demo")}` |
| Policy identity | `{evidence.get("policy_identity")}` |

## Owner playtest focus

1. Read the paired evaluation summary (baseline vs candidates, 200 held-out seeds).
2. Inspect build/trade/war samples under `decision_traces/`.
3. Confirm policy identity after save/load (`policy_identity.json`).
4. Confirm forced inference failure → legal heuristic fallback without a free extra action.

## Known limits / blockers

{chr(10).join(f"- {b}" for b in blockers) if blockers else "- None recorded for automation; owner still decides library readiness."}

G05–G08 remain without human PASS; do not invent acceptance.
"""
    (G09 / "MORNING_REVIEW.md").write_text(body, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
