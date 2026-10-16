"""How much does one simulated minute of a Wizard World cost? (plan amendment 10: the offline catch-up budget.)

Builds the same world the host builds for a phone (`net.host.new_world`: small map, campaign profile, narrative layer, the AI on, the
`plus` policy as the host uses) and advances it in 100 ms quanta, printing wall seconds per simulated minute at each minute. Run on the PC
and on a phone (through `android_entry`'s self-test harness, or by hand) to set `R` and `CAP` in `data/narrative/config.json`.

    py -3 WizardRTSHybrid/scripts/bench_catchup.py --minutes 10 --map small --seed 507
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB))
sys.path.insert(0, str(HYB.parent))
os.environ.setdefault("HYBRID_AI", "1")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, default=10)
    ap.add_argument("--map", default="small")
    ap.add_argument("--seed", type=int, default=507)
    ap.add_argument("--quantum-ms", type=int, default=100)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    from wizard_rts.net.host import new_world

    t0 = time.perf_counter()
    world = new_world(a.seed, a.map, "campaign")
    build_s = time.perf_counter() - t0
    rows = []
    seq = 0
    last = time.perf_counter()
    for minute in range(1, a.minutes + 1):
        for _ in range(60_000 // a.quantum_ms):
            seq += 1
            world.advance(a.quantum_ms, seq, snapshot=False)
        now = time.perf_counter()
        rows.append({"minute": minute, "wall_s": round(now - last, 2), "buildings": len(world.buildings), "workers": len(world.workers),
                     "units": sum(1 for u in world.units.values() if u.get("alive", True))})
        print(json.dumps(rows[-1]), flush=True)
        last = now
    total = sum(r["wall_s"] for r in rows)
    summary = {"map": a.map, "seed": a.seed, "build_s": round(build_s, 2), "minutes": a.minutes, "wall_s_total": round(total, 2),
               "wall_s_per_sim_minute": round(total / max(1, a.minutes), 2), "x_realtime": round(60 * a.minutes / max(total, 1e-6), 1),
               "python": sys.version.split()[0], "platform": sys.platform, "rows": rows}
    print("CATCHUP_BENCH " + json.dumps({k: v for k, v in summary.items() if k != "rows"}))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(summary, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
