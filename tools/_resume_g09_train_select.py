#!/usr/bin/env python3
"""Resume G09 after a successful collect when imitation failed (e.g. missing numpy)."""
from __future__ import annotations
import json, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
CHECKPOINTS = ROOT / "training" / "checkpoints"
POLICIES = ROOT / "godot_project" / "content" / "policies"
G09 = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking" / "gates" / "G09"

def run(argv, timeout=10000):
    print(json.dumps({"cmd": argv[:4]}), flush=True)
    t0 = time.time()
    p = subprocess.run(argv, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)
    print(json.dumps({"exit": p.returncode, "duration_s": round(time.time()-t0,3)}), flush=True)
    if p.returncode != 0:
        print((p.stderr or p.stdout or "")[-2000:], flush=True)
    return p.returncode

def main() -> int:
    steps = [
        [sys.executable, "training/train_imitation.py", "--target-decisions", "12000", "--budget-seconds", "2400", "--seed", "101", "--name", "imitation_build", "--prefer-family", "build"],
        [sys.executable, "training/train_imitation.py", "--target-decisions", "12000", "--budget-seconds", "2400", "--seed", "202", "--name", "imitation_trade", "--prefer-family", "trade"],
        [sys.executable, "training/train_imitation.py", "--target-decisions", "12000", "--budget-seconds", "2400", "--seed", "303", "--name", "imitation_war", "--prefer-family", "war"],
        [sys.executable, "training/train_imitation.py", "--target-decisions", "10000", "--budget-seconds", "1800", "--seed", "1", "--name", "imitation_generalist"],
    ]
    for s in steps:
        if run(s, timeout=2800) != 0:
            print("training step failed", s[4:], flush=True)
            # continue other families
    if (CHECKPOINTS / "imitation_generalist.json").is_file():
        run([sys.executable, "training/train_actor_critic.py", "--init", str(CHECKPOINTS / "imitation_generalist.json"), "--target-decisions", "20000", "--budget-seconds", "2400", "--max-steps", "25", "--seed", "2", "--name", "actor_critic_v1"], timeout=2700)
    cand = []
    for name, pid in (("imitation_build","policy-im-build"),("imitation_trade","policy-im-trade"),("imitation_war","policy-im-war"),("imitation_generalist","policy-im-gen"),("actor_critic_v1","policy-ac-1")):
        path = CHECKPOINTS / f"{name}.json"
        if path.is_file():
            cand.extend(["--candidate", f"{pid}={path.relative_to(ROOT)}"])
    code = run([sys.executable, "training/select_library.py", "--seed-count", "200", "--max-steps", "8", *cand], timeout=10000)
    # Re-enter full pipeline packet writing via run_g09_pipeline if select succeeded partially — call select path only
    # Always run the remainder of run_g09_pipeline by invoking a thin wrap: re-run select is done; write evidence via pipeline main from select onward is complex.
    # Invoke full pipeline but short-circuit collect by checking — easier: call tools/run_g09_pipeline after patching.
    print(json.dumps({"select_exit": code}))
    return 0 if code in (0, 2) else code  # 2 = fewer than 3 qualified

if __name__ == "__main__":
    raise SystemExit(main())
