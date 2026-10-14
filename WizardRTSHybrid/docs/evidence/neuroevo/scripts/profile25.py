import sys, os, time, json, cProfile, pstats, io
from pathlib import Path
HYB = Path(__file__).resolve().parents[4]  # WizardRTSHybrid (evidence copy of a scratch script; run from the repo)
sys.path.insert(0, str(HYB)); sys.path.insert(0, str(HYB.parent))
os.environ["HYBRID_AI"] = "1"; os.environ["HYBRID_AI_POLICY"] = "plus"
from wizard_rts.world import HybridWorld
from wizard_rts import ai_plus, regions
w = HybridWorld(7, terrain=True, map_size="standard", profile="campaign"); w.cardset, w.draft_v2 = "v2", True
seq = 0
for i in range(25 * 60):
    seq += 1; w.advance(1000, seq, snapshot=False)
t = time.perf_counter()
for _ in range(60):
    seq += 1; w.advance(1000, seq, snapshot=False)
per_s = (time.perf_counter() - t) / 60 * 1000
# AI cost: time ai_plus.decide for all six factions once
t = time.perf_counter()
for n in list(w.faction_info): ai_plus.decide(w, n)
ai_ms = (time.perf_counter() - t) * 1000
s = regions.state(w)
print(json.dumps({"buildings": len(w.buildings), "units": sum(1 for u in w.units.values() if u.get("alive", True)), "advance_1s_ms": round(per_s, 1), "x_realtime": round(1000/per_s, 1), "ai_decide_6_factions_ms": round(ai_ms, 1), "regions": len(s.axials), "map": [w.terrain.w, w.terrain.h]}))
pr = cProfile.Profile(); pr.enable()
for _ in range(60):
    seq += 1; w.advance(1000, seq, snapshot=False)
pr.disable(); out = io.StringIO(); pstats.Stats(pr, stream=out).sort_stats("tottime").print_stats(22); txt = out.getvalue()
print("\n".join(l[:160] for l in txt.splitlines()[:40]))
