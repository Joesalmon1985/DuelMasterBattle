"""The unattended-run supervisor: clean finish, repeated-error stop, stall kill, stop file (plan v2 11.3)."""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

SUP = Path(__file__).resolve().parents[1] / "scripts" / "autorun" / "supervisor.py"


def run(tmp_path, name, job, *extra, timeout=60):
    env = dict(os.environ, DMB_RUNS=str(tmp_path))
    p = subprocess.run([sys.executable, str(SUP), "--name", name, "--poll-s", "0.3", *extra, "--", sys.executable, "-c", job],
                       capture_output=True, text=True, env=env, timeout=timeout)
    return p.returncode, json.loads((tmp_path / name / "STATUS.json").read_text())


def test_clean_finish(tmp_path):
    rc, st = run(tmp_path, "ok", "print('hi')")
    assert rc == 0 and st["state"] == "finished"


def test_same_error_stops(tmp_path):
    rc, st = run(tmp_path, "bad", "print('boom'); raise SystemExit(2)", "--max-same", "2")
    assert rc == 1 and "same error" in st["state"] and st["restarts"] == 2


def test_stall_is_killed(tmp_path):
    t0 = time.time()
    rc, st = run(tmp_path, "stall", "import time; time.sleep(60)", "--stall-s", "1.5", "--max-restarts", "0")
    assert rc == 1 and time.time() - t0 < 30
    assert "stalled" in (tmp_path / "stall" / "supervisor.log").read_text()


def test_stop_file(tmp_path):
    run_dir = tmp_path / "stopme"

    def later():
        time.sleep(2)
        (run_dir / "STOP").write_text("")

    threading.Thread(target=later, daemon=True).start()
    rc, st = run(tmp_path, "stopme", "import time; time.sleep(60)", "--stall-s", "100")
    assert rc == 0 and st["state"].startswith("stopped")
