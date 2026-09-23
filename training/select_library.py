"""Select up to three qualified distinct leadership policies (C14 / T149).

Does NOT invent trained duplicates. If fewer than three qualify, documents the
gap honestly and never relabels heuristic clones as trained leadership.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from training.evaluate import evaluate_policy, paired_promotion_check
from training.collect import PROMOTION_SEEDS
from training.environment import schema_hash

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking" / "policy_evaluations"
POLICIES_DIR = ROOT / "godot_project" / "content" / "policies"
CHECKPOINTS = ROOT / "training" / "checkpoints"


def _family_distance(a: dict[str, float], b: dict[str, float]) -> float:
    keys = set(a) | set(b)
    return max(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in keys) if keys else 0.0


def select_library(
    *,
    candidates: list[dict[str, Any]],
    seed_count: int = 200,
    max_steps: int = 40,
) -> dict[str, Any]:
    seeds = PROMOTION_SEEDS[:seed_count]
    baseline = evaluate_policy(
        policy_id="heuristic",
        artifact=None,
        seeds=seeds,
        max_steps=max_steps,
        label="heuristic_baseline",
    )
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    (EVAL_DIR / "library_baseline.json").write_text(
        json.dumps({k: v for k, v in baseline.items() if k != "rows"}, indent=2) + "\n",
        encoding="utf-8",
    )

    qualified: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for cand in candidates:
        artifact = Path(cand["artifact"])
        if not artifact.is_file():
            rejected.append({**cand, "reason": "missing_artifact"})
            continue
        report = evaluate_policy(
            policy_id=str(cand["id"]),
            artifact=artifact,
            seeds=seeds,
            max_steps=max_steps,
            label=str(cand["id"]),
        )
        promo = paired_promotion_check(baseline, report)
        entry = {
            "id": cand["id"],
            "artifact": str(artifact.relative_to(ROOT)) if artifact.is_relative_to(ROOT) else str(artifact),
            "provenance": cand.get("provenance") or {},
            "evaluation": {k: v for k, v in report.items() if k != "rows"},
            "promotion": promo,
        }
        (EVAL_DIR / f"eval_{cand['id']}.json").write_text(json.dumps(entry, indent=2) + "\n", encoding="utf-8")
        if promo["promoted"] and report.get("artifact"):
            # Require genuinely trained provenance mark on the artifact file.
            payload = json.loads(artifact.read_text(encoding="utf-8"))
            if not payload.get("trained"):
                entry["promotion"]["promoted"] = False
                entry["promotion"]["reasons"] = list(promo["reasons"]) + ["artifact_not_marked_trained"]
                rejected.append(entry)
                continue
            qualified.append(entry)
        else:
            rejected.append(entry)

    # Diversity: ≥10pp difference in one action-family share (C14).
    selected: list[dict[str, Any]] = []
    for entry in qualified:
        share = entry["evaluation"]["action_family_share"]
        if not selected:
            selected.append(entry)
            continue
        if any(_family_distance(share, s["evaluation"]["action_family_share"]) >= 0.10 for s in selected):
            selected.append(entry)
        elif len(selected) < 3:
            # Keep as alternate if diversity not met — do not fake diversity.
            entry = dict(entry)
            entry["diversity_ok"] = False
            # Only add if we still need slots AND competence holds; mark diversity fail.
            if len([s for s in selected if s.get("diversity_ok", True)]) < 3:
                # Prefer not adding non-diverse as "accepted library" members.
                pass
        if len(selected) >= 3:
            break

    # Rebuild selection with explicit diversity gate.
    selected = []
    for entry in qualified:
        share = entry["evaluation"]["action_family_share"]
        diverse = True
        if selected:
            diverse = any(
                _family_distance(share, s["evaluation"]["action_family_share"]) >= 0.10 for s in selected
            )
        if not selected or diverse:
            entry = dict(entry)
            entry["diversity_ok"] = True
            selected.append(entry)
        if len(selected) >= 3:
            break

    POLICIES_DIR.mkdir(parents=True, exist_ok=True)
    # Copy accepted artifacts into content/policies (inference-only).
    library_policies = []
    for entry in selected[:3]:
        src = ROOT / entry["artifact"] if not Path(entry["artifact"]).is_absolute() else Path(entry["artifact"])
        dest = POLICIES_DIR / f"{entry['id']}.json"
        shutil.copy2(src, dest)
        library_policies.append(
            {
                "id": entry["id"],
                "artifact": f"content/policies/{entry['id']}.json",
                "weights_digest": json.loads(dest.read_text(encoding="utf-8")).get("weights_digest"),
                "schema_hash": schema_hash(),
                "trained": True,
                "provenance": entry.get("provenance"),
                "evaluation_summary": {
                    "wins_10vp": entry["evaluation"]["wins_10vp"],
                    "catastrophe_count": entry["evaluation"]["catastrophe_count"],
                    "action_family_share": entry["evaluation"]["action_family_share"],
                },
                "kind": "trained_neural",
            }
        )

    # Always retain heuristic as legal fallback — never labelled trained.
    manifest = {
        "schema_hash": schema_hash(),
        "heuristic_fallback": {"id": "heuristic", "kind": "heuristic", "trained": False},
        "policies": library_policies,
        "qualified_count": len(library_policies),
        "required_count": 3,
        "rejected": [
            {"id": r.get("id"), "reasons": (r.get("promotion") or {}).get("reasons") or [r.get("reason")]}
            for r in rejected
        ],
        "status": (
            "COMPLETE"
            if len(library_policies) >= 3
            else ("PARTIAL" if library_policies else "NONE_QUALIFIED")
        ),
        "honesty": (
            "Heuristic clones are not listed as trained policies. "
            "Fewer than three qualified policies means G09 cannot claim a full library."
        ),
    }
    (POLICIES_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (EVAL_DIR / "library_selection.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-count", type=int, default=200)
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument(
        "--candidate",
        action="append",
        default=[],
        help="id=path pairs, e.g. policy_a=training/checkpoints/actor_critic_v1.json",
    )
    args = parser.parse_args(argv)
    candidates: list[dict[str, Any]] = []
    for item in args.candidate:
        pid, _, path = item.partition("=")
        candidates.append({"id": pid, "artifact": str(ROOT / path), "provenance": {"cli": item}})
    if not candidates:
        # Default overnight candidates if present.
        for name in ("actor_critic_v1", "imitation_v1", "actor_critic_v2", "imitation_v2", "imitation_v3"):
            path = CHECKPOINTS / f"{name}.json"
            if path.is_file():
                candidates.append(
                    {
                        "id": name.replace("_", "-"),
                        "artifact": str(path),
                        "provenance": {"checkpoint": name},
                    }
                )
    manifest = select_library(candidates=candidates, seed_count=args.seed_count, max_steps=args.max_steps)
    print(json.dumps({"status": manifest["status"], "qualified": manifest["qualified_count"]}))
    return 0 if manifest["qualified_count"] >= 3 else 2


if __name__ == "__main__":
    raise SystemExit(main())
