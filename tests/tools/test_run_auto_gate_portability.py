"""Unit tests for tools/run_auto_gate.py shell portability."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from run_auto_gate import rewrite_shell_cmd  # noqa: E402


def test_rewrite_python3_to_sys_executable() -> None:
    out = rewrite_shell_cmd(["python3", "tools/evaluate_mvp.py"])
    assert out[0] == sys.executable
    assert out[1:] == ["tools/evaluate_mvp.py"]


def test_rewrite_python_and_py_launchers() -> None:
    assert rewrite_shell_cmd(["python", "-c", "print(1)"])[0] == sys.executable
    assert rewrite_shell_cmd(["py", "-3", "tools/x.py"])[0] == sys.executable


def test_rewrite_python3_exe_windows_style() -> None:
    out = rewrite_shell_cmd(["python3.exe", "tools/evaluate_mvp.py"])
    assert out[0] == sys.executable


def test_rewrite_leaves_godot_and_other_tools() -> None:
    godot = ["/opt/Godot", "--path", "godot_project"]
    assert rewrite_shell_cmd(godot) == godot
    bash = ["bash", "tools/play_g05.sh"]
    assert rewrite_shell_cmd(bash) == bash


def test_rewrite_empty_and_custom_executable() -> None:
    assert rewrite_shell_cmd([]) == []
    custom = rewrite_shell_cmd(
        ["python3", "tools/x.py"],
        python_executable=r"C:\proj\.venv\Scripts\python.exe",
    )
    assert custom[0] == r"C:\proj\.venv\Scripts\python.exe"


def test_g06_through_g12_shell_steps_are_rewritable() -> None:
    """Every gate JSON shell step that starts with python3 must rewrite cleanly."""
    import json

    qa = ROOT / "qa" / "auto_gates"
    for gate in ("G06", "G07", "G08", "G09", "G10", "G11", "G12"):
        spec = json.loads((qa / f"{gate}.json").read_text(encoding="utf-8"))
        for step in spec.get("steps") or []:
            if str(step.get("kind") or "shell") != "shell":
                continue
            cmd = list(step.get("cmd") or [])
            if not cmd:
                continue
            head = Path(str(cmd[0])).name.lower().removesuffix(".exe")
            if head in {"python", "python3", "py"}:
                rewritten = rewrite_shell_cmd(cmd)
                assert rewritten[0] == sys.executable, f"{gate} step {step.get('name')}"
                assert rewritten[1:] == [str(x) for x in cmd[1:]]
