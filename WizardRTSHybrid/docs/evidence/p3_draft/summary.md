# P3 drafting v2: first tournament and probes (13 Oct 2026)

Command: `python3 scripts/run_civilisation_tournament.py --draft --mode war --minutes 90 --seeds 507 11 --jobs 2` (mirrored plus/baseline legs, cards v2 = 121 generated cards, era-start seven-round ring draft, era bar = max(8, leader VP + 4), debounce 60 s). Failures: 0 in 4 games.

| metric (mean per faction, n=12 each) | plus | baseline |
| --- | --- | --- |
| vp | 6.83 | 5.92 |
| settlements | 6.83 | 5.92 |
| cards | 12.75 | 12.33 |
| buildings | 80.0 | 55.33 |
| army | 3.67 | 2.75 |
| units_produced | 14.25 | 12.42 |
| unit_kills | 4.83 | 3.33 |
| building_losses | 0.33 | 1.5 |
| founded | 5.83 | 5.33 |
| unrest | 0.86 | 0.78 |

VP 95% CI: plus +/-1.02, baseline +/-1.44. Games won by VP: plus 2.0, baseline 2.0 (4 games, too few to separate).

Findings
* Every game reached the Historic era by VP (minute ~31-40) and **none reached Modern in 90 minutes**: after the first transition the bar is leader VP + 4 (12+), and the AIs found settlements but made very little war (building kills 0.3-1.5 per faction), so VP stalls at 6-10. The plan's target (all four eras reachable by VP in natural play in at least 60% of runs) is **not met**; the era bar and AI aggression are the levers for the P12 study.
* Cards-used rate (entities of drafted cards that were built or produced at least once, `scripts/draft_probe.py`, plus AIs, 60 min, seed 507): **35% before and 67% after** `ai_plus.card_step` (build what the drafted cards unlock). Unused entities are mostly other tribes' buildings (dealt as trade-offs/denial), units without a producer decision, and late chains.
* Cards: 121 generated cards (94 unlock one entity, 27 unlock two). Modern and Dystopian have only 6 cards between them (no Mindustry content is dealt yet), so later phases fill packs with undrafted older cards.
