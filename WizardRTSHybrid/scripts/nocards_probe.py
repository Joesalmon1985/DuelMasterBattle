"""No-card civilisation probe (plan v2 P2): campaign profile, drafting off, what do the six factions achieve?

    python3 scripts/nocards_probe.py [--seed 507] [--minutes 60]
"""
from __future__ import annotations

import argparse
import collections
import os
import sys
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB))
sys.path.insert(0, str(HYB.parent))
os.environ.setdefault("HYBRID_AI", "1")

from wizard_rts import tech  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=507)
    ap.add_argument("--minutes", type=int, default=60)
    a = ap.parse_args()
    w = HybridWorld(a.seed, terrain=True, map_size="standard", profile="campaign")
    w.nocards = True
    ev = collections.Counter()
    why = collections.Counter()
    for i in range(a.minutes * 60):
        w.advance(1000, i + 1, snapshot=False)
        if (i + 1) % 600 == 0:
            ccs = collections.Counter(b["faction_name"] for b in w.buildings.values() if b.get("command_center") and int(b.get("hp", 1)) > 0)
            bl = collections.Counter(b["faction_name"] for b in w.buildings.values() if b["faction_name"] and int(b.get("hp", 1)) > 0)
            print(f"min {(i + 1) // 60:3}: settlements {dict(sorted(ccs.items()))}  buildings {dict(sorted(bl.items()))}")
        for e in w.events:
            ev[e["kind"]] += 1
            if e["kind"] == "worker_failed":
                why[e.get("reason", "")] += 1
        w.events.clear()
    print({k: v for k, v in ev.most_common(25)})
    print("worker_failed reasons", why.most_common(8))
    print("ai notes", getattr(w, "ai_notes", {}))
    print("VP", getattr(w, "vp", None) and {k: v for k, v in w.vp.items()} if hasattr(w, "vp") else "")


if __name__ == "__main__":
    main()
