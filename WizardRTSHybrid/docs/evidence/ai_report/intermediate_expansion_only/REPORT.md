# AI behaviour report

Deterministic headless runs of the real simulation; every faction scripted (`wizard_rts/ai.py`).

## Seed 507 - 40 game minutes (war), 138.6 s wall, worst step 413 ms
State hash `013f1ffd2489578e`.

| check | result |
| --- | --- |
| every faction built a working economy | PASS |
| most factions deployed a second command centre | PASS |
| territory grew | **FAIL** |
| armies were recruited | PASS |
| armies moved | PASS |
| some factions stayed alive | PASS |
| attacks were launched | PASS |
| enemies were damaged | PASS |
| more than one faction attacked | PASS |
| no long unresolved stuck entities | PASS |

| faction | alive | CCs | territory | buildings | army | navy | produced | attacks | defends | kills (u/b) | losses (b) | MCV q/d | stuck |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Red | True | 2 | 5850 | 29 | 4 | 0 | 40 | 14 | 7 | 27/57 | 41 | 2/1 | 0 |
| Blue | True | 1 | 1089 | 12 | 0 | 0 | 12 | 1 | 4 | 19/0 | 33 | 3/2 | 0 |
| Green | True | 2 | 5850 | 41 | 7 | 0 | 36 | 8 | 9 | 18/15 | 4 | 3/2 | 0 |
| Yellow | True | 3 | 6939 | 36 | 6 | 0 | 31 | 6 | 9 | 25/56 | 24 | 2/2 | 0 |
| Purple | False | 0 | 0 | 5 | 0 | 0 | 11 | 1 | 4 | 29/1 | 69 | 3/2 | 0 |
| Orange | True | 3 | 6939 | 46 | 5 | 0 | 38 | 4 | 12 | 35/51 | 9 | 2/2 | 0 |

Command centres by minute: m1: 1,1,1,1,1,1; m6: 1,1,1,1,1,1; m11: 1,1,1,1,1,1; m16: 1,2,2,2,2,2; m21: 2,3,2,2,3,3; m26: 2,1,3,3,1,3; m31: 2,1,2,3,1,3; m36: 2,1,2,3,0,3
