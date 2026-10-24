"""Headless God World runs: the acceptance corpus (PRD 14). Each seed runs until the fourth-age result or until an age reaches the diagnostic
budget of production pulses (a stall to investigate, never a reason to advance).

    python WizardRTSHybrid/scripts/god_world_run.py --seeds 0-19 507 --budget 600 --out docs/evidence/god_world/corpus.json
    python WizardRTSHybrid/scripts/god_world_run.py --seeds 3 --ages 1          # one age-one win

Prints one JSON line per seed and a summary; exit code 1 when any seed stalled or broke an invariant."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parents[1]
for entry in (str(_HERE), str(_HERE.parent)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from wizard_rts.god_world import rules  # noqa: E402
from wizard_rts.god_world.world import GodWorld  # noqa: E402


def parse_seeds(items: list[str]) -> list[int]:
    out: list[int] = []
    for item in items:
        if "-" in item:
            a, b = item.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(item))
    return out


def run_seed(seed: int, budget: int, ages: int, check_every: int = 600, save_load_every: int = 0, economy_only: bool = False, max_retries: int = 3) -> dict:
    w = GodWorld(seed=seed)
    w.pandemic_enabled = not economy_only
    retries_total = 0
    t0 = time.time()
    seq = 0
    per_age: dict[int, dict] = {}
    stalled = False
    last_age = w.age
    age_start_ms = 0
    quanta = 0
    while True:
        seq += 1
        w.advance(1000, seq, snapshot=False)
        quanta += 10
        if quanta % check_every == 0:
            w.check()
        if save_load_every and quanta % save_load_every == 0:
            w = GodWorld.from_dict(json.loads(json.dumps(w.to_dict())))
        if w.age != last_age:
            per_age[last_age] = _age_row(w, last_age, age_start_ms)
            last_age = w.age
            age_start_ms = w.game_ms
        if w.final_result is not None:
            per_age[w.age] = _age_row(w, w.age, age_start_ms)
            break
        if w.pandemic_lost is not None and w.paused:
            # a lost campaign pauses the run; the corpus retries from the age's checkpoint up to the limit, and the loss is on the record
            if retries_total >= max_retries:
                stalled = True
                per_age[w.age] = _age_row(w, w.age, age_start_ms)
                per_age[w.age]["stalled"] = True
                per_age[w.age]["lost_campaign"] = dict(w.pandemic_lost)
                break
            retries_total += 1
            w.retry_pandemic()
        if w.pulses >= budget:
            stalled = True
            per_age[w.age] = _age_row(w, w.age, age_start_ms)
            per_age[w.age]["stalled"] = True
            per_age[w.age]["diagnostics"] = {f: {"hand": w.ledger.available(f), "vp": w.vp(f), "goal": w.ai[f].get("goal"), "reason": w.ai[f].get("reason"),
                                                 "legal_sites": len(w.legal_sites(f)), "villages": len(w.faction_villages(f))} for f in w.fids}
            break
        if ages and w.age > ages:
            break
        if ages and w.age == ages and w.history["age_winners"] and w.history["age_winners"][-1]["age"] == ages:
            break
    w.check()
    winners = [(r["age"], r["winner"]) for r in w.history["age_winners"]]
    campaigns = list(w.history.get("pandemic", []))
    return {"seed": seed, "ok": not stalled, "stalled": stalled, "ages": per_age, "winners": winners, "game_minutes": round(w.game_ms / 60000.0, 1),
            "wall_s": round(time.time() - t0, 1), "counters": dict(w.counters), "final": bool(w.final_result), "economy_only": economy_only,
            "campaigns": campaigns, "campaign_wins": sum(1 for c in campaigns if c["result"] == "won"), "campaign_losses": sum(1 for c in campaigns if c["result"] == "lost"),
            "retries": retries_total}


def _age_row(w: GodWorld, age: int, start_ms: int) -> dict:
    rec = next((r for r in w.history["age_winners"] if r["age"] == age), None)
    return {"age": age, "name": rules.age_name(age), "winner": rec["winner"] if rec else None, "pulses": rec["pulses"] if rec else w.pulses,
            "minutes": round((w.game_ms - start_ms) / 60000.0, 1), "vp": rec["vp"] if rec else {f: w.vp(f) for f in w.fids},
            "villages": rec["villages"] if rec else sum(1 for v in w.villages.values() if v["status"] in ("operational", "rebuilding")),
            "cities": rec["cities"] if rec else sum(1 for v in w.villages.values() if v["status"] == "operational" and int(v["level"]) >= 2),
            "trades": int(w.counters["trades"]), "bank_trades": int(w.counters["bank_trades"]), "roads": int(w.counters["roads"])}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="+", default=["0-19", "507"])
    ap.add_argument("--budget", type=int, default=rules.limit("diagnostic_pulses_per_age"))
    ap.add_argument("--ages", type=int, default=0, help="stop after this age's result (0 = the full four ages)")
    ap.add_argument("--out", default="")
    ap.add_argument("--save-load-every", type=int, default=0, help="round-trip the world through its save every N quanta (a determinism check)")
    ap.add_argument("--economy-only", action="store_true", help="the strategic regression alone: the campaign off, the age gate the economy's")
    ap.add_argument("--max-retries", type=int, default=3, help="combined runs: retries from the checkpoint after a lost campaign before the seed counts as stalled")
    args = ap.parse_args(argv)
    rows = []
    for seed in parse_seeds(args.seeds):
        row = run_seed(seed, args.budget, args.ages, save_load_every=args.save_load_every, economy_only=args.economy_only, max_retries=args.max_retries)
        rows.append(row)
        print(json.dumps(row, separators=(",", ":")), flush=True)
    ok = all(r["ok"] for r in rows)
    summary = {"seeds": len(rows), "ok": ok, "stalled": [r["seed"] for r in rows if r["stalled"]], "economy_only": bool(args.economy_only),
               "campaign_wins": sum(r.get("campaign_wins", 0) for r in rows), "campaign_losses": sum(r.get("campaign_losses", 0) for r in rows), "retries": sum(r.get("retries", 0) for r in rows),
               "minutes_per_age": sorted(round(a["minutes"], 1) for r in rows for a in r["ages"].values() if a.get("winner")),
               "pulses_per_age": sorted(a["pulses"] for r in rows for a in r["ages"].values() if a.get("winner"))}
    print("GOD_WORLD_CORPUS " + json.dumps(summary), flush=True)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps({"summary": summary, "runs": rows, "budget": args.budget}, indent=1), encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
