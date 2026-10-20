# AI training session report — 2026-10-19 21:15 — run 20261019-1542

Verdict: TOO EARLY TO SAY   (2 generations so far; the verdict needs 10)

This session: generations 0..1 (2 new), 116 games (8 controls), 455.2 simulated hours in 5.54 wall hours (7x real time per worker), 14 workers.
Champion: none yet (no candidate has beaten the heuristic AI on held-out games). The best genome of each generation is kept under best_by_gen/.
Collective loss: controls 0.00 of worlds (catastrophe level C0, outbreak scale 1.0); candidates' own loss rates are in the held-out figures above.

| generation | best advantage | mean advantage | best raw fitness | control loss rate | commands per tick | rejected % | sigma (mean) | lineage of best |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0 | -55.7 | -205.2 | 1013.0 | 0.00 | 1.77 | 1.89 | 0.098 | random |
| 1 | -42.7 | -386.8 | 1019.5 | 0.00 | 1.49 | 1.74 | 0.103 | random |

Behaviour grid: 2/18 cells filled (military share / expansion / cooperation); best per cell:
  - cell 0,0,0: raw fitness 1013.0 (imitation, generation 0)
  - cell 0,1,0: raw fitness 1019.5 (imitation, generation 1)

Decision statistics (last generation, all candidate games): heads used: H1 37%, H2 8%, H3 5%, H4 12%, H5 3%, H6 6%, H7 0%, H8 23%, H9 6%; commands per tick 1.49; rejected 1.74%.
Imitation lineage: parent advantage -73.0 against the random lineage's -457.7 (means over this session); adoptions: 0.

Disk: 0.07 GB in the run (cap 20); last checkpoint generation 2.
To continue: double-click "Train AI.bat" (it resumes this run). To test the champion: "Evaluate Best AI.bat".
Notes: time budget reached (7.0 h; the next generation would have overrun it).
