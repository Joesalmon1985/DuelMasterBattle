# M6 proving run: PARTIAL, paused, NOT judged

**The 8-hour acceptance run did not complete and was not judged.** `scripts/judge_proof.py` has not been run. This folder is the evidence of a paused run, not a result.

Run `proving` (config `proving60`: 60-minute games, population 16, 2 seeds per generation, 14 workers, catastrophe level C0, imitation fraction 0.25), started 14 Oct 2026 22:11 and stopped by the owner's pause request at 22:51 (40 minutes, 0.68 wall hours) with `train_ai.py stop --run proving` (graceful). The trainer exited cleanly (STATUS `stopped`, no worker processes left, checkpoint at generation 4, session report written).

Where the large files are (not copied here): `C:\Users\joesa\dmb_runs\neuro\proving\` (`code/` frozen code copy, `games/`, `checkpoints/`, `theta/`, `best_by_gen/`, `imitation/`). 0.08 GB in total. Do not delete it: resuming needs it.

## What the run showed (as it actually was)

| generation | best advantage | mean advantage | parent advantage, random lineage | parent advantage, imitation lineage | notes |
| ---: | ---: | ---: | ---: | ---: | --- |
| 0 | -49.2 | -63.3 | -64.5 | -63.7 | 38 games, 518 s |
| 1 | -53.5 | -69.2 | -69.5 | -53.5 | 557 s |
| 2 | -39.2 | -54.1 | -58.0 | -45.0 | 549 s |
| 3 | -69.7 | -75.0 | -73.3 | (none) | **partial**: the stop request voided 10 not-yet-started games, so the imitation lineage had no children |

- Advantage is fitness minus the all-`plus` control game on the same seed and seat. **Every number is negative: the neural seats played worse than the heuristic AI by roughly 40-75 fitness points.** There is no upward trend yet in four generations (the verdict needs ten); generation-to-generation noise (about +-15) is as large as any change. The imitation lineage's parent was ahead of the random lineage's in generations 0-2 (-63.7/-53.5/-45.0 against -64.5/-69.5/-58.0) and improved over those three, which is encouraging but is three noisy points.
- No champion promoted (no candidate had a positive advantage, so no held-out evaluation ran). One behaviour-grid cell filled (0,0,0).
- Commands per tick 1.65-1.98, rejected 0.8-1.7 %, no crashes, no `repro.json`. Generation wall time 7-9 minutes (418 s for the partial one), 20x real time per worker.
- 142 simulated hours in 0.68 wall hours.
- Fitness is sparse: a seat's victory points equal its standing settlements, so fitness only differs between controllers once settlements are founded; the neural seats mostly sit at 1 VP, the heuristic AIs reach 4-7 in 60 minutes.
