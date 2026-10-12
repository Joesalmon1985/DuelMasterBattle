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

## 1b. Tournaments war90_d and war90_e (split tuning)

Same command and seeds as war90_c. war90_d: commit 83fde8f (sickness closures 0.5% per cube-minute, isolation 0.01). war90_e:
commit 7695535 (a split also needs unrest held at >= 0.6 for 10 game minutes; 40-minute faction split cooldown; peace switch and
nest-safe guard posts, which do not affect war games).

| per root faction at 90 min | war90_d plus | war90_d baseline | war90_e plus | war90_e baseline |
| --- | --- | --- | --- | --- |
| VP (95% CI) | 4.36 (±0.38) | 3.08 (±0.42) | 4.39 (±0.30) | 2.94 (±0.22) |
| settlements | 4.33 | 2.33 | 4.31 | 2.53 |
| buildings | 80 | 50 | 82 | 51 |
| units produced | 87 | 126 | 78 | 133 |
| own buildings lost | 16 | 34 | 12 | 34 |
| food / iron in store | 93 / 7.9 | 15 / 0 | 104 / 7.9 | 16 / 0.1 |
| peak settlement unrest | 0.83 | 0.71 | 0.78 | 0.84 |
| nest cubes cleared, trades | 0.53, 0.86 | 0.33, 0.42 | 0.72, 0.72 | 0.33, 0.28 |

| per game | war90_d | war90_e |
| --- | --- | --- |
| games won by VP (plus - baseline) | 7 - 5 | 9.5 - 2.5 |
| reached Historic / Modern / Dystopian in 90 min | 12 / 12 / 6 of 12 | 12 / 12 / 0 of 12 |
| Historic at (min) | 17-23 | 17-23 |
| Modern at (min) | 26-62 | 26-65 |
| splits | about 54 (4.5 a game) | 34 (2.8 a game) |
| collapsed successors | 11 | 7 |
| stall-guard transitions, validation failures | 0, 0 | 0, 0 |

The sustained-unrest rule cut splits by about 40% and the improved AI's lead widened. All eras changed by VP. **No game of war90_e
reached Dystopian within 90 minutes** (war90_d: 6 of 12). With fewer splits there are fewer weak successors to raze and refound, so
world VP grows more slowly in Modern. The 180-minute all-plus run still reached Dystopian at 119 min. Whether Modern -> Dystopian
in 60-90 minutes is wanted is an owner call (`ERA_VP_THRESHOLDS` third value, or the 75-minute stall guard).

## 1c. Crisis tournaments: factions clearing outbreaks without the wizard

`--mode crisis --seeds 507 11 23 --minutes 60 --jobs 1` (outbreak cadence doubled), commit 7695535, with and without
`--wizard-pilot` (the scripted wizard walks to infected regions and treats by the public rules only).

| 18 faction-games per policy, 60 min | no wizard: plus | no wizard: baseline | wizard: plus | wizard: baseline |
| --- | --- | --- | --- | --- |
| VP | 4.44 | 2.72 | 4.33 | 2.89 |
| nest cubes cleared by the faction's army | 0.67 | 0.11 | 0.06 | 0.06 |
| peak settlement unrest | 0.96 | 0.63 | 0.59 | 0.14 |
| workplace closures | 4.83 | 3.06 | 0.33 | 0.28 |
| collapsed | 0 | 0 | 0 | 0 |

Without the wizard, armies sent 20 squads against nests and destroyed 12 nests in 6 games. The improved AI does most of it (it
weighs nests in or next to its settlements and commits only with enough strength), and the baseline only clears nests its guards
happen to fight. With the wizard, 53 treatments kept outbreaks small: armies destroyed only 2 nests, and closures and unrest fell
sharply. The factions survive outbreaks alone, and the wizard's help is visible. Improved AI won 6 - 0 in both.

## 1d. Headed 16x God Mode (Godot 4.5.1, commit 7695535)

`run_headed_suite.sh autoplay` (developer profile, seed 507, mixed policies, speed 16x, spectating): PASS. Milestones were the first
draft at 1:34, a card's building working at 5:57, the first catastrophe at 10:12, a new settlement at 11:46 and the first battle
at 11:54. Historic came naturally (by VP) at 19:10. Shots are in `WizardRTSHybrid/docs/evidence/civilisation/autoplay_16x/`.
The pace was about 15x early and about 3x after the first battle on this laptop (the game slows as armies grow; see section 4).

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
| Split cascades (one faction split six times) | no cooldown; one unrest spike was enough | 40-min faction cooldown, 30-min successor grace, unrest held 10 min |
| Peace runs had a battle; a nest killed a soldier a minute | guards auto-fired at a passing MCV under the peace switch; guard posts stood in nest range | peace switch: no inter-faction targeting; posts avoid nest reach |
| Simulation 12x realtime | road A* set unions, quadratic logistics scans, per-step unit occupancy, naval search retries | flat-array A*, indexed scans, counted occupancy (same state hashes) |

## 4. Open balance problems (next iterations)

- **Splits** fell from about 4.5 to 2.8 a game (war90_e) after the sustained-unrest rule. Unrest is still high (peak ~0.8). The
  split chronicle records society's pressures, but outbreak unrest (regions._unrest) is not in that record yet. Add it before tuning
  further.
- **Dystopian within 90 min**: 0/12 in war90_e (6/12 in war90_d); see 1b.
- **Nests** are cleared by armies when the wizard is absent (1c), but rarely in war games, where squads go to enemies first.
- **The baseline barely trades and never uses the Mindustry line** (it needs three cards and large stocks); the improved AI drafts the
  cards but rarely holds the 70 planks / 40 granite / 30 iron the line costs.
- Late-game speed: ~5-8x realtime at 100+ units with other jobs running; enough for tournaments, short of 16x in Godot late on.
