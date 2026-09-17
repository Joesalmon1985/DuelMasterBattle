# G02 playtest handoff — FX-CARGO performance repair

**Status:** AWAITING_HUMAN (do not start T049)  
**Scenario:** FX-CARGO · **Seed:** 202  
**Review baseline:** `f947f57d06ad6ab1b2223baae152ff1ecfcc67f3`  
**Tested revision:** _(stamp after commit)_  
**Save slot:** `g02_playtest` · recovery: `_recovery`

## Launch (verified)

```bash
cd /home/joe/Projects/DuelMasterBattle
bash tools/play_g02.sh --direct
```

Windows local verify used Godot 4.5.1 console at 450×800 with `DMB_FIXTURE=FX-CARGO` `DMB_SEED=202`.

Portrait **450×800**. Economy panel is collapsible top-right (refresh ~2 Hz only while expanded).

## FIX (performance)

- **Nonblocking bridge:** `WorldClient` frame-polled queue, one request in flight, `expected_world_version` assigned at send time, all received frames processed; SyncPose/progress coalesced; transition ACKs preserved.
- **Traffic cut:** cached player projections for ordinary HUD; economy lean fields (no `command_receipts` / raw knowledge / leases) only while expanded.
- **Smooth carts:** Game-Time sim still 100 ms; render interpolates along path every frame without double phase/ACK.
- **Bounded clock:** `ClockDriver` pending cap 2; drained/acked by shell; no unused unbounded queue growth; no catch-up storm after delayed replies.
- **Checkpoint:** recovery snapshot still consistent/atomic; disk write deferred until after the command reply returns.

## Measured results (rendered, 450×800, Windows A520M K V2)

| Sample | Median ms | p95 | p99 | stalls >100 ms | notes |
| --- | --- | --- | --- | --- | --- |
| before (`f947f57` blocking) | — | — | — | unplayable | 15 s harness timed out at 90 s wall |
| after 30 s | 0.58 | 0.92 | 1.43 | **0** | walk + cart + economy toggle |
| after 5 min | 0.57 | 0.90 | 16.6 | **14** | no worsening runaway; ~23 bridge req/s |

Evidence: `tracking/gates/G02/perf_before_short.json`, `perf_after_short.json`, `perf_after_5min.json`, journey demo frames under `recordings/`.

## Automated checks (agent)

| Check | Result |
| --- | --- |
| `pytest tests/sim/test_g02_perf_bridge.py` (+ presentation journeys) | PASS |
| `run_g02_smoke.gd` | PASS |
| `run_g02_cart_followthrough.gd` | PASS |
| `run_g02_cart_journey_demo.gd` | PASS |
| `run_g01_smoke.gd` | PASS |

## Remaining limitations

- Infrequent user commands (`Wait` / `Travel` / `Save`) still use a short blocking wait helper (not the clock hot path).
- Periodic recovery still snapshots on the sidecar thread after reply; a few >100 ms stalls remain over long runs (14 / 5 min).
- Uncapped scripted FPS makes median frame time look sub-millisecond; use stall counts and play feel as the gate signal.

## Controls checklist

| Control | Where | Use for |
| --- | --- | --- |
| **Start delivery** | Economy | Load haul; cart walks to exit (~64 px/s Game Time) |
| **Wait** | bottom | ≤1 road edge; depart then fully hide through doorway |
| **Travel** (follow) | exit | Enter once, cross once; no left↔right loops |
| **Block** / **Clear** | Economy | Route hazard on `node:2` |
| **Pause** | bottom | Freezes Game Time + cart motion |
| **Save** / **Load** | bottom | Mid-journey resume without replaying consumed entrance |

Reply `G02 PASS — <build/commit>` or `G02 FIX_REQUIRED — <symptom>`.

**Not claimed as human gate PASS.** **T049 remains NOT_STARTED.**
