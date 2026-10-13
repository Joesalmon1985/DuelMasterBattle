# Era-bar study (draft v2, plus AIs, war mode)

| configuration | games | eras reached (final era per game) | transition minutes (VP / stall guard) | early-ending phases (before round 7) | leftover cards awarded / lost per transition | mean top VP at end |
| --- | ---: | --- | --- | --- | --- | --- |
| A_end8_step2_all-plus | 2 | [1, 1] | 26, 33 | 0 | 0/0 over 0 | 8.0 |
| B_end10_step3_all-plus | 2 | [1, 1] | 75s, 75s | 0 | 0/0 over 0 | 8.5 |
| C_end8_step4_mirror | 4 | [1, 1, 1, 1] | 26, 30, 28, 24 | 0 | 0/0 over 0 | 9.2 |

Transition minutes suffixed `s` ended by the 75-minute stall guard. `events.jsonl` keeps only the tournament's major events, so leftover counts are lower bounds when `draft_leftovers` is not in that list.

## Reading (first pass, 2-4 games per configuration: indicative only)
* **Bar 8 (A, C)** ends the first era at minute 24-33 in every game, before round 7 of the draft (the plan wants 20-80% of eras to end early, so 100% is at the top of the range): the leaders found 8 settlements by minute ~30.
* **Bar 10 (B)** is never reached by settlement VP (leaders peak at 9): the era only ends at the 75-minute stall guard. Settlement VP saturates at 8-9 because rivals and water use up the space.
* **After the first transition no game reached the next era** in 90-100 minutes: the next bar is leader VP + step (10 or 12), reachable only by conquest, and the plus AIs rarely attack (0.3-1.5 building kills per faction per 90 minutes). The target "all four eras reachable by VP in natural play in 60% of runs" is therefore **not met**; AI aggression, not the threshold, is the binding constraint.
* Candidate for the next study: first bar 9 (between the two observed regimes) with step 2, 10+ seeds, and an AI that builds and uses an army.
