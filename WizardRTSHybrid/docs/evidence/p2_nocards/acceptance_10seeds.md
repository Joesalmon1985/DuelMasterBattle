# P2 acceptance run: no-card civilisation, 10 seeds x 120 game minutes (13 Oct 2026)

Command: `python3 scripts/run_civilisation_tournament.py --nocards --pairing all-plus --seeds 101..110 --minutes 120 --jobs 2` (campaign profile, drafting off, foundation set only, six **plus** AIs, standard map). Raw per-game files and series are in `~/dmb_runs/nocards_acc/`.

Acceptance asked (plan v2 P2): every faction founds at least 3 settlements, ledger balanced, no permanent stalls, in all 10 seeds.

| seed | final era (old VP-gain rule) | validation failures | founded by faction (R B G Y P O) | standing at 120 min |
| --- | ---: | ---: | --- | --- |
| 101 | 3 | 0 | [6, 2, 5, 6, 6, 5] | [7, 3, 6, 7, 7, 6] |
| 102 | 3 | 0 | [4, 1, 6, 5, 8, 5] | [5, 2, 7, 6, 9, 6] |
| 103 | 3 | 0 | [6, 5, 5, 4, 4, 7] | [7, 6, 6, 5, 5, 8] |
| 104 | 3 | 0 | [8, 1, 7, 6, 6, 6] | [9, 2, 8, 7, 7, 7] |
| 105 | 3 | 0 | [4, 1, 7, 4, 5, 5] | [5, 2, 8, 5, 6, 6] |
| 106 | 3 | 0 | [6, 2, 3, 5, 5, 6] | [7, 3, 4, 6, 6, 7] |
| 107 | 3 | 0 | [5, 3, 5, 4, 6, 6] | [6, 4, 6, 5, 7, 7] |
| 108 | 3 | 0 | [6, 0, 5, 5, 5, 8] | [7, 1, 6, 6, 6, 9] |
| 109 | 3 | 0 | [3, 1, 2, 6, 7, 8] | [4, 2, 3, 7, 8, 9] |
| 110 | 3 | 0 | [5, 1, 5, 6, 5, 6] | [6, 2, 6, 7, 6, 7] |

| faction | seeds with 3+ founded | seeds with 3+ standing at minute 120 | mean founded | worst |
| --- | ---: | ---: | ---: | ---: |
| Red | 10/10 | 10/10 | 5.3 | 3 |
| Blue | 2/10 | 4/10 | 1.7 | 0 |
| Green | 9/10 | 10/10 | 5.0 | 2 |
| Yellow | 10/10 | 10/10 | 5.1 | 4 |
| Purple | 10/10 | 10/10 | 5.7 | 4 |
| Orange | 10/10 | 10/10 | 6.2 | 5 |

Validation failures over all games (negative stock, ware ledger, VP replay): **0**.

## Result
* **Met**: ware ledger balanced, VP replay consistent and no negative stock in every game; five of six factions found 3+ settlements in most seeds (the count includes the capital only in "standing").
* **Not met**: **Blue (Empire)** founded 0-2 settlements in most seeds. Diagnosis on seed 108 (`ai_notes`): "expansion waits: a blight nest killed our last founder" eight times, 33 founder wagons queued, then "no legal settlement site left". An outbreak nest sits on the founders' road; the AI waits five minutes and sends the next wagon down the same road, and in this mode there are no soldiers to clear the nest. Other seeds show a boxed-in start ("founder has no reachable legal site"), now handled by unfolding where the wagon stands (added after most of these games started, so not reflected here).
* Fix candidates (not done): route founders around nest weapon range using the real path (not the straight line used by `_site_value`), mark the death tile as bad, and let a faction without an army ask a rival or the clinic chain for help.

## Follow-up the same evening (seed 108, plus AIs, 50 minutes, after the clinic reach fix)
The clinic now treats the regions within 24 tiles (a nest at a region border could not be reached before). Blue's founder-wagon queue events in that game fell from **33 to 3** (the wagons stopped being sacrificed), but Blue still ended with one settlement: the AI then reports "no legal settlement site left" (the separation rule around rivals' capitals plus water leaves Blue no site within 70 tiles of its own settlements). So Blue's shortfall is partly a **map geometry / separation-rule problem** (its start is hemmed in), not only an AI problem; whether a start position should be guaranteed room for three settlements is a design question for the owner (queue: `docs/ledger/QUESTIONS.md`).
