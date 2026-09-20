# G05 — Procedural village / quest / duel playtest

**Status:** AWAITING_HUMAN  
**Stop point:** T096  
**Scenario:** FX-VILLAGE  
**Branch:** `feature/g05-village-quest`  
**Launch:** `bash tools/play_g05.sh` → playable Overworld village (not a status screen)

## What you should see immediately

- Terrain / village streets
- Player character near the quiet factory
- Mara (authoritative Python person id)
- Factory door labeled quiet/working from Python shortage state
- Ridge manifestation (demon cube)
- Sluice works entrance
- Interaction labels + movement controls

## What to play

1. Launch without reading optional hints.
2. Walk to Mara; observe / talk. Infer why work stopped (no debug causal dump).
3. On one save, challenge the ridge manifestation (retained GameBoard duel). Confirm factory resumes and Mara acknowledges Route A; demon is gone.
4. On a fresh save, enter the sluice works; pick up the handle; push the box; place handle; open gate/actuator. Confirm Route B dialogue does **not** claim the demon was cleared.
5. Drop/recover the handle; save/reload; re-enter village — entity IDs must stay stable.
6. Optional: world-resolved / destroyed-target scenario snapshots under `scenarios/`.

## Automated evidence (necessary, not decisive)

```bash
python3 tools/check.py --gate G05
```

Includes `run_g05_playable.gd` (presentation + Mara/factory IDs + talk + sluice enter + demon lease start).

Agents cannot self-PASS the experience question. Only Joe's explicit  
`G05 PASS — <commit>` clears this gate.

## Same presentation path

- `tools/play_g05.sh` → `g05_shell.tscn` (Python + Overworld)
- Village Test Menu → **FX-VILLAGE (Python-backed)** → same shell

## Experience question

Would you want to meet these people and solve another such problem?
