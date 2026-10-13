# Neural drafting module v1: imitation of the heuristic drafter (13 Oct 2026)

Stage 1 of the neural programme (plan v2 9.3 step 2) for the drafting module only. Nothing here is reinforcement learning: the network is trained to *copy* the plus AI's drafter, and the test asks whether copying costs anything in games.

## Method
* Data: `scripts/draft_collect.py`, 36 games of 45 game minutes (seeds 1000-1035), six plus AIs, generated cards v2; every heuristic pick recorded with a 22-number faction state vector and a 28-number description of every card in the pack (`wizard_rts/learn/draft_module.py`). 32 games were complete when the model was trained (1211 train picks, 403 held-out picks).
* Model: a card scorer, a NumPy MLP (3649 parameters, hidden [48, 24]) applied to every card of the pack with the same state vector (the pack order cannot matter: tested). Softmax cross-entropy over the pack, Adam, 60 epochs, split **by game** (whole seeds held out).
* Inference needs only NumPy (`DraftScorer.load`), as the plan requires for simulation workers. Weights: `draft_scorer_v1.json` (76 KB).

## Imitation accuracy (held-out games the network never saw)
| | top-1 agreement with the heuristic |
| --- | ---: |
| random choice from the pack | 0.253 |
| always the first offer | 0.325 |
| network, training games | 0.96 |
| **network, held-out games** | **0.886** (era 0: 0.912, n=283; era 1: 0.825, n=120) |

## Module-swap test in games (`scripts/draft_swap_eval.py`, held-out seeds 3000-3011)
Same seed twice: all factions heuristic, and one faction (rotating with the seed) drafting with the learned scorer. Outcome metrics only (never training reward).

Module swap, 12 paired seeds, 45 game minutes, one faction (rotating by seed) drafts with the learned scorer.

| metric | heuristic mean | neural mean | paired diff (neural - heuristic) | 95% bootstrap CI |
| --- | --- | --- | --- | --- |
| vp | 5.42 | 5.50 | +0.08 | [+0.00, +0.25] |
| buildings | 64.92 | 64.58 | -0.33 | [-1.92, +1.17] |
| cards | 8.58 | 8.42 | -0.17 | [-0.50, +0.00] |
| used_rate | 0.65 | 0.65 | +0.00 | [-0.04, +0.05] |

Raw games: `draft_swap_games.jsonl`.

## Reading
* The learned drafter is **statistically indistinguishable from the heuristic** it imitates (all four paired CIs include or touch 0), so the stage-1 gate "no worse than the heuristic module on held-out seeds" is met for drafting. That is the expected result of behaviour cloning of a deterministic rule from the same observations; it is **not** evidence that the network plays better.
* Limits: one faction per game (12 paired games, 12 faction instances), 45-minute horizon (first draft phase only), the heuristic itself is a hand-weighted score, and games diverge chaotically after the first different pick, so differences are noisy. Era 1 accuracy is lower because fewer samples exist.
* Next (not done): RL on realised use (branching rollouts from saved states), then the other modules (economy, military, trade, catastrophe, industrialisation) and the coordinator. All need a faster simulator and more cores than this laptop (plan section 9.6).
