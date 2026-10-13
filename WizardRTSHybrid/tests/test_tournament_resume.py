"""A stopped tournament resumes from the games it already finished (plan v2 11.3) and does not reuse games from other arguments."""
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_civilisation_tournament.py"


def run(tmp_path, *extra):
    p = subprocess.run([sys.executable, str(SCRIPT), "--seeds", "507", "--minutes", "1", "--jobs", "1", "--pairing", "all-plus", "--every", "30",
                        "--report-dir", str(tmp_path), *extra], capture_output=True, text=True, timeout=300)
    assert p.returncode == 0, p.stderr[-800:]
    return p.stdout


def test_second_run_loads_the_finished_game_and_changed_arguments_replay(tmp_path):
    first = run(tmp_path)
    assert "resumed" not in first and (tmp_path / "games" / "507-.json").exists()
    second = run(tmp_path)
    assert "resumed seed 507- from 507-.json" in second
    third = run(tmp_path, "--map", "small")  # a different map: the saved game must not be reused
    assert "not reusing 507-.json" in third and "resumed" not in third


def test_corrupt_checkpoint_is_replayed_and_gives_the_same_game(tmp_path):
    import json

    run(tmp_path)
    good = json.loads((tmp_path / "games" / "507-.json").read_text())["result"]["summary"]["state_hash"]
    (tmp_path / "games" / "507-.json").write_text('{"stamp": {"sha": "x"')  # a truncated file, as a crash mid-write would leave without the atomic rename
    again = run(tmp_path)
    assert "unreadable 507-.json" in again
    assert json.loads((tmp_path / "games" / "507-.json").read_text())["result"]["summary"]["state_hash"] == good  # deterministic replay
