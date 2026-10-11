# AI behaviour report

Deterministic headless runs of the real simulation; every faction scripted (`wizard_rts/ai.py`).

## Seed 507 - 40 game minutes (war), 384.5 s wall, worst step 783 ms
State hash `c6035a4167cf6b80`.

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
| Red | True | 2 | 5850 | 40 | 1 | 1 | 29 | 2 | 8 | 35/3 | 25 | 1/1 | 1 |
| Blue | True | 3 | 6939 | 42 | 5 | 0 | 35 | 0 | 225 | 31/5 | 95 | 2/2 | 0 |
| Green | True | 3 | 6939 | 47 | 7 | 0 | 34 | 2 | 161 | 24/23 | 35 | 2/2 | 1 |
| Yellow | True | 3 | 6939 | 59 | 19 | 9 | 47 | 4 | 2 | 12/113 | 0 | 2/2 | 0 |
| Purple | True | 2 | 5850 | 49 | 23 | 0 | 42 | 0 | 11 | 34/107 | 6 | 3/2 | 0 |
| Orange | True | 3 | 6939 | 26 | 0 | 0 | 19 | 1 | 13 | 12/1 | 91 | 2/2 | 0 |

Command centres by minute: m1: 1,1,1,1,1,1; m6: 1,1,1,1,1,1; m11: 1,1,1,1,1,2; m16: 2,2,2,2,2,2; m21: 2,3,2,2,2,2; m26: 2,3,3,3,2,2; m31: 2,3,3,3,3,2; m36: 2,3,3,3,3,3

Stalled entities at the end:

- carrier cart:1 (Red) at [80, 48] for 2378 s: hazard on the road: the carrier waits for the wizard to clear it
- unit unit:9 (Green) at [327, 84] for 162 s: ordered but not moving (moving)
