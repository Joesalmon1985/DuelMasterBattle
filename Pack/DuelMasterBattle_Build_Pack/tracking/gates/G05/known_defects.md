# G05 FIX_REQUIRED — cumulative runtime regression

**Status:** repaired candidate — AWAITING_HUMAN after automated pass

## Audit matrix (G05 vs accepted G01–G03)

| Behaviour | Status | Notes |
|-----------|--------|-------|
| Game Time / AdvanceGame | **preserved** | ClockDriver + nonblocking AdvanceGame on G05 shell |
| Pause/Resume / no catch-up | **preserved** | acquire_pause/release_pause; dialogue/duel freeze Game Time |
| SyncPose | **preserved** | Coalesced SyncPose after Overworld steps + periodic |
| Mouse world steering | **preserved** | LMB hold dominant-axis grid step; GUI/entity priority |
| Touch D-pad | **preserved** | Overworld TouchPad |
| Keyboard movement | **preserved** | WASD/arrows |
| Carts / journeys | **N/A (fixture)** | FX-VILLAGE has no cart hauls; export keeps cart/unit IDs |
| Workers / carriers | **preserved** | IndustryProjection + WorkerController (not `_tick_workers`) |
| Industry connections | **preserved** | Real IndustryService routes / factory_readout |
| Factory meters | **preserved** | Computed rates; solutions never assign `output_rate` |
| Military units | **N/A initially** | Spawn after positive factory rate |
| Save/load | **preserved** | SyncPose before Save; IDs/pose survive Load |
| Semantic interaction | **preserved** | Bridge talk / labels |
| G04 retained duel | **preserved** | DuelLeaseAdapter |

## Root cause (fixed)

G05 fed `overworld_area` into legacy Overworld and bypassed ClockDriver /
IndustryService / WorkerController. FX-VILLAGE stubbed `output_rate` instead of
real PrimaryChannels / ProcessorBinding / FactoryRoutes.

## Repair

Combine Overworld presentation with migrated G01–G03 clock + industry runtime.
Route A blocked by demon via `industrial_blocked`; Route B blocked by inactive
sluice processor (`modifier=0`). Solutions clear causes through owning services
and let the next industry tick compute positive production.
