"""G09 evidence honesty — manifest must match evaluation reports."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "godot_project" / "content" / "policies" / "manifest.json"
EVAL_DIR = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking" / "policy_evaluations"


def _family_distance(a: dict, b: dict) -> float:
    keys = set(a) | set(b)
    return max(abs(float(a.get(k, 0.0)) - float(b.get(k, 0.0))) for k in keys) if keys else 0.0


def test_heuristic_fallback_never_trained() -> None:
    if not MANIFEST.is_file():
        return
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest.get("heuristic_fallback", {}).get("trained") is False


def test_manifest_shares_match_eval_reports_when_present() -> None:
    """Fail closed when manifest action_family_share diverges from eval_*.json."""
    if not MANIFEST.is_file():
        return
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for policy in manifest.get("policies") or []:
        pid = str(policy.get("id") or "")
        if not pid:
            continue
        eval_path = EVAL_DIR / f"eval_{pid}.json"
        if not eval_path.is_file():
            # Incomplete library is allowed; missing eval while claiming COMPLETE is not.
            if str(manifest.get("status")) == "COMPLETE":
                raise AssertionError(f"COMPLETE manifest missing eval report for {pid}")
            continue
        entry = json.loads(eval_path.read_text(encoding="utf-8"))
        eval_share = (
            (entry.get("evaluation") or {}).get("action_family_share")
            or entry.get("action_family_share")
            or {}
        )
        man_share = (policy.get("evaluation_summary") or {}).get("action_family_share") or {}
        assert eval_share, f"{pid}: eval missing action_family_share"
        assert man_share, f"{pid}: manifest missing action_family_share"
        for key in set(eval_share) | set(man_share):
            assert abs(float(eval_share.get(key, 0.0)) - float(man_share.get(key, 0.0))) < 1e-9, (
                f"{pid}: manifest share {man_share} != eval share {eval_share}"
            )


def test_selected_policies_pairwise_diversity_when_complete() -> None:
    if not MANIFEST.is_file():
        return
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if str(manifest.get("status")) != "COMPLETE":
        return
    policies = list(manifest.get("policies") or [])
    assert len(policies) >= 3
    shares = []
    for policy in policies:
        share = (policy.get("evaluation_summary") or {}).get("action_family_share") or {}
        shares.append(share)
        art = ROOT / "godot_project" / str(policy.get("artifact") or "")
        assert art.is_file(), f"missing artifact {art}"
        payload = json.loads(art.read_text(encoding="utf-8"))
        assert payload.get("trained") is True
    for i, a in enumerate(shares):
        for j, b in enumerate(shares):
            if i >= j:
                continue
            dist = _family_distance(a, b)
            assert dist >= 0.10, f"policies {i},{j} diversity {dist} < 0.10"


def test_eval_seed_count_is_200_when_eval_present() -> None:
    if not EVAL_DIR.is_dir():
        return
    for path in EVAL_DIR.glob("eval_policy-*.json"):
        entry = json.loads(path.read_text(encoding="utf-8"))
        evaluation = entry.get("evaluation") or entry
        seed_count = evaluation.get("seed_count") or evaluation.get("seeds_evaluated")
        if seed_count is None and isinstance(evaluation.get("rows"), list):
            seed_count = len(evaluation["rows"])
        # Older incomplete reports may use small smokes; COMPLETE library requires 200.
        if MANIFEST.is_file():
            manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
            if str(manifest.get("status")) == "COMPLETE":
                assert int(seed_count or 0) >= 200, f"{path.name} seed_count={seed_count}"
