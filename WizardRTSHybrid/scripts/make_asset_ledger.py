"""Asset ledger (plan v2 8.3 item 4): one row per shipped art file with its catalogue item, source, licence note and SHA-256.

    python3 scripts/make_asset_ledger.py            # write docs/evidence/assets/asset_ledger.csv and print coverage
    python3 scripts/make_asset_ledger.py --check    # fail if a shipped png has no ledger row (not covered by any catalogue item)
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
REPO = HYB.parent
ART = REPO / "godot_project" / "client" / "hybrid" / "art"
OUT = HYB / "docs" / "evidence" / "assets" / "asset_ledger.csv"


def files_of(item: dict) -> list[str]:
    out = []
    if item.get("godot"):
        out.append(item["godot"])
    out += list(item.get("frames_godot", []))
    lay = item.get("layers")
    if lay:  # independent turret layers: <prefix>-NNNN.png for each facing
        out += [f"res://client/hybrid/art/openra/{lay[k]}-{f:04d}.png" for k in ("body_prefix", "turret_prefix") for f in range(int(lay.get("facings", 32)))]
    out += [pt["file"] for pt in item.get("parts", [])]
    return [p.replace("res://client/hybrid/art/", "") for p in dict.fromkeys(out)]


def main() -> int:
    cat = json.loads((ART / "catalogue.json").read_text(encoding="utf-8"))["items"]
    rows, covered = [], set()
    for item in cat:
        for rel in files_of(item):
            f = ART / rel
            covered.add(rel)
            rows.append([rel, item["id"], item.get("game", ""), item.get("status", ""), item.get("alias_of", ""), item.get("source", "")[:120],
                         (item.get("license", "") or "")[:90], hashlib.sha256(f.read_bytes()).hexdigest() if f.is_file() else "MISSING"])
    shipped = {str(p.relative_to(ART)) for p in ART.rglob("*.png")}
    orphan = sorted(shipped - covered)
    print(f"{len(rows)} ledger rows, {sum(r[-1] == 'MISSING' for r in rows)} listed files missing on disk, {len(orphan)} shipped png without a catalogue item")
    if "--check" in sys.argv:
        return 1 if orphan or any(r[-1] == "MISSING" for r in rows) else 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "catalogue_id", "game", "status", "alias_of", "source", "license", "sha256"])
        w.writerows(sorted(rows))
        for rel in orphan:
            w.writerow([rel, "", "", "orphan", "", "", "", hashlib.sha256((ART / rel).read_bytes()).hexdigest()])
    print("wrote", OUT.relative_to(REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
