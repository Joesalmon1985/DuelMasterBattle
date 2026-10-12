# AI behaviour report

Deterministic headless runs of the real simulation; every faction scripted (`wizard_rts/ai.py`).

## Seed 507 - 40 game minutes (war), 225.0 s wall, worst step 502 ms (game minute 28.5)
State hash `108d7b602e3d711d`.

| check | result |
| --- | --- |
| every faction built a working economy | PASS |
| most factions deployed a second command centre | PASS |
| territory grew | PASS |
| armies were recruited | PASS |
| armies moved | PASS |
| some factions stayed alive | PASS |
| attacks were launched | PASS |
| enemies were damaged | PASS |
| more than one faction attacked | PASS |
| no long unresolved stuck entities | PASS |

| faction | alive | CCs | territory | buildings | army | navy | produced | attacks | defends | kills (u/b) | losses (b) | MCV q/d | stuck |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Red | True | 2 | 5850 | 44 | 0 | 2 | 32 | 1 | 5 | 34/1 | 3 | 1/1 | 2 |
| Blue | True | 3 | 6939 | 54 | 5 | 8 | 45 | 0 | 214 | 48/95 | 0 | 2/2 | 0 |
| Green | True | 2 | 5850 | 37 | 1 | 0 | 27 | 1 | 213 | 20/83 | 94 | 3/2 | 0 |
| Yellow | True | 2 | 2178 | 22 | 1 | 0 | 19 | 2 | 5 | 11/2 | 40 | 2/2 | 0 |
| Purple | True | 1 | 1089 | 20 | 3 | 0 | 5 | 0 | 4 | 6/0 | 28 | 2/1 | 0 |
| Orange | False | 0 | 0 | 0 | 6 | 0 | 15 | 2 | 2 | 7/28 | 44 | 2/1 | 0 |

Command centres by minute: m1: 1,1,1,1,1,1; m6: 1,1,1,1,1,1; m11: 1,1,1,1,1,2; m16: 2,2,2,2,1,2; m21: 2,3,2,2,1,0; m26: 2,3,2,3,1,0; m31: 2,3,2,2,1,0; m36: 2,3,2,2,1,0

Stalled entities at the end:

- carrier cart:1 (Red) at [80, 48] for 2378 s: hazard on the road: the carrier waits for the wizard to clear it
- carrier cart:289 (Red) at [80, 48] for 393 s: hazard on the road: the carrier waits for the wizard to clear it

## Seed 11 - 40 game minutes (war), 194.6 s wall, worst step 380 ms (game minute 29.23)
State hash `d61eef23a2edde7b`.

| check | result |
| --- | --- |
| every faction built a working economy | PASS |
| most factions deployed a second command centre | PASS |
| territory grew | PASS |
| armies were recruited | PASS |
| armies moved | PASS |
| some factions stayed alive | PASS |
| attacks were launched | PASS |
| enemies were damaged | PASS |
| more than one faction attacked | PASS |
| no long unresolved stuck entities | PASS |

| faction | alive | CCs | territory | buildings | army | navy | produced | attacks | defends | kills (u/b) | losses (b) | MCV q/d | stuck |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Red | True | 1 | 1089 | 8 | 0 | 0 | 12 | 1 | 3 | 5/0 | 34 | 2/1 | 0 |
| Blue | False | 0 | 0 | 0 | 0 | 0 | 10 | 1 | 5 | 25/7 | 34 | 2/1 | 0 |
| Green | True | 2 | 5850 | 42 | 1 | 0 | 36 | 2 | 102 | 35/59 | 74 | 3/2 | 0 |
| Yellow | True | 3 | 6939 | 59 | 25 | 4 | 48 | 3 | 10 | 25/92 | 0 | 2/2 | 0 |
| Purple | True | 3 | 6939 | 51 | 11 | 1 | 44 | 3 | 111 | 28/33 | 35 | 2/2 | 0 |
| Orange | True | 1 | 1089 | 32 | 0 | 0 | 37 | 3 | 17 | 35/21 | 35 | 3/2 | 0 |

Command centres by minute: m1: 1,1,1,1,1,1; m6: 1,1,1,1,1,1; m11: 1,1,1,1,2,1; m16: 2,1,2,2,2,2; m21: 1,1,3,2,3,2; m26: 1,1,3,3,3,3; m31: 1,0,2,3,3,3; m36: 1,0,2,3,3,2

## Seed 23 - 40 game minutes (war), 213.2 s wall, worst step 433 ms (game minute 30.58)
State hash `de6c1bdb9d92e2c7`.

| check | result |
| --- | --- |
| every faction built a working economy | PASS |
| most factions deployed a second command centre | PASS |
| territory grew | PASS |
| armies were recruited | PASS |
| armies moved | PASS |
| some factions stayed alive | PASS |
| attacks were launched | PASS |
| enemies were damaged | PASS |
| more than one faction attacked | PASS |
| no long unresolved stuck entities | PASS |

| faction | alive | CCs | territory | buildings | army | navy | produced | attacks | defends | kills (u/b) | losses (b) | MCV q/d | stuck |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Red | True | 1 | 1089 | 2 | 6 | 0 | 31 | 3 | 14 | 32/30 | 41 | 3/2 | 0 |
| Blue | True | 1 | 1089 | 3 | 3 | 0 | 9 | 1 | 0 | 11/49 | 31 | 3/1 | 0 |
| Green | True | 1 | 1089 | 15 | 2 | 0 | 7 | 1 | 2 | 8/4 | 37 | 2/1 | 0 |
| Yellow | True | 3 | 6939 | 56 | 17 | 3 | 50 | 4 | 13 | 23/50 | 3 | 2/2 | 0 |
| Purple | True | 2 | 5850 | 44 | 5 | 0 | 21 | 1 | 65 | 26/10 | 12 | 4/1 | 0 |
| Orange | True | 2 | 5850 | 44 | 7 | 0 | 34 | 2 | 34 | 17/3 | 22 | 3/2 | 0 |

Command centres by minute: m1: 1,1,1,1,1,1; m6: 1,1,1,1,1,1; m11: 1,1,2,1,1,1; m16: 2,2,2,2,2,2; m21: 2,1,1,2,2,3; m26: 3,1,1,3,2,3; m31: 2,1,1,3,2,3; m36: 2,1,1,3,2,3
