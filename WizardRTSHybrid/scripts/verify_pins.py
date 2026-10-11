#!/usr/bin/env python3
"""Pin verification: every external/<id> checkout that exists must be at the commit in sources/manifest.json.
Exit 1 on mismatch; missing checkouts are reported but not an error unless --require is given."""
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(require: bool = False) -> list[tuple[str, str, str]]:
    rows = []
    for s in json.loads((ROOT / "sources" / "manifest.json").read_text())["sources"]:
        d = ROOT / "external" / s["id"]
        if not (d / ".git").exists():
            rows.append((s["id"], "MISSING" if require else "absent", s["commit"]))
            continue
        head = subprocess.run(["git", "-C", str(d), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        rows.append((s["id"], "OK" if head == s["commit"] else "MISMATCH", head))
    return rows


if __name__ == "__main__":
    rows = check("--require" in sys.argv)
    for r in rows:
        print("PIN_%s %s %s" % (r[1], r[0], r[2]))
    sys.exit(1 if any(r[1] in ("MISMATCH", "MISSING") for r in rows) else 0)
