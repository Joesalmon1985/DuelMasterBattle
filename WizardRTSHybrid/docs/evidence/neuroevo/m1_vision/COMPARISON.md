# T1.1 before and after: heuristic AIs find enemies only through their visibility memory

Tournament `run_civilisation_tournament.py` (3 `plus` vs 3 `baseline` seats, legs A and B, standard map, `war` mode). Directories:

* `before/`, `long120/legacy/`: commit `4b67f55c`. Old rule: every home capital is public, and anything within 32 tiles of an own building or armed unit is known.
* `after_final/`, `long120/final/`: the committed rule. The AI knows only what `visibility.py` shows it (sight, scouts, spies). With an army ready and nothing known, one detachment scouts: `ai.recon_step` attack-moves to the nearest part of a fixed 5 x 3 map grid the faction has not seen. This reconnaissance is new AI behaviour added to compensate for the removed free knowledge.
* `after_sight/`, `after_wide/`, `long120/sight/`, `long120/wide/`: intermediate experiments (strict sight without reconnaissance; sight plus the old 32-tile rule), kept as evidence for the choice. `wide` was rejected: it gives the AI far more awareness than a neural controller will have.

| run | `plus` VP | `baseline` VP | wins by VP (plus : baseline) | `baseline` building kills | `plus` building losses |
| --- | ---: | ---: | --- | ---: | ---: |
| 40 min before (4 games) | 7.0 | 6.17 | 3.5 : 0.5 | 1.42 | 1.42 |
| 40 min final (4 games) | 7.0 | 6.17 | 3.5 : 0.5 | 1.83 | 1.83 |
| 120 min before (2 games) | 4.67 | 11.83 | 0 : 2 | 68.3 | 50.2 |
| 120 min final (2 games) | 3.67 | 11.83 | 0 : 2 | 110.2 | 105.7 |

* **Behaviour:** at 40 minutes the two policies score exactly as before. At 120 minutes wars still happen and `baseline` out-scores `plus` both before and after (a pre-existing weakness of `plus` at long horizons, important context for the neural control games); the final run is a harsher war than the old one (two games per row: treat differences as noise-level). First attacks come about ten minutes later than before: the 22-minute behaviour test now needs 36 game minutes (`test_ai_behaviour.py`).
* **Throughput:** `bench_sim --minutes 15`: 75.5x realtime before, 75.9-76.4x after the visibility change; peak memory 66 -> 64 MB.
* **State hashes:** the showcase/baseline-AI baseline diverges from minute 12 (intended). All baselines were re-recorded as `docs/perf/hash_baseline_v5*.json` after the final AI.
