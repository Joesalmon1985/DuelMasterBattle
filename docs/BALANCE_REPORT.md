# Balance report: improved AI (plus) against the original AI (baseline)

Written from the headless tournaments of 12 October 2026. Every game is the shipped `campaign` profile (primitive start, gated cards,
no grants or fixtures, nothing skipped). Reproduce with the commands given per section. Raw outputs: `~/dmb_runs/<dir>`; the small files
are copied to `WizardRTSHybrid/docs/evidence/civilisation/`.

## 1. Tournament war90_c (commit 5b9ec0e)

`python3 WizardRTSHybrid/scripts/run_civilisation_tournament.py --mode war --seeds 507 11 23 101 102 103 --minutes 90 --jobs 2`

12 games: 6 seeds, each played twice with the improved AI on Red/Green/Purple (A) then on Blue/Yellow/Orange (B), so every start
position plays both policies. 36 faction-games per policy.

| per root faction at 90 min | plus | baseline |
| --- | --- | --- |
| VP (95% CI) | 3.64 (±0.46) | 2.17 (±0.28) |
| settlements | 3.42 | 1.94 |
| buildings | 74 | 46 |
| founded settlements | 2.7 | 1.8 |
| army size / strength | 10.8 / 40k | 13.9 / 44k |
| units produced | 85 | 108 |
| enemy units / buildings destroyed | 54 / 12 | 51 / 38 |
| own buildings lost | 17 | 29 |
| food / iron in store | 49 / 5.9 | 26 / 0.5 |
| collapsed | 0 of 36 | 1 of 36 |
| nest cubes cleared, trades | 0.86, 0.36 | 0.72, 0.19 |

Games won by end VP: **plus 10, baseline 2**. The improved AI wins by economy and expansion (more settlements, food and iron,
fewer losses) rather than by out-fighting: the baseline builds more units and razes more buildings. That is the intended kind of
advantage (better decisions, no extra resources).

Eras: **12/12 games reached Historic and 8/12 Modern within 90 game minutes, every transition by VP** (no stall-guard
transition). The owner's targets (>=8/10 Historic within 60 min, >=6/10 Modern within 120 min) are met on this sample.
Integrity: 0 validation failures (ware ledger, negative stock, VP replay) in 12 games.

## 2. A full historical run

All six factions on the improved AI, seed 507, 180 game minutes (`docs/evidence/civilisation/long_all_plus_seed507_180min.txt`):
Prehistoric -> **Historic at 32 min -> Modern at 69 min -> Dystopian at 119 min, all by VP**. Blue declined, split (Blue-2) and
collapsed at 119 min; Yellow split at 153 min; Blue-2 collapsed at 174 min. Armies cleared 8 nest cubes; 7 cubes stood at the end.

## 3. Defects the simulations found (fixed, with tests)

| Finding | Cause | Fix |
| --- | --- | --- |
| Every faction stuck in Prehistoric at 1 VP for 40+ min | one card per 15 min; MCV four cards deep; leader-only era rule | 4-min rounds, offers of 7; Settlers card; world-VP era rule |
| Red crippled in every game | new roads could share the Ward Duel hazard tile; then a nest by Red's capital shot its wagons; then the mines ate the wagon's rations | roads never cross a carrier-blocked tile; reroute command; nests keep 9 tiles from centres; civilians path round nests; queued units reserve their goods |
| Capitals razed by 5 clubmen | 500 HP, Wood armour, the militia never fired (combat loop skipped non-OpenRA buildings) | 2000 HP Concrete capitals, militia fires |
| Ware ledger leaks | destroyed stock, removed roads, killed carriers and founders, founder cargo in production not booked | all booked as consumed/held; checked every game |
| Split cascades (one faction split six times) | no cooldown | 20-min faction cooldown, 30-min successor grace |
| Simulation 12x realtime | road A* set unions, quadratic logistics scans, per-step unit occupancy, naval search retries | flat-array A*, indexed scans, counted occupancy (same state hashes) |

## 4. Open balance problems (next iterations)

- **Splits are frequent** (26 in 12 games). Unrest is high (mean ~0.8) from sickness closures (a 3-cube region shut most of a
  settlement) and outpost isolation. Tuned after this tournament: sickness closures 1.2% -> 0.5% per cube-minute with at most a
  quarter of a region closed, isolation 0.015 -> 0.01; to be re-measured.
- **Nests are rarely cleared** (<1 cube per faction in 90 min); outbreaks grow in the later eras. Expect the next run to show if the
  nest priority rule changes this.
- **The baseline barely trades and never uses the Mindustry line** (it needs three cards and large stocks); the improved AI drafts the
  cards but rarely holds the 70 planks / 40 granite / 30 iron the line costs.
- Late-game speed: ~5-8x realtime at 100+ units with other jobs running; enough for tournaments, short of 16x in Godot late on.
