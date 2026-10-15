#!/usr/bin/env python3
"""Stage the Python sources the Android host needs into the gradle project (Chaquopy packages this directory into the APK).

    python3 scripts/android/stage_python.py [--out godot_project/android/build/python_src]

What goes in: `wizard_rts` (the simulation, the LAN host, data files) without the training packages (`learn`, `envs`: numpy),
`sim` (the embedded DuelMasterBattle state, quests, people, duels) and the authored content it reads (`godot_project/content/source`). Nothing else is read at runtime (the clean-environment
test proves no `external/` access; `docs`, `tests`, `scripts` are not imported). The staged tree is byte-identical to the
repository sources, so the phone runs the same simulation the desktop tests exercise."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

HYB = Path(__file__).resolve().parents[2]
ROOT = HYB.parent
EXCLUDE_DIRS = {"__pycache__", "learn", "envs", ".pytest_cache"}
EXCLUDE_SUFFIX = {".pyc", ".so", ".dll", ".c"}


def copy_tree(src: Path, dst: Path, manifest: dict[str, str]) -> int:
    n = 0
    for p in sorted(src.rglob("*")):
        rel = p.relative_to(src)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if p.is_dir():
            continue
        if p.suffix in EXCLUDE_SUFFIX:
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        manifest[str(Path(src.name) / rel)] = hashlib.sha1(p.read_bytes()).hexdigest()[:12]
        n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "godot_project" / "android" / "build" / "python_src"))
    args = ap.parse_args()
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    manifest: dict[str, str] = {}
    n = copy_tree(HYB / "wizard_rts", out / "wizard_rts", manifest)
    n += copy_tree(ROOT / "sim", out / "sim", manifest)
    (out / "sim" / "__init__.py").touch(exist_ok=True)
    # sim/dmb reads authored people, dialogue, buildings, units and technology JSON from godot_project/content/source,
    # located relative to its own file (parents[3] / "godot_project"), so the content sits beside it in the staged tree
    n += copy_tree(ROOT / "godot_project" / "content" / "source", out / "godot_project" / "content" / "source", manifest)
    (out / "STAGED.json").write_text(json.dumps({"files": n, "sha1": manifest}, indent=0, sort_keys=True), encoding="utf-8")
    total = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"staged {n} files, {total / 1e6:.1f} MB into {out}")
    # the staged tree must import without numpy or a compiler, exactly as it will on the phone
    import subprocess

    probe = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, %r); import wizard_rts.net.android_entry as e; print(e.self_test())" % str(out)],
                           capture_output=True, text=True, timeout=600, env={"DMB_NO_NATIVE": "1", "HYBRID_AI": "1", "PATH": "/usr/bin:/bin"})
    if probe.returncode != 0:
        print(probe.stdout[-2000:], probe.stderr[-2000:])
        sys.exit("staged sources failed the isolated self test")
    print("isolated self test:", probe.stdout.strip().splitlines()[-1])


if __name__ == "__main__":
    main()
