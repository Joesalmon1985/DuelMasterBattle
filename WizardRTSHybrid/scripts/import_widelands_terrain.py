"""Import Widelands terrain, resource and tree-affinity definitions into wizard_rts/data/terrain_defs.json.

Reads the sparse Widelands checkout under external/widelands (pinned in sources/manifest.json).
Source files: data/world/terrains/<world>/<name>/init.lua, data/world/resources/<name>/init.lua,
data/world/immovables/trees/<species>/terrain_affinity.lua. GPL-2.0-or-later, Widelands Development Team.
Run with: python3 scripts/import_widelands_terrain.py
"""
from __future__ import annotations
import sys as _sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from wizard_rts import freeze_guard  # noqa: E402  (content is frozen: D33)
freeze_guard.require_unfreeze(__file__)

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WL = ROOT / "external" / "widelands"
OUT = ROOT / "wizard_rts" / "data" / "terrain_defs.json"


def _strip(src: str) -> str:
    """Drop Lua comment lines: some init.lua files carry a commented example with another terrain's name."""
    return "\n".join(line for line in src.splitlines() if not line.lstrip().startswith("--"))


def _val(src: str, key: str, default=None):
    src = _strip(src)
    m = re.search(rf"\b{key}\s*=\s*(\"[^\"]*\"|-?\d+)", src)
    if not m:
        return default
    v = m.group(1)
    return v.strip('"') if v.startswith('"') else int(v)


def main() -> int:
    if not (WL / "data/world/terrains").is_dir():
        print("missing sparse Widelands checkout: see docs/WORK_LOG.md for the commands", file=sys.stderr)
        return 1
    commit = subprocess.run(["git", "-C", str(WL), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    terrains = {}
    for init in sorted((WL / "data/world/terrains").glob("*/*/init.lua")):
        src = init.read_text()
        name = _val(src, "name")
        vr = re.search(r"valid_resources\s*=\s*\{([^}]*)\}", _strip(src))
        res = re.findall(r"resource_(\w+)", vr.group(1)) if vr else []
        dres = _val(src, "default_resource", "") or ""
        terrains[name] = {
            "world": init.parent.parent.name,
            "dir": init.parent.name,
            "is": _val(src, "is"),
            "valid_resources": res,
            "default_resource": dres.replace("resource_", ""),
            "default_amount": _val(src, "default_resource_amount", 0),
            "temperature": _val(src, "temperature", 100),
            "humidity": _val(src, "humidity", 500),
            "fertility": _val(src, "fertility", 500),
            "textures": sorted(p.name for p in init.parent.glob("*.png"))[:1],
        }
    resources = {}
    for init in sorted((WL / "data/world/resources").glob("*/init.lua")):
        src = init.read_text()
        name = _val(src, "name", "").replace("resource_", "")
        resources[name] = {
            "max_amount": _val(src, "max_amount", 0),
            "detectable": "detectable = true" in src,
        }
    affinity = {}
    for f in sorted((WL / "data/world/immovables/trees").glob("*/terrain_affinity.lua")):
        src = f.read_text()
        affinity[f.parent.name] = {k: _val(src, k) for k in
                                   ("preferred_temperature", "preferred_humidity", "preferred_fertility", "pickiness")}
    OUT.write_text(json.dumps({
        "source": {"repo": "widelands/widelands", "commit": commit, "licence": "GPL-2.0-or-later"},
        "terrains": terrains, "resources": resources, "tree_affinity": affinity,
    }, indent=1, sort_keys=True))
    print(f"terrains={len(terrains)} resources={len(resources)} affinities={len(affinity)} -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
