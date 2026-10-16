#!/usr/bin/env python3
"""Fail unless every place that names the game or protocol version agrees: the Python host (`net/protocol.py`), the Godot client that says hello
(`client/net/lan_session.gd`) and both export presets. A phone whose client says 0.2.0 to a host that is 0.3.0 gets `version_mismatch` and cannot even
host (the host app checks its own client), so `build_apk.ps1` runs this before it exports anything.

    python3 scripts/android/check_versions.py        # prints VERSIONS_OK <game> <protocol> <code>, exit 1 with the differences otherwise"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def versions() -> dict[str, object]:
    py = read("WizardRTSHybrid/wizard_rts/net/protocol.py")
    gd = read("godot_project/client/net/lan_session.gd")
    presets = read("godot_project/export_presets.cfg")
    out: dict[str, object] = {
        "host game": re.search(r'^GAME_VERSION = "([^"]+)"', py, re.M).group(1),
        "host protocol": int(re.search(r"^PROTOCOL_VERSION = (\d+)", py, re.M).group(1)),
        "client game": re.search(r'^const GAME_VERSION := "([^"]+)"', gd, re.M).group(1),
        "client protocol": int(re.search(r"^const PROTOCOL_VERSION := (\d+)", gd, re.M).group(1)),
    }
    for i, m in enumerate(re.finditer(r'version/code=(\d+)\s*\nversion/name="([^"]+)"', presets)):
        out[f"preset {i} name"] = m.group(2)
        out[f"preset {i} code"] = int(m.group(1))
    return out


def problems(v: dict[str, object]) -> list[str]:
    bad = []
    if v["host game"] != v["client game"]:
        bad.append(f"game version: host {v['host game']} but client {v['client game']} (client/net/lan_session.gd GAME_VERSION)")
    if v["host protocol"] != v["client protocol"]:
        bad.append(f"protocol: host {v['host protocol']} but client {v['client protocol']} (client/net/lan_session.gd PROTOCOL_VERSION)")
    names = {k: x for k, x in v.items() if k.startswith("preset") and k.endswith("name")}
    codes = {k: x for k, x in v.items() if k.startswith("preset") and k.endswith("code")}
    if not names:
        bad.append("no export preset carries a version")
    for k, x in names.items():
        if x != v["host game"]:
            bad.append(f"{k}: {x} but the host is {v['host game']} (godot_project/export_presets.cfg)")
    if len(set(codes.values())) > 1:
        bad.append(f"the two presets have different version codes: {codes}")
    return bad


def main() -> int:
    v = versions()
    bad = problems(v)
    if bad:
        print("VERSIONS_MISMATCH")
        for b in bad:
            print("  - " + b)
        return 1
    print(f"VERSIONS_OK {v['host game']} protocol {v['host protocol']} code {v['preset 0 code']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
