# P10 catastrophe study, first pass (13 Oct 2026)

Runner: `scripts/catastrophe_study.py` (six plus AIs, outbreak cadence scaled to 0.12, i.e. one cube every 72 game seconds, cumulative loss limit 8 outbreaks, per-era limit off, 4 seeds per cell, 90-minute horizon, game stops at collective loss). Policies: `ignore` (no clinics, no nest hunting), `selfish` (clinics and nest hunting in own settlements), `coop` (selfish + nest hunting anywhere, scaled by pressure, + cooperative truces under pressure).

## A. Old hand-written cards, no clinics (nothing but combat can remove cubes)

| policy | era limit | total limit | games | P(collective loss) | median minutes to loss | mean outbreaks | mean cubes cleared | mean truces |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ignore | 99 | 8 | 4 | 1.00 | 43.599999999999994 | 9.8 | 9.5 | 0.0 |
| selfish | 99 | 8 | 4 | 1.00 | 42.4 | 10.5 | 6.8 | 0.0 |
| coop | 99 | 8 | 4 | 1.00 | 42.4 | 10.5 | 6.8 | 12.8 |

Every policy loses at about minute 42-47. Identical outcomes for `ignore` and `selfish` on three of four seeds: the AIs' nest policy changes nothing at this pressure, because nests are mostly killed (or not) by units and defences that happen to be nearby.

## B. Generated cards v2, clinic available to every faction (foundation building; rations and water per cube)

| policy | era limit | total limit | games | P(collective loss) | median minutes to loss | mean outbreaks | mean cubes cleared | mean truces |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ignore | 99 | 8 | 4 | 1.00 | 43.6 | 10.2 | 7.5 | 0.0 |
| selfish | 99 | 8 | 4 | 0.75 | 64.0 | 8.2 | 5.5 | 0.0 |
| coop | 99 | 8 | 4 | 0.75 | 64.0 | 8.2 | 5.5 | 21.8 |

The clinic changes the outcome: with clinics `selfish` and `coop` lose in 3 of 4 games at a median of minute 64 against minute 44 for `ignore`, and one game survives the whole 90 minutes. `coop` and `selfish` are identical in outcome: the truces (about 22 per game) are signed but nothing in a truce moves wares or soldiers to a rival's region, so cooperation has no effect yet.

## Reading and what is not met
* The plan's calibration targets (7.4: ignore loses in most games, selfish in a meaningful minority, cooperative rarely) are **not met**: at this cadence even the best policy loses in most games. Cadence 0.12 is far harsher than the design default (scale 1.0) at which no game came close to the limit, so the useful scale is between; the next pass needs scales 0.2-0.5, more seeds (4 per cell is far too few for a probability) and the per-era limit grid.
* Cooperation needs a physical channel: wares or squads sent to a rival's infected settlement (the trade caravan can carry rations and water; a squad can clear a nest in a truce partner's region). Until then `coop` cannot beat `selfish`.
* The collective-loss flag, per-era counters, relations, nest policies and clinics are all implemented and tested (`tests/test_outbreaks.py`, `tests/test_diplomacy.py`); this study is the first use of them.

## C. Intermediate cadence (scale 0.3: one cube every 3 minutes), v2 cards with clinics, 2 seeds per cell, 90-minute horizon (added at the end of the run)
| policy | games | collective loss | minutes to loss | mean outbreaks | cubes cleared by units |
| --- | ---: | ---: | --- | ---: | ---: |
| ignore (no clinics, no nest hunting) | 2 | **2 of 2** | 73 and 85 | 12 | 5 |
| selfish (clinics + nest hunting at home) | 2 | **0 of 2** | - | 0 | 5.5 |

Here the response works as the plan wants it to be needed: without it the world is lost in both games at 73-85 minutes, with clinics neither game had a single outbreak (the clinics cured the cubes before any region overflowed). Together with B (scale 0.12: clinics delay the loss from minute 44 to 64) this brackets the interesting regime: scales between 0.12 and 0.3 should give "ignore loses, selfish sometimes loses, cooperative rarely". Two seeds per cell are not a probability; the calibration study (10+ seeds per cell, scales 0.15 / 0.2 / 0.25, the per-era limit grid and `coop`) is the next step and was not run for lack of time. Raw rows: `cat_study4_cells.jsonl`.

## D. Cadence 0.2 (one cube every 2 minutes), v2 cards with clinics, 2 seeds per cell (last run of the session)
| policy | games | collective loss | outbreaks (mean) | truces signed (mean) |
| --- | ---: | ---: | ---: | ---: |
| selfish | 2 | 1 of 2 (minute 56) | 6 | 0 |
| coop | 2 | 1 of 2 (minute 56, **the same game**) | 6 | 24.5 |

At 0.2 the response is neither always enough nor never: one game is lost at minute 56, the other has no outbreak at all. `coop` reproduces `selfish` game for game (49 truces were signed in the lost game and changed nothing): the cooperative channel (truces, aid caravans) did not matter here because the loss came from a region the clinics could not clear in time, not from missing rations. The regime for the full calibration is therefore scale 0.15-0.25; `coop` needs a stronger physical channel (squads sent to a partner's region, wares delivered before the cubes arrive) before it can beat `selfish`. Raw rows: `cat_study5_cells.jsonl`.
