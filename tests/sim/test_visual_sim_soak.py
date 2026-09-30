"""Stage 5 — bounded multi-seed soak + failure clustering."""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from pathlib import Path

from sim.dmb.testing.visual_sim.report import new_run_dir, write_json, write_summary
from sim.dmb.testing.visual_sim.slices import run_slice_a_combat, run_slice_b_construction

# Small fixed seed set (proposed budget — not measured throughput claim).
SEEDS = [507, 508, 509, 510, 511, 512]


def _signature(scenario: str, code: str, entity_kind: str = "") -> str:
    return f"{scenario}|{code}|{entity_kind}"


def test_bounded_multi_seed_soak_and_cluster(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(Path(__file__).resolve().parents[2])
    run_dir = new_run_dir(Path("."), f"soak_{tmp_path.name}_{uuid.uuid4().hex[:6]}")
    failures: list[dict] = []
    clusters: dict[str, list[dict]] = defaultdict(list)
    results = []

    for seed in SEEDS:
        # Slice B — cheap sim (retry once with larger budget if needed)
        b = run_slice_b_construction(seed=seed, max_waits=200, advance_s=40)
        if not b["ok"]:
            b = run_slice_b_construction(seed=seed, max_waits=300, advance_s=90)
        entry_b = {
            "seed": seed,
            "scenario": "slice_b",
            "scenario_class": "PRODUCTION_JOURNEY",
            "ok": b["ok"],
            "order": (b.get("committed_order") or {}).get("id"),
        }
        results.append(entry_b)
        if not b["ok"]:
            sig = _signature("slice_b", "no_committed_order", "order")
            packet = {
                "signature": sig,
                "seed": seed,
                "expected": "committed construction order",
                "actual_authority": b["authority"]["counts"],
                "assertion": "committed_action",
            }
            failures.append(packet)
            clusters[sig].append(packet)

        # Slice A — strategic/attended (bounded waits); retry once
        a = run_slice_a_combat(seed=seed, advance_s=90, max_waits=50)
        if not a["attended_ok"]:
            a = run_slice_a_combat(seed=seed, advance_s=140, max_waits=80)
        entry_a = {
            "seed": seed,
            "scenario": "slice_a",
            "scenario_class": "PRODUCTION_JOURNEY",
            "ok": a["attended_ok"],
            "strategic_ok": a["strategic_ok"],
            "battle": (a.get("battle_seen") or {}).get("id"),
        }
        results.append(entry_a)
        if not a["attended_ok"]:
            sig = _signature("slice_a", "attended_lease_failed", "battle")
            packet = {
                "signature": sig,
                "seed": seed,
                "expected": "OpenBattleLease+CloseBattleLease ACCEPTED",
                "actual_authority": a["authority"]["counts"],
                "battle_seen": a.get("battle_seen"),
                "lease_opened": a.get("lease_opened"),
                "assertion": "lease_lifecycle",
            }
            failures.append(packet)
            clusters[sig].append(packet)

    # One representative packet per signature
    packets_dir = run_dir / "failure_packets"
    packets_dir.mkdir(exist_ok=True)
    for sig, items in clusters.items():
        rep = items[0]
        rep["occurrence_count"] = len(items)
        write_json(packets_dir / f"{sig.replace('|', '_')}.json", rep)

    summary = {
        "profile": "soak_bounded",
        "seeds": SEEDS,
        "results": results,
        "failure_signatures": {k: len(v) for k, v in clusters.items()},
        "status": "PASS" if not failures else "FAIL",
        "note": "No LLM calls; passing screenshots not sent anywhere.",
    }
    write_summary(run_dir, summary)
    write_json(run_dir / "soak_results.json", results)
    # Gate: all seeds must pass both slices for this bounded soak.
    assert not failures, json.dumps(summary, indent=2)
