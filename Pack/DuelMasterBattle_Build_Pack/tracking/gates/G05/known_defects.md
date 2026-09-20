# G05 FIX_REQUIRED → AWAITING_HUMAN

**Status:** AWAITING_HUMAN after integrated-world repair

## Audit

| Item | Result |
|------|--------|
| Real BoardBuilder board | seed **507** — 19 hexes / 54 nodes / 72 edges |
| Real settlement node | `node:35` / `settlement:3` / `faction:2` |
| Working + shortage chains | wood+clay working; wood+ore blocked by demon on `hex:1,1` |
| One person = one actor | industry people excluded from Overworld NPC export; uniqueness asserted in cumulative Godot test |
| ActorVisual sprites | WorkerController uses character families (woodcutter/miner/worker/…) |
| No output_rate fakes | IndustryService computes rates |
| Architecture doc | `docs/INTEGRATED_RUNTIME_ARCHITECTURE.md` (linked from AGENT_START_HERE) |
| Manual play_g05 | Launched seed 507; settlement reads as a real village slice (pixel sprites, human labels such as Clay pits / Clay works) |

Raw connection IDs must not appear in player-facing labels (debug overlay only).

Spare setup factory `building:27` is labelled **Idle factory** (present from WorldSetupService, not on the shortage routes).
