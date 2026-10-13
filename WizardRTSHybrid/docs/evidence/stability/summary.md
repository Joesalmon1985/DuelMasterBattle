# 180-minute all-systems stability run (13 Oct 2026)

`python3 scripts/long_stability.py --minutes 180 --seed 7` under the supervisor (nice 5): generated cards with the era-start ring draft, six plus AIs, cooperative diplomacy and nest hunting enabled, clinics, caravans, outbreaks at the design cadence. Sampled every 5 game minutes (`progress_180min.jsonl`); invariants checked every 30 minutes.

| | |
| --- | --- |
| wall time | 5855 s (98 min) for 180 game minutes **while sharing the 4 threads with 4-6 other jobs** (average about 1.8x realtime under that load; the same game alone ran faster, see the throughput column below) |
| invariant failures (ware ledger, negative stock, VP replay) | **0** at minutes 30, 60, 90, 120, 150, 180 |
| memory | peak RSS 67 MB, flat from minute 5 to 180 (58 -> 64 MB): no leak |
| buildings / units at the end | 511 / 49 (workers 261, carriers 481) |
| eras | reached era 2 (Modern) at minute ~150: **both transitions were stall-guard (75 minute) transitions**, no faction reached the VP bar again (top VP 7) |
| splits | the Yellow empire split three times (Yellow-2, -3, -4) |
| collective loss | no (0 terminal_loss events) |
| relations | none signed: the catastrophe pressure never reached the cooperation threshold at the design cadence |
| cards-used rate | 30% of the entities of drafted cards were ever built or produced (62-67% in the 60-minute probes; later phases hand out cards the AIs cannot use yet) |
| `worker_failed` events | 108,259 of 380,255 counted events: quarries and woodcutters retrying with nothing to cut (known, not fixed) |

Throughput by game minute (game seconds per wall second, shared machine): 5: 7.9x, 35: 1.6x, 65: 1.7x, 95: 1.0x, 125: 1.4x, 155: 3.6x.

What this shows: the new systems (draft phases, bonus hands, clinics, caravans, diplomacy hooks, native A*) run for three hours of game time without a crash, a hang, a conservation break or a memory leak. What it does not show: balance. The era pace is driven by the stall guard, the economy plateaus at 500 buildings with only ~45 units, and most late cards go unused.
