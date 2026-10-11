# AI behaviour report

Deterministic headless runs of the real simulation; every faction scripted (`wizard_rts/ai.py`).

## Seed 507 - 40 game minutes (war), 1039.7 s wall, worst step 1976 ms
State hash `a703085da6f963a2`.

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
| no long unresolved stuck entities | **FAIL** |

| faction | alive | CCs | territory | buildings | army | navy | produced | attacks | defends | kills (u/b) | losses (b) | MCV q/d | stuck |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Red | True | 2 | 5850 | 45 | 9 | 9 | 26 | 1 | 2 | 14/13 | 2 | 1/1 | 16 |
| Blue | True | 1 | 1089 | 22 | 1 | 0 | 8 | 0 | 7 | 6/0 | 13 | 2/1 | 0 |
| Green | True | 2 | 5850 | 49 | 33 | 9 | 41 | 0 | 0 | 0/0 | 0 | 2/1 | 38 |
| Yellow | True | 2 | 5850 | 51 | 32 | 9 | 45 | 1 | 0 | 4/2 | 0 | 2/1 | 37 |
| Purple | True | 2 | 5850 | 52 | 24 | 9 | 33 | 0 | 9 | 5/0 | 1 | 2/1 | 27 |
| Orange | True | 2 | 5850 | 48 | 33 | 9 | 46 | 1 | 0 | 1/1 | 0 | 2/1 | 38 |

Command centres by minute: m1: 1,1,1,1,1,1; m6: 1,1,1,1,1,1; m11: 1,1,1,1,1,2; m16: 2,1,2,2,2,2; m21: 2,1,2,2,2,2; m26: 2,1,2,2,2,2; m31: 2,1,2,2,2,2; m36: 2,1,2,2,2,2

Stalled entities at the end:

- carrier cart:1 (Red) at [80, 48] for 2378 s: hazard on the road: the carrier waits for the wizard to clear it
- unit unit:9 (Green) at [339, 109] for 1799 s: another unit stands on the next tile
- unit unit:18 (Orange) at [499, 205] for 1679 s: another unit stands on the next tile
- unit unit:16 (Orange) at [500, 204] for 1519 s: another unit stands on the next tile
- unit unit:12 (Yellow) at [260, 185] for 1264 s: another unit stands on the next tile
- unit unit:86 (Orange) at [467, 176] for 1239 s: route search budget for this quantum was spent
- unit unit:81 (Red) at [95, 48] for 1229 s: route search budget for this quantum was spent
- unit unit:87 (Red) at [96, 44] for 1229 s: route search budget for this quantum was spent
