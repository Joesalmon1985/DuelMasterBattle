"""Evidence: are faction outcomes identical with the legacy story_quantum switched off? Compares a faction-only hash
(buildings, units, stocks, workers, carriers, tech, stats, fstats, faction_info, history, draft_state, wares_ledger, terrain) and the
world RNG state every game minute, story on versus off, same seed, AIs on."""
import os, sys, json, hashlib, time
sys.path[:0] = [os.path.abspath('.'), os.path.abspath('..')]
os.environ['HYBRID_AI'] = '1'
from wizard_rts.world import HybridWorld
from wizard_rts import story

def faction_hash(w):
    raw = {n: getattr(w, n, None) for n in ("buildings", "units", "stocks", "workers", "carriers", "tech", "stats", "fstats", "faction_info", "history", "draft_state", "wares_ledger")}
    h = hashlib.sha1(json.dumps(raw, sort_keys=True, default=str).encode())
    h.update(w.terrain.state_hash().encode())
    return h.hexdigest()

def run(seed, minutes, story_on):
    orig = story.story_quantum
    if not story_on:
        story.story_quantum = lambda world: None
    try:
        w = HybridWorld(seed, terrain=True, map_size='standard', profile='campaign')
        out = []
        t0 = time.time()
        for i in range(minutes * 60):
            w.advance(1000, i + 1, snapshot=False)
            if (i + 1) % 60 == 0:
                out.append((faction_hash(w), hashlib.sha1(repr(w.rng.getstate()).encode()).hexdigest(), w.state_hash()))
        return out, time.time() - t0, len(story.state(w)["quests"]), len(w.dmb.people), w.events.total
    finally:
        story.story_quantum = orig

seed, minutes = int(sys.argv[1]), int(sys.argv[2])
a, ta, qa, pa, ea = run(seed, minutes, True)
b, tb, qb, pb, eb = run(seed, minutes, False)
first_diff_faction = next((i + 1 for i, (x, y) in enumerate(zip(a, b)) if x[0] != y[0]), None)
first_diff_rng = next((i + 1 for i, (x, y) in enumerate(zip(a, b)) if x[1] != y[1]), None)
first_diff_full = next((i + 1 for i, (x, y) in enumerate(zip(a, b)) if x[2] != y[2]), None)
print(json.dumps({"seed": seed, "minutes": minutes, "wall_on_s": round(ta, 1), "wall_off_s": round(tb, 1),
                  "quests_on": qa, "people_on": pa, "events_on": ea, "quests_off": qb, "people_off": pb, "events_off": eb,
                  "first_minute_faction_hash_differs": first_diff_faction, "first_minute_rng_differs": first_diff_rng,
                  "first_minute_full_state_hash_differs": first_diff_full}))
