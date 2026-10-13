# Performance results of the v2 run (13 Oct 2026, ThinkPad T460, Python 3.12, one core per game)

All optimisations in this run are **behaviour-preserving**: the state hash is identical to the starting commit `11b70b2` at every game minute that was compared.

| Measurement | Starting commit | End of run | Conditions |
| --- | ---: | ---: | --- |
| 15 game minutes, seed 507, six baseline AIs (`perf_gate.py early`) | 35.5x realtime | **42.9x** | idle machine, same hash `b317aff9...` |
| 30 game minutes, seed 507 (`hash_gate.py record`) | 19.2x (93.9 s) | **30.7x (58.6 s)** | idle machine, hash equal at all 30 minute marks, **1.6x faster** |
| 50 game minutes, seed 507 | 6.6x (451.8 s) | 17.8x (168.6 s) | the starting-commit figure was measured while another job ran (understates its speed), hash equal at 50 minutes |
| nocards civilisation, minutes 40-50 (`perf_gate.py mid`) | n/a (mode did not exist) | 17.8x | idle machine, about 390 buildings |
| nocards civilisation, warm-up to minute 90 | 848 s (shared CPU, before the site-search fix) | 439 s (shared CPU) | about 430 buildings |
| 120 game minutes, six plus AIs, seed 507 | n/a | 695 s (10.4x average) | recorded as `hash_baseline_late120.json` |
| 180 game minutes, all systems on, shared CPU | n/a | 5,855 s (about 1.8x under 4-6 concurrent jobs), memory flat at 64 MB | `docs/evidence/stability/` |

What produced the gains (profile first, then change): the tree container visited every tree every tick (now slot buckets), the A* inner loop did a division, two range tests and a call per neighbour (tightened, then an optional C kernel through `ctypes` with identical tie-breaks and a pure-Python fallback), the command-centre list was rebuilt about 11,000 times per game second (cached; it was 12% of the profile), nest and site searches scanned whole squares for ring cells.
What was **not** done: PyPy, Numba, structure-of-arrays, native combat/logistics kernels (plan P8/P13), cross-OS state-hash equality, Windows measurements. Targets of plan 10.2 (mid-game at least 25x, late game at least 8x per core) are not yet met: mid-game is 18x, and late game with 400+ buildings is 5-6x unshared.
