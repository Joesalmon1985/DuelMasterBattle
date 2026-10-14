"""Cost of observation extraction, legal-action masks and one heuristic AI decision on a 25-minute six-faction world."""
import sys, os, time, json
from pathlib import Path
HYB = Path(__file__).resolve().parents[4]  # WizardRTSHybrid (evidence copy of a scratch script; run from the repo)
sys.path.insert(0, str(HYB)); sys.path.insert(0, str(HYB.parent))
os.environ["HYBRID_AI"] = "1"; os.environ["HYBRID_AI_POLICY"] = "plus"
from wizard_rts.sim_api import HybridEnv
from wizard_rts import ai_plus, ai
env = HybridEnv(seed=7, map_size="standard", agent_factions=(), step_ms=5000, profile="campaign")
env.reset(); w = env.world; w.cardset, w.draft_v2 = "v2", True
t0 = time.time()
for i in range(25 * 60): w.advance(1000, i + 1, snapshot=False)
print(json.dumps({"warmup_wall_s": round(time.time()-t0,1), "buildings": len(w.buildings), "units": sum(1 for u in w.units.values() if u.get("alive", True)), "workers": len(w.workers), "carriers": len(w.carriers)}))
def timeit(fn, n=20):
    t = time.perf_counter()
    for _ in range(n): fn()
    return round((time.perf_counter() - t) / n * 1000, 2)
out = {}
out["observe_ms"] = timeit(lambda: env.observe("Red"))
out["legal_actions_ms"] = timeit(lambda: env.legal_actions("Red"))
out["flatten_len"] = len(env.flatten(env.observe("Red")))
out["state_hash_ms"] = timeit(lambda: w.state_hash(), 3)
out["snapshot_ms"] = timeit(lambda: w.snapshot(), 3)
out["snapshot_kb"] = len(json.dumps(w.snapshot())) // 1024
t = time.perf_counter(); ai_plus.decide(w, "Red"); out["ai_plus_decide_ms"] = round((time.perf_counter()-t)*1000, 2)
t = time.perf_counter(); 
for _ in range(50): w.advance(1000, 10_000 + _, snapshot=False)
out["advance_1s_mean_ms_at_25min"] = round((time.perf_counter()-t)*1000/50, 2)
# per-quantum breakdown via cProfile on 30 game seconds
import cProfile, pstats, io
pr = cProfile.Profile(); pr.enable()
for _ in range(30): w.advance(1000, 20_000 + _, snapshot=False)
pr.disable(); s = io.StringIO(); pstats.Stats(pr, stream=s).sort_stats("tottime").print_stats(18); 
print(json.dumps(out, indent=1)); print(s.getvalue()[:4500])
