"""Content report (plan v2 14.8 / P17): which cards and entities are dealt, drafted and actually built, and why the rest are not.

    python3 scripts/content_report.py --seeds 4000-4011 --minutes 45 --jobs 2 --out ~/dmb_runs/content_report

Plays plus-AI games with the generated cards (drafting v2) and aggregates over all games and factions. For every card: games it was dealt
in, times drafted, drafted-and-built. The diagnosis follows the plan's order: not dealt -> dealt but not drafted -> drafted but belongs to another
tribe -> drafted, usable, not built (an AI decision or a chain problem to look at by hand) -> built. No unit is forced into use.
"""
from __future__ import annotations

import argparse
import collections
import json
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB))
sys.path.insert(0, str(HYB.parent))


def play(job: dict) -> dict:
    os.environ["HYBRID_AI"] = "1"
    os.environ["HYBRID_AI_POLICY"] = "plus"
    from wizard_rts import inspector
    from wizard_rts.world import HybridWorld

    t0 = time.time()
    w = HybridWorld(job["seed"], terrain=True, map_size="standard", profile="campaign")
    w.cardset, w.draft_v2 = "v2", True
    dealt: set[str] = set()
    drafted: list[list[str]] = []
    for i in range(job["minutes"] * 60):
        w.advance(1000, i + 1, snapshot=False)
        for e in w.events:
            if e["kind"] == "draft_phase":
                dealt.update(e["dealt"])
            elif e["kind"] == "card_drafted":
                drafted.append([e["faction"], e["card"]])
        w.events.clear()
    fv = inspector.factions(w)
    built = {f: [e["id"] for h in v["cards"] for e in h["entities"] if e["produced"]] for f, v in fv.items()}
    return {"seed": job["seed"], "dealt": sorted(dealt), "drafted": drafted, "built": built, "tribes": {f: i.get("tribe", "") for f, i in w.faction_info.items()},
            "wall_s": round(time.time() - t0, 1)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="4000-4011")
    ap.add_argument("--minutes", type=int, default=45)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--out", default=str(Path.home() / "dmb_runs" / "content_report"))
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.seeds.split("-"))
    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    f = out / "games.jsonl"
    done = {r["seed"]: r for r in map(json.loads, f.read_text().splitlines())} if f.exists() else {}
    jobs = [{"seed": s, "minutes": a.minutes} for s in range(lo, hi + 1) if s not in done]
    with mp.get_context("spawn").Pool(a.jobs) as pool, f.open("a") as fh:
        for r in pool.imap_unordered(play, jobs):
            fh.write(json.dumps(r) + "\n")
            fh.flush()
            done[r["seed"]] = r
            print("seed", r["seed"], r["wall_s"], "s", flush=True)
    from wizard_rts.content import graph

    cards = graph.generated_cards()
    ents = graph.entities()
    dealt_n, drafted_n, built_n, other_tribe = (collections.Counter() for _ in range(4))
    for r in done.values():
        for c in r["dealt"]:
            dealt_n[c] += 1
        for fac, c in r["drafted"]:
            drafted_n[c] += 1
            tribe = cards.get(c, {}).get("tribe", "")
            if tribe and tribe != r["tribes"].get(fac, ""):
                other_tribe[c] += 1
            elif any(e in r["built"].get(fac, []) for e in cards.get(c, {}).get("entities", [])):
                built_n[c] += 1
    n = len(done)
    lines = [f"# Content report: {n} games, {a.minutes} game minutes, plus AIs, generated cards\n",
             f"Cards dealt at least once: {sum(1 for c in cards if dealt_n[c])}/{len(cards)}; drafted at least once: {sum(1 for c in cards if drafted_n[c])}/{len(cards)}; "
             f"drafted and built at least once: {sum(1 for c in cards if built_n[c])}/{len(cards)}\n",
             "| diagnosis | cards |", "| --- | ---: |"]
    cat = collections.defaultdict(list)
    for c, card in cards.items():
        if not dealt_n[c]:
            cat["never dealt in these games"].append(c)
        elif not drafted_n[c]:
            cat["dealt, never drafted"].append(c)
        elif built_n[c]:
            cat["drafted and built"].append(c)
        elif other_tribe[c] == drafted_n[c]:
            cat["drafted only by other tribes (denial or trade-off)"].append(c)
        else:
            cat["drafted by its tribe, never built (look at the AI or the chain)"].append(c)
    for k, v in sorted(cat.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"| {k} | {len(v)} |")
    lines.append("\n## Drafted by its own tribe but never built\n")
    for c in sorted(cat.get("drafted by its tribe, never built (look at the AI or the chain)", [])):
        lines.append(f"* `{c}` ({', '.join(cards[c]['entities'])}), drafted {drafted_n[c]}x, dealt in {dealt_n[c]} games")
    lines.append("\n## Dealt but never drafted\n")
    lines.append(", ".join(f"`{c}`" for c in sorted(cat.get("dealt, never drafted", []))) or "none")
    (out / "report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:12]))


if __name__ == "__main__":
    main()
