"""Drafting v2 probe: full AI game with the generated card set; reports picks, unlocks used, settlements and errors.

    python3 scripts/draft_probe.py [--seed 507] [--minutes 90] [--policy plus|baseline]
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

from wizard_rts import draft, tech, vp  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=507)
    ap.add_argument("--minutes", type=int, default=90)
    ap.add_argument("--policy", default="")
    a = ap.parse_args()
    w = HybridWorld(a.seed, terrain=True, map_size="standard", profile="campaign")
    w.cardset, w.draft_v2 = "v2", True
    os.environ["HYBRID_AI_POLICY"] = a.policy or os.environ.get("HYBRID_AI_POLICY", "baseline")
    if a.policy:
        pass
    ev = collections.Counter()
    for i in range(a.minutes * 60):
        w.advance(1000, i + 1, snapshot=False)
        for e in w.events:
            ev[e["kind"]] += 1
            if e["kind"] in ("era_advanced", "draft_leftovers", "draft_phase"):
                print(i // 60, e["kind"], {k: v for k, v in e.items() if k != "kind"} if e["kind"] != "draft_phase" else e["era"])
        w.events.clear()
        if (i + 1) % 1200 == 0:
            ccs = collections.Counter(b["faction_name"] for b in w.buildings.values() if b.get("command_center") and int(b.get("hp", 1)) > 0)
            print(f"min {(i + 1) // 60}: VP {vp.totals(w)}  settlements {dict(ccs)}  cards {({f: len(s['cards']) for f, s in w.tech.items()})}")
    st = draft.state(w)
    print("draft state: era", st["era"], "round", st["round"], "defaults", st["default_picks"], "dups", st["duplicated_cards"], "phases", st["phases"])
    print({k: v for k, v in ev.most_common(12)})
    for f, s in w.tech.items():
        print(f, [c.split(".", 1)[1] for c in s["cards"]])


if __name__ == "__main__":
    main()
