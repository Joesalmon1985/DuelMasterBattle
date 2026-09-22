# G05 reset — full Prehistoric world

Isolated slots / files (delete before a clean playtest):

- `.dmb_saves/g05_playtest*` / `g05_village*` (if present)
- `.dmb_endpoint.json` (stale sidecar)

Reload baseline (no quest):

```bash
DMB_SEED=507 bash tools/play_g05.sh
```

Or re-run:

```bash
python3 tools/run_scenario.py --fixture FX-VILLAGE --seed 507 \
  --record Pack/DuelMasterBattle_Build_Pack/tracking/gates/G05/fx_village_record.json
```

## Archived quest snapshots

The `scenarios/*.json` files under this packet are **historical** shortage-quest
saves. They are not the current G05 acceptance path. To revisit the prototype:

```bash
DMB_FIXTURE=FX-VILLAGE-QUEST DMB_SEED=507 bash tools/play_g05.sh
```
