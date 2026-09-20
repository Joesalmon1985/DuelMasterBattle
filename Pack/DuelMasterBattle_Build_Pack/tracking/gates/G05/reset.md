# G05 reset

Isolated slots / files (delete before a clean playtest):

- `.dmb_saves/g05_playtest*` (if present)
- `.dmb_endpoint.json` (stale sidecar)
- `user://` adventure saves only if you intentionally mixed sessions

Scenario snapshots (do not edit; reload from packet):

- `scenarios/fresh_launch.json` — seed 507 offered shortage
- `scenarios/solution_demon_duel.json` — Route A completed
- `scenarios/solution_sluice_route.json` — Route B completed, demon still active
- `scenarios/world_resolved.json` — patrol cleared ridge first
- `scenarios/destroyed_target.json` — factory destroyed / displaced loss

Reload FX-VILLAGE with:

```bash
DMB_SEED=507 bash tools/play_g05.sh
```

Or re-run:

```bash
python3 tools/run_scenario.py --fixture FX-VILLAGE --seed 507 --record Pack/DuelMasterBattle_Build_Pack/tracking/gates/G05/fx_village_record.json
```
