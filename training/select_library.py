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
        # Provenance must come from the trained artifact itself, not caller guesses.
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        artifact_prov = payload.get("provenance") if isinstance(payload.get("provenance"), dict) else {}
        provenance = {**artifact_prov, **(cand.get("provenance") or {})}
        provenance.setdefault("weights_digest", payload.get("weights_digest"))
        provenance.setdefault("trained", bool(payload.get("trained")))
        provenance.setdefault("schema_hash", payload.get("schema_hash") or schema_hash())
        entry = {
            "id": cand["id"],
            "artifact": str(artifact.relative_to(ROOT)) if artifact.is_relative_to(ROOT) else str(artifact),
            "provenance": provenance,
            "evaluation": {k: v for k, v in report.items() if k != "rows"},
            "promotion": promo,
        }
        (EVAL_DIR / f"eval_{cand['id']}.json").write_text(json.dumps(entry, indent=2) + "\n", encoding="utf-8")
        if promo["promoted"] and report.get("artifact"):
            # Require genuinely trained provenance mark on the artifact file.
            if not payload.get("trained"):
                entry["promotion"]["promoted"] = False
                entry["promotion"]["reasons"] = list(promo["reasons"]) + ["artifact_not_marked_trained"]
                rejected.append(entry)
                continue
            if payload.get("weights_digest") and artifact_prov.get("init_digest"):
                if payload.get("weights_digest") == artifact_prov.get("init_digest"):
                    entry["promotion"]["promoted"] = False
                    entry["promotion"]["reasons"] = list(promo.get("reasons") or []) + [
                        "weights_unchanged_from_init"
                    ]
                    rejected.append(entry)
                    continue
            qualified.append(entry)
        else:
            rejected.append(entry)

    # Diversity: ≥10pp difference vs every already-selected policy (C14).
    # Prefer candidates that maximise pairwise distance when multiple qualify.
    selected: list[dict[str, Any]] = []
    remaining = list(qualified)
    while remaining and len(selected) < 3:
        best = None
        best_score = -1.0
        for entry in remaining:
            share = entry["evaluation"]["action_family_share"]
            if not selected:
                best = entry
                best_score = 1.0
                break
            dists = [
                _family_distance(share, s["evaluation"]["action_family_share"]) for s in selected
            ]
            if min(dists) < 0.10:
                continue
            score = min(dists)
            if score > best_score:
                best = entry
                best_score = score
        if best is None:
            # Record remaining as diversity rejects.
            for entry in remaining:
                fail = dict(entry)
                fail["diversity_ok"] = False
                fail["reason"] = "diversity_below_0.10_vs_selected"
                rejected.append(fail)
            break
        chosen = dict(best)
        chosen["diversity_ok"] = True
        if selected:
            chosen["pairwise_diversity"] = {
                s["id"]: _family_distance(
                    chosen["evaluation"]["action_family_share"],
                    s["evaluation"]["action_family_share"],
                )
                for s in selected
            }
        selected.append(chosen)
        remaining = [e for e in remaining if e["id"] != chosen["id"]]

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
        artifact = ROOT / path
        provenance: dict[str, Any] = {"cli": item}
        if artifact.is_file():
            try:
                payload = json.loads(artifact.read_text(encoding="utf-8"))
                if isinstance(payload.get("provenance"), dict):
                    provenance = {**payload["provenance"], **provenance}
            except json.JSONDecodeError:
                pass
        candidates.append({"id": pid, "artifact": str(artifact), "provenance": provenance})
    if not candidates:
        # Default overnight candidates if present.
        for name in (
            "imitation_build",
            "imitation_trade",
            "imitation_war",
            "imitation_generalist",
            "actor_critic_v1",
            "imitation_v1",
            "imitation_v2",
            "imitation_v3",
        ):
            path = CHECKPOINTS / f"{name}.json"
            if path.is_file():
                provenance = {"checkpoint": name}
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(payload.get("provenance"), dict):
                        provenance = {**payload["provenance"], **provenance}
                except json.JSONDecodeError:
                    pass
                candidates.append(
                    {
                        "id": name.replace("_", "-"),
                        "artifact": str(path),
                        "provenance": provenance,
                    }
                )
    manifest = select_library(candidates=candidates, seed_count=args.seed_count, max_steps=args.max_steps)
    print(json.dumps({"status": manifest["status"], "qualified": manifest["qualified_count"]}))
    return 0 if manifest["qualified_count"] >= 3 else 2


if __name__ == "__main__":
    raise SystemExit(main())
