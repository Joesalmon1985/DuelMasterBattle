"""Modern-start probe (plan v2 6.2, 9.3 industrialisation scenario): do the AIs use the Mindustry content when the world starts in the Modern era?

    python3 scripts/modern_probe.py [--seed 507] [--minutes 60] [--era 2]

Developer profile with the generated cards, the era jumped to Modern (or Dystopian) at minute 0 so a phase of Modern cards is dealt; reports per
faction which Mindustry buildings and units were drafted and built, and the ware ledger of machine outputs (silicon, graphite, ...).
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
os.environ.setdefault("HYBRID_AI_POLICY", "plus")

from wizard_rts import inspector, tech, vp  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=507)
    ap.add_argument("--minutes", type=int, default=60)
    ap.add_argument("--era", type=int, default=2)
    a = ap.parse_args()
    w = HybridWorld(a.seed, terrain=True, map_size="standard", profile="developer")
    w.cardset, w.draft_v2 = "v2", True
    vp.set_era(w, a.era)
    ev = collections.Counter()
    for i in range(a.minutes * 60):
        w.advance(1000, i + 1, snapshot=False)
        for e in w.events:
            ev[e["kind"]] += 1
        w.events.clear()
    print("events:", {k: v for k, v in ev.most_common(10)})
    print("machine wares made:", {k[5:]: v for k, v in w.stats.items() if k.startswith("made_") and k[5:] in ("silicon", "graphite", "copper", "lead", "sand", "scrap", "titanium", "coal", "iron_ore")})
    for f, view in inspector.factions(w).items():
        mdy = [e for h in view["cards"] for e in h["entities"] if e["id"].startswith("mdy:") or e["id"] in ("unit:dagger", "unit:crawler", "unit:nova")]
        built = [e["id"] for e in mdy if e["produced"]]
        print(f, "cards", len(view["cards"]), "mindustry entities drafted", len(mdy), "built", built)
    print("era", tech.ERAS[w.era_index], "VP", vp.totals(w))


if __name__ == "__main__":
    main()
