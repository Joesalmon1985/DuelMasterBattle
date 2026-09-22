#!/usr/bin/env python3
"""Package a Linux desktop launch bundle for MVP (T113).

Does NOT claim Windows certification. Records platform honestly.
"""

from __future__ import annotations

import json
import platform
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "desktop" / "mvp_linux"
TRACK = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking" / "mvp_build"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    TRACK.mkdir(parents=True, exist_ok=True)
    # Bundle launchers + docs; Godot binary is referenced, not duplicated.
    for name in ("play_mvp.sh", "play_fx_era.sh", "play_g05.sh", "find_godot.sh"):
        src = ROOT / "tools" / name
        if src.is_file():
            dst = OUT / name
            shutil.copy2(src, dst)
            dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    readme = OUT / "README.md"
    readme.write_text(
        "# DMB MVP Linux launch bundle\n\n"
        "Requires Godot 4.4.1 on PATH or via `find_godot.sh`.\n\n"
        "```bash\n./play_mvp.sh\n# or near-transition checkpoint:\n./play_fx_era.sh\n```\n\n"
        "Sidecar starts automatically from the Godot client. Quitting Godot should stop the sidecar.\n\n"
        "**Windows:** not packaged/tested by this script (Linux ≠ Windows).\n",
        encoding="utf-8",
    )
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.system(),
        "machine": platform.machine(),
        "windows_certified": False,
        "bundle": str(OUT.relative_to(ROOT)),
        "launchers": ["play_mvp.sh", "play_fx_era.sh", "play_g05.sh"],
    }
    (TRACK / "desktop_bundle.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (OUT / "bundle.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
