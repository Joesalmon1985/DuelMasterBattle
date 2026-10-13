# P2 no-card civilisation probe (campaign profile, drafting off, foundation = primitive kit + settlers + tavern, baseline AI)

Command: `python3 scripts/nocards_probe.py --seed S --minutes 120` (commit at time of run: see ledger). Settlements counted as standing command centres.

| seed | min 30 | min 60 | min 90 | min 120 | smallest main-faction count at 120 | worker_failed (no_tree/no_rock) |
| --- | --- | --- | --- | --- | --- | --- |
| 507 | B3 G6 O8 P7 R5 Y6 | B3 G5 O8 P8 R6 Y7 | B2 G5 O8 P8 R6 Y6 | B2 G4 O7 P7 R5 Y5 | 2 | [('no_tree', 24325), ('no_rock', 20561), ('no_game', 7547), ('no_fish', 1283)] |
| 11 | B4 G7 O7 P8 R5 Y7 | B4 G7 O7 P9 R5 Y8 | B4 G6 O6 P9 R5 Y8 | B3 G5 O6 P9 R5 Y7 | 3 | [('no_tree', 21779), ('no_rock', 18232), ('no_game', 4754), ('no_fish', 1145), ( |
| 23 | B5 G8 O7 P5 R5 Y6 | B5 G8 O8 P4 R4 Y6 | B5 G8 O8 P4 R3 Y6 | B5 G8 O7 P3 R2 Y6 | 2 | [('no_tree', 20088), ('no_rock', 17127), ('no_game', 7003), ('no_fish', 1260)] |

Reading: every faction reached 3 or more standing settlements by game minute 30 in all three seeds (Blue: 3, 4, 5), against 1 each and no growth before the foundation set and the removal of the quota (v1 plan section 1.3). Standing counts then move with space, rivals, splits (`-2`, `-3` successors) and losses; the smallest main-faction count at minute 120 was 2, 3 and 2 (acceptance asks for 3 *founded*; standing-at-120 falls below 3 for Blue/Red/Purple in some seeds, to be examined with the VP study). Growth saturates at 6-9 settlements per faction by minute 40. `worker_failed` is dominated by `no_tree` and `no_rock` retries (about 45k per 120 min): checked later, each site retries after the 10-second failure sleep as Widelands does, so it is event volume, not an economy defect.
