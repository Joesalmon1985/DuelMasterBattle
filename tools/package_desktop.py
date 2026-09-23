#!/usr/bin/env python3
"""T155 — package desktop release (Linux local + Windows scaffold).

Honest about platforms: Linux packaging can run here; Windows executable requires
a Windows runner. Never sets windows_certified=true without Windows evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACK = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking"
RELEASE_MANIFEST = ROOT / "godot_project" / "content" / "manifests" / "release.json"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_release_manifest(meta: dict) -> None:
    RELEASE_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "generated_at": meta["generated_at"],
        "bundle": meta,
        "offline": True,
        "network_required": False,
        "api_keys_required": False,
        "placeholder_art": "semantic_permitted",
        "windows_release": "SCAFFOLDED_PENDING_WINDOWS_RUNNER"
        if not meta.get("windows_certified")
        else "PRODUCED",
    }
    RELEASE_MANIFEST.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def package_linux() -> dict:
    out = ROOT / "build" / "desktop" / "mvp_linux"
    out.mkdir(parents=True, exist_ok=True)
    for name in ("play_mvp.sh", "play_fx_era.sh", "play_g05.sh", "find_godot.sh", "play_g10_release.sh"):
        src = ROOT / "tools" / name
        if src.is_file():
            dst = out / name
            shutil.copy2(src, dst)
            dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    readme = out / "README.md"
    readme.write_text(
        "# DMB release launch bundle (Linux)\n\n"
        "Requires Godot 4.4.1 on PATH or via `find_godot.sh`.\n\n"
        "```bash\n./play_mvp.sh\n./play_g10_release.sh\n```\n\n"
        "Sidecar starts from the Godot client. Offline; no API keys.\n\n"
        "**Windows:** not certified by this Linux packaging step.\n",
        encoding="utf-8",
    )
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.system(),
        "machine": platform.machine(),
        "target": "linux",
        "windows_certified": False,
        "bundle": str(out.relative_to(ROOT)),
        "launchers": [p.name for p in out.glob("*.sh")],
        "hashes": {p.name: _sha256(p) for p in out.iterdir() if p.is_file()},
    }
    (TRACK / "mvp_build").mkdir(parents=True, exist_ok=True)
    (TRACK / "mvp_build" / "desktop_bundle.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (out / "bundle.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    _write_release_manifest(meta)
    return meta


def package_windows_scaffold() -> dict:
    """Write Windows bundle layout + instructions without fabricating an .exe."""
    out = ROOT / "build" / "windows" / "release_scaffold"
    out.mkdir(parents=True, exist_ok=True)
    (out / "README_WINDOWS.md").write_text(
        "# Windows release scaffold (T155)\n\n"
        "This folder is prepared on Linux for a Windows CI/export runner.\n\n"
        "## Required on Windows runner\n"
        "1. Export Godot 4.4.1 Windows desktop build into `Godot/`.\n"
        "2. Build Python sidecar with PyInstaller (`dmb_sidecar.exe`).\n"
        "3. Copy `godot_project/content`, policies, and `manifests/release.json`.\n"
        "4. Run `tools/smoke_release.py --platform windows` offline.\n\n"
        "Do **not** mark windows_certified until those steps execute on Windows.\n",
        encoding="utf-8",
    )
    (out / "LICENSES.txt").write_text(
        "See repository LICENSE and third-party notices under godot_project/.\n",
        encoding="utf-8",
    )
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform_builder": platform.system(),
        "target": "windows",
        "windows_certified": False,
        "windows_executable_produced": False,
        "bundle": str(out.relative_to(ROOT)),
        "blocker": "No Windows runner execution in this environment — scaffold only.",
    }
    (TRACK / "gates" / "G10").mkdir(parents=True, exist_ok=True)
    (TRACK / "gates" / "G10" / "windows_scaffold.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    (out / "bundle.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("linux", "windows", "all"), default="all")
    args = parser.parse_args(argv)
    results = {}
    if args.target in ("linux", "all"):
        results["linux"] = package_linux()
    if args.target in ("windows", "all"):
        results["windows"] = package_windows_scaffold()
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
