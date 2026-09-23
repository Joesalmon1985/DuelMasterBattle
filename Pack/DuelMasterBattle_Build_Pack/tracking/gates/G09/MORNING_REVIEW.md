# G09 Morning Review — AUTO_FAILED — fewer_than_three_qualified_policies (0)

**Gate:** G09 — Trained faction leadership  
**Status:** `AUTO_FAILED — fewer_than_three_qualified_policies (0)`  
**Human acceptance:** PENDING — do **not** invent `PASS` or `accepted_by`  
**Overnight policy:** continuation past G09 only when status is AUTO_READY_FOR_OWNER_REVIEW; PARTIAL/AUTO_FAILED still leaves infrastructure for independent G10 work

## Candidate

- Branch: `phase/g06-g12-autoqa`
- Evaluation dir: `tracking/policy_evaluations/`
- Policy manifest: `godot_project/content/policies/manifest.json`
- Auto report: `tracking/gates/G09/auto/result.json`
- Launch / inspect: `python3 training/evaluate.py --seed-count 200 --max-steps 30`
- Decision traces: `tracking/gates/G09/decision_traces/`

## Honesty

- Pure-numpy local training (torch not installed). Weights are **real trained artifacts** when `trained: true`, not relabelled heuristics.
- Heuristic fallback remains legal and required on schema/timeout/exception.
- **Heuristic clones are never labelled trained.**
- Incomplete batches stopped by local compute budget are **not** claimed as promotion.

## Qualification

| Metric | Value |
|---|---|
| Qualified trained policies | 0 / 3 |
| Manifest status | NONE_QUALIFIED |
| Blockers | ['fewer_than_three_qualified_policies (0)'] |

## Automated evidence

| Suite | Path |
|---|---|
| Eval reports | `none yet` |
| Action samples | `Pack/DuelMasterBattle_Build_Pack/tracking/gates/G09/decision_traces/action_samples.json` |
| Fallback demo | `Pack/DuelMasterBattle_Build_Pack/tracking/gates/G09/decision_traces/fallback_demo.json` |
| Policy identity | `Pack/DuelMasterBattle_Build_Pack/tracking/gates/G09/decision_traces/policy_identity.json` |

## Owner playtest focus

1. Read the paired evaluation summary (baseline vs candidates, 200 held-out seeds).
2. Inspect build/trade/war samples under `decision_traces/`.
3. Confirm policy identity after save/load (`policy_identity.json`).
4. Confirm forced inference failure → legal heuristic fallback without a free extra action.

## Known limits / blockers

- fewer_than_three_qualified_policies (0)

G05–G08 remain without human PASS; do not invent acceptance.
