#!/usr/bin/env python3
"""Windows playtest helper for G01/G02/G03 launch and gate checks.

Used by Playtest.bat. Resolves native Godot/Python, launches the same scenes
and fixtures as tools/play_g01.sh / tools/play_g02.sh, and invokes
tools/check.py for gates without duplicating gate logic.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL_CONFIG = ROOT / ".dmb_windows_local.json"
LOG_DIR = ROOT / "logs" / "playtest"
CHECK_PY = ROOT / "tools" / "check.py"

G01_FIXTURE = "FX-CLOCK"
G01_SEED = "7"
G02_FIXTURE = "FX-CARGO"
G02_SEED = "202"
G03_FIXTURE = "FX-INDUSTRY"
G03_SEED = "303"
G04_BATTLE_FIXTURE = "FX-BATTLE"
G04_BATTLE_SEED = "404"
G04_HAZARD_FIXTURE = "FX-HAZARD"
G04_HAZARD_SEED = "408"
DEFAULT_RESOLUTION = "450x800"


def _load_local() -> dict:
    if not LOCAL_CONFIG.is_file():
        return {}
    try:
        data = json.loads(LOCAL_CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_local(data: dict) -> None:
    LOCAL_CONFIG.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _is_exe(path: Path | None) -> bool:
    return path is not None and path.is_file()


def _candidate_godot_paths() -> list[Path]:
    home = Path.home()
    downloads = home / "Downloads"
    docs = home / "Documents"
    names = [
        "Godot_v4.4.1-stable_win64.exe",
        "Godot_v4.4.1-stable_win64_console.exe",
        "Godot_v4.5.1-stable_win64.exe",
        "Godot_v4.5.1-stable_win64_console.exe",
        "Godot_v4.4.1-stable_win64.exe.exe",  # nested extract folder quirks
        "godot.exe",
        "godot.exe.exe",
    ]
    roots = [
        downloads,
        docs / "Godot",
        Path(r"C:\Tools\Godot"),
        Path(r"C:\Godot"),
        home / "Godot",
    ]
    out: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for name in names:
            out.append(root / name)
            # Common nested extract: Downloads/Godot_vX_win64.exe/Godot_vX_win64.exe
            stem = name.replace(".exe", "")
            out.append(root / f"{stem}.exe" / name)
            out.append(root / name / name)
        # Shallow scan one level for Godot*.exe
        try:
            for child in root.iterdir():
                if child.is_file() and child.suffix.lower() == ".exe" and "godot" in child.name.lower():
                    out.append(child)
                if child.is_dir() and "godot" in child.name.lower():
                    for nested in child.glob("Godot*.exe"):
                        out.append(nested)
        except OSError:
            pass
    return out


def _godot_version(exe: Path) -> str:
    try:
        proc = subprocess.run(
            [str(exe), "--version"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        text = (proc.stdout or proc.stderr or "").strip()
        return text.splitlines()[0] if text else "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def resolve_godot(*, prompt: bool = True) -> Path:
    env = os.environ.get("GODOT", "").strip().strip('"')
    if env and _is_exe(Path(env)):
        return Path(env)

    local = _load_local()
    saved = str(local.get("godot", "")).strip().strip('"')
    if saved and _is_exe(Path(saved)):
        return Path(saved)

    toolchain = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking" / "toolchain.json"
    if toolchain.is_file():
        try:
            data = json.loads(toolchain.read_text(encoding="utf-8"))
            exe = ((data.get("godot") or {}) if isinstance(data.get("godot"), dict) else {}).get(
                "executable"
            )
            if isinstance(exe, str) and _is_exe(Path(exe)):
                return Path(exe)
        except (OSError, json.JSONDecodeError):
            pass

    for candidate in _candidate_godot_paths():
        if _is_exe(candidate):
            return candidate

    which = shutil.which("godot") or shutil.which("godot4")
    if which and _is_exe(Path(which)):
        return Path(which)

    if not prompt:
        raise FileNotFoundError("Godot executable not found")

    print("Godot executable not found automatically.")
    print("Enter the full path to Godot (e.g. ...\\Godot_v4.4.1-stable_win64.exe):")
    while True:
        raw = input("> ").strip().strip('"')
        if not raw:
            print("Path required.")
            continue
        path = Path(raw)
        if not _is_exe(path):
            print(f"Not a file: {path}")
            continue
        version = _godot_version(path)
        print(f"Validated Godot: {path}")
        print(f"Version: {version}")
        local = _load_local()
        local["godot"] = str(path)
        local["godot_version"] = version
        _save_local(local)
        print(f"Saved to {LOCAL_CONFIG.name} (gitignored).")
        return path


def resolve_python() -> Path:
    local = _load_local()
    saved = str(local.get("python", "")).strip().strip('"')
    if saved and _is_exe(Path(saved)):
        return Path(saved)

    for rel in (
        Path(".venv") / "Scripts" / "python.exe",
        Path("venv") / "Scripts" / "python.exe",
        Path(".venv") / "bin" / "python",
        Path("venv") / "bin" / "python",
    ):
        candidate = ROOT / rel
        if _is_exe(candidate):
            return candidate

    # Prefer the interpreter running this helper when it can import pytest.
    current = Path(sys.executable)
    if _is_exe(current):
        return current

    for name in ("python", "python3", "py"):
        which = shutil.which(name)
        if which and _is_exe(Path(which)):
            return Path(which)

    raise FileNotFoundError(
        "Python interpreter not found. Install Python 3.11+ or create .venv in the repo root."
    )


def _python_version(exe: Path) -> str:
    try:
        proc = subprocess.run(
            [str(exe), "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return (proc.stdout or proc.stderr or "").strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def prepare_env(python: Path, godot: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["DMB_PYTHON"] = str(python)
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    if godot is not None:
        env["GODOT"] = str(godot)
    return env


def cmd_resolve(_: argparse.Namespace) -> int:
    try:
        python = resolve_python()
        godot = resolve_godot(prompt=True)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(f"Python: {python}")
    print(f"Python version: {_python_version(python)}")
    print(f"Godot: {godot}")
    print(f"Godot version: {_godot_version(godot)}")
    local = _load_local()
    local["python"] = str(python)
    local["godot"] = str(godot)
    local["godot_version"] = _godot_version(godot)
    local["python_version"] = _python_version(python)
    _save_local(local)
    return 0


def launch_godot(
    *,
    scene: str,
    fixture: str | None,
    seed: str | None,
    resolution: str = DEFAULT_RESOLUTION,
) -> int:
    try:
        python = resolve_python()
        godot = resolve_godot(prompt=True)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 1

    version = _godot_version(godot)
    print(f"Using Godot: {godot}")
    print(f"Godot version: {version}")
    print(f"Using Python (sidecar DMB_PYTHON): {python} ({_python_version(python)})")
    if fixture:
        print(f"Fixture: {fixture} seed={seed}")
    print(f"Scene: {scene}")
    print(f"Resolution: {resolution}")

    env = prepare_env(python, godot)
    if fixture:
        env["DMB_FIXTURE"] = fixture
    if seed:
        env["DMB_SEED"] = seed

    argv = [
        str(godot),
        "--path",
        str(ROOT / "godot_project"),
        "--resolution",
        resolution,
        scene,
    ]
    try:
        proc = subprocess.run(argv, cwd=str(ROOT), env=env, check=False)
    except OSError as exc:
        print(f"ERROR: failed to launch Godot: {exc}")
        return 1
    return int(proc.returncode)


def cmd_play_g02(_: argparse.Namespace) -> int:
    # Match tools/play_g02.sh --direct defaults.
    return launch_godot(
        scene="res://client/scenes/g02_shell.tscn",
        fixture=G02_FIXTURE,
        seed=G02_SEED,
        resolution=DEFAULT_RESOLUTION,
    )


def cmd_play_g03(_: argparse.Namespace) -> int:
    return launch_godot(
        scene="res://client/scenes/g03_shell.tscn",
        fixture=G03_FIXTURE,
        seed=G03_SEED,
        resolution=DEFAULT_RESOLUTION,
    )


def cmd_play_g04_battle(_: argparse.Namespace) -> int:
    return launch_godot(
        scene="res://client/scenes/g04_battle_shell.tscn",
        fixture=G04_BATTLE_FIXTURE,
        seed=G04_BATTLE_SEED,
        resolution=DEFAULT_RESOLUTION,
    )


def cmd_play_g04_hazard(_: argparse.Namespace) -> int:
    return launch_godot(
        scene="res://client/scenes/g04_hazard_shell.tscn",
        fixture=G04_HAZARD_FIXTURE,
        seed=G04_HAZARD_SEED,
        resolution=DEFAULT_RESOLUTION,
    )


def cmd_play_g01(_: argparse.Namespace) -> int:
    # Match documented G01 gate launch (FX-CLOCK / seed 7) with --direct scene.
    return launch_godot(
        scene="res://client/scenes/g01_shell.tscn",
        fixture=G01_FIXTURE,
        seed=G01_SEED,
        resolution=DEFAULT_RESOLUTION,
    )


def cmd_play_menu(_: argparse.Namespace) -> int:
    return launch_godot(
        scene="res://client/scenes/main_menu.tscn",
        fixture=None,
        seed=None,
        resolution=DEFAULT_RESOLUTION,
    )


def _summarize_check_payload(payload: dict) -> str:
    status = str(payload.get("status", "FAIL")).upper()
    results = payload.get("results") or []
    if any(str(item.get("status", "")).upper() == "BLOCKED" for item in results if isinstance(item, dict)):
        return "BLOCKED"
    if status == "PASS":
        # Never promote empty / skipped suites to PASS.
        if not results:
            return "FAIL"
        if not all(str(item.get("status", "")).upper() == "PASS" for item in results if isinstance(item, dict)):
            return "FAIL"
        return "PASS"
    return "FAIL" if status != "BLOCKED" else "BLOCKED"


def run_gate(gate: str) -> int:
    try:
        python = resolve_python()
        godot = resolve_godot(prompt=True)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 1

    if not CHECK_PY.is_file():
        print(f"ERROR: missing {CHECK_PY}")
        return 1

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"{gate}_{stamp}.log"
    json_path = LOG_DIR / f"{gate}_{stamp}.json"

    env = prepare_env(python, godot)
    argv = [str(python), str(CHECK_PY), "--gate", gate, "--json-report", str(json_path)]
    print(f"Running: {' '.join(argv)}")
    print(f"Log: {log_path}")
    started = time.monotonic()
    try:
        proc = subprocess.run(
            argv,
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        print(f"ERROR: failed to run check.py: {exc}")
        return 1
    duration = time.monotonic() - started
    output = (proc.stdout or "") + (proc.stderr or "")
    log_path.write_text(output, encoding="utf-8")

    summary = "FAIL"
    payload: dict = {}
    if json_path.is_file():
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            summary = _summarize_check_payload(payload)
        except (OSError, json.JSONDecodeError):
            summary = "FAIL"
    elif proc.returncode == 0:
        # Missing report must never be treated as PASS.
        summary = "FAIL"

    # Preserve nonzero process exit; also force nonzero when summary is not PASS.
    exit_code = int(proc.returncode)
    if summary != "PASS":
        exit_code = exit_code or 1

    print()
    print("=" * 60)
    print(f"Gate {gate}: {summary}")
    print(f"Exit code: {exit_code}  ({duration:.1f}s)")
    print(f"Log: {log_path}")
    print(f"JSON: {json_path}")
    if isinstance(payload.get("results"), list):
        for item in payload["results"]:
            if not isinstance(item, dict):
                continue
            print(
                f"  - {item.get('name')}: {item.get('status')} "
                f"(exit={item.get('exit_code')}) {item.get('detail', '')}"
            )
    print("=" * 60)
    # Echo tail of output for convenience.
    lines = output.strip().splitlines()
    if lines:
        print("Output tail:")
        for line in lines[-20:]:
            print(line)
    return exit_code


def cmd_check_g01(_: argparse.Namespace) -> int:
    return run_gate("G01")


def cmd_check_g02(_: argparse.Namespace) -> int:
    return run_gate("G02")


def cmd_check_g03(_: argparse.Namespace) -> int:
    return run_gate("G03")


def cmd_check_g04(_: argparse.Namespace) -> int:
    return run_gate("G04")


def cmd_check_all(_: argparse.Namespace) -> int:
    codes = [run_gate("G01"), run_gate("G02"), run_gate("G03"), run_gate("G04")]
    # Any nonzero / non-PASS must surface.
    return 0 if all(code == 0 for code in codes) else 1


def cmd_check_both(_: argparse.Namespace) -> int:
    codes = [run_gate("G01"), run_gate("G02")]
    return 0 if all(code == 0 for code in codes) else 1


def interactive_menu() -> int:
    while True:
        print()
        print("DuelMasterBattle Windows playtest")
        print(f"Repo: {ROOT}")
        print("1. Play G04 battle — default portrait 450x800")
        print("2. Play G04 hazard — default portrait 450x800")
        print("3. Play G03 directly")
        print("4. Play G02 directly")
        print("5. Play G01 directly")
        print("6. Open the main menu")
        print("7. Run automated G04 checks")
        print("8. Run all implemented gates G01-G04")
        print("0. Exit")
        choice = input("Select: ").strip()
        if choice == "1":
            code = cmd_play_g04_battle(argparse.Namespace())
            if code:
                input("Press Enter to continue...")
        elif choice == "2":
            code = cmd_play_g04_hazard(argparse.Namespace())
            if code:
                input("Press Enter to continue...")
        elif choice == "3":
            code = cmd_play_g03(argparse.Namespace())
            if code:
                input("Press Enter to continue...")
        elif choice == "4":
            code = cmd_play_g02(argparse.Namespace())
            if code:
                input("Press Enter to continue...")
        elif choice == "5":
            code = cmd_play_g01(argparse.Namespace())
            if code:
                input("Press Enter to continue...")
        elif choice == "6":
            code = cmd_play_menu(argparse.Namespace())
            if code:
                input("Press Enter to continue...")
        elif choice == "7":
            code = cmd_check_g04(argparse.Namespace())
            input("Press Enter to continue...")
        elif choice == "8":
            code = cmd_check_all(argparse.Namespace())
            input("Press Enter to continue...")
        elif choice == "0":
            return 0
        else:
            print("Invalid choice.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("resolve", help="Resolve and remember Godot/Python")
    sub.add_parser("play-g02", help="Launch G02 shell directly")
    sub.add_parser("play-g03", help="Launch G03 shell directly")
    sub.add_parser("play-g04-battle", help="Launch G04 battle shell")
    sub.add_parser("play-g04-hazard", help="Launch G04 hazard shell")
    sub.add_parser("play-g01", help="Launch G01 shell directly")
    sub.add_parser("play-menu", help="Launch main menu")
    sub.add_parser("check-g01", help="Run tools/check.py --gate G01")
    sub.add_parser("check-g02", help="Run tools/check.py --gate G02")
    sub.add_parser("check-g03", help="Run tools/check.py --gate G03")
    sub.add_parser("check-g04", help="Run tools/check.py --gate G04")
    sub.add_parser("check-all", help="Run G01 through G04 gates")
    sub.add_parser("check-both", help="Run G01 and G02 gates")
    sub.add_parser("menu", help="Interactive menu (default)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "menu"
    handlers = {
        "resolve": cmd_resolve,
        "play-g02": cmd_play_g02,
        "play-g03": cmd_play_g03,
        "play-g04-battle": cmd_play_g04_battle,
        "play-g04-hazard": cmd_play_g04_hazard,
        "play-g01": cmd_play_g01,
        "play-menu": cmd_play_menu,
        "check-g01": cmd_check_g01,
        "check-g02": cmd_check_g02,
        "check-g03": cmd_check_g03,
        "check-g04": cmd_check_g04,
        "check-all": cmd_check_all,
        "check-both": cmd_check_both,
        "menu": lambda _a: interactive_menu(),
    }
    os.chdir(ROOT)
    return handlers[command](args)


if __name__ == "__main__":
    raise SystemExit(main())
