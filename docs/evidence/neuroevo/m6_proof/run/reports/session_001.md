# AI training session report — 2026-10-15 13:37 — run proving

Verdict: FLAT   (best advantage -33.2 over the last 5 generations against -28.7 over the 5 before (-4.6))

This session: generations 0..22 (23 new), 942 games (46 controls), 940.0 simulated hours in 4.09 wall hours (18x real time per worker), 14 workers.
Champion: none yet (no candidate has beaten the heuristic AI on held-out games). The best genome of each generation is kept under best_by_gen/.
Collective loss: controls 0.00 of worlds (catastrophe level C0, outbreak scale 1.0); candidates' own loss rates are in the held-out figures above.

| generation | best advantage | mean advantage | best raw fitness | control loss rate | commands per tick | rejected % | sigma (mean) | lineage of best |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0 | -25.8 | -49.2 | 1028.3 | 0.00 | 2.29 | 1.65 | 0.105 | imitation |
| 1 | -39.2 | -56.7 | 1021.5 | 0.00 | 2.10 | 1.49 | 0.105 | imitation |
| 2 | -30.3 | -44.5 | 1024.8 | 0.00 | 2.12 | 2.54 | 0.106 | imitation |
| 3 | -38.2 | -63.2 | 1026.2 | 0.00 | 2.34 | 1.42 | 0.105 | random |
| 4 | -43.8 | -61.3 | 1026.5 | 0.00 | 2.44 | 0.86 | 0.110 | imitation |
| 5 | -21.5 | -32.2 | 1028.3 | 0.00 | 2.39 | 0.69 | 0.108 | random |
| 6 | -45.7 | -60.3 | 1023.2 | 0.00 | 2.15 | 1.12 | 0.106 | imitation |
| 7 | -40.0 | -48.4 | 1019.5 | 0.00 | 2.28 | 4.43 | 0.108 | imitation |
| 8 | -37.0 | -51.7 | 1023.7 | 0.00 | 2.29 | 4.67 | 0.108 | imitation |
| 9 | -36.2 | -44.1 | 1024.0 | 0.00 | 2.42 | 2.14 | 0.114 | random |
| 10 | -25.3 | -38.8 | 1032.5 | 0.00 | 2.35 | 1.55 | 0.115 | imitation |
| 11 | -38.0 | -48.0 | 1020.3 | 0.00 | 2.53 | 2.28 | 0.115 | random |
| 12 | -19.0 | -30.4 | 1030.3 | 0.00 | 2.42 | 3.22 | 0.116 | random |
| 13 | -26.5 | -45.6 | 1029.8 | 0.00 | 2.25 | 0.46 | 0.113 | random |
| 14 | -17.7 | -41.6 | 1036.3 | 0.00 | 2.18 | 2.31 | 0.114 | imitation |
| 15 | -39.2 | -51.6 | 1026.3 | 0.00 | 2.60 | 3.06 | 0.115 | imitation |
| 16 | -36.3 | -48.9 | 1024.7 | 0.00 | 2.45 | 2.68 | 0.115 | imitation |
| 17 | -23.7 | -38.9 | 1037.5 | 0.00 | 2.57 | 3.28 | 0.115 | random |
| 18 | -35.7 | -48.1 | 1020.0 | 0.00 | 2.61 | 2.82 | 0.116 | imitation |
| 19 | -39.8 | -54.1 | 1022.5 | 0.00 | 2.41 | 2.93 | 0.113 | random |
| 20 | -36.3 | -46.8 | 1021.0 | 0.00 | 2.44 | 2.27 | 0.111 | random |
| 21 | -18.8 | -34.0 | 1033.7 | 0.00 | 2.80 | 1.75 | 0.110 | random |
| 22 | -35.5 | -48.4 | 1027.2 | 0.00 | 2.42 | 1.78 | 0.108 | imitation |

Behaviour grid: 2/18 cells filled (military share / expansion / cooperation); best per cell:
  - cell 0,0,0: raw fitness 1025.3 (imitation, generation 21)
  - cell 0,1,0: raw fitness 1037.5 (random, generation 17)

Decision statistics (last generation, all candidate games): heads used: H1 30%, H2 6%, H3 8%, H4 10%, H5 13%, H6 5%, H7 1%, H8 21%, H9 6%; commands per tick 2.42; rejected 1.78%.
Imitation lineage: parent advantage -39.3 against the random lineage's -44.3 (means over this session); adoptions: 0.

Disk: 0.10 GB in the run (cap 20); last checkpoint generation 23.
To continue: double-click "Train AI.bat" (it resumes this run). To test the champion: "Evaluate Best AI.bat".
Notes: stopped by the STOP file. 2 games were voided (crash twice, stall or wall-cap); details in games/*/repro.json and the generation events.
