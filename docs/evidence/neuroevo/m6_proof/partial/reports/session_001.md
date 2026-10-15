# AI training session report — 2026-10-14 22:51 — run proving

Verdict: TOO EARLY TO SAY   (4 generations so far; the verdict needs 10)

This session: generations 0..3 (4 new), 152 games (8 controls), 142.0 simulated hours in 0.68 wall hours (20x real time per worker), 14 workers.
Champion: none yet (no candidate has beaten the heuristic AI on held-out games). The best genome of each generation is kept under best_by_gen/.
Collective loss: controls 0.00 of worlds (catastrophe level C0, outbreak scale 1.0); candidates' own loss rates are in the held-out figures above.

| generation | best advantage | mean advantage | best raw fitness | control loss rate | commands per tick | rejected % | sigma (mean) | lineage of best |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0 | -49.2 | -63.2 | 1005.0 | 0.00 | 1.65 | 0.81 | 0.105 | imitation |
| 1 | -53.5 | -69.2 | 1007.2 | 0.00 | 1.64 | 1.71 | 0.105 | imitation |
| 2 | -39.2 | -54.1 | 1016.0 | 0.00 | 1.80 | 1.23 | 0.106 | imitation |
| 3 | -69.7 | -75.0 | 994.7 | 0.00 | 1.98 | 1.35 | 0.104 | random |

Behaviour grid: 1/18 cells filled (military share / expansion / cooperation); best per cell:
  - cell 0,0,0: raw fitness 1016.0 (imitation, generation 2)

Decision statistics (last generation, all candidate games): heads used: H1 10%, H2 10%, H3 2%, H4 10%, H5 19%, H6 7%, H7 0%, H8 37%, H9 6%; commands per tick 1.98; rejected 1.35%.
Imitation lineage: parent advantage n/a against the random lineage's -66.3 (means over this session); adoptions: 0.

Disk: 0.08 GB in the run (cap 20); last checkpoint generation 4.
To continue: double-click "Train AI.bat" (it resumes this run). To test the champion: "Evaluate Best AI.bat".
Notes: stopped by the STOP file. 10 games were voided (crash twice, stall or wall-cap); details in games/*/repro.json and the generation events.
