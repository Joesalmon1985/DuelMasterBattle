"""Run the AI of whichever tree is on sys.path[0] for N game minutes (war) and print a compact per-faction summary as JSON."""
import json, os, sys, time
root = sys.argv[1]; seed = int(sys.argv[2]); minutes = int(sys.argv[3])
sys.path.insert(0, root + "/WizardRTSHybrid"); sys.path.insert(0, root)
os.environ["HYBRID_AI"] = "1"
from wizard_rts.world import HybridWorld, FACTIONS
w = HybridWorld(seed=seed); w.ai_aggressive = True
seq = 0; t0 = time.perf_counter(); worst = 0; series = []
for step in range(minutes * 600):
    seq += 1; t = time.perf_counter(); w.advance(100, seq, snapshot=False); worst = max(worst, time.perf_counter() - t)
    if (step + 1) % 6000 == 0:
        row = {}
        for n, _h, _c in FACTIONS:
            units = [u for u in w.units.values() if u["faction_name"] == n and u.get("alive", True)]
            blds = [b for b in w.buildings.values() if b["faction_name"] == n and "hp" in b and int(b["hp"]) > 0]
            wh = [b for b in blds if b["kind"] == "warehouse"]
            fs = w.fstats.get(n, {})
            row[n] = {"alive": bool(wh), "warehouses": len(wh), "buildings": len(blds), "units": len(units), "navy": sum(1 for u in units if u.get("loco") in ("naval", "lcraft")),
                      "idle_far_from_home": 0, "unit_kills": int(fs.get("unit_kills", 0)), "building_kills": int(fs.get("building_kills", 0)), "building_losses": int(fs.get("building_losses", 0))}
        series.append({"minute": (step + 1) // 600, "f": row})
print(json.dumps({"root": root, "seed": seed, "wall": round(time.perf_counter() - t0), "worst_step_ms": round(worst * 1000), "series": series}))
