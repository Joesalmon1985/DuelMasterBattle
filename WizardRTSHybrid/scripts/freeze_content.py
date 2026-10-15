"""Write, check or bump the frozen content roster (decision D33).

    py -3 scripts/freeze_content.py --write                          # first time only: writes data/content_freeze.json
    py -3 scripts/freeze_content.py --check                          # prints the differences, exit 1 if there are any
    py -3 scripts/freeze_content.py --bump minor --reason "..."      # regenerate the manifest, bump ROSTER_VERSION, log it in docs/CONTENT_FREEZE.md

A bump changes what the game contains. It needs a reason and the owner's approval (docs/CONTENT_FREEZE.md).
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB))
sys.path.insert(0, str(HYB.parent))

from wizard_rts import freeze  # noqa: E402

CHANGELOG = HYB.parent / "docs" / "CONTENT_FREEZE.md"


def _head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=HYB, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _write(manifest: dict) -> None:
    freeze.MANIFEST.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8", newline="\n")


def _bumped(version: str, part: str) -> str:
    major, minor, patch = (int(x) for x in version.removeprefix("roster-").split("."))
    major, minor, patch = {"major": (major + 1, 0, 0), "minor": (major, minor + 1, 0), "patch": (major, minor, patch + 1)}[part]
    return f"roster-{major}.{minor}.{patch}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="first-time write of the manifest (refuses if it exists)")
    mode.add_argument("--check", action="store_true", help="compare the live registries with the manifest")
    mode.add_argument("--bump", choices=("major", "minor", "patch"), help="regenerate the manifest under a new roster version")
    ap.add_argument("--reason", help="required with --bump: why the roster changes")
    args = ap.parse_args()
    today = datetime.date.today().isoformat()

    if args.write:
        if freeze.MANIFEST.exists():
            print(f"{freeze.MANIFEST} exists; use --bump with a reason to change the roster.", file=sys.stderr)
            return 2
        manifest = freeze.build_manifest(_head(), today)
        _write(manifest)
        print(f"wrote {freeze.MANIFEST}: {manifest['roster_version']}, counts {manifest['counts']}, roster_sha256 {manifest['roster_sha256']}")
        return 0

    if args.check:
        problems = freeze.check()
        for line in problems:
            print(line)
        print("roster matches the manifest" if not problems else f"{len(problems)} difference(s) from the frozen roster")
        return 1 if problems else 0

    if not args.reason or not args.reason.strip():
        print("--bump needs --reason \"...\"", file=sys.stderr)
        return 2
    old = freeze.manifest()
    new_version = _bumped(old["roster_version"], args.bump)
    src = Path(freeze.__file__)
    text = src.read_text(encoding="utf-8")
    text, n = re.subn(r'^ROSTER_VERSION = "[^"]*"', f'ROSTER_VERSION = "{new_version}"', text, count=1, flags=re.M)
    assert n == 1, "ROSTER_VERSION line not found in freeze.py"
    src.write_text(text, encoding="utf-8", newline="\n")
    freeze.ROSTER_VERSION = new_version
    manifest = freeze.build_manifest(_head(), today)
    _write(manifest)
    delta = ", ".join(f"{k} {manifest['counts'][k] - old['counts'].get(k, 0):+d}" for k in manifest["counts"] if manifest["counts"][k] != old["counts"].get(k, 0)) or "no count change"
    with CHANGELOG.open("a", encoding="utf-8", newline="\n") as f:
        f.write(f"| {today} | {new_version} | {args.reason.strip()} | {delta} |\n")
    print(f"bumped {old['roster_version']} -> {new_version} ({delta}); logged in {CHANGELOG.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
