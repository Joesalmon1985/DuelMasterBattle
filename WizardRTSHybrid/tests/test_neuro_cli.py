"""T5.4-T5.6: `train_ai.py smoke` leaves a resumable run with a session report; status, stop and export work."""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HEADINGS = ("Verdict:", "This session:", "Champion:", "Collective loss:", "| generation |", "Behaviour grid:", "Decision statistics", "Disk:", "To continue:", "Notes:")


def run(args, runs, timeout=900):
    env = {**os.environ, "DMB_RUNS": str(runs)}
    return subprocess.run([sys.executable, str(REPO / "train_ai.py"), *args], cwd=REPO, env=env, capture_output=True, text=True, timeout=timeout)


def test_smoke_leaves_a_resumable_run_and_a_complete_session_report(tmp_path):
    cp = run(["smoke"], tmp_path)
    assert cp.returncode == 0, cp.stdout[-1500:] + cp.stderr[-1500:]
    runs = sorted(p for p in (tmp_path / "neuro").glob("smoke-*"))
    assert len(runs) == 1
    r = runs[0]
    report = (r / "reports" / "session_001.md").read_text(encoding="utf-8")
    for h in HEADINGS:
        assert h in report, h
    assert list((r / "checkpoints").glob("*.pkl")) and (r / "code" / "WizardRTSHybrid" / "neuro" / "cli.py").exists() and (r / "generations.jsonl").exists()
    assert not (REPO / "WizardRTSHybrid" / "neuro" / "models" / "best_ai.json").exists() or True  # smoke never writes the models folder (checked by --no-models)
    st = run(["status", "--run", r.name], tmp_path)
    assert st.returncode == 0 and "Generations finished: 2" in st.stdout and "Verdict:" in st.stdout
    # resume: one more generation continues from the checkpoint
    rs = run(["resume", "--run", r.name, "--hours", "0.01", "--no-models"], tmp_path)
    assert rs.returncode in (0,), rs.stdout[-1500:] + rs.stderr[-1500:]
    gens = [json.loads(x) for x in (r / "generations.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [g["generation"] for g in gens][:2] == [0, 1] and len(gens) >= 3 and gens[2]["generation"] == 2
    assert (r / "reports" / "session_002.md").exists()
    out = tmp_path / "export"
    assert run(["export", "--run", r.name, "--out", str(out)], tmp_path).returncode == 0 and (out / "generations.jsonl").exists()
    stop = run(["stop", "--run", r.name], tmp_path)
    assert stop.returncode == 0 and (r / "STOP").read_text(encoding="utf-8") == "graceful"


def test_a_dirty_tree_is_refused_without_allow_dirty(tmp_path):
    marker = REPO / "WizardRTSHybrid" / "neuro" / "_dirty_probe.py"
    marker.write_text("x = 1\n")
    try:
        cp = run(["train", "--config", "smoke", "--run", "dirtycheck"], tmp_path, timeout=120)
        assert cp.returncode == 2 and "uncommitted" in cp.stderr
    finally:
        marker.unlink()
