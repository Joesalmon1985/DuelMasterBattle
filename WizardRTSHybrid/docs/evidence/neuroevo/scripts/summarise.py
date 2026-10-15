import json, sys
base = sys.argv[1]
for s in sys.argv[2:]:
    rows = [json.loads(l) for l in open(f"{base}/bench/g240_seed{s}/progress.jsonl") if l.strip()]
    rows = [r for r in rows if "minute" in r]
    print(f"=== seed {s} ===")
    for r in rows:
        if r["minute"] % 20 == 0 or r.get("ended"):
            print(f"min {r['minute']:>5} x{r['x_realtime']:>5} wall {r['wall_total_s']:>5}s bld {r['buildings']:>4} units {r['units']:>3} era {r['era']} outbreaks {r['outbreaks']} cubes {r['cubes']:>2} vp_sum {sum(r['vp'].values()):>3} factions {len(r['vp'])} {r.get('ended','')}")
    print("last:", rows[-1]["minute"], rows[-1]["wall_total_s"], "s")
