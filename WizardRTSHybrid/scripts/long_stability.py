"""One long game with every v2 system switched on, checking invariants as it goes (plan v2 14.5: headless long runs).

    python3 scripts/long_stability.py --minutes 180 --seed 7 --out ~/dmb_runs/stability_180

Cards v2 with the era-start ring draft, plus AIs, cooperative diplomacy and nest hunting, clinics, caravans. Every 5 game minutes it logs wall seconds
per game minute (the throughput curve), entity counts and event counts; every 30 minutes it checks the ware ledger, negative stocks and VP replay.
Writes progress.jsonl (append-only, so a crash keeps what was seen) and summary.json at the end.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB))
sys.path.insert(0, str(HYB.parent))
os.environ["HYBRID_AI"] = "1"
os.environ["HYBRID_AI_POLICY"] = "plus"

from wizard_rts import diplomacy, inspector, ledger, sysinfo, vp  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, default=180)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=str(Path.home() / "dmb_runs" / "stability"))
    a = ap.parse_args()
    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    w = HybridWorld(a.seed, terrain=True, map_size="standard", profile="campaign")
    w.cardset, w.draft_v2, w.diplomacy_enabled = "v2", True, True
    w.nest_policy = {n: "coop" for n in w.faction_info}
    initial = ledger.snapshot_totals(w)
    ev = collections.Counter()
    failures = []
    hb = os.environ.get("DMB_HEARTBEAT")
    t0 = last = time.time()
    prog = (out / "progress.jsonl").open("a")
    for i in range(a.minutes * 60):
        w.advance(1000, i + 1, snapshot=False)
        for e in w.events:
            ev[e["kind"]] += 1
        w.events.clear()
        if (i + 1) % 300 == 0:
            now = time.time()
            row = {"minute": (i + 1) // 60, "wall_s_per_5min": round(now - last, 1), "x_realtime": round(300 / (now - last), 1), "buildings": len(w.buildings), "units": sum(1 for u in w.units.values() if u.get("alive", True)),
                   "workers": len(w.workers), "carriers": len(w.carriers), "era": w.era_index, "vp": vp.totals(w), "rss_mb": sysinfo.rss_mb(),
                   "relations": len(w.__dict__.get("relations", {}))}
            last = now
            prog.write(json.dumps(row) + "\n")
            prog.flush()
            if hb:
                Path(hb).write_text(str(now))
        if (i + 1) % 1800 == 0:
            bad = ledger.check(w, initial)
            neg = [(b, g, v) for b, s in w.stocks.items() for g, v in s.items() if v < 0]
            if bad or neg or vp.replay(w) != vp.totals(w):
                failures.append({"minute": (i + 1) // 60, "ledger": bad[:5] if bad else None, "negative": neg[:5], "vp_replay_ok": vp.replay(w) == vp.totals(w)})
    fv = inspector.factions(w)
    ents = [e for v in fv.values() for h in v["cards"] for e in h["entities"]]
    summary = {"seed": a.seed, "minutes": a.minutes, "wall_s": round(time.time() - t0), "failures": failures, "events": dict(ev.most_common(40)), "state_hash": w.state_hash(),
               "era": w.era_index, "vp": vp.totals(w), "cards_used_rate": round(sum(1 for e in ents if e["produced"]) / max(1, len(ents)), 3),
               "collective_loss": bool(getattr(w, "collective_loss", False)), "peak_rss_mb": sysinfo.rss_mb()}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps(summary, indent=1, default=str)[:1500])


if __name__ == "__main__":
    main()
