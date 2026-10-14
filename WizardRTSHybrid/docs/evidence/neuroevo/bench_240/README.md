# 240-minute benchmark games (14 Oct 2026, Windows PC, plan section 11)

Two headless six-faction games, `campaign` profile, six `plus` AIs, drafting v2, diplomacy on, cooperative nest policy, default outbreak cadence, standard map; one core each, run concurrently with each other and with other work. Script: `WizardRTSHybrid/scripts/bench_full_game.py --minutes 240 --seed <7|11> --out <dir>`. Machine: AMD Ryzen 7 5800X (8c/16t), 32 GB, Python 3.14.0, NumPy 2.4.0, no C compiler (pure-Python A*), no psutil (memory not measured).

| Game minute | seed 7: x real time | seed 7: wall s so far | seed 7: buildings / units / factions | seed 11: x real time | seed 11: wall s so far | seed 11: buildings / units / factions |
| ---: | ---: | ---: | --- | ---: | ---: | --- |
| 20 | 44.9 | 21 | 255 / 10 / 6 | 46.7 | 20 | 252 / 10 / 6 |
| 40 | 19.7 | 66 | 376 / 9 / 7 | 18.7 | 68 | 403 / 7 / 6 |
| 60 | 19.1 | 129 | 402 / 19 / 7 | 14.6 | 145 | 465 / 15 / 6 |
| 90 | 14.5 | 238 | 452 / 27 / 9 | 14.9 | 267 | 505 / 30 / 6 |
| 120 | 13.6 | 361 | 472 / 27 / 9 | 12.2 | 400 | 559 / 28 / 7 |
| 150 | 13.3 | 492 | 490 / 28 / 9 | 11.2 | 555 | 572 / 41 / 7 |
| 180 | 10.8 | 652 | 525 / 47 / 9 | 10.0 | 726 | 574 / 40 / 7 |
| 210 | 10.5 | 825 | 529 / 49 / 9 | 9.3 | 912 | 580 / 47 / 7 |
| 240 | 9.9 | 1003 | 534 / 37 / 9 | 8.6 | 1125 | 584 / 40 / 7 |

| | seed 7 | seed 11 |
| --- | --- | --- |
| Wall time for 240 game minutes (one core, shared machine) | **1003 s** (16.7 min, 14.4x average) | **1125 s** (18.8 min, 12.8x average) |
| End reason | horizon (no collective loss, no cycle completion) | horizon (no collective loss, no cycle completion) |
| Era first seen at minute (0 Prehistoric, 1 Historic, 2 Modern, 3 Dystopian) | {0: 5.0, 1: 75.0, 2: 150.0, 3: 225.0} | {0: 5.0, 1: 30.0, 2: 105.0, 3: 180.0} |
| Final VP | {'Red': 5, 'Blue': 4, 'Green': 6, 'Yellow': 5, 'Purple': 7, 'Orange': 5, 'Yellow-2': 1, 'Yellow-3': 1, 'Red-2': 1} | {'Red': 6, 'Blue': 3, 'Green': 5, 'Yellow': 7, 'Purple': 10, 'Orange': 10, 'Red-2': 1} |
| Sum of VP at minute 40 / 120 / 240 | 35 / 35 / 35 | 40 / 40 / 42 |
| Outbreaks (collective-loss counter) / cubes on the map at the end | 0 / 3 | 0 / 6 |
| Buildings / units at the end | 534 / 37 | 584 / 40 |
| Attack-move orders / unit hits over the game | 2183 / 1541 | 2973 / 2329 |
| Memory | not measured (no `psutil`; the Linux runs reported 64-73 MB peak RSS at 180 minutes) | |

Reading: throughput falls from about 45x in the first 20 minutes to about 10x after minute 160 as the world grows to 530-590 buildings; the mean over a whole game is **about 13-14x real time per core, 17-19 wall minutes per 240-minute game**. Both games ran concurrently with each other and with the session's other work, so an idle machine should be somewhat faster. **The VP race is essentially over by minute 40**: the summed VP changes by at most 2 over the remaining 200 minutes in both games (settlement VP saturates at 8-10 per faction; the heuristic AIs fight, with 2,000-3,000 attack-move orders, but rarely raze a settlement). An evolved controller that conquers would therefore find VP where the heuristics do not, which is the intended discriminator; but it also means a fitness based on VP alone would be flat among heuristic-like candidates after minute 40 (section 8.6).

Outbreaks: Both games: **0 outbreaks** in 240 minutes at the default cadence (one cube per 10 game minutes); cubes on the map stayed between 1 and 6 because the factions' clinics cured them (the clinic is a foundation building that every faction gets). The 180-minute run of 13 Oct (reported) also had 0 outbreaks. **At cadence 1.0 the collective failure state is not reachable in a four-hour game with the current heuristic AIs**, so objective B of the brief would be vacuous during training unless the training cadence is raised; see section 8.5 and owner decision Q2. The opposite regime is documented in the P10 study (reported): at scale 0.12 every 90-minute game was lost by minute 42-64 even with clinics. The interesting regime is in between and must be measured at 240 minutes (M4 calibration).

Files: `seed7_progress.jsonl`, `seed11_progress.jsonl` (one row per 5 game minutes), `seed7_summary.json`, `seed11_summary.json` (end state, top-40 event counts, state hash). The audit scripts used for the plan's counts and profiles are in `../scripts/` (evidence copies; the roster-count logic becomes `scripts/freeze_content.py` in M0).
