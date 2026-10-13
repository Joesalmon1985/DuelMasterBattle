# Era-bar study (draft v2, plus AIs, war mode)

| configuration | games | eras reached (final era per game) | transition minutes (VP / stall guard) | early-ending phases (before round 7) | leftover cards awarded / lost per transition | mean top VP at end |
| --- | ---: | --- | --- | --- | --- | --- |
| A_end8_step2_all-plus | 2 | [1, 1] | 26, 33 | 0 | 0/0 over 0 | 8.0 |
| B_end10_step3_all-plus | 2 | [1, 1] | 75s, 75s | 0 | 0/0 over 0 | 8.5 |
| C_end8_step4_mirror | 4 | [1, 1, 1, 1] | 26, 30, 28, 24 | 0 | 0/0 over 0 | 9.2 |
| D_end8_step4_metal_all-plus | 3 | [1, 1, 1] | 26, 29, 33 | 3 | 0/0 over 3 | 9.0 |
| E_end8_step4_parity_all-plus | 2 | [1, 1] | 26, 33 | 2 | 3/15 over 2 | 9.5 |


Transition minutes suffixed `s` ended by the 75-minute stall guard. The `early-ending` and leftover columns come from recorded events and are lower bounds (see the addendum).

## Reading (first pass, 2-4 games per configuration: indicative only)
* **Bar 8 (A, C)** ends the first era at minute 24-33 in every game, before round 7 of the draft (the plan wants 20-80% of eras to end early, so 100% is at the top of the range): the leaders found 8 settlements by minute ~30.
* **Bar 10 (B)** is never reached by settlement VP (leaders peak at 9): the era only ends at the 75-minute stall guard. Settlement VP saturates at 8-9 because rivals and water use up the space.
* **After the first transition no game reached the next era** in 90-100 minutes: the next bar is leader VP + step (10 or 12), reachable only by conquest, and the plus AIs rarely attack (0.3-1.5 building kills per faction per 90 minutes). The target "all four eras reachable by VP in natural play in 60% of runs" is therefore **not met**; AI aggression, not the threshold, is the binding constraint.
* Candidate for the next study: first bar 9 (between the two observed regimes) with step 2, 10+ seeds, and an AI that builds and uses an army.

## Addendum: the same run after the AI valued the metal chain (D, 3 seeds, 90 min, all-plus)
Armies appear (Green 20, Orange 11, Red 20 units in different games; 24-34 units produced by the busiest factions against about 14 before) but there are still **no attacks and no building kills**: the transition minutes (26, 29, 33) are unchanged and no game reached era 2. The AIs raise armies and then do not use them: the target value rule (squad strength at least 1.4x the defence near the target) rejects every capital. The tournament recorder dropped the dict fields of `draft_leftovers` (awarded/lost), so the leftover counts in the table are zero by omission; the recorder now keeps dicts, so the next run will report them.

## Addendum 2: attack at parity (E, seeds 11 and 507, 90 min, all-plus; `attack_ratio` 1.0 instead of 1.4)
Green attacked three times in seed 11 (20 units), but there were still **no building kills and no destroyed settlement**, and no game reached era 2 (transitions at minutes 26 and 33). The leftover rule did run in a natural game for the first time: at minute 26 (seed 11, draft round 5 of 7) Purple (10 VP) was awarded the two cards left in the pack it held and Red, Blue, Green, Yellow and Orange (below 8 VP at that instant) lost their two cards each; at minute 33 (seed 507) Red (9 VP) received one card and five factions lost one each. So early era ends distribute a few cards to the leader only, as specified, and the cost to the others is small (one or two late, much-passed cards).
Conclusion for the study so far: the AIs' armies do not convert into conquests, whatever the ratio; the next lever is target choice and squad behaviour (the army reaches a capital's militia and turns back), not the era bar.
