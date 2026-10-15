"""Headless 240-minute benchmark (neuroevolution plan, section 11): one game with every v2 system on (same settings as scripts/long_stability.py), Windows-safe (no `resource`).
Logs wall seconds per 5 game minutes, entity counts, era, VP, outbreaks, collective loss. Stops at --minutes or when the cycle ends."""
from __future__ import annotations
import argparse, collections, json, os, sys, time
from pathlib import Path
HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB)); sys.path.insert(0, str(HYB.parent))
os.environ["HYBRID_AI"] = "1"
os.environ.setdefault("HYBRID_AI_POLICY", "plus")
from wizard_rts import vp, history, regions  # noqa: E402
from wizard_rts.sysinfo import rss_mb  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, default=240); ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", required=True); ap.add_argument("--wall-cap-s", type=int, default=0)
    ap.add_argument("--diplomacy", type=int, default=1); ap.add_argument("--map", default="standard")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    w = HybridWorld(a.seed, terrain=True, map_size=a.map, profile="campaign")
    w.cardset, w.draft_v2, w.diplomacy_enabled = "v2", True, bool(a.diplomacy)
    w.nest_policy = {n: "coop" for n in w.faction_info}
    gen = time.time() - t0
    ev = collections.Counter(); last = time.time(); prog = (out / "progress.jsonl").open("a")
    prog.write(json.dumps({"generate_s": round(gen, 1), "seed": a.seed, "policy": os.environ["HYBRID_AI_POLICY"], "pid": os.getpid()}) + "\n"); prog.flush()
    ended = ""
    for i in range(a.minutes * 60):
        w.advance(1000, i + 1, snapshot=False)
        for e in w.events: ev[e["kind"]] += 1
        w.events.clear()
        if getattr(w, "collective_loss", False): ended = "collective_loss"
        elif getattr(w, "cycle_pending", False): ended = "cycle_complete"
        if (i + 1) % 300 == 0 or ended:
            now = time.time(); s = regions.state(w)
            row = {"minute": round((i + 1) / 60, 1), "wall_s_per_5min": round(now - last, 1), "x_realtime": round(300 / max(now - last, 1e-6), 1),
                   "wall_total_s": round(now - t0), "buildings": len(w.buildings), "units": sum(1 for u in w.units.values() if u.get("alive", True)),
                   "workers": len(w.workers), "carriers": len(w.carriers), "era": w.era_index, "vp": vp.totals(w), "rss_mb": rss_mb(),
                   "outbreaks": s.outbreaks if s else None, "cubes": sum(s.cubes) if s else None, "ended": ended}
            last = now; prog.write(json.dumps(row) + "\n"); prog.flush()
        if ended: break
        if a.wall_cap_s and time.time() - t0 > a.wall_cap_s:
            ended = "wall_cap"; prog.write(json.dumps({"minute": round((i + 1) / 60, 1), "ended": ended}) + "\n"); prog.flush(); break
    summary = {"seed": a.seed, "minutes_played": round((i + 1) / 60, 1), "wall_s": round(time.time() - t0), "ended": ended or "horizon",
               "outcome": history.outcome(w), "era": w.era_index, "vp": vp.totals(w), "events": dict(ev.most_common(40)), "state_hash": w.state_hash(),
               "buildings": len(w.buildings), "units": sum(1 for u in w.units.values() if u.get("alive", True)), "rss_mb": rss_mb()}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str)); print(json.dumps(summary, default=str)[:2000])

if __name__ == "__main__":
    main()
